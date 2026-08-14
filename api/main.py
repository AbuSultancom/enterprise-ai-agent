"""Enterprise AI Agent — FastAPI application entry-point.

This file is intentionally thin: it wires together routers, middleware,
singletons, and the dashboard static files. All business logic lives in
the routers under api/routers/.
"""

from __future__ import annotations

import os
import platform
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI

import config_loader
import tools.accounting  # noqa: F401 — registers accounting/ERP tools
import tools.builtin  # noqa: F401 — registers built-in tools
import tools.communication  # noqa: F401 — registers communication tools
import tools.memory  # noqa: F401 — registers long-term memory tools
import tools.voice  # noqa: F401 — registers voice tools
from api.middleware import register_middleware
from connectors.accounting import connector as accounting_db
from llm_gateway.gateway import LLMGateway
from memory.conversation import get_store as get_conv_store
from memory.store import KnowledgeStore
from scheduler.engine import scheduler_engine
from tools.registry import registry

# ─── Load .env ───────────────────────────────────────────────────────────────


def _load_dotenv() -> None:
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


_load_dotenv()

# ─── Remove tools disabled by setup wizard ───────────────────────────────────

for _tool in list(registry.list()):
    if not config_loader.is_tool_allowed(_tool.name):
        del registry._tools[_tool.name]

# ─── Singletons ──────────────────────────────────────────────────────────────

gateway = LLMGateway()
store = KnowledgeStore()
conv_store = get_conv_store()

# ─── Lifespan (startup / shutdown) ──────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    scheduler_engine.init(gateway)
    await scheduler_engine.start()
    yield
    # Shutdown
    await scheduler_engine.stop()


# ─── App ─────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Enterprise AI Agent API",
    description=(
        "Enterprise AI Agent Platform — Secure, self-hosted AI with ERP connectors, "
        "knowledge base RAG, multi-agent orchestration, real-time streaming, "
        "and scheduled agent tasks."
    ),
    version="0.7.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

register_middleware(app)

# ─── Routers ─────────────────────────────────────────────────────────────────

from api.routers import accounting, admin, chat, conversations, knowledge  # noqa: E402
from api.routers import scheduler as scheduler_router  # noqa: E402

# Inject shared singletons into each router module
chat.init(gateway, store, conv_store)
conversations.init(conv_store)
knowledge.init(store, gateway)
accounting.init(accounting_db)
admin.init(gateway)

app.include_router(chat.router)
app.include_router(conversations.router)
app.include_router(knowledge.router)
app.include_router(accounting.router)
app.include_router(admin.router)
app.include_router(scheduler_router.router)

# ─── Health endpoint ─────────────────────────────────────────────────────────


@app.get("/health", tags=["System"])
async def health():
    db_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "conversations.db"
    )
    uptime = "unknown"
    if os.path.exists(db_path):
        import datetime

        uptime = str(
            datetime.datetime.now() - datetime.datetime.fromtimestamp(os.path.getmtime(db_path))
        )

    tools_list = [{"name": t.name, "description": t.description} for t in registry.list()]
    acc_status = accounting_db.test_connection() if accounting_db.available else None
    acc_info = accounting_db.get_schema_info() if accounting_db.available else None
    scheduled_jobs = scheduler_engine.list_jobs()

    return {
        "status": "ok",
        "version": "0.7.0",
        "providers": await gateway.health(),
        "tools_count": len(tools_list),
        "tools": tools_list,
        "accounting": acc_status,
        "accounting_schema": acc_info,
        "conversations": len(conv_store.list_sessions(limit=1000)),
        "knowledge_docs": len(store.list()),
        "scheduled_jobs": len(scheduled_jobs),
        "system": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "uptime": uptime,
        },
        "channels": {
            "whatsapp": os.getenv("WHATSAPP_ENABLED", "false") == "true",
            "telegram": os.getenv("TELEGRAM_ENABLED", "false") == "true",
        },
    }


# ─── Static dashboard (must be last) ─────────────────────────────────────────

from fastapi.staticfiles import StaticFiles  # noqa: E402

app.mount("/", StaticFiles(directory="dashboard", html=True), name="dashboard")
