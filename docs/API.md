# API Reference

The Enterprise AI Agent provides a comprehensive, RESTful **FastAPI** backend to interact with the LLM orchestrator, manage configurations, and integrate with external systems (like WhatsApp and Telegram).

All endpoints run by default on `http://localhost:8000`.

---

## 🔐 Authentication

All API requests MUST include an `X-API-Key` header.
- **Admin Key (`ADMIN_KEY`):** Has access to all endpoints, including configuration and database management.
- **User Key (`USER_KEY`):** Has access only to chat, conversations, and reports.

```http
GET /health HTTP/1.1
X-API-Key: your-secret-key-here
```

---

## 🟢 Core Endpoints

### 1. Check Health
`GET /health`
Returns the status of the server, loaded models, and the number of active tools. (Does not require API key).

### 2. Stream Chat Message
`POST /v1/chat/stream`
Sends a message to the Multi-Agent Orchestrator and streams back the response (Server-Sent Events).

**Body:**
```json
{
  "message": "What were our total sales today?",
  "conversation_id": "123e4567-e89b-12d3-a456-426614174000",
  "model": "openai:gpt-4o"
}
```
*Note: `conversation_id` is optional. If omitted, a new conversation is started. `model` is optional and overrides the default provider.*

### 3. Send Message (Non-Streaming)
`POST /v1/chat/message`
Returns the entire response as a single JSON object once processing is complete.

---

## 💬 Conversation Management

### 1. List Conversations
`GET /v1/conversations`
Returns a list of all active conversations in memory.

### 2. Get Conversation Details
`GET /v1/conversations/{conv_id}`
Returns the full chat history for a specific conversation ID.

### 3. Delete Conversation
`DELETE /v1/conversations/{conv_id}`
Removes a conversation from the SQLite memory store.

---

## 🛠️ Tool & Registry Endpoints

### 1. List Registered Tools
`GET /v1/tools`
Returns a list of all active tools that the agent can currently use, along with their schemas.

---

## 📊 Accounting & Database Endpoints

### 1. List ERP Databases
`GET /v1/accounting/databases`
Lists all registered database connections from `config/accounting_schema.json`.

### 2. Test ERP Connection
`GET /v1/accounting/health`
Attempts to ping the primary ERP database and returns its connectivity status.

### 3. Add ERP Database
`POST /v1/accounting/databases`
Registers a new ODBC/SQLAlchemy connection string dynamically without restarting the server.

---

## 📱 Bridge Webhooks

These endpoints are used internally by the Node.js bots.

### 1. WhatsApp Webhook
`POST /webhook/whatsapp`
Receives incoming messages from the `whatsapp-web.js` bridge.

### 2. Telegram Webhook
`POST /webhook/telegram`
Receives incoming messages from the Telegram bot.

---

## 📚 Interactive Documentation

Because the backend is built with FastAPI, you can view the fully interactive Swagger UI and Redoc directly in your browser:
- **Swagger UI:** `http://localhost:8000/docs`
- **Redoc:** `http://localhost:8000/redoc`
