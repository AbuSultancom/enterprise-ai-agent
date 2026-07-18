"""Accounting tools — let the agent answer questions like
'How much did we sell last month?' directly from the ERP database.

Also includes diagnostic tools for setup and schema discovery.
"""
from __future__ import annotations

import datetime
import json
import os

from connectors.accounting import (
    AccountingConnector,
    SchemaConfig,
    discover_schema,
    SCHEMA_CONFIG_PATH,
    connector,
)

from .registry import registry

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _default_range(start: str | None, end: str | None) -> tuple[str, str]:
    today = datetime.date.today()
    if not end:
        end = today.isoformat()
    if not start:
        start = today.replace(day=1).isoformat()
    return start, end


def _to_json(rows: list[dict]) -> str:
    def default(o):
        if isinstance(o, (datetime.date, datetime.datetime)):
            return o.isoformat()
        if hasattr(o, "__float__"):  # Decimal
            return float(o)
        return str(o)
    return json.dumps(rows, ensure_ascii=False, default=default, indent=2)


# ─── Diagnostic tools ─────────────────────────────────────────────

@registry.register(
    description="Test the accounting database connection and show status. "
                "Use this first to check if the ERP is reachable.",
    parameters={},
)
def diagnose_connection() -> str:
    if not connector.available:
        return (
            "⚠️ Accounting database is NOT configured.\n"
            "Set ACCOUNTING_DB_URL in .env or run the setup wizard.\n"
            "Required: SQLAlchemy + pyodbc installed."
        )
    info = connector.get_schema_info()
    status = connector.test_connection()
    lines = [
        f"Database: {'✅ Connected' if status.get('connected') else '❌ Failed'}",
        f"Server:   {status.get('database', 'N/A')}",
        f"Schema:   {info['name']} (v{info['version']})",
        f"Tables:   {len(info['tables'])} mapped",
        f"Queries:  {len(info['queries'])} available",
    ]
    if status.get("error"):
        lines.append(f"Error:    {status['error']}")
    lines.append("")
    lines.append("Mapped tables:")
    for tb_name, tb_info in info["tables"].items():
        cols = ", ".join(tb_info["columns"])
        lines.append(f"  • {tb_info['table']} → {tb_name} ({cols})")
    lines.append("")
    lines.append("Available queries:")
    for q in info["queries"]:
        lines.append(f"  • {q}")
    return "\n".join(lines)


@registry.register(
    description="Automatically discover the accounting database schema. "
                "Scans INFORMATION_SCHEMA to find tables and columns, "
                "then saves the mapping to config/accounting_schema.json.",
    parameters={},
)
def discover_schema_tool() -> str:
    db_url = os.getenv("ACCOUNTING_DB_URL", "")
    if not db_url:
        return "⚠️ ACCOUNTING_DB_URL is not set in .env. Configure it first."

    try:
        discovered = discover_schema(db_url)
        discovered.save()
        info = discovered.get_schema_info()
        lines = [
            f"✅ Schema discovery complete!",
            f"   Name: {info['name']}",
            f"   Saved to: {SCHEMA_CONFIG_PATH}",
            "",
            "Discovered tables:",
        ]
        for tb_name, tb_info in info["tables"].items():
            cols = ", ".join(tb_info["columns"])
            lines.append(f"  • {tb_info['table']} → {tb_name} ({cols})")
        lines.append("")
        lines.append(f"Available queries: {len(info['queries'])}")
        return "\n".join(lines)
    except Exception as e:
        return f"❌ Discovery failed: {e}"


@registry.register(
    description="Show the current accounting schema configuration.",
    parameters={},
)
def show_schema_config() -> str:
    info = connector.get_schema_info()
    lines = [
        f"Schema: {info['name']} (v{info['version']})",
        "",
        "Tables:",
    ]
    for tb_name, tb_info in info["tables"].items():
        cols = ", ".join(tb_info["columns"])
        lines.append(f"  • {tb_info['table']} → {tb_name} ({cols})")
    lines.append("")
    lines.append(f"Queries ({len(info['queries'])}):")
    for q in info["queries"]:
        lines.append(f"  • {q}")
    return "\n".join(lines)


# ─── Accounting query tools ───────────────────────────────────────

@registry.register(
    description="Get company sales summary (invoice count, total sales, tax, discounts) for a date range. "
                "Dates are YYYY-MM-DD; leave empty for the current month.",
    parameters={
        "start_date": {"type": "str", "description": "Start date YYYY-MM-DD (optional)"},
        "end_date": {"type": "str", "description": "End date YYYY-MM-DD (optional)"},
    },
)
def get_sales_summary(start_date: str = "", end_date: str = "") -> str:
    start, end = _default_range(start_date or None, end_date or None)
    try:
        rows = connector.run("sales_summary", start=start, end=end)
        return _to_json({"period": f"{start} -> {end}", "summary": rows})
    except Exception as e:
        return f"❌ Sales query failed: {e}"


@registry.register(
    description="Get company revenue grouped by month for a date range (YYYY-MM-DD).",
    parameters={
        "start_date": {"type": "str", "description": "Start date YYYY-MM-DD (optional)"},
        "end_date": {"type": "str", "description": "End date YYYY-MM-DD (optional)"},
    },
)
def get_revenue_by_month(start_date: str = "", end_date: str = "") -> str:
    start, end = _default_range(start_date or None, end_date or None)
    try:
        rows = connector.run("revenue_by_month", start=start, end=end)
        return _to_json(rows)
    except Exception as e:
        return f"❌ Revenue query failed: {e}"


@registry.register(
    description="Get the top customers by total sales for a date range.",
    parameters={
        "limit": {"type": "int", "description": "Number of customers (default 5)"},
        "start_date": {"type": "str", "description": "Start date YYYY-MM-DD (optional)"},
        "end_date": {"type": "str", "description": "End date YYYY-MM-DD (optional)"},
    },
)
def get_top_customers(limit: int = 5, start_date: str = "", end_date: str = "") -> str:
    start, end = _default_range(start_date or None, end_date or None)
    try:
        rows = connector.run("top_customers", limit=int(limit or 5), start=start, end=end)
        return _to_json(rows)
    except Exception as e:
        return f"❌ Top customers query failed: {e}"


@registry.register(
    description="Get company expenses grouped by expense account for a date range.",
    parameters={
        "start_date": {"type": "str", "description": "Start date YYYY-MM-DD (optional)"},
        "end_date": {"type": "str", "description": "End date YYYY-MM-DD (optional)"},
    },
)
def get_expenses_summary(start_date: str = "", end_date: str = "") -> str:
    start, end = _default_range(start_date or None, end_date or None)
    try:
        rows = connector.run("expenses_summary", start=start, end=end)
        return _to_json(rows)
    except Exception as e:
        return f"❌ Expenses query failed: {e}"


@registry.register(
    description="Look up a specific sales invoice by its invoice number.",
    parameters={"invoice_no": {"type": "str", "description": "Invoice number"}},
)
def get_invoice(invoice_no: str) -> str:
    try:
        rows = connector.run("invoice_lookup", invoice_no=invoice_no)
        return _to_json(rows) if rows else f"❌ Invoice {invoice_no} not found."
    except Exception as e:
        return f"❌ Invoice lookup failed: {e}"


@registry.register(
    description="Get current cash and bank account balances.",
    parameters={},
)
def get_cash_balance() -> str:
    try:
        rows = connector.run("cash_balance")
        return _to_json(rows)
    except Exception as e:
        return f"❌ Balance query failed: {e}"


@registry.register(
    description="Get vendor/supplier balances and total purchases for a date range.",
    parameters={
        "start_date": {"type": "str", "description": "Start date YYYY-MM-DD (optional)"},
        "end_date": {"type": "str", "description": "End date YYYY-MM-DD (optional)"},
    },
)
def get_vendor_balances(start_date: str = "", end_date: str = "") -> str:
    start, end = _default_range(start_date or None, end_date or None)
    try:
        rows = connector.run("vendor_balances", start=start, end=end)
        return _to_json(rows)
    except Exception as e:
        return f"❌ Vendor balances query failed: {e}"


@registry.register(
    description="Get sales totals grouped by item/product for a date range.",
    parameters={
        "start_date": {"type": "str", "description": "Start date YYYY-MM-DD (optional)"},
        "end_date": {"type": "str", "description": "End date YYYY-MM-DD (optional)"},
    },
)
def get_sales_by_item(start_date: str = "", end_date: str = "") -> str:
    start, end = _default_range(start_date or None, end_date or None)
    try:
        rows = connector.run("sales_by_item", start=start, end=end)
        return _to_json(rows)
    except Exception as e:
        return f"❌ Sales by item query failed: {e}"
