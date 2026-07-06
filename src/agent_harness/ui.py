"""All terminal interaction: the interview REPL, the plan gate, live progress.

Kept in one module so the stages stay testable — they call these functions,
tests replace them.
"""

from __future__ import annotations

import os
import platform
import shlex
import subprocess
import tempfile
from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt

console = Console()


def info(message: str) -> None:
    console.print(f"[dim]•[/dim] {message}")


def stage(title: str) -> None:
    console.rule(f"[bold cyan]{title}")


def show_markdown(text: str, title: str | None = None) -> None:
    body = Markdown(text)
    console.print(Panel(body, title=title) if title else body)


def ask_question(question: str, why: str, options: list[str] | None = None) -> str:
    """One interview question. Free-text answer; 'skip' and 'you decide' are valid."""
    console.print(f"\n[bold]{question}[/bold]")
    console.print(f"[dim]why this matters: {why}[/dim]")
    if options:
        for i, opt in enumerate(options, 1):
            console.print(f"  [cyan]{i}.[/cyan] {opt}")
        console.print("[dim](pick a number, or type your own answer)[/dim]")
    answer = Prompt.ask("[green]you[/green]").strip()
    if options and answer.isdigit() and 1 <= int(answer) <= len(options):
        return options[int(answer) - 1]
    return answer


def plan_gate() -> tuple[str, str]:
    """The approval gate. Returns (action, detail).

    Actions: approve | comment (detail = change request) | edit | reject | defer.
    """
    console.print(
        "\n[bold][a][/bold]pprove  [bold][c][/bold]omment/request changes  "
        "[bold][e][/bold]dit in editor  [bold][r][/bold]eject  [bold][d][/bold]efer"
    )
    while True:
        choice = Prompt.ask("[green]decision[/green]").strip().lower()
        if choice in ("a", "approve"):
            return "approve", ""
        if choice in ("c", "comment"):
            comment = Prompt.ask("[green]what should change[/green]").strip()
            if comment:
                return "comment", comment
        elif choice in ("e", "edit"):
            return "edit", ""
        elif choice in ("r", "reject"):
            return "reject", Prompt.ask("[green]why (goes to retro)[/green]", default="").strip()
        elif choice in ("d", "defer"):
            return "defer", ""
        else:
            console.print("[red]a / c / e / r / d[/red]")


def choice(options: dict[str, str]) -> str:
    """Generic single-key menu: {'a': 'accept', 'd': 'defer'} → returns the key."""
    legend = "  ".join(
        f"[bold][{key}][/bold]{label[1:] if label.startswith(key) else ' ' + label}"
        for key, label in options.items()
    )
    console.print(f"\n{legend}")
    while True:
        picked = Prompt.ask("[green]choice[/green]").strip().lower()
        if picked in options:
            return picked
        console.print(f"[red]{' / '.join(options)}[/red]")


def confirm(question: str, default: bool = True) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    answer = Prompt.ask(f"{question} {suffix}", default="y" if default else "n").strip().lower()
    return answer.startswith("y")


def edit_in_editor(initial: str, suffix: str = ".md") -> str:
    """Open text in $EDITOR (notepad/vi fallback), return the edited content."""
    on_windows = platform.system() == "Windows"
    editor = os.environ.get("EDITOR") or ("notepad" if on_windows else "vi")
    # posix=False keeps Windows paths intact; strip the quotes it preserves.
    tokens = [t.strip('"') for t in shlex.split(editor, posix=not on_windows)]
    with tempfile.NamedTemporaryFile("w", suffix=suffix, delete=False, encoding="utf-8") as f:
        f.write(initial)
        temp_path = Path(f.name)
    try:
        subprocess.run([*tokens, str(temp_path)], check=True)
        return temp_path.read_text(encoding="utf-8")
    finally:
        temp_path.unlink(missing_ok=True)


def narrate_stream_event(event: dict) -> None:
    """Compact one-line narration of stream-json events during execution."""
    etype = event.get("type")
    if etype == "tool_call" and event.get("subtype") == "started":
        call = event.get("tool_call", event)
        name = call.get("name") or call.get("tool") or "tool"
        console.print(f"  [dim]→ {name}[/dim]")
    elif etype == "assistant":
        message = event.get("message", {})
        content = message.get("content") if isinstance(message, dict) else None
        if isinstance(content, str) and content.strip():
            first_line = content.strip().splitlines()[0]
            console.print(f"  [dim]{first_line[:120]}[/dim]")
