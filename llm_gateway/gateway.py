"""Unified LLM gateway: route requests to local (Ollama) or cloud (OpenAI-compatible) providers."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import httpx


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
        self.base_url = (base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")).rstrip("/")

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
            usage={"eval_count": data.get("eval_count"), "prompt_eval_count": data.get("prompt_eval_count")},
        )


class OpenAICompatibleProvider(BaseProvider):
    """Any OpenAI-compatible endpoint (OpenAI, DeepSeek, Qwen, vLLM...)."""

    name = "openai"

    def __init__(self, base_url: str | None = None, api_key: str | None = None):
        self.base_url = (base_url or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")).rstrip("/")
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")

    async def chat(self, messages: list[Message], model: str, **kw) -> LLMResponse:
        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": kw.get("temperature", 0.3),
        }
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(f"{self.base_url}/chat/completions", json=payload, headers=headers)
            r.raise_for_status()
            data = r.json()
        return LLMResponse(
            content=data["choices"][0]["message"]["content"],
            model=model,
            provider=self.name,
            usage=data.get("usage", {}),
        )


class LLMGateway:
    """Single entry point. Picks provider by prefix: 'ollama:model' or 'openai:model'."""

    def __init__(self):
        self.providers: dict[str, BaseProvider] = {
            "ollama": OllamaProvider(),
            "openai": OpenAICompatibleProvider(),
        }

    async def chat(self, messages: list[Message], model: str | None = None, **kw) -> LLMResponse:
        model = model or os.getenv("DEFAULT_MODEL", "ollama:qwen2.5:7b")
        if ":" in model and model.split(":", 1)[0] in self.providers:
            provider_name, model_name = model.split(":", 1)
        else:
            provider_name, model_name = "ollama", model
        provider = self.providers[provider_name]
        return await provider.chat(messages, model_name, **kw)

    async def health(self) -> dict[str, bool]:
        status = {}
        async with httpx.AsyncClient(timeout=5) as client:
            try:
                r = await client.get(f"{self.providers['ollama'].base_url}/api/tags")
                status["ollama"] = r.status_code == 200
            except Exception:
                status["ollama"] = False
        status["openai"] = bool(self.providers["openai"].api_key)
        return status
