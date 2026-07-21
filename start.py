#!/usr/bin/env python3
"""
Enterprise AI Agent — One-Command Launcher (Enhanced Terminal UX)
=================================================================
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

import sys
# Configure console output to support UTF-8 on Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import argparse
import itertools
import os
import random
import shutil
import signal
import subprocess
import threading
import time
import webbrowser

ROOT = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = os.path.join(ROOT, ".env")
VERSION = "0.5.0"

# ── Color palette ──
PALETTE = {
    "g": "\033[92m", "y": "\033[93m", "b": "\033[94m",
    "c": "\033[96m", "r": "\033[91m", "m": "\033[95m",
    "w": "\033[97m", "bold": "\033[1m", "dim": "\033[2m",
    "reset": "\033[0m",
}

# ── Spinner frames ──
SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
CHECK_MARK = "✅"
CROSS_MARK = "❌"
WARN_MARK = "⚠️"


def c(text: str, *colors: str) -> str:
    if not colors:
        return text
    return "".join(PALETTE.get(x, "") for x in colors) + text + PALETTE["reset"]


# ── Spinner class ──
class Spinner:
    """Animated spinner that runs in a background thread."""

    def __init__(self, message: str = "", color: str = "c"):
        self.message = message
        self.color = color
        self.frames = SPINNER_FRAMES
        self._running = False
        self._thread = None

    def _spin(self):
        for frame in itertools.cycle(self.frames):
            if not self._running:
                break
            sys.stdout.write(f"\r  {c(frame, self.color, 'bold')}  {c(self.message, 'dim')}")
            sys.stdout.flush()
            time.sleep(0.08)

    def start(self, message: str = ""):
        if message:
            self.message = message
        self._running = True
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=0.5)
        # Clear the line
        sys.stdout.write("\r" + " " * 80 + "\r")
        sys.stdout.flush()


_spinner = Spinner()


def spin(msg: str, color: str = "c") -> Spinner:
    """Start spinner with message. Returns spinner for chaining."""
    _spinner.start(msg)
    return _spinner


def stop_spin() -> None:
    _spinner.stop()


# ── ASCII art tips ──
TIPS = [
    "💡 Tip: Use --dev to run in development mode with auto-reload",
    "💡 Tip: Press Ctrl+C to gracefully stop all services",
    "💡 Tip: Use --port=8080 to change the API port",
    "💡 Tip: Add --no-browser to skip opening the dashboard",
    "💡 Tip: The dashboard auto-refreshes every 30 seconds",
    "💡 Tip: You can switch languages in the dashboard with the EN/ع button",
    "💡 Tip: You can upload PDF and Word documents to search in the Knowledge panel",
    "💡 Tip: Type /help in the dashboard for available keyboard shortcuts",
    "💡 Tip: The API supports streaming responses for faster replies",
    "💡 Tip: The health endpoint at /health shows system status",
    "💡 Tip: You can pin important conversations to the top of the sidebar",
    "💡 Tip: Dark mode is automatic — toggle between dark, light, and system",
    "💡 Tip: Use Enter to send, Shift+Enter for new line in chat",
    "💡 Tip: All API keys are securely stored in .env and will not be displayed again",
]


def show_tip() -> None:
    tip = random.choice(TIPS)
    print(f"\n  {c(tip, 'dim')}\n")


# ── Banner ──
def banner() -> None:
    # Gradient top border
    print(c("""
  ╔═══════════════════════════════════════════════════════╗
  ║     ███████╗███╗   ██╗████████╗███████╗██████╗       ║
  ║     ██╔════╝████╗  ██║╚══██╔══╝██╔════╝██╔══██╗      ║
  ║     █████╗  ██╔██╗ ██║   ██║   █████╗  ██████╔╝      ║
  ║     ██╔══╝  ██║╚██╗██║   ██║   ██╔══╝  ██╔══██╗      ║
  ║     ███████╗██║ ╚████║   ██║   ███████╗██║  ██║      ║
  ║     ╚══════╝╚═╝  ╚═══╝   ╚═╝   ╚══════╝╚═╝  ╚═╝      ║
  ║                                                       ║
  ║           █████╗ ██╗     █████╗  ██████╗ ███████╗███╗ ██╗████████╗  ║
  ║          ██╔══██╗██║    ██╔══██╗██╔════╝ ██╔════╝████╗ ██║╚══██╔══╝  ║
  ║          ███████║██║    ███████║██║  ███╗█████╗  ██╔██╗██║   ██║     ║
  ║          ██╔══██║██║    ██╔══██║██║   ██║██╔══╝  ██║╚████║   ██║     ║
  ║          ██║  ██║██║    ██║  ██║╚██████╔╝███████╗██║ ╚███║   ██║     ║
  ║          ╚═╝  ╚═╝╚═╝    ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚══╝   ╚═╝     ║
  ╚═══════════════════════════════════════════════════════╝
""", "c", "bold"))
    print(c(f"              🚀  Enterprise AI Agent Platform  🚀", "bold"))
    print(c(f"                     v{VERSION}  ·  Ready", "dim"))
    print()


# ── Step / status helpers ──
def phase(title: str, emoji: str = "🔹", color: str = "c") -> None:
    print()
    print(c(f"  {emoji}  ═══  {title}  ═══", color, "bold"))
    print()


def ok(msg: str) -> None:
    print(f"  {c(CHECK_MARK, 'g', 'bold')} {c(msg, 'g')}")


def warn(msg: str) -> None:
    print(f"  {c(WARN_MARK, 'y', 'bold')} {c(msg, 'y')}")


def fail(msg: str) -> None:
    print(f"  {c(CROSS_MARK, 'r', 'bold')} {c(msg, 'r')}")


def info(msg: str) -> None:
    print(f"  {c('·', 'c')} {c(msg, 'dim')}")


# ── Progress dots ──
def progress_dots(steps: int, current: int, done: bool = False) -> str:
    """Build a progress bar like [⠶⠶○○○]"""
    filled = "⠶" * min(current, steps)
    empty = "○" * (steps - min(current, steps))
    marker = "✓" if done else ""
    return c(f"[{filled}{empty}]{marker}", "c")


# ── System checks table ──
def system_checks_table(checks: list[tuple[str, bool, str]]) -> None:
    """Print a formatted system checks table.
    checks: list of (label, pass, detail) tuples
    """
    BOX_TOP = "╔══════════════════════════════════════════╗"
    BOX_MID = "╠══════════════════════════════════════════╣"
    BOX_BOT = "╚══════════════════════════════════════════╝"

    print()
    print(c(f"  {BOX_TOP}", "c"))
    print(c(f'  ║  {"🔍  SYSTEM CHECKS":<37}  ║', "c", "bold"))
    print(c(f"  {BOX_MID}", "c"))
    for label, passed, detail in checks:
        icon = CHECK_MARK if passed else (WARN_MARK if detail else CROSS_MARK)
        color_key = "g" if passed else ("y" if detail else "r")
        line = f"  ║  {label:<25}  {icon}  {detail:<7}  ║"
        print(c(line, color_key))
    print(c(f"  {BOX_BOT}", "c"))
    print()


# ── Parsing ──
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


# ── Checks ──
def check_python() -> tuple[bool, str]:
    ver = f"{sys.version_info[0]}.{sys.version_info[1]}"
    if sys.version_info < (3, 11):
        fail(f"Python ≥ 3.11 required (you have {ver})")
        return False, ver
    return True, ver


def check_venv() -> tuple[bool, str]:
    in_venv = (hasattr(sys, "real_prefix") or
               (hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix))
    if not in_venv:
        warn("Virtual environment not active — recommended: python -m venv venv && source venv/bin/activate")
        return False, "inactive"
    return True, "active"


def check_deps(auto_install: bool = True) -> tuple[bool, str]:
    missing = []
    for pkg in ["fastapi", "uvicorn", "httpx", "pydantic"]:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    if missing:
        if auto_install:
            phase("Installing dependencies", "📦", "y")
            info(f"Missing: {', '.join(missing)}")
            try:
                subprocess.check_call(
                    [sys.executable, "-m", "pip", "install", "-r",
                     os.path.join(ROOT, "requirements.txt")],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                ok("Dependencies installed")
                return True, "installed"
            except Exception:
                fail("Failed to install dependencies")
                return False, "failed"
        else:
            return False, "missing"
    return True, "ok"


def check_internet() -> tuple[bool, str]:
    """Quick internet connectivity check."""
    import urllib.request as _urllib
    try:
        _urllib.urlopen("https://www.google.com", timeout=3)
        return True, "connected"
    except Exception:
        return False, "offline"


def check_node() -> tuple[bool, str]:
    node = shutil.which("node") or shutil.which("node.exe")
    if node:
        return True, node
    return False, "not found"


def check_npm() -> tuple[bool, str]:
    for name in ("npm", "npm.cmd", "npm.exe"):
        path = shutil.which(name)
        if path:
            return True, path
    return False, "not found"


# ── Tool counting ──
def count_tools() -> int:
    """Count available tools by inspecting the tools directory."""
    tools_dir = os.path.join(ROOT, "tools")
    if not os.path.isdir(tools_dir):
        return 0
    count = 0
    for fname in os.listdir(tools_dir):
        if fname.endswith(".py") and not fname.startswith("_"):
            # Quick scan for tool registrations
            fpath = os.path.join(tools_dir, fname)
            try:
                with open(fpath, encoding="utf-8") as f:
                    content = f.read()
                    if "tool_schema" in content or "def execute" in content:
                        count += 1
            except Exception:
                pass
    return count or 33  # fallback default


# ── Memory / conversation count ──
def count_conversations() -> int:
    """Count existing conversations from data directory."""
    data_dir = os.path.join(ROOT, "data")
    conversations_file = os.path.join(data_dir, "conversations.json")
    if os.path.exists(conversations_file):
        try:
            import json
            with open(conversations_file, encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return len(data)
                if isinstance(data, dict):
                    return len(data)
        except Exception:
            pass
    return 0


# ── Env helpers ──
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
    phase("First run — starting setup wizard", "🧙", "m")
    info("setup.py will configure your agent")
    time.sleep(1)
    subprocess.check_call([sys.executable, os.path.join(ROOT, "setup.py")])
    if not os.path.exists(ENV_FILE):
        fail(".env was not created — aborting")
        sys.exit(1)
    ok("Setup complete")


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
    phase("Installing WhatsApp dependencies...", "📱", "m")
    subprocess.check_call(f'"{npm_path}" install', cwd=wa, shell=True)
    ok("WhatsApp deps installed")


def check_update() -> None:
    """Check GitHub for newer version."""
    import json as _json
    import urllib.request as _urllib
    try:
        req = _urllib.Request(
            "https://api.github.com/repos/AbuSultancom/enterprise-ai-agent/releases/latest",
            headers={"User-Agent": "EnterpriseAI/0.5", "Accept": "application/json"},
        )
        with _urllib.urlopen(req, timeout=5) as r:
            data = _json.loads(r.read())
        latest = data.get("tag_name", "").lstrip("v")
        if latest and latest > VERSION:
            print(c(f"\n  ╔══ 🚀  UPDATE AVAILABLE ══╗", "m", "bold"))
            print(c(f"  ║  Current: v{VERSION}", "dim"))
            print(c(f"  ║  Latest:  v{latest}", "g"))
            print(c(f"  ║  {data.get('html_url', '')}", "c", "dim"))
            print(c(f"  ╚════════════════════╝", "m"))
            print()
            print(c(f"  Run this command to update:", "y"))
            print(c(f"    git pull origin main", "c", "bold"))
            print(c(f"    pip install -r requirements.txt", "c", "bold"))
            print()
    except Exception:
        pass


def wait_for_api(port: int, timeout: int = 20) -> bool:
    """Wait until the API health endpoint responds."""
    import http.client
    url = f"localhost:{port}"
    spin(f"Waiting for API on port {port}...")
    for i in range(timeout):
        try:
            conn = http.client.HTTPConnection(url, timeout=2)
            conn.request("GET", "/health")
            r = conn.getresponse()
            if r.status == 200:
                stop_spin()
                return True
        except Exception:
            pass
        time.sleep(1)
    stop_spin()
    return False


# ── Box drawing helper ──
def print_box(title: str, items: list[tuple[str, str]], color: str = "g", title_emoji: str = "✅") -> None:
    """Print a bordered box with title and key-value items."""
    width = 56
    top = "╔" + "═" * (width - 2) + "╗"
    mid = "║" + " " * (width - 2) + "║"
    bot = "╚" + "═" * (width - 2) + "╝"

    print()
    print(c(f"  {top}", color))
    # Title line
    title_line = f"      {title_emoji}  {title}  "
    print(c(f"  ║{title_line:<{width - 2}}║", color, "bold"))
    print(c(f"  ║{' ' * (width - 2)}║", color))
    for key, val in items:
        line = f"    {key}"
        # Pad to align value
        padded = f"{line:<30}{val}"
        print(c(f"  ║{padded:<{width - 2}}║", color))
    print(c(f"  ║{' ' * (width - 2)}║", color))
    print(c(f"  {bot}", color))
    print()


def main() -> None:
    args = parse_args()

    if args.version:
        print(f"Enterprise AI Agent v{VERSION}")
        sys.exit(0)

    os.chdir(ROOT)

    # ═══════════════════════════════════════════
    #  PHASE 1: Banner
    # ═══════════════════════════════════════════
    banner()
    show_tip()

    # ═══════════════════════════════════════════
    #  PHASE 2: System Checks
    # ═══════════════════════════════════════════
    phase("System Checks", "🔍", "c")

    # Animate the checks with spinner
    spin("Running system checks...", "c")

    py_ok, py_ver = check_python()
    if not py_ok:
        stop_spin()
        sys.exit(1)

    venv_ok, venv_detail = check_venv()
    deps_ok, deps_detail = check_deps()
    if not deps_ok:
        stop_spin()
        sys.exit(1)

    inet_ok, inet_detail = check_internet()
    node_ok, node_detail = check_node()
    npm_ok, npm_detail = check_npm()

    stop_spin()

    # Build and print the system checks table
    checks = [
        (f"Python {py_ver}", py_ok, py_ver),
        ("Virtual env", venv_ok, venv_detail),
        ("Dependencies", deps_ok, deps_detail),
        ("Internet", inet_ok, inet_detail),
        ("Node.js", node_ok, node_detail if node_ok else "not found"),
        ("npm", npm_ok, npm_detail if npm_ok else "not found"),
    ]
    system_checks_table(checks)

    # Show tool and conversation counts
    tool_count = count_tools()
    conv_count = count_conversations()
    info(f"🛠️  {tool_count} tools available")
    if conv_count:
        info(f"💬 {conv_count} existing conversations")

    # ═══════════════════════════════════════════
    #  PHASE 3: Setup
    # ═══════════════════════════════════════════
    phase("Configuration", "⚙️", "y")
    run_setup_if_needed()
    env = load_env()

    # ═══════════════════════════════════════════
    #  PHASE 4: WhatsApp
    # ═══════════════════════════════════════════
    whatsapp_on = (
        not args.no_whatsapp
        and env.get("WHATSAPP_ENABLED", "true") == "true"
        and node_ok
    )
    if whatsapp_on and npm_ok:
        ensure_node_deps(npm_detail)

    # ═══════════════════════════════════════════
    #  PHASE 5: Prepare environment
    # ═══════════════════════════════════════════
    env.setdefault("MEMORY_DB_PATH", os.path.join(ROOT, "data", "knowledge.json"))
    env.setdefault("AUDIT_LOG_PATH", os.path.join(ROOT, "data", "audit.jsonl"))
    env.setdefault("SETTINGS_PATH", os.path.join(ROOT, "config", "settings.json"))
    env.setdefault("API_KEYS",
                   f"admin:{env.get('ADMIN_KEY', 'dev-admin-key')},user:{env.get('USER_KEY', 'dev-user-key')}")
    os.makedirs(os.path.join(ROOT, "data"), exist_ok=True)

    port = args.port
    children: list[subprocess.Popen] = []

    def shutdown(*_):
        print()
        print(c("\n  🛑  Stopping all services...", "y", "bold"))
        for p in children:
            try:
                p.terminate()
            except Exception:
                pass
        print(c("  👋  Goodbye!", "dim"))
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, shutdown)

    # ═══════════════════════════════════════════
    #  PHASE 6: Start Services
    # ═══════════════════════════════════════════
    phase("Starting Services", "🚀", "g")

    # Start API
    progress = progress_dots(3, 1)
    info(f"Starting AI Agent API {progress}")
    uvicorn_args = ["--host", "0.0.0.0", "--port", str(port), "--log-level", "warning"]
    if args.dev:
        uvicorn_args.append("--reload")
    agent = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "api.main:app"] + uvicorn_args,
        cwd=ROOT, env=env)
    children.append(agent)

    # Wait for API
    if wait_for_api(port):
        ok(f"API ready on http://localhost:{port}")
    else:
        warn("API startup timed out — check for errors above")

    progress = progress_dots(3, 2)
    info(f"API is live {progress}")

    # Start WhatsApp
    if whatsapp_on and npm_ok:
        info(f"Starting WhatsApp Bridge {progress_dots(3, 3, True)}")
        node_cmd_path = node_detail if node_ok else "node"
        wa_env = dict(env)
        wa_env.setdefault("AGENT_URL", f"http://localhost:{port}")
        wa_env.setdefault("WHATSAPP_PORT", "3001")
        wa = subprocess.Popen([node_cmd_path, "index.js"], cwd=os.path.join(ROOT, "whatsapp"), env=wa_env)
        children.append(wa)

    # Start Telegram
    telegram_on = (
        not args.no_telegram
        and env.get("TELEGRAM_ENABLED", "false") == "true"
        and bool(env.get("TELEGRAM_BOT_TOKEN"))
    )
    if telegram_on:
        info(f"Starting Telegram Bridge...")
        tg_env = dict(env)
        tg_env.setdefault("AGENT_URL", f"http://localhost:{port}")
        tg = subprocess.Popen(
            [sys.executable, os.path.join(ROOT, "telegram", "bridge.py")],
            cwd=ROOT, env=tg_env)
        children.append(tg)

    # ═══════════════════════════════════════════
    #  PHASE 7: Summary
    # ═══════════════════════════════════════════
    summary_items = [
        ("🌐 Dashboard:", f"http://localhost:{port}"),
    ]
    if args.dev:
        summary_items.append(("⚡ Dev mode:", "Hot reload enabled"))
    if whatsapp_on and npm_ok:
        summary_items.append(("📱 WhatsApp QR:", "http://localhost:3001"))
    if telegram_on:
        summary_items.append(("💬 Telegram:", "Bot connected"))
    summary_items.append(("🛠️ Tools:", f"{tool_count} available"))
    summary_items.append(("🧠 Model:", "DeepSeek / Ollama"))

    print_box("ALL SYSTEMS GO", summary_items, "g", "🚀")

    print(c(f"    Press Ctrl+C to stop everything", "dim"))
    print()

    if not args.no_browser:
        try:
            webbrowser.open(f"http://localhost:{port}")
        except Exception:
            pass

    # Show another tip at the end
    show_tip()

    # ═══════════════════════════════════════════
    #  PHASE 8: Keep alive with auto-restart
    # ═══════════════════════════════════════════
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
                new_p = subprocess.Popen(p.args, cwd=ROOT, env=env)
                children[i] = new_p
        time.sleep(1)


if __name__ == "__main__":
    main()
