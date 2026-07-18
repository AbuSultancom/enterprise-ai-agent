"""Built-in tools shipped with the platform. Add your own in tools/custom/."""
from __future__ import annotations

import datetime
import math
import os

import httpx

from .registry import registry


@registry.register(
    description="Search through past conversations to recall what was discussed.",
    parameters={"query": {"type": "str", "description": "What to search for in past conversations"}},
)
def search_conversations(query: str) -> str:
    from memory.conversation import get_store
    store = get_store()
    results = store.search(query, limit=8)
    if not results:
        return "No past conversations found matching that query."
    lines = []
    for r in results:
        lines.append(f"[{r['session_title']}] {r['role']}: {r['content'][:300]}")
    return "\n\n".join(lines)


@registry.register(
    description="Generate and save a text report to the data/reports folder. Returns the file path.",
    parameters={
        "title": {"type": "str", "description": "Report title (used as filename)"},
        "content": {"type": "str", "description": "Report body content in plain text or markdown"},
    },
)
def generate_report(title: str, content: str) -> str:
    import datetime
    reports_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                               "data", "reports")
    os.makedirs(reports_dir, exist_ok=True)
    safe_name = "".join(c for c in title if c.isalnum() or c in " _-").strip() or "report"
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{safe_name}_{timestamp}.md"
    filepath = os.path.join(reports_dir, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"# {title}\n\n")
        f.write(f"Generated: {datetime.datetime.now().isoformat()}\n\n")
        f.write(content)
    return f"Report saved to: {filepath}"


@registry.register(
    description="List all previously saved reports in the data/reports folder.",
    parameters={},
)
def list_reports() -> str:
    reports_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                               "data", "reports")
    if not os.path.isdir(reports_dir):
        return "No reports found yet."
    files = sorted(os.listdir(reports_dir), reverse=True)
    if not files:
        return "No reports found yet."
    lines = []
    for f in files[:20]:
        fpath = os.path.join(reports_dir, f)
        size = os.path.getsize(fpath)
        lines.append(f"- {f} ({size} bytes)")
    return "Saved reports:\n" + "\n".join(lines)


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
    """Evaluate a math expression using AST-based sandbox (no eval)."""
    import ast
    import operator as _operator

    allowed_ops = {
        ast.Add: _operator.add, ast.Sub: _operator.sub,
        ast.Mult: _operator.mul, ast.Div: _operator.truediv,
        ast.FloorDiv: _operator.floordiv, ast.Mod: _operator.mod,
        ast.Pow: _operator.pow, ast.USub: _operator.neg,
        ast.UAdd: _operator.pos,
    }
    allowed_funcs = {
        "abs": abs, "round": round, "min": min, "max": max,
        "pow": pow, "sum": sum,
    }
    # Expose math module functions by name
    allowed_funcs.update(
        {k: getattr(math, k) for k in dir(math) if not k.startswith("_")}
    )

    def _eval(node):
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            if node.id in allowed_funcs:
                return allowed_funcs[node.id]
            raise ValueError(f"Unknown identifier: {node.id}")
        if isinstance(node, ast.Call):
            func = _eval(node.func)
            args = [_eval(a) for a in node.args]
            return func(*args)
        if isinstance(node, ast.BinOp):
            op = allowed_ops.get(type(node.op))
            if op is None:
                raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
            return op(_eval(node.left), _eval(node.right))
        if isinstance(node, ast.UnaryOp):
            op = allowed_ops.get(type(node.op))
            if op is None:
                raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")
            return op(_eval(node.operand))
        if isinstance(node, ast.List):
            return [_eval(e) for e in node.elts]
        raise ValueError(f"Unsupported syntax: {type(node).__name__}")

    try:
        tree = ast.parse(expression.strip(), mode="eval")
        return str(_eval(tree))
    except ValueError as e:
        return f"Error: {e}"
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
    import os.path
    base = os.getenv("WORKSPACE_PATH", "/data/workspace")
    # Resolve to an absolute path and ensure it stays under the workspace base
    abs_base = os.path.abspath(base)
    requested = os.path.normpath(os.path.join(abs_base, path))
    if not requested.startswith(abs_base + os.sep) and requested != abs_base:
        return f"Error: path '{path}' escapes the workspace boundary."
    try:
        with open(requested, encoding="utf-8") as f:
            return f.read()[:8000]
    except Exception as e:
        return f"Error: {e}"
