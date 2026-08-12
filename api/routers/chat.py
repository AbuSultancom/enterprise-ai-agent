"""Chat router: /v1/chat and /v1/chat/stream endpoints."""

from __future__ import annotations

import json
import os

from fastapi import APIRouter, Depends, Security
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import config_loader
from agent_core.agent import Agent
from api.dependencies import audit, require_role
from llm_gateway.gateway import LLMGateway, Message
from memory.store import KnowledgeStore
from orchestrator.agent import OrchestratorAgent

router = APIRouter(prefix="/v1", tags=["Chat"])

# Lazily shared singletons (injected from main.py via app.state)
_gateway: LLMGateway | None = None
_store: KnowledgeStore | None = None
_conv_store = None


def init(gateway: LLMGateway, store: KnowledgeStore, conv_store) -> None:  # noqa: ANN001
    global _gateway, _store, _conv_store
    _gateway = gateway
    _store = store
    _conv_store = conv_store


class ChatRequest(BaseModel):
    message: str
    model: str | None = None
    use_knowledge: bool = True
    history: list[dict] | None = None
    session_id: str | None = None
    mode: str = "orchestrator"


async def _with_knowledge(message: str) -> str:
    assert _store and _gateway
    docs = await _store.search(message, gateway=_gateway)
    if docs:
        context = "\n\n".join(f"[{d.title}]\n{d.content}" for d in docs)
        return f"Company knowledge context:\n{context}\n\nQuestion: {message}"
    return message


@router.post("/chat", dependencies=[Depends(require_role("admin", "user"))])
async def chat(req: ChatRequest, role: str = Security(require_role("admin", "user"))):
    if _gateway is None or _conv_store is None:
        raise RuntimeError("Gateway or conversation store not initialized")

    session_id = _conv_store.get_or_create_session(req.session_id)
    _conv_store.save_message(session_id, "user", req.message)

    from tools.registry import registry as _registry

    agent = (
        OrchestratorAgent(_gateway) if req.mode == "orchestrator" else Agent(_gateway, _registry)
    )
    message = req.message
    if req.use_knowledge and config_loader.knowledge_rag_enabled():
        message = await _with_knowledge(req.message)

    max_mem = int(os.getenv("CHAT_MEMORY", "5"))
    history_raw = _conv_store.get_history(session_id, limit=max_mem * 2 + 2)
    history = [Message(**m) for m in history_raw]

    result = await agent.run(message, model=req.model, history=history)
    answer = result.get("answer", "")
    _conv_store.save_message(session_id, "assistant", answer)

    # Learn from exchange
    try:
        from memory.learning import learner

        tools_used = [s.get("tool", "") for s in result.get("steps", [])]
        learner.learn_from_exchange(req.message, answer, tools_used)
        for step in result.get("steps", []):
            if "weather" in step.get("tool", ""):
                city = req.message.replace("طقس", "").replace("weather", "").strip("? ").strip()
                if city:
                    learner.learn_fact(
                        "last_weather_check", f"{city}: {str(step.get('result', ''))[:100]}"
                    )
    except Exception:
        pass

    # Auto-title
    sessions = _conv_store.list_sessions(limit=1)
    if sessions and sessions[0]["title"] == "New conversation":
        title = req.message[:60] + ("…" if len(req.message) > 60 else "")
        _conv_store.rename_session(session_id, title)

    audit(
        "chat",
        role,
        {
            "message": req.message[:500],
            "session_id": session_id,
            "tools_used": [s.get("tool") for s in result.get("steps", [])],
        },
    )
    return {"session_id": session_id, **result}


@router.post("/chat/stream", dependencies=[Depends(require_role("admin", "user"))])
async def chat_stream(req: ChatRequest, role: str = Security(require_role("admin", "user"))):
    if _gateway is None or _conv_store is None:
        raise RuntimeError("Gateway or conversation store not initialized")

    session_id = _conv_store.get_or_create_session(req.session_id)
    _conv_store.save_message(session_id, "user", req.message)

    from tools.registry import registry as _registry

    agent = (
        OrchestratorAgent(_gateway) if req.mode == "orchestrator" else Agent(_gateway, _registry)
    )
    message = req.message
    if req.use_knowledge and config_loader.knowledge_rag_enabled():
        message = await _with_knowledge(req.message)

    max_mem = int(os.getenv("CHAT_MEMORY", "5"))
    history_raw = _conv_store.get_history(session_id, limit=max_mem * 2 + 2)
    history = [Message(**m) for m in history_raw]

    audit("chat_stream", role, {"message": req.message[:500], "session_id": session_id})

    async def event_source():
        answer_parts: list[str] = []
        async for event in agent.run_stream(message, model=req.model, history=history):
            if event.get("type") == "token":
                answer_parts.append(event.get("text", ""))
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

        full = "".join(answer_parts)
        if full:
            _conv_store.save_message(session_id, "assistant", full)
            try:
                from memory.learning import learner

                learner.learn_from_exchange(req.message, full)
            except Exception:
                pass

        sessions = _conv_store.list_sessions(limit=1)
        if sessions and sessions[0]["title"] == "New conversation":
            title = req.message[:60] + ("…" if len(req.message) > 60 else "")
            _conv_store.rename_session(session_id, title)

        yield f"data: {json.dumps({'type': 'session_id', 'session_id': session_id})}\n\n"

    return StreamingResponse(event_source(), media_type="text/event-stream")
