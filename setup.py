#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════╗
║         Enterprise AI Agent — Professional Setup Wizard v3.0        ║
║                                                                      ║
║  Usage:                                                              ║
║    python setup.py              → Interactive mode selector          ║
║    python setup.py --cli        → Force CLI wizard                   ║
║    python setup.py --web        → Force Web wizard                   ║
║    python setup.py --update     → Update existing config             ║
╚══════════════════════════════════════════════════════════════════════╝
"""
from __future__ import annotations

import argparse
import getpass
import json
import locale
import os
import re
import secrets
import shutil
import subprocess
import sys
import time
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

# ── Root directory ────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.resolve()
CONFIG_DIR = ROOT / "config"
CONFIG_DIR.mkdir(exist_ok=True)

ENV_FILE = ROOT / ".env"
SETTINGS_FILE = ROOT / "settings.json"          # legacy flat file
SETTINGS_CFG  = CONFIG_DIR / "settings.json"    # preferred location
SCHEMA_FILE   = CONFIG_DIR / "accounting_schema.json"
BACKUP_DIR    = ROOT / "backups"

# ── Bilingual strings ─────────────────────────────────────────────────────
STR: dict[str, dict[str, str]] = {
    "en": {
        "welcome_title": "Enterprise AI Agent — Setup Wizard v3.0",
        "choose_mode": "Choose setup mode:",
        "mode_cli": "Command Line (Terminal)",
        "mode_web": "Web Browser (Recommended)",
        "web_launching": "\n🚀 Launching web setup…",
        "web_open": "Open your browser at:",
        "web_url": "http://localhost:8088/setup",
        "web_stop": "\nPress Ctrl+C to stop the server",
        "step1": "[1/8]  Language",
        "step2": "[2/8]  LLM Provider",
        "step3": "[3/8]  Agent Identity",
        "step4": "[4/8]  Security & API Keys",
        "step5": "[5/8]  Communication Channels",
        "step6": "[6/8]  Database / Accounting Setup",
        "step7": "[7/8]  Permissions",
        "step8": "[8/8]  Review & Finalize",
        "done": "✅  Setup Complete!",
        "error": "❌  Error",
        "warning": "⚠️   Warning",
        "info": "ℹ️   Info",
        "skip": "Skip (press Enter)",
        "test_connection": "Testing connection …",
        "connection_ok": "✅  Connection successful",
        "connection_fail": "❌  Connection failed",
        "backup_created": "Backup created",
        "required": "Required",
        "optional": "Optional",
        "default": "default",
        "update_mode": "Update Mode — existing config loaded",
        "select": "Select",
        "enter_value": "Enter value",
    },
    "ar": {
        "welcome_title": "وكيل الذكاء الاصطناعي المؤسسي — معالج الإعداد v3.0",
        "choose_mode": "اختر وضع الإعداد:",
        "mode_cli": "سطر الأوامر (Terminal)",
        "mode_web": "متصفح الويب (موصى به)",
        "web_launching": "\n🚀 جاري تشغيل خادم الإعداد…",
        "web_open": "افتح المتصفح على:",
        "web_url": "http://localhost:8088/setup",
        "web_stop": "\nاضغط Ctrl+C لإيقاف الخادم",
        "step1": "[1/8]  اللغة",
        "step2": "[2/8]  مزوّد نموذج اللغة (LLM)",
        "step3": "[3/8]  هوية الوكيل",
        "step4": "[4/8]  الأمان ومفاتيح API",
        "step5": "[5/8]  قنوات التواصل",
        "step6": "[6/8]  إعداد قاعدة البيانات / المحاسبة",
        "step7": "[7/8]  الصلاحيات",
        "step8": "[8/8]  مراجعة وإنهاء",
        "done": "✅  اكتمل الإعداد!",
        "error": "❌  خطأ",
        "warning": "⚠️   تحذير",
        "info": "ℹ️   معلومة",
        "skip": "تخطي (اضغط Enter)",
        "test_connection": "جاري اختبار الاتصال …",
        "connection_ok": "✅  الاتصال ناجح",
        "connection_fail": "❌  فشل الاتصال",
        "backup_created": "تم إنشاء نسخة احتياطية",
        "required": "مطلوب",
        "optional": "اختياري",
        "default": "افتراضي",
        "update_mode": "وضع التحديث — تم تحميل الإعدادات الحالية",
        "select": "اختر",
        "enter_value": "أدخل القيمة",
    },
}

# Auto-detect language from system locale
try:
    _sys_locale = locale.getlocale()[0] or ""
except Exception:
    _sys_locale = ""
DEFAULT_LANG: str = "ar" if _sys_locale.startswith("ar") else "en"
L: dict[str, str] = STR[DEFAULT_LANG]


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  Terminal UI helpers                                                     ║
# ╚══════════════════════════════════════════════════════════════════════════╝

class C:
    """ANSI color codes."""
    HDR    = "\033[95m"
    BLUE   = "\033[94m"
    CYAN   = "\033[96m"
    GREEN  = "\033[92m"
    YELLOW = "\033[93m"
    RED    = "\033[91m"
    BOLD   = "\033[1m"
    DIM    = "\033[2m"
    RESET  = "\033[0m"

    @staticmethod
    def ok(s: str) -> str:    return f"{C.GREEN}{s}{C.RESET}"
    @staticmethod
    def err(s: str) -> str:   return f"{C.RED}{s}{C.RESET}"
    @staticmethod
    def warn(s: str) -> str:  return f"{C.YELLOW}{s}{C.RESET}"
    @staticmethod
    def info(s: str) -> str:  return f"{C.CYAN}{s}{C.RESET}"
    @staticmethod
    def bold(s: str) -> str:  return f"{C.BOLD}{s}{C.RESET}"
    @staticmethod
    def dim(s: str) -> str:   return f"{C.DIM}{s}{C.RESET}"


def banner(title: str) -> None:
    """Print a full-width banner."""
    w = min(shutil.get_terminal_size((80, 20)).columns, 76)
    inner = title.center(w - 4)
    top    = C.CYAN + "╔" + "═" * (w - 2) + "╗" + C.RESET
    mid    = C.CYAN + "║ " + C.RESET + C.BOLD + inner + C.RESET + C.CYAN + " ║" + C.RESET
    bottom = C.CYAN + "╚" + "═" * (w - 2) + "╝" + C.RESET
    print(f"\n{top}\n{mid}\n{bottom}\n")


def section(title: str) -> None:
    """Print a section header."""
    w = min(shutil.get_terminal_size((80, 20)).columns, 72)
    line = "─" * w
    print(f"\n{C.CYAN}{line}{C.RESET}")
    print(f"  {C.BOLD}{C.CYAN}{title}{C.RESET}")
    print(f"{C.CYAN}{line}{C.RESET}")


def progress_bar(current: int, total: int, width: int = 40) -> str:
    filled = int(width * current / total)
    bar = "█" * filled + "░" * (width - filled)
    pct = int(100 * current / total)
    return f"{C.CYAN}[{bar}]{C.RESET} {C.BOLD}{pct}%{C.RESET}  ({current}/{total})"


def ask(
    prompt: str,
    default: str | None = None,
    required: bool = False,
    password: bool = False,
    hint: str = "",
) -> str | None:
    """Prompt the user for a value, with optional default and password masking."""
    parts = [f"  {C.BOLD}{prompt}{C.RESET}"]
    if hint:
        parts.append(f" {C.DIM}({hint}){C.RESET}")
    if default is not None:
        parts.append(f" {C.DIM}[{L['default']}: {default}]{C.RESET}")
    parts.append(": ")
    display = "".join(parts)

    while True:
        if password:
            value = getpass.getpass(display)
        else:
            value = input(display).strip()
        if not value:
            if default is not None:
                return default
            if required:
                print(C.err(f"  ✗ {L['required']}"))
                continue
            return None
        return value


def ask_yes(prompt: str, default: bool = True) -> bool:
    """Ask a yes/no question."""
    suffix = f" {C.DIM}[Y/n]{C.RESET}" if default else f" {C.DIM}[y/N]{C.RESET}"
    while True:
        resp = input(f"  {C.BOLD}{prompt}{C.RESET}{suffix}: ").strip().lower()
        if not resp:
            return default
        if resp in ("y", "yes", "نعم", "1"):
            return True
        if resp in ("n", "no", "لا", "0"):
            return False
        print(C.warn("  Please answer yes (y) or no (n)"))


def choose(options: list[str], prompt: str = "", default: int = 0) -> int:
    """Display a numbered menu and return the selected index (0-based)."""
    if prompt:
        print(f"\n  {C.BOLD}{prompt}{C.RESET}")
    for i, opt in enumerate(options, 1):
        marker = C.GREEN + "  ▶" + C.RESET if (i - 1) == default else "   "
        num    = C.CYAN + f"[{i}]" + C.RESET
        print(f"{marker} {num} {opt}")
    while True:
        try:
            raw = input(f"\n  {L['select']} [1–{len(options)}]: ").strip()
            if not raw:
                return default
            idx = int(raw) - 1
            if 0 <= idx < len(options):
                return idx
        except (ValueError, EOFError):
            pass
        print(C.err(f"  Invalid choice — enter a number between 1 and {len(options)}"))


def spinner_run(text: str, func, *args, **kwargs) -> Any:
    """Run func in background while displaying a spinner."""
    result: list[Any] = [None]
    exc:    list[Exception | None] = [None]
    done:   list[bool] = [False]

    def _worker():
        try:
            result[0] = func(*args, **kwargs)
        except Exception as e:
            exc[0] = e
        finally:
            done[0] = True

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    frames = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
    i = 0
    while not done[0]:
        print(f"\r  {C.CYAN}{frames[i % len(frames)]}{C.RESET}  {text}", end="", flush=True)
        time.sleep(0.08)
        i += 1
    print(f"\r  {' ' * (len(text) + 6)}\r", end="")
    t.join()
    if exc[0] is not None:
        raise exc[0]
    return result[0]


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  Config Manager                                                          ║
# ╚══════════════════════════════════════════════════════════════════════════╝

class ConfigManager:
    """Reads and writes .env, settings.json, and accounting_schema.json."""

    def load_env(self) -> dict[str, str]:
        env: dict[str, str] = {}
        for path in (ENV_FILE,):
            if path.exists():
                for line in path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        env[k.strip()] = v.strip().strip('"').strip("'")
        return env

    def load_settings(self) -> dict:
        for path in (SETTINGS_CFG, SETTINGS_FILE):
            if path.exists():
                try:
                    return json.loads(path.read_text(encoding="utf-8"))
                except Exception:
                    pass
        return {}

    def load_schema(self) -> dict:
        if SCHEMA_FILE.exists():
            try:
                return json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    def backup(self) -> Path:
        BACKUP_DIR.mkdir(exist_ok=True)
        ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
        dst = BACKUP_DIR / f"backup_{ts}"
        dst.mkdir(exist_ok=True)
        for src in (ENV_FILE, SETTINGS_FILE, SETTINGS_CFG, SCHEMA_FILE):
            if src.exists():
                shutil.copy2(src, dst / src.name)
        return dst

    # ── Write helpers ──────────────────────────────────────────────────

    def write_env(self, env: dict[str, str]) -> None:
        lines = [
            "# Enterprise AI Agent — Environment Variables",
            f"# Generated: {datetime.now().isoformat()}",
            "# DO NOT commit this file to version control.",
            "",
        ]
        for k, v in sorted(env.items()):
            if v is not None:
                # Quote values that contain spaces or special chars
                if any(c in str(v) for c in (" ", "#", "&", ";")):
                    lines.append(f'{k}="{v}"')
                else:
                    lines.append(f"{k}={v}")
        ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def write_settings(self, settings: dict) -> None:
        """Write to both locations for compatibility."""
        payload = json.dumps(settings, indent=2, ensure_ascii=False)
        SETTINGS_FILE.write_text(payload, encoding="utf-8")
        SETTINGS_CFG.write_text(payload, encoding="utf-8")

    def write_schema(self, schema: dict) -> None:
        SCHEMA_FILE.write_text(
            json.dumps(schema, indent=2, ensure_ascii=False), encoding="utf-8"
        )


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  Database helpers                                                        ║
# ╚══════════════════════════════════════════════════════════════════════════╝

DB_DRIVERS = {
    "mssql":      "mssql+pyodbc",
    "mysql":      "mysql+pymysql",
    "postgresql": "postgresql+psycopg2",
    "sqlite":     "sqlite",
}

DB_DISPLAY_NAMES = {
    "mssql":      "Microsoft SQL Server (Onyx Pro / MSSQL)",
    "mysql":      "MySQL / MariaDB",
    "postgresql": "PostgreSQL",
    "sqlite":     "SQLite (local file)",
}

DB_DEFAULT_PORTS = {
    "mssql":      "1433",
    "mysql":      "3306",
    "postgresql": "5432",
    "sqlite":     "",
}


def build_connection_url(db_type: str, cfg: dict) -> str:
    """Build a SQLAlchemy connection URL from collected config."""
    drv = DB_DRIVERS[db_type]
    if db_type == "sqlite":
        path = cfg.get("sqlite_path", "data/accounting.db")
        return f"sqlite:///{path}"
    host = cfg.get("host", "localhost")
    port = cfg.get("port", DB_DEFAULT_PORTS[db_type])
    name = cfg.get("db_name", "")
    user = cfg.get("username", "")
    pw   = cfg.get("password", "")

    # URL-encode special chars in password
    import urllib.parse
    pw_enc = urllib.parse.quote_plus(str(pw)) if pw else ""
    user_part = f"{user}:{pw_enc}@" if user else ""

    if db_type == "mssql":
        driver = cfg.get("odbc_driver", "ODBC Driver 18 for SQL Server")
        trust  = "TrustServerCertificate=yes"
        return (
            f"{drv}://{user_part}{host}:{port}/{name}"
            f"?driver={urllib.parse.quote_plus(driver)}&{trust}"
        )
    return f"{drv}://{user_part}{host}:{port}/{name}"


def test_db_connection(url: str) -> tuple[bool, str]:
    """Test a database connection; returns (success, message)."""
    try:
        from sqlalchemy import create_engine, text  # type: ignore
        engine = create_engine(url, connect_args={"timeout": 8}, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
        return True, "Connection successful"
    except ImportError:
        return False, "SQLAlchemy not installed — run: pip install sqlalchemy"
    except Exception as exc:
        return False, str(exc)


def discover_db_schema(url: str) -> dict:
    """
    Auto-discover tables and columns from a live database.
    Returns a dict mapping logical names → SchemaConfig table entries.
    """
    try:
        from sqlalchemy import create_engine, inspect as sa_inspect  # type: ignore
        engine = create_engine(url)
        inspector = sa_inspect(engine)
        tables_raw = inspector.get_table_names()
        schema: dict[str, dict] = {}
        for tbl in tables_raw:
            try:
                cols = inspector.get_columns(tbl)
                col_map = {c["name"].lower().replace(" ", "_"): c["name"] for c in cols}
                schema[tbl.lower()] = {
                    "table": tbl,
                    "columns": col_map,
                }
            except Exception:
                continue
        engine.dispose()
        return schema
    except Exception as exc:
        return {"_error": str(exc)}


# ── Map well-known table names to logical names ──────────────────────────
_TABLE_ALIASES = {
    # Onyx Pro / Arabic ERP names
    "salesinvoices":     "sales_invoices",
    "purchaseinvoices":  "purchase_invoices",
    "journalentries":    "journal_entries",
    "customers":         "customers",
    "vendors":           "vendors",
    "accounts":          "accounts",
    "items":             "items",
    "employees":         "employees",
    "salaries":          "salaries",
    "inventory":         "inventory",
    "stocktransactions": "stock_transactions",
    # Generic
    "invoice":           "sales_invoices",
    "customer":          "customers",
    "vendor":            "vendors",
    "account":           "accounts",
    "item":              "items",
    "product":           "items",
}


def normalize_discovered(raw: dict) -> dict:
    """Map discovered table names to standard logical keys where possible."""
    normalized: dict[str, dict] = {}
    for tbl_lower, entry in raw.items():
        if tbl_lower == "_error":
            continue
        logical = _TABLE_ALIASES.get(tbl_lower, tbl_lower)
        normalized[logical] = entry
    return normalized


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  CLI Wizard                                                              ║
# ╚══════════════════════════════════════════════════════════════════════════╝

class CLIWizard:
    TOTAL_STEPS = 8

    def __init__(self, cfg: ConfigManager, update_mode: bool = False):
        self.cfg = cfg
        self.update_mode = update_mode
        # Carry over existing values so update mode keeps unmodified fields
        self.existing_env      = cfg.load_env() if update_mode else {}
        self.existing_settings = cfg.load_settings() if update_mode else {}
        self.existing_schema   = cfg.load_schema() if update_mode else {}

        self.env:      dict[str, str] = dict(self.existing_env)
        self.settings: dict[str, Any] = dict(self.existing_settings)
        self.schema:   dict[str, Any] = dict(self.existing_schema)

    # ── Step helpers ──────────────────────────────────────────────────────

    def _header(self, step: int, title: str) -> None:
        print(f"\n{progress_bar(step - 1, self.TOTAL_STEPS)}")
        section(f"  {title}")

    def _ok(self, msg: str) -> None:
        print(C.ok(f"  ✔  {msg}"))

    def _warn(self, msg: str) -> None:
        print(C.warn(f"  ⚠  {msg}"))

    def _info(self, msg: str) -> None:
        print(C.info(f"  ℹ  {msg}"))

    # ── Main runner ───────────────────────────────────────────────────────

    def run(self) -> None:
        banner(L["welcome_title"])
        if self.update_mode:
            self._info(L["update_mode"])

        self.step_language()
        self.step_llm()
        self.step_identity()
        self.step_security()
        self.step_channels()
        self.step_database()
        self.step_permissions()
        self.step_finalize()

    # ──────────────────────────────────────────────────────────────────────
    # STEP 1 — Language
    # ──────────────────────────────────────────────────────────────────────

    def step_language(self) -> None:
        global L
        self._header(1, L["step1"])
        options = ["English", "العربية (Arabic)"]
        current = self.settings.get("agent", {}).get("language", DEFAULT_LANG)
        default = 0 if current == "en" else 1
        idx = choose(options, "Interface language / لغة الواجهة", default=default)
        lang = "en" if idx == 0 else "ar"
        L = STR[lang]
        self.settings.setdefault("agent", {})["language"] = lang
        self._ok(f"Language: {options[idx]}")

    # ──────────────────────────────────────────────────────────────────────
    # STEP 2 — LLM Provider
    # ──────────────────────────────────────────────────────────────────────

    def step_llm(self) -> None:
        self._header(2, L["step2"])

        providers = [
            "Ollama  (Local — recommended, data stays on-premise)",
            "OpenAI  (GPT-4o, GPT-4o-mini …)",
            "Anthropic Claude  (Claude 3.5 Sonnet, Opus …)",
            "Google Gemini  (Gemini 1.5 Pro, Flash …)",
            "DeepSeek  (deepseek-chat, deepseek-r1 …)",
            "Custom OpenAI-compatible endpoint",
        ]
        provider_keys = ["ollama", "openai", "anthropic", "google", "deepseek", "custom"]
        current_provider = self.settings.get("llm_provider", "ollama")
        default_idx = provider_keys.index(current_provider) if current_provider in provider_keys else 0

        idx = choose(providers, "LLM Provider:", default=default_idx)
        provider = provider_keys[idx]
        self.settings["llm_provider"] = provider

        # Model selection
        model_options: dict[str, list[str]] = {
            "ollama":    ["qwen2.5:7b", "qwen2.5:14b", "llama3.1:8b", "deepseek-r1:14b", "mistral:7b", "Other"],
            "openai":    ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "o1-mini", "Other"],
            "anthropic": ["claude-3-5-sonnet-20241022", "claude-3-opus-20240229", "claude-3-haiku-20240307", "Other"],
            "google":    ["gemini-1.5-pro", "gemini-1.5-flash", "gemini-2.0-flash", "Other"],
            "deepseek":  ["deepseek-chat", "deepseek-r1", "Other"],
            "custom":    ["Other"],
        }
        models = model_options.get(provider, ["Other"])
        current_model_raw = self.existing_env.get("DEFAULT_MODEL", "")
        # Strip provider prefix for display
        current_model = current_model_raw.split(":", 1)[-1] if ":" in current_model_raw else current_model_raw
        m_default = 0
        for i, m in enumerate(models):
            if current_model and current_model in m:
                m_default = i
                break

        midx = choose(models, "Model:", default=m_default)
        model = models[midx]
        if model == "Other":
            model = ask("Enter model name", required=True) or "qwen2.5:7b"

        # Build DEFAULT_MODEL env var with provider prefix
        prefix_map = {
            "ollama": "ollama",
            "openai": "openai",
            "anthropic": "openai",  # use OpenAI-compatible format
            "google": "openai",
            "deepseek": "openai",
            "custom": "openai",
        }
        env_prefix = prefix_map[provider]
        self.env["DEFAULT_MODEL"] = f"{env_prefix}:{model}"

        # Base URL
        default_urls = {
            "ollama":    "http://localhost:11434",
            "openai":    "https://api.openai.com/v1",
            "anthropic": "https://api.anthropic.com/v1",
            "google":    "https://generativelanguage.googleapis.com/v1beta",
            "deepseek":  "https://api.deepseek.com/v1",
            "custom":    "http://localhost:11434",
        }
        current_url = self.existing_env.get("OPENAI_BASE_URL") or self.existing_env.get("LLM_URL") or default_urls[provider]
        url = ask("API Base URL", default=current_url, required=True)
        self.env["OPENAI_BASE_URL"] = url
        self.env["OLLAMA_BASE_URL"] = url if provider == "ollama" else self.env.get("OLLAMA_BASE_URL", "http://localhost:11434")

        # API Key
        if provider != "ollama":
            print(f"\n  {C.CYAN}Enter your {providers[idx].split('(')[0].strip()} API key{C.RESET}")
            current_key = self.existing_env.get("OPENAI_API_KEY", "")
            if current_key:
                self._info(f"Existing key found: {current_key[:8]}…{current_key[-4:]}")
                if not ask_yes("Replace existing key?", default=False):
                    self._ok("Keeping existing API key")
                    self.env["OPENAI_API_KEY"] = current_key
                    self.settings["llm_model"] = model
                    return
            key = ask("API Key", password=True)
            if key:
                self.env["OPENAI_API_KEY"] = key
        else:
            # Test Ollama connectivity
            if ask_yes("\n  Test Ollama connection now?", default=True):
                def _test_ollama():
                    import urllib.request
                    try:
                        req = urllib.request.Request(
                            f"{url}/api/tags",
                            headers={"User-Agent": "EnterpriseAI/3.0"}
                        )
                        with urllib.request.urlopen(req, timeout=6) as r:
                            return r.status, r.read()
                    except Exception as e:
                        raise e

                try:
                    status, body = spinner_run(L["test_connection"], _test_ollama)
                    self._ok(f"{L['connection_ok']} (HTTP {status})")
                    try:
                        data = json.loads(body)
                        model_names = [m["name"] for m in data.get("models", [])[:5]]
                        if model_names:
                            self._info(f"Available models: {', '.join(model_names)}")
                    except Exception:
                        pass
                except Exception as e:
                    self._warn(f"{L['connection_fail']}: {e}")
                    self._info("You can configure Ollama later and re-run setup.")

        self.settings["llm_model"] = model
        self._ok(f"LLM configured: {env_prefix}:{model}")

    # ──────────────────────────────────────────────────────────────────────
    # STEP 3 — Agent Identity
    # ──────────────────────────────────────────────────────────────────────

    def step_identity(self) -> None:
        self._header(3, L["step3"])
        agent = self.settings.get("agent", {})

        name = ask(
            "Agent Name",
            default=agent.get("name", "Enterprise AI Agent"),
            required=True,
            hint="e.g. SmartBot, OnyxAssistant",
        )
        personality = ask(
            "Agent Personality",
            default=agent.get("personality", "a professional, concise enterprise assistant"),
            hint="Describe how the agent should behave",
        )
        reply_lang_options = ["Auto-detect (from user message)", "English only", "Arabic only"]
        reply_lang_keys    = ["auto", "en", "ar"]
        current_rl = agent.get("reply_language", "auto")
        rl_default = reply_lang_keys.index(current_rl) if current_rl in reply_lang_keys else 0
        rl_idx = choose(reply_lang_options, "Agent reply language:", default=rl_default)

        self.settings["agent"] = {
            **agent,
            "name":           name or "Enterprise AI Agent",
            "personality":    personality or "a professional, concise enterprise assistant",
            "reply_language": reply_lang_keys[rl_idx],
        }
        self._ok(f"Agent: {name}")

    # ──────────────────────────────────────────────────────────────────────
    # STEP 4 — Security & Keys
    # ──────────────────────────────────────────────────────────────────────

    def step_security(self) -> None:
        self._header(4, L["step4"])
        existing_admin = self.existing_env.get("ADMIN_KEY", "")
        existing_user  = self.existing_env.get("USER_KEY", "")

        if existing_admin and existing_user:
            self._info(f"Existing ADMIN_KEY: {existing_admin[:8]}…")
            self._info(f"Existing USER_KEY:  {existing_user[:8]}…")
            if not ask_yes("Regenerate API keys?", default=False):
                self.env["ADMIN_KEY"] = existing_admin
                self.env["USER_KEY"]  = existing_user
                self._ok("Keeping existing keys")
                return

        admin_key = secrets.token_urlsafe(40)
        user_key  = secrets.token_urlsafe(40)
        self.env["ADMIN_KEY"] = admin_key
        self.env["USER_KEY"]  = user_key

        # Also update the legacy API_KEYS format that the app uses
        self.env["API_KEYS"] = f"admin:{admin_key},user:{user_key}"

        print(f"\n  {C.BOLD}Generated keys:{C.RESET}")
        print(f"  {C.CYAN}ADMIN_KEY{C.RESET} = {C.GREEN}{admin_key}{C.RESET}")
        print(f"  {C.CYAN}USER_KEY {C.RESET} = {C.GREEN}{user_key}{C.RESET}")
        print(f"\n  {C.YELLOW}⚠  Save these keys! They will not be shown again.{C.RESET}")

        # JWT + encryption keys
        self.env["JWT_SECRET"]      = secrets.token_urlsafe(40)
        self.env["ENCRYPTION_KEY"]  = secrets.token_urlsafe(40)
        self._ok("Security keys generated")

    # ──────────────────────────────────────────────────────────────────────
    # STEP 5 — Channels
    # ──────────────────────────────────────────────────────────────────────

    def step_channels(self) -> None:
        self._header(5, L["step5"])
        channels: dict[str, Any] = self.settings.get("channels", {})

        # Web Dashboard
        web_port = ask("Web Dashboard port", default="8000", hint="press Enter to keep 8000")
        channels["web"] = {"enabled": True, "port": int(web_port or 8000)}

        # WhatsApp
        if ask_yes("Enable WhatsApp integration?", default=False):
            prefix = ask("Command prefix", default="!", hint="character users type before commands")
            channels["whatsapp"] = {"enabled": True, "prefix": prefix or "!"}
            self._info("Requires WhatsApp Business API or Baileys bridge running locally.")
        else:
            channels.setdefault("whatsapp", {"enabled": False})

        # Telegram
        if ask_yes("Enable Telegram Bot?", default=False):
            existing_tok = self.existing_env.get("TELEGRAM_BOT_TOKEN", "")
            if existing_tok:
                self._info(f"Existing token: {existing_tok[:10]}…")
                if ask_yes("Keep existing Telegram token?", default=True):
                    self.env["TELEGRAM_BOT_TOKEN"] = existing_tok
                    channels["telegram"] = {"enabled": True}
                    self._ok("Telegram enabled")
                else:
                    tok = ask("Telegram Bot Token (from @BotFather)", required=True)
                    if tok:
                        self.env["TELEGRAM_BOT_TOKEN"] = tok
                        channels["telegram"] = {"enabled": True}
                        self._ok("Telegram enabled")
            else:
                tok = ask("Telegram Bot Token (from @BotFather)", required=True)
                if tok:
                    self.env["TELEGRAM_BOT_TOKEN"] = tok
                    channels["telegram"] = {"enabled": True}
                    self._ok("Telegram enabled")
        else:
            channels.setdefault("telegram", {"enabled": False})

        # Email / SMTP
        if ask_yes("Configure SMTP for email notifications?", default=False):
            smtp_server = ask("SMTP Server", default="smtp.gmail.com")
            smtp_port   = ask("SMTP Port", default="587")
            smtp_user   = ask("SMTP Username / Email")
            smtp_pass   = ask("SMTP Password / App Password", password=True)
            smtp_from   = ask("From Address", default=smtp_user)
            if smtp_server:
                self.env["SMTP_SERVER"] = smtp_server
                self.env["SMTP_PORT"]   = smtp_port or "587"
            if smtp_user:   self.env["SMTP_USER"] = smtp_user
            if smtp_pass:   self.env["SMTP_PASS"] = smtp_pass
            if smtp_from:   self.env["SMTP_FROM"] = smtp_from
            self._ok("SMTP configured")

        self.settings["channels"] = channels
        self._ok("Channels configured")

    # ──────────────────────────────────────────────────────────────────────
    # STEP 6 — Database / Accounting Setup   ★  THE MAIN NEW SECTION  ★
    # ──────────────────────────────────────────────────────────────────────

    def step_database(self) -> None:
        self._header(6, L["step6"])

        print(f"""
  {C.BOLD}What this step does:{C.RESET}
  • Configures a read-only connection to your accounting / ERP database
  • Builds the connection string automatically
  • Tests the connection (optional)
  • Auto-discovers tables and columns from the live database
  • Writes {C.CYAN}config/accounting_schema.json{C.RESET} used by the AI agent
        """)

        existing_enabled = self.settings.get("accounting", {}).get("enabled", False)
        if not ask_yes("Enable database / accounting integration?", default=existing_enabled):
            self.settings.setdefault("accounting", {})["enabled"] = False
            self._info("Accounting integration disabled. You can enable it later by re-running setup.")
            return

        self.settings.setdefault("accounting", {})["enabled"] = True

        # ── How many databases? ──────────────────────────────────────────
        existing_dbs: dict = self.existing_schema.get("databases", {})
        new_schema: dict = {"version": 2, "databases": dict(existing_dbs)}

        add_another = True
        while add_another:
            db_cfg = self._configure_single_db(new_schema)
            if db_cfg:
                key = db_cfg["key"]
                new_schema["databases"][key] = {
                    "name":    db_cfg["name"],
                    "db_url":  db_cfg["db_url"],
                    "enabled": True,
                    "tables":  db_cfg["tables"],
                    "query_aliases": {},
                }
                self._ok(f"Database '{db_cfg['name']}' added (key: {key})")

            if len(new_schema["databases"]) > 0:
                add_another = ask_yes("Add another database?", default=False)
            else:
                add_another = False

        self.schema = new_schema

        # ── Accounting permissions ────────────────────────────────────────
        print()
        self._info("Configure accounting query permissions:")
        all_queries = [
            "sales_summary", "revenue_by_month", "top_customers",
            "expenses_summary", "invoice_lookup", "cash_balance",
            "vendor_balances", "sales_by_item",
        ]
        allowed = []
        for q in all_queries:
            if ask_yes(f"  Allow query '{q}'?", default=True):
                allowed.append(q)

        acct = self.settings.get("accounting", {})
        acct.update({
            "enabled":        True,
            "read_only":      True,
            "allowed_queries": allowed,
        })
        self.settings["accounting"] = acct
        self._ok("Database setup complete")

    def _configure_single_db(self, existing_schema: dict) -> dict | None:
        """Walk the user through configuring a single database. Returns config dict or None."""
        print(f"\n  {C.BOLD}{C.CYAN}── New Database Configuration ──{C.RESET}")

        # DB type
        db_type_options = list(DB_DISPLAY_NAMES.values())
        db_type_keys    = list(DB_DISPLAY_NAMES.keys())
        type_idx = choose(db_type_options, "Database Type:", default=0)
        db_type  = db_type_keys[type_idx]

        # Logical key (internal identifier)
        default_key_map = {
            "mssql":      "onyxdb",
            "mysql":      "mysqldb",
            "postgresql": "pgdb",
            "sqlite":     "localdb",
        }
        existing_keys = list(existing_schema.get("databases", {}).keys())
        default_key   = default_key_map[db_type]
        if default_key in existing_keys:
            default_key = f"{default_key}_{len(existing_keys) + 1}"

        key = ask(
            "Internal key (short name for this DB)",
            default=default_key,
            required=True,
            hint="letters/numbers/underscore only, e.g. 'onyxdb'",
        ) or default_key
        key = re.sub(r"[^a-zA-Z0-9_]", "_", key).lower()

        display_name = ask("Database display name", default=key.replace("_", " ").title(), required=True)

        # ── Connection details by DB type ──────────────────────────────────
        conn_cfg: dict[str, str] = {}
        if db_type == "sqlite":
            sqlite_path = ask(
                "SQLite file path",
                default="data/accounting.db",
                required=True,
                hint="relative to project root",
            )
            conn_cfg["sqlite_path"] = sqlite_path or "data/accounting.db"
        else:
            # Check if user wants to paste a full URL directly
            if ask_yes("Paste full connection URL directly? (advanced)", default=False):
                full_url = ask("Full connection URL", required=True)
                if full_url:
                    conn_cfg["_full_url"] = full_url
            else:
                # Step-by-step
                existing_url = ""
                for db_entry in existing_schema.get("databases", {}).values():
                    if db_type in db_entry.get("db_url", ""):
                        existing_url = db_entry["db_url"]
                        break

                print(f"\n  {C.DIM}Enter connection details for {DB_DISPLAY_NAMES[db_type]}{C.RESET}")

                conn_cfg["host"] = ask(
                    "Host / IP address",
                    default="localhost",
                    required=True,
                    hint="e.g. 192.168.1.10 or db.company.local",
                ) or "localhost"

                conn_cfg["port"] = ask(
                    "Port",
                    default=DB_DEFAULT_PORTS[db_type],
                    hint=f"default is {DB_DEFAULT_PORTS[db_type]}",
                ) or DB_DEFAULT_PORTS[db_type]

                conn_cfg["db_name"] = ask(
                    "Database name",
                    required=True,
                    hint="e.g. OnyxDB, CompanyDB",
                ) or ""

                conn_cfg["username"] = ask(
                    "Username",
                    hint="use a read-only user in production",
                ) or ""

                conn_cfg["password"] = ask(
                    "Password",
                    password=True,
                ) or ""

                if db_type == "mssql":
                    # ODBC driver
                    odbc_options = [
                        "ODBC Driver 18 for SQL Server  (recommended)",
                        "ODBC Driver 17 for SQL Server",
                        "SQL Server  (older)",
                        "Custom driver name",
                    ]
                    odbc_keys = [
                        "ODBC Driver 18 for SQL Server",
                        "ODBC Driver 17 for SQL Server",
                        "SQL Server",
                        "custom",
                    ]
                    odbc_idx = choose(odbc_options, "ODBC Driver:", default=0)
                    odbc_drv = odbc_keys[odbc_idx]
                    if odbc_drv == "custom":
                        odbc_drv = ask("Driver name", required=True) or "ODBC Driver 18 for SQL Server"
                    conn_cfg["odbc_driver"] = odbc_drv

        # Build URL
        if "_full_url" in conn_cfg:
            db_url = conn_cfg["_full_url"]
        else:
            db_url = build_connection_url(db_type, conn_cfg)

        print(f"\n  {C.DIM}Connection URL:{C.RESET}")
        print(f"  {C.CYAN}{db_url[:100]}{'…' if len(db_url) > 100 else ''}{C.RESET}")

        # ── Test connection ────────────────────────────────────────────────
        tables: dict[str, Any] = {}
        if ask_yes("\n  Test database connection now?", default=True):
            try:
                ok, msg = spinner_run(L["test_connection"], test_db_connection, db_url)
                if ok:
                    print(f"  {C.GREEN}✔  {L['connection_ok']}{C.RESET}")

                    # ── Auto-discover ──────────────────────────────────────
                    if ask_yes("  Auto-discover tables and columns?", default=True):
                        try:
                            raw = spinner_run("Discovering schema …", discover_db_schema, db_url)
                            if "_error" in raw:
                                self._warn(f"Discovery error: {raw['_error']}")
                            else:
                                tables = normalize_discovered(raw)
                                print(f"  {C.GREEN}✔  Found {len(tables)} tables{C.RESET}")
                                sample = list(tables.keys())[:8]
                                print(f"  {C.DIM}Tables: {', '.join(sample)}{'…' if len(tables) > 8 else ''}{C.RESET}")
                        except Exception as e:
                            self._warn(f"Auto-discover failed: {e}")
                else:
                    self._warn(f"{L['connection_fail']}: {msg}")
                    self._info("Check host/port/credentials. The URL will still be saved.")
            except Exception as e:
                self._warn(f"Test error: {e}")
        else:
            self._info("Skipping connection test. Remember to test before starting the agent.")

        # ── If no tables discovered, use defaults for known DB types ──────
        if not tables and db_type == "mssql":
            self._info("Using default Onyx Pro table mappings (you can edit accounting_schema.json later).")
            tables = _default_onyx_tables()

        # ── Store URL in .env ─────────────────────────────────────────────
        env_key = f"ACCOUNTING_DB_URL_{key.upper()}" if len(existing_schema.get("databases", {})) > 0 else "ACCOUNTING_DB_URL"
        self.env[env_key] = db_url
        # Also set the primary key for backward compatibility
        if not self.env.get("ACCOUNTING_DB_URL"):
            self.env["ACCOUNTING_DB_URL"] = db_url

        return {
            "key":    key,
            "name":   display_name or key,
            "db_url": db_url,
            "tables": tables,
        }

    # ──────────────────────────────────────────────────────────────────────
    # STEP 7 — Permissions
    # ──────────────────────────────────────────────────────────────────────

    def step_permissions(self) -> None:
        self._header(7, L["step7"])
        existing = self.settings.get("permissions", {})

        perm_items = [
            ("web_search",          "Web search",                        True),
            ("calculator",          "Calculator",                        True),
            ("get_current_time",    "Get current time",                  True),
            ("read_file",           "File system read access",           False),
            ("knowledge_rag",       "Knowledge base (RAG)",              True),
            ("accounting_tools",    "Accounting / ERP queries",          False),
            ("generate_report",     "Report generation",                 True),
            ("list_reports",        "List reports",                      True),
            ("search_conversations","Search conversation history",       True),
            ("send_email",          "Send email notifications",          False),
            ("send_webhook",        "Send webhook alerts (Slack/Teams)", False),
        ]

        perms: dict[str, bool] = {}
        for key, label, default in perm_items:
            current = existing.get(key, default)
            perms[key] = ask_yes(f"  Enable: {label}", default=current)

        # If accounting is enabled in step 6, auto-enable accounting_tools
        if self.settings.get("accounting", {}).get("enabled", False):
            perms["accounting_tools"] = perms.get("accounting_tools", True)

        self.settings["permissions"] = perms
        self._ok("Permissions configured")

    # ──────────────────────────────────────────────────────────────────────
    # STEP 8 — Review & Finalize
    # ──────────────────────────────────────────────────────────────────────

    def step_finalize(self) -> None:
        self._header(8, L["step8"])

        # ── Summary ───────────────────────────────────────────────────────
        print(f"\n  {C.BOLD}Configuration Summary:{C.RESET}")
        agent = self.settings.get("agent", {})
        print(f"  {C.CYAN}Agent:{C.RESET}      {agent.get('name', '—')}")
        print(f"  {C.CYAN}LLM:{C.RESET}        {self.env.get('DEFAULT_MODEL', '—')}")
        print(f"  {C.CYAN}LLM URL:{C.RESET}    {self.env.get('OPENAI_BASE_URL', self.env.get('OLLAMA_BASE_URL', '—'))}")
        print(f"  {C.CYAN}Admin Key:{C.RESET}  {self.env.get('ADMIN_KEY', '—')[:12]}…")
        print(f"  {C.CYAN}User Key:{C.RESET}   {self.env.get('USER_KEY', '—')[:12]}…")
        acct = self.settings.get("accounting", {})
        print(f"  {C.CYAN}Accounting:{C.RESET} {'✔ enabled' if acct.get('enabled') else '✗ disabled'}")
        db_count = len(self.schema.get("databases", {}))
        if db_count:
            print(f"  {C.CYAN}Databases:{C.RESET}  {db_count} configured")
            for k, v in self.schema.get("databases", {}).items():
                tbl_count = len(v.get("tables", {}))
                print(f"    {C.DIM}• {v['name']} ({k}) — {tbl_count} tables{C.RESET}")

        # ── Confirm ───────────────────────────────────────────────────────
        if not ask_yes(f"\n  Save configuration?", default=True):
            print(C.warn("\n  Setup cancelled — no files were modified."))
            sys.exit(0)

        # Backup existing config
        backup_path = self.cfg.backup()
        self._info(f"{L['backup_created']}: {backup_path.name}")

        # ── Add metadata to settings ──────────────────────────────────────
        self.settings["version"] = 4
        self.settings["setup_completed_at"] = datetime.now().isoformat()

        # ── Write files ───────────────────────────────────────────────────
        self.cfg.write_env(self.env)
        self._ok(".env written")

        self.cfg.write_settings(self.settings)
        self._ok("config/settings.json written")

        if self.schema.get("databases"):
            self.cfg.write_schema(self.schema)
            self._ok("config/accounting_schema.json written")

        # ── Done banner ───────────────────────────────────────────────────
        print(f"\n{C.GREEN}{'═' * 60}{C.RESET}")
        print(f"{C.GREEN}{C.BOLD}  {L['done']}{C.RESET}")
        print(f"{C.GREEN}{'═' * 60}{C.RESET}")

        web_port = self.settings.get("channels", {}).get("web", {}).get("port", 8000)
        print(f"""
  {C.BOLD}Files written:{C.RESET}
    {C.CYAN}•{C.RESET} .env
    {C.CYAN}•{C.RESET} config/settings.json
    {C.CYAN}•{C.RESET} config/accounting_schema.json  {'(' + str(db_count) + ' databases)' if db_count else '(not written — accounting disabled)'}

  {C.BOLD}Next steps:{C.RESET}
    1. {C.CYAN}python start.py{C.RESET}  — Start the agent
    2. {C.CYAN}http://localhost:{web_port}{C.RESET}  — Open the dashboard
    3. API endpoint: {C.CYAN}http://localhost:{web_port}/docs{C.RESET}

  {C.BOLD}API Access:{C.RESET}
    Admin key: {C.YELLOW}{self.env.get('ADMIN_KEY', '—')}{C.RESET}
    User key:  {C.YELLOW}{self.env.get('USER_KEY', '—')}{C.RESET}
    Header:    {C.DIM}X-API-Key: <key>{C.RESET}
        """)


# ── Default Onyx Pro table mappings (used when auto-discover is skipped) ─

def _default_onyx_tables() -> dict:
    return {
        "sales_invoices": {
            "table": "SalesInvoices",
            "columns": {
                "id": "InvoiceID", "number": "InvoiceNo", "date": "InvoiceDate",
                "net_total": "NetTotal", "tax": "TaxAmount", "discount": "DiscountAmount",
                "status": "Status", "customer_id": "CustomerID",
            },
        },
        "customers": {
            "table": "Customers",
            "columns": {
                "id": "CustomerID", "name": "CustomerName", "code": "CustomerCode",
                "phone": "Phone", "email": "Email",
            },
        },
        "accounts": {
            "table": "Accounts",
            "columns": {
                "id": "AccountID", "name": "AccountName", "code": "AccountCode",
                "type": "AccountType",
            },
        },
        "journal_entries": {
            "table": "JournalEntries",
            "columns": {
                "id": "EntryID", "date": "EntryDate", "account_id": "AccountID",
                "debit": "Debit", "credit": "Credit", "description": "Description",
                "reference": "ReferenceNo",
            },
        },
        "purchase_invoices": {
            "table": "PurchaseInvoices",
            "columns": {
                "id": "PurchaseID", "number": "PurchaseNo", "date": "PurchaseDate",
                "net_total": "NetTotal", "tax": "TaxAmount", "status": "Status",
                "vendor_id": "VendorID",
            },
        },
        "vendors": {
            "table": "Vendors",
            "columns": {"id": "VendorID", "name": "VendorName", "code": "VendorCode"},
        },
        "items": {
            "table": "Items",
            "columns": {
                "id": "ItemID", "name": "ItemName", "code": "ItemCode",
                "category": "Category", "unit_price": "UnitPrice",
            },
        },
    }


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  Web Setup Launcher                                                      ║
# ╚══════════════════════════════════════════════════════════════════════════╝

def launch_web_setup() -> None:
    """Start the FastAPI web setup server."""
    print(L["web_launching"])
    print(f"\n  {C.CYAN}{L['web_open']}{C.RESET}")
    print(f"  {C.BOLD}{C.GREEN}{L['web_url']}{C.RESET}")
    print(L["web_stop"])

    try:
        import webbrowser
        import time as _t
        _t.sleep(1.5)  # wait for server to start
        webbrowser.open(L["web_url"])
    except Exception:
        pass

    try:
        subprocess.run([
            sys.executable, "-m", "uvicorn",
            "setup_web:app",
            "--host", "0.0.0.0",
            "--port", "8088",
            "--reload",
        ], check=False)
    except KeyboardInterrupt:
        print(f"\n{C.YELLOW}  Server stopped.{C.RESET}")


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  Entry point                                                             ║
# ╚══════════════════════════════════════════════════════════════════════════╝

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Enterprise AI Agent -- Professional Setup Wizard v3.0",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python setup.py            -- Interactive mode selector
  python setup.py --cli      -- CLI wizard (no browser required)
  python setup.py --web      -- Web-based wizard
  python setup.py --update   -- Update existing configuration
        """,
    )
    parser.add_argument("--cli",    action="store_true", help="Force CLI mode")
    parser.add_argument("--web",    action="store_true", help="Force Web mode")
    parser.add_argument("--update", action="store_true", help="Update existing configuration (keeps unchanged values)")
    args = parser.parse_args()

    cfg = ConfigManager()

    # Mode selection
    if args.cli:
        mode = "cli"
    elif args.web:
        mode = "web"
    else:
        banner(L["welcome_title"])
        print(f"  {C.DIM}Professional Setup Wizard v3.0{C.RESET}\n")
        modes = [L["mode_cli"], L["mode_web"]]
        idx  = choose(modes, L["choose_mode"], default=0)
        mode = "cli" if idx == 0 else "web"

    if mode == "cli":
        try:
            wizard = CLIWizard(cfg, update_mode=args.update)
            wizard.run()
        except KeyboardInterrupt:
            print(f"\n\n{C.YELLOW}  Setup cancelled by user.{C.RESET}\n")
            sys.exit(1)
    else:
        launch_web_setup()


if __name__ == "__main__":
    main()
