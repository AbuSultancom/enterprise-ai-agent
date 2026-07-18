#!/usr/bin/env python3
"""
Enterprise AI Agent — Onboarding Wizard (v5)
============================================
Premium Dashboard-style setup experience.
Bilingual Arabic/English support.
Run:  python setup.py

Developer: @Abdulhameed · github.com/AbuSultancom
"""
from __future__ import annotations

import json, os, re, secrets, shutil, socket, subprocess, sys, time, urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = os.path.join(ROOT, ".env")
SETTINGS_FILE = os.path.join(ROOT, "config", "settings.json")
TOTAL_STEPS = 7

# ─── Colors ───
R = "\033[0m"
B = "\033[1m"
D = "\033[2m"
K = {"r": "\033[91m", "g": "\033[92m", "y": "\033[93m", "b": "\033[94m", "m": "\033[95m", "c": "\033[96m"}


def c(t, *k): return "".join(K.get(x, "") for x in k) + t + R if k else t


def clr(): sys.stdout.write("\033[2J\033[H"); sys.stdout.flush()


def ask(p, d=""):
    pr = f"  {p}" + (f" [{d}]" if d else "")
    v = input(f"{pr}: ").strip()
    return v if v else d


def yn(p, d=True):
    return ask(p, "Y" if d else "N").lower()[:1] in ("y", "ن")


def ch(p, opts, d=0):
    print(f"  {p}")
    for i, o in enumerate(opts): print(f"    {c('→','g') if i == d else ' '} {i+1}) {o}")
    try: return int(ask("  ▶ " + "اختر / Choose", str(d + 1))) - 1
    except: return d


# ─── Bilingual ───
LANG = "ar"
STR = {
    "ar": {
        "dev": "AbuSultancom",
        "lang_choose": "اختر لغتك / Choose language",
        "go": "اضغط Enter للبدء",
        "skip_q": "تخطي هذه الخطوة؟",
        "done": "✅ تم",
    },
    "en": {
        "dev": "AbuSultancom",
        "lang_choose": "Choose your language / اختر لغتك",
        "go": "Press Enter to begin",
        "skip_q": "Skip this step?",
        "done": "✅ Done",
    },
}
L = STR[LANG]


def t(k): return L.get(k, k)


# ─── UI ───
def hr(w=62): print(c("  " + "─" * w, "c", D))


def box_hdr(title, w=62):
    tl = f"  {title}"
    print(c(f"  ┌{'─'*w}┐", "c"))
    print(c(f"  │{tl:<{w}}│", B, "c"))
    print(c(f"  ├{'─'*w}┤", "c"))


def box_row(line, w=62):
    print(c(f"  │  {line}" + " " * (w - len(line) - 2) + "│", D))


def box_end(w=62): print(c(f"  └{'─'*w}┘", "c"))


def step_header(n):
    clr()
    print()
    print(c("  Enterprise AI Agent", B, "c"))
    print(c(f"  ─{t('dev'):─^36}─", D))
    print(c("  github.com/AbuSultancom  " + c("v0.5", D), D))
    hr()
    bar = c("█" * n + "░" * (TOTAL_STEPS - n), "g" if n > 3 else "y")
    print(f"  {bar}  {c(str(n*100//TOTAL_STEPS)+'%', B)}  {c(f'[{n}/{TOTAL_STEPS}]', D)}")
    hr()
    print()


def ok(s): print(c(f"  ✅ {s}", "g"))


def warn(s): print(c(f"  ⚠ {s}", "y"))


def info(s): print(c(f"  ℹ  {s}", D))


# ─── Spinner ───
class Spinner:
    _f = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

    def __init__(self, msg): self.m = msg; self.s = False

    def __enter__(self):
        import threading
        self._t = threading.Thread(target=self._r, daemon=True); self._t.start()
        return self

    def __exit__(self, *a):
        self.s = True
        if self._t: self._t.join(0.3)
        sys.stdout.write("\r" + " " * 60 + "\r"); sys.stdout.flush()

    def _r(self):
        i = 0
        while not self.s:
            sys.stdout.write(f"\r    {self._f[i]} {self.m}... "); sys.stdout.flush()
            i = (i + 1) % len(self._f); time.sleep(0.1)


def test_tcp(host, port, t=3):
    try:
        s = socket.create_connection((host, port), t); s.close(); return True, ""
    except Exception as e:
        return False, str(e)


# ═══════════════════════════════════════════════════════════════════
# LANGUAGE SELECTION
# ═══════════════════════════════════════════════════════════════════
def choose_language():
    global LANG, L
    print(c("  Enterprise AI Agent", B, "c"))
    print(c("  ── by AbuSultancom ──", D))
    print()
    print("  1)  العربية")
    print("  2)  English")
    print()
    v = input("  ▶  اختر / Choose [1]: ").strip()
    if v == "2": LANG = "en"
    else: LANG = "ar"
    L = STR[LANG]
    clr()


# ═══════════════════════════════════════════════════════════════════
# STEP 1 — MODEL PROVIDER
# ═══════════════════════════════════════════════════════════════════
def step_model(env, st):
    step_header(1)
    box_hdr("📍 مزود الذكاء / AI Provider")
    box_row("")
    box_row(c("اختر المزود الذي سيشغل الوكيل:", B))
    box_row("")
    box_end()

    print()
    m = ch("أي مزود تريد؟ / Which provider?", [
        "Ollama — محلي، مجاني، خصوصي / Local, free, private",
        "DeepSeek — سحاب، رخيص وقوي / Cloud, cheap & powerful",
        "OpenAI — سحاب (GPT-4o) / Cloud",
        "مخصص — أي رابط متوافق مع OpenAI / Custom endpoint",
    ], 0)

    if m == 0:
        env["DEFAULT_MODEL"] = f"ollama:{ask('اسم الموديل / Model name', 'llama3')}"
        env["OLLAMA_BASE_URL"] = ask("رابط Ollama / URL", "http://localhost:11434/v1")
    elif m == 1:
        env["DEFAULT_MODEL"] = f"openai:{ask('اسم الموديل / Model', 'deepseek-chat')}"
        env["OPENAI_API_KEY"] = ask("مفتاح API / API Key", "")
        env["OPENAI_BASE_URL"] = "https://api.deepseek.com/v1"
    elif m == 2:
        env["DEFAULT_MODEL"] = f"openai:{ask('اسم الموديل / Model', 'gpt-4o')}"
        env["OPENAI_API_KEY"] = ask("مفتاح API / API Key", "")
        env["OPENAI_BASE_URL"] = ask("رابط API / URL", "https://api.openai.com/v1")
    else:
        name = ask("اسم المزود / Provider name", "custom")
        env["DEFAULT_MODEL"] = f"openai:{ask('اسم الموديل / Model', 'gpt-4o')}"
        env["OPENAI_API_KEY"] = ask("مفتاح API / API Key", "")
        env["OPENAI_BASE_URL"] = ask("رابط API الأساسي / Base URL", "")

    ok(f"تم: {env['DEFAULT_MODEL']}")

    # Test API key
    if env.get("OPENAI_API_KEY"):
        with Spinner("اختبار المفتاح / Testing API key"):
            try:
                req = urllib.request.Request(
                    f"{env.get('OPENAI_BASE_URL', 'https://api.deepseek.com/v1')}/models",
                    headers={"Authorization": f"Bearer {env['OPENAI_API_KEY']}"})
                with urllib.request.urlopen(req, timeout=5) as r:
                    ok("API key يعمل / works ✅")
            except:
                warn("تعذر التحقق — تم الحفظ / Saved anyway")


# ═══════════════════════════════════════════════════════════════════
# STEP 2 — AGENT IDENTITY
# ═══════════════════════════════════════════════════════════════════
def step_identity(env, st):
    step_header(2)
    box_hdr("👤 هوية الوكيل / Agent Identity")
    box_end()
    print()
    st.setdefault("agent", {})
    st["agent"]["name"] = ask("اسم الوكيل / Agent name", "المساعد الذكي")
    lang = ch("لغة الردود / Response language", [
        "نفس لغة المستخدم — تلقائي / Auto",
        "العربية — يرد بالعربية دائماً / Always Arabic",
        "English — always English",
    ], 0)
    st["agent"]["language"] = ["auto", "ar", "en"][lang]
    st["agent"]["personality"] = ask("الشخصية / Personality", "مساعد مؤسسي محترف ومختصر")
    ok(f"تم: {st['agent']['name']}")


# ═══════════════════════════════════════════════════════════════════
# STEP 3 — SECURITY
# ═══════════════════════════════════════════════════════════════════
def step_security(env, st):
    step_header(3)
    box_hdr("🔒 الأمان / Security")
    box_end()
    print()
    env["ADMIN_KEY"] = secrets.token_hex(16)
    env["USER_KEY"] = secrets.token_hex(16)
    ok("تم إنشاء مفاتيح API")
    print(f"  مشرف / Admin: {c(env['ADMIN_KEY'], 'g', B)}")
    print(f"  مستخدم / User:  {c(env['USER_KEY'], 'g', B)}")
    print(c("  ⚠ احفظها — لن تظهر مرة أخرى!", "y", B))
    input(c("\n  ▶ اضغط Enter للمتابعة", D))


# ═══════════════════════════════════════════════════════════════════
# STEP 4 — CHANNELS
# ═══════════════════════════════════════════════════════════════════
def step_channels(env, st):
    step_header(4)
    st["channels"] = {}

    box_hdr("📱 واتساب / WhatsApp")
    box_end()
    print()
    if yn("تفعيل واتساب؟ / Enable WhatsApp?", True):
        env["WHATSAPP_ENABLED"] = "true"
        env["BOT_PREFIX"] = ask("بادئة الرسائل (فارغ = الكل) / Prefix (empty=all)", "")
        env["IGNORE_GROUPS"] = "true" if yn("تجاهل المجموعات؟ / Ignore groups?", True) else "false"
        r = ch("صلاحية مستخدمي واتساب؟ / WhatsApp role?", [
            "user — محادثة وأدوات آمنة / Chat + safe tools",
            "admin — صلاحية كاملة / Full access",
        ], 0)
        env["WHATSAPP_ROLE"] = "user" if r == 0 else "admin"
        st["channels"]["whatsapp"] = {"role": env["WHATSAPP_ROLE"]}
        ok(f"واتساب: مفعل — بادئة '{env['BOT_PREFIX'] or '(بدون)'}'")
    else:
        env["WHATSAPP_ENABLED"] = "false"
        st["channels"]["whatsapp"] = {"enabled": False}
        warn("واتساب: معطل")

    print()
    box_hdr("💬 تلغرام / Telegram")
    box_end()
    print()
    if yn("تفعيل تلغرام؟ / Enable Telegram?", False):
        env["TELEGRAM_ENABLED"] = "true"
        env["TELEGRAM_BOT_TOKEN"] = ask("Token البوت / Bot Token", "")
        st["channels"]["telegram"] = {"enabled": True}
        ok("تلغرام: مفعل")
    else:
        env["TELEGRAM_ENABLED"] = "false"
        st["channels"]["telegram"] = {"enabled": False}


# ═══════════════════════════════════════════════════════════════════
# STEP 5 — DATABASE (⭐ THE STAR)
# ═══════════════════════════════════════════════════════════════════
def step_accounting(env, st):
    step_header(5)

    # Help guide
    box_hdr("📘 دليل ربط قواعد البيانات / Database Guide", 64)
    box_row(c("🟦 SQL Server  — أونكس برو، Microsoft ERP", "c"), 64)
    box_row("   تجد البيانات في: SSMS > Server Properties", 64)
    box_row(c("🟥 Oracle      — Toad, SQL Developer", "r"), 64)
    box_row("   Toad > Session > New Connection > Direct", 64)
    box_row("   أو ملف: C:\\app\\oracle\\...\\Network\\Admin\\tnsnames.ora", 64)
    box_row(c("🟩 MySQL       — تطبيقات ويب، CMS", "g"), 64)
    box_row("   إعدادات التطبيق أو ملف .env", 64)
    box_row(c("🟨 PostgreSQL  — تطبيقات حديثة", "y"), 64)
    box_row("   إعدادات التطبيق أو ملف .env", 64)
    box_row(c("⬜ رابط مباشر  — أي قاعدة SQLAlchemy", D), 64)
    box_end(64)
    print()

    st.setdefault("accounting", {"enabled": False, "read_only": True})

    if not yn("تفعيل ربط قاعدة البيانات؟ / Enable database connection?", True):
        warn("تم التخطي — أضف لاحقاً من الوكيل: أضف قاعدة بيانات")
        return

    st["accounting"]["enabled"] = True
    dbs = []
    n = 1

    while True:
        print()
        hr()
        print(c(f"  📦 قاعدة بيانات #{n} / Database #{n}", B))
        hr()
        print()

        tpe = ch("نوع القاعدة / Database type:", [
            "🟦 SQL Server — MSSQL",
            "🟥 Oracle — Oracle DB",
            "🟩 MySQL",
            "🟨 PostgreSQL",
            "⬜ رابط مباشر / Direct URL",
        ], 0)

        if tpe == 4:  # Direct URL
            url = ask("Connection string")
            key = ask("مفتاح مختصر (إنجليزي) / Key", f"db{n}")
            name = ask("اسم العرض / Display name", f"Database {n}")
        else:
            host = ask("Host / الخادم", "localhost")
            ports = ["1433", "1521", "3306", "5432"]
            port = ask("Port / المنفذ", ports[tpe])
            user = ask("User / المستخدم", "")
            pwd = ask("Password / كلمة المرور", "")

            with Spinner(f"اختبار {host}:{port}"):
                ok_, err = test_tcp(host, int(port))
            if ok_: ok("الخادم متصل ✅")
            else: warn(f"تعذر الوصول: {err}")

            if tpe == 0:  # SQL Server
                db = ask("Database name", "")
                url = f"mssql+pyodbc://{user}:{pwd}@{host}:{port}/{db}?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes"
                key = db.lower().replace(" ", "_") if db else f"db{n}"
                name = ask("اسم العرض / Display name", db or f"DB {n}")

            elif tpe == 1:  # Oracle ⭐
                svc = ask("🔧 Service Name (مثلاً ORCL, XE)", "ORCL")
                url = f"oracle+oracledb://{user}:{pwd}@{host}:{port}/?service_name={svc}"
                key = svc.lower()
                name = ask("اسم العرض / Display name", f"Oracle {svc}")

            elif tpe == 2:  # MySQL
                db = ask("Database name", "")
                url = f"mysql+pymysql://{user}:{pwd}@{host}:{port}/{db}"
                key = db.lower().replace(" ", "_") if db else f"db{n}"
                name = ask("اسم العرض / Display name", db or f"DB {n}")

            else:  # PostgreSQL
                db = ask("Database name", "")
                url = f"postgresql://{user}:{pwd}@{host}:{port}/{db}"
                key = db.lower().replace(" ", "_") if db else f"db{n}"
                name = ask("اسم العرض / Display name", db or f"DB {n}")

        dbs.append({"key": key, "name": name, "db_url": url, "enabled": True, "tables": {}})
        ok(f"تمت إضافة: {name} ✅")
        print()

        if not yn("➕ إضافة قاعدة أخرى؟ / Add another?", False):
            break
        n += 1

    # Save
    cfg = {"version": 2, "databases": {}}
    for d in dbs:
        cfg["databases"][d["key"]] = {"name": d["name"], "db_url": d["db_url"],
                                       "enabled": d["enabled"], "tables": d["tables"]}
    os.makedirs(os.path.join(ROOT, "config"), exist_ok=True)
    with open(os.path.join(ROOT, "config", "accounting_schema.json"), "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    if dbs:
        env["ACCOUNTING_DB_URL"] = dbs[0]["db_url"]
    ok(f"تم حفظ {len(dbs)} قاعدة بيانات")


# ═══════════════════════════════════════════════════════════════════
# STEP 6 — PERMISSIONS
# ═══════════════════════════════════════════════════════════════════
def step_permissions(env, st):
    step_header(6)
    box_hdr("🛠️ صلاحيات الأدوات / Tool Permissions")
    box_row("")
    box_row(c("اختر الأدوات المسموح للوكيل استخدامها:", B))
    box_row("")
    box_end()
    print()
    st["permissions"] = {}
    tools_list = [
        ("web_search", "بحث ويب / Web search"),
        ("get_weather", "الطقس / Weather"),
        ("get_currency_rate", "أسعار العملات / Currency rates"),
        ("calculator", "آلة حاسبة / Calculator"),
        ("read_image", "قراءة الصور / Vision"),
        ("generate_report", "إنشاء تقارير / Reports"),
        ("tasi_stocks", "أسهم سعودية / Saudi stocks"),
        ("vat_calc", "الضريبة / VAT"),
        ("zakat_calc", "الزكاة / Zakat"),
        ("search_employee_tool", "دليل الموظفين / Employee directory"),
        ("compare_branches", "مقارنة الفروع / Branches"),
    ]
    for key, desc in tools_list:
        st["permissions"][key] = yn(f"  تفعيل: {desc}?", True)

    # Accounting tools
    ac = yn("تفعيل أدوات المحاسبة كلها؟ / Enable all accounting tools?", True)
    for t in ["diagnose_connection", "discover_schema_tool", "show_schema_config",
              "get_vendor_balances", "get_sales_by_item"]:
        st["permissions"][t] = ac
    ok("تم حفظ الصلاحيات")


# ═══════════════════════════════════════════════════════════════════
# STEP 7 — FINISH
# ═══════════════════════════════════════════════════════════════════
def step_finish(env, st):
    step_header(7)

    # Write .env
    lines = [
        f"DEFAULT_MODEL={env.get('DEFAULT_MODEL', '')}",
        f"OPENAI_API_KEY={env.get('OPENAI_API_KEY', '')}",
        f"OPENAI_BASE_URL={env.get('OPENAI_BASE_URL', '')}",
        f"OLLAMA_BASE_URL={env.get('OLLAMA_BASE_URL', '')}",
        f"WHATSAPP_ENABLED={env.get('WHATSAPP_ENABLED', 'false')}",
        f"BOT_PREFIX={env.get('BOT_PREFIX', '')}",
        f"IGNORE_GROUPS={env.get('IGNORE_GROUPS', 'true')}",
        f"WHATSAPP_ROLE={env.get('WHATSAPP_ROLE', 'user')}",
        f"TELEGRAM_ENABLED={env.get('TELEGRAM_ENABLED', 'false')}",
        f"TELEGRAM_BOT_TOKEN={env.get('TELEGRAM_BOT_TOKEN', '')}",
        f"ADMIN_KEY={env.get('ADMIN_KEY', '')}",
        f"USER_KEY={env.get('USER_KEY', '')}",
        f"ACCOUNTING_DB_URL={env.get('ACCOUNTING_DB_URL', '')}",
    ]
    with open(ENV_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    # Write settings.json
    os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=2)

    ok("تم حفظ الإعدادات ✅")

    # Summary
    print()
    box_hdr("📋 ملخص الإعدادات / Summary", 62)
    box_row(f"🤖 الموديل: {env.get('DEFAULT_MODEL', '?')}", 62)
    box_row(f"👤 الوكيل: {st.get('agent',{}).get('name','?')} ({st.get('agent',{}).get('language','auto')})", 62)
    box_row(f"📱 واتساب: {'✅' if env.get('WHATSAPP_ENABLED')=='true' else '❌'}", 62)
    box_row(f"💬 تلغرام: {'✅' if env.get('TELEGRAM_ENABLED')=='true' else '❌'}", 62)
    box_row(f"🏦 المحاسبة: {'✅' if env.get('ACCOUNTING_DB_URL') else '❌'}", 62)
    box_row("", 62)
    box_row(c(f"🔑 ADMIN_KEY: {env.get('ADMIN_KEY', '')}", "g", B), 62)
    box_row(c(f"🔑 USER_KEY:  {env.get('USER_KEY', '')}", "g", B), 62)
    box_row(c("⚠️ احفظ هذه المفاتيح!", "y"), 62)
    box_end(62)
    print()
    print(c("  🚀 للتشغيل:", "g", B))
    print(c("     python start.py", "c", B))
    print(c("     http://localhost:8000", "c"))
    print()


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════
def main():
    choose_language()
    env = {}
    st = {"version": 5}
    step_model(env, st)
    step_identity(env, st)
    step_security(env, st)
    step_channels(env, st)
    step_accounting(env, st)
    step_permissions(env, st)
    step_finish(env, st)


if __name__ == "__main__":
    main()
