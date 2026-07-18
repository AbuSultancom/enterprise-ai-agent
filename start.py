#!/usr/bin/env python3
"""
Enterprise AI Agent — One-Command Launcher
==========================================
    python start.py

Does EVERYTHING in one go:
  1. Runs the setup wizard (only if .env is missing)
  2. Installs Python dependencies (only if missing)
  3. Installs WhatsApp bridge dependencies (only if missing)
  4. Starts the AI agent API + dashboard  -> http://localhost:8000
  5. Starts the WhatsApp bridge           -> QR prints right here in the terminal
  6. Starts the Telegram bridge           -> if enabled in the wizard

Press Ctrl+C to stop everything.
"""
from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import time
import webbrowser

ROOT = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = os.path.join(ROOT, ".env")


def c(text: str, *colors: str) -> str:
    palette = {"g": "\033[92m", "y": "\033[93m", "b": "\033[94m",
               "c": "\033[96m", "r": "\033[91m", "bold": "\033[1m", "dim": "\033[2m"}
    if not colors:
        return text
    return "".join(palette.get(x, "") for x in colors) + text + "\033[0m"


def step(msg: str) -> None:
    print(c("\n==> ", "c", "bold") + c(msg, "bold"))


def load_env() -> dict:
    env = dict(os.environ)
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    return env


def run_setup_if_needed() -> None:
    if os.path.exists(ENV_FILE):
        print(c("  .env found — skipping wizard (delete it to reconfigure)", "dim"))
        return
    step("First run — starting the setup wizard")
    import setup
    setup.main()
    if not os.path.exists(ENV_FILE):
        print(c("Setup did not produce .env — aborting.", "r"))
        sys.exit(1)


def ensure_python_deps() -> None:
    try:
        import fastapi, uvicorn, httpx, sqlalchemy  # noqa: F401
        print(c("  Python dependencies OK", "dim"))
        return
    except ImportError:
        step("Installing Python dependencies (first time)...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r",
                               os.path.join(ROOT, "requirements.txt")])


def npm_cmd() -> str | None:
    """Full path to npm (handles npm.cmd on Windows)."""
    for name in ("npm", "npm.cmd", "npm.exe"):
        path = shutil.which(name)
        if path:
            return path
    return None


def node_cmd() -> str | None:
    return shutil.which("node") or shutil.which("node.exe")


def ensure_node_deps(npm: str) -> None:
    wa = os.path.join(ROOT, "whatsapp")
    if os.path.isdir(os.path.join(wa, "node_modules")):
        print(c("  WhatsApp dependencies OK", "dim"))
        return
    step("Installing WhatsApp bridge dependencies (first time)...")
    subprocess.check_call(f'"{npm}" install', cwd=wa, shell=True)


def main() -> None:
    os.chdir(ROOT)
    print(c(r"""
  _____       _                       _    ___
 | ____|_ __ | |_ ___ _ __ _ __  ___ / \  |_ _|
 |  _| | '_ \| __/ _ \ '__| '_ \/ __/ _ \  | |
 | |___| | | | ||  __/ |  | |_) \__ \ ___ \ | |
 |_____|_| |_|\__\___|_|  | .__/|___/_/   \_\___|
  Enterprise AI Agent     |_|     One-Command Launcher
""", "c"))

    run_setup_if_needed()
    env = load_env()

    step("Checking dependencies")
    ensure_python_deps()

    npm = npm_cmd()
    whatsapp_on = env.get("WHATSAPP_ENABLED", "true") == "true"
    if whatsapp_on and npm is None:
        print(c("  [!] Node.js not found — WhatsApp bridge disabled.", "y"))
        print(c("      Install Node.js from https://nodejs.org then re-run start.py", "dim"))
        whatsapp_on = False
    if whatsapp_on:
        ensure_node_deps(npm)

    env.setdefault("MEMORY_DB_PATH", os.path.join(ROOT, "data", "knowledge.json"))
    env.setdefault("AUDIT_LOG_PATH", os.path.join(ROOT, "data", "audit.jsonl"))
    env.setdefault("SETTINGS_PATH", os.path.join(ROOT, "config", "settings.json"))
    # build the API_KEYS map (role:key,role:key) the API expects, from wizard keys
    env.setdefault("API_KEYS",
                   f"admin:{env.get('ADMIN_KEY', 'dev-admin-key')},user:{env.get('USER_KEY', 'dev-user-key')}")
    os.makedirs(os.path.join(ROOT, "data"), exist_ok=True)

    children: list[subprocess.Popen] = []

    def shutdown(*_):
        print(c("\n\nStopping everything...", "y"))
        for p in children:
            try:
                p.terminate()
            except Exception:
                pass
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, shutdown)

    step("Starting the AI agent API  ->  http://localhost:8000")
    agent = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"],
        cwd=ROOT, env=env)
    children.append(agent)
    time.sleep(2)

    if whatsapp_on:
        step("Starting the WhatsApp bridge  ->  QR will appear below")
        node = node_cmd() or "node"
        wa_env = dict(env)
        wa_env.setdefault("AGENT_URL", "http://localhost:8000")
        wa_env.setdefault("WHATSAPP_PORT", "3001")
        wa = subprocess.Popen([node, "index.js"], cwd=os.path.join(ROOT, "whatsapp"), env=wa_env)
        children.append(wa)

    telegram_on = (env.get("TELEGRAM_ENABLED", "false") == "true"
                   and bool(env.get("TELEGRAM_BOT_TOKEN")))
    if telegram_on:
        step("Starting the Telegram bridge")
        tg_env = dict(env)
        tg_env.setdefault("AGENT_URL", "http://localhost:8000")
        tg = subprocess.Popen(
            [sys.executable, os.path.join(ROOT, "telegram", "bridge.py")],
            cwd=ROOT, env=tg_env)
        children.append(tg)

    print(c("\n" + "=" * 58, "g"))
    print(c("  ALL RUNNING", "g", "bold"))
    print(c("=" * 58, "g"))
    print(f"  Dashboard:   {c('http://localhost:8000', 'c')}")
    if whatsapp_on:
        print(f"  WhatsApp QR: {c('http://localhost:3001', 'c')}  (or scan the QR printed above)")
    if telegram_on:
        print(f"  Telegram:    {c('bot connected — message it from Telegram', 'c')}")
    print(c("\n  Press Ctrl+C to stop everything\n", "dim"))

    try:
        webbrowser.open("http://localhost:8000")
    except Exception:
        pass

    # keep alive; if a child dies, exit with its code
    while True:
        for p in children:
            code = p.poll()
            if code is not None:
                print(c(f"\nA service stopped (exit code {code}). Shutting down.", "r"))
                shutdown()
        time.sleep(1)


if __name__ == "__main__":
    main()
