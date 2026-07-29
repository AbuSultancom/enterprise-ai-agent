#!/usr/bin/env python3
"""
Enterprise AI Agent - Unified Setup Wizard
===========================================
Single command setup with CLI and Web options.

Usage:
    python setup.py
    # Then choose: CLI or Web
"""

import os
import sys
import json
import time
import shutil
import locale
import secrets
import argparse
import threading
import subprocess
from pathlib import Path
from datetime import datetime

# ── Localization ──────────────────────────────────────────────────────────
STR = {
    "en": {
        "welcome": "\n╔══════════════════════════════════════════════════════════════╗\n║     Welcome to Enterprise AI Agent Setup Wizard v2.0         ║\n╚══════════════════════════════════════════════════════════════╝",
        "choose_mode": "\nChoose setup mode:",
        "mode_cli": "Command Line (Terminal)",
        "mode_web": "Web Browser (Recommended)",
        "web_launching": "\n🚀 Launching web setup server...",
        "web_open": "Open your browser and go to:",
        "web_url": "http://localhost:8000/setup",
        "web_stop": "\nPress Ctrl+C to stop the server",
        "step1": "\n[1/7] Language",
        "step2": "\n[2/7] LLM Configuration",
        "step3": "\n[3/7] Agent Identity",
        "step4": "\n[4/7] Security & Keys",
        "step5": "\n[5/7] Communication Channels",
        "step6": "\n[6/7] Accounting Integration",
        "step7": "\n[7/7] Permissions & Finalize",
        "done": "\n✅ Setup Complete!",
        "error": "❌ Error",
        "warning": "⚠️  Warning",
        "info": "ℹ️  Info",
        "retry": "Retry?",
        "skip": "Skip",
        "back": "Back",
        "next": "Next",
        "save": "Save",
        "cancel": "Cancel",
        "test_connection": "Testing connection...",
        "connection_ok": "Connection OK",
        "connection_fail": "Connection failed",
        "enter_value": "Enter value",
        "invalid_input": "Invalid input",
        "required": "Required",
        "optional": "Optional",
        "default": "Default",
        "progress": "Progress",
        "backup_created": "Backup created",
        "update_mode": "Update Mode - Current config loaded",
        "silent_mode": "Silent Mode - Using config file",
    },
    "ar": {
        "welcome": "\n╔══════════════════════════════════════════════════════════════╗\n║     مرحباً بك في معالج إعداد وكيل الذكاء الاصطناعي v2.0      ║\n╚══════════════════════════════════════════════════════════════╝",
        "choose_mode": "\nاختر وضع الإعداد:",
        "mode_cli": "سطر الأوامر (الترمنال)",
        "mode_web": "متصفح الويب (موصى به)",
        "web_launching": "\n🚀 تشغيل خادم إعداد الويب...",
        "web_open": "افتح المتصفح واذهب إلى:",
        "web_url": "http://localhost:8000/setup",
        "web_stop": "\nاضغط Ctrl+C لإيقاف الخادم",
        "step1": "\n[1/7] اللغة",
        "step2": "\n[2/7] إعداد نموذج اللغة الكبير (LLM)",
        "step3": "\n[3/7] هوية الوكيل",
        "step4": "\n[4/7] الأمان والمفاتيح",
        "step5": "\n[5/7] قنوات التواصل",
        "step6": "\n[6/7] ربط النظام المحاسبي",
        "step7": "\n[7/7] الصلاحيات والإنهاء",
        "done": "\n✅ اكتمل الإعداد!",
        "error": "❌ خطأ",
        "warning": "⚠️  تحذير",
        "info": "ℹ️  معلومة",
        "retry": "إعادة المحاولة؟",
        "skip": "تخطي",
        "back": "رجوع",
        "next": "التالي",
        "save": "حفظ",
        "cancel": "إلغاء",
        "test_connection": "جاري اختبار الاتصال...",
        "connection_ok": "الاتصال ناجح",
        "connection_fail": "فشل الاتصال",
        "enter_value": "أدخل القيمة",
        "invalid_input": "إدخال غير صالح",
        "required": "مطلوب",
        "optional": "اختياري",
        "default": "افتراضي",
        "progress": "التقدم",
        "backup_created": "تم إنشاء نسخة احتياطية",
        "update_mode": "وضع التحديث - تم تحميل الإعدادات الحالية",
        "silent_mode": "وضع الصمت - استخدام ملف الإعدادات",
    }
}

system_lang = locale.getdefaultlocale()[0]
if system_lang and system_lang.startswith("ar"):
    DEFAULT_LANG = "ar"
else:
    DEFAULT_LANG = "en"

L = STR[DEFAULT_LANG]

# ── UI Helpers ────────────────────────────────────────────────────────────

class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    END = "\033[0m"

def box(text, color=Colors.CYAN):
    lines = text.split("\n")
    width = max(len(line) for line in lines) + 4
    top = color + "╔" + "═" * (width - 2) + "╗" + Colors.END
    bottom = color + "╚" + "═" * (width - 2) + "╝" + Colors.END
    middle = []
    for line in lines:
        pad = width - len(line) - 4
        middle.append(color + "║ " + Colors.END + line + " " * pad + color + " ║" + Colors.END)
    return "\n".join([top] + middle + [bottom])

def ask(prompt, default=None, required=False, password=False):
    while True:
        display = prompt
        if default is not None:
            display += f" [{L['default']}: {default}]"
        display += ": "
        if password:
            import getpass
            value = getpass.getpass(display)
        else:
            value = input(display).strip()
        if not value:
            if default is not None:
                return default
            elif required:
                print(f"{Colors.RED}{L['required']}{Colors.END}")
                continue
            else:
                return None
        return value

def ask_yes(prompt, default=True):
    suffix = " [Y/n]" if default else " [y/N]"
    while True:
        resp = input(prompt + suffix + ": ").strip().lower()
        if not resp:
            return default
        if resp in ("y", "yes", "نعم"):
            return True
        if resp in ("n", "no", "لا"):
            return False
        print(f"{Colors.YELLOW}Please answer yes/no{Colors.END}")

def choose(options, prompt=None, default=0):
    if prompt:
        print(f"\n{Colors.CYAN}{prompt}{Colors.END}")
    for i, opt in enumerate(options, 1):
        marker = "→" if i - 1 == default else " "
        print(f"  {marker} [{i}] {opt}")
    while True:
        try:
            choice = input(f"\nSelect [1-{len(options)}]: ").strip()
            if not choice:
                return default
            idx = int(choice) - 1
            if 0 <= idx < len(options):
                return idx
        except ValueError:
            pass
        print(f"{Colors.RED}Invalid choice{Colors.END}")

def spinner(text, func, *args, **kwargs):
    import threading
    result = [None]
    done = [False]
    def run():
        result[0] = func(*args, **kwargs)
        done[0] = True
    t = threading.Thread(target=run)
    t.start()
    spin_chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
    i = 0
    while not done[0]:
        print(f"\r{Colors.CYAN}{spin_chars[i % len(spin_chars)]}{Colors.END} {text}", end="", flush=True)
        time.sleep(0.1)
        i += 1
    print(f"\r{' ' * (len(text) + 10)}", end="\r")
    t.join()
    return result[0]

# ── Config Manager ────────────────────────────────────────────────────────

class ConfigManager:
    def __init__(self, base_dir="."):
        self.base_dir = Path(base_dir)
        self.env_file = self.base_dir / ".env"
        self.settings_file = self.base_dir / "settings.json"
        self.backup_dir = self.base_dir / "backups"

    def load_current(self):
        config = {"env": {}, "settings": {}}
        if self.env_file.exists():
            with open(self.env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, val = line.split("=", 1)
                        config["env"][key.strip()] = val.strip().strip('"').strip("'")
        if self.settings_file.exists():
            with open(self.settings_file, "r", encoding="utf-8") as f:
                config["settings"] = json.load(f)
        return config

    def create_backup(self):
        self.backup_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.backup_dir / f"config_backup_{timestamp}"
        backup_path.mkdir(exist_ok=True)
        if self.env_file.exists():
            shutil.copy2(self.env_file, backup_path / ".env")
        if self.settings_file.exists():
            shutil.copy2(self.settings_file, backup_path / "settings.json")
        print(f"{Colors.GREEN}{L['backup_created']}: {backup_path}{Colors.END}")
        return backup_path

# ── CLI Wizard ────────────────────────────────────────────────────────────

class CLIWizard:
    def __init__(self, config_manager):
        self.config = config_manager
        self.current_config = self.config.load_current()
        self.env = {}
        self.settings = {}

    def run(self):
        print(L["welcome"])
        self.step_language()
        self.step_llm()
        self.step_identity()
        self.step_security()
        self.step_channels()
        self.step_accounting()
        self.step_permissions()
        self.finalize()

    def step_language(self):
        print(L["step1"])
        langs = ["English", "العربية (Arabic)"]
        idx = choose(langs, "Select your language / اختر لغتك:", default=0 if DEFAULT_LANG == "en" else 1)
        selected = "en" if idx == 0 else "ar"
        self.settings["language"] = selected
        # Update global L for this session
        import __main__
        __main__.L = STR[selected]
        print(f"{Colors.GREEN}✓ Language set to: {langs[idx]}{Colors.END}")

    def step_llm(self):
        print(L["step2"])
        providers = ["Ollama (Local)", "OpenAI", "Anthropic Claude", "Google Gemini", "Custom"]
        idx = choose(providers, "LLM Provider:")
        provider_map = ["ollama", "openai", "anthropic", "google", "custom"]
        provider = provider_map[idx]
        self.settings["llm_provider"] = provider

        models = {
            "ollama": ["qwen2.5:7b", "llama3.1:8b", "deepseek-r1:14b", "mistral:7b", "Other"],
            "openai": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "Other"],
            "anthropic": ["claude-3-5-sonnet", "claude-3-opus", "claude-3-haiku", "Other"],
            "google": ["gemini-1.5-pro", "gemini-1.5-flash", "Other"],
            "custom": ["Custom Model"]
        }
        model_idx = choose(models.get(provider, ["Custom"]), "Select Model:")
        model = models[provider][model_idx]
        if model == "Other":
            model = ask("Enter model name", required=True)
        self.settings["llm_model"] = model

        default_urls = {
            "ollama": "http://localhost:11434",
            "openai": "https://api.openai.com/v1",
            "anthropic": "https://api.anthropic.com/v1",
            "google": "https://generativelanguage.googleapis.com/v1",
            "custom": "http://localhost:8000"
        }
        url = ask("LLM API URL", default=default_urls.get(provider, ""), required=True)
        self.env["LLM_URL"] = url

        if provider != "ollama":
            key = ask("API Key", password=True)
            if key:
                self.env["LLM_API_KEY"] = key

        print(f"{Colors.GREEN}✓ LLM configured{Colors.END}")

    def step_identity(self):
        print(L["step3"])
        name = ask("Agent Name", default="EnterpriseBot", required=True)
        self.settings["agent_name"] = name
        desc = ask("Agent Description", default=f"AI assistant for {name}")
        if desc:
            self.settings["agent_description"] = desc
        print(f"{Colors.GREEN}✓ Identity set{Colors.END}")

    def step_security(self):
        print(L["step4"])
        if ask_yes("Generate new API keys?", default=True):
            self.env["API_KEY"] = secrets.token_urlsafe(32)
            self.env["JWT_SECRET"] = secrets.token_urlsafe(32)
            self.env["ENCRYPTION_KEY"] = secrets.token_urlsafe(32)
            print(f"{Colors.GREEN}✓ New keys generated{Colors.END}")

    def step_channels(self):
        print(L["step5"])
        channels = {}
        if ask_yes("Enable WhatsApp integration?", default=False):
            channels["whatsapp"] = {
                "enabled": True,
                "prefix": ask("Command prefix", default="!") or "!"
            }
        if ask_yes("Enable Telegram integration?", default=False):
            token = ask("Telegram Bot Token")
            if token:
                self.env["TELEGRAM_BOT_TOKEN"] = token
                channels["telegram"] = {"enabled": True}
        if ask_yes("Enable Web Dashboard?", default=True):
            channels["web"] = {"enabled": True, "port": 8000}
        self.settings["channels"] = channels
        print(f"{Colors.GREEN}✓ Channels configured{Colors.END}")

    def step_accounting(self):
        print(L["step6"])
        if not ask_yes("Enable accounting integration?", default=False):
            self.settings["accounting"] = {"enabled": False}
            return
        self.settings["accounting"] = {"enabled": True, "databases": []}
        print(f"{Colors.GREEN}✓ Accounting configured{Colors.END}")

    def step_permissions(self):
        print(L["step7"])
        self.settings["permissions"] = {
            "web_search": ask_yes("Allow web search?", default=True),
            "file_access": ask_yes("Allow file system access?", default=False),
            "accounting_tools": ask_yes("Allow accounting operations?", default=True),
            "code_execution": ask_yes("Allow code execution?", default=False),
        }
        print(f"{Colors.GREEN}✓ Permissions set{Colors.END}")

    def finalize(self):
        print(f"\n{L['done']}")
        self.config.create_backup()

        with open(self.config.env_file, "w", encoding="utf-8") as f:
            f.write(f"# Enterprise AI Agent - Environment Variables\n")
            f.write(f"# Generated: {datetime.now().isoformat()}\n\n")
            for key, val in sorted(self.env.items()):
                f.write(f'{key}="{val}"\n')

        with open(self.config.settings_file, "w", encoding="utf-8") as f:
            json.dump(self.settings, f, indent=2, ensure_ascii=False)

        print(f"\n{Colors.GREEN}Configuration saved!{Colors.END}")
        print(f"  {Colors.CYAN}•{Colors.END} .env")
        print(f"  {Colors.CYAN}•{Colors.END} settings.json")
        print(f"\n{Colors.BOLD}Next steps:{Colors.END}")
        print("  1. Review .env and settings.json")
        print("  2. Run: python start.py")
        print("  3. Open: http://localhost:8000")

# ── Web Launcher ──────────────────────────────────────────────────────────

def launch_web_setup():
    """Launch the web-based setup server."""
    print(L["web_launching"])
    print(f"\n  {Colors.CYAN}{L['web_open']}{Colors.END}")
    print(f"  {Colors.BOLD}{Colors.GREEN}{L['web_url']}{Colors.END}")
    print(L["web_stop"])

    # Try to open browser automatically
    try:
        import webbrowser
        webbrowser.open(L["web_url"])
    except Exception:
        pass

    # Start uvicorn server
    try:
        subprocess.run([
            sys.executable, "-m", "uvicorn", "setup_web:app",
            "--host", "0.0.0.0", "--port", "8000",
            "--reload"
        ])
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Server stopped.{Colors.END}")

# ── Mode Selector ─────────────────────────────────────────────────────────

def select_mode():
    """Show mode selector and return choice."""
    print(L["welcome"])
    print(L["choose_mode"])

    modes = [L["mode_cli"], L["mode_web"]]
    idx = choose(modes, default=1)  # Default to Web (recommended)
    return idx

# ── Main ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Enterprise AI Agent Setup")
    parser.add_argument("--cli", action="store_true", help="Force CLI mode")
    parser.add_argument("--web", action="store_true", help="Force Web mode")
    parser.add_argument("--update", action="store_true", help="Update existing config")
    parser.add_argument("--config", type=str, help="Config file for silent mode")
    parser.add_argument("--yes", "-y", action="store_true", help="Auto-confirm")

    args = parser.parse_args()

    config = ConfigManager()

    # Handle silent mode
    if args.config and args.yes:
        print(f"{Colors.CYAN}{L['silent_mode']}{Colors.END}")
        # ... silent mode implementation
        return

    # Determine mode
    if args.cli:
        mode = 0  # CLI
    elif args.web:
        mode = 1  # Web
    else:
        mode = select_mode()

    # Execute chosen mode
    if mode == 0:
        # CLI Mode
        try:
            wizard = CLIWizard(config)
            wizard.run()
        except KeyboardInterrupt:
            print(f"\n\n{Colors.YELLOW}Setup cancelled.{Colors.END}")
            sys.exit(1)
    else:
        # Web Mode
        launch_web_setup()

if __name__ == "__main__":
    main()
