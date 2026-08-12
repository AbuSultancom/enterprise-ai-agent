"""Unified LLM gateway: route requests to Ollama, OpenAI-compatible, HuggingFace,
Anthropic Claude, or Google Gemini providers, with automatic fallback and retry."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)


# ─── Retry helper ─────────────────────────────────────────────────────────────


async def _retry(coro_fn, retries: int = 3, base_delay: float = 1.0):
    """Run *coro_fn()* with exponential-backoff retries on transient errors."""
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            return await coro_fn()
        except (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError) as exc:
            last_err = exc
            if attempt < retries - 1:
                delay = base_delay * (2**attempt)
                logger.warning(
                    "LLM request failed (attempt %d/%d), retrying in %.1fs: %s",
                    attempt + 1,
                    retries,
                    delay,
                    exc,
                )
                await asyncio.sleep(delay)
    raise last_err  # type: ignore[misc]


@dataclass
class Message:
    role: str  # "system" | "user" | "assistant" | "tool"
    content: str
    name: str | None = None


@dataclass
class LLMResponse:
    content: str
    model: str
    provider: str
    usage: dict[str, Any] = field(default_factory=dict)


class BaseProvider:
    name = "base"

    async def chat(self, messages: list[Message], model: str, **kw) -> LLMResponse:
        raise NotImplementedError


class OllamaProvider(BaseProvider):
    """Local models via Ollama — data never leaves the company network."""

    name = "ollama"

    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")).rstrip(
            "/"
        )

    async def chat(self, messages: list[Message], model: str, **kw) -> LLMResponse:
        payload = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
            "options": {"temperature": kw.get("temperature", 0.3)},
        }
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(f"{self.base_url}/api/chat", json=payload)
            r.raise_for_status()
            data = r.json()
        return LLMResponse(
            content=data["message"]["content"],
            model=model,
            provider=self.name,
            usage={
                "eval_count": data.get("eval_count"),
                "prompt_eval_count": data.get("prompt_eval_count"),
            },
        )


class OpenAICompatibleProvider(BaseProvider):
    """Any OpenAI-compatible endpoint (OpenAI, DeepSeek, Qwen, vLLM...)."""

    name = "openai"

    def __init__(self, base_url: str | None = None, api_key: str | None = None):
        self.base_url = (
            base_url or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        ).rstrip("/")
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")

    async def chat(self, messages: list[Message], model: str, **kw) -> LLMResponse:
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": kw.get("temperature", 0.3),
        }
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(
                f"{self.base_url}/chat/completions", json=payload, headers=headers
            )
            r.raise_for_status()
            data = r.json()
        return LLMResponse(
            content=data["choices"][0]["message"]["content"],
            model=model,
            provider=self.name,
            usage=data.get("usage", {}),
        )

    async def chat_vision(
        self,
        text: str,
        image_data: str,
        image_type: str = "url",
        model: str | None = None,
        max_tokens: int = 2000,
    ) -> str:
        """Send an image + question to a vision-capable model.

        Args:
            text: The question/prompt about the image.
            image_data: URL string or base64-encoded image data.
            image_type: "url" for a direct HTTPS URL, "base64" or "base64:image/png" for
                        base64 data (may include MIME prefix).
            model: Vision-capable model name (defaults to VISION_MODEL env, then current model).
            max_tokens: Max tokens in the response.

        Returns:
            The model's text response.
        """
        model = model or os.getenv("VISION_MODEL") or os.getenv("DEFAULT_MODEL", "gpt-4o")
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        content_parts: list[dict] = []
        content_parts.append({"type": "text", "text": text})

        if image_type.startswith("base64"):
            # Extract MIME type if provided as "base64:image/jpeg"
            parts = image_type.split(":", 1)
            mime = parts[1] if len(parts) > 1 else "image/jpeg"
            content_parts.append(
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{image_data}"}}
            )
        else:
            content_parts.append({"type": "image_url", "image_url": {"url": image_data}})

        payload = {
            "model": model,
            "messages": [{"role": "user", "content": content_parts}],
            "max_tokens": max_tokens,
            "temperature": 0.2,
        }
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(
                f"{self.base_url}/chat/completions", json=payload, headers=headers
            )
            r.raise_for_status()
            data = r.json()
        return data["choices"][0]["message"]["content"]


class HuggingFaceProvider(BaseProvider):
    """Hugging Face Inference API — free tier for many models, better rate limits with HF_TOKEN.

    Two endpoints:
      - /v1/chat/completions  for TGI (Text Generation Inference) servers that expose
        an OpenAI-compatible endpoint.
      - /models/{model_name}   fallback: generic HF text-generation API for
        models that don't expose the chat endpoint.
    """

    name = "huggingface"

    def __init__(self, base_url: str | None = None, api_key: str | None = None):
        self.base_url = (
            base_url or os.getenv("HF_BASE_URL", "https://api-inference.huggingface.co")
        ).rstrip("/")
        self.api_key = api_key or os.getenv("HF_TOKEN", "")

    async def chat(self, messages: list[Message], model: str, **kw) -> LLMResponse:
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        # Build the prompt from messages (HF text-generation format)
        prompt_parts = []
        for m in messages:
            if m.role == "system":
                prompt_parts.append(f"[INST] <<SYS>>\n{m.content}\n<</SYS>>\n\n")
            elif m.role == "user":
                prompt_parts.append(f"{m.content} [/INST]")
            elif m.role == "assistant":
                prompt_parts.append(f"{m.content} </s><s>[INST] ")

        prompt = "".join(prompt_parts) if prompt_parts else messages[-1].content

        payload: dict = {
            "inputs": prompt,
            "parameters": {
                "temperature": kw.get("temperature", 0.3),
                "max_new_tokens": kw.get("max_tokens", 1024),
                "return_full_text": False,
            },
        }

        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(
                f"{self.base_url}/models/{model}",
                json=payload,
                headers=headers,
            )
            r.raise_for_status()
            data = r.json()

        # Parse HF response — varies by model
        if isinstance(data, list) and len(data) > 0:
            generated = data[0].get("generated_text", str(data[0]))
        elif isinstance(data, dict):
            generated = data.get("generated_text", str(data))
        else:
            generated = str(data)

        return LLMResponse(
            content=generated,
            model=model,
            provider=self.name,
            usage={},
        )


class AnthropicProvider(BaseProvider):
    """Anthropic Claude via the native Messages API.

    Set ANTHROPIC_API_KEY in your .env to enable.
    Models: claude-3-5-sonnet-20241022, claude-3-haiku-20240307, etc.
    """

    name = "anthropic"
    BASE_URL = "https://api.anthropic.com/v1"
    API_VERSION = "2023-06-01"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")

    async def chat(self, messages: list[Message], model: str, **kw) -> LLMResponse:
        if not self.api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set")

        # Separate system message from user/assistant messages
        system_text = ""
        anthropic_messages: list[dict] = []
        for m in messages:
            if m.role == "system":
                system_text = m.content
            else:
                anthropic_messages.append({"role": m.role, "content": m.content})

        payload: dict = {
            "model": model,
            "max_tokens": kw.get("max_tokens", 4096),
            "temperature": kw.get("temperature", 0.3),
            "messages": anthropic_messages,
        }
        if system_text:
            payload["system"] = system_text

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": self.API_VERSION,
            "Content-Type": "application/json",
        }

        async def _call():
            async with httpx.AsyncClient(timeout=120) as client:
                r = await client.post(f"{self.BASE_URL}/messages", json=payload, headers=headers)
                r.raise_for_status()
                data = r.json()
            return LLMResponse(
                content=data["content"][0]["text"],
                model=model,
                provider=self.name,
                usage=data.get("usage", {}),
            )

        return await _retry(_call)


class GeminiProvider(BaseProvider):
    """Google Gemini via the Generative Language REST API.

    Set GEMINI_API_KEY in your .env to enable.
    Models: gemini-2.0-flash, gemini-1.5-pro, gemini-1.5-flash, etc.
    """

    name = "gemini"
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")

    async def chat(self, messages: list[Message], model: str, **kw) -> LLMResponse:
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is not set")

        # Convert to Gemini content format
        contents: list[dict] = []
        system_text = ""
        for m in messages:
            if m.role == "system":
                system_text = m.content
                continue
            role = "model" if m.role == "assistant" else "user"
            contents.append({"role": role, "parts": [{"text": m.content}]})

        payload: dict = {
            "contents": contents,
            "generationConfig": {
                "temperature": kw.get("temperature", 0.3),
                "maxOutputTokens": kw.get("max_tokens", 4096),
            },
        }
        if system_text:
            payload["systemInstruction"] = {"parts": [{"text": system_text}]}

        url = f"{self.BASE_URL}/models/{model}:generateContent?key={self.api_key}"

        async def _call():
            async with httpx.AsyncClient(timeout=120) as client:
                r = await client.post(url, json=payload)
                r.raise_for_status()
                data = r.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            usage = data.get("usageMetadata", {})
            return LLMResponse(
                content=text,
                model=model,
                provider=self.name,
                usage=usage,
            )

        return await _retry(_call)


class PIIMasker:
    """Enterprise PII and Sensitive Data Masker.
    Masks sensitive data (credit cards, national IDs, tokens, keys) before sending payloads to cloud LLMs.
    """

    CREDIT_CARD_REGEX = re.compile(r"\b(?:\d[ -]*?){13,16}\b")
    TOKEN_REGEX = re.compile(
        r'(?:bearer\s+[a-zA-Z0-9_\-\.=]+|api[_\-]?key["\s:=]+[a-zA-Z0-9_\-]{16,})', re.IGNORECASE
    )
    SAUDI_ID_REGEX = re.compile(r"\b[12]\d{9}\b")

    @classmethod
    def mask_text(cls, text: str) -> str:
        if not text or not isinstance(text, str):
            return text
        text = cls.CREDIT_CARD_REGEX.sub("[REDACTED_CREDIT_CARD]", text)
        text = cls.TOKEN_REGEX.sub("[REDACTED_TOKEN]", text)
        text = cls.SAUDI_ID_REGEX.sub("[REDACTED_NATIONAL_ID]", text)
        return text

    @classmethod
    def mask_messages(cls, messages: list[Message]) -> list[Message]:
        return [
            Message(role=m.role, content=cls.mask_text(m.content), name=m.name) for m in messages
        ]


class LLMGateway:
    """Single entry point. Picks provider by prefix:
    'ollama:model', 'openai:model', 'anthropic:model', 'gemini:model',
    or 'huggingface:model', with automatic fallback and retry."""

    def __init__(self):
        self.providers: dict[str, BaseProvider] = {
            "ollama": OllamaProvider(),
            "openai": OpenAICompatibleProvider(),
            "huggingface": HuggingFaceProvider(),
            "anthropic": AnthropicProvider(),
            "gemini": GeminiProvider(),
        }

    async def chat(
        self, messages: list[Message], model: str | None = None, mask_pii: bool = True, **kw
    ) -> LLMResponse:
        model = model or os.getenv("DEFAULT_MODEL", "ollama:qwen2.5:7b")

        # Apply PII masking if requested
        if mask_pii:
            messages = PIIMasker.mask_messages(messages)

        if ":" in model and model.split(":", 1)[0] in self.providers:
            provider_name, model_name = model.split(":", 1)
        else:
            provider_name, model_name = "ollama", model

        # Primary attempt
        try:
            provider = self.providers[provider_name]
            return await provider.chat(messages, model_name, **kw)
        except Exception as primary_err:
            # Fallback mechanism: if primary provider fails (e.g. Ollama down/timeout), fallback to available provider
            fallback_order = [p for p in ["openai", "huggingface", "ollama"] if p != provider_name]
            for fb in fallback_order:
                fb_provider = self.providers[fb]
                if fb == "openai" and not fb_provider.api_key:
                    continue
                try:
                    fb_model = (
                        os.getenv("OPENAI_MODEL", "gpt-4o-mini") if fb == "openai" else model_name
                    )
                    res = await fb_provider.chat(messages, fb_model, **kw)
                    res.content = f"*(Fallback via {fb})*\n\n" + res.content
                    return res
                except Exception:
                    continue
            raise primary_err

    async def health(self) -> dict[str, bool]:
        status: dict[str, bool] = {}
        async with httpx.AsyncClient(timeout=5) as client:
            try:
                r = await client.get(f"{self.providers['ollama'].base_url}/api/tags")
                status["ollama"] = r.status_code == 200
            except Exception:
                status["ollama"] = False
        status["openai"] = bool(self.providers["openai"].api_key)
        status["anthropic"] = bool(self.providers["anthropic"].api_key)
        status["gemini"] = bool(self.providers["gemini"].api_key)
        status["huggingface"] = bool(self.providers["huggingface"].api_key)
        return status

    async def chat_vision(
        self,
        text: str,
        image_data: str,
        image_type: str = "url",
        model: str | None = None,
        max_tokens: int = 2000,
    ) -> str:
        """Analyze an image through a vision-capable model.

        Args:
            text: The question or prompt about the image.
            image_data: URL string or base64-encoded image data.
            image_type: "url" for a direct HTTPS image URL, "base64" for base64 data.
            model: Vision model name (defaults to VISION_MODEL env, then DEFAULT_MODEL).
            max_tokens: Max tokens in the response.

        Returns:
            The model's text analysis of the image.
        """
        provider = self.providers["openai"]
        return await provider.chat_vision(text, image_data, image_type, model, max_tokens)

    # ---- Streaming: yields text deltas as they arrive ----
    async def chat_stream(
        self, messages: list[Message], model: str | None = None, **kw
    ) -> AsyncGenerator[str, None]:
        model = model or os.getenv("DEFAULT_MODEL", "ollama:qwen2.5:7b")
        if ":" in model and model.split(":", 1)[0] in self.providers:
            provider_name, model_name = model.split(":", 1)
        else:
            provider_name, model_name = "ollama", model

        if provider_name == "ollama":
            url = f"{self.providers['ollama'].base_url}/api/chat"
            payload = {
                "model": model_name,
                "stream": True,
                "messages": [{"role": m.role, "content": m.content} for m in messages],
                "options": {"temperature": kw.get("temperature", 0.3)},
            }
            async with httpx.AsyncClient(timeout=300) as client:
                async with client.stream("POST", url, json=payload) as r:
                    async for line in r.aiter_lines():
                        if line.strip():
                            try:
                                chunk = json.loads(line)
                                delta = chunk.get("message", {}).get("content", "")
                                if delta:
                                    yield delta
                            except json.JSONDecodeError:
                                continue
        elif provider_name == "huggingface":
            # HF Inference API does not support streaming natively —
            # fall back to a single chat call and yield the full response.
            p = self.providers["huggingface"]
            result = await p.chat(messages, model_name, **kw)
            yield result.content
        else:
            p = self.providers["openai"]
            url = f"{p.base_url}/chat/completions"
            headers = {}
            if p.api_key:
                headers["Authorization"] = f"Bearer {p.api_key}"
            payload = {
                "model": model_name,
                "stream": True,
                "messages": [{"role": m.role, "content": m.content} for m in messages],
                "temperature": kw.get("temperature", 0.3),
            }
            async with httpx.AsyncClient(timeout=300) as client:
                async with client.stream("POST", url, json=payload, headers=headers) as r:
                    if r.status_code != 200:
                        yield f"[Stream error: HTTP {r.status_code}]"
                        return
                    async for line in r.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                            delta = chunk["choices"][0].get("delta", {}).get("content", "")
                            if delta:
                                yield delta
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue

    # ---- Embeddings (Ollama first, then OpenAI-compatible; None if unavailable) ----
    async def embed(self, texts: list[str], model: str | None = None) -> list[list[float]] | None:
        embed_model = model or os.getenv("EMBED_MODEL", "nomic-embed-text")
        # 1) try local Ollama
        try:
            base = self.providers["ollama"].base_url
            async with httpx.AsyncClient(timeout=60) as client:
                r = await client.post(
                    f"{base}/api/embed", json={"model": embed_model, "input": texts}
                )
                r.raise_for_status()
                return r.json().get("embeddings")
        except Exception:
            pass
        # 2) try OpenAI-compatible embeddings (if key configured)
        p = self.providers["openai"]
        if p.api_key:
            try:
                headers = {}
                if p.api_key:
                    headers["Authorization"] = f"Bearer {p.api_key}"
                async with httpx.AsyncClient(timeout=60) as client:
                    r = await client.post(
                        f"{p.base_url}/embeddings",
                        headers=headers,
                        json={
                            "model": os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small"),
                            "input": texts,
                        },
                    )
                    r.raise_for_status()
                    data = r.json().get("data", [])
                    return [d["embedding"] for d in sorted(data, key=lambda x: x["index"])]
            except Exception:
                pass
        return None
