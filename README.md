# Enterprise AI Agent Platform 🧠🚀

[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Node.js](https://img.shields.io/badge/Node.js-43853D?style=for-the-badge&logo=node.js&logoColor=white)](https://nodejs.org/)
[![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org/)
[![Ollama](https://img.shields.io/badge/Ollama-Local-black?style=for-the-badge)](https://ollama.com/)

A self-hosted, open-source AI agent platform designed for enterprises. Deploy it on your own infrastructure, connect local or cloud LLMs, plug in tools, and let employees interact with an intelligent agent that understands your company's documents and connects securely to your ERP databases.

---

## 📖 Comprehensive Documentation

We have moved detailed guides to the `docs/` folder for better organization:
- 🏗️ **[Architecture Guide](docs/ARCHITECTURE.md):** Learn how the Multi-Agent Orchestrator, LLM Gateway, and API components interact.
- 🛠️ **[Tools Registry](docs/TOOLS.md):** Browse the ~50 available tools (ERP Connectors, Web Search, Weather, HR Directories).
- 📡 **[API Reference](docs/API.md):** View the complete list of REST endpoints and authentication methods.
- ⚙️ **[Configuration Guide](docs/CONFIGURATION.md):** Learn how to configure `.env` and `accounting_schema.json`.

---

## ✨ Key Features

- **🤖 Multi-Agent Orchestrator:** Automatically routes queries to specialized sub-agents.
- **💬 Smart Streaming Chat:** Real-time replies supporting English & Arabic queries.
- **📊 Modern Web Dashboard:** Beautiful dark-mode UI with animated metrics, SVG rings, and live session uptime.
- **💾 Persistent Memory:** Long-term memory store powered by SQLite.
- **📤 Chat Export:** Export your conversations cleanly to Markdown, JSON, or HTML Reports.
- **📱 Communication Bridges:** Full bot functionality on WhatsApp (via QR scan) and Telegram.
- **🏦 ERP Database Connectors:** Secure, read-only connections to Onyx Pro, SQL Server, Oracle, MySQL, Postgres.
- **📚 Knowledge Base (RAG):** Upload company documents for instant vector-based retrieval.
- **🔒 Advanced Security:** Separate Admin and User scopes with strict read-only execution safety.

---

## 📥 Quickstart Installation

### Prerequisites
- **Python** ≥ 3.11
- **Node.js** ≥ 18 (Required for WhatsApp integration)
- **Ollama** (Optional, for running local, offline models)

### 1. Clone & Setup
```bash
git clone https://github.com/AbuSultancom/enterprise-ai-agent.git
cd enterprise-ai-agent

# Create and activate a virtual environment
python -m venv venv
# Windows: venv\Scripts\activate
# Mac/Linux: source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure via Wizard
```bash
python setup.py
```
*The wizard will guide you through setting up API keys, LLM providers (Ollama or OpenAI), and database connections.*

### 3. Launch the Platform
```bash
python start.py
```

### Access Points:
- 🌐 **Dashboard:** [http://localhost:8000](http://localhost:8000)
- 📱 **WhatsApp QR Scanner:** [http://localhost:3001](http://localhost:3001)
- 🤖 **Swagger API Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 📝 License

This project is licensed under the MIT License. © 2026 AbuSultancom
