"""Built-in tools shipped with the platform. Add your own in tools/custom/."""
from __future__ import annotations

import datetime
import math

import httpx

from .registry import registry


@registry.register(
    description="Get the current date and time.",
    parameters={},
)
def get_current_time() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


@registry.register(
    description="Evaluate a math expression safely (e.g. '2 * (3 + 4)').",
    parameters={"expression": {"type": "str", "description": "Math expression"}},
)
def calculator(expression: str) -> str:
    allowed = {k: getattr(math, k) for k in dir(math) if not k.startswith("_")}
    allowed.update({"abs": abs, "round": round, "min": min, "max": max})
    try:
        return str(eval(expression, {"__builtins__": {}}, allowed))  # noqa: S307 - sandboxed namespace
    except Exception as e:
        return f"Error: {e}"


@registry.register(
    description="Search the web and return top results (title + snippet + url).",
    parameters={"query": {"type": "str", "description": "Search query"}},
)
async def web_search(query: str) -> str:
    url = "https://api.duckduckgo.com/"
    params = {"q": query, "format": "json", "no_html": 1}
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(url, params=params)
        data = r.json()
    results = [data.get("AbstractText", "")]
    for topic in data.get("RelatedTopics", [])[:5]:
        if isinstance(topic, dict) and topic.get("Text"):
            results.append(topic["Text"])
    return "\n".join(filter(None, results)) or "No results found."


@registry.register(
    description="Read a text file from the shared workspace volume.",
    parameters={"path": {"type": "str", "description": "File path inside /data/workspace"}},
)
def read_file(path: str) -> str:
    base = "/data/workspace"
    safe_path = path.replace("..", "").lstrip("/")
    try:
        with open(f"{base}/{safe_path}", encoding="utf-8") as f:
            return f.read()[:8000]
    except Exception as e:
        return f"Error: {e}"
