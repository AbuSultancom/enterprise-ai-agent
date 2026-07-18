#!/usr/bin/env python3
"""
Enterprise AI Agent — One-Command Launcher
==========================================
    python start.py

Does EVERYTHING in one go:
  1. Checks Python version and dependencies
  2. Runs the setup wizard (only if .env is missing)
  3. Installs Python dependencies (only if missing)
  4. Installs WhatsApp bridge dependencies (only if missing)
  5. Starts the AI agent API + dashboard  -> http://localhost:8000
  6. Starts the WhatsApp bridge           -> QR prints right here in the terminal

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
  ║            |_|  |_|  v0.5                     ║
  ╚═══════════════════════════════════════════════╝
  """, "c", "bold"))
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


def check_python() -> bool:
    if sys.version_info < (3, 11):
        fail(f"Python ≥ 3.11 مطلوب (الإصدار الحالي: {sys.version_info[0]}.{sys.version_info[1]})")
        fail(f"Python ≥ 3.11 required (current: {sys.version_info[0]}.{sys.version_info[1]})")
        return False
    return True


def check_venv() -> None:
    in_venv = (hasattr(sys, "real_prefix") or
               (hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix))
    if not in_venv:
        warn("البيئة الافتراضية غير مفعلة — يفضل استخدام venv")
        warn("Virtual environment not active")


def check_deps(auto_install: bool = True) -> bool:
    missing = []
    for pkg in ["fastapi", "uvicorn", "httpx", "pydantic"]:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    if missing:
        if auto_install:
            step("تثبيت الاعتماديات / Installing dependencies")
            info(f"المفقودة: {', '.join(missing)}")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", "-r",
                                       os.path.join(ROOT, "requirements.txt")],
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                ok("تم تثبيت الاعتماديات / Dependencies installed")
                return True
            except Exception:
                fail("فشل تثبيت الاعتماديات / Failed to install dependencies")
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
        ok("ملف .env موجود — تجاوز المعالج")
        return
    step("التشغيل الأول — تشغيل معالج الإعداد")
    info("سيتم تشغيل setup.py لتكوين الوكيل")
    time.sleep(1)
    subprocess.check_call([sys.executable, os.path.join(ROOT, "setup.py")])
    if not os.path.exists(ENV_FILE):
        fail(".env لم يتم إنشاؤه — إلغاء")
        sys.exit(1)
    ok("تم إعداد الوكيل بنجاح")


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


def ensure_node_deps(npm: str) -> None:
    wa = os.path.join(ROOT, "whatsapp")
    if not node_deps_stale(wa):
        ok("اعتماديات واتساب جاهزة")
        return
    step("تثبيت اعتماديات واتساب...")
    subprocess.check_call(f'"{npm}" install', cwd=wa, shell=True)
    ok("تم تثبيت اعتماديات واتساب")


def check_node() -> str | None:
    node = node_cmd()
    if node:
        ok(f"Node.js: {node}")
    else:
        warn("Node.js غير مثبت — واتساب لن يعمل. ثبته من https://nodejs.org")
    return node


def main() -> None:
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
    whatsapp_on = env.get("WHATSAPP_ENABLED", "true") == "true" and node is not None
    if whatsapp_on and npm:
        ensure_node_deps(npm)

    # ── Prepare env ──
    env.setdefault("MEMORY_DB_PATH", os.path.join(ROOT, "data", "knowledge.json"))
    env.setdefault("AUDIT_LOG_PATH", os.path.join(ROOT, "data", "audit.jsonl"))
    env.setdefault("SETTINGS_PATH", os.path.join(ROOT, "config", "settings.json"))
    env.setdefault("API_KEYS",
                   f"admin:{env.get('ADMIN_KEY', 'dev-admin-key')},user:{env.get('USER_KEY', 'dev-user-key')}")
    os.makedirs(os.path.join(ROOT, "data"), exist_ok=True)

    children: list[subprocess.Popen] = []

    def shutdown(*_):
        print(c("\n\n  ═══ جارٍ إيقاف الخدمات... ═══", "y"))
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
    step("تشغيل الوكيل / Starting AI Agent")
    print(c(f"  Dashboard:  http://localhost:8000", "c", "bold"))
    agent = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000",
         "--log-level", "warning"],
        cwd=ROOT, env=env)
    children.append(agent)
    time.sleep(2)

    # ── Start WhatsApp ──
    if whatsapp_on and npm:
        step("تشغيل واتساب / Starting WhatsApp Bridge")
        node = node_cmd() or "node"
        wa_env = dict(env)
        wa_env.setdefault("AGENT_URL", "http://localhost:8000")
        wa_env.setdefault("WHATSAPP_PORT", "3001")
        print(c(f"  WhatsApp QR: http://localhost:3001", "c"))
        wa = subprocess.Popen([node, "index.js"], cwd=os.path.join(ROOT, "whatsapp"), env=wa_env)
        children.append(wa)

    # ── Start Telegram ──
    telegram_on = (env.get("TELEGRAM_ENABLED", "false") == "true"
                   and bool(env.get("TELEGRAM_BOT_TOKEN")))
    if telegram_on:
        step("تشغيل تلغرام / Starting Telegram Bridge")
        tg_env = dict(env)
        tg_env.setdefault("AGENT_URL", "http://localhost:8000")
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
    print(f"    {c('🌐 Dashboard:', 'bold')}   {c('http://localhost:8000', 'c')}")
    if whatsapp_on and npm:
        print(f"    {c('📱 WhatsApp QR:', 'bold')} {c('http://localhost:3001', 'c')}")
    if telegram_on:
        print(f"    {c('💬 Telegram:', 'bold')}   Bot connected — message it")
    print(c(f"\n    Press Ctrl+C to stop everything\n", "dim"))

    try:
        webbrowser.open("http://localhost:8000")
    except Exception:
        pass

    # keep alive
    while True:
        for p in children:
            code = p.poll()
            if code is not None:
                print(c(f"\n  ✖ خدمة توقفت (رمز {code}). جاري الإيقاف.", "r"))
                shutdown()
        time.sleep(1)


if __name__ == "__main__":
    main()
