#!/usr/bin/env python3
"""
Enterprise AI Agent — One-Command Launcher
==========================================
    python start.py
    python start.py --port=8080
    python start.py --no-whatsapp
    python start.py --no-telegram
    python start.py --no-browser
    python start.py --version
    python start.py --help

Does EVERYTHING in one go:
  1. Checks Python version and dependencies
  2. Runs the setup wizard (only if .env is missing)
  3. Installs and checks dependencies
  4. Starts the AI agent API + dashboard  -> http://localhost:8000
  5. Starts the WhatsApp bridge           -> QR on http://localhost:3001
  6. Starts the Telegram bridge (if configured)

Press Ctrl+C to stop everything.
"""
from __future__ import annotations

import argparse
import os
import shutil
import signal
import subprocess
import sys
import time
import webbrowser

ROOT = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = os.path.join(ROOT, ".env")
VERSION = "0.5.0"


def c(text: str, *colors: str) -> str:
    palette = {"g": "\033[92m", "y": "\033[93m", "b": "\033[94m",
               "c": "\033[96m", "r": "\033[91m", "m": "\033[95m",
               "bold": "\033[1m", "dim": "\033[2m"}
    if not colors:
        return text
    return "".join(palette.get(x, "") for x in colors) + text + "\033[0m"


def banner() -> None:
    print(c("""
  ╔═══════════════════════════════════════════════╗
  ║     ___                   _    ___            ║
  ║    | __|_ ___ __ _ _ __  (_)  / __|___ _ _   ║
  ║    | _|\\ \\ / '_ \\ '_ \\ | |  \\__ \\/ _ \\ '_|  ║
  ║    |___/_\\_\\ .__/ .__/_|_|  |___/\\___/_|     ║
  ║            |_|  |_|  v{VERSION}                     ║
  ╚═══════════════════════════════════════════════╝
  """.format(VERSION=VERSION), "c", "bold"))
    print(c("  Enterprise AI Agent Platform", "bold"))
    print(c("  " + "=" * 42, "dim"))
    print()


def step(msg: str) -> None:
    print(c("\n  ═══ ", "c") + c(msg, "bold") + c(" ═══", "c"))


def ok(msg: str) -> None:
    print(f"  {c('✔', 'g', 'bold')} {c(msg, 'g')}")


def warn(msg: str) -> None:
    print(f"  {c('⚠', 'y', 'bold')} {c(msg, 'y')}")


def fail(msg: str) -> None:
    print(f"  {c('✖', 'r', 'bold')} {c(msg, 'r')}")


def info(msg: str) -> None:
    print(f"  {c('·', 'c')} {c(msg, 'dim')}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Enterprise AI Agent — One-Command Launcher",
        epilog="Example: python start.py --port=8080 --no-whatsapp"
    )
    parser.add_argument("--port", type=int, default=8000, help="API port (default: 8000)")
    parser.add_argument("--no-whatsapp", action="store_true", help="Skip WhatsApp bridge")
    parser.add_argument("--no-telegram", action="store_true", help="Skip Telegram bridge")
    parser.add_argument("--no-browser", action="store_true", help="Don't open browser")
    parser.add_argument("--version", action="store_true", help="Show version and exit")
    parser.add_argument("--dev", action="store_true", help="Development mode (hot reload)")
    return parser.parse_args()


def check_python() -> bool:
    if sys.version_info < (3, 11):
        fail(f"Python ≥ 3.11 required (you have {sys.version_info[0]}.{sys.version_info[1]})")
        return False
    return True


def check_venv() -> None:
    in_venv = (hasattr(sys, "real_prefix") or
               (hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix))
    if not in_venv:
        warn("Virtual environment not active — recommended: python -m venv venv && source venv/bin/activate")


def check_deps(auto_install: bool = True) -> bool:
    missing = []
    for pkg in ["fastapi", "uvicorn", "httpx", "pydantic"]:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    if missing:
        if auto_install:
            step("Installing dependencies")
            info(f"Missing: {', '.join(missing)}")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", "-r",
                                       os.path.join(ROOT, "requirements.txt")],
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                ok("Dependencies installed")
                return True
            except Exception:
                fail("Failed to install dependencies")
                return False
        else:
            return False
    return True


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
        ok(".env found — skipping setup")
        return
    step("First run — starting setup wizard")
    info("setup.py will configure your agent")
    time.sleep(1)
    subprocess.check_call([sys.executable, os.path.join(ROOT, "setup.py")])
    if not os.path.exists(ENV_FILE):
        fail(".env was not created — aborting")
        sys.exit(1)
    ok("Setup complete")


def npm_cmd() -> str | None:
    for name in ("npm", "npm.cmd", "npm.exe"):
        path = shutil.which(name)
        if path:
            return path
    return None


def node_cmd() -> str | None:
    return shutil.which("node") or shutil.which("node.exe")


def node_deps_stale(wa_dir: str) -> bool:
    nm = os.path.join(wa_dir, "node_modules")
    pkg = os.path.join(wa_dir, "package.json")
    if not os.path.isdir(nm):
        return True
    try:
        return os.path.getmtime(pkg) > os.path.getmtime(nm)
    except OSError:
        return True


def ensure_node_deps(npm_path: str) -> None:
    wa = os.path.join(ROOT, "whatsapp")
    if not node_deps_stale(wa):
        ok("WhatsApp deps OK")
        return
    step("Installing WhatsApp dependencies...")
    subprocess.check_call(f'"{npm_path}" install', cwd=wa, shell=True)
    ok("WhatsApp deps installed")


def check_node() -> str | None:
    node = node_cmd()
    if node:
        ok(f"Node.js: {node}")
    else:
        warn("Node.js not found — WhatsApp will be disabled. Install from https://nodejs.org")
    return node


def wait_for_api(port: int, timeout: int = 15) -> bool:
    """Wait until the API health endpoint responds."""
    import http.client
    url = f"localhost:{port}"
    for i in range(timeout):
        try:
            conn = http.client.HTTPConnection(url, timeout=2)
            conn.request("GET", "/health")
            r = conn.getresponse()
            if r.status == 200:
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


def main() -> None:
    args = parse_args()

    if args.version:
        print(f"Enterprise AI Agent v{VERSION}")
        sys.exit(0)

    os.chdir(ROOT)

    # ── Banner ──
    banner()

    # ── Checks ──
    if not check_python():
        sys.exit(1)
    check_venv()
    if not check_deps():
        sys.exit(1)

    # ── Setup ──
    run_setup_if_needed()
    env = load_env()

    # ── Node / WhatsApp ──
    node = check_node()
    npm = npm_cmd()
    whatsapp_on = (
        not args.no_whatsapp
        and env.get("WHATSAPP_ENABLED", "true") == "true"
        and node is not None
    )
    if whatsapp_on and npm:
        ensure_node_deps(npm)

    # ── Prepare env ──
    env.setdefault("MEMORY_DB_PATH", os.path.join(ROOT, "data", "knowledge.json"))
    env.setdefault("AUDIT_LOG_PATH", os.path.join(ROOT, "data", "audit.jsonl"))
    env.setdefault("SETTINGS_PATH", os.path.join(ROOT, "config", "settings.json"))
    env.setdefault("API_KEYS",
                   f"admin:{env.get('ADMIN_KEY', 'dev-admin-key')},user:{env.get('USER_KEY', 'dev-user-key')}")
    os.makedirs(os.path.join(ROOT, "data"), exist_ok=True)

    port = args.port
    children: list[subprocess.Popen] = []

    def shutdown(*_):
        print(c("\n\n  ═══ Stopping... ═══", "y"))
        for p in children:
            try:
                p.terminate()
            except Exception:
                pass
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, shutdown)

    # ── Start API ──
    step("Starting AI Agent")
    print(c(f"  Dashboard:  http://localhost:{port}", "c", "bold"))
    uvicorn_args = ["--host", "0.0.0.0", "--port", str(port), "--log-level", "warning"]
    if args.dev:
        uvicorn_args.append("--reload")
    agent = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "api.main:app"] + uvicorn_args,
        cwd=ROOT, env=env)
    children.append(agent)

    # Wait for API to be ready
    if wait_for_api(port):
        ok(f"API ready on http://localhost:{port}")
    else:
        warn("API startup timed out — check for errors above")

    # ── Start WhatsApp ──
    if whatsapp_on and npm:
        step("Starting WhatsApp Bridge")
        node = node_cmd() or "node"
        wa_env = dict(env)
        wa_env.setdefault("AGENT_URL", f"http://localhost:{port}")
        wa_env.setdefault("WHATSAPP_PORT", "3001")
        print(c(f"  WhatsApp QR: http://localhost:3001", "c"))
        wa = subprocess.Popen([node, "index.js"], cwd=os.path.join(ROOT, "whatsapp"), env=wa_env)
        children.append(wa)

    # ── Start Telegram ──
    telegram_on = (
        not args.no_telegram
        and env.get("TELEGRAM_ENABLED", "false") == "true"
        and bool(env.get("TELEGRAM_BOT_TOKEN"))
    )
    if telegram_on:
        step("Starting Telegram Bridge")
        tg_env = dict(env)
        tg_env.setdefault("AGENT_URL", f"http://localhost:{port}")
        tg = subprocess.Popen(
            [sys.executable, os.path.join(ROOT, "telegram", "bridge.py")],
            cwd=ROOT, env=tg_env)
        children.append(tg)

    # ── Summary ──
    print(c("\n  ╔" + "═" * 50 + "╗", "g"))
    print(c("  ║" + " " * 50 + "║", "g"))
    print(c("  ║" + "      ✅  ALL RUNNING  ".center(50) + "║", "g", "bold"))
    print(c("  ║" + " " * 50 + "║", "g"))
    print(c("  ╚" + "═" * 50 + "╝", "g"))
    print(f"    {c('🌐 Dashboard:', 'bold')}   {c(f'http://localhost:{port}', 'c')}")
    if args.dev:
        print(f"    {c('⚡ Dev mode:', 'bold')}  Hot reload enabled")
    if whatsapp_on and npm:
        print(f"    {c('📱 WhatsApp QR:', 'bold')} {c('http://localhost:3001', 'c')}")
    if telegram_on:
        print(f"    {c('💬 Telegram:', 'bold')}   Bot connected")
    print(c(f"\n    Press Ctrl+C to stop everything\n", "dim"))

    if not args.no_browser:
        try:
            webbrowser.open(f"http://localhost:{port}")
        except Exception:
            pass

    # keep alive with auto-restart
    MAX_RESTARTS = 3
    restart_counts: dict[int, int] = {}
    while True:
        for i, p in enumerate(children):
            code = p.poll()
            if code is not None:
                restart_counts[i] = restart_counts.get(i, 0) + 1
                if restart_counts[i] > MAX_RESTARTS:
                    print(c(f"\n  ✖ Service {i} crashed {MAX_RESTARTS} times. Stopping.", "r"))
                    shutdown()
                print(c(f"\n  ⚠ Service {i} crashed (code {code}). Restarting...", "y"))
                new_p = subprocess.Popen(
                    p.args, cwd=ROOT, env=env)
                children[i] = new_p
        time.sleep(1)


if __name__ == "__main__":
    main()
