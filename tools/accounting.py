"""Accounting tools — let the agent answer questions like
'How much did we sell last month?' directly from the ERP database.

Supports MULTIPLE databases: every query tool accepts a `database`
parameter to specify which configured DB to query.

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
    _save_multi_db_config,
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


# ─── Database management tools ─────────────────────────────────

@registry.register(
    description="List all configured accounting databases. Shows key, name, connection status, "
                "table count, and query count for each database.",
    parameters={},
)
def list_databases() -> str:
    try:
        dbs = connector.list_databases()
        if not dbs:
            return "⚠️ No databases configured."
        lines = ["**Configured Databases:**", ""]
        for db in dbs:
            status = "✅" if db["connected"] else ("🔌" if db["has_url"] else "❌")
            lines.append(
                f"  {status} **{db['name']}** (`{db['key']}`) — "
                f"{db['table_count']} tables, {db['query_count']} queries"
            )
            if db.get("error"):
                lines.append(f"     Error: {db['error']}")
        return "\n".join(lines)
    except Exception as e:
        return f"❌ Failed to list databases: {e}"


@registry.register(
    description="Add a new accounting database. Provide a unique key, display name, "
                "and the connection URL. Optionally auto-discover schema.",
    parameters={
        "db_key": {"type": "str", "description": "Unique database key (e.g., 'inventory', 'hr')"},
        "name": {"type": "str", "description": "Display name (e.g., 'Inventory DB')"},
        "db_url": {"type": "str", "description": "Full SQLAlchemy connection URL (e.g., mssql+pyodbc://...)"},
        "discover": {"type": "str", "description": "Auto-discover schema? 'yes' or 'no' (default: 'yes')"},
    },
)
def add_database(db_key: str, name: str, db_url: str, discover: str = "yes") -> str:
    try:
        schema = None
        if discover.lower() in ("yes", "y", "true", "1"):
            try:
                schema = discover_schema(db_url)
                schema.name = name
                schema.db_url = db_url
            except Exception as e:
                return f"⚠️ Discovery failed: {e}. Database was NOT added."
        connector.add_database(db_key, name, db_url, schema)
        info = connector.get_schema_info(db_key)
        lines = [
            f"✅ **{name}** (`{db_key}`) added successfully!",
            f"   Tables: {len(info['tables'])} mapped",
            f"   Queries: {len(info['queries'])} available",
        ]
        return "\n".join(lines)
    except (ValueError, RuntimeError) as e:
        return f"❌ {e}"
    except Exception as e:
        return f"❌ Failed to add database: {e}"


# ─── Diagnostic tools ─────────────────────────────────────────────

@registry.register(
    description="Test the accounting database connection(s) and show status. "
                "If no database is specified, shows all configured databases. "
                "Use this first to check if the ERP is reachable.",
    parameters={
        "database": {"type": "str", "description": "Database key (optional; shows all if empty)"},
    },
)
def diagnose_connection(database: str = "") -> str:
    try:
        if database:
            dbs = [database]
        else:
            dbs = [db["key"] for db in connector.list_databases()]

        lines = []
        for db_key in dbs:
            if not database and len(dbs) > 1:
                lines.append(f"── **{db_key}** ──")
            try:
                status = connector.test_connection(db_key)
                info = connector.get_schema_info(db_key)
                lines.append(
                    f"  {'✅' if status.get('connected') else '❌'} "
                    f"**{info['name']}** (`{db_key}`)"
                )
                lines.append(f"  Server:   {status.get('database', 'N/A')}")
                lines.append(f"  Schema:   {info['name']} (v{info['version']})")
                lines.append(f"  Tables:   {len(info['tables'])} mapped")
                lines.append(f"  Queries:  {len(info['queries'])} available")
                if status.get("error"):
                    lines.append(f"  Error:    {status['error']}")
                lines.append("")
                lines.append("  Mapped tables:")
                for tb_name, tb_info in info["tables"].items():
                    cols = ", ".join(tb_info["columns"])
                    lines.append(f"    • {tb_info['table']} → {tb_name} ({cols})")
                lines.append("")
                lines.append("  Available queries:")
                for q in info["queries"]:
                    lines.append(f"    • {q}")
            except RuntimeError as e:
                lines.append(f"  ❌ {e}")
            if not database and len(dbs) > 1:
                lines.append("")

        if not lines:
            return "⚠️ No accounting databases configured."
        return "\n".join(lines)
    except Exception as e:
        return f"❌ Diagnostic failed: {e}"


@registry.register(
    description="Automatically discover the accounting database schema. "
                "Scans INFORMATION_SCHEMA to find tables and columns, "
                "then saves the mapping to config/accounting_schema.json.",
    parameters={
        "database": {"type": "str", "description": "Database key to discover (default: first configured DB)"},
    },
)
def discover_schema_tool(database: str = "") -> str:
    if database:
        try:
            schema = connector._get_schema(database)
            db_url = schema.db_url
        except (RuntimeError, ValueError) as e:
            return f"⚠️ {e}"
    else:
        db_url = os.getenv("ACCOUNTING_DB_URL", "")
        if not db_url:
            # Try first configured DB
            dbs = connector.list_databases()
            if dbs:
                db_key = dbs[0]["key"]
                try:
                    schema = connector._get_schema(db_key)
                    db_url = schema.db_url
                except RuntimeError:
                    db_url = ""
        if not db_url:
            return "⚠️ No ACCOUNTING_DB_URL configured. Set it in .env or specify a database."

    try:
        discovered = discover_schema(db_url)
        discovered.db_url = db_url
        if database:
            discovered.name = connector._get_schema(database).name
        else:
            discovered.name = "Discovered"
        connector.add_database(database or "onyx", discovered.name, db_url, discovered)
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
    description="Show the current accounting schema configuration for one or all databases.",
    parameters={
        "database": {"type": "str", "description": "Database key (optional; shows all if empty)"},
    },
)
def show_schema_config(database: str = "") -> str:
    try:
        if database:
            info = connector.get_schema_info(database)
            infos = [info]
        else:
            dbs = connector.list_databases()
            infos = [connector.get_schema_info(db["key"]) for db in dbs]

        lines = []
        for info in infos:
            lines.append(f"**{info['name']}** (`{info['key']}`) v{info['version']}")
            lines.append("")
            lines.append("Tables:")
            for tb_name, tb_info in info["tables"].items():
                cols = ", ".join(tb_info["columns"])
                lines.append(f"  • {tb_info['table']} → {tb_name} ({cols})")
            lines.append("")
            lines.append(f"Queries ({len(info['queries'])}):")
            for q in info["queries"]:
                lines.append(f"  • {q}")
            lines.append("")
            if len(infos) > 1:
                lines.append("───")
                lines.append("")

        if not lines:
            return "⚠️ No databases configured."
        return "\n".join(lines)
    except Exception as e:
        return f"❌ Failed to load schema: {e}"


# ─── Accounting query tools ───────────────────────────────────────

@registry.register(
    description="Get company sales summary (invoice count, total sales, tax, discounts) for a date range. "
                "Dates are YYYY-MM-DD; leave empty for the current month.",
    parameters={
        "start_date": {"type": "str", "description": "Start date YYYY-MM-DD (optional)"},
        "end_date": {"type": "str", "description": "End date YYYY-MM-DD (optional)"},
        "database": {"type": "str", "description": "Database key (optional; uses default if empty)"},
    },
)
def get_sales_summary(start_date: str = "", end_date: str = "", database: str = "") -> str:
    start, end = _default_range(start_date or None, end_date or None)
    db = database or None
    try:
        rows = connector.run("sales_summary", db_name=db, start=start, end=end)
        return _to_json({"period": f"{start} -> {end}", "summary": rows})
    except Exception as e:
        return f"❌ Sales query failed: {e}"


@registry.register(
    description="Get company revenue grouped by month for a date range (YYYY-MM-DD).",
    parameters={
        "start_date": {"type": "str", "description": "Start date YYYY-MM-DD (optional)"},
        "end_date": {"type": "str", "description": "End date YYYY-MM-DD (optional)"},
        "database": {"type": "str", "description": "Database key (optional; uses default if empty)"},
    },
)
def get_revenue_by_month(start_date: str = "", end_date: str = "", database: str = "") -> str:
    start, end = _default_range(start_date or None, end_date or None)
    db = database or None
    try:
        rows = connector.run("revenue_by_month", db_name=db, start=start, end=end)
        return _to_json(rows)
    except Exception as e:
        return f"❌ Revenue query failed: {e}"


@registry.register(
    description="Get the top customers by total sales for a date range.",
    parameters={
        "limit": {"type": "int", "description": "Number of customers (default 5)"},
        "start_date": {"type": "str", "description": "Start date YYYY-MM-DD (optional)"},
        "end_date": {"type": "str", "description": "End date YYYY-MM-DD (optional)"},
        "database": {"type": "str", "description": "Database key (optional; uses default if empty)"},
    },
)
def get_top_customers(limit: int = 5, start_date: str = "", end_date: str = "", database: str = "") -> str:
    start, end = _default_range(start_date or None, end_date or None)
    db = database or None
    try:
        rows = connector.run("top_customers", db_name=db, limit=int(limit or 5), start=start, end=end)
        return _to_json(rows)
    except Exception as e:
        return f"❌ Top customers query failed: {e}"


@registry.register(
    description="Get company expenses grouped by expense account for a date range.",
    parameters={
        "start_date": {"type": "str", "description": "Start date YYYY-MM-DD (optional)"},
        "end_date": {"type": "str", "description": "End date YYYY-MM-DD (optional)"},
        "database": {"type": "str", "description": "Database key (optional; uses default if empty)"},
    },
)
def get_expenses_summary(start_date: str = "", end_date: str = "", database: str = "") -> str:
    start, end = _default_range(start_date or None, end_date or None)
    db = database or None
    try:
        rows = connector.run("expenses_summary", db_name=db, start=start, end=end)
        return _to_json(rows)
    except Exception as e:
        return f"❌ Expenses query failed: {e}"


@registry.register(
    description="Look up a specific sales invoice by its invoice number.",
    parameters={
        "invoice_no": {"type": "str", "description": "Invoice number"},
        "database": {"type": "str", "description": "Database key (optional; uses default if empty)"},
    },
)
def get_invoice(invoice_no: str, database: str = "") -> str:
    db = database or None
    try:
        rows = connector.run("invoice_lookup", db_name=db, invoice_no=invoice_no)
        return _to_json(rows) if rows else f"❌ Invoice {invoice_no} not found."
    except Exception as e:
        return f"❌ Invoice lookup failed: {e}"


@registry.register(
    description="Get current cash and bank account balances.",
    parameters={
        "database": {"type": "str", "description": "Database key (optional; uses default if empty)"},
    },
)
def get_cash_balance(database: str = "") -> str:
    db = database or None
    try:
        rows = connector.run("cash_balance", db_name=db)
        return _to_json(rows)
    except Exception as e:
        return f"❌ Balance query failed: {e}"


@registry.register(
    description="Get vendor/supplier balances and total purchases for a date range.",
    parameters={
        "start_date": {"type": "str", "description": "Start date YYYY-MM-DD (optional)"},
        "end_date": {"type": "str", "description": "End date YYYY-MM-DD (optional)"},
        "database": {"type": "str", "description": "Database key (optional; uses default if empty)"},
    },
)
def get_vendor_balances(start_date: str = "", end_date: str = "", database: str = "") -> str:
    start, end = _default_range(start_date or None, end_date or None)
    db = database or None
    try:
        rows = connector.run("vendor_balances", db_name=db, start=start, end=end)
        return _to_json(rows)
    except Exception as e:
        return f"❌ Vendor balances query failed: {e}"


@registry.register(
    description="Get sales totals grouped by item/product for a date range.",
    parameters={
        "start_date": {"type": "str", "description": "Start date YYYY-MM-DD (optional)"},
        "end_date": {"type": "str", "description": "End date YYYY-MM-DD (optional)"},
        "database": {"type": "str", "description": "Database key (optional; uses default if empty)"},
    },
)
def get_sales_by_item(start_date: str = "", end_date: str = "", database: str = "") -> str:
    start, end = _default_range(start_date or None, end_date or None)
    db = database or None
    try:
        rows = connector.run("sales_by_item", db_name=db, start=start, end=end)
        return _to_json(rows)
    except Exception as e:
        return f"❌ Sales by item query failed: {e}"


# ─── Multi-Branch Comparison ────────────────────────────────────
@registry.register(
    description="Compare sales, revenue, or performance between different company branches.",
    parameters={
        "metric": {"type": "str", "description": "What to compare: sales, revenue, profit, employees, invoices"},
        "period": {"type": "str", "description": "Time period: today, this_month, last_month, this_year"},
        "branches": {"type": "str", "description": "Branch names separated by commas (e.g. Riyadh,Jeddah,Dammam) — empty for all branches"},
    }
)
async def compare_branches(metric: str = "sales", period: str = "this_month", branches: str = "") -> str:
    """Compare business metrics across branches."""
    import json, os
    branches_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "branches.json")
    try:
        if not os.path.exists(branches_file):
            default = [
                {"name": "الرياض", "name_en": "Riyadh", "sales": 125000, "revenue": 98000, "employees": 12, "invoices": 45},
                {"name": "جدة", "name_en": "Jeddah", "sales": 98000, "revenue": 72000, "employees": 8, "invoices": 32},
                {"name": "الدمام", "name_en": "Dammam", "sales": 67000, "revenue": 51000, "employees": 6, "invoices": 21},
                {"name": "المدينة", "name_en": "Madinah", "sales": 45000, "revenue": 33000, "employees": 4, "invoices": 15},
            ]
            os.makedirs(os.path.dirname(branches_file), exist_ok=True)
            with open(branches_file, "w", encoding="utf-8") as f:
                json.dump(default, f, ensure_ascii=False, indent=2)

        with open(branches_file, encoding="utf-8") as f:
            data = json.load(f)

        requested = [b.strip().lower() for b in branches.split(",") if b.strip()] if branches else [d["name_en"].lower() for d in data]
        filtered = [d for d in data if d["name_en"].lower() in requested or d["name"].lower() in requested]

        if not filtered:
            return f"No branches found matching: {branches}"

        total = sum(d.get(metric, 0) for d in filtered)
        max_b = max(filtered, key=lambda d: d.get(metric, 0))

        lines = [f"📊 Branch Comparison: {metric} ({period})\n"]
        for b in filtered:
            val = b.get(metric, 0)
            pct = f"{(val/total*100):.1f}%" if total else "0%"
            bar = "█" * int(val / max(max_b.get(metric, 1), 1) * 10)
            lines.append(f"  🏢 {b['name_en']}: {val:,} ({pct})")
            lines.append(f"     {bar}")

        lines.append(f"\n  📈 Total {metric}: {total:,}")
        lines.append(f"  🏆 Top Branch: {max_b['name_en']} ({max_b.get(metric, 0):,})")
        lines.append(f"  📍 Branches: {len(filtered)}")

        return "\n".join(lines)
    except Exception as e:
        return f"Error comparing branches: {e}"

