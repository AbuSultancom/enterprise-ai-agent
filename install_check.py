"""
Enterprise AI Agent — Pre-flight Diagnostic Tool
Run: python install_check.py

Checks all system requirements and prints a full health report.
Exit code 0 = all good, 1 = warnings, 2 = critical errors.
"""

from __future__ import annotations

import importlib
import os
import platform
import shutil
import subprocess
import sys

# ─── Helpers ──────────────────────────────────────────────────────────────────

GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

TICK = "✓"
WARN = "⚠"
CROSS = "✗"
INFO = "→"

_errors = 0
_warnings = 0


def ok(msg: str) -> None:
    print(f"  {GREEN}{TICK}{RESET}  {msg}")


def warn(msg: str) -> None:
    global _warnings
    _warnings += 1
    print(f"  {YELLOW}{WARN}{RESET}  {msg}")


def fail(msg: str) -> None:
    global _errors
    _errors += 1
    print(f"  {RED}{CROSS}{RESET}  {msg}")


def info(msg: str) -> None:
    print(f"  {CYAN}{INFO}{RESET}  {msg}")


def header(msg: str) -> None:
    print(f"\n{BOLD}{CYAN}{msg}{RESET}")


# ─── Checks ───────────────────────────────────────────────────────────────────


def check_python() -> None:
    header("Python")
    v = sys.version_info
    if v >= (3, 11):
        ok(f"Python {v.major}.{v.minor}.{v.micro} ({platform.python_implementation()})")
    else:
        fail(f"Python 3.11+ required — found {v.major}.{v.minor}.{v.micro}")


def check_venv() -> None:
    header("Virtual Environment")
    if sys.prefix != sys.base_prefix:
        ok(f"Virtual environment active: {sys.prefix}")
    else:
        warn("Not running inside a virtual environment (recommended: activate venv first)")


def check_packages() -> None:
    header("Python Packages")
    required = [
        ("fastapi", "fastapi"),
        ("uvicorn", "uvicorn"),
        ("httpx", "httpx"),
        ("pydantic", "pydantic"),
        ("sqlalchemy", "sqlalchemy"),
        ("multipart", "python-multipart"),
        ("pypdf", "pypdf"),
        ("docx", "python-docx"),
        ("dotenv", "python-dotenv"),
    ]
    optional = [
        ("pyodbc", "pyodbc (ERP/SQL Server connector)"),
        ("pytest", "pytest (testing)"),
    ]
    for mod, label in required:
        try:
            importlib.import_module(mod)
            ok(f"{label}")
        except ImportError:
            fail(f"{label} — run: pip install {label.split()[0]}")
    for mod, label in optional:
        try:
            importlib.import_module(mod)
            ok(f"{label} (optional)")
        except ImportError:
            warn(f"{label} not installed (optional — needed for ERP connections)")


def check_nodejs() -> None:
    header("Node.js (required for WhatsApp)")
    node = shutil.which("node")
    if not node:
        warn("Node.js not found — WhatsApp integration will not work")
        info("Install from https://nodejs.org/ (v18+)")
        return
    try:
        result = subprocess.run([node, "--version"], capture_output=True, text=True, timeout=5)
        version = result.stdout.strip().lstrip("v")
        major = int(version.split(".")[0])
        if major >= 18:
            ok(f"Node.js v{version}")
        else:
            warn(f"Node.js v{version} — v18+ recommended")
    except Exception as e:
        warn(f"Could not determine Node.js version: {e}")


def check_env() -> None:
    header("Environment / .env File")
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if not os.path.exists(env_path):
        fail(".env file not found — copy .env.example to .env and fill in your keys")
        return
    ok(".env file found")

    # Load .env manually
    env_vars: dict[str, str] = {}
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env_vars[k.strip()] = v.strip()

    admin_key = env_vars.get("ADMIN_KEY", "change-me-admin-key")
    user_key = env_vars.get("USER_KEY", "change-me-user-key")

    if "change-me" in admin_key:
        fail("ADMIN_KEY is still the default — change it immediately!")
    else:
        ok("ADMIN_KEY is set")

    if "change-me" in user_key:
        fail("USER_KEY is still the default — change it immediately!")
    else:
        ok("USER_KEY is set")

    # LLM keys
    providers_configured: list[str] = []
    for env_key, provider in [
        ("OPENAI_API_KEY", "OpenAI"),
        ("ANTHROPIC_API_KEY", "Anthropic Claude"),
        ("GEMINI_API_KEY", "Google Gemini"),
        ("HF_TOKEN", "HuggingFace"),
    ]:
        if env_vars.get(env_key, ""):
            providers_configured.append(provider)
            ok(f"{env_key} configured ({provider})")

    if not providers_configured:
        info("No cloud LLM API keys configured — Ollama (local) will be used as default")


def check_ollama() -> None:
    header("Ollama (Local LLM)")
    try:
        import httpx as _httpx

        with _httpx.Client(timeout=3) as client:
            r = client.get("http://localhost:11434/api/tags")
            if r.status_code == 200:
                models = r.json().get("models", [])
                ok(f"Ollama running — {len(models)} model(s) available")
                if not models:
                    warn("No Ollama models found — run: ollama pull qwen2.5:7b")
                else:
                    for m in models[:5]:
                        info(f"  Model: {m.get('name', '?')}")
            else:
                warn(f"Ollama responded with HTTP {r.status_code}")
    except Exception:
        warn("Ollama not running (optional — needed for local LLMs)")
        info("Start with: ollama serve")


def check_config() -> None:
    header("Configuration Files")
    settings = os.path.join(os.path.dirname(__file__), "config", "settings.json")
    if os.path.exists(settings):
        ok("settings.json found")
    else:
        warn("config/settings.json not found — run: python setup.py")

    schema = os.path.join(os.path.dirname(__file__), "config", "accounting_schema.json")
    if os.path.exists(schema):
        ok("accounting_schema.json found")
    else:
        info("accounting_schema.json not found (needed only for ERP integration)")

    data_dir = os.path.join(os.path.dirname(__file__), "data")
    if os.path.exists(data_dir):
        ok("data/ directory exists")
    else:
        warn("data/ directory missing — will be created on first run")


def check_dashboard() -> None:
    header("Dashboard")
    idx = os.path.join(os.path.dirname(__file__), "dashboard", "index.html")
    if os.path.exists(idx):
        size_kb = os.path.getsize(idx) // 1024
        ok(f"dashboard/index.html ({size_kb} KB)")
    else:
        fail("dashboard/index.html not found — dashboard will not load")


# ─── Main ─────────────────────────────────────────────────────────────────────


def main() -> int:
    # Fix Windows console encoding for Unicode output
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

    banner = """
  ===================================================================
   Enterprise AI Agent -- Pre-flight Diagnostic               v0.6.0
  ===================================================================
"""
    print(CYAN + banner + RESET)

    check_python()
    check_venv()
    check_packages()
    check_nodejs()
    check_env()
    check_ollama()
    check_config()
    check_dashboard()

    print()
    print("─" * 60)
    if _errors == 0 and _warnings == 0:
        print(f"  {GREEN}{BOLD}All checks passed! ✓{RESET}")
        print(f"  Start with: {CYAN}python start.py{RESET}")
        return 0
    elif _errors == 0:
        print(f"  {YELLOW}{BOLD}{_warnings} warning(s) — review above.{RESET}")
        print(f"  Start with: {CYAN}python start.py{RESET}")
        return 1
    else:
        print(
            f"  {RED}{BOLD}{_errors} critical error(s), {_warnings} warning(s) — fix above before starting.{RESET}"
        )
        return 2


if __name__ == "__main__":
    sys.exit(main())
