"""Conversations router: list, get, export, delete sessions."""

from __future__ import annotations

import datetime
import io
import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from api.dependencies import require_role

router = APIRouter(prefix="/v1/conversations", tags=["Conversations"])

_conv_store = None


def init(conv_store) -> None:  # noqa: ANN001
    global _conv_store
    _conv_store = conv_store


@router.get("", dependencies=[Depends(require_role("admin", "user"))])
async def list_conversations():
    if _conv_store is None:
        raise RuntimeError("Conversation store not initialized")
    return _conv_store.list_sessions(limit=50)


@router.get("/{session_id}", dependencies=[Depends(require_role("admin", "user"))])
async def get_conversation(session_id: str):
    if _conv_store is None:
        raise RuntimeError("Conversation store not initialized")
    messages = _conv_store.get_history(session_id, limit=200)
    sessions = _conv_store.list_sessions(limit=200)
    title = next((s["title"] for s in sessions if s["id"] == session_id), "Conversation")
    return {"session_id": session_id, "title": title, "messages": messages}


@router.get("/{session_id}/export", dependencies=[Depends(require_role("admin", "user"))])
async def export_conversation(session_id: str, format: str = "markdown"):
    if _conv_store is None:
        raise RuntimeError("Conversation store not initialized")
    messages = _conv_store.get_history(session_id, limit=1000)
    sessions = _conv_store.list_sessions(limit=200)
    title = next((s["title"] for s in sessions if s["id"] == session_id), "Conversation")
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    if format == "json":
        data = json.dumps(
            {"session_id": session_id, "title": title, "messages": messages},
            indent=2,
            ensure_ascii=False,
        )
        return StreamingResponse(
            io.BytesIO(data.encode("utf-8")),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="chat_{session_id[:8]}.json"'},
        )

    if format == "html":
        body = f"<h1>{title}</h1><p><em>Exported on {now_str}</em></p><hr>"
        for m in messages:
            role_title = "👤 User" if m["role"] == "user" else "🤖 Assistant"
            body += (
                f"<div style='margin-bottom:15px;padding:10px;background:#f4f5f8;"
                f"border-radius:8px;'><strong>{role_title}:</strong>"
                f"<div style='margin-top:5px;'>{m['content']}</div></div>"
            )
        full_html = (
            f"<!DOCTYPE html><html><head><meta charset='utf-8'><title>{title}</title>"
            f"<style>body{{font-family:system-ui,sans-serif;padding:30px;line-height:1.6;"
            f"color:#1a1a1a;max-width:800px;margin:0 auto;}}</style></head>"
            f"<body>{body}</body></html>"
        )
        return StreamingResponse(
            io.BytesIO(full_html.encode("utf-8")),
            media_type="text/html",
            headers={"Content-Disposition": f'attachment; filename="chat_{session_id[:8]}.html"'},
        )

    # Default: Markdown
    lines = [f"# {title}", f"*Exported on {now_str}*", "---", ""]
    for m in messages:
        name = "**User**" if m["role"] == "user" else "**Assistant**"
        lines.append(f"### {name}:\n{m['content']}\n")
    return StreamingResponse(
        io.BytesIO("\n".join(lines).encode("utf-8")),
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="chat_{session_id[:8]}.md"'},
    )


@router.delete("/{session_id}", dependencies=[Depends(require_role("admin"))])
async def delete_conversation(session_id: str):
    if _conv_store is None:
        raise RuntimeError("Conversation store not initialized")
    if not _conv_store.delete_session(session_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"deleted": session_id}
