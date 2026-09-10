import datetime
import os
import sys
import time
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.rule import Rule
from rich.columns import Columns
from rich import box
from rich.emoji import Emoji
from rich.align import Align
from rich.traceback import install as install_rich_traceback
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TimeRemainingColumn
)
from src.utils.logger import get_file_logger, clean_rich_markup

# Install beautiful rich tracebacks globally
install_rich_traceback(show_locals=True, width=100)

import json

_EMOJI_FALLBACKS = {}
_emoji_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "emojis.json")
try:
    with open(_emoji_file, "r", encoding="utf-8") as _f:
        _EMOJI_FALLBACKS = json.load(_f)
except Exception:
    pass

def em(text: str) -> str:
    """
    Converts Rich emoji shortcodes (e.g. :zap:, :newspaper:, :white_check_mark:)
    to Unicode emoji characters at runtime using Rich's Emoji parser with safety fallbacks.
    """
    if not text or not isinstance(text, str):
        return text
    try:
        res = Emoji.replace(text)
    except Exception:
        res = text
    for code, emoji_char in _EMOJI_FALLBACKS.items():
        if code in res:
            res = res.replace(code, emoji_char)
    return res

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

# Initialize Rich Console
console = Console(log_time=True, log_path=True, log_time_format="%Y-%m-%d %H:%M:%S", legacy_windows=False)

def fix_persian(text: str) -> str:
    """Pass-through string helper maintained for backward compatibility."""
    return text if isinstance(text, str) else str(text)

def format_bilingual_prompt(english: str, persian: str = "") -> str:
    """Formats an interactive CLI prompt."""
    return f"{english}:"

def ask_yes_no(english_question: str, persian_question: str = "", default: bool = True) -> bool:
    """
    Displays an interactive selection menu with Yes / No options.
    """
    import questionary
    prompt_text = em(english_question)
    yes_choice = questionary.Choice(title=em(":white_check_mark: Yes"), value=True)
    no_choice = questionary.Choice(title=em(":x: No"), value=False)
    choices = [yes_choice, no_choice]

    choice = questionary.select(
        prompt_text,
        choices=choices,
        default=yes_choice if default else no_choice
    ).ask()
    return default if choice is None else bool(choice)

def ask_choice_or_custom(
    english_title: str,
    persian_title: str = "",
    options: list = None,
    default_val: any = None,
    custom_prompt_en: str = "Enter custom value",
    custom_prompt_fa: str = "",
    val_type: type = int
):
    """
    Shows an interactive list of preset choices with a 'Custom...' option.
    """
    import questionary
    prompt_text = em(f"{english_title}:")
    
    choices = []
    default_choice = None
    
    if options:
        for opt in options:
            val = opt[0]
            title_en = opt[1]
            desc_en = opt[2] if len(opt) > 2 else ""
            icon = opt[3] if len(opt) > 3 else ":point_right:"
            label = em(f"{icon} {title_en} - {desc_en}" if desc_en else f"{icon} {title_en}")
            c = questionary.Choice(title=label, value=val)
            choices.append(c)
            if default_val is not None and val == default_val:
                default_choice = c
            
    custom_choice = questionary.Choice(
        title=em(":gear: Custom... (Manual configuration)"),
        value="__custom__"
    )
    choices.append(custom_choice)
    
    if default_choice is None and choices:
        default_choice = choices[0]
        
    selected = questionary.select(
        prompt_text,
        choices=choices,
        default=default_choice
    ).ask()
    
    if selected == "__custom__":
        cust_prompt = f"{custom_prompt_en}:"
        val_str = questionary.text(
            em(cust_prompt),
            default=str(default_val if default_val is not None else "1"),
            validate=lambda x: True if len(x.strip()) > 0 else "Please enter a value"
        ).ask() or str(default_val if default_val is not None else "1")
        try:
            if val_type == int:
                return max(1, int(float(val_str.strip())))
            elif val_type == float:
                return max(0.1, float(val_str.strip()))
            return val_str.strip()
        except ValueError:
            return default_val if default_val is not None else (1 if val_type == int else 1.0)
    
    return selected if selected is not None else default_val


def ask_api_delay_range(default_range: list = None) -> list:
    """
    Interactive select menu for base API request delay presets.
    """
    import questionary
    if not default_range or len(default_range) != 2:
        default_range = [3, 7]

    prompt_text = em("Select base Instagram API request delay range (seconds):")

    c_fast = questionary.Choice(title=em(":zap: 2 - 5 seconds (Fast)"), value="2_5")
    c_safe = questionary.Choice(title=em(":shield: 3 - 7 seconds (Recommended & Safe)"), value="3_7")
    c_slow = questionary.Choice(title=em(":hourglass: 5 - 10 seconds (Conservative / Slow)"), value="5_10")
    c_custom = questionary.Choice(title=em(":gear: Custom interval... (Manual entry)"), value="custom")
    choices = [c_fast, c_safe, c_slow, c_custom]

    selected = questionary.select(
        prompt_text,
        choices=choices,
        default=c_safe
    ).ask()

    if selected == "2_5":
        return [2, 5]
    elif selected == "3_7":
        return [3, 7]
    elif selected == "5_10":
        return [5, 10]
    elif selected == "custom":
        min_p = "Base API request delay min (seconds):"
        max_p = "Base API request delay max (seconds):"
        min_val_str = questionary.text(em(min_p), default=str(default_range[0])).ask() or str(default_range[0])
        max_val_str = questionary.text(em(max_p), default=str(default_range[1])).ask() or str(default_range[1])
        try:
            val1 = max(1, int(min_val_str.strip()))
            val2 = max(1, int(max_val_str.strip()))
            return [min(val1, val2), max(val1, val2)]
        except ValueError:
            return default_range
    else:
        return default_range


def ask_delay_range(action_name: str = "likes", default_range: list = None) -> list:
    """
    Interactive select menu for delay presets with a Custom option.
    Includes [60, 90] seconds preset among popular safe ranges.
    """
    import questionary
    if not default_range or len(default_range) != 2:
        default_range = [60, 90]

    prompt_text = em(f"Select delay interval between {action_name} (seconds):")

    c_25_50 = questionary.Choice(title=em(":zap: 25 - 50 seconds (Fast)"), value="25_50")
    c_60_90 = questionary.Choice(title=em(":shield: 60 - 90 seconds (Standard & Safe)"), value="60_90")
    c_90_150 = questionary.Choice(title=em(":hourglass: 90 - 150 seconds (Conservative / Slow)"), value="90_150")
    c_custom = questionary.Choice(title=em(":gear: Custom interval... (Manual entry)"), value="custom")
    choices = [c_25_50, c_60_90, c_90_150, c_custom]

    selected = questionary.select(
        prompt_text,
        choices=choices,
        default=c_60_90
    ).ask()

    if selected == "25_50":
        return [25, 50]
    elif selected == "60_90":
        return [60, 90]
    elif selected == "90_150":
        return [90, 150]
    elif selected == "custom":
        min_p = f"Enter minimum delay for {action_name} (seconds):"
        max_p = f"Enter maximum delay for {action_name} (seconds):"
        min_val_str = questionary.text(em(min_p), default=str(default_range[0])).ask() or str(default_range[0])
        max_val_str = questionary.text(em(max_p), default=str(default_range[1])).ask() or str(default_range[1])
        try:
            val1 = max(1, int(min_val_str.strip()))
            val2 = max(1, int(max_val_str.strip()))
            return [min(val1, val2), max(val1, val2)]
        except ValueError:
            return default_range
    else:
        return default_range


def show_system_dashboard():
    """Displays a stylized system dashboard with multiple columns."""
    from rich.panel import Panel
    from rich.columns import Columns
    from rich.table import Table
    import platform
    from src.config import DB_PATH, SESSIONS_DIR

    # 1. System Info Panel
    sys_table = Table(box=None, padding=(0, 1), show_header=False)
    sys_table.add_row(em(":desktop_computer: OS:"), platform.system() + " " + platform.release())
    sys_table.add_row(em(":clock1: Time:"), datetime.datetime.now().strftime("%H:%M:%S"))
    sys_panel = Panel(sys_table, title=em("[bold cyan]System Status[/bold cyan]"), border_style="cyan")

    # 2. Storage & DB Info Panel
    db_size = "0 KB"
    if os.path.exists(DB_PATH):
        db_size = f"{os.path.getsize(DB_PATH) / 1024:.1f} KB"
        
    sessions_count = len([name for name in os.listdir(SESSIONS_DIR) if os.path.isfile(os.path.join(SESSIONS_DIR, name))]) if os.path.exists(SESSIONS_DIR) else 0

    storage_table = Table(box=None, padding=(0, 1), show_header=False)
    storage_table.add_row(em(":floppy_disk: DB Size:"), db_size)
    storage_table.add_row(em(":key: Saved Sessions:"), str(sessions_count))
    storage_panel = Panel(storage_table, title=em("[bold green]Storage & DB[/bold green]"), border_style="green")

    # Display columns
    console.print(Columns([sys_panel, storage_panel], expand=True))
    console.print()

def show_markdown(text: str):
    """Renders markdown text elegantly."""
    from rich.markdown import Markdown
    md = Markdown(text)
    console.print(md)
    console.print()

def show_config_tree():
    """Displays the current configuration in a beautiful tree structure."""
    from rich.tree import Tree
    from src.config import STORAGE_DIR, SESSIONS_DIR, DATABASE_DIR, LOGS_DIR, get_delay_range, load_comments
    
    tree = Tree(em(":robot: [bold cyan]Bot Configuration System[/bold cyan]"))
    
    dirs = tree.add(em(":open_file_folder: [bold yellow]Directories[/bold yellow]"))
    dirs.add(f"[green]Storage Root:[/green] {STORAGE_DIR}")
    dirs.add(f"[green]Sessions:[/green] {SESSIONS_DIR}")
    dirs.add(f"[green]Database:[/green] {DATABASE_DIR}")
    dirs.add(f"[green]Logs:[/green] {LOGS_DIR}")
    
    api = tree.add(em(":gear: [bold yellow]API Settings[/bold yellow]"))
    api.add(f"[green]Request Delay Range:[/green] {get_delay_range()} seconds")
    
    comments = load_comments()
    msg = tree.add(em(":speech_balloon: [bold yellow]Comments Data[/bold yellow]"))
    msg.add(f"[green]Loaded Templates:[/green] {len(comments)} items")
    
    console.print(tree)
    console.print()

def log_print(*args, _stack_offset: int = 2, **kwargs):
    """Logs messages with Rich console and writes to storage/logs/bot.log."""
    processed_args = [em(str(a)) if isinstance(a, str) else a for a in args]
    console.log(*processed_args, _stack_offset=_stack_offset, **kwargs)
    try:
        msg = " ".join(str(a) for a in processed_args)
        get_file_logger().info(clean_rich_markup(msg))
    except Exception:
        pass

def log_success(message: str, _stack_offset: int = 2):
    """Logs a success message with green styling and writes to log file."""
    msg = em(f"[bold green]:white_check_mark: [Successful]:[/bold green] {message}")
    console.log(msg, _stack_offset=_stack_offset)
    try:
        get_file_logger().info(f"[SUCCESS] {clean_rich_markup(message)}")
    except Exception:
        pass

def log_error(message: str, exception: str = "", _stack_offset: int = 2):
    """Logs an error message with red styling and writes to log file."""
    exc_str = f" {exception}" if exception else ""
    msg = em(f"[bold red]:cross_mark: [Error]:[/bold red] {message}{exc_str}")
    console.log(msg, _stack_offset=_stack_offset)
    try:
        get_file_logger().error(f"[ERROR] {clean_rich_markup(message)}{exc_str}")
    except Exception:
        pass

def log_warning(message: str, _stack_offset: int = 2):
    """Logs a warning message with yellow styling and writes to log file."""
    msg = em(f"[bold yellow]:warning: [Warning]:[/bold yellow] {message}")
    console.log(msg, _stack_offset=_stack_offset)
    try:
        get_file_logger().warning(f"[WARNING] {clean_rich_markup(message)}")
    except Exception:
        pass

def log_data(data, title: str = "", _stack_offset: int = 2, **kwargs):
    """Logs data collections with Rich syntax highlighting and writes to file."""
    if title:
        console.log(f"[bold cyan]{em(title)}:[/bold cyan]", data, _stack_offset=_stack_offset, **kwargs)
        try:
            get_file_logger().info(f"{title}: {data}")
        except Exception:
            pass
    else:
        console.log(data, _stack_offset=_stack_offset, **kwargs)
        try:
            get_file_logger().info(str(data))
        except Exception:
            pass

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
        TextColumn(em("[bold yellow]:sleeping: {task.description}[/bold yellow]")),
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
    """Displays a stylized Rich banner for CLI start using Rich emoji markup and rounded borders."""
    text_content = em(f":robot: [bold bright_cyan]{title}[/bold bright_cyan]\n")
    if subtitle:
        text_content += em(f"[dim bright_white]:sparkles: {subtitle}[/dim bright_white]\n")
    console.print(Panel(
        Text.from_markup(text_content.strip()),
        box=box.ROUNDED,
        border_style="bright_blue",
        padding=(1, 2),
        expand=False
    ))
    try:
        get_file_logger().info(f"=== {title} ({subtitle}) ===")
    except Exception:
        pass

def show_section_divider(title: str = "", style: str = "bold magenta"):
    """Draws an elegant Rich Rule divider across the console."""
    if title:
        console.print(Rule(em(title), style=style))
    else:
        console.print(Rule(style=style))

def show_stats_card(title: str, stats: dict, border_style: str = "cyan"):
    """
    Renders a sleek summary statistics card with Rich box borders and emojis.
    """
    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="bold white", justify="left")
    grid.add_column(style="bold yellow", justify="right")

    for k, v in stats.items():
        grid.add_row(em(k), em(str(v)))

    panel = Panel(
        grid,
        title=em(f":bar_chart: [bold]{title}[/bold]"),
        box=box.ROUNDED,
        border_style=border_style,
        padding=(1, 2),
        expand=False
    )
    console.print(panel)

def show_user_table(users: list, title: str = "Target Users"):
    """Renders a Rich table of Instagram users with Rich emoji icons and rounded borders."""
    table = Table(
        title=em(f":clipboard: [bold cyan]{title}[/bold cyan] ([bold yellow]{len(users)}[/bold yellow] users)"),
        box=box.ROUNDED,
        border_style="cyan",
        header_style="bold magenta"
    )
    table.add_column(em(":hash: #"), justify="center", style="cyan", no_wrap=True, width=5)
    table.add_column(em(":id: User ID (PK)"), style="yellow", justify="center")
    table.add_column(em(":bust_in_silhouette: Username"), style="bold green")
    table.add_column(em(":name_badge: Full Name"), style="white")
    table.add_column(em(":lock: Privacy"), justify="center")

    for i, user in enumerate(users, start=1):
        uid = str(getattr(user, 'pk', '-'))
        uname = str(getattr(user, 'username', '-'))
        fname = str(getattr(user, 'full_name', '-'))
        is_priv = getattr(user, 'is_private', False)
        privacy = em("[red]:lock: Private[/red]") if is_priv else em("[green]:globe_with_meridians: Public[/green]")
        table.add_row(str(i), uid, f"@{uname}", fname if fname else "[dim]-[/dim]", privacy)

    console.print(table)



def ask_int(english_question: str, default: int = 1, min_val: int = -1) -> int:
    import questionary
    while True:
        val = questionary.text(f"{english_question} (default: {default})").ask()
        if val is None:
            return default
        val = val.strip()
        if not val:
            return default
        try:
            val_int = int(val)
            if val_int < min_val:
                print(f"Please enter a number >= {min_val}")
                continue
            return val_int
        except ValueError:
            print("Please enter a valid integer.")
