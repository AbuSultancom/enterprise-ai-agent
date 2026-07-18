"""Unified LLM gateway: route requests to local (Ollama) or cloud (OpenAI-compatible) providers."""
from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator

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
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
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

    async def chat_vision(self, text: str, image_data: str, image_type: str = "url",
                          model: str | None = None, max_tokens: int = 2000) -> str:
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
            content_parts.append({
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{image_data}"}
            })
        else:
            content_parts.append({
                "type": "image_url",
                "image_url": {"url": image_data}
            })

        payload = {
            "model": model,
            "messages": [{"role": "user", "content": content_parts}],
            "max_tokens": max_tokens,
            "temperature": 0.2,
        }
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(f"{self.base_url}/chat/completions", json=payload, headers=headers)
            r.raise_for_status()
            data = r.json()
        return data["choices"][0]["message"]["content"]


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

    async def chat_vision(self, text: str, image_data: str, image_type: str = "url",
                          model: str | None = None, max_tokens: int = 2000) -> str:
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
    async def chat_stream(self, messages: list[Message], model: str | None = None, **kw) -> AsyncGenerator[str, None]:
        model = model or os.getenv("DEFAULT_MODEL", "ollama:qwen2.5:7b")
        if ":" in model and model.split(":", 1)[0] in self.providers:
            provider_name, model_name = model.split(":", 1)
        else:
            provider_name, model_name = "ollama", model

        if provider_name == "ollama":
            url = f"{self.providers['ollama'].base_url}/api/chat"
            payload = {"model": model_name, "stream": True,
                       "messages": [{"role": m.role, "content": m.content} for m in messages],
                       "options": {"temperature": kw.get("temperature", 0.3)}}
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
        else:
            p = self.providers["openai"]
            url = f"{p.base_url}/chat/completions"
            headers = {}
            if p.api_key:
                headers["Authorization"] = f"Bearer {p.api_key}"
            payload = {"model": model_name, "stream": True,
                       "messages": [{"role": m.role, "content": m.content} for m in messages],
                       "temperature": kw.get("temperature", 0.3)}
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
                r = await client.post(f"{base}/api/embed", json={"model": embed_model, "input": texts})
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
                    r = await client.post(f"{p.base_url}/embeddings", headers=headers,
                                          json={"model": os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small"),
                                                "input": texts})
                    r.raise_for_status()
                    data = r.json().get("data", [])
                    return [d["embedding"] for d in sorted(data, key=lambda x: x["index"])]
            except Exception:
                pass
        return None
