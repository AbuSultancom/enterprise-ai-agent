"""
Schema Discovery Tool — auto-detect real Onyx Pro (or any SQL) tables & columns.

Connects to the accounting database and updates config/accounting_schema.json
with the REAL table/column names, matched to the logical schema keys used by
the query templates (sales_invoices, customers, journal_entries, ...).

Usage:
    python tools/discover_schema.py
    python tools/discover_schema.py --db-url "oracle+oracledb://user:pwd@host:1521/?service_name=ORCL"
    python tools/discover_schema.py --db-url "..." --owner ONYX --db-key onyx
    python tools/discover_schema.py --list-only --db-url "..."

Security: SELECT-only queries against the data dictionary. No writes to the DB.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Any

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

SCHEMA_CONFIG_PATH = os.path.join(ROOT, "config", "accounting_schema.json")

# ─── Logical schema keys → keywords used to auto-match real tables ─────────
LOGICAL_TABLES: dict[str, list[str]] = {
    "sales_invoices": ["sales_invoice", "sale_invoice", "invoice", "sales"],
    "purchase_invoices": ["purchase_invoice", "purchase", "vendor_invoice", "po_invoice", "grn_invoice"],
    "customers": ["customer", "client", "debtor"],
    "vendors": ["vendor", "supplier", "creditor"],
    "accounts": ["account", "chart", "coa"],
    "journal_entries": ["journal", "gl_entry", "entry", "voucher", "transaction"],
    "items": ["item", "product", "inventory", "stock", "goods", "material"],
}

# ─── Logical column keys → keywords used to auto-match real columns ────────
LOGICAL_COLUMNS: dict[str, list[str]] = {
    "id": ["id", "pk", "guid", "code_id"],
    "number": ["no", "num", "number", "ref", "reference"],
    "date": ["date", "dt", "time"],
    "net_total": ["net", "total", "amount", "sum", "grand"],
    "tax": ["tax", "vat", "gst"],
    "discount": ["discount", "disc"],
    "status": ["status", "state", "posted", "flag"],
    "customer_id": ["customer_id", "cust_id", "client_id", "debtor_id"],
    "vendor_id": ["vendor_id", "supplier_id", "creditor_id"],
    "account_id": ["account_id", "acc_id", "gl_id"],
    "name": ["name", "title", "desc"],
    "code": ["code"],
    "phone": ["phone", "mobile", "tel", "telephone"],
    "email": ["email", "mail"],
    "debit": ["debit", "dr"],
    "credit": ["credit", "cr"],
    "description": ["description", "desc", "details", "notes"],
    "reference": ["reference", "ref", "doc_no", "docno"],
    "unit_price": ["unit_price", "price", "rate", "unitprice"],
    "category": ["category", "cat", "group", "type"],
    "quantity": ["quantity", "qty", "qty_sold"],
    "line_total": ["line_total", "line_total", "net", "total"],
}


def normalize(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def score_name(name: str, keywords: list[str]) -> int:
    """How well `name` matches the keyword list. 0 = no match."""
    n = normalize(name)
    if not n:
        return 0
    best = 0
    for kw in keywords:
        k = normalize(kw)
        if n == k:
            best = max(best, 100)
        elif k in n:
            best = max(best, 60)
        elif n in k:
            best = max(best, 40)
    return best


# ─── Database introspection (Oracle + SQL Server) ─────────────────────────
def get_engine(db_url: str):
    try:
        from sqlalchemy import create_engine
    except ImportError as e:
        raise SystemExit("SQLAlchemy is not installed. Run: pip install sqlalchemy") from e
    return create_engine(db_url)


def dialect_name(db_url: str) -> str:
    return db_url.split(":", 1)[0].split("+")[0].lower()


def discover_tables(engine, owner: str | None) -> list[tuple[str, str]]:
    """Return [(table_name, table_type)] — type is 'TABLE'/'VIEW'."""
    from sqlalchemy import text

    d = dialect_name(str(engine.url))
    with engine.connect() as conn:
        if d == "oracle":
            if owner:
                rows = conn.execute(text(
                    "SELECT table_name, 'TABLE' FROM all_tables WHERE owner = :o "
                    "AND table_name NOT LIKE 'BIN$%' ORDER BY table_name"
                ), {"o": owner}).all()
            else:
                rows = conn.execute(text(
                    "SELECT table_name, 'TABLE' FROM user_tables "
                    "WHERE table_name NOT LIKE 'BIN$%' ORDER BY table_name"
                )).all()
        else:  # sql server / mssql / generic
            rows = conn.execute(text(
                "SELECT TABLE_NAME, TABLE_TYPE FROM INFORMATION_SCHEMA.TABLES "
                "WHERE TABLE_NAME NOT LIKE 'sys%' ORDER BY TABLE_NAME"
            )).all()
    return [(str(r[0]), str(r[1])) for r in rows]


def discover_columns(engine, table: str, owner: str | None) -> list[str]:
    from sqlalchemy import text

    d = dialect_name(str(engine.url))
    with engine.connect() as conn:
        if d == "oracle":
            if owner:
                rows = conn.execute(text(
                    "SELECT column_name FROM all_tab_columns WHERE owner = :o "
                    "AND table_name = :t ORDER BY column_id"
                ), {"o": owner, "t": table}).all()
            else:
                rows = conn.execute(text(
                    "SELECT column_name FROM user_tab_columns "
                    "WHERE table_name = :t ORDER BY column_id"
                ), {"t": table}).all()
        else:
            rows = conn.execute(text(
                "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
                "WHERE TABLE_NAME = :t ORDER BY ORDINAL_POSITION"
            ), {"t": table}).all()
    return [str(r[0]) for r in rows]


# ─── Matching logic ────────────────────────────────────────────────────────
def match_tables(discovered: list[tuple[str, str]]) -> dict[str, str]:
    """Match discovered tables to logical keys. Returns {logical_key: real_table}."""
    matched: dict[str, str] = {}
    taken: set[str] = set()
    for logical, keywords in LOGICAL_TABLES.items():
        best_name, best_score = None, 0
        for tbl, _ttype in discovered:
            if tbl in taken:
                continue
            s = score_name(tbl, keywords)
            if s > best_score:
                best_name, best_score = tbl, s
        if best_name and best_score >= 40:
            matched[logical] = best_name
            taken.add(best_name)
    return matched


def match_columns(real_table: str, discovered_cols: list[str], engine, owner: str | None) -> dict[str, str]:
    """Match discovered columns to logical column keys. Returns {logical_col: real_col}."""
    result: dict[str, str] = {}
    taken: set[str] = set()
    # prioritize exact name matches first
    for logical, keywords in LOGICAL_COLUMNS.items():
        best_col, best_score = None, 0
        for col in discovered_cols:
            if col in taken:
                continue
            s = score_name(col, keywords)
            if s > best_score:
                best_col, best_score = col, s
        if best_col and best_score >= 40:
            result[logical] = best_col
            taken.add(best_col)
    return result


def build_schema_mapping(engine, owner: str | None) -> dict[str, dict[str, Any]]:
    """Discover all tables and columns, return the {logical: {table, columns}} map."""
    tables = discover_tables(engine, owner)
    print(f"  Found {len(tables)} tables")
    matched = match_tables(tables)

    mapping: dict[str, dict[str, Any]] = {}
    for logical, real in matched.items():
        cols = discover_columns(engine, real, owner)
        col_map = match_columns(real, cols, engine, owner)
        mapping[logical] = {"table": real, "columns": col_map}
        print(f"  ✔ {logical:18s} → {real} ({len(col_map)} columns matched)")
    return mapping


# ─── Config file handling ──────────────────────────────────────────────────
def load_config() -> dict:
    if os.path.exists(SCHEMA_CONFIG_PATH):
        try:
            with open(SCHEMA_CONFIG_PATH, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {
        "version": 2,
        "databases": {},
    }


def save_config(config: dict) -> None:
    with open(SCHEMA_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    print(f"\n  ✅ Config saved to {SCHEMA_CONFIG_PATH}")


def update_db_entry(config: dict, db_key: str, name: str, db_url: str,
                    mapping: dict[str, dict[str, Any]]) -> None:
    entry = config.setdefault("databases", {}).setdefault(db_key, {})
    entry["name"] = name
    entry["db_url"] = db_url
    entry["enabled"] = True
    entry["tables"] = mapping
    print(f"  ✅ Updated database entry '{db_key}'")


# ─── Main ──────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(description="Discover accounting DB schema (Onyx Pro)")
    parser.add_argument("--db-url", help="SQLAlchemy URL (oracle+oracledb://user:pwd@host:1521/?service_name=ORCL)")
    parser.add_argument("--owner", help="Oracle schema owner (e.g. ONYX). Default: current user")
    parser.add_argument("--db-key", default="onyx", help="Key for the database entry in the config (default: onyx)")
    parser.add_argument("--name", default="Onyx Pro", help="Display name for the database entry")
    parser.add_argument("--list-only", action="store_true", help="Only list tables, do not write config")
    args = parser.parse_args()

    db_url = args.db_url or os.getenv("ACCOUNTING_DB_URL") or input("Database URL (oracle+oracledb://...): ").strip()
    if not db_url:
        raise SystemExit("No database URL provided.")

    print(f"\n🔍 Connecting to: {db_url.split('@')[-1] if '@' in db_url else db_url}")
    engine = get_engine(db_url)

    # Test connection
    from sqlalchemy import text
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("  ✅ Connection OK")
    except Exception as e:
        raise SystemExit(f"  ❌ Connection failed: {e}")

    print(f"  Discovering tables...")
    mapping = build_schema_mapping(engine, args.owner)

    if args.list_only:
        print("\n  (list-only mode — config not modified)")
        return

    config = load_config()
    update_db_entry(config, args.db_key, args.name, db_url, mapping)
    save_config(config)


if __name__ == "__main__":
    main()
