"""Structured Audit Logger for Enterprise AI Agent.
Logs all tool calls, database operations, and user queries to immutable audit logs.
"""

from __future__ import annotations

import datetime
import json
import logging
from pathlib import Path
from typing import Any

LOG_DIR = Path("data/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)
AUDIT_FILE = LOG_DIR / "audit_log.jsonl"


class AuditLogger:
    """Logs structured JSON audit events to data/logs/audit_log.jsonl."""

    @staticmethod
    def log_event(
        event_type: str, user_id: str, details: dict[str, Any], status: str = "SUCCESS"
    ) -> None:
        record = {
            "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
            "event_type": event_type,
            "user_id": user_id,
            "status": status,
            "details": details,
        }
        try:
            with open(AUDIT_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception as e:
            logging.error(f"Audit log write failed: {e}")

    @classmethod
    def log_tool_call(
        cls,
        tool_name: str,
        args: dict[str, Any],
        user_id: str,
        status: str = "SUCCESS",
        result_snippet: str = "",
    ) -> None:
        cls.log_event(
            event_type="TOOL_CALL",
            user_id=user_id,
            status=status,
            details={
                "tool_name": tool_name,
                "arguments": args,
                "result_snippet": result_snippet[:200] if result_snippet else "",
            },
        )

    @classmethod
    def log_user_query(cls, query: str, user_id: str, channel: str = "web") -> None:
        cls.log_event(
            event_type="USER_QUERY",
            user_id=user_id,
            details={"query_snippet": query[:200], "channel": channel},
        )
