"""Admin router: tools list, settings, SMTP test, key rotation, audit log."""
from __future__ import annotations

import json
import os
import secrets

from fastapi import APIRouter, Depends, Security
from pydantic import BaseModel

import config_loader
from api.dependencies import AUDIT_PATH, audit, require_role
from tools.registry import registry

router = APIRouter(prefix="/v1", tags=["Admin"])

_gateway = None


def init(gateway) -> None:  # noqa: ANN001
    global _gateway
    _gateway = gateway


class AgentSettingsRequest(BaseModel):
    name: str | None = None
    personality: str | None = None
    language: str | None = None
    pii_masking: bool | None = None
    max_memory: int | None = None


@router.get("/tools", dependencies=[Depends(require_role("admin", "user"))])
async def list_tools():
    return [{"name": t.name, "description": t.description, "parameters": t.parameters} for t in registry.list()]


@router.get("/settings/agent", dependencies=[Depends(require_role("admin", "user"))])
async def get_agent_settings():
    identity = config_loader.agent_identity()
    return {
        "name": identity.get("name", "Enterprise AI Agent"),
        "personality": identity.get("personality", "a professional assistant"),
        "language": identity.get("language", "auto"),
        "pii_masking": True,
        "max_memory": int(os.getenv("CHAT_MEMORY", "5")),
    }


@router.post("/settings/agent", dependencies=[Depends(require_role("admin"))])
async def update_agent_settings(req: AgentSettingsRequest, role: str = Security(require_role("admin"))):
    current = config_loader.load_settings()
    agent_cfg = current.get("agent", {})
    if req.name is not None:
        agent_cfg["name"] = req.name
    if req.personality is not None:
        agent_cfg["personality"] = req.personality
    if req.language is not None:
        agent_cfg["language"] = req.language
    current["agent"] = agent_cfg
    config_loader.save_settings(current)
    audit("update_settings", role, {"updated": req.model_dump(exclude_unset=True)})
    return {"status": "ok", "settings": current["agent"]}


@router.post("/settings/smtp/test", dependencies=[Depends(require_role("admin"))])
async def test_smtp_settings(to_email: str):
    from tools.communication import send_email_notification
    res = await send_email_notification(
        to_email,
        "Enterprise AI Agent — Test Alert",
        "This is a test notification from the Enterprise AI Agent Settings Center.",
    )
    return {"result": res}


@router.post("/admin/rotate-key", dependencies=[Depends(require_role("admin"))])
async def rotate_key(role: str = "user"):
    from api.dependencies import API_KEYS
    key = secrets.token_urlsafe(32)
    API_KEYS[key] = role
    return {"api_key": key, "role": role}


@router.get("/admin/audit", dependencies=[Depends(require_role("admin"))])
async def get_audit(limit: int = 100):
    if not os.path.exists(AUDIT_PATH):
        return []
    with open(AUDIT_PATH, encoding="utf-8") as f:
        lines = f.readlines()[-limit:]
    return [json.loads(line) for line in lines if line.strip()]
