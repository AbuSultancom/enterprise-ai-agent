# Connecting Onyx Pro to the AI Agent

Onyx Pro typically stores its data in **Microsoft SQL Server**. This guide connects the
agent to it in **read-only** mode so it can answer questions about sales, revenue,
expenses, customers, invoices, and cash balances.

## 1. Create a read-only database user (recommended)

Run this on the SQL Server hosting your Onyx database (adjust names):

```sql
CREATE LOGIN ai_agent_reader WITH PASSWORD = 'StrongPassword!123';
USE OnyxDB;  -- your Onyx database name
CREATE USER ai_agent_reader FOR LOGIN ai_agent_reader;
EXEC sp_addrolemember 'db_datareader', 'ai_agent_reader';
```

## 2. Set the connection string

In `.env` (or `docker-compose.yml` environment):

```
ACCOUNTING_DB_URL=mssql+pyodbc://ai_agent_reader:StrongPassword!123@SERVER_IP/OnyxDB?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes
```

The Docker image already includes the Microsoft ODBC Driver 18.

## 3. Adapt the queries to your schema (important)

Table and column names differ between Onyx versions and installations.
Open `connectors/accounting.py` and edit `QUERY_MAP` to match your schema:

| Query key | What it returns | Tables involved (adjust these) |
|---|---|---|
| `sales_summary` | Invoice count, total sales, tax, discounts | Sales invoices table |
| `revenue_by_month` | Revenue per month | Sales invoices table |
| `top_customers` | Best customers by sales | Invoices + customers |
| `expenses_summary` | Expenses per account | Journal + chart of accounts |
| `invoice_lookup` | One invoice by number | Invoices + customers |
| `cash_balance` | Cash & bank balances | Journal + accounts |

Ask your Onyx partner/reseller for the **data dictionary** of your version — it lists
the exact table names. Replace `SalesInvoices`, `Customers`, `JournalEntries`,
`Accounts` and their columns accordingly.

## 4. Test

```bash
curl http://localhost:8000/health
# -> "accounting_db": true

curl -X POST http://localhost:8000/v1/accounting/query \
  -H "X-API-Key: dev-admin-key" \
  -H "Content-Type: application/json" \
  -d '{"query": "sales_summary", "params": {"start": "2026-07-01", "end": "2026-07-31"}}'
```

Then just ask the agent in the dashboard: **"How much did we sell this month?"**

## Security notes

- The connector only executes whitelisted `SELECT` queries from `QUERY_MAP` — no
  free-form SQL from users or the LLM.
- Always use a `db_datareader` account, never the Onyx admin/sa account.
- The `/v1/accounting/query` endpoint is restricted to the `admin` role.
