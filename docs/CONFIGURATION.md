# Configuration Guide

The Enterprise AI Agent is highly configurable via environment variables and JSON configuration files.

## 1. Environment Variables (`.env`)

The core application settings are defined in the `.env` file located in the root directory. Copy `.env.example` to `.env` to get started.

```env
# ─── Authentication (Required) ──────────
ADMIN_KEY=your-secure-admin-key
USER_KEY=your-secure-user-key

# ─── API Keys (Optional) ────────────────
# If omitted, the system falls back to Local Ollama models
OPENAI_API_KEY=sk-your-openai-key
HF_TOKEN=hf_your-huggingface-token

# ─── Bridges (Optional) ─────────────────
WHATSAPP_ENABLED=true
TELEGRAM_BOT_TOKEN=your-telegram-token

# ─── ERP Database (Legacy fallback) ──────
# Used if accounting_schema.json is missing
ACCOUNTING_DB_URL=mssql+pyodbc://user:pass@192.168.1.10/OnyxDB?driver=ODBC+Driver+18+for+SQL+Server
```

---

## 2. Dynamic Accounting Schema (`config/accounting_schema.json`)

To securely query your internal enterprise databases, the agent uses a strictly defined schema mapping. This file tells the agent exactly which tables and columns it is allowed to query, and translates your Arabic/internal column names into English concepts the LLM understands.

File location: `config/accounting_schema.json`

### Example Configuration:
```json
{
  "onyx": {
    "enabled": true,
    "description": "Onyx Pro Accounting Database",
    "db_url": "mssql+pyodbc://user:pass@192.168.1.10/OnyxDB?driver=ODBC+Driver+18+for+SQL+Server",
    "tables": {
      "sales": {
        "actual_name": "Sales_Invoice_Master",
        "columns": {
          "id": "Invoice_ID",
          "date": "Invoice_Date",
          "total": "Net_Total",
          "customer_id": "Cust_Code"
        }
      },
      "vendors": {
        "actual_name": "Vendors_Table",
        "columns": {
          "id": "Vendor_ID",
          "name": "Vendor_Name",
          "balance": "Current_Balance"
        }
      }
    }
  }
}
```

### Why use a mapping file?
1. **Security:** The LLM cannot "guess" or "hallucinate" queries to sensitive HR or Payroll tables if they are not explicitly defined here.
2. **Translation:** Legacy ERPs often use cryptic column names (e.g., `TBL_SLS_01_HDR`). This file maps `TBL_SLS_01_HDR` to a concept the AI understands (`sales`).

---

## 3. Web Dashboard Config (`dashboard/index.html`)

The dashboard connects to the backend API. By default, it expects the backend to run on `localhost:8000`.

If you host the backend on a server, update the `config.API_BASE` variable at the top of the `dashboard/index.html` file:

```javascript
const config = {
  // Change this if your API is hosted remotely
  API_BASE: 'http://192.168.1.100:8000' 
};
```
