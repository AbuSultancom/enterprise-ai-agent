# Enterprise AI Agent Platform

A self-hosted, open-source AI agent platform for companies — inspired by OpenClaw. Deploy it on your own infrastructure, connect local or cloud LLMs, plug in tools, and let employees chat with an agent that knows your company's documents.

## Features

- **Multi-LLM gateway** — run fully local via Ollama (data never leaves your network) or route to any OpenAI-compatible API (DeepSeek, Qwen, vLLM...) with one config change
- **ReAct agent loop** — the agent reasons, calls tools, observes results, and iterates until it has an answer
- **Pluggable tools** — built-in: web search, calculator, file reader, clock. Add your own with one decorator
- **Company knowledge (RAG)** — upload internal documents; the agent retrieves and answers from them
- **Accounting integration (ERP)** — connects read-only to your accounting database (Onyx Pro / SQL Server) so the agent answers "how much did we sell this month?", "top customers?", "cash balance?" — see [docs/ONYX_SETUP.md](docs/ONYX_SETUP.md)
- **Role-based access** — `admin` and `user` roles via API keys (SSO/LDAP-ready design)
- **Web dashboard** — clean chat UI served by the API, no separate frontend build
- **One-command deploy** — Docker Compose with Ollama included

## Architecture

```
Dashboard (chat UI)
      │
      ▼
FastAPI API ── auth + RBAC (admin / user)
      │
      ├──▶ Agent (ReAct loop) ──▶ Tool Registry (web · calc · files · accounting · custom)
      │
      ├──▶ LLM Gateway ──▶ Ollama (local) / OpenAI-compatible (cloud)
      │
      ├──▶ Knowledge Store (company docs, RAG-ready)
      │
      └──▶ Accounting Connector ──▶ Onyx Pro DB (SQL Server, read-only)
```

## Quick start

```bash
cd deploy
docker compose up -d
# pull a model (first time only)
docker exec -it deploy-ollama-1 ollama pull qwen2.5:7b
```

Open **http://localhost:8000** — log in with the dev key `dev-admin-key`.

### Local development (no Docker)

```bash
pip install -r requirements.txt
ollama pull qwen2.5:7b          # or any model you prefer
uvicorn api.main:app --reload
```

## Accounting integration (Onyx Pro)

The agent ships with 6 accounting tools: sales summary, revenue by month, top
customers, expenses summary, invoice lookup, and cash/bank balances. Setup guide:
[docs/ONYX_SETUP.md](docs/ONYX_SETUP.md).

## Configuration (environment variables)

| Variable | Default | Description |
|---|---|---|
| `API_KEYS` | `admin:dev-admin-key` | Comma-separated `role:key` pairs. Roles: `admin`, `user` |
| `DEFAULT_MODEL` | `ollama:qwen2.5:7b` | Model as `provider:name` |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | Any OpenAI-compatible endpoint |
| `OPENAI_API_KEY` | — | Key for the cloud provider |
| `MEMORY_DB_PATH` | `/data/knowledge.json` | Knowledge store file |
| `ACCOUNTING_DB_URL` | — | Accounting DB (SQLAlchemy URL, SQL Server for Onyx Pro) |

Switch providers per request: `{"message": "...", "model": "openai:deepseek-chat"}`.

## API

| Endpoint | Method | Role | Description |
|---|---|---|---|
| `/health` | GET | — | Service + provider + accounting status |
| `/v1/chat` | POST | user+ | Chat with the agent |
| `/v1/tools` | GET | user+ | List registered tools |
| `/v1/knowledge` | GET/POST | admin to add | Manage knowledge documents |
| `/v1/knowledge/{id}` | DELETE | admin | Delete a document |
| `/v1/admin/rotate-key` | POST | admin | Issue a new API key |
| `/v1/accounting/query` | POST | admin | Run a whitelisted read-only accounting query |

Example:

```bash
curl -X POST http://localhost:8000/v1/chat \
  -H "X-API-Key: dev-admin-key" \
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

- [ ] Semantic search (Chroma/Qdrant embeddings) for the knowledge store
- [ ] Multi-agent orchestration and scheduled tasks
- [ ] SSO / LDAP authentication
- [ ] Audit logging per user
- [ ] Streaming responses (SSE)

## License

MIT
