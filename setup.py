#!/usr/bin/env python3
"""
Enterprise AI Agent — Interactive Setup Wizard
==============================================
Run this after downloading the project:

    python setup.py

A friendly terminal UI that asks about every setting — AI model, WhatsApp,
accounting (Onyx Pro), permissions — tests connections live, then generates
.env, config/settings.json, and (optionally) starts the Docker stack.
Pure standard library — no dependencies needed.
"""
from __future__ import annotations

import json
import os
import re as _re
import secrets
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request

ENV_FILE = ".env"
SETTINGS_FILE = os.path.join("config", "settings.json")

# ------------------------------------------------------------------ palette
C = {
    "reset": "\033[0m", "bold": "\033[1m", "dim": "\033[2m",
    "green": "\033[92m", "yellow": "\033[93m", "blue": "\033[94m",
    "cyan": "\033[96m", "red": "\033[91m", "magenta": "\033[95m",
}
ANSI = _re.compile(r"\033\[[0-9;]*m")


def c(text: str, *colors: str) -> str:
    if not colors:
        return text
    return "".join(C.get(x, "") for x in colors) + text + C["reset"]


def clear() -> None:
    os.system("cls" if os.name == "nt" else "clear")


BANNER = r"""
  _____       _                       _    ___
 | ____|_ __ | |_ ___ _ __ _ __  ___ / \  |_ _|
 |  _| | '_ \| __/ _ \ '__| '_ \/ __/ _ \  | |
 | |___| | | | ||  __/ |  | |_) \__ \ ___ \ | |
 |_____|_| |_|\__\___|_|  | .__/|___/_/   \_\___|
  Enterprise AI Agent     |_|     Setup Wizard
"""


def banner() -> None:
    clear()
    print(c(BANNER, "cyan"))
    print(c("  Interactive Setup Wizard", "bold"), c(" v0.4", "dim"))
    print(c("  Press Enter to accept any [default] · Ctrl+C to abort", "dim"))


def section(num: int, total: int, title: str, subtitle: str = "") -> None:
    print()
    print(c("  +" + "-" * 56 + "+", "blue"))
    print(c("  | ", "blue") + c(f" {num}/{total}  {title}".ljust(55), "bold") + c("|", "blue"))
    if subtitle:
        print(c("  | ", "blue") + c(f" {subtitle}".ljust(55), "dim") + c("|", "blue"))
    print(c("  +" + "-" * 56 + "+", "blue"))


def ask(prompt: str, default: str = "", secret: bool = False) -> str:
    suffix = c(f" [{default}]", "dim") if default else ""
    value = input(f"  {c('?', 'yellow', 'bold')} {prompt}{suffix}: ").strip()
    return value or default


def ask_yes(prompt: str, default: bool = True) -> bool:
    hint = c("[Y/n]", "dim") if default else c("[y/N]", "dim")
    value = input(f"  {c('?', 'yellow', 'bold')} {prompt} {hint}: ").strip().lower()
    if not value:
        return default
    return value in ("y", "yes", "1", "true")


def ask_choice(prompt: str, choices: list[str], default: int = 0) -> int:
    print(f"  {c('?', 'yellow', 'bold')} {prompt}")
    for i, choice in enumerate(choices, 1):
        if i - 1 == default:
            print(f"    {c('●', 'green')} {c(str(i) + ')', 'green', 'bold')} {choice}")
        else:
            print(f"    {c('○', 'dim')} {str(i)}) {c(choice, 'dim')}")
    while True:
        value = input(f"    {c('>', 'cyan')} Choose [default {default + 1}]: ").strip()
        if not value:
            return default
        if value.isdigit() and 1 <= int(value) <= len(choices):
            return int(value) - 1
        print(c("    x Invalid choice, try again.", "red"))


def ok(msg: str) -> None:
    print(f"  {c('[OK]', 'green', 'bold')} {c(msg, 'green')}")


def warn(msg: str) -> None:
    print(f"  {c('[!]', 'yellow', 'bold')} {c(msg, 'yellow')}")


def fail(msg: str) -> None:
    print(f"  {c('[X]', 'red', 'bold')} {c(msg, 'red')}")


# ------------------------------------------------------------- spinner/test
class Spinner:
    def __init__(self, text: str):
        self.text = text
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self):
        frames = "|/-\\"
        i = 0
        while not self._stop.is_set():
            sys.stdout.write(f"\r  {c(frames[i % len(frames)], 'cyan')} {self.text}...")
            sys.stdout.flush()
            i += 1
            time.sleep(0.1)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *args):
        self._stop.set()
        self._thread.join()
        sys.stdout.write("\r" + " " * (len(self.text) + 10) + "\r")
        sys.stdout.flush()


def test_http(url: str, headers: dict | None = None, timeout: int = 8) -> tuple[bool, str]:
    try:
        req = urllib.request.Request(url, headers=headers or {})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return True, f"HTTP {r.status}"
    except Exception as e:
        return False, str(e)[:60]


def test_tcp(host: str, port: int, timeout: int = 5) -> tuple[bool, str]:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, "reachable"
    except Exception as e:
        return False, str(e)[:60]


# ---------------------------------------------------------------- sections
def setup_llm(env: dict, settings: dict) -> None:
    section(1, 5, "AI Model (LLM)", "The agent's brain - local or cloud")
    choice = ask_choice("Which provider do you want to use?", [
        "Ollama - local, private, free (recommended)",
        "DeepSeek - cloud API, cheap & strong",
        "OpenAI - cloud API (GPT-4o etc.)",
        "Other OpenAI-compatible endpoint (Qwen / vLLM / LM Studio...)",
    ])
    if choice == 0:
        env["DEFAULT_MODEL"] = "ollama:" + ask("Ollama model name", "qwen2.5:7b")
        env["OLLAMA_BASE_URL"] = ask("Ollama URL", "http://localhost:11434")
        with Spinner("Checking Ollama"):
            good, info = test_http(env["OLLAMA_BASE_URL"].rstrip("/") + "/api/tags")
        if good:
            ok(f"Ollama is reachable ({info})")
        else:
            warn(f"Ollama not reachable at {env['OLLAMA_BASE_URL']} ({info}) - start it before chatting")
    else:
        presets = {
            1: ("https://api.deepseek.com/v1", "deepseek-chat"),
            2: ("https://api.openai.com/v1", "gpt-4o-mini"),
            3: ("", ""),
        }
        base, model = presets[choice]
        env["OPENAI_BASE_URL"] = ask("API base URL", base)
        env["OPENAI_API_KEY"] = ask("API key", secret=True)
        env["DEFAULT_MODEL"] = "openai:" + ask("Model name", model)
        if env["OPENAI_API_KEY"]:
            with Spinner("Testing API key"):
                good, info = test_http(
                    env["OPENAI_BASE_URL"].rstrip("/") + "/models",
                    {"Authorization": f"Bearer {env['OPENAI_API_KEY']}"})
            if good:
                ok(f"API key works ({info})")
            else:
                warn(f"Could not verify the key ({info}) - saved anyway")
        else:
            warn("No API key entered - cloud calls will fail until you set OPENAI_API_KEY in .env")
    settings["llm"] = {"default_model": env["DEFAULT_MODEL"]}
    ok(f"Model: {env['DEFAULT_MODEL']}")


def setup_security(env: dict, settings: dict) -> None:
    section(2, 5, "Access & Security", "API keys for dashboard / WhatsApp / integrations")
    if ask_yes("Generate secure random API keys for you?", True):
        env["ADMIN_KEY"] = secrets.token_urlsafe(24)
        env["USER_KEY"] = secrets.token_urlsafe(24)
        ok("Keys generated (shown once at the end - save them)")
    else:
        env["ADMIN_KEY"] = ask("Admin key (full access)", "dev-admin-key")
        env["USER_KEY"] = ask("User key (chat only)", "dev-user-key")
    settings["security"] = {"note": "admin = full access, user = chat + read only"}


def setup_whatsapp(env: dict, settings: dict) -> None:
    section(3, 5, "WhatsApp (QR login)", "Chat with the agent from WhatsApp")
    enabled = ask_yes("Enable the WhatsApp bridge?", True)
    settings["whatsapp"] = {"enabled": enabled}
    if not enabled:
        env["WHATSAPP_ENABLED"] = "false"
        warn("WhatsApp disabled. Re-run setup.py anytime to enable it.")
        return
    env["WHATSAPP_ENABLED"] = "true"
    print()
    warn("QR login uses the UNOFFICIAL WhatsApp Web protocol.")
    print(c("    A dedicated number for the bot is strongly recommended.", "dim"))
    prefix = ask("Reply only to messages starting with a prefix? (empty = all)", "!ai ")
    env["BOT_PREFIX"] = prefix
    env["IGNORE_GROUPS"] = "true" if ask_yes("Ignore group chats?", True) else "false"
    wa_role = ask_choice("Which API key role should WhatsApp users get?", [
        "user - chat & safe tools only (recommended for customers/staff)",
        "admin - everything including accounting queries (owner only)",
    ])
    env["WHATSAPP_ROLE"] = "user" if wa_role == 0 else "admin"
    settings["whatsapp"].update({
        "prefix": prefix,
        "ignore_groups": env["IGNORE_GROUPS"] == "true",
        "role": env["WHATSAPP_ROLE"],
    })
    ok(f"WhatsApp enabled - prefix '{prefix or '(all)'}', role: {env['WHATSAPP_ROLE']}")


def setup_accounting(env: dict, settings: dict) -> None:
    section(4, 5, "Accounting - Onyx Pro", "Read-only SQL Server connection")
    enabled = ask_yes("Connect the accounting database now?", False)
    settings["accounting"] = {"enabled": enabled}
    if not enabled:
        warn("Skipped. Set ACCOUNTING_DB_URL in .env later (see docs/ONYX_SETUP.md).")
        return
    print(c("    Use a READ-ONLY database user (see docs/ONYX_SETUP.md).", "dim"))
    host = ask("SQL Server host/IP", "192.168.1.10")
    while True:
        port_raw = ask("Port", "1433")
        if port_raw.isdigit():
            port = int(port_raw)
            break
        fail("Port must be a number.")
    db = ask("Database name", "OnyxDB")
    user = ask("DB user (read-only!)", "ai_agent_reader")
    password = ask("DB password", secret=True)
    with Spinner(f"Testing connection to {host}:{port}"):
        reachable, info = test_tcp(host, port)
    if reachable:
        ok(f"Server reachable at {host}:{port}")
    else:
        warn(f"Cannot reach {host}:{port} ({info}) - saved anyway; check network/firewall")
    env["ACCOUNTING_DB_URL"] = (
        f"mssql+pyodbc://{user}:{password}@{host}:{port}/{db}"
        "?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes"
    )
    settings["accounting"].update({
        "read_only": True,
        "allowed_queries": ["sales_summary", "revenue_by_month", "top_customers",
                            "expenses_summary", "invoice_lookup", "cash_balance"],
    })
    warn("Adapt table names in connectors/accounting.py to your Onyx schema.")
    ok("Accounting connection string saved.")


def setup_permissions(env: dict, settings: dict) -> None:
    section(5, 5, "Agent Permissions", "What the AI is allowed to read & do")
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
    perms["knowledge_rag"] = ask_yes("Use the knowledge base (company documents)?", True)
    settings["permissions"] = perms
    enabled = [k for k, v in perms.items() if v]
    ok(f"Enabled: {', '.join(enabled) or 'none'}")


# ---------------------------------------------------------------- output
def write_files(env: dict, settings: dict) -> None:
    env_lines = [
        "# Generated by setup.py - edit anytime then restart the app",
        f"ADMIN_KEY={env.get('ADMIN_KEY', 'dev-admin-key')}",
        f"USER_KEY={env.get('USER_KEY', 'dev-user-key')}",
        f"DEFAULT_MODEL={env.get('DEFAULT_MODEL', 'ollama:qwen2.5:7b')}",
        f"OLLAMA_BASE_URL={env.get('OLLAMA_BASE_URL', 'http://localhost:11434')}",
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


def box_line(text: str, width: int = 62) -> str:
    pad = width - len(ANSI.sub("", text))
    return c("  | ", "cyan") + text + " " * max(pad, 0) + c(" |", "cyan")


def print_summary(env: dict, settings: dict) -> None:
    perms = ", ".join(k for k, v in settings.get("permissions", {}).items() if v) or "none"
    print()
    print(c("  +" + "=" * 64 + "+", "cyan"))
    print(box_line(c("SETUP COMPLETE", "green", "bold")))
    print(c("  +" + "=" * 64 + "+", "cyan"))
    print(box_line(f"AI model ...... {env.get('DEFAULT_MODEL', '')[:45]}"))
    wa = "enabled" if env.get("WHATSAPP_ENABLED") == "true" else "disabled"
    print(box_line(f"WhatsApp ...... {wa} (role: {env.get('WHATSAPP_ROLE', 'user')}, prefix: '{env.get('BOT_PREFIX', '')}')"))
    acc = "connected" if env.get("ACCOUNTING_DB_URL") else "not configured"
    print(box_line(f"Accounting .... {acc}"))
    print(box_line(f"Permissions ... {perms[:46]}"))
    print(c("  +" + "-" * 64 + "+", "cyan"))
    print(box_line(c("YOUR API KEYS - SAVE THESE:", "yellow")))
    print(box_line(c(f"Admin: {env.get('ADMIN_KEY', '')}", "green")))
    print(box_line(c(f"User:  {env.get('USER_KEY', '')}", "green")))
    print(c("  +" + "-" * 64 + "+", "cyan"))
    print(box_line(c("NEXT STEPS:", "yellow")))
    print(box_line("1. Start:  uvicorn api.main:app --host 0.0.0.0 --port 8000"))
    print(box_line("2. Dashboard:  http://localhost:8000"))
    print(box_line("3. WhatsApp:   cd whatsapp && npm install && npm start"))
    print(box_line("   then scan QR at http://localhost:3001"))
    if env.get("DEFAULT_MODEL", "").startswith("ollama:"):
        model = env["DEFAULT_MODEL"].split(":", 1)[-1]
        print(box_line(f"4. First time: ollama pull {model}"))
    print(c("  +" + "=" * 64 + "+", "cyan"))
    print()


def main() -> None:
    banner()
    env: dict = {}
    settings: dict = {"version": 1}
    try:
        setup_llm(env, settings)
        setup_security(env, settings)
        setup_whatsapp(env, settings)
        setup_accounting(env, settings)
        setup_permissions(env, settings)
    except KeyboardInterrupt:
        print()
        fail("Aborted - nothing was saved.")
        sys.exit(1)
    print()
    write_files(env, settings)
    print_summary(env, settings)
    if shutil.which("docker") and ask_yes("Start the platform now with Docker?", False):
        subprocess.run(["docker", "compose", "up", "-d", "--build"], cwd="deploy")


if __name__ == "__main__":
    main()
