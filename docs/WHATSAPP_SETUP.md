# WhatsApp Integration (QR login)

The `whatsapp/` service bridges WhatsApp to the AI agent using
[whatsapp-web.js](https://github.com/pedroslopez/whatsapp-web.js) — the same
protocol as WhatsApp Web. You scan a QR code once, and the session persists.

> Warning: this uses the **unofficial** WhatsApp Web protocol. WhatsApp may
> restrict or ban numbers that use unofficial clients. For a mission-critical
> business number, use the official **WhatsApp Business Platform (Cloud API)**
> instead.

## How it works

```
Customer WhatsApp message
        |
        v
whatsapp-web.js bridge  (session via QR, stored in volume)
        |
        v  POST /v1/chat  (X-API-Key)
   AI Agent  --> tools: sales, invoices, knowledge base...
        |
        v
Reply sent back to the customer on WhatsApp
```

## Setup

```bash
cd deploy
docker compose up -d --build
```

1. Open **http://localhost:3001**
2. On your phone: WhatsApp -> **Linked devices** -> **Link a device**
3. Scan the QR code shown on the page
4. Done — the page shows "WhatsApp connected"

The session is stored in the `whatsapp-session` volume, so you only scan once
(unless you log out from the phone or delete the volume).

## Configuration (environment variables of the `whatsapp` service)

| Variable | Default | Description |
|---|---|---|
| `AGENT_URL` | `http://agent:8000` | Agent API base URL |
| `AGENT_API_KEY` | `dev-admin-key` | API key used to call the agent |
| `BOT_PREFIX` | _(empty)_ | If set (e.g. `!ai `), the bot only replies to messages starting with this prefix |
| `IGNORE_GROUPS` | `true` | Ignore messages from group chats |
| `WHATSAPP_PORT` | `3001` | Port of the QR/status web page |

## Behavior

- Private chats: the agent replies to every message (or only prefixed ones if
  `BOT_PREFIX` is set)
- Group chats: ignored by default
- The bot shows a "thinking" placeholder while the agent works, then sends the answer
- Because it is the same agent from the platform, WhatsApp users can ask things
  like "what's the status of invoice 1024?" or "how much did we sell this month?"
  (be careful who has access — see security notes below)

## Security notes

- Anyone who can message the linked number can query the agent. Consider:
  - setting `BOT_PREFIX` and sharing it only with staff
  - using a dedicated WhatsApp number for the bot
  - giving the `AGENT_API_KEY` a **user** (non-admin) role
- The QR page has no authentication — restrict port 3001 to localhost or your
  internal network.

## Local development (without Docker)

```bash
cd whatsapp
npm install
# needs Chrome/Chromium installed on the machine
AGENT_URL=http://localhost:8000 AGENT_API_KEY=dev-admin-key npm start
```
