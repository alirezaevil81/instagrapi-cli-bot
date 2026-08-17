import datetime
import os
import sys
import time
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TimeRemainingColumn
)

# Configure UTF-8 encoding on Windows consoles
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8")
        if hasattr(sys.stdin, "reconfigure"):
            sys.stdin.reconfigure(encoding="utf-8")
        import ctypes
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        ctypes.windll.kernel32.SetConsoleCP(65001)
    except Exception:
        pass

# Initialize Rich Console with log time, caller path, and UTF-8 support
console = Console(log_time=True, log_path=True, log_time_format="%Y-%m-%d %H:%M:%S", legacy_windows=False)

import arabic_reshaper
from bidi.algorithm import get_display

# Configure Persian-specific character joining and ligatures
_reshaper_config = {
    'delete_harakat': False,
    'support_ligatures': True,
    'language': 'Persian'
}
_persian_reshaper = arabic_reshaper.ArabicReshaper(configuration=_reshaper_config)

def fix_persian(text: str) -> str:
    """
    Reshapes and applies BiDi algorithm to Persian/Arabic text for correct terminal rendering.
    If the text has no Persian/Arabic characters, returns the original text.
    """
    if not text or not isinstance(text, str):
        return text
    # Check if string contains Persian/Arabic unicode characters
    has_persian = any('\u0600' <= char <= '\u06FF' or '\uFB50' <= char <= '\uFDFF' or '\uFE70' <= char <= '\uFEFF' for char in text)
    if not has_persian:
        return text

    try:
        reshaped = _persian_reshaper.reshape(text)
        return get_display(reshaped)
    except Exception:
        try:
            reshaped = arabic_reshaper.reshape(text)
            return get_display(reshaped)
        except Exception:
            return text

def log_print(*args, _stack_offset: int = 2, **kwargs):
    """Logs messages with Rich's native console.log(), rendering timestamp, caller file:line, and syntax highlighting."""
    console.log(*args, _stack_offset=_stack_offset, **kwargs)

def log_success(message: str, _stack_offset: int = 2):
    """Logs a success message with green styling and a check mark."""
    console.log(f"[bold green]:white_check_mark: [Successful]:[/bold green] {message}", _stack_offset=_stack_offset)

def log_error(message: str, exception: str = "", _stack_offset: int = 2):
    """Logs an error message with red styling and a cross mark."""
    exc_str = f" {exception}" if exception else ""
    console.log(f"[bold red]:cross_mark: [Error]:[/bold red] {message}{exc_str}", _stack_offset=_stack_offset)

def log_warning(message: str, _stack_offset: int = 2):
    """Logs a warning message with yellow styling and a warning icon."""
    console.log(f"[bold yellow]:warning: [Warning]:[/bold yellow] {message}", _stack_offset=_stack_offset)

def log_data(data, title: str = "", _stack_offset: int = 2, **kwargs):
    """Logs data collections (dicts, lists, objects) with Rich syntax highlighting and pretty-printing."""
    if title:
        console.log(f"[bold cyan]{title}:[/bold cyan]", data, _stack_offset=_stack_offset, **kwargs)
    else:
        console.log(data, _stack_offset=_stack_offset, **kwargs)

def format_seconds(seconds: int) -> str:
    """Formats seconds into readable human format (e.g. 45s, 2m 30s, 1h 15m 00s)."""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        mins, secs = divmod(seconds, 60)
        return f"{mins}m {secs:02d}s"
    else:
        hours, rem = divmod(seconds, 3600)
        mins, secs = divmod(rem, 60)
        return f"{hours}h {mins:02d}m {secs:02d}s"

def log_sleep(seconds: int, message: str = "Sleeping for safety / cooldown", _stack_offset: int = 2):
    """
    Dynamic countdown sleep with an animated rotating spinner, progress bar,
    and live real-time countdown of remaining seconds/minutes.
    """
    if seconds <= 0:
        return

    sec_int = int(seconds)
    formatted_total = format_seconds(sec_int)

    with Progress(
        SpinnerColumn(spinner_name="dots", style="bold cyan"),
        TextColumn("[bold yellow]:sleeping: {task.description}[/bold yellow]"),
        BarColumn(bar_width=20, style="bright_black", complete_style="bold green", finished_style="bold green"),
        TextColumn("[bold cyan]{task.fields[remaining_display]}[/bold cyan] remaining"),
        TimeRemainingColumn(),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task(
            message,
            total=sec_int,
            remaining_display=formatted_total
        )

        for elapsed in range(1, sec_int + 1):
            time.sleep(1)
            rem = sec_int - elapsed
            progress.update(
                task,
                advance=1,
                remaining_display=format_seconds(rem)
            )

        frac = seconds - sec_int
        if frac > 0:
            time.sleep(frac)


def show_banner(title: str, subtitle: str = ""):
    """Displays a rich banner for CLI start using Rich emoji markup."""
    text_content = f":robot: [bold cyan]{title}[/bold cyan]\n"
    if subtitle:
        text_content += f"[dim white]{subtitle}[/dim white]\n"
    console.print(Panel(Text.from_markup(text_content), border_style="bright_blue", expand=False))

def show_user_table(users: list, title: str = "Target Users"):
    """Renders a Rich table of Instagram users with Rich emoji icons."""
    table = Table(title=f":clipboard: {title} ({len(users)} users)", border_style="cyan", header_style="bold magenta")
    table.add_column("Index", justify="right", style="cyan", no_wrap=True)
    table.add_column("User ID (PK)", style="yellow")
    table.add_column("Username", style="bold green")
    table.add_column("Full Name", style="white")
    table.add_column("Privacy", justify="center")

    for i, user in enumerate(users, start=1):
        uid = str(getattr(user, 'pk', '-'))
        uname = str(getattr(user, 'username', '-'))
        fname = str(getattr(user, 'full_name', '-'))
        is_priv = getattr(user, 'is_private', False)
        privacy = "[red]:lock: Private[/red]" if is_priv else "[green]:globe_with_meridians: Public[/green]"
        table.add_row(str(i), uid, uname, fix_persian(fname), privacy)

    console.print(table)

