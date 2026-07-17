"""Accounting connector — read-only access to the company's ERP/accounting database.

Designed for Onyx Pro ERP, which typically runs on Microsoft SQL Server.
Table/column names vary between Onyx installations, so all queries live in
QUERY_MAP below — adjust them once to match your schema and everything works.

SECURITY: this connector enforces read-only queries (SELECT/WITH only).
Use a dedicated DB user with SELECT-only permissions in production.
"""
from __future__ import annotations

import os
import re
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

# Query map — adapt table/column names to YOUR Onyx Pro schema.
QUERY_MAP: dict[str, str] = {
    "sales_summary": """
        SELECT
            COUNT(DISTINCT inv.InvoiceNo) AS invoice_count,
            SUM(inv.NetTotal) AS total_sales,
            SUM(inv.TaxAmount) AS total_tax,
            SUM(inv.DiscountAmount) AS total_discount
        FROM SalesInvoices inv
        WHERE inv.InvoiceDate BETWEEN :start AND :end
          AND inv.Status = 'Posted'
    """,
    "revenue_by_month": """
        SELECT
            FORMAT(inv.InvoiceDate, 'yyyy-MM') AS month,
            SUM(inv.NetTotal) AS revenue
        FROM SalesInvoices inv
        WHERE inv.InvoiceDate BETWEEN :start AND :end
          AND inv.Status = 'Posted'
        GROUP BY FORMAT(inv.InvoiceDate, 'yyyy-MM')
        ORDER BY month
    """,
    "top_customers": """
        SELECT TOP (:limit)
            c.CustomerName,
            SUM(inv.NetTotal) AS total_sales,
            COUNT(DISTINCT inv.InvoiceNo) AS invoices
        FROM SalesInvoices inv
        JOIN Customers c ON c.CustomerID = inv.CustomerID
        WHERE inv.InvoiceDate BETWEEN :start AND :end
          AND inv.Status = 'Posted'
        GROUP BY c.CustomerName
        ORDER BY total_sales DESC
    """,
    "expenses_summary": """
        SELECT
            a.AccountName,
            SUM(j.Debit - j.Credit) AS total
        FROM JournalEntries j
        JOIN Accounts a ON a.AccountID = j.AccountID
        WHERE a.AccountType = 'Expense'
          AND j.EntryDate BETWEEN :start AND :end
        GROUP BY a.AccountName
        ORDER BY total DESC
    """,
    "invoice_lookup": """
        SELECT
            inv.InvoiceNo, inv.InvoiceDate, inv.NetTotal, inv.Status,
            c.CustomerName
        FROM SalesInvoices inv
        JOIN Customers c ON c.CustomerID = inv.CustomerID
        WHERE inv.InvoiceNo = :invoice_no
    """,
    "cash_balance": """
        SELECT
            a.AccountName,
            SUM(j.Debit - j.Credit) AS balance
        FROM JournalEntries j
        JOIN Accounts a ON a.AccountID = j.AccountID
        WHERE a.AccountType IN ('Cash', 'Bank')
        GROUP BY a.AccountName
    """,
}

READONLY_PATTERN = re.compile(r"^\s*(SELECT|WITH)\b", re.IGNORECASE | re.DOTALL)


class AccountingConnector:
    """Runs whitelisted, read-only queries against the accounting database."""

    def __init__(self, db_url: str | None = None):
        self.db_url = db_url or os.getenv("ACCOUNTING_DB_URL", "")
        self._engine: Engine | None = None

    @property
    def available(self) -> bool:
        return bool(self.db_url)

    @property
    def engine(self) -> Engine:
        if self._engine is None:
            # Example: mssql+pyodbc://user:pass@server/OnyxDB?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes
            self._engine = create_engine(self.db_url, pool_size=3, pool_recycle=1800)
        return self._engine

    def run(self, query_name: str, **params: Any) -> list[dict[str, Any]]:
        if not self.available:
            raise RuntimeError("Accounting database is not configured. Set ACCOUNTING_DB_URL.")
        query = QUERY_MAP.get(query_name)
        if query is None:
            raise ValueError(f"Unknown accounting query '{query_name}'. Allowed: {list(QUERY_MAP)}")
        if not READONLY_PATTERN.match(query):
            raise PermissionError("Only read-only (SELECT) queries are allowed.")
        with self.engine.connect() as conn:
            result = conn.execute(text(query), params)
            return [dict(row) for row in result.mappings()]


connector = AccountingConnector()
