"""Optional Rich UI layer for the setup wizard (setup.py).

Auto-installs the pure-Python `rich` package on first run and upgrades the
wizard's visuals: panels, rules, styled prompts, braille spinners and a live
step tracker. If rich cannot be installed (offline, restricted), the wizard
keeps working with its built-in ANSI interface — nothing breaks.

Usage inside setup.py (at the start of main()):

    try:
        from cli_ui import apply as _rich_ui
        _rich_ui(globals())
    except Exception:
        pass
"""

from __future__ import annotations

import subprocess
import sys
import threading
from typing import Any

STEP_NAMES = [
    "Language", "Model", "Identity", "Security",
    "Channels", "Database", "Permissions", "Finish",
]


def _ensure_rich() -> bool:
    try:
        import rich  # noqa: F401

        return True
    except ImportError:
        pass
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--quiet", "rich"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=180,
        )
        import rich  # noqa: F401

        return True
    except Exception:
        return False


def apply(g: dict[str, Any]) -> bool:
    """Replace the ANSI helpers in setup.py's globals with Rich versions.

    Returns True if the rich UI was applied, False to keep the ANSI fallback.
    """
    if not _ensure_rich():
        return False

    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Confirm, Prompt
    from rich.rule import Rule
    from rich.text import Text

    console = Console()
    L = g["L"]

    def banner(title: str) -> None:
        console.print()
        console.print(
            Panel(
                Text(title, justify="center", style="bold bright_cyan"),
                border_style="bright_cyan",
                padding=(1, 4),
            )
        )

    def section(title: str) -> None:
        console.print(Rule(f"[bold bright_cyan]{title.strip()}[/]", style="bright_cyan"))

    def progress_bar(current: int, total: int, width: int = 40) -> str:
        filled = int(width * current / total)
        bar = "█" * filled + "░" * (width - filled)
        return f"[bright_cyan][{bar}][/] [bold]{int(100 * current / total)}%[/] ({current}/{total})"

    def ask(
        prompt: str,
        default: str | None = None,
        required: bool = False,
        password: bool = False,
        hint: str = "",
    ) -> str | None:
        label = f"[bold]{prompt}[/]"
        if hint:
            label += f" [dim]({hint})[/]"
        while True:
            value = Prompt.ask(
                label,
                default=default if default is not None else None,
                password=password,
                console=console,
            )
            value = (value or "").strip()
            if not value:
                if default is not None:
                    return default
                if required:
                    console.print(f"[red]  ✗ {L['required']}[/]")
                    continue
                return None
            return value

    def ask_yes(prompt: str, default: bool = True) -> bool:
        return Confirm.ask(f"[bold]{prompt.strip()}[/]", default=default, console=console)

    def choose(options: list[str], prompt: str = "", default: int = 0) -> int:
        if prompt:
            console.print(f"[bold]{prompt}[/]")
        for i, opt in enumerate(options, 1):
            marker = "[green]❯[/]" if (i - 1) == default else " "
            console.print(f" {marker} [bright_cyan]\\[{i}][/] {opt}")
        while True:
            raw = Prompt.ask(f"[bold]{L['select']}[/]", default=str(default + 1), console=console)
            try:
                idx = int(raw) - 1
                if 0 <= idx < len(options):
                    return idx
            except (ValueError, EOFError):
                pass
            console.print(f"[red]✗ 1–{len(options)}[/]")

    def spinner_run(text: str, func, *args, **kwargs) -> Any:
        result: list[Any] = [None]
        exc: list[Exception | None] = [None]

        def _worker():
            try:
                result[0] = func(*args, **kwargs)
            except Exception as e:
                exc[0] = e

        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        with console.status(f"[bright_cyan]{text}[/]", spinner="dots"):
            t.join()
        if exc[0] is not None:
            raise exc[0]
        return result[0]

    g.update(
        banner=banner,
        section=section,
        progress_bar=progress_bar,
        ask=ask,
        ask_yes=ask_yes,
        choose=choose,
        spinner_run=spinner_run,
    )

    # Rich step tracker replaces the plain progress-bar header
    wizard_cls = g.get("CLIWizard")
    if wizard_cls is not None:

        def _header(self, step: int, title: str) -> None:
            parts = []
            for i, name in enumerate(STEP_NAMES, 1):
                if i < step:
                    parts.append(f"[green]✓ {name}[/]")
                elif i == step:
                    parts.append(f"[bold bright_cyan]▶ {name}[/]")
                else:
                    parts.append(f"[dim]· {name}[/]")
            console.print()
            console.print("  ".join(parts))
            console.print(Rule(f"[bold bright_cyan]{title.strip()}[/]", style="bright_cyan"))

        wizard_cls._header = _header

    return True
