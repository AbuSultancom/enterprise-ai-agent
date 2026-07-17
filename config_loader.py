"""Runtime settings loader — reads config/settings.json produced by setup.py.

Controls what the agent is allowed to do: which tools are enabled,
whether the knowledge base is used, and which accounting queries are allowed.
Missing file = permissive defaults (all built-ins on).
"""
from __future__ import annotations

import json
import os

SETTINGS_PATH = os.getenv("SETTINGS_PATH", "config/settings.json")

DEFAULTS: dict = {
    "permissions": {
        "web_search": True,
        "calculator": True,
        "get_current_time": True,
        "read_file": False,
        "accounting_tools": True,
        "knowledge_rag": True,
    },
    "accounting": {
        "enabled": False,
        "read_only": True,
        "allowed_queries": [
            "sales_summary", "revenue_by_month", "top_customers",
            "expenses_summary", "invoice_lookup", "cash_balance",
        ],
    },
}

ACCOUNTING_TOOLS = {
    "get_sales_summary", "get_revenue_by_month", "get_top_customers",
    "get_expenses_summary", "get_invoice", "get_cash_balance",
}


def load_settings() -> dict:
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, encoding="utf-8") as f:
                user = json.load(f)
            merged = {**DEFAULTS, **user}
            merged["permissions"] = {**DEFAULTS["permissions"], **user.get("permissions", {})}
            merged["accounting"] = {**DEFAULTS["accounting"], **user.get("accounting", {})}
            return merged
        except (json.JSONDecodeError, OSError):
            pass
    return DEFAULTS


settings = load_settings()


def is_tool_allowed(tool_name: str) -> bool:
    perms = settings["permissions"]
    if tool_name in ACCOUNTING_TOOLS:
        return perms.get("accounting_tools", True)
    return perms.get(tool_name, True)  # unknown tools default to allowed


def allowed_accounting_queries() -> list[str]:
    return settings["accounting"].get("allowed_queries", DEFAULTS["accounting"]["allowed_queries"])


def knowledge_rag_enabled() -> bool:
    return settings["permissions"].get("knowledge_rag", True)
