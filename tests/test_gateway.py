"""Tests for LLM gateway: providers, retry, PII masking, fallback."""
from __future__ import annotations

import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from llm_gateway.gateway import (
    AnthropicProvider,
    GeminiProvider,
    LLMGateway,
    LLMResponse,
    Message,
    PIIMasker,
    _retry,
)


# ─── PII Masker ───────────────────────────────────────────────────────────────

class TestPIIMaskerExtended:
    """Extended PII masking tests."""

    def test_email_preserved(self):
        """Emails should NOT be masked (not a PII target in current rules)."""
        text = "Send to john@example.com"
        assert PIIMasker.mask_text(text) == text

    def test_multiple_credit_cards(self):
        text = "Card1: 4532 1234 5678 9012 and Card2: 5500 0000 0000 0004"
        masked = PIIMasker.mask_text(text)
        assert "4532" not in masked
        assert "5500" not in masked
        assert masked.count("[REDACTED_CREDIT_CARD]") == 2

    def test_empty_string(self):
        assert PIIMasker.mask_text("") == ""

    def test_none_input(self):
        assert PIIMasker.mask_text(None) is None  # type: ignore[arg-type]

    def test_mask_messages_list(self):
        msgs = [
            Message(role="user", content="My ID is 1098765432"),
            Message(role="assistant", content="OK"),
        ]
        masked = PIIMasker.mask_messages(msgs)
        assert "[REDACTED_NATIONAL_ID]" in masked[0].content
        assert masked[1].content == "OK"


# ─── Retry helper ────────────────────────────────────────────────────────────

class TestRetryHelper:
    """Tests for _retry exponential backoff."""

    def test_succeeds_first_try(self):
        calls = 0

        async def fn():
            nonlocal calls
            calls += 1
            return "ok"

        result = asyncio.run(_retry(fn, retries=3, base_delay=0))
        assert result == "ok"
        assert calls == 1

    def test_retries_on_network_error(self):
        import httpx
        calls = 0

        async def fn():
            nonlocal calls
            calls += 1
            if calls < 3:
                raise httpx.NetworkError("connection refused")
            return "ok"

        result = asyncio.run(_retry(fn, retries=3, base_delay=0))
        assert result == "ok"
        assert calls == 3

    def test_raises_after_max_retries(self):
        import httpx

        async def fn():
            raise httpx.TimeoutException("timeout", request=None)  # type: ignore[arg-type]

        with pytest.raises(httpx.TimeoutException):
            asyncio.run(_retry(fn, retries=2, base_delay=0))


# ─── LLMGateway provider selection ──────────────────────────────────────────

class TestGatewayProviderRouting:
    """Test that gateway routes to the correct provider by model prefix."""

    def test_routes_to_ollama(self):
        gw = LLMGateway()
        mock_resp = LLMResponse(content="hello", model="qwen2.5:7b", provider="ollama")
        with patch.object(gw.providers["ollama"], "chat", new=AsyncMock(return_value=mock_resp)):
            result = asyncio.run(gw.chat([Message("user", "hi")], model="ollama:qwen2.5:7b", mask_pii=False))
        assert result.provider == "ollama"

    def test_routes_to_openai(self):
        gw = LLMGateway()
        mock_resp = LLMResponse(content="hello", model="gpt-4o-mini", provider="openai")
        with patch.object(gw.providers["openai"], "chat", new=AsyncMock(return_value=mock_resp)):
            result = asyncio.run(gw.chat([Message("user", "hi")], model="openai:gpt-4o-mini", mask_pii=False))
        assert result.provider == "openai"

    def test_routes_to_anthropic(self):
        gw = LLMGateway()
        mock_resp = LLMResponse(content="hello", model="claude-3-haiku", provider="anthropic")
        with patch.object(gw.providers["anthropic"], "chat", new=AsyncMock(return_value=mock_resp)):
            result = asyncio.run(gw.chat(
                [Message("user", "hi")], model="anthropic:claude-3-haiku", mask_pii=False
            ))
        assert result.provider == "anthropic"

    def test_routes_to_gemini(self):
        gw = LLMGateway()
        mock_resp = LLMResponse(content="hello", model="gemini-2.0-flash", provider="gemini")
        with patch.object(gw.providers["gemini"], "chat", new=AsyncMock(return_value=mock_resp)):
            result = asyncio.run(gw.chat(
                [Message("user", "hi")], model="gemini:gemini-2.0-flash", mask_pii=False
            ))
        assert result.provider == "gemini"

    def test_fallback_on_primary_failure(self):
        import httpx
        gw = LLMGateway()
        openai_resp = LLMResponse(content="fallback", model="gpt-4o-mini", provider="openai")

        async def run():
            with (
                patch.object(gw.providers["ollama"], "chat", new=AsyncMock(side_effect=httpx.NetworkError("down"))),
                patch.object(gw.providers["openai"], "chat", new=AsyncMock(return_value=openai_resp)),
                patch.object(gw.providers["openai"], "api_key", "sk-fake"),
            ):
                return await gw.chat([Message("user", "hi")], model="ollama:qwen2.5:7b", mask_pii=False)

        result = asyncio.run(run())
        assert result.provider == "openai"

    def test_providers_registered(self):
        gw = LLMGateway()
        assert "ollama" in gw.providers
        assert "openai" in gw.providers
        assert "anthropic" in gw.providers
        assert "gemini" in gw.providers
        assert "huggingface" in gw.providers

    def test_anthropic_provider_raises_without_key(self):
        p = AnthropicProvider(api_key="")
        with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
            asyncio.run(p.chat([Message("user", "hi")], model="claude-3-haiku"))

    def test_gemini_provider_raises_without_key(self):
        p = GeminiProvider(api_key="")
        with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
            asyncio.run(p.chat([Message("user", "hi")], model="gemini-2.0-flash"))


# ─── Health check ────────────────────────────────────────────────────────────

class TestGatewayHealth:
    """Test gateway health() method."""

    def test_health_returns_dict_with_all_providers(self):
        gw = LLMGateway()

        async def run():
            with patch("httpx.AsyncClient") as mock_cls:
                mock_resp = MagicMock()
                mock_resp.status_code = 200
                mock_ctx = AsyncMock()
                mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
                mock_ctx.__aexit__ = AsyncMock(return_value=None)
                mock_ctx.get = AsyncMock(return_value=mock_resp)
                mock_cls.return_value = mock_ctx
                return await gw.health()

        status = asyncio.run(run())
        assert "ollama" in status
        assert "openai" in status
        assert "anthropic" in status
        assert "gemini" in status
        assert "huggingface" in status
        assert isinstance(status["ollama"], bool)
