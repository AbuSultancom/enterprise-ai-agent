"""Shared FastAPI dependencies: authentication, role checking, audit helper."""
from __future__ import annotations

import datetime
import json
import os

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

# ─── API Key store (key → role) ──────────────────────────────────────────────

def _build_api_keys() -> dict[str, str]:
    keys: dict[str, str] = {}
    env = os.getenv("API_KEYS")
    if not env:
        env = (
            f"admin:{os.getenv('ADMIN_KEY', 'dev-admin-key')},"
            f"user:{os.getenv('USER_KEY', 'dev-user-key')}"
        )
    for entry in env.split(","):
        if ":" in entry:
            role, key = entry.split(":", 1)
            keys[key.strip()] = role.strip()
    return keys


API_KEYS: dict[str, str] = _build_api_keys()

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_role(*roles: str):
    """FastAPI dependency factory: validates API key and enforces role."""

    def checker(api_key: str = Security(api_key_header)) -> str:
        role = API_KEYS.get(api_key or "")
        if role is None or (roles and role not in roles):
            raise HTTPException(status_code=403, detail="Invalid or insufficient API key")
        return role

    return checker


# ─── Audit helper ─────────────────────────────────────────────────────────────

AUDIT_PATH = os.getenv(
    "AUDIT_LOG_PATH",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "audit.jsonl"),
)

_MAX_AUDIT_BYTES = 50 * 1024 * 1024  # 50 MB — rotate when exceeded


def audit(event: str, role: str, detail: dict) -> None:
    """Append a JSON-lines audit record; rotates the file at 50 MB."""
    try:
        os.makedirs(os.path.dirname(AUDIT_PATH) or ".", exist_ok=True)

        # Rotate if too large
        if os.path.exists(AUDIT_PATH) and os.path.getsize(AUDIT_PATH) > _MAX_AUDIT_BYTES:
            rotated = AUDIT_PATH + f".{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
            os.rename(AUDIT_PATH, rotated)

        entry = {
            "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "event": event,
            "role": role,
            **detail,
        }
        with open(AUDIT_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass
