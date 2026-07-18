# Installation & Setup Guide

One command after downloading the project — the wizard asks about everything
(AI model, WhatsApp, Telegram, accounting, permissions) and generates all config files.

## 1. Download

```bash
git clone https://github.com/AbuSultancom/enterprise-ai-agent.git
cd enterprise-ai-agent
```

## 2. Run the setup wizard

```bash
python setup.py        # or: python3 setup.py
```

The wizard (OpenClaw/Hermes-style onboarding) walks you through **7 steps** with a progress bar — press **Enter** to accept any default:

### Step 1 — AI model
Choose the agent's brain:
- **Ollama** (local, private, free) — pick any model, default `qwen2.5:7b`; the wizard checks Ollama is reachable
- **DeepSeek / OpenAI / any OpenAI-compatible API** — enter base URL + API key; the wizard **tests the key live** before saving

### Step 2 — Agent identity
- **Name** shown to users
- **Answer language**: auto (reply in the user's language) / Arabic / English
- **Personality** — one line of instructions injected into the system prompt

### Step 3 — Access & security
- Auto-generates secure **admin** and **user** API keys (or enter your own)
- Keys are shown once at the end — save them

### Step 4 — Channels (WhatsApp & Telegram)
**WhatsApp** (QR login):
- Optional **prefix** (e.g. `!ai `) so the bot only replies to prefixed messages
- Ignore group chats (default: yes)
- Which **role** WhatsApp users get: `user` (safe, recommended) or `admin`
- **Allowed phone numbers** — whitelist (international format, comma-separated; empty = everyone)

**Telegram** (bot token):
- Create a bot with **@BotFather** in Telegram, paste the token — the wizard verifies it via `getMe`
- **Allowed Telegram users** — user IDs or @usernames (comma-separated; empty = everyone)

### Step 5 — Accounting (Onyx Pro)
- SQL Server host, port, database, user, password (with live TCP connection test)
- Builds the `ACCOUNTING_DB_URL` connection string for you
- Use a **read-only** DB user — the agent only runs SELECT queries anyway
- Reminder: adapt table names in `connectors/accounting.py` to your Onyx schema

### Step 6 — Agent permissions (what the AI can read & do)
Toggle each capability:
- Web search / calculator / date-time
- Reading files from the workspace (default: off)
- Querying accounting data
- Using the knowledge base (RAG) in answers

### Step 7 — Finish & link WhatsApp
- Summary box shows everything you configured + your API keys
- The wizard launches the bridge and prints the **QR right inside the wizard**
- Scan it (WhatsApp → Linked devices → Link a device); the wizard detects the
  connection and confirms it — the session is saved, no QR needed next time

## 3. What the wizard generates

| File | Contents |
|---|---|
| `.env` | API keys, model, channels & accounting settings |
| `config/settings.json` | Agent identity, permissions & accounting query whitelist (enforced by the API at runtime) |

## 4. Start

```bash
python start.py        # agent + dashboard + WhatsApp + Telegram, all at once
```

Or with Docker:

```bash
cd deploy
docker compose up -d --build
```

| Service | URL |
|---|---|
| Web dashboard | http://localhost:8000 (log in with admin key) |
| WhatsApp QR scan | http://localhost:3001 |

First time with Ollama:
```bash
docker exec -it deploy-ollama-1 ollama pull qwen2.5:7b
```

## Changing settings later

- **Quick change:** edit `.env` or `config/settings.json`, then restart
- **Full reconfigure:** run `python setup.py` again

## Manual setup (without the wizard)

Copy `.env.example` to `.env`, fill in values, and edit `config/settings.json`.
All variables are documented in the README.
