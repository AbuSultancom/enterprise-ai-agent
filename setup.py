#!/usr/bin/env python3
"""
Enterprise AI Agent — Onboarding Wizard (v4)
============================================
Clean, modern, bilingual (AR/EN) setup experience.

Run:  python setup.py
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

# ─── ANSI palette ────────────────────────────────────────────────
C = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "dim": "\033[2m",
    "green": "\033[92m",
    "yellow": "\033[93m",
    "blue": "\033[94m",
    "cyan": "\033[96m",
    "red": "\033[91m",
    "magenta": "\033[95m",
}
ANSI_RE = _re.compile(r"\033\[[0-9;]*m")


def color(text: str, *styles: str) -> str:
    if not styles:
        return text
    return "".join(C.get(s, "") for s in styles) + text + C["reset"]


def clear() -> None:
    os.system("cls" if os.name == "nt" else "clear")


# ─── Bilingual strings ────────────────────────────────────────────
LANG = "ar"  # will be set by user at start

def t(key: str) -> str:
    """Get translation for current language."""
    return STR[LANG].get(key, key) if 'STR' in dir() else key

# STR dictionary starts on next line

STR = {
    "ar": {
        "welcome_title": "مرحباً بك في معالج إعداد وكيل الذكاء الاصطناعي",
        "welcome_desc": "هذا المعالج يهيئ وكيلك في 7 خطوات خلال ~3 دقائق",
        "steps": [
            "مزود الذكاء — اختر الموديل (محلي أو سحاب)",
            "هوية الوكيل — الاسم، اللغة، الشخصية",
            "الأمان — مفاتيح API للوحة التحكم والقنوات",
            "القنوات — واتساب، تلغرام، جهات الاتصال المسموحة",
            "المحاسبة — ربط بقاعدة بيانات Onyx Pro",
            "الصلاحيات — الأدوات المسموح للوكيل استخدامها",
            "إنهاء — حفظ الإعدادات + ربط واتساب",
        ],
        "step_titles": [
            "مزود الذكاء",
            "هوية الوكيل",
            "الأمان",
            "القنوات",
            "المحاسبة",
            "الصلاحيات",
            "إنهاء",
        ],
        "press_enter": "اضغط Enter للبدء...",
        "model_prompt": "أي مزود تريد استخدامه؟",
        "model_ollama": "Ollama — محلي، مجاني، خصوصي (موصى به)",
        "model_deepseek": "DeepSeek — سحاب، رخيص وقوي",
        "model_openai": "OpenAI — سحاب (GPT-4o...)",
        "model_other": "نقطة نهاية متوافقة مع OpenAI (Qwen / vLLM...)",
        "ollama_model": "اسم الموديل في Ollama",
        "ollama_url": "رابط Ollama",
        "ollama_check_ok": "Ollama يعمل",
        "ollama_check_fail": "لا يمكن الوصول إلى Ollama",
        "api_base": "رابط API الأساسي",
        "api_key": "مفتاح API",
        "model_name": "اسم الموديل",
        "api_check_ok": "مفتاح API يعمل",
        "api_check_fail": "تعذر التحقق من المفتاح — تم الحفظ على أي حال",
        "no_api_key": "لم تدخل مفتاح API — المكالمات السحابية ستفشل حتى تضبط OPENAI_API_KEY",
        "model_ok": "الموديل",
        "agent_name": "اسم الوكيل (الذي يظهر للمستخدمين)",
        "agent_lang": "بأي لغة يجب أن يرد الوكيل؟",
        "lang_auto": "نفس لغة المستخدم (تلقائي)",
        "lang_ar": "العربية — يرد بالعربية دائماً",
        "lang_en": "English — always answers in English",
        "agent_personality": "الشخصية / التعليمات (سطر واحد)",
        "personality_default": "مساعد مؤسسي محترف ومختصر",
        "identity_ok": "الهوية",
        "gen_keys": "توليد مفاتيح API عشوائية آمنة؟",
        "keys_generated": "تم توليد المفاتيح (ستظهر في النهاية — احفظها)",
        "admin_key": "مفتاح المشرف (صلاحية كاملة)",
        "user_key": "مفتاح المستخدم (محادثة فقط)",
        "enable_whatsapp": "تفعيل قناة واتساب؟ (تسجيل دخول QR)",
        "wa_warn": "بروتوكول واتساب غير رسمي — استخدم رقماً مخصصاً للبوت",
        "wa_prefix": "يرد فقط على الرسائل التي تبدأ ببادئة؟ (اترك فارغاً للكل)",
        "wa_ignore_groups": "تجاهل المجموعات؟",
        "wa_role_prompt": "أي صلاحية لمستخدمي واتساب؟",
        "wa_role_user": "user — محادثة وأدوات آمنة فقط (موصى به)",
        "wa_role_admin": "admin — كل شيء بما في ذلك المحاسبة (للمالك فقط)",
        "wa_allowed": "الأرقام المسموحة (دولي، مفصول بفاصلة؛ فارغ = الجميع)",
        "wa_allowed_example": "مثال: 967712345678,966501234567",
        "wa_ok": "واتساب",
        "enable_telegram": "تفعيل قناة تلغرام؟ (بوت Token)",
        "tg_create_hint": "أنشئ بوتاً مع @BotFather على تلغرام لتحصل على Token",
        "tg_token": "Token البوت",
        "tg_check_ok": "Token البوت صحيح",
        "tg_check_fail": "تعذر التحقق من Token — تم الحفظ على أي حال",
        "tg_no_token": "لم تدخل Token — بوت تلغرام لن يعمل حتى تضبط TELEGRAM_BOT_TOKEN",
        "tg_allowed": "مستخدمي تلغرام المسموحين (IDs أو @usernames، فارغ = الجميع)",
        "tg_ok": "تلغرام",
        "enable_accounting": "ربط قاعدة بيانات المحاسبة الآن؟",
        "acc_skip": "تم التجاهل. اضبط ACCOUNTING_DB_URL في .env لاحقاً",
        "acc_host": "خادم SQL Server",
        "acc_port": "المنفذ",
        "acc_db": "اسم قاعدة البيانات",
        "acc_user": "مستخدم DB (للقراءة فقط!)",
        "acc_pass": "كلمة مرور DB",
        "acc_server_ok": "الخادم يمكن الوصول إليه",
        "acc_server_fail": "لا يمكن الوصول إلى الخادم — تم الحفظ على أي حال",
        "acc_warn": "عدل أسماء الجداول في connectors/accounting.py حسب هيكل Onyx لديك",
        "acc_ok": "تم حفظ اتصال المحاسبة",
        "perm_web": "السماح بالبحث في الويب؟",
        "perm_calc": "السماح بالآلة الحاسبة؟",
        "perm_time": "السماح بالتاريخ والوقت؟",
        "perm_file": "السماح بقراءة الملفات؟",
        "perm_accounting": "السماح للوكيل باستعلام بيانات المحاسبة؟",
        "perm_knowledge": "استخدام قاعدة المعرفة (مستندات الشركة)؟",
        "perm_conversations": "السماح للوكيل بالبحث في المحادثات السابقة؟",
        "perm_reports": "السماح بإنشاء وعرض التقارير؟",
        "perm_enabled": "التفعيلات",
        "link_wa_now": "ربط واتساب الآن؟ (سيظهر QR هنا)",
        "link_wa_skip": "تم التجاهل. سيظهر QR عند أول تشغيل لـ start.py",
        "link_wa_no_node": "Node.js غير مثبت — لا يمكن ربط واتساب هنا",
        "node_hint": "ثبته من https://nodejs.org ثم اركض: python start.py",
        "npm_install": "تثبيت اعتماديات واتساب",
        "npm_fail": "فشل تثبيت npm. اركض: cd whatsapp && npm install يدوياً",
        "link_start": "تشغيل الجسر... سيظهر QR أدناه",
        "link_phone_hint": "على هاتفك: واتساب → الأجهزة المرتبطة → ربط جهاز",
        "link_wait": "الانتظار حتى 3 دقائق للفحص",
        "link_ok": "واتساب مرتبط بنجاح!",
        "link_timeout": "لم يتم الربط بعد (انتهت المهلة أو توقف الجسر). لا مشكلة: اركض start.py وسيظهر QR مجدداً",
        "summary_title": "✅  تم الإعداد بنجاح",
        "keys_warn": "🔑  مفاتيح API — احفظها",
        "start_cmd": "🚀  شغّل كل شيء بأمر واحد",
        "yes": "نعم",
        "no": "لا",
        "choose": "اختر",
        "aborted": "تم الإلغاء — لم يتم حفظ أي شيء.",
        "admin": "مشرف",
        "user": "مستخدم",
    },
    "en": {
        "welcome_title": "Welcome! Configure your AI agent in ~3 minutes",
        "welcome_desc": "This wizard will set up everything in 7 steps:",
        "steps": [
            "Model provider — local or cloud model",
            "Agent identity — name, language, personality",
            "Security — API keys for dashboard & channels",
            "Channels — WhatsApp, Telegram, allowed contacts",
            "Accounting — Onyx Pro read-only connection",
            "Permissions — tools the agent may use",
            "Finish — save + optional WhatsApp QR linking",
        ],
        "step_titles": [
            "Model Provider",
            "Agent Identity",
            "Security",
            "Channels",
            "Accounting",
            "Permissions",
            "Finish",
        ],
        "press_enter": "Press Enter to begin...",
        "model_prompt": "Which provider do you want to use?",
        "model_ollama": "Ollama — local, private, free (recommended)",
        "model_deepseek": "DeepSeek — cloud API, cheap & strong",
        "model_openai": "OpenAI — cloud API (GPT-4o etc.)",
        "model_other": "Other OpenAI-compatible endpoint (Qwen / vLLM...)",
        "ollama_model": "Ollama model name",
        "ollama_url": "Ollama URL",
        "ollama_check_ok": "Ollama is reachable",
        "ollama_check_fail": "Ollama not reachable",
        "api_base": "API base URL",
        "api_key": "API key",
        "model_name": "Model name",
        "api_check_ok": "API key works",
        "api_check_fail": "Could not verify key — saved anyway",
        "no_api_key": "No API key entered — cloud calls will fail until you set OPENAI_API_KEY",
        "model_ok": "Model",
        "agent_name": "Agent name (shown to users)",
        "agent_lang": "Which language should the agent answer in?",
        "lang_auto": "Same as the user's message (auto)",
        "lang_ar": "Arabic — always answers in Arabic",
        "lang_en": "English — always answers in English",
        "agent_personality": "Personality / instructions (one line)",
        "personality_default": "a professional, concise enterprise assistant",
        "identity_ok": "Identity",
        "gen_keys": "Generate secure random API keys for you?",
        "keys_generated": "Keys generated (shown at the end — save them)",
        "admin_key": "Admin key (full access)",
        "user_key": "User key (chat only)",
        "enable_whatsapp": "Enable the WhatsApp channel? (QR login)",
        "wa_warn": "QR login uses the UNOFFICIAL WhatsApp Web protocol — use a dedicated number.",
        "wa_prefix": "Reply only to messages starting with a prefix? (empty = all)",
        "wa_ignore_groups": "Ignore group chats?",
        "wa_role_prompt": "Which role should WhatsApp users get?",
        "wa_role_user": "user — chat & safe tools only (recommended)",
        "wa_role_admin": "admin — everything including accounting queries (owner only)",
        "wa_allowed": "Allowed WhatsApp numbers (international format, comma-separated; empty = everyone)",
        "wa_allowed_example": "Example: 967712345678,8613800138000",
        "wa_ok": "WhatsApp",
        "enable_telegram": "Enable the Telegram channel? (bot token)",
        "tg_create_hint": "Create a bot with @BotFather on Telegram to get a token.",
        "tg_token": "Telegram bot token",
        "tg_check_ok": "Bot token verified",
        "tg_check_fail": "Could not verify token — saved anyway",
        "tg_no_token": "No token entered — Telegram bridge will not start until you set TELEGRAM_BOT_TOKEN",
        "tg_allowed": "Allowed Telegram users (IDs or @usernames, comma; empty = everyone)",
        "tg_ok": "Telegram",
        "enable_accounting": "Connect the accounting database now?",
        "acc_skip": "Skipped. Set ACCOUNTING_DB_URL in .env later.",
        "acc_host": "SQL Server host/IP",
        "acc_port": "Port",
        "acc_db": "Database name",
        "acc_user": "DB user (read-only!)",
        "acc_pass": "DB password",
        "acc_server_ok": "Server reachable",
        "acc_server_fail": "Cannot reach server — saved anyway; check network/firewall",
        "acc_warn": "Adapt table names in connectors/accounting.py to your Onyx schema.",
        "acc_ok": "Accounting connection string saved.",
        "perm_web": "Allow web search?",
        "perm_calc": "Allow calculator?",
        "perm_time": "Allow date/time?",
        "perm_file": "Allow reading files?",
        "perm_accounting": "Allow the agent to query accounting data?",
        "perm_knowledge": "Use the knowledge base (company documents)?",
        "perm_conversations": "Allow the agent to search past conversations?",
        "perm_reports": "Allow creating & viewing reports?",
        "perm_enabled": "Enabled",
        "link_wa_now": "Link your WhatsApp number NOW? (QR will appear here)",
        "link_wa_skip": "Skipped. The QR will appear on the first 'python start.py' run instead.",
        "link_wa_no_node": "Node.js is not installed — cannot link WhatsApp here.",
        "node_hint": "Install it from https://nodejs.org then run: python start.py",
        "npm_install": "Installing WhatsApp bridge dependencies",
        "npm_fail": "npm install failed. Run 'cd whatsapp && npm install' manually.",
        "link_start": "Starting the bridge... the QR code will appear below.",
        "link_phone_hint": "On your phone: WhatsApp → Linked devices → Link a device",
        "link_wait": "Waiting up to 3 minutes for you to scan.",
        "link_ok": "WhatsApp LINKED successfully! Session saved — no QR needed next time.",
        "link_timeout": "Not linked yet (timeout or bridge stopped). No problem: run 'python start.py' and the QR will show again.",
        "summary_title": "✅  SETUP COMPLETE",
        "keys_warn": "🔑  YOUR API KEYS — SAVE THESE:",
        "start_cmd": "🚀  START EVERYTHING WITH ONE COMMAND:",
        "yes": "yes",
        "no": "no",
        "choose": "Choose",
        "aborted": "Aborted — nothing was saved.",
        "admin": "admin",
        "user": "user",
    },
}

L = STR[LANG]


# ─── UI helpers ───────────────────────────────────────────────────
def box_top(width: int = 60) -> str:
    return color("  ┌" + "─" * width + "┐", "cyan")


def box_mid(width: int = 60) -> str:
    return color("  ├" + "─" * width + "┤", "cyan")


def box_bot(width: int = 60) -> str:
    return color("  └" + "─" * width + "┘", "cyan")


def box_line(text: str, width: int = 60) -> str:
    plain = ANSI_RE.sub("", text)
    pad = width - len(plain)
    return color("  │ ", "cyan") + text + " " * max(pad, 0) + color(" │", "cyan")


def banner() -> None:
    clear()
    print(color(r"""
    ╔══════════════════════════════════════════════╗
    ║     ___                   _                ║
    ║    | __|_ ___ __ _ _ __  (_)___ _ _  ___   ║
    ║    | _|\ \ / '_ \ '_ \ | | / -_) ' \/ -_)  ║
    ║    |___/_\_\ .__/ .__/_|_|_\___|_||_\___|  ║
    ║            |_|  |_|                        ║
    ╚══════════════════════════════════════════════╝
    """, "cyan", "bold"))
    print(color(f"   ╔══ {L['welcome_title']} ══╗", "bold"))
    print()
    for i, s in enumerate(L["steps"], 1):
        print(color(f"     {i:>2}. {s}", "dim"))
    print()
    print(color(f"   {L['press_enter']}", "yellow"))
    input(color("   ▶ ", "green", "bold"))
    clear()


def progress_bar(done: int) -> str:
    filled = done * 20 // TOTAL_STEPS
    pct = done * 100 // TOTAL_STEPS
    bar = color("█" * filled, "green") + color("░" * (20 - filled), "dim")
    step_text = f"{done}/{TOTAL_STEPS}" if done > 0 else "   "
    return f"  {bar}  {color(str(pct) + '%', 'bold')}  {color(step_text, 'dim')}  "


def section(num: int, subtitle: str = "") -> None:
    print()
    pbar = progress_bar(num - 1)
    title = L["step_titles"][num - 1]
    print(color("  ┌" + "─" * 62 + "┐", "cyan"))
    print(pbar + color("│", "cyan") + color(f" {title} ", "bold") + color("│", "cyan"))
    print(color("  ├" + "─" * 62 + "┤", "cyan"))
    if subtitle:
        print(color(f"  │ {subtitle}".ljust(66) + "│", "dim"))
    print(color("  └" + "─" * 62 + "┘", "cyan"))
    print()


def ok(msg: str) -> None:
    print(f"  {color('✔', 'green', 'bold')} {color(msg, 'green')}")


def warn(msg: str) -> None:
    print(f"  {color('⚠', 'yellow', 'bold')} {color(msg, 'yellow')}")


def fail(msg: str) -> None:
    print(f"  {color('✖', 'red', 'bold')} {color(msg, 'red')}")


def info(msg: str) -> None:
    print(f"  {color('·', 'cyan')} {color(msg, 'dim')}")


# ─── Input helpers ────────────────────────────────────────────────
def ask(prompt: str, default: str = "") -> str:
    suffix = color(f" [{default}]", "dim") if default else ""
    val = input(f"  {color('?', 'yellow')} {prompt}{suffix}: ").strip()
    return val or default


def ask_yes(prompt: str, default: bool = True) -> bool:
    hint = color("[Y/n]", "dim") if default else color("[y/N]", "dim")
    val = input(f"  {color('?', 'yellow')} {prompt} {hint}: ").strip().lower()
    if not val:
        return default
    return val in ("y", "yes", "1", "true", "نعم", "yup", "yeah")


def ask_choice(prompt: str, choices: list[str], default: int = 0) -> int:
    print(f"  {color('?', 'yellow')} {prompt}")
    for i, c in enumerate(choices, 1):
        if i - 1 == default:
            print(f"    {color('●', 'green')} {color(str(i) + ')', 'green', 'bold')} {c}")
        else:
            print(f"    {color('○', 'dim')} {i}) {color(c, 'dim')}")
    while True:
        val = input(f"    {color('›', 'cyan')} {L['choose']} [{default + 1}]: ").strip()
        if not val:
            return default
        if val.isdigit() and 1 <= int(val) <= len(choices):
            return int(val) - 1
        fail("❌")


# ─── Spinner ──────────────────────────────────────────────────────
class Spinner:
    def __init__(self, text: str):
        self.text = text
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self):
        frames = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
        i = 0
        while not self._stop.is_set():
            sys.stdout.write(f"\r  {color(frames[i % len(frames)], 'cyan')} {self.text}...")
            sys.stdout.flush()
            i += 1
            time.sleep(0.08)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *args):
        self._stop.set()
        self._thread.join()
        sys.stdout.write("\r" + " " * (len(self.text) + 14) + "\r")
        sys.stdout.flush()


# ─── Network tests ────────────────────────────────────────────────
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
        p = shutil.which(name)
        if p:
            return p
    return None


def node_cmd() -> str | None:
    return shutil.which("node") or shutil.which("node.exe")


# ─── Steps ────────────────────────────────────────────────────────
def step_model(env: dict, settings: dict) -> None:
    section(1, L["steps"][0])
    choice = ask_choice(L["model_prompt"], [
        L["model_ollama"],
        L["model_deepseek"],
        L["model_openai"],
        L["model_other"],
    ])
    if choice == 0:
        env["DEFAULT_MODEL"] = "ollama:" + ask(L["ollama_model"], "qwen2.5:7b")
        env["OLLAMA_BASE_URL"] = ask(L["ollama_url"], "http://localhost:11434")
        with Spinner(L["ollama_check_ok"]):
            good, info = test_http(env["OLLAMA_BASE_URL"].rstrip("/") + "/api/tags")
        if good:
            ok(f"{L['ollama_check_ok']} ({info})")
        else:
            warn(f"{L['ollama_check_fail']} ({info})")
    else:
        presets = {1: ("https://api.deepseek.com/v1", "deepseek-chat"),
                    2: ("https://api.openai.com/v1", "gpt-4o-mini"),
                    3: ("", "")}
        base, model = presets[choice]
        env["OPENAI_BASE_URL"] = ask(L["api_base"], base)
        env["OPENAI_API_KEY"] = ask(L["api_key"])
        env["DEFAULT_MODEL"] = "openai:" + ask(L["model_name"], model)
        if env["OPENAI_API_KEY"]:
            with Spinner(L["api_check_ok"]):
                good, info = test_http(
                    env["OPENAI_BASE_URL"].rstrip("/") + "/models",
                    {"Authorization": f"Bearer {env['OPENAI_API_KEY']}"})
            if good:
                ok(f"{L['api_check_ok']} ({info})")
            else:
                warn(L["api_check_fail"])
        else:
            warn(L["no_api_key"])
    settings["llm"] = {"default_model": env["DEFAULT_MODEL"]}
    ok(f"{L['model_ok']}: {env['DEFAULT_MODEL']}")


def step_identity(env: dict, settings: dict) -> None:
    section(2, L["steps"][1])
    name = ask(L["agent_name"], "Enterprise AI Agent")
    lang_idx = ask_choice(L["agent_lang"], [
        L["lang_auto"], L["lang_ar"], L["lang_en"],
    ])
    lang = ["auto", "ar", "en"][lang_idx]
    personality = ask(L["agent_personality"], L["personality_default"])
    settings["agent"] = {"name": name, "language": lang, "personality": personality}
    ok(f"{L['identity_ok']}: {name} · {lang}")


def step_security(env: dict, settings: dict) -> None:
    section(3, L["steps"][2])
    if ask_yes(L["gen_keys"], True):
        env["ADMIN_KEY"] = secrets.token_urlsafe(24)
        env["USER_KEY"] = secrets.token_urlsafe(24)
        ok(L["keys_generated"])
    else:
        env["ADMIN_KEY"] = ask(L["admin_key"], "dev-admin-key")
        env["USER_KEY"] = ask(L["user_key"], "dev-user-key")
    settings["security"] = {"note": "admin = full access, user = chat + read only"}


def step_channels(env: dict, settings: dict) -> None:
    section(4, L["steps"][3])
    settings["channels"] = {}

    # WhatsApp
    wa_on = ask_yes(L["enable_whatsapp"], True)
    env["WHATSAPP_ENABLED"] = "true" if wa_on else "false"
    if wa_on:
        warn(L["wa_warn"])
        env["BOT_PREFIX"] = ask(L["wa_prefix"], "")
        env["IGNORE_GROUPS"] = "true" if ask_yes(L["wa_ignore_groups"], True) else "false"
        role_choice = ask_choice(L["wa_role_prompt"], [
            L["wa_role_user"],
            L["wa_role_admin"],
        ])
        env["WHATSAPP_ROLE"] = "user" if role_choice == 0 else "admin"
        settings["channels"]["whatsapp"] = {
            "role": env["WHATSAPP_ROLE"],
        }
        ok(f"{L['wa_ok']}: prefix '{env['BOT_PREFIX'] or '(all)'}' · role {env['WHATSAPP_ROLE']}")
    else:
        settings["channels"]["whatsapp"] = {"enabled": False}

    print()

    # Telegram
    tg_on = ask_yes(L["enable_telegram"], False)
    env["TELEGRAM_ENABLED"] = "true" if tg_on else "false"
    if tg_on:
        info(L["tg_create_hint"])
        env["TELEGRAM_BOT_TOKEN"] = ask(L["tg_token"], "")
        if env["TELEGRAM_BOT_TOKEN"]:
            with Spinner(L["tg_check_ok"]):
                good, info2 = test_http(
                    f"https://api.telegram.org/bot{env['TELEGRAM_BOT_TOKEN']}/getMe")
            if good:
                ok(L["tg_check_ok"])
            else:
                warn(f"{L['tg_check_fail']} ({info2})")
        else:
            warn(L["tg_no_token"])
        tg_allowed = ask(L["tg_allowed"], "")
        env["TELEGRAM_ALLOWED"] = ",".join(x.strip() for x in tg_allowed.split(",") if x.strip())
        settings["channels"]["telegram"] = {"enabled": True, "allowed": env["TELEGRAM_ALLOWED"]}
        token_status = "set" if env.get("TELEGRAM_BOT_TOKEN") else "MISSING"
        ok(f"{L['tg_ok']}: token {token_status}")
    else:
        settings["channels"]["telegram"] = {"enabled": False}


def step_accounting(env: dict, settings: dict) -> None:
    section(5, L["steps"][4])
    enabled = ask_yes(L["enable_accounting"], False)
    settings["accounting"] = {"enabled": enabled, "read_only": True}
    if not enabled:
        warn(L["acc_skip"])
        return

    # Multi-DB: collect database configs
    db_configs: list[dict] = []
    db_idx = 1

    while True:
        if db_idx > 1:
            print()
            info(f"📦 Database #{db_idx}")
        info(L["acc_warn"])
        host = ask(L["acc_host"], "192.168.1.10")
        while True:
            port_raw = ask(L["acc_port"], "1433")
            if port_raw.isdigit():
                port = int(port_raw)
                break
            fail("❌")
        db_name = ask(L["acc_db"], "OnyxDB")
        user = ask(L["acc_user"], "ai_agent_reader")
        password = ask(L["acc_pass"])

        # Use database name as the key (sanitized)
        db_key = db_name.lower().replace(" ", "_").replace("-", "_")
        display_name = ask("Display name (label)", db_name)

        with Spinner(f"Testing {host}:{port}"):
            reachable, info2 = test_tcp(host, port)
        if reachable:
            ok(f"{L['acc_server_ok']} at {host}:{port}")
        else:
            warn(f"{L['acc_server_fail']} ({info2})")

        db_url = (
            f"mssql+pyodbc://{user}:{password}@{host}:{port}/{db_name}"
            "?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes"
        )

        db_configs.append({
            "key": db_key,
            "name": display_name,
            "db_url": db_url,
        })
        ok(f"✅ {display_name} ({db_key})")

        # Store first DB URL in ACCOUNTING_DB_URL for backward compat
        if db_idx == 1:
            env["ACCOUNTING_DB_URL"] = db_url

        print()
        # Ask to add another
        if db_idx >= 1 and not ask_yes("Add another database? / هل تريد إضافة قاعدة بيانات أخرى؟", False):
            break
        db_idx += 1

    settings["accounting"]["allowed_queries"] = [
        "sales_summary", "revenue_by_month", "top_customers",
        "expenses_summary", "invoice_lookup", "cash_balance",
        "vendor_balances", "sales_by_item",
    ]

    # Save multi-DB config
    if db_configs:
        from connectors.accounting import SchemaConfig, _save_multi_db_config, DEFAULT_SCHEMA
        databases = {}
        for cfg in db_configs:
            databases[cfg["key"]] = SchemaConfig(
                version=1,
                name=cfg["name"],
                db_url=cfg["db_url"],
                enabled=True,
            )
        _save_multi_db_config(databases)
        ok(f"📝 Saved {len(db_configs)} database(s) to config/accounting_schema.json")

    # Schema discovery for each DB
    for cfg in db_configs:
        if ask_yes(f"🔄 Auto-discover schema for {cfg['name']}? / اكتشاف هيكل {cfg['name']}؟", True):
            with Spinner(f"Discovering schema for {cfg['name']}..."):
                try:
                    from connectors.accounting import discover_schema, _load_multi_db_config
                    discovered = discover_schema(cfg["db_url"])
                    discovered.name = cfg["name"]
                    discovered.db_url = cfg["db_url"]
                    dbs = _load_multi_db_config()
                    dbs[cfg["key"]] = discovered
                    _save_multi_db_config(dbs)
                    found = len(discovered.tables)
                    if found > 0:
                        ok(f"{cfg['name']}: تم اكتشاف {found} جدول")
                        for k, v in discovered.tables.items():
                            info(f"  {v['table']} → {k}")
                    else:
                        warn(f"{cfg['name']}: لم يتم العثور على جداول")
                except ImportError:
                    warn("SQLAlchemy غير مثبت - جارٍ استخدام التكوين الافتراضي")
                except Exception as e:
                    warn(f"فشل الاكتشاف: {e}")
        else:
            info(f"{cfg['name']}: تم استخدام التكوين الافتراضي (Onyx Pro)")

    ok(L["acc_ok"])


def step_permissions(env: dict, settings: dict) -> None:
    section(6, L["steps"][5])
    perms = {}
    perms["web_search"] = ask_yes(L["perm_web"], True)
    perms["calculator"] = ask_yes(L["perm_calc"], True)
    perms["get_current_time"] = ask_yes(L["perm_time"], True)
    perms["read_file"] = ask_yes(L["perm_file"], False)
    perms["search_conversations"] = ask_yes(L["perm_conversations"], True)
    perms["generate_report"] = ask_yes(L["perm_reports"], True)
    perms["list_reports"] = perms["generate_report"]
    accounting_on = settings.get("accounting", {}).get("enabled", False)
    if accounting_on:
        perms["accounting_tools"] = ask_yes(L["perm_accounting"], True)
    else:
        perms["accounting_tools"] = False
    perms["knowledge_rag"] = ask_yes(L["perm_knowledge"], True)
    settings["permissions"] = perms
    enabled = [k for k, v in perms.items() if v]
    ok(f"{L['perm_enabled']}: {', '.join(enabled)}")


def step_finish(env: dict, settings: dict) -> None:
    section(7, L["steps"][6])
    _write_files(env, settings)
    _print_summary(env, settings)
    if env.get("WHATSAPP_ENABLED") == "true":
        _link_whatsapp(env)
    else:
        warn("WhatsApp disabled — skipping.")


# ─── File output ──────────────────────────────────────────────────
def _write_files(env: dict, settings: dict) -> None:
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
        f"ADMIN_NUMBERS={env.get('ADMIN_NUMBERS', '')}",
        f"CHAT_MEMORY={env.get('CHAT_MEMORY', '20')}",
        f"REPORT_ENABLED={env.get('REPORT_ENABLED', 'false')}",
        f"REPORT_TIME={env.get('REPORT_TIME', '08:00')}",
        f"REPORT_TO={env.get('REPORT_TO', '')}",
        f"TELEGRAM_ENABLED={env.get('TELEGRAM_ENABLED', 'false')}",
        f"TELEGRAM_BOT_TOKEN={env.get('TELEGRAM_BOT_TOKEN', '')}",
        f"TELEGRAM_ALLOWED={env.get('TELEGRAM_ALLOWED', '')}",
    ]
    with open(ENV_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(env_lines) + "\n")
    os.makedirs(os.path.join(ROOT, "config"), exist_ok=True)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)
    ok("📝 .env")
    ok("📝 config/settings.json")


def _print_summary(env: dict, settings: dict) -> None:
    perms = ", ".join(k for k, v in settings.get("permissions", {}).items() if v) or "none"
    agent = settings.get("agent", {})
    w = 58
    print()
    print(color("  ╔" + "═" * w + "╗", "green"))
    print(box_line(color(f"  {L['summary_title']}", "bold", "green"), w - 4))
    print(color("  ╠" + "═" * w + "╣", "green"))
    print(box_line(f"  🤖  {L['model_ok']}:  {env.get('DEFAULT_MODEL', '')[:42]}", w - 4))
    print(box_line(f"  👤  {L['identity_ok']}: {agent.get('name', '')[:42]} ({agent.get('language', 'auto')})", w - 4))
    wa = "ON" if env.get("WHATSAPP_ENABLED") == "true" else "OFF"
    tg = "ON" if env.get("TELEGRAM_ENABLED") == "true" else "OFF"
    print(box_line(f"  📡  WhatsApp: {wa}  ·  Telegram: {tg}", w - 4))
    acc = "connected" if env.get("ACCOUNTING_DB_URL") else "not configured"
    print(box_line(f"  🏦  {L['steps'][4][:35]}: {acc}", w - 4))
    print(box_line(f"  🛠️   {L['perm_enabled']}: {perms[:42]}", w - 4))
    print(color("  ╠" + "═" * w + "╣", "green"))
    print(box_line(color(f"  {L['keys_warn']}", "yellow", "bold"), w - 4))
    print(box_line(f"  {L['admin']}: {color(env.get('ADMIN_KEY', ''), 'green', 'bold')}", w - 4))
    print(box_line(f"  {L['user']}:  {color(env.get('USER_KEY', ''), 'green', 'bold')}", w - 4))
    print(color("  ╠" + "═" * w + "╣", "green"))
    print(box_line(color(f"  {L['start_cmd']}", "yellow", "bold"), w - 4))
    print(box_line(f"  {color('python start.py', 'cyan', 'bold')}", w - 4))
    print(box_line(f"  {color('http://localhost:8000', 'cyan')}", w - 4))
    print(box_line(f"  {color('http://localhost:3001', 'cyan')}" + "  (WhatsApp QR)", w - 4))
    if env.get("DEFAULT_MODEL", "").startswith("ollama:"):
        model = env["DEFAULT_MODEL"].split(":", 1)[-1]
        print(box_line(color(f"  (first time: ollama pull {model})", "dim"), w - 4))
    print(color("  ╚" + "═" * w + "╝", "green"))
    print()


def _link_whatsapp(env: dict) -> None:
    if not ask_yes(L["link_wa_now"], True):
        warn(L["link_wa_skip"])
        return
    node = node_cmd()
    npm = npm_cmd()
    if not node or not npm:
        fail(L["link_wa_no_node"])
        info(L["node_hint"])
        return
    wa_dir = os.path.join(ROOT, "whatsapp")
    nm = os.path.join(wa_dir, "node_modules")
    pkg = os.path.join(wa_dir, "package.json")
    stale = (not os.path.isdir(nm)) or (
        os.path.exists(pkg) and os.path.getmtime(pkg) > os.path.getmtime(nm))
    if stale:
        with Spinner(L["npm_install"]):
            r = subprocess.run(f'"{npm}" install', cwd=wa_dir, shell=True,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if r.returncode != 0:
            fail(L["npm_fail"])
            return
        ok("npm install OK")
    print()
    info(L["link_start"])
    info(L["link_phone_hint"])
    info(L["link_wait"])
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
        "ADMIN_NUMBERS": env.get("ADMIN_NUMBERS", ""),
        "CHAT_MEMORY": env.get("CHAT_MEMORY", "20"),
        "REPORT_ENABLED": env.get("REPORT_ENABLED", "false"),
        "REPORT_TIME": env.get("REPORT_TIME", "08:00"),
        "REPORT_TO": env.get("REPORT_TO", ""),
        "WHATSAPP_ENABLED": "true",
    })
    proc = subprocess.Popen([node, "index.js"], cwd=wa_dir, env=wa_env)
    try:
        linked = False
        deadline = time.time() + 180  # 3-minute timeout for WhatsApp linking
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
            ok(L["link_ok"])
            # Ask for allowed numbers NOW (after QR scan)
            print()
            info(L["wa_allowed"])
            info(L["wa_allowed_example"])
            nums = ask(L["wa_allowed"], "")
            env["ALLOWED_NUMBERS"] = ",".join(_re.sub(r"\D", "", n) for n in nums.split(",") if n.strip())
            env["ADMIN_NUMBERS"] = env["ALLOWED_NUMBERS"]
            # Update .env with the new numbers
            _write_files(env, settings)
            ok("✅ تم حفظ الأرقام المسموحة")
        else:
            warn(L["link_timeout"])
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()


# ─── Entry point ──────────────────────────────────────────────────
def choose_language() -> None:
    """Ask user to choose language first."""
    global LANG, L
    import sys as _sys
    print()
    print("  ╔════════════════════════════════════════╗")
    print("  ║       Enterprise AI Agent Setup        ║")
    print("  ╚════════════════════════════════════════╝")
    print()
    print("  Choose your language / اختر لغتك:")
    print()
    print("    1)  العربية")
    print("    2)  English")
    print()
    while True:
        choice = input("  ▶  Choose [1]: ").strip()
        if not choice or choice == "1":
            LANG = "ar"
            break
        if choice == "2":
            LANG = "en"
            break
        print("  ✗ Invalid choice / اختيار غير صحيح")
    L = STR[LANG]
    _sys.stdout.write("\033[2J\033[H")  # clear screen
    _sys.stdout.flush()


def main() -> None:
    env: dict = {}
    settings: dict = {"version": 4}
    try:
        choose_language()
        banner()
        step_model(env, settings)
        step_identity(env, settings)
        step_security(env, settings)
        step_channels(env, settings)
        step_accounting(env, settings)
        step_permissions(env, settings)
        step_finish(env, settings)
    except KeyboardInterrupt:
        print()
        fail(L["aborted"])
        sys.exit(1)


if __name__ == "__main__":
    main()
