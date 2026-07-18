#!/usr/bin/env python3
"""
Enterprise AI Agent — Onboarding Wizard (v3)
============================================
Inspired by OpenClaw's `onboard` and Hermes Agent's `setup` — one guided flow
that configures EVERYTHING:

    [1/7] Model provider  (with live test)
    [2/7] Agent identity  (name, language, personality)
    [3/7] Security        (API keys)
    [4/7] Channels        (WhatsApp + Telegram + allowed contacts)
    [5/7] Accounting      (Onyx Pro, with live server test)
    [6/7] Tools & permissions
    [7/7] Finish          (save + optional WhatsApp QR linking + self-test)

Run:  python setup.py        (pure standard library)
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

ROOT = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = os.path.join(ROOT, ".env")
SETTINGS_FILE = os.path.join(ROOT, "config", "settings.json")
TOTAL_STEPS = 7

# ------------------------------------------------------------------ palette
C = {"reset": "\033[0m", "bold": "\033[1m", "dim": "\033[2m",
     "green": "\033[92m", "yellow": "\033[93m", "blue": "\033[94m",
     "cyan": "\033[96m", "red": "\033[91m"}
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
  Enterprise AI Agent     |_|      Onboarding
"""


def progress_bar(done: int) -> str:
    filled = int(20 * done / TOTAL_STEPS)
    return c("█" * filled, "green") + c("░" * (20 - filled), "dim")


def section(num: int, title: str, subtitle: str = "") -> None:
    print()
    print(f"  {progress_bar(num - 1)}  {c(f'Step {num}/{TOTAL_STEPS}', 'dim')}")
    print(c("  ┌" + "─" * 58 + "┐", "blue"))
    print(c("  │ ", "blue") + c(f" {title}".ljust(57), "bold") + c("│", "blue"))
    if subtitle:
        print(c("  │ ", "blue") + c(f" {subtitle}".ljust(57), "dim") + c("│", "blue"))
    print(c("  └" + "─" * 58 + "┘", "blue"))


def welcome() -> None:
    clear()
    print(c(BANNER, "cyan"))
    print(c("  Welcome! This wizard configures your AI agent in ~3 minutes:", "bold"))
    print(c("""
    ◆ Model provider — Ollama locally or a cloud API (with live test)
    ◆ Agent identity — name, answer language, personality
    ◆ Security — API keys for dashboard & channels
    ◆ Channels — WhatsApp (QR) + Telegram (bot token) + allowed contacts
    ◆ Accounting — Onyx Pro read-only connection
    ◆ Tools — what the agent is allowed to read & do
    ◆ Finish — link WhatsApp with a QR scan, right here
""", "dim"))
    print(c("  Press Enter to accept any [default] · Ctrl+C to abort anytime", "yellow"))
    input(f"\n  {c('▶', 'green', 'bold')} Press Enter to begin... ")


def ask(prompt: str, default: str = "") -> str:
    suffix = c(f" [{default}]", "dim") if default else ""
    value = input(f"  {c('?', 'yellow', 'bold')} {prompt}{suffix}: ").strip()
    return value or default


def ask_yes(prompt: str, default: bool = True) -> bool:
    hint = c("[Y/n]", "dim") if default else c("[y/N]", "dim")
    value = input(f"  {c('?', 'yellow', 'bold')} {prompt} {hint}: ").strip().lower()
    if not value:
        return default
    return value in ("y", "yes", "1", "true", "نعم")


def ask_choice(prompt: str, choices: list[str], default: int = 0) -> int:
    print(f"  {c('?', 'yellow', 'bold')} {prompt}")
    for i, choice in enumerate(choices, 1):
        if i - 1 == default:
            print(f"    {c('●', 'green')} {c(str(i) + ')', 'green', 'bold')} {choice}")
        else:
            print(f"    {c('○', 'dim')} {str(i)}) {c(choice, 'dim')}")
    while True:
        value = input(f"    {c('›', 'cyan')} Choose [default {default + 1}]: ").strip()
        if not value:
            return default
        if value.isdigit() and 1 <= int(value) <= len(choices):
            return int(value) - 1
        print(c("    ✗ Invalid choice, try again.", "red"))


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
        sys.stdout.write("\r" + " " * (len(self.text) + 12) + "\r")
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


def npm_cmd() -> str | None:
    for name in ("npm", "npm.cmd", "npm.exe"):
        path = shutil.which(name)
        if path:
            return path
    return None


def node_cmd() -> str | None:
    return shutil.which("node") or shutil.which("node.exe")


# ---------------------------------------------------------------- sections
def step_model(env: dict, settings: dict) -> None:
    section(1, "Model Provider", "The agent's brain — local or cloud")
    choice = ask_choice("Which provider do you want to use?", [
        "Ollama — local, private, free (recommended)",
        "DeepSeek — cloud API, cheap & strong",
        "OpenAI — cloud API (GPT-4o etc.)",
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
            warn(f"Ollama not reachable at {env['OLLAMA_BASE_URL']} ({info})")
    else:
        presets = {
            1: ("https://api.deepseek.com/v1", "deepseek-chat"),
            2: ("https://api.openai.com/v1", "gpt-4o-mini"),
            3: ("", ""),
        }
        base, model = presets[choice]
        env["OPENAI_BASE_URL"] = ask("API base URL", base)
        env["OPENAI_API_KEY"] = ask("API key")
        env["DEFAULT_MODEL"] = "openai:" + ask("Model name", model)
        if env["OPENAI_API_KEY"]:
            with Spinner("Testing API key"):
                good, info = test_http(
                    env["OPENAI_BASE_URL"].rstrip("/") + "/models",
                    {"Authorization": f"Bearer {env['OPENAI_API_KEY']}"})
            if good:
                ok(f"API key works ({info})")
            else:
                warn(f"Could not verify the key ({info}) — saved anyway")
        else:
            warn("No API key entered — cloud calls will fail until you set OPENAI_API_KEY in .env")
    settings["llm"] = {"default_model": env["DEFAULT_MODEL"]}
    ok(f"Model: {env['DEFAULT_MODEL']}")


def step_identity(env: dict, settings: dict) -> None:
    section(2, "Agent Identity", "Name, answer language & personality")
    name = ask("Agent name (shown to users)", "Enterprise AI Agent")
    lang_idx = ask_choice("Which language should the agent answer in?", [
        "Same as the user's message (auto)",
        "Arabic — always answers in Arabic",
        "English — always answers in English",
    ])
    lang = ["auto", "ar", "en"][lang_idx]
    personality = ask("Personality / instructions (one line)",
                      "a professional, concise enterprise assistant")
    settings["agent"] = {"name": name, "language": lang, "personality": personality}
    ok(f"Identity: {name} · language: {lang}")


def step_security(env: dict, settings: dict) -> None:
    section(3, "Security", "API keys for dashboard & channels")
    if ask_yes("Generate secure random API keys for you?", True):
        env["ADMIN_KEY"] = secrets.token_urlsafe(24)
        env["USER_KEY"] = secrets.token_urlsafe(24)
        ok("Keys generated (shown once at the end — save them)")
    else:
        env["ADMIN_KEY"] = ask("Admin key (full access)", "dev-admin-key")
        env["USER_KEY"] = ask("User key (chat only)", "dev-user-key")
    settings["security"] = {"note": "admin = full access, user = chat + read only"}


def step_channels(env: dict, settings: dict) -> None:
    section(4, "Channels", "WhatsApp + Telegram + who may talk to the bot")
    settings["channels"] = {}

    # ---- WhatsApp ----
    wa_on = ask_yes("Enable the WhatsApp channel? (QR login)", True)
    env["WHATSAPP_ENABLED"] = "true" if wa_on else "false"
    if wa_on:
        warn("QR login uses the UNOFFICIAL WhatsApp Web protocol — use a dedicated number.")
        env["BOT_PREFIX"] = ask("Reply only to messages starting with a prefix? (empty = all)", "!ai ")
        env["IGNORE_GROUPS"] = "true" if ask_yes("Ignore group chats?", True) else "false"
        role = ask_choice("Which role should WhatsApp users get?", [
            "user — chat & safe tools only (recommended)",
            "admin — everything including accounting queries (owner only)",
        ])
        env["WHATSAPP_ROLE"] = "user" if role == 0 else "admin"
        print(c("    Allowed numbers (international format, comma-separated; empty = everyone)", "dim"))
        print(c("    Example: 967712345678,8613800138000", "dim"))
        nums = ask("Allowed WhatsApp numbers", "")
        env["ALLOWED_NUMBERS"] = ",".join(_re.sub(r"\D", "", n) for n in nums.split(",") if n.strip())
        ok(f"WhatsApp: prefix '{env['BOT_PREFIX'] or '(all)'}', role {env['WHATSAPP_ROLE']}, "
           f"allowed: {env['ALLOWED_NUMBERS'] or 'everyone'}")
        settings["channels"]["whatsapp"] = {"role": env["WHATSAPP_ROLE"],
                                            "allowed": env["ALLOWED_NUMBERS"]}
    else:
        settings["channels"]["whatsapp"] = {"enabled": False}

    print()
    # ---- Telegram ----
    tg_on = ask_yes("Enable the Telegram channel? (bot token)", False)
    env["TELEGRAM_ENABLED"] = "true" if tg_on else "false"
    if tg_on:
        print(c("    Create a bot with @BotFather on Telegram to get a token.", "dim"))
        env["TELEGRAM_BOT_TOKEN"] = ask("Telegram bot token", "")
        if env["TELEGRAM_BOT_TOKEN"]:
            with Spinner("Verifying bot token"):
                good, info = test_http(
                    f"https://api.telegram.org/bot{env['TELEGRAM_BOT_TOKEN']}/getMe")
            ok("Bot token verified") if good else warn(f"Could not verify token ({info}) — saved anyway")
        else:
            warn("No token entered — Telegram bridge will not start until you set TELEGRAM_BOT_TOKEN")
        tg_allowed = ask("Allowed Telegram users (IDs or @usernames, comma; empty = everyone)", "")
        env["TELEGRAM_ALLOWED"] = ",".join(x.strip() for x in tg_allowed.split(",") if x.strip())
        settings["channels"]["telegram"] = {"enabled": True, "allowed": env["TELEGRAM_ALLOWED"]}
        ok(f"Telegram: token {'set' if env.get('TELEGRAM_BOT_TOKEN') else 'MISSING'}, "
           f"allowed: {env['TELEGRAM_ALLOWED'] or 'everyone'}")
    else:
        settings["channels"]["telegram"] = {"enabled": False}


def step_accounting(env: dict, settings: dict) -> None:
    section(5, "Accounting — Onyx Pro", "Read-only SQL Server connection")
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
    password = ask("DB password")
    with Spinner(f"Testing connection to {host}:{port}"):
        reachable, info = test_tcp(host, port)
    if reachable:
        ok(f"Server reachable at {host}:{port}")
    else:
        warn(f"Cannot reach {host}:{port} ({info}) — saved anyway; check network/firewall")
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


def step_permissions(env: dict, settings: dict) -> None:
    section(6, "Tools & Permissions", "What the AI is allowed to read & do")
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


def step_finish(env: dict, settings: dict) -> None:
    section(7, "Finish", "Save, link WhatsApp, launch")
    write_files(env, settings)
    print_summary(env, settings)
    if env.get("WHATSAPP_ENABLED") == "true":
        link_whatsapp_now(env)
    else:
        warn("WhatsApp disabled — skipping linking.")


def link_whatsapp_now(env: dict) -> None:
    if not ask_yes("Link your WhatsApp number NOW? (QR will appear here)", True):
        warn("Skipped. The QR will appear on the first 'python start.py' run instead.")
        return
    node = node_cmd()
    npm = npm_cmd()
    if not node or not npm:
        fail("Node.js is not installed — cannot link WhatsApp here.")
        print(c("    Install it from https://nodejs.org then run: python start.py", "dim"))
        return
    wa_dir = os.path.join(ROOT, "whatsapp")
    nm = os.path.join(wa_dir, "node_modules")
    pkg = os.path.join(wa_dir, "package.json")
    stale = (not os.path.isdir(nm)) or (
        os.path.exists(pkg) and os.path.getmtime(pkg) > os.path.getmtime(nm))
    if stale:
        with Spinner("Installing WhatsApp bridge dependencies (~1-3 min)"):
            r = subprocess.run(f'"{npm}" install', cwd=wa_dir, shell=True,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if r.returncode != 0:
            fail("npm install failed. Run 'cd whatsapp && npm install' manually.")
            return
        ok("Dependencies installed")
    print()
    print(c("  Starting the bridge... the QR code will appear below.", "cyan"))
    print(c("  On your phone: WhatsApp → Linked devices → Link a device", "dim"))
    print(c("  Waiting up to 3 minutes for you to scan.\n", "dim"))
    wa_env = dict(os.environ)
    wa_env.update({
        "AGENT_URL": "http://localhost:8000",
        "WHATSAPP_PORT": "3001",
        "ADMIN_KEY": env.get("ADMIN_KEY", "dev-admin-key"),
        "USER_KEY": env.get("USER_KEY", "dev-user-key"),
        "WHATSAPP_ROLE": env.get("WHATSAPP_ROLE", "user"),
        "BOT_PREFIX": env.get("BOT_PREFIX", ""),
        "IGNORE_GROUPS": env.get("IGNORE_GROUPS", "true"),
        "ALLOWED_NUMBERS": env.get("ALLOWED_NUMBERS", ""),
        "WHATSAPP_ENABLED": "true",
    })
    proc = subprocess.Popen([node, "index.js"], cwd=wa_dir, env=wa_env)
    try:
        deadline = time.time() + 180
        linked = False
        while time.time() < deadline:
            try:
                with urllib.request.urlopen("http://localhost:3001/status", timeout=3) as r:
                    if json.loads(r.read()).get("status") == "ready":
                        linked = True
                        break
            except Exception:
                pass
            if proc.poll() is not None:
                break
            time.sleep(3)
        print()
        if linked:
            ok("WhatsApp LINKED successfully! Session saved — no QR needed next time.")
        else:
            warn("Not linked yet (timeout or bridge stopped).")
            print(c("    No problem: run 'python start.py' and the QR will show again.", "dim"))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()


# ---------------------------------------------------------------- output
def write_files(env: dict, settings: dict) -> None:
    env_lines = [
        "# Generated by setup.py — edit anytime then restart the app",
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
        f"ALLOWED_NUMBERS={env.get('ALLOWED_NUMBERS', '')}",
        f"TELEGRAM_ENABLED={env.get('TELEGRAM_ENABLED', 'false')}",
        f"TELEGRAM_BOT_TOKEN={env.get('TELEGRAM_BOT_TOKEN', '')}",
        f"TELEGRAM_ALLOWED={env.get('TELEGRAM_ALLOWED', '')}",
    ]
    with open(ENV_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(env_lines) + "\n")
    os.makedirs(os.path.join(ROOT, "config"), exist_ok=True)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)
    ok("Wrote .env")
    ok("Wrote config/settings.json")


def box_line(text: str, width: int = 64) -> str:
    pad = width - len(ANSI.sub("", text))
    return c("  ║ ", "cyan") + text + " " * max(pad, 0) + c(" ║", "cyan")


def print_summary(env: dict, settings: dict) -> None:
    perms = ", ".join(k for k, v in settings.get("permissions", {}).items() if v) or "none"
    agent = settings.get("agent", {})
    print()
    print(c("  ╔" + "═" * 66 + "╗", "cyan"))
    print(box_line(c("SETUP COMPLETE ✔", "green", "bold")))
    print(c("  ╠" + "═" * 66 + "╣", "cyan"))
    print(box_line(f"Model ......... {env.get('DEFAULT_MODEL', '')[:47]}"))
    print(box_line(f"Agent ......... {agent.get('name', '')} (lang: {agent.get('language', 'auto')})"))
    wa = "ON" if env.get("WHATSAPP_ENABLED") == "true" else "off"
    tg = "ON" if env.get("TELEGRAM_ENABLED") == "true" else "off"
    print(box_line(f"Channels ...... WhatsApp: {wa} · Telegram: {tg}"))
    nums = env.get("ALLOWED_NUMBERS", "") or "everyone"
    print(box_line(f"Allowed nums .. {nums[:48]}"))
    acc = "connected" if env.get("ACCOUNTING_DB_URL") else "not configured"
    print(box_line(f"Accounting .... {acc}"))
    print(box_line(f"Permissions ... {perms[:48]}"))
    print(c("  ╠" + "═" * 66 + "╣", "cyan"))
    print(box_line(c("YOUR API KEYS — SAVE THESE:", "yellow")))
    print(box_line(c(f"Admin: {env.get('ADMIN_KEY', '')}", "green")))
    print(box_line(c(f"User:  {env.get('USER_KEY', '')}", "green")))
    print(c("  ╠" + "═" * 66 + "╣", "cyan"))
    print(box_line(c("START EVERYTHING WITH ONE COMMAND:", "yellow")))
    print(box_line(c("   python start.py", "green", "bold")))
    print(box_line("Dashboard:  http://localhost:8000"))
    if env.get("DEFAULT_MODEL", "").startswith("ollama:"):
        model = env["DEFAULT_MODEL"].split(":", 1)[-1]
        print(box_line(f"(first time: ollama pull {model})"))
    print(c("  ╚" + "═" * 66 + "╝", "cyan"))
    print()


def main() -> None:
    env: dict = {}
    settings: dict = {"version": 3}
    try:
        welcome()
        step_model(env, settings)
        step_identity(env, settings)
        step_security(env, settings)
        step_channels(env, settings)
        step_accounting(env, settings)
        step_permissions(env, settings)
        step_finish(env, settings)
    except KeyboardInterrupt:
        print()
        fail("Aborted — nothing was saved.")
        sys.exit(1)


if __name__ == "__main__":
    main()
