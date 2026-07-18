# Enterprise AI Agent Platform 🧠🚀

وكيل ذكاء اصطناعي مؤسسي — استضافة ذاتية، يدعم العربية والإنجليزية.

A self-hosted, open-source AI agent platform for companies — inspired by OpenClaw. Deploy it on your own infrastructure, connect local or cloud LLMs, plug in tools, and let employees chat with an agent that knows your company's documents.

---

## 📥 Installation Guide — دليل التثبيت الكامل

### 📋 المتطلبات الأساسية (Prerequisites)

| المتطلب | الإصدار | ملاحظة |
|---------|---------|--------|
| **Python** | ≥ 3.11 | [`python.org`](https://python.org) |
| **Node.js** | ≥ 18 | [`nodejs.org`](https://nodejs.org) — ضروري لوضع واتساب |
| **Git** | أي إصدار | [`git-scm.com`](https://git-scm.com) |
| **Ollama** | (اختياري) | [`ollama.com`](https://ollama.com) — للتشغيل المحلي |

---

### 🪜 خطوة بخطوة (Step by Step)

### 1. تحميل المشروع (Clone)

```bash
git clone https://github.com/AbuSultancom/enterprise-ai-agent.git
cd enterprise-ai-agent
```

### 2. إنشاء البيئة الافتراضية (Virtual Environment)

#### Windows:
```bash
python -m venv venv
venv\Scripts\activate
```

#### Mac / Linux:
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. تثبيت الاعتماديات (Install Dependencies)

```bash
pip install -r requirements.txt
```

### 4. تشغيل معالج الإعداد (Run Setup Wizard)

```bash
python setup.py
```

المعالج يسألك 7 أسئلة:
1. **مزود الذكاء** — اختر Ollama (محلي) أو DeepSeek/OpenAI (سحاب)
2. **هوية الوكيل** — الاسم، اللغة (عربي/إنجليزي)، الشخصية
3. **الأمان** — توليد مفاتيح API للوحة التحكم
4. **القنوات** — تفعيل واتساب وتلغرام
5. **المحاسبة** — ربط Onyx Pro (اختياري)
6. **الصلاحيات** — الأدوات المسموحة
7. **إنهاء** — حفظ الإعدادات

### 5. تشغيل المشروع (Start Everything)

```bash
python start.py
```

راح يشتغل تلقائياً:
- 🌐 **Dashboard:** http://localhost:8000
- 📱 **WhatsApp QR:** http://localhost:3001 (أو يظهر في الطرفية)
- 🤖 **API:** http://localhost:8000/v1/chat

> **إيقاف:** Ctrl+C

---

### 🐳 تشغيل عبر Docker (قريباً)

```bash
cd deploy
docker compose up -d
```

---

## ✨ المميزات (Features)

| الميزة | الحالة |
|-------|--------|
| **🤖 Multi-Agent Orchestrator** — 4 وكلاء متخصصين | ✅ |
| **💬 محادثة ذكية** (Streaming + عربي/إنجليزي) | ✅ |
| **🔍 بحث ويب** (DuckDuckGo) | ✅ |
| **🖼️ قراءة الصور** (Vision - فواتير، مستندات) | ✅ |
| **📊 Dashboard عصري** (Dark Mode, RTL) | ✅ |
| **💾 ذاكرة محادثة دائمة** (SQLite + FTS5) | ✅ |
| **🌤️ الطقس** + **💰 أسعار العملات** | ✅ |
| **📄 إنشاء تقارير** | ✅ |
| **📱 واتساب** (QR login) | ✅ |
| **💬 تلغرام** (Bot token) | ✅ |
| **🏦 محاسبة متعددة القواعد** (Onyx Pro + غيره) | ✅ |
| **📚 قاعدة معرفة** (رفع PDF/Word/نص) | ✅ |
| **🔒 أمان** (صلاحيات Admin/User، قراءة فقط) | ✅ |

---

## 🔧 الأدوات (19 Tool)

| الأداة | الوظيفة |
|-------|---------|
| `web_search` | بحث في الويب |
| `get_weather` | طقس أي مدينة |
| `get_currency_rate` | سعر صرف العملات |
| `calculator` | آلة حاسبة آمنة |
| `get_current_time` | التاريخ والوقت |
| `read_file` | قراءة ملفات |
| `read_image` | تحليل الصور بالذكاء الاصطناعي |
| `search_conversations` | بحث في المحادثات السابقة |
| `generate_report` | إنشاء تقارير |
| `list_reports` | عرض التقارير |
| `list_databases` | عرض قواعد البيانات المتصلة |
| `add_database` | إضافة قاعدة بيانات جديدة |
| `diagnose_connection` | تشخيص اتصال قاعدة البيانات |
| `discover_schema_tool` | اكتشاف هيكل الجداول |
| `show_schema_config` | عرض إعدادات الجداول |
| `get_sales_summary` | ملخص المبيعات |
| `get_invoice` | بحث عن فاتورة |
| `get_vendor_balances` | أرصدة الموردين |
| `get_sales_by_item` | مبيعات حسب الصنف |

---

## 🏗️ المشروع Architecture

```
enterprise-ai-agent/
├── api/main.py              # FastAPI server
├── agent_core/agent.py      # ReAct agent loop
├── orchestrator/agent.py    # Multi-Agent orchestrator
├── connectors/accounting.py # Accounting DB connector
├── llm_gateway/gateway.py   # LLM provider (Ollama/OpenAI)
├── tools/                   # Tool registry + built-in tools
│   ├── registry.py
│   ├── builtin.py
│   └── accounting.py
├── memory/                  # Conversation + Knowledge stores
│   ├── conversation.py
│   └── store.py
├── dashboard/index.html     # Web UI
├── telegram/bridge.py       # Telegram bot
├── whatsapp/index.js        # WhatsApp bridge
├── deploy/                  # Docker config
├── setup.py                 # Setup wizard
└── start.py                 # One-command launcher
```

---

## 📡 API

| الـ Endpoint | الطريقة | الوظيفة |
|---|---|---|
| `/health` | GET | حالة النظام |
| `/v1/chat` | POST | محادثة |
| `/v1/chat/stream` | POST | محادثة متدفقة |
| `/v1/conversations` | GET | قائمة المحادثات |
| `/v1/knowledge` | GET/POST | إدارة المعرفة |
| `/v1/knowledge/upload` | POST | رفع ملف |
| `/v1/tools` | GET | قائمة الأدوات |
| `/v1/accounting/health` | GET | حالة المحاسبة |
| `/v1/accounting/databases` | GET/POST | إدارة قواعد البيانات |
| `/v1/admin/audit` | GET | سجل التدقيق |

---

## 📝 License

MIT — © AbuSultancom
