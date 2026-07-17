"""FastAPI application: auth, chat endpoint, knowledge management, dashboard."""
from __future__ import annotations

import os
import secrets

from fastapi import Depends, FastAPI, HTTPException, Security
from fastapi.security import APIKeyHeader
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import tools.builtin  # noqa: F401 - registers built-in tools
import tools.accounting  # noqa: F401 - registers accounting/ERP tools
from agent_core.agent import Agent
from connectors.accounting import connector as accounting_db
from llm_gateway.gateway import LLMGateway, Message
from memory.store import KnowledgeStore
from tools.registry import registry

# --- Simple role-based auth (replace with SSO/LDAP in production) ---
API_KEYS: dict[str, str] = {}  # key -> role
for entry in os.getenv("API_KEYS", "admin:dev-admin-key").split(","):
    role, key = entry.split(":", 1)
    API_KEYS[key] = role

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_role(*roles: str):
    def checker(api_key: str = Security(api_key_header)) -> str:
        role = API_KEYS.get(api_key or "")
        if role is None or (roles and role not in roles):
            raise HTTPException(status_code=403, detail="Invalid or insufficient API key")
        return role
    return checker


app = FastAPI(title="Enterprise AI Agent Platform", version="0.2.0")
gateway = LLMGateway()
store = KnowledgeStore()


class ChatRequest(BaseModel):
    message: str
    model: str | None = None
    use_knowledge: bool = True
    history: list[dict] | None = None


class DocRequest(BaseModel):
    title: str
    content: str


@app.get("/health")
async def health():
    return {"status": "ok", "providers": await gateway.health(),
            "tools": len(registry.list()), "accounting_db": accounting_db.available}


@app.post("/v1/chat", dependencies=[Depends(require_role("admin", "user"))])
async def chat(req: ChatRequest):
    agent = Agent(gateway, registry)
    message = req.message
    if req.use_knowledge:
        docs = store.search(req.message)
        if docs:
            context = "\n\n".join(f"[{d.title}]\n{d.content}" for d in docs)
            message = f"Company knowledge context:\n{context}\n\nQuestion: {req.message}"
    history = [Message(**m) for m in (req.history or [])]
    return await agent.run(message, model=req.model, history=history)


@app.get("/v1/tools", dependencies=[Depends(require_role("admin", "user"))])
async def list_tools():
    return [{"name": t.name, "description": t.description, "parameters": t.parameters} for t in registry.list()]


@app.get("/v1/knowledge", dependencies=[Depends(require_role("admin", "user"))])
async def list_docs():
    return store.list()


@app.post("/v1/knowledge", dependencies=[Depends(require_role("admin"))])
async def add_doc(req: DocRequest):
    return store.add(req.title, req.content)


@app.delete("/v1/knowledge/{doc_id}", dependencies=[Depends(require_role("admin"))])
async def delete_doc(doc_id: str):
    if not store.delete(doc_id):
        raise HTTPException(status_code=404, detail="Document not found")
    return {"deleted": doc_id}


@app.post("/v1/admin/rotate-key", dependencies=[Depends(require_role("admin"))])
async def rotate_key(role: str = "user"):
    key = secrets.token_urlsafe(32)
    API_KEYS[key] = role
    return {"api_key": key, "role": role}


class AccountingQuery(BaseModel):
    query: str
    params: dict | None = None


@app.post("/v1/accounting/query", dependencies=[Depends(require_role("admin"))])
async def accounting_query(req: AccountingQuery):
    """Run a whitelisted read-only accounting query (admin only)."""
    try:
        return accounting_db.run(req.query, **(req.params or {}))
    except (RuntimeError, ValueError, PermissionError) as e:
        raise HTTPException(status_code=400, detail=str(e))


app.mount("/", StaticFiles(directory="dashboard", html=True), name="dashboard")
