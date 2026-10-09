"""
Termux & System Notification Helper with Connection Error Recovery.
Detects Termux environment, sends native Android notifications via termux-api,
and handles interactive network/connection recovery with notifications.
"""
import os
import sys
import time
import socket
import ssl
import urllib.request
import urllib.error
import shutil
import subprocess
import atexit
from typing import Optional, Tuple

from src.utils.console import (
    console,
    em,
    log_print,
    log_success,
    log_warning,
    log_error,
    ask_yes_no,
    is_compact_terminal,
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


ONGOING_NOTIFICATION_ID = "instagrapi_ongoing_progress"
_last_ongoing_update_time: float = 0.0
_last_ongoing_content: str = ""


def send_termux_notification(
    title: str,
    content: str,
    notification_id: str = "instagrapi_bot",
    priority: str = "high",
    vibrate: str = "500,250,500",
    sound: bool = True,
    toast: bool = False,
    ongoing: bool = False,
    alert_once: bool = False
) -> bool:
    """
    Sends an Android notification using Termux:API if available.
    Supports persistent ongoing notifications and alert suppression.
    Falls back to terminal bell on non-Termux environments.
    """
    # Audible terminal alert (only if sound is enabled and not ongoing update)
    if sound and not ongoing:
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
    if ongoing:
        cmd.append("--ongoing")
    if alert_once:
        cmd.append("--alert-once")
    if vibrate and vibrate.strip():
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


def remove_termux_notification(notification_id: str = ONGOING_NOTIFICATION_ID) -> bool:
    """
    Cancels and dismisses a Termux notification by its ID using termux-notification-remove.
    """
    if not has_termux_api():
        return False

    remover = shutil.which("termux-notification-remove")
    if remover:
        try:
            subprocess.run(
                [remover, str(notification_id)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=3,
                check=False
            )
            return True
        except Exception:
            pass
    return False


def remove_ongoing_notification(notification_id: str = ONGOING_NOTIFICATION_ID) -> bool:
    """Alias for cleanly removing ongoing persistent progress notification."""
    global _last_ongoing_content
    _last_ongoing_content = ""
    return remove_termux_notification(notification_id=notification_id)


# Ensure ongoing notification is cleaned up on script termination
atexit.register(remove_ongoing_notification)


def update_ongoing_progress_notification(
    bot_title: str,
    current_step: str,
    processed_count: int,
    total_items: int,
    status: str = "ACTIVE",
    target: str = "",
    force: bool = False,
    notification_id: str = ONGOING_NOTIFICATION_ID
) -> bool:
    """
    Displays / updates a persistent ongoing Android notification (نوتیف دائمی)
    showing:
    - Exactly what stage the operation is currently in
    - Percentage remaining to finish (and % completed)
    - Processed vs total item counts and active target

    Runs silently with low priority and alert-once so user is kept informed
    without sound or vibration disruptions.
    """
    global _last_ongoing_update_time, _last_ongoing_content

    now = time.time()
    # Throttle rapid updates to prevent Android process saturation (min 1.5s interval unless forced)
    if not force and (now - _last_ongoing_update_time) < 1.5:
        return False

    if not is_termux() or not has_termux_api():
        return False

    status_tag = f"[{status}]" if status and status not in ("RUNNING", "ACTIVE") else ""
    title = f"🤖 {bot_title} {status_tag}".strip()

    target_display = f"@{target.lstrip('@')}" if target and target != "-" else ""

    if total_items > 0:
        pct_done = min(100, int((processed_count / total_items) * 100))
        pct_remaining = max(0, 100 - pct_done)
        
        # Primary headline: percent remaining & progress
        headline = f"⏳ {pct_remaining}% remaining ({pct_done}% done • {processed_count}/{total_items})"
        
        stage_desc = f"📍 Stage: {current_step}"
        if target_display:
            stage_desc += f" ({target_display})"
        
        content = f"{headline}\n{stage_desc}"
    else:
        # Continuous mode / undetermined total count
        target_info = f" ({target_display})" if target_display else ""
        content = f"⚡ Processed: {processed_count} items\n📍 Stage: {current_step}{target_info}"

    # Deduplicate exact identical consecutive content within short window
    if content == _last_ongoing_content and (now - _last_ongoing_update_time) < 8.0:
        return False

    _last_ongoing_update_time = now
    _last_ongoing_content = content

    return send_termux_notification(
        title=title,
        content=content,
        notification_id=notification_id,
        priority="low",
        vibrate="",
        sound=False,
        toast=False,
        ongoing=True,
        alert_once=True
    )


def notify_task_completed(service_name: str, summary: str = "") -> None:
    """
    Sends a completion notification when a bot task finishes its operations,
    and removes the ongoing progress notification.
    """
    # Clean up the ongoing progress notification first
    remove_ongoing_notification()

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
        toast=True,
        ongoing=False,
        alert_once=False
    )
    if is_termux():
        if sent:
            log_print(":bell: [bold green]Completion notification sent to device.[/bold green] :iphone:")
        else:
            log_print(":information_source: [dim]Termux detected. (Install 'pkg install termux-api' for Android notifications)[/dim]")


def check_internet_connection(timeout: float = 2.5) -> bool:
    """
    Checks if general internet connection is active by pinging reliable global DNS servers.
    Returns True if reachable, False if offline (airplane mode, Wi-Fi off, cellular data off).
    """
    test_hosts = [
        ("8.8.8.8", 53),
        ("1.1.1.1", 53),
        ("9.9.9.9", 53),
        ("www.google.com", 80),
    ]
    for host, port in test_hosts:
        try:
            sock = socket.create_connection((host, port), timeout=timeout)
            sock.close()
            return True
        except Exception:
            continue
    return False


def check_instagram_connectivity(timeout: float = 3.5, proxy_url: Optional[str] = None) -> bool:
    """
    Checks if Instagram servers are reachable.
    In regions with internet filtering (e.g. Iran), general internet works but Instagram
    is blocked unless a VPN or proxy is connected.
    Returns True if Instagram is reachable, False if blocked or connection fails.
    """
    proxy = proxy_url or os.environ.get("IG_PROXY") or os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")

    # 1. If proxy is configured, test connection through proxy
    if proxy and proxy.strip():
        try:
            proxy_clean = proxy.strip()
            proxy_handler = urllib.request.ProxyHandler({"http": proxy_clean, "https": proxy_clean})
            opener = urllib.request.build_opener(proxy_handler)
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            req = urllib.request.Request(
                "https://i.instagram.com/api/v1/health_check/",
                headers={"User-Agent": "Instagram 219.0.0.12.117 Android"}
            )
            opener.open(req, timeout=timeout)
            return True
        except urllib.error.HTTPError:
            # An HTTP response (400, 403, 404) proves reaching Instagram's server!
            return True
        except Exception:
            return False

    # 2. Direct TCP connection to Instagram servers (verifies VPN tunnel is routing Instagram)
    ig_hosts = [
        ("i.instagram.com", 443),
        ("www.instagram.com", 443),
        ("graph.instagram.com", 443),
    ]
    for host, port in ig_hosts:
        try:
            sock = socket.create_connection((host, port), timeout=timeout)
            sock.close()
            return True
        except Exception:
            continue

    # 3. HTTP probe fallback
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(
            "https://i.instagram.com/api/v1/health_check/",
            headers={"User-Agent": "Instagram 219.0.0.12.117 Android"}
        )
        with urllib.request.urlopen(req, timeout=timeout, context=ctx):
            return True
    except urllib.error.HTTPError:
        return True
    except Exception:
        pass

    return False


def diagnose_connection(proxy_url: Optional[str] = None) -> str:
    """
    Diagnoses current network status:
    - 'ONLINE': Both general internet and Instagram are fully accessible.
    - 'INTERNET_OFFLINE': General internet connection is down.
    - 'VPN_DISCONNECTED': Internet is UP, but Instagram is blocked/unreachable (VPN required).
    """
    if not check_internet_connection():
        return "INTERNET_OFFLINE"
    if not check_instagram_connectivity(proxy_url=proxy_url):
        return "VPN_DISCONNECTED"
    return "ONLINE"


def notify_connection_error(
    action_name: str = "Instagram Operation",
    status_type: str = "INTERNET_OFFLINE",
    error_detail: str = ""
) -> None:
    """
    Suppressed per user specification:
    Disconnection error notifications are strictly disabled so the user is not disturbed.
    The bot automatically pauses, monitors connectivity in the background, and resumes
    seamlessly once the Internet/VPN connection is re-established.
    """
    # Silently pass - do not disturb user with error notifications
    return


def notify_connection_restored(action_name: str = "Instagram Operation") -> None:
    """
    Quietly logs or sends a lightweight resumption notification if configured.
    """
    pass


def wait_for_connection(
    action_name: str = "Instagram Operation",
    exc: Optional[Exception] = None,
    check_interval: int = 4,
    timeout_seconds: Optional[int] = None
) -> bool:
    """
    Pauses operations automatically when connection is lost and continuously monitors status:
    1. If general internet is down -> pauses and waits until internet connects.
    2. If VPN is down -> waits until VPN connects completely and Instagram is reachable.
    Automatically resumes the operation once connection is restored without sending error notifications.
    User can press Ctrl+C to safely stop and preserve progress.
    """
    start_time = time.time()
    err_text = str(exc) if exc else "Connection drop / network timeout"
    status_type = diagnose_connection()

    # Per user request: DO NOT send notification on connection errors!
    # All recovery is performed completely automatically in the background.

    # Render Termux-optimized diagnostic banner
    from rich.panel import Panel
    from rich.table import Table

    is_compact = is_compact_terminal()

    if status_type == "INTERNET_OFFLINE":
        status_badge = "[bold red]:satellite: INTERNET OFFLINE (No Network Connection)[/bold red]"
        tip_text = "Check Wi-Fi or mobile data. Bot is auto-waiting for internet..."
    elif status_type == "VPN_DISCONNECTED":
        status_badge = "[bold yellow]:shield: VPN DISCONNECTED (Instagram Unreachable)[/bold yellow]"
        tip_text = "Reconnect your VPN. Bot is auto-waiting for VPN / Instagram..."
    else:
        status_badge = "[bold magenta]:warning: CONNECTION DROPPED / RESET[/bold magenta]"
        tip_text = "Socket reset. Bot is verifying connection..."

    if is_compact:
        card_content = (
            f"{status_badge}\n\n"
            f"[bold white]Action Paused:[/bold white] [cyan]{action_name}[/cyan]\n"
            f"[dim]Error: {err_text[:65]}[/dim]\n\n"
            f"[yellow]💡 Status:[/yellow] {tip_text}\n"
            f"[green]:hourglass_flowing_sand: Auto-monitoring... Will resume automatically once connected.[/green]\n"
            f"[dim](Press Ctrl+C to cancel and save progress safely)[/dim]"
        )
    else:
        card_table = Table(box=None, padding=(0, 2), show_header=False)
        card_table.add_row("[bold white]Current Status:[/bold white]", status_badge)
        card_table.add_row("[bold white]Paused Operation:[/bold white]", f"[cyan]{action_name}[/cyan]")
        card_table.add_row("[bold white]Error Detail:[/bold white]", f"[italic dim]{err_text[:80]}[/italic dim]")
        card_table.add_row("[bold white]Notice:[/bold white]", f"[yellow]{tip_text}[/yellow]")
        card_table.add_row(
            "[bold white]Auto Recovery:[/bold white]",
            "[green]Monitoring connection every few seconds. Operation will resume automatically![/green]"
        )
        card_table.add_row("[bold white]Safe Exit:[/bold white]", "[dim]Press Ctrl+C to stop and save progress in SQLite database[/dim]")
        card_content = card_table

    console.print()
    console.print(Panel(
        card_content,
        title=em(":satellite: [bold red]Connection Paused | Auto-Waiting for Internet / VPN[/bold red]"),
        border_style="red"
    ))
    console.print()

    # Continuous Auto-Check Loop
    attempt = 1
    last_status = status_type

    dash = None
    try:
        from src.utils.dashboard import get_active_dashboard
        dash = get_active_dashboard()
    except Exception:
        pass

    if dash:
        dash.set_status("WAITING_NETWORK", f"Paused: Waiting for {status_type.replace('_', ' ').title()}")
    else:
        update_ongoing_progress_notification(
            bot_title="Instagram Bot",
            current_step=f"Paused: Waiting for {status_type.replace('_', ' ').title()}",
            processed_count=0,
            total_items=0,
            status="WAITING_NETWORK",
            force=True
        )

    while True:
        # Check timeout if specified
        if timeout_seconds and (time.time() - start_time) > timeout_seconds:
            log_warning(f":stop_sign: Reconnection wait timed out after {timeout_seconds} seconds.")
            return False

        try:
            # 1. First check: General Internet
            has_internet = check_internet_connection()
            if not has_internet:
                status_msg = f"[yellow]:satellite: Check #{attempt}: Internet is Offline... Waiting for connection[/yellow]"
                if last_status != "INTERNET_OFFLINE":
                    last_status = "INTERNET_OFFLINE"
                    log_warning(":satellite: Internet offline. Paused, waiting for connection...")
                    if dash:
                        dash.set_status("WAITING_NETWORK", f"Internet Offline... Waiting for network")
                    else:
                        update_ongoing_progress_notification(
                            bot_title="Instagram Bot",
                            current_step=f"Internet Offline... Waiting for network (Check #{attempt})",
                            processed_count=0,
                            total_items=0,
                            status="WAITING_NETWORK",
                            force=True
                        )

                with console.status(em(f"{status_msg} [dim](Rechecking in {check_interval}s)[/dim]"), spinner="dots"):
                    time.sleep(check_interval)
                attempt += 1
                continue

            # 2. Second check: Instagram / VPN
            has_ig = check_instagram_connectivity()
            if not has_ig:
                status_msg = f"[cyan]:shield: Check #{attempt}: Internet is connected! Waiting for VPN to Instagram...[/cyan]"
                if last_status != "VPN_DISCONNECTED":
                    last_status = "VPN_DISCONNECTED"
                    log_print(":information_source: Internet connected. Waiting for VPN to reach Instagram...")
                    if dash:
                        dash.set_status("WAITING_NETWORK", f"Waiting for VPN to reach Instagram")
                    else:
                        update_ongoing_progress_notification(
                            bot_title="Instagram Bot",
                            current_step=f"Waiting for VPN to reach Instagram (Check #{attempt})",
                            processed_count=0,
                            total_items=0,
                            status="WAITING_NETWORK",
                            force=True
                        )

                with console.status(em(f"{status_msg} [dim](Rechecking in {check_interval}s)[/dim]"), spinner="dots"):
                    time.sleep(check_interval)
                attempt += 1
                continue

            # 3. Both Internet and Instagram are reachable!
            # Brief check to ensure socket stability
            time.sleep(1.5)
            if check_instagram_connectivity():
                if dash:
                    dash.set_status("RUNNING", "Connection restored! Resuming operations...")
                console.print()
                log_success(":white_check_mark: Full connection restored! Internet and VPN are active. Resuming automatically... :sparkles:")
                # Small settle delay before resuming API requests
                time.sleep(1.0)
                return True

        except KeyboardInterrupt:
            console.print()
            log_warning("\n:pause_button: Wait interrupted by user.")
            try:
                should_abort = ask_yes_no(
                    english_question="Do you want to stop the bot and safely save progress? (Yes to Stop, No to Keep Waiting)",
                    default=True
                )
                if should_abort:
                    log_warning(":stop_sign: Operation cancelled by user. Progress is saved in SQLite database. :floppy_disk:")
                    return False
                else:
                    log_print(":hourglass_flowing_sand: Resuming connection monitoring...")
                    continue
            except KeyboardInterrupt:
                log_warning(":stop_sign: Force interrupted. Progress is saved in SQLite database. :floppy_disk:")
                return False


def handle_connection_recovery(exc: Optional[Exception] = None, action_name: str = "Instagram Operation") -> bool:
    """
    Standard recovery handler called when a network error is caught.
    Invokes wait_for_connection to automatically monitor and wait for internet/VPN.
    Returns True when reconnected so the caller can retry, or False to cancel.
    """
    return wait_for_connection(action_name=action_name, exc=exc)
