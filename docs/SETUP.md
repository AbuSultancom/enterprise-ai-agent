# Installation & Setup Guide

One command after downloading the project — the wizard asks about everything
(AI model, WhatsApp + allowed numbers, accounting, permissions) and can link
your WhatsApp right inside the wizard.

## 1. Download

```bash
git clone https://github.com/AbuSultancom/enterprise-ai-agent.git
cd enterprise-ai-agent
```

## 2. Run the setup wizard

```bash
python setup.py        # or: python3 setup.py
```

The wizard walks you through 6 sections — press **Enter** to accept any default:

### Section 1 — AI model
Choose the agent's brain:
- **Ollama** (local, private, free) — pick any model, default `qwen2.5:7b`
- **DeepSeek / OpenAI / any OpenAI-compatible API** — enter base URL + API key

### Section 2 — Access & security
- Auto-generates secure **admin** and **user** API keys (or enter your own)
- Keys are shown once at the end — save them

### Section 3 — WhatsApp (QR)
- Enable/disable the WhatsApp bridge
- Optional **prefix** (e.g. `!ai `) so the bot only replies to prefixed messages
- Ignore group chats (default: yes)
- Which **role** WhatsApp users get: `user` (safe, recommended) or `admin`
- **Allowed phone numbers** — whitelist of numbers that may talk to the bot
  (international format, comma-separated; empty = everyone)

### Section 4 — Accounting (Onyx Pro)
- SQL Server host, port, database, user, password
- Builds the `ACCOUNTING_DB_URL` connection string for you
- Use a **read-only** DB user — the agent only runs SELECT queries anyway
- Reminder: adapt table names in `connectors/accounting.py` to your Onyx schema

### Section 5 — Agent permissions (what the AI can read & do)
Toggle each capability:
- Web search / calculator / date-time
- Reading files from the workspace (default: off)
- Querying accounting data
- Using the knowledge base (RAG) in answers

### Section 6 — Link WhatsApp now
- The wizard launches the bridge and prints the **QR right inside the wizard**
- Scan it (WhatsApp → Linked devices → Link a device); the wizard detects the
  connection and confirms it — the session is saved, no QR needed next time

## 3. What the wizard generates

| File | Contents |
|---|---|
| `.env` | API keys, model, WhatsApp & accounting settings, allowed numbers |
| `config/settings.json` | Agent permissions & accounting query whitelist (enforced by the API at runtime) |

## 4. Start

```bash
python start.py     # everything: agent + dashboard + WhatsApp bridge
```

Or with Docker:

```bash
cd deploy
docker compose up -d --build
```

| Service | URL |
|---|---|
| Web dashboard | http://localhost:8000 (log in with admin key) |
| WhatsApp QR scan | http://localhost:3001 (or the terminal QR) |

First time with Ollama:
```bash
ollama pull qwen2.5:7b
```

## Changing settings later

- **Quick change:** edit `.env` or `config/settings.json`, then restart
- **Full reconfigure:** run `python setup.py` again

## Manual setup (without the wizard)

Copy `.env.example` to `.env`, fill in values, and edit `config/settings.json`.
All variables are documented in the README.
