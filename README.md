# Enterprise AI Agent Platform 🧠🚀

[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Node.js](https://img.shields.io/badge/Node.js-43853D?style=for-the-badge&logo=node.js&logoColor=white)](https://nodejs.org/)
[![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org/)
[![Ollama](https://img.shields.io/badge/Ollama-Local-black?style=for-the-badge)](https://ollama.com/)
[![Tests](https://img.shields.io/github/actions/workflow/status/AbuSultancom/enterprise-ai-agent/ci.yml?label=tests&style=for-the-badge)](https://github.com/AbuSultancom/enterprise-ai-agent/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](LICENSE)

A self-hosted, open-source AI agent platform designed for enterprises. Deploy it on your own infrastructure, connect local or cloud LLMs, plug in tools, and let employees interact with an intelligent agent that understands your company's documents and connects securely to your ERP databases.

---

## 📖 Comprehensive Documentation

We have moved detailed guides to the `docs/` folder for better organization:
- 🏗️ **[Architecture Guide](docs/ARCHITECTURE.md):** Learn how the Multi-Agent Orchestrator, LLM Gateway, and API components interact.
- 🛠️ **[Tools Registry](docs/TOOLS.md):** Browse the ~50 available tools (ERP Connectors, Web Search, Weather, HR Directories).
- 📡 **[API Reference](docs/API.md):** View the complete list of REST endpoints and authentication methods.
- ⚙️ **[Configuration Guide](docs/CONFIGURATION.md):** Learn how to configure `.env` and `accounting_schema.json`.
- 📋 **[Changelog](docs/CHANGELOG.md):** What's new in each release.

---

## ✨ Key Features

- **🤖 Multi-Agent Orchestrator:** Automatically routes queries to specialized sub-agents.
- **💬 Smart Streaming Chat:** Real-time replies supporting English & Arabic queries.
- **📊 Modern Web Dashboard:** Beautiful dark-mode UI with animated metrics, SVG rings, and live session uptime.
- **💾 Persistent Memory:** Long-term memory store powered by SQLite.
- **📤 Chat Export:** Export your conversations cleanly to Markdown, JSON, or HTML Reports.
- **📱 Communication Bridges:** Full bot functionality on WhatsApp (via QR scan) and Telegram.
- **🏦 ERP Database Connectors:** Secure, read-only connections to Onyx Pro, SQL Server, Oracle, MySQL, Postgres.
- **📚 Knowledge Base (RAG):** Upload company documents for instant hybrid BM25+vector retrieval.
- **🔒 Advanced Security:** Rate limiting, security headers, role-based access (Admin/User).
- **🌐 5 LLM Providers:** Ollama (local), OpenAI, Anthropic Claude, Google Gemini, HuggingFace.
- **♻️ Auto Retry:** Exponential backoff on transient network errors.

---

## 📥 Quickstart Installation

### Prerequisites
- **Python** ≥ 3.11
- **Node.js** ≥ 18 (Required for WhatsApp integration)
- **Ollama** (Optional, for running local, offline models)

### Option A — One-Click (Windows)
```bat
install.bat
```
> The installer checks Python, Node.js, creates a virtual environment, installs dependencies, runs pre-flight diagnostics, and launches the setup wizard.

### Option B — Manual
```bash
git clone https://github.com/AbuSultancom/enterprise-ai-agent.git
cd enterprise-ai-agent

# Create and activate virtual environment
python -m venv venv
# Windows: venv\Scripts\activate
# Mac/Linux: source venv/bin/activate

# Install dependencies
pip install -e ".[dev]"

# Run pre-flight diagnostics
python install_check.py

# Configure API keys, LLM provider, databases
python setup.py

# Start the platform
python start.py
```

### Access Points
- 🌐 **Dashboard:** [http://localhost:8000](http://localhost:8000)
- 📱 **WhatsApp QR Scanner:** [http://localhost:3001](http://localhost:3001)
- 🤖 **Swagger API Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 🌐 Supported LLM Providers

| Provider | Model Prefix | Key Env Var |
|---|---|---|
| Ollama (Local) | `ollama:qwen2.5:7b` | — |
| OpenAI | `openai:gpt-4o-mini` | `OPENAI_API_KEY` |
| Anthropic Claude | `anthropic:claude-3-5-sonnet-20241022` | `ANTHROPIC_API_KEY` |
| Google Gemini | `gemini:gemini-2.0-flash` | `GEMINI_API_KEY` |
| HuggingFace | `huggingface:mistralai/Mistral-7B-Instruct-v0.3` | `HF_TOKEN` |

---

## 🔒 Security

- **Rate Limiting:** 60 req/min for users, 300 for admins (sliding window)
- **Security Headers:** X-Frame-Options, X-Content-Type-Options, HSTS, Referrer-Policy
- **PII Masking:** Credit cards, national IDs, and tokens are automatically redacted before cloud LLM calls
- **Audit Logging:** All tool calls and admin actions are logged with automatic 50 MB rotation
- **Read-only ERP:** All database connectors enforce read-only execution

---

## 🧪 Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage report
pytest tests/ --cov=. --cov-report=term-missing

# Skip integration tests (no live services needed)
pytest tests/ -m "not integration"
```

---

## 🛠️ Troubleshooting

**Problem:** `install_check.py` reports Ollama not running  
**Solution:** Run `ollama serve` in a separate terminal, then `ollama pull qwen2.5:7b`

**Problem:** WhatsApp bridge not working  
**Solution:** Ensure Node.js ≥ 18 is installed and `WHATSAPP_ENABLED=true` in `.env`

**Problem:** 403 Forbidden on API calls  
**Solution:** Check `ADMIN_KEY` / `USER_KEY` in `.env` and pass `X-API-Key: <key>` header

**Problem:** "Rate limit exceeded" (429 error)  
**Solution:** Reduce request frequency or increase limits in `api/middleware.py`

---

## 📝 License

This project is licensed under the MIT License. © 2026 AbuSultancom
