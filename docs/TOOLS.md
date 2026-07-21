# Tool Registry

The Enterprise AI Agent features a dynamic **Tool Registry** that currently supports up to **49 specialized tools** across multiple domains. When the agent receives a prompt, the orchestrator evaluates the prompt against the registered tools and automatically selects the correct tool to gather information.

---

## 🛠️ Built-in General Tools (`tools/builtin.py`)

| Tool Name | Description | Example Usage |
|-----------|-------------|---------------|
| `get_current_time` | Returns the current date, time, and timezone. | "What time is it right now?" |
| `calculator` | Evaluates safe mathematical expressions. | "Calculate 25% of 1500." |
| `get_weather` | Fetches real-time weather data for any city. | "What's the weather in Dubai?" |
| `get_currency_rate` | Gets current exchange rates between two currencies. | "Convert 100 USD to EUR." |
| `web_search` | Performs a live web search using DuckDuckGo. | "Who won the World Cup in 2022?" |
| `read_file` | Reads system files (with admin permissions). | "Read the config.json file." |
| `read_image` | Uses a Vision API to extract text from images. | "What does this invoice say?" |
| `search_conversations`| Searches past chat history. | "What did we discuss about servers yesterday?" |
| `generate_report` | Compiles data into a structured report and saves it. | "Generate a weekly summary report." |
| `list_reports` | Lists all previously generated reports. | "Show me all reports from this month." |
| `read_report` | Reads the content of a specific report file. | "Read report-123.md." |

---

## 🏦 Accounting & ERP Tools (`tools/accounting.py`)

These tools connect directly to your enterprise database (like Onyx Pro, SQL Server, MySQL, etc.) to perform read-only data extraction.

| Tool Name | Description | Example Usage |
|-----------|-------------|---------------|
| `diagnose_connection` | Tests connection to the ERP database. | "Check if the database is online." |
| `list_databases` | Lists all configured ERP connections. | "What databases are connected?" |
| `add_database` | Adds a new database connection dynamically. | "Connect a new HR database." |
| `show_schema_config`| Shows the active table mappings configuration. | "Show me the database schema setup." |
| `discover_schema_tool`| Attempts to auto-discover tables and columns. | "Scan the database for new tables." |
| `get_sales_summary` | Calculates total sales for a given date range. | "What were the total sales today?" |
| `get_invoice` | Retrieves specific invoice details by number. | "Find invoice #INV-4029." |
| `get_vendor_balances` | Compiles a list of vendors and outstanding balances. | "Who do we owe money to?" |
| `get_sales_by_item` | Breaks down sales performance by item code. | "How many units of ITEM-A did we sell?" |

---

## 👥 Directory & HR Tools (`tools/directory.py`)

| Tool Name | Description | Example Usage |
|-----------|-------------|---------------|
| `search_employee` | Finds employee contact info by name. | "What is John's phone number?" |
| `get_department_info` | Lists all employees in a specific department. | "Who works in IT?" |
| `get_employee_role` | Retrieves job title and responsibilities. | "What does Sarah do?" |

---

## ⚙️ Settings & Admin Tools (`tools/settings.py`)

| Tool Name | Description | Example Usage |
|-----------|-------------|---------------|
| `update_api_keys` | Updates API keys for external services. | "Update my OpenAI API key." |
| `switch_model` | Changes the default LLM provider. | "Switch to the local Ollama model." |
| `get_system_status` | Checks uptime and service health. | "Is the WhatsApp bridge running?" |

---

### How Tools Work

The system uses **OpenAI Function Calling / Tool Calling** standard. The `Registry` class automatically introspects Python function signatures, docstrings, and type hints to generate a JSON Schema. This schema is passed to the LLM, which replies with the precise JSON arguments to execute the function.
