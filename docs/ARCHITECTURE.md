# System Architecture

The **Enterprise AI Agent** is designed as a secure, local-first platform that connects large language models to your enterprise data. It uses a **Multi-Agent Orchestrator** to route queries efficiently while maintaining strict security boundaries.

---

## 🏗️ High-Level Component Diagram

```mermaid
graph TD
    %% Clients
    User([User / Employee])
    
    subgraph Interfaces [Client Interfaces]
        Dash[Web Dashboard]
        WA[WhatsApp Bridge]
        TG[Telegram Bridge]
    end

    User -->|Browser| Dash
    User -->|App| WA
    User -->|App| TG

    %% Backend Server
    subgraph Backend [FastAPI Backend Core]
        API[API Gateway / FastAPI]
        Dash --> API
        WA --> API
        TG --> API

        Orch[Multi-Agent Orchestrator]
        API -->|Route Request| Orch
        
        AgentCore[Agent Core / ReAct Loop]
        Orch -->|Delegate Task| AgentCore
        
        LLM[LLM Gateway]
        AgentCore <-->|Inference| LLM

        Registry[Tool Registry]
        AgentCore -->|Execute| Registry
    end

    %% Storage & External
    subgraph Storage [Memory & Databases]
        Mem[(SQLite Memory)]
        RAG[(Vector RAG Store)]
        Orch <--> Mem
        AgentCore <--> RAG
    end

    subgraph External [LLM Providers]
        Ollama[Ollama (Local)]
        OpenAI[OpenAI / DeepSeek]
        LLM --> Ollama
        LLM --> OpenAI
    end

    subgraph Tools [Execution Tools]
        Registry --> Builtin[Built-in Tools\n(Search, Calc, Weather)]
        Registry --> Vision[Vision API\n(HuggingFace)]
        Registry --> DBConn[Accounting Connectors\n(PyODBC / SQLAlchemy)]
    end

    %% Enterprise Data
    ERP[(Enterprise ERP DB\nSQL Server / Oracle)]
    DBConn <-->|Read-only Queries| ERP
```

---

## 🧩 Core Components

### 1. API Gateway (`api/main.py`)
Built on **FastAPI**, this is the entry point for all requests. It provides:
- Streaming Chat endpoints (`/v1/chat/stream`)
- Dashboard API routes (`/v1/tools`, `/v1/conversations`)
- Webhook endpoints for Telegram and WhatsApp bridges

### 2. Multi-Agent Orchestrator (`orchestrator/agent.py`)
Analyzes the user's prompt and routes it to the most capable specialized agent. For example:
- A math question goes to the **Math Agent**.
- A request to check invoices goes to the **Accounting Agent**.
- A general question goes to the **General Assistant**.

### 3. Agent Core (`agent_core/agent.py`)
Implements the **ReAct (Reason + Act)** loop. The agent core is responsible for:
- Formulating thoughts based on user prompts.
- Deciding which tools to call from the Tool Registry.
- Executing tools and observing their outputs.
- Synthesizing a final response.

### 4. LLM Gateway (`llm_gateway/gateway.py`)
A unified wrapper that normalizes requests across multiple providers:
- **Local:** Ollama (`qwen2.5`, `llama3.2`)
- **Cloud:** OpenAI (`gpt-4o`, `deepseek-chat`)
It handles API retries, context window management, and fallback logic.

### 5. Memory Store (`memory/`)
- **Conversation Memory:** SQLite-based storage of past conversations, allowing users to resume chats.
- **Vector Knowledge Base:** In-memory or local vector database storing uploaded company documents (PDFs, Word docs) for **RAG (Retrieval-Augmented Generation)**.

### 6. WhatsApp Bridge (`whatsapp/index.js`)
A Node.js service using `whatsapp-web.js` that spins up a headless browser, connects to WhatsApp via QR code, and forwards incoming messages to the FastAPI backend.

---

## 🔒 Security Architecture

Enterprise security is enforced at three levels:

1. **API Keys:** The backend requires a valid `X-API-Key` (matching `ADMIN_KEY` or `USER_KEY` in `.env`) for all requests.
2. **Read-Only Database Access:** The ERP connector explicitly enforces `SELECT`-only queries and denies any mutation commands (`INSERT`, `UPDATE`, `DROP`, `DELETE`).
3. **Local Inference:** By using **Ollama**, all company data can remain entirely on-premises without being sent to external cloud APIs.
