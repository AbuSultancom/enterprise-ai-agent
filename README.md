# Enterprise AI Agent Platform

A self-hosted, open-source AI agent platform for companies — inspired by OpenClaw. Deploy it on your own infrastructure, connect local or cloud LLMs, plug in tools, and let employees chat with an agent that knows your company's documents.

## Features

- **Multi-LLM gateway** — run fully local via Ollama (data never leaves your network) or route to any OpenAI-compatible API (DeepSeek, Qwen, vLLM...) with one config change
- **ReAct agent loop** — the agent reasons, calls tools, observes results, and iterates until it has an answer
- **Pluggable tools** — built-in: web search, calculator, file reader, clock. Add your own with one decorator
- **Company knowledge (RAG)** — upload PDF/Word/text documents from the dashboard; semantic search via embeddings with keyword fallback
- **Streaming chat (SSE)** — answers appear token by token
- **Audit log** — every chat, upload, and accounting query is logged (admin-only access)
- **Accounting integration (ERP)** — connects read-only to your accounting database (Onyx Pro / SQL Server) so the agent answers "how much did we sell this month?", "top customers?", "cash balance?" — see [docs/ONYX_SETUP.md](docs/ONYX_SETUP.md)
- **WhatsApp integration** — customers/staff chat with the agent on WhatsApp; login once via QR code (like WhatsApp Web) — see [docs/WHATSAPP_SETUP.md](docs/WHATSAPP_SETUP.md)
- **Role-based access** — `admin` and `user` roles via API keys (SSO/LDAP-ready design)
- **Bilingual dashboard** — Arabic (RTL) / English chat UI served by the API, no separate frontend build
- **One-command launcher** — `python start.py` does everything: wizard, deps, agent, WhatsApp with QR in the terminal
- **Docker deploy** — Docker Compose with Ollama included
- **Interactive setup wizard** — `python setup.py` asks about everything (AI model, WhatsApp, accounting, what the agent may read/do) and generates `.env` + `config/settings.json`

## Architecture

```
WhatsApp ──▶ whatsapp bridge (QR login)
                  │
Dashboard ────────┼──────▶ FastAPI API (auth + RBAC + permissions + audit)
 (AR/EN UI)       │              │
                  │              ├──▶ Agent (ReAct, streaming) ──▶ Tools (web · calc · files · accounting)
                  │              ├──▶ LLM Gateway ──▶ Ollama (local) / OpenAI-compatible (cloud)
                  │              ├──▶ Knowledge Store (PDF/Word upload, semantic + keyword search)
                  │              └──▶ Accounting Connector ──▶ Onyx Pro DB (SQL Server, read-only)
```

## Quick start

### Easiest — one command does everything

```bash
git clone https://github.com/AbuSultancom/enterprise-ai-agent.git
cd enterprise-ai-agent
python start.py
```

`start.py` runs the setup wizard (first time only), installs dependencies,
starts the agent API + dashboard, starts the WhatsApp bridge, and prints the
**WhatsApp QR code right in the terminal**. Ctrl+C stops everything.

- Web dashboard: **http://localhost:8000**
- WhatsApp QR: printed in terminal + **http://localhost:3001**

### With Docker

```bash
python setup.py          # interactive wizard: AI model, WhatsApp, accounting, permissions
cd deploy
docker compose up -d --build
# pull a model (first time only)
docker exec -it deploy-ollama-1 ollama pull qwen2.5:7b
```

Full installation guide: [docs/SETUP.md](docs/SETUP.md)

### Local development (no Docker)

```bash
pip install -r requirements.txt
ollama pull qwen2.5:7b          # or any model you prefer
uvicorn api.main:app --reload
```

## Configuration (environment variables)

| Variable | Default | Description |
|---|---|---|
| `ADMIN_KEY` / `USER_KEY` | generated | API keys per role |
| `DEFAULT_MODEL` | `ollama:qwen2.5:7b` | Model as `provider:name` |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server |
| `OPENAI_BASE_URL` / `OPENAI_API_KEY` | — | Cloud provider (DeepSeek/OpenAI/...) |
| `EMBED_MODEL` / `OPENAI_EMBED_MODEL` | `nomic-embed-text` / `text-embedding-3-small` | Embedding models for semantic search |
| `ACCOUNTING_DB_URL` | — | Accounting DB (SQL Server for Onyx Pro) |
| `WHATSAPP_ENABLED` / `BOT_PREFIX` / `WHATSAPP_ROLE` | `true` / `!ai ` / `user` | WhatsApp bridge controls |
| `AUDIT_LOG_PATH` | `/data/audit.jsonl` | Audit log file |

Switch providers per request: `{"message": "...", "model": "openai:deepseek-chat"}`.

## API

| Endpoint | Method | Role | Description |
|---|---|---|---|
| `/health` | GET | — | Service + provider status |
| `/v1/chat` | POST | user+ | Chat with the agent |
| `/v1/chat/stream` | POST | user+ | Chat with streaming (SSE) |
| `/v1/tools` | GET | user+ | List registered tools |
| `/v1/knowledge` | GET/POST | admin to add | Manage knowledge documents |
| `/v1/knowledge/upload` | POST | admin | Upload PDF/Word/text into the knowledge base |
| `/v1/knowledge/{id}` | DELETE | admin | Delete a document |
| `/v1/admin/rotate-key` | POST | admin | Issue a new API key |
| `/v1/admin/audit` | GET | admin | Read the audit log |
| `/v1/accounting/query` | POST | admin | Run a whitelisted read-only accounting query |

Example:

```bash
curl -X POST http://localhost:8000/v1/chat \
  -H "X-API-Key: <admin-key>" \
  -H "Content-Type: application/json" \
  -d '{"message": "How much did we sell this month?"}'
```

## Adding a custom tool

```python
# tools/builtin.py (or your own module imported in api/main.py)
from tools.registry import registry

@registry.register(
    description="Look up an employee in the HR database.",
    parameters={"employee_id": {"type": "str"}},
)
def hr_lookup(employee_id: str) -> str:
    ...
```

The agent discovers and can call it immediately — no other changes needed.

## Roadmap

- [x] Semantic search (embeddings with keyword fallback) for the knowledge store
- [x] File upload (PDF / Word / text) into the knowledge base from the dashboard
- [x] Streaming responses (SSE)
- [x] Audit log per user (`/v1/admin/audit`)
- [x] Arabic / English dashboard (RTL)
- [x] One-command launcher (`start.py`) with terminal QR
- [ ] Multi-agent orchestration and scheduled tasks
- [ ] SSO / LDAP authentication

## License

MIT
