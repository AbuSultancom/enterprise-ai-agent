"""Accounting tools — let the agent answer questions like
'How much did we sell last month?' directly from the ERP database.
"""
from __future__ import annotations

import datetime
import json

from connectors.accounting import connector

from .registry import registry


def _default_range(start: str | None, end: str | None) -> tuple[str, str]:
    today = datetime.date.today()
    if not end:
        end = today.isoformat()
    if not start:
        start = today.replace(day=1).isoformat()  # current month
    return start, end


def _to_json(rows: list[dict]) -> str:
    def default(o):
        if isinstance(o, (datetime.date, datetime.datetime)):
            return o.isoformat()
        if hasattr(o, "__float__"):  # Decimal
            return float(o)
        return str(o)
    return json.dumps(rows, ensure_ascii=False, default=default, indent=2)


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
    rows = connector.run("sales_summary", start=start, end=end)
    return _to_json({"period": f"{start} -> {end}", "summary": rows})


@registry.register(
    description="Get company revenue grouped by month for a date range (YYYY-MM-DD).",
    parameters={
        "start_date": {"type": "str", "description": "Start date YYYY-MM-DD (optional)"},
        "end_date": {"type": "str", "description": "End date YYYY-MM-DD (optional)"},
    },
)
def get_revenue_by_month(start_date: str = "", end_date: str = "") -> str:
    start, end = _default_range(start_date or None, end_date or None)
    rows = connector.run("revenue_by_month", start=start, end=end)
    return _to_json(rows)


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
    rows = connector.run("top_customers", limit=int(limit or 5), start=start, end=end)
    return _to_json(rows)


@registry.register(
    description="Get company expenses grouped by expense account for a date range.",
    parameters={
        "start_date": {"type": "str", "description": "Start date YYYY-MM-DD (optional)"},
        "end_date": {"type": "str", "description": "End date YYYY-MM-DD (optional)"},
    },
)
def get_expenses_summary(start_date: str = "", end_date: str = "") -> str:
    start, end = _default_range(start_date or None, end_date or None)
    rows = connector.run("expenses_summary", start=start, end=end)
    return _to_json(rows)


@registry.register(
    description="Look up a specific sales invoice by its invoice number.",
    parameters={"invoice_no": {"type": "str", "description": "Invoice number"}},
)
def get_invoice(invoice_no: str) -> str:
    rows = connector.run("invoice_lookup", invoice_no=invoice_no)
    return _to_json(rows) if rows else f"Invoice {invoice_no} not found."


@registry.register(
    description="Get current cash and bank account balances.",
    parameters={},
)
def get_cash_balance() -> str:
    rows = connector.run("cash_balance")
    return _to_json(rows)
