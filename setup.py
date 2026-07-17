#!/usr/bin/env python3
"""
Enterprise AI Agent — Interactive Setup Wizard
==============================================
Run this after downloading the project:

    python setup.py

It asks you about every setting — AI model, WhatsApp, accounting (Onyx Pro),
and what the agent is allowed to read/do — then generates .env, config/settings.json,
and (optionally) starts the Docker stack.
"""
from __future__ import annotations

import json
import os
import secrets
import shutil
import subprocess
import sys

ENV_FILE = ".env"
SETTINGS_FILE = os.path.join("config", "settings.json")


# ---------------------------------------------------------------- helpers
def c(text: str, color: str = "") -> str:
    colors = {"g": "\033[92m", "y": "\033[93m", "b": "\033[94m", "r": "\033[91m", "bold": "\033[1m"}
    end = "\033[0m" if color else ""
    return f"{colors.get(color, '')}{text}{end}"


def header(title: str) -> None:
    print("\n" + c("=" * 60, "b"))
    print(c(f"  {title}", "bold"))
    print(c("=" * 60, "b"))


def ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{c('?', 'y')} {prompt}{suffix}: ").strip()
    return value or default


def ask_yes(prompt: str, default: bool = True) -> bool:
    hint = "Y/n" if default else "y/N"
    value = input(f"{c('?', 'y')} {prompt} [{hint}]: ").strip().lower()
    if not value:
        return default
    return value in ("y", "yes", "1", "true")


def ask_choice(prompt: str, choices: list[str], default: int = 0) -> int:
    print(c("?", "y"), prompt)
    for i, choice in enumerate(choices, 1):
        marker = c("●", "g") if i - 1 == default else "○"
        print(f"   {marker} {i}) {choice}")
    while True:
        value = input(f"   Choose [default {default + 1}]: ").strip()
        if not value:
            return default
        if value.isdigit() and 1 <= int(value) <= len(choices):
            return int(value) - 1
        print(c("   Invalid choice, try again.", "r"))


def ok(msg: str) -> None:
    print(c(f"  ✔ {msg}", "g"))


def warn(msg: str) -> None:
    print(c(f"  ⚠ {msg}", "y"))


# ---------------------------------------------------------------- sections
def setup_llm(env: dict, settings: dict) -> None:
    header("1/5  AI Model (LLM)")
    print("The agent needs a brain. Run models locally (private, free) or use a cloud API.")
    choice = ask_choice("Which provider do you want to use?", [
        "Ollama — local, private, free (recommended)",
        "DeepSeek — cloud API, cheap & strong",
        "OpenAI — cloud API (GPT-4o etc.)",
        "Other OpenAI-compatible endpoint (Qwen / vLLM / LM Studio...)",
    ])
    if choice == 0:
        env["DEFAULT_MODEL"] = "ollama:" + ask("Ollama model name", "qwen2.5:7b")
        env["OLLAMA_BASE_URL"] = ask("Ollama URL", "http://ollama:11434")
        ok(f"Local model: {env['DEFAULT_MODEL']}")
    else:
        presets = {
            1: ("https://api.deepseek.com/v1", "deepseek-chat"),
            2: ("https://api.openai.com/v1", "gpt-4o-mini"),
            3: ("", ""),
        }
        base, model = presets[choice]
        env["OPENAI_BASE_URL"] = ask("API base URL", base)
        env["OPENAI_API_KEY"] = ask("API key", "")
        env["DEFAULT_MODEL"] = "openai:" + ask("Model name", model)
        if not env["OPENAI_API_KEY"]:
            warn("No API key entered — cloud calls will fail until you set OPENAI_API_KEY in .env")
    settings["llm"] = {"default_model": env["DEFAULT_MODEL"]}


def setup_security(env: dict, settings: dict) -> None:
    header("2/5  Access & Security")
    print("API keys control who can talk to the agent (dashboard, WhatsApp, integrations).")
    if ask_yes("Generate secure random API keys for you?", True):
        env["ADMIN_KEY"] = secrets.token_urlsafe(24)
        env["USER_KEY"] = secrets.token_urlsafe(24)
        ok("Keys generated (save them — shown at the end)")
    else:
        env["ADMIN_KEY"] = ask("Admin key (full access)", "dev-admin-key")
        env["USER_KEY"] = ask("User key (chat only)", "dev-user-key")
    settings["security"] = {"note": "admin = full access, user = chat + read only"}


def setup_whatsapp(env: dict, settings: dict) -> None:
    header("3/5  WhatsApp (QR login)")
    enabled = ask_yes("Enable the WhatsApp bridge?", True)
    settings["whatsapp"] = {"enabled": enabled}
    if not enabled:
        env["WHATSAPP_ENABLED"] = "false"
        warn("WhatsApp service will not start. Re-run setup.py to enable it later.")
        return
    env["WHATSAPP_ENABLED"] = "true"
    print(c("\n  ⚠ WhatsApp via QR uses the UNOFFICIAL WhatsApp Web protocol.", "y"))
    print(c("    A dedicated number for the bot is strongly recommended.", "y"))
    prefix = ask("Reply only to messages starting with a prefix? (empty = reply to all)", "!ai ")
    env["BOT_PREFIX"] = prefix
    env["IGNORE_GROUPS"] = "true" if ask_yes("Ignore group chats?", True) else "false"
    wa_role = ask_choice("Which API key role should WhatsApp users get?", [
        "user — chat & safe tools only (recommended for customers/staff)",
        "admin — everything including accounting queries (owner only)",
    ])
    env["WHATSAPP_ROLE"] = "user" if wa_role == 0 else "admin"
    settings["whatsapp"].update({
        "prefix": prefix,
        "ignore_groups": env["IGNORE_GROUPS"] == "true",
        "role": env["WHATSAPP_ROLE"],
    })
    ok(f"WhatsApp enabled — prefix: '{prefix or '(all messages)'}', role: {env['WHATSAPP_ROLE']}")


def setup_accounting(env: dict, settings: dict) -> None:
    header("4/5  Accounting — Onyx Pro (SQL Server)")
    enabled = ask_yes("Connect the accounting database now?", False)
    settings["accounting"] = {"enabled": enabled}
    if not enabled:
        warn("Skipped. You can set ACCOUNTING_DB_URL in .env later (see docs/ONYX_SETUP.md).")
        return
    print("Enter your Onyx Pro SQL Server details (use a READ-ONLY db user).")
    host = ask("SQL Server host/IP", "192.168.1.10")
    port = ask("Port", "1433")
    db = ask("Database name", "OnyxDB")
    user = ask("DB user (read-only!)", "ai_agent_reader")
    password = ask("DB password", "")
    env["ACCOUNTING_DB_URL"] = (
        f"mssql+pyodbc://{user}:{password}@{host}:{port}/{db}"
        "?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes"
    )
    ro = ask_yes("Restrict agent to READ-ONLY accounting (SELECT only)?", True)
    settings["accounting"].update({
        "read_only": ro,
        "allowed_queries": ["sales_summary", "revenue_by_month", "top_customers",
                            "expenses_summary", "invoice_lookup", "cash_balance"],
    })
    warn("Remember: adapt table names in connectors/accounting.py to your Onyx schema.")
    ok("Accounting connection string saved.")


def setup_permissions(env: dict, settings: dict) -> None:
    header("5/5  Agent Permissions — what can the AI read & do?")
    print("Choose which capabilities (tools) the agent is allowed to use.\n")
    perms = {}
    perms["web_search"] = ask_yes("Allow web search?", True)
    perms["calculator"] = ask_yes("Allow calculator?", True)
    perms["get_current_time"] = ask_yes("Allow date/time?", True)
    perms["read_file"] = ask_yes("Allow reading files from the workspace?", False)
    accounting_on = settings.get("accounting", {}).get("enabled", False)
    if accounting_on:
        perms["accounting_tools"] = ask_yes("Allow the agent to query accounting data?", True)
    else:
        perms["accounting_tools"] = False
    perms["knowledge_rag"] = ask_yes("Use the knowledge base (company documents) in answers?", True)
    settings["permissions"] = perms
    enabled = [k for k, v in perms.items() if v]
    ok(f"Enabled capabilities: {', '.join(enabled) or 'none'}")


# ---------------------------------------------------------------- output
def write_files(env: dict, settings: dict) -> None:
    env_lines = [
        "# Generated by setup.py — edit anytime then restart: docker compose up -d",
        f"ADMIN_KEY={env.get('ADMIN_KEY', 'dev-admin-key')}",
        f"USER_KEY={env.get('USER_KEY', 'dev-user-key')}",
        f"DEFAULT_MODEL={env.get('DEFAULT_MODEL', 'ollama:qwen2.5:7b')}",
        f"OLLAMA_BASE_URL={env.get('OLLAMA_BASE_URL', 'http://ollama:11434')}",
        f"OPENAI_BASE_URL={env.get('OPENAI_BASE_URL', '')}",
        f"OPENAI_API_KEY={env.get('OPENAI_API_KEY', '')}",
        f"ACCOUNTING_DB_URL={env.get('ACCOUNTING_DB_URL', '')}",
        f"WHATSAPP_ENABLED={env.get('WHATSAPP_ENABLED', 'true')}",
        f"BOT_PREFIX={env.get('BOT_PREFIX', '')}",
        f"IGNORE_GROUPS={env.get('IGNORE_GROUPS', 'true')}",
        f"WHATSAPP_ROLE={env.get('WHATSAPP_ROLE', 'user')}",
    ]
    with open(ENV_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(env_lines) + "\n")
    os.makedirs("config", exist_ok=True)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)
    ok(f"Wrote {ENV_FILE}")
    ok(f"Wrote {SETTINGS_FILE}")


def print_summary(env: dict, settings: dict) -> None:
    header("SETUP COMPLETE ✔")
    print(f"""
{c('Your configuration:', 'bold')}
  AI model .......... {env.get('DEFAULT_MODEL')}
  WhatsApp .......... {'enabled' if env.get('WHATSAPP_ENABLED') == 'true' else 'disabled'} (role: {env.get('WHATSAPP_ROLE', 'user')}, prefix: '{env.get('BOT_PREFIX', '')}')
  Accounting ........ {'connected' if env.get('ACCOUNTING_DB_URL') else 'not configured'}
  Permissions ....... {', '.join(k for k, v in settings.get('permissions', {}).items() if v) or 'none'}

{c('Your API keys — SAVE THESE:', 'bold')}
  Admin key: {c(env.get('ADMIN_KEY', ''), 'g')}
  User key:  {c(env.get('USER_KEY', ''), 'g')}

{c('Next steps:', 'bold')}
  1. cd deploy && docker compose up -d --build
  2. Dashboard:  http://localhost:8000   (log in with the admin key)
  3. WhatsApp:   http://localhost:3001   (scan the QR with your phone)
  4. If using Ollama for the first time:
     docker exec -it deploy-ollama-1 ollama pull {env.get('DEFAULT_MODEL', 'ollama:qwen2.5:7b').split(':', 1)[-1]}
""")


def main() -> None:
    print(c("\n  Enterprise AI Agent — Setup Wizard", "bold"))
    print("  Press Enter to accept any [default]. Ctrl+C to abort.\n")
    env: dict = {}
    settings: dict = {"version": 1}
    try:
        setup_llm(env, settings)
        setup_security(env, settings)
        setup_whatsapp(env, settings)
        setup_accounting(env, settings)
        setup_permissions(env, settings)
    except KeyboardInterrupt:
        print(c("\n\nAborted — nothing was saved.", "r"))
        sys.exit(1)
    write_files(env, settings)
    print_summary(env, settings)
    if shutil.which("docker") and ask_yes("Start the platform now with Docker?", False):
        subprocess.run(["docker", "compose", "up", "-d", "--build"], cwd="deploy")


if __name__ == "__main__":
    main()
