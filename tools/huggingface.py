"""Hugging Face tools: translation, summarization, and sentiment analysis.

Uses the free Hugging Face Inference API (no API key required, but adding
HF_TOKEN in your .env is recommended for higher rate limits).
"""

from __future__ import annotations

import os

import httpx

from .registry import registry

HF_API_BASE = "https://api-inference.huggingface.co/models"

# Model names
MODEL_AR_EN = "Helsinki-NLP/opus-mt-ar-en"   # Arabic → English
MODEL_EN_AR = "Helsinki-NLP/opus-mt-en-ar"   # English → Arabic
MODEL_SUMMARIZE = "facebook/bart-large-cnn"
MODEL_SENTIMENT = "cardiffnlp/twitter-roberta-base-sentiment-latest"


def _hf_headers() -> dict[str, str]:
    """Build headers; include HF_TOKEN if available for better rate limits."""
    headers = {}
    token = os.getenv("HF_TOKEN", "")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _detect_arabic(text: str) -> bool:
    """Heuristic: return True if text contains a significant amount of Arabic script."""
    arabic_chars = sum(1 for ch in text if "\u0600" <= ch <= "\u06ff")
    total_chars = len(text.replace(" ", ""))
    if total_chars == 0:
        return False
    return (arabic_chars / total_chars) > 0.3


# ─── translate_text ────────────────────────────────────────────────

@registry.register(
    description=(
        "Translate text between Arabic and English. Auto-detects direction; "
        "explicitly specify source_lang='ar' or 'en' to force direction."
    ),
    parameters={
        "text": {"type": "str", "description": "Text to translate"},
        "source_lang": {
            "type": "str",
            "description": "Source language: 'ar' (Arabic) or 'en' (English). "
                           "Leave empty for auto-detect.",
            "default": "",
        },
    },
)
async def translate_text(text: str, source_lang: str = "") -> str:
    """Translate between Arabic and English using Helsinki-NLP OPUS-MT models.

    Args:
        text: The text to translate.
        source_lang: 'ar' for Arabic→English, 'en' for English→Arabic.
                     If empty, the direction is auto-detected.

    Returns:
        Translated text.
    """
    text = text.strip()
    if not text:
        return "⚠️ No text provided for translation."

    # Determine direction
    if source_lang in ("ar", "arabic"):
        model = MODEL_AR_EN
        direction = "Arabic → English"
    elif source_lang in ("en", "english"):
        model = MODEL_EN_AR
        direction = "English → Arabic"
    else:
        if _detect_arabic(text):
            model = MODEL_AR_EN
            direction = "Arabic → English"
        else:
            model = MODEL_EN_AR
            direction = "English → Arabic"

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{HF_API_BASE}/{model}",
                json={"inputs": text},
                headers=_hf_headers(),
            )
            resp.raise_for_status()
            result = resp.json()

        # HF Inference API returns [{"translation_text": "..."}] for translation models
        if isinstance(result, list) and len(result) > 0:
            translated = result[0].get("translation_text", str(result[0]))
        elif isinstance(result, dict):
            translated = result.get("translation_text", result.get("generated_text", str(result)))
        else:
            translated = str(result)

        return f"🌐 {direction}\n{'─' * 40}\n{translated.strip()}"

    except httpx.HTTPStatusError as e:
        return f"⚠️ Translation failed (HTTP {e.response.status_code}): {e.response.text[:300]}"
    except Exception as e:
        return f"⚠️ Translation error: {e}"


# ─── summarize_text ─────────────────────────────────────────────────

@registry.register(
    description="Summarize long text into a concise paragraph using BART.",
    parameters={
        "text": {"type": "str", "description": "Long text to summarize"},
        "max_length": {
            "type": "number",
            "description": "Maximum summary length in tokens (default 130)",
            "default": 130,
        },
        "min_length": {
            "type": "number",
            "description": "Minimum summary length in tokens (default 30)",
            "default": 30,
        },
    },
)
async def summarize_text(
    text: str, max_length: float = 130, min_length: float = 30
) -> str:
    """Summarize long text using facebook/bart-large-cnn.

    Args:
        text: The text to summarize.
        max_length: Maximum length of the summary in tokens.
        min_length: Minimum length of the summary in tokens.

    Returns:
        Summarized text.
    """
    text = text.strip()
    if not text:
        return "⚠️ No text provided for summarization."

    # BART truncates long inputs, so warn if input is very long
    if len(text) > 4000:
        text = text[:4000]
        note = "\n\n⚠️ Text was truncated to 4000 characters (BART input limit)."
    else:
        note = ""

    try:
        payload = {
            "inputs": text,
            "parameters": {
                "max_length": int(max_length),
                "min_length": int(min_length),
                "do_sample": False,
            },
        }
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{HF_API_BASE}/{MODEL_SUMMARIZE}",
                json=payload,
                headers=_hf_headers(),
            )
            resp.raise_for_status()
            result = resp.json()

        # HF returns [{"summary_text": "..."}] for summarization models
        if isinstance(result, list) and len(result) > 0:
            summary = result[0].get("summary_text", str(result[0]))
        elif isinstance(result, dict):
            summary = result.get("summary_text", result.get("generated_text", str(result)))
        else:
            summary = str(result)

        return (
            f"📝 Summary\n{'─' * 40}\n{summary.strip()}"
            f"\n{'─' * 40}\n📊 Original: {len(text)} chars → Summary: {len(summary)} chars"
            f"{note}"
        )

    except httpx.HTTPStatusError as e:
        return f"⚠️ Summarization failed (HTTP {e.response.status_code}): {e.response.text[:300]}"
    except Exception as e:
        return f"⚠️ Summarization error: {e}"


# ─── analyze_sentiment ──────────────────────────────────────────────

SENTIMENT_LABELS_EN = {
    "LABEL_0": "Negative",
    "LABEL_1": "Neutral",
    "LABEL_2": "Positive",
}
SENTIMENT_LABELS_AR = {
    "LABEL_0": "سلبي",
    "LABEL_1": "محايد",
    "LABEL_2": "إيجابي",
}

SENTIMENT_EMOJI = {
    "Negative": "😞",
    "Neutral": "😐",
    "Positive": "😊",
    "سلبي": "😞",
    "محايد": "😐",
    "إيجابي": "😊",
}


@registry.register(
    description="Analyze sentiment of text: positive, negative, or neutral.",
    parameters={
        "text": {"type": "str", "description": "Text to analyze for sentiment"},
    },
)
async def analyze_sentiment(text: str) -> str:
    """Analyze sentiment using cardiffnlp/twitter-roberta-base-sentiment-latest.

    Returns bilingual (Arabic/English) output with confidence scores.

    Args:
        text: The text to analyze.

    Returns:
        Sentiment label and confidence scores.
    """
    text = text.strip()
    if not text:
        return "⚠️ No text provided for sentiment analysis."

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{HF_API_BASE}/{MODEL_SENTIMENT}",
                json={"inputs": text},
                headers=_hf_headers(),
            )
            resp.raise_for_status()
            result = resp.json()

        # HF returns [[{"label": "LABEL_X", "score": 0.98}, ...]] for this model
        if isinstance(result, list) and len(result) > 0:
            scores = result[0] if isinstance(result[0], list) else result
        else:
            scores = result if isinstance(result, list) else []

        # Build sorted list of labels with scores
        scored = []
        for item in scores:
            label = item.get("label", "?")
            score = item.get("score", 0.0)
            en_label = SENTIMENT_LABELS_EN.get(label, label)
            ar_label = SENTIMENT_LABELS_AR.get(label, label)
            scored.append((en_label, ar_label, score))

        scored.sort(key=lambda x: x[2], reverse=True)
        top = scored[0]
        emoji = SENTIMENT_EMOJI.get(top[0], "")

        lines = [
            f"🔍 Sentiment Analysis {emoji}",
            "─" * 40,
            f"Text: \"{text[:200]}{'...' if len(text) > 200 else ''}\"",
            "─" * 40,
            f"Result: {top[0]} / {top[1]}  (confidence: {top[2]*100:.1f}%)",
            "",
            "Details:",
        ]
        for en_label, ar_label, score in scored:
            bar = "█" * int(score * 20) + "░" * (20 - int(score * 20))
            lines.append(f"  {en_label:<10} {ar_label:<8} {bar} {score*100:.1f}%")

        return "\n".join(lines)

    except httpx.HTTPStatusError as e:
        return f"⚠️ Sentiment analysis failed (HTTP {e.response.status_code}): {e.response.text[:300]}"
    except Exception as e:
        return f"⚠️ Sentiment analysis error: {e}"
