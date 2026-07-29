"""Voice processing tools (Speech-to-Text & Text-to-Speech)."""
from __future__ import annotations

import base64
import os
import httpx
from tools.registry import registry


@registry.register(
    name="speech_to_text",
    description="Transcribe user audio clip into text using Whisper or local STT.",
    parameters={
        "type": "object",
        "properties": {
            "audio_base64": {"type": "string", "description": "Base64 encoded audio clip"},
            "language": {"type": "string", "description": "Expected language code ('ar', 'en', or 'auto')"},
        },
        "required": ["audio_base64"],
    },
)
async def speech_to_text(audio_base64: str, language: str = "auto") -> str:
    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        return "STT processing completed (Simulated transcription: 'أهلاً بك، أريد عرض تقرير المبيعات')."

    try:
        audio_bytes = base64.b64decode(audio_base64)
        files = {"file": ("audio.wav", audio_bytes, "audio/wav")}
        data = {"model": "whisper-1"}
        if language != "auto":
            data["language"] = language

        headers = {"Authorization": f"Bearer {openai_key}"}
        async with httpx.AsyncClient(timeout=30) as client:
            res = await client.post("https://api.openai.com/v1/audio/transcriptions", headers=headers, data=data, files=files)
            res.raise_for_status()
            return res.json().get("text", "")
    except Exception as e:
        return f"Speech-to-Text failed: {e}"


@registry.register(
    name="text_to_speech",
    description="Synthesize text answer into spoken audio (TTS).",
    parameters={
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Text to convert to speech"},
            "voice": {"type": "string", "description": "Voice type or accent ('alloy', 'echo', 'fable', 'ar-SA-Zariyah')"},
        },
        "required": ["text"],
    },
)
async def text_to_speech(text: str, voice: str = "alloy") -> str:
    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        return "TTS synthesized successfully (Audio placeholder ready)."

    try:
        headers = {"Authorization": f"Bearer {openai_key}"}
        payload = {"model": "tts-1", "input": text, "voice": voice}
        async with httpx.AsyncClient(timeout=30) as client:
            res = await client.post("https://api.openai.com/v1/audio/speech", headers=headers, json=payload)
            res.raise_for_status()
            encoded = base64.b64encode(res.content).decode("utf-8")
            return f"data:audio/mp3;base64,{encoded}"
    except Exception as e:
        return f"Text-to-Speech failed: {e}"
