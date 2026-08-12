"""Shared pytest fixtures for all test modules."""

from __future__ import annotations

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure project root on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ─── Register all tools once per session ─────────────────────────────────────


@pytest.fixture(scope="session", autouse=True)
def register_tools():
    import tools.accounting  # noqa: F401
    import tools.builtin  # noqa: F401
    import tools.communication  # noqa: F401
    import tools.voice  # noqa: F401


# ─── Mock LLM Gateway ────────────────────────────────────────────────────────


@pytest.fixture
def mock_gateway():
    """A Gateway that returns a canned response without hitting any LLM."""
    from llm_gateway.gateway import LLMGateway, LLMResponse

    gw = MagicMock(spec=LLMGateway)
    gw.chat = AsyncMock(
        return_value=LLMResponse(
            content="Mocked LLM response",
            model="mock:model",
            provider="mock",
        )
    )
    gw.chat_stream = AsyncMock(return_value=iter([]))
    gw.embed = AsyncMock(return_value=[[0.1] * 768])
    gw.health = AsyncMock(
        return_value={
            "ollama": False,
            "openai": False,
            "anthropic": False,
            "gemini": False,
            "huggingface": False,
        }
    )
    return gw


# ─── In-memory Knowledge Store ───────────────────────────────────────────────


@pytest.fixture
def tmp_knowledge_store(tmp_path):
    """A KnowledgeStore backed by a temp SQLite DB."""
    with patch.dict(os.environ, {"KNOWLEDGE_DB_PATH": str(tmp_path / "test_knowledge.db")}):
        from memory.store import KnowledgeStore

        yield KnowledgeStore()


# ─── In-memory Conversation Store ────────────────────────────────────────────


@pytest.fixture
def tmp_conv_store(tmp_path):
    """A ConversationStore backed by a temp SQLite DB."""
    with patch.dict(os.environ, {"CONV_DB_PATH": str(tmp_path / "test_conv.db")}):
        from memory.conversation import ConversationStore

        yield ConversationStore(str(tmp_path / "test_conv.db"))


# ─── FastAPI test client ──────────────────────────────────────────────────────


@pytest.fixture
def test_client(mock_gateway):
    """A TestClient for the FastAPI app with mocked LLM gateway."""
    from httpx import ASGITransport, AsyncClient

    from api import main as api_main

    # Inject mock gateway
    api_main.gateway = mock_gateway
    app = api_main.app

    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture
def admin_headers():
    return {"X-API-Key": os.getenv("ADMIN_KEY", "dev-admin-key")}


@pytest.fixture
def user_headers():
    return {"X-API-Key": os.getenv("USER_KEY", "dev-user-key")}
