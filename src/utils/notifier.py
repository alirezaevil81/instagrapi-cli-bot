"""
Termux & System Notification Helper with Connection Error Recovery.
Detects Termux environment, sends native Android notifications via termux-api,
and handles interactive network/connection recovery with notifications.
"""
import os
import sys
import shutil
import subprocess
from typing import Optional

from src.utils.console import (
    console,
    em,
    log_print,
    log_success,
    log_warning,
    log_error,
    ask_yes_no,
    QUESTIONARY_STYLE
)
from src.core.exceptions import is_network_error


def is_termux() -> bool:
    """
    Detects if the Python script is running inside the Termux Android environment.
    """
    if os.environ.get("TERMUX_VERSION"):
        return True
    prefix = os.environ.get("PREFIX", "")
    if "com.termux" in prefix:
        return True
    if os.path.exists("/data/data/com.termux"):
        return True
    if "com.termux" in sys.executable:
        return True
    return False


def has_termux_api() -> bool:
    """
    Checks if Termux:API tools (like termux-notification) are installed and accessible in PATH.
    """
    return shutil.which("termux-notification") is not None


def install_termux_api_package() -> bool:
    """
    Attempts to install termux-api CLI package via pkg or apt in Termux.
    """
    pkg_bin = shutil.which("pkg") or shutil.which("apt") or shutil.which("apt-get")
    if not pkg_bin:
        return False
    
    with console.status("[bold cyan]:package: Installing termux-api package in Termux...[/bold cyan]", spinner="dots"):
        try:
            cmd = [pkg_bin, "install", "-y", "termux-api"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=False)
            if res.returncode == 0 and has_termux_api():
                return True
        except Exception:
            pass
    return has_termux_api()


def ensure_termux_api(interactive: bool = True) -> bool:
    """
    Checks if Termux is detected and if termux-api is installed.
    If missing, prompts to install automatically or displays a clear warning and instructions.
    """
    if not is_termux():
        return True

    if has_termux_api():
        return True

    from rich.panel import Panel
    warning_msg = (
        "[bold yellow]:bell: Android Notification Addon (termux-api) is not installed in Termux.[/bold yellow]\n\n"
        "[white]To receive bot completion alerts and network/VPN disconnection warnings on your phone, the [bold cyan]termux-api[/bold cyan] package is recommended.[/white]\n\n"
        "[dim]Manual installation command:[/dim] [bold green]pkg install termux-api[/bold green]\n"
        "[dim]Note: The [bold magenta]Termux:API[/bold magenta] Android app must also be installed on your device (F-Droid / GitHub).[/dim]"
    )
    console.print()
    console.print(Panel(em(warning_msg), title=em(":iphone: [bold yellow]Termux:API Notification Setup[/bold yellow]"), border_style="yellow"))
    console.print()

    if interactive:
        should_install = ask_yes_no(
            english_question="Would you like to automatically install termux-api package now? (pkg install termux-api)",
            default=True
        )
        if should_install:
            success = install_termux_api_package()
            if success:
                log_success(":white_check_mark: termux-api package installed successfully! Android notifications are enabled. :iphone:")
                return True
            else:
                log_error("Automatic installation failed. Please run [bold cyan]pkg install termux-api[/bold cyan] manually in Termux.")
                return False
        else:
            log_warning("Skipped termux-api installation. Default terminal audio alerts will be used.")
            return False

    return False


def send_termux_notification(
    title: str,
    content: str,
    notification_id: str = "instagrapi_bot",
    priority: str = "high",
    vibrate: str = "500,250,500",
    sound: bool = True,
    toast: bool = False
) -> bool:
    """
    Sends an Android notification using Termux:API if available.
    Falls back to terminal bell on non-Termux environments.
    """
    # Audible terminal alert
    try:
        sys.stdout.write("\a")
        sys.stdout.flush()
    except Exception:
        pass

    if not has_termux_api():
        return False

    cmd = [
        "termux-notification",
        "--id", str(notification_id),
        "--title", str(title),
        "--content", str(content),
        "--priority", str(priority),
    ]
    if vibrate:
        cmd.extend(["--vibrate", str(vibrate)])
    if sound:
        cmd.append("--sound")

    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=4, check=False)
        
        if toast and shutil.which("termux-toast"):
            subprocess.run(
                ["termux-toast", "-s", str(content)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=3,
                check=False
            )
        return True
    except Exception:
        return False


def notify_task_completed(service_name: str, summary: str = "") -> None:
    """
    Sends a completion notification when a bot task finishes its operations.
    """
    title = f"🤖 Bot Task Completed | {service_name}"
    content = summary if summary else "Bot task finished successfully. All operations completed."
    
    # Send Termux notification if in Termux
    sent = send_termux_notification(
        title=title,
        content=content,
        notification_id="bot_completed",
        priority="high",
        vibrate="600,200,600",
        sound=True,
        toast=True
    )
    if is_termux():
        if sent:
            log_print(":bell: [bold green]Completion notification sent to device.[/bold green] :iphone:")
        else:
            log_print(":information_source: [dim]Termux detected. (Install 'pkg install termux-api' for Android notifications)[/dim]")


def notify_connection_error(action_name: str = "Instagram Operation", error_detail: str = "") -> None:
    """
    Sends an urgent notification when network/DNS connection is lost.
    """
    title = f"⚠️ Network Connection Error | {action_name}"
    detail_msg = f" ({error_detail})" if error_detail else ""
    content = f"Bot paused due to lost connection! Please check your internet or VPN.{detail_msg}"
    
    send_termux_notification(
        title=title,
        content=content,
        notification_id="bot_conn_error",
        priority="max",
        vibrate="1000,400,1000,400,1000",
        sound=True,
        toast=True
    )


def handle_connection_recovery(exc: Optional[Exception] = None, action_name: str = "Instagram Operation") -> bool:
    """
    Pauses the bot when a connection/DNS error occurs, sends a Termux notification,
    and displays an interactive Yes/No prompt asking if the user resolved the connection issue.
    Returns True if the user resolved it and wants to retry, or False to abort/skip.
    """
    err_text = str(exc) if exc else "Connection drop / DNS resolve failure"
    notify_connection_error(action_name=action_name, error_detail=err_text[:80])

    from rich.panel import Panel
    warning_text = (
        f"[bold red]:satellite: Instagram Connection / DNS Error[/bold red]\n\n"
        f"[yellow]Action:[/yellow] [bold white]{action_name}[/bold white]\n"
        f"[yellow]Error Detail:[/yellow] [italic dim]{err_text}[/italic dim]\n\n"
        f"[cyan]💡 Tip:[/cyan] Check your internet connection, Wi-Fi, mobile data, or VPN / proxy status."
    )
    console.print()
    console.print(Panel(em(warning_text), title=em(":warning: [bold yellow]Network & Connection Error[/bold yellow]"), border_style="red"))
    console.print()

    # Interactive prompt with Questionary
    resolved = ask_yes_no(
        english_question="Connection issue resolved? (Choose Yes to Retry, No to Stop)",
        default=True
    )

    if resolved:
        log_success(":white_check_mark: Connection verified. Retrying operation... :rocket:")
        return True
    else:
        log_warning(":stop_sign: Operation cancelled by user. Progress is saved in SQLite database. :floppy_disk:")
        return False
