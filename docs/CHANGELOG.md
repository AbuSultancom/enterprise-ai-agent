# Changelog

All notable changes to **Enterprise AI Agent** are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [0.6.0] — 2026-08-09

### 🚀 Added
- **Anthropic Claude provider** — use `anthropic:claude-3-5-sonnet-20241022` as model prefix
- **Google Gemini provider** — use `gemini:gemini-2.0-flash` as model prefix
- **Exponential backoff retry** — transient network errors auto-retry (3 attempts, 1s/2s/4s)
- **`memory/cache.py`** — LRU cache with TTL and `@cache.cached()` decorator for tools & embeddings
- **`api/middleware.py`** — sliding-window rate limiting (60 req/min user, 300 admin), security headers (X-Frame-Options, X-Content-Type-Options, Referrer-Policy, HSTS), request timing header
- **`api/dependencies.py`** — centralized auth, API key store, audit helper with 50MB log rotation
- **API Routers** — `api/main.py` split into `api/routers/chat.py`, `conversations.py`, `knowledge.py`, `accounting.py`, `admin.py`
- **`install_check.py`** — pre-flight diagnostic script (Python, venv, packages, Node.js, env keys, Ollama, config, dashboard)
- **`pyproject.toml`** — replaces `requirements.txt`; adds optional dependency groups (`erp`, `dev`, `all`), Ruff config, pytest config, coverage config
- **`tests/conftest.py`** — shared fixtures: mock gateway, temp stores, FastAPI async test client, auth headers
- **`tests/test_api.py`** — 15+ API endpoint integration tests (health, tools, auth, security headers, knowledge, settings, conversations)
- **`tests/test_gateway.py`** — gateway unit tests (PII masking edge cases, retry backoff, provider routing, fallback, health)
- **`.github/workflows/ci.yml`** — GitHub Actions: Python 3.11+3.12 matrix, Ruff lint, Bandit security scan, pytest+coverage, Codecov, auto-release on tags

### 🔧 Changed
- **`api/main.py`** — reduced from 612 → ~110 lines (wiring only)
- **`llm_gateway/gateway.py`** — added `asyncio`, `logging`, retry helper, Anthropic+Gemini providers, improved `health()` to show all 5 providers
- **`install.bat`** — added Node.js check, uses `pyproject.toml` when available, runs `install_check.py`, skips wizard if already configured
- **`.env.example`** — comprehensive documentation for all env vars (Anthropic, Gemini, SMTP, channels, performance)
- **`agent_core/audit.py`** — referenced from centralized `api/dependencies.py` audit function with log rotation

### 📦 Dependencies
- Pinned all versions in `pyproject.toml` (from `>=` to `==`)
- Added `python-dotenv` as explicit dependency
- Added optional `pyodbc` under `[erp]` group

---

## [0.5.0] — 2026-08-02

### Added
- Multi-database accounting connector (Onyx Pro, SQL Server, Oracle, MySQL, Postgres)
- Chat export to Markdown, JSON, HTML
- Hybrid BM25 + vector RAG search
- WhatsApp and Telegram bridges
- HuggingFace provider
- Vision model support (GPT-4o, Claude)
- Zakat and VAT calculators
- 33+ built-in tools

---

## [0.1.0] — 2026-07-01

### Added
- Initial release: FastAPI server, Ollama/OpenAI gateway, knowledge base, SQLite memory
