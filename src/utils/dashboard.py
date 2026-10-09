"""
Live Operational Dashboard for Instagram CLI Bot.
Provides an interactive real-time dashboard display using rich.live.Live
instead of standard scrolling log stream.
Features:
- Dynamic header with active bot mode, logged-in account, and status badge
- Live statistics cards (Target, Processed, Liked, Stories, Comments, Success Rate)
- Smooth animated progress bar with ETA & elapsed timer
- Current operational state & active target inspection
- Live dynamic activity feed (last 4-6 actions)
- Termux & compact mobile terminal auto-adaptation
"""
import time
from typing import Optional, List, Dict, Any
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn, TimeRemainingColumn, SpinnerColumn
from rich import box
from rich.align import Align
from rich.columns import Columns

from src.utils.console import console, em, is_compact_terminal, format_seconds
from src.utils.logger import get_file_logger, clean_rich_markup
from src.utils.notifier import (
    update_ongoing_progress_notification,
    remove_ongoing_notification
)


class LiveDashboard:
    """
    Real-time interactive dashboard managing a rich.live.Live context.
    Displays live metrics, progress, current activity, and action history
    without terminal log spamming.
    """

    def __init__(
        self,
        bot_title: str = "Instagram Automation Bot",
        total_items: int = 0,
        account_name: str = "Connected Account",
        refresh_per_second: float = 4.0
    ):
        self.bot_title = bot_title
        self.total_items = max(0, total_items)
        self.account_name = account_name
        self.refresh_per_second = refresh_per_second

        # Metrics
        self.processed_count: int = 0
        self.liked_count: int = 0
        self.stories_viewed_count: int = 0
        self.stories_liked_count: int = 0
        self.comments_count: int = 0
        self.skipped_count: int = 0
        self.errors_count: int = 0

        # Current State
        self.status: str = "RUNNING"  # RUNNING, COOLDOWN, SLEEPING, PAUSED, WAITING_NETWORK, FINISHED
        self.current_step: str = "Initializing session..."
        self.current_target: str = "-"
        self.round_num: int = 1

        # Countdown / Sleep tracking
        self.sleep_total: int = 0
        self.sleep_remaining: int = 0
        self.sleep_label: str = ""

        # Activity feed history (latest entries)
        self.recent_activities: List[Dict[str, str]] = []
        self.max_activities: int = 5 if is_compact_terminal() else 7

        # Timing
        self.start_time: float = time.time()

        # Persistent Notification Configuration
        self.enable_persistent_notification: bool = True
        self.persistent_notification_id: str = "instagrapi_ongoing_progress"

        # Rich Live Instance
        self._live: Optional[Live] = None
        self._is_active: bool = False

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def _sync_persistent_notification(self, force: bool = False):
        """Pushes current operation stage and percentage remaining to persistent Android notification."""
        if not self.enable_persistent_notification:
            return
        try:
            update_ongoing_progress_notification(
                bot_title=self.bot_title,
                current_step=self.current_step,
                processed_count=self.processed_count,
                total_items=self.total_items,
                status=self.status,
                target=self.current_target,
                force=force,
                notification_id=self.persistent_notification_id
            )
        except Exception:
            pass

    def start(self):
        """Starts the Rich Live context."""
        if not self._is_active:
            set_active_dashboard(self)
            self._live = Live(
                self._render_view(),
                console=console,
                refresh_per_second=self.refresh_per_second,
                transient=False
            )
            self._live.start()
            self._is_active = True
            self._sync_persistent_notification(force=True)

    def stop(self):
        """Stops the Rich Live context cleanly and dismisses ongoing notification."""
        if self._is_active and self._live:
            try:
                self.update_render()
                self._live.stop()
            except Exception:
                pass
            self._is_active = False
            self._live = None
            if get_active_dashboard() is self:
                set_active_dashboard(None)
            try:
                remove_ongoing_notification(self.persistent_notification_id)
            except Exception:
                pass

    def refresh(self):
        """Forces immediate screen refresh."""
        if self._is_active and self._live:
            self._live.update(self._render_view(), refresh=True)
            self._sync_persistent_notification(force=False)

    def update_render(self):
        """Updates the Live display view."""
        if self._is_active and self._live:
            self._live.update(self._render_view())
            self._sync_persistent_notification(force=False)

    # -------------------------------------------------------------
    # State & Metric Updaters
    # -------------------------------------------------------------
    def set_target(self, username: str, step: str = "Engaging target"):
        """Sets the current target username and current action step."""
        self.current_target = f"@{username}" if username and not username.startswith("@") else (username or "-")
        self.current_step = step
        self.status = "RUNNING"
        self.sleep_remaining = 0
        self.update_render()
        self._sync_persistent_notification(force=True)

    def set_status(self, status: str, step: str = ""):
        """Sets general status badge."""
        self.status = status
        if step:
            self.current_step = step
        self.update_render()
        self._sync_persistent_notification(force=True)

    def set_round(self, round_num: int):
        """Updates loop round count."""
        self.round_num = round_num
        self.update_render()
        self._sync_persistent_notification(force=True)

    def set_total(self, total: int):
        """Updates total target items."""
        self.total_items = max(0, total)
        self.update_render()
        self._sync_persistent_notification(force=True)

    def record_action(
        self,
        action_type: str,  # 'like', 'story_view', 'story_like', 'comment', 'skip', 'error'
        target: str,
        detail: str = "",
        success: bool = True
    ):
        """Records an action into metrics and recent activity feed."""
        t_str = f"@{target}" if target and not target.startswith("@") else (target or "-")
        now_str = time.strftime("%H:%M:%S")

        if action_type == "like":
            if success:
                self.liked_count += 1
            else:
                self.errors_count += 1
            icon = ":heart:" if success else ":cross_mark:"
            act_text = f"Liked post {detail}" if detail else "Liked post"
        elif action_type == "story_view":
            self.stories_viewed_count += 1
            icon = ":eyes:"
            act_text = f"Viewed story {detail}" if detail else "Viewed active story"
        elif action_type == "story_like":
            self.stories_liked_count += 1
            icon = ":clapper:"
            act_text = "Liked story"
        elif action_type == "comment":
            if success:
                self.comments_count += 1
            else:
                self.errors_count += 1
            icon = ":speech_balloon:"
            act_text = f"Commented: '{detail[:30]}...'" if len(detail) > 30 else f"Commented: '{detail}'"
        elif action_type == "skip":
            self.skipped_count += 1
            icon = ":fast_forward:"
            act_text = f"Skipped: {detail}" if detail else "Skipped"
        elif action_type == "network_wait":
            icon = ":satellite:"
            act_text = f"Paused: {detail}"
        else:
            icon = ":information_source:"
            act_text = detail or action_type

        # Add to activities
        self.recent_activities.insert(0, {
            "time": now_str,
            "icon": icon,
            "target": t_str,
            "action": act_text,
            "status": "[green]OK[/green]" if success else "[red]FAIL[/red]"
        })

        if len(self.recent_activities) > self.max_activities:
            self.recent_activities = self.recent_activities[:self.max_activities]

        # Log to permanent file
        try:
            get_file_logger().info(clean_rich_markup(f"[{action_type.upper()}] {t_str} - {act_text}"))
        except Exception:
            pass

        self.update_render()

    def advance_processed(self, amount: int = 1):
        """Increments processed items counter."""
        self.processed_count += amount
        self.update_render()

    def live_sleep(self, seconds: int, message: str = "Safety Cooldown"):
        """
        Executes a real-time countdown delay right inside the live dashboard
        without printing noisy sleep rows.
        """
        if seconds <= 0:
            return

        self.status = "COOLDOWN"
        self.sleep_total = int(seconds)
        self.sleep_label = message
        self._sync_persistent_notification(force=True)

        for remaining in range(self.sleep_total, 0, -1):
            self.sleep_remaining = remaining
            self.current_step = f"{message} ({format_seconds(remaining)} remaining)"
            self.refresh()
            if remaining % 3 == 0 or remaining == self.sleep_total:
                self._sync_persistent_notification(force=False)
            time.sleep(1)

        self.sleep_remaining = 0
        self.status = "RUNNING"
        self.current_step = "Resuming actions..."
        self.refresh()
        self._sync_persistent_notification(force=True)

    # -------------------------------------------------------------
    # Dashboard View Builder
    # -------------------------------------------------------------
    def _render_view(self) -> Panel:
        """Constructs the comprehensive Rich layout panel."""
        compact = is_compact_terminal()

        # 1. Header Banner
        header_text = self._build_header(compact)

        # 2. Key Metrics Grid
        metrics_table = self._build_metrics_grid(compact)

        # 3. Live Progress & Timers
        progress_table = self._build_progress_section(compact)

        # 4. Current Target & Operational Status Card
        current_state_panel = self._build_current_state(compact)

        # 5. Live Activity Feed (Latest Events)
        activity_table = self._build_activity_feed(compact)

        # Assemble layout table
        main_table = Table(box=None, padding=(0, 0), show_header=False, expand=True)
        main_table.add_column("Dashboard", justify="left")

        main_table.add_row(header_text)
        main_table.add_row(Text(""))
        main_table.add_row(metrics_table)
        main_table.add_row(Text(""))
        main_table.add_row(progress_table)
        main_table.add_row(Text(""))
        main_table.add_row(current_state_panel)
        main_table.add_row(Text(""))
        main_table.add_row(activity_table)

        # Wrap in Master Panel
        border_col = "cyan" if self.status == "RUNNING" else ("yellow" if self.status == "COOLDOWN" else "green")
        title_tag = em(f":zap: [bold white]LIVE OPERATION DASHBOARD[/bold white] [bold yellow]v0.2.0[/bold yellow]")
        
        return Panel(
            main_table,
            title=title_tag,
            subtitle=em("[dim bright_white]Press Ctrl+C to safely pause/stop with saved SQLite state[/dim bright_white]"),
            border_style=border_col,
            box=box.ROUNDED,
            padding=(0, 1) if compact else (1, 2)
        )

    def _build_header(self, compact: bool) -> Table:
        """Header with mode name, logged-in user, and live status badge."""
        t = Table(box=None, padding=(0, 1), show_header=False, expand=True)
        t.add_column("Left", justify="left", ratio=3)
        t.add_column("Right", justify="right", ratio=2)

        status_badge = {
            "RUNNING": "[bold black on #00ffaa] ● ACTIVE [/bold black on #00ffaa]",
            "COOLDOWN": "[bold black on #facc15] ⏱ COOLDOWN [/bold black on #facc15]",
            "SLEEPING": "[bold white on #3b82f6] 💤 SLEEPING [/bold white on #3b82f6]",
            "PAUSED": "[bold white on #ef4444] ⏸ PAUSED [/bold white on #ef4444]",
            "WAITING_NETWORK": "[bold white on #ec4899] 📡 RECONNECTING [/bold white on #ec4899]",
            "FINISHED": "[bold black on #10b981] ✔ COMPLETED [/bold black on #10b981]"
        }.get(self.status, "[bold white on blue] ● ACTIVE [/bold white on blue]")

        acc_badge = f"[bold green]@{self.account_name}[/bold green]" if self.account_name else "[dim]Guest[/dim]"

        if compact:
            title_line = f"[bold magenta]{self.bot_title}[/bold magenta] (R#{self.round_num})"
            info_line = f"User: {acc_badge} | {status_badge}"
            t.add_row(em(title_line), em(info_line))
        else:
            left = em(f"[bold magenta]{self.bot_title}[/bold magenta]  [dim]•[/dim]  Cycle: [bold yellow]Round #{self.round_num}[/bold yellow]")
            right = em(f"Account: {acc_badge}  {status_badge}")
            t.add_row(left, right)

        return t

    def _build_metrics_grid(self, compact: bool) -> Table:
        """Table grid displaying key operational metrics."""
        grid = Table(
            box=box.ROUNDED if not compact else box.SIMPLE,
            border_style="bright_black",
            header_style="bold cyan",
            padding=(0, 1),
            expand=True
        )

        grid.add_column(em(":bar_chart: Progress"), justify="center")
        grid.add_column(em(":heart: Likes"), justify="center")
        grid.add_column(em(":eyes: Stories"), justify="center")
        grid.add_column(em(":speech_balloon: Comments"), justify="center")
        grid.add_column(em(":shield: Success"), justify="center")

        # Calculations
        progress_str = f"[bold white]{self.processed_count}[/bold white]"
        if self.total_items > 0:
            progress_str += f"/[dim]{self.total_items}[/dim]"

        likes_str = f"[bold #ec4899]{self.liked_count}[/bold #ec4899]"
        stories_str = f"[bold cyan]{self.stories_viewed_count}[/bold cyan]"
        if self.stories_liked_count > 0:
            stories_str += f" ([green]♥{self.stories_liked_count}[/green])"

        comments_str = f"[bold yellow]{self.comments_count}[/bold yellow]"

        total_actions = self.liked_count + self.stories_viewed_count + self.comments_count
        if total_actions + self.errors_count > 0:
            rate = int((total_actions / (total_actions + self.errors_count)) * 100)
            rate_str = f"[bold green]{rate}%[/bold green]"
        else:
            rate_str = "[bold green]100%[/bold green]"

        grid.add_row(
            progress_str,
            likes_str,
            stories_str,
            comments_str,
            rate_str
        )
        return grid

    def _build_progress_section(self, compact: bool) -> Table:
        """Visual progress bar and elapsed/remaining timers."""
        t = Table(box=None, padding=(0, 1), show_header=False, expand=True)
        t.add_column("Bar", ratio=3)
        t.add_column("Timers", justify="right", ratio=2)

        elapsed = int(time.time() - self.start_time)
        elapsed_str = format_seconds(elapsed)

        if self.total_items > 0:
            pct = min(100, int((self.processed_count / self.total_items) * 100))
            bar_len = 12 if compact else 26
            filled = int(bar_len * (pct / 100))
            empty = bar_len - filled
            bar_art = f"[bold green]{'━' * filled}[/bold green][bright_black]{'━' * empty}[/bright_black] [bold yellow]{pct}%[/bold yellow]"
            
            # Estimate remaining
            if self.processed_count > 0:
                sec_per_item = elapsed / self.processed_count
                rem_items = max(0, self.total_items - self.processed_count)
                rem_sec = int(rem_items * sec_per_item)
                eta_str = f"ETA: [bold cyan]{format_seconds(rem_sec)}[/bold cyan]"
            else:
                eta_str = "ETA: [dim]calculating...[/dim]"
        else:
            # Continuous mode
            spinner_chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
            idx = int(time.time() * 4) % len(spinner_chars)
            bar_art = f"[bold cyan]{spinner_chars[idx]}[/bold cyan] [italic]Continuous Engagement Loop active[/italic]"
            eta_str = f"Run: [bold cyan]{elapsed_str}[/bold cyan]"

        time_line = f":hourglass: Elapsed: [white]{elapsed_str}[/white] | {eta_str}"
        t.add_row(em(bar_art), em(time_line))
        return t

    def _build_current_state(self, compact: bool) -> Panel:
        """Card showing current target profile and active operation."""
        state_table = Table(box=None, padding=(0, 1), show_header=False, expand=True)
        state_table.add_column("Label", style="bold cyan", width=14 if not compact else 10)
        state_table.add_column("Value", style="white")

        state_table.add_row(em(":target: Current Target:"), f"[bold yellow]{self.current_target}[/bold yellow]")
        state_table.add_row(em(":gear: Current Action:"), f"[white]{self.current_step}[/white]")

        if self.sleep_remaining > 0:
            sec_bar = f"[bold yellow]{self.sleep_remaining}s[/bold yellow] / {self.sleep_total}s"
            state_table.add_row(em(":sleeping: Cooldown Timer:"), sec_bar)

        return Panel(
            state_table,
            title=em(":mag: [bold bright_cyan]Live Operation State[/bold bright_cyan]"),
            border_style="cyan",
            box=box.ROUNDED,
            padding=(0, 1)
        )

    def _build_activity_feed(self, compact: bool) -> Table:
        """Live scrolling feed of latest actions performed."""
        table = Table(
            box=box.SIMPLE_HEAD if not compact else box.SIMPLE,
            padding=(0, 1),
            header_style="bold magenta",
            expand=True
        )

        table.add_column(em(":clock1: Time"), width=9, justify="center")
        table.add_column(em(":bust_in_silhouette: Target"), width=16 if not compact else 13)
        table.add_column(em(":zap: Action"), style="white")
        table.add_column(em("Status"), justify="center", width=8)

        if not self.recent_activities:
            table.add_row("[dim]--:--:--[/dim]", "[dim]-[/dim]", "[italic dim]Waiting for first engagement event...[/italic dim]", "[dim]-[/dim]")
        else:
            for item in self.recent_activities:
                table.add_row(
                    item["time"],
                    f"[bold green]{item['target']}[/bold green]",
                    em(f"{item['icon']} {item['action']}"),
                    item["status"]
                )

        return table


_ACTIVE_DASHBOARD: Optional[LiveDashboard] = None

def get_active_dashboard() -> Optional[LiveDashboard]:
    """Returns the currently active live dashboard instance if running."""
    global _ACTIVE_DASHBOARD
    return _ACTIVE_DASHBOARD

def set_active_dashboard(dash: Optional[LiveDashboard]):
    """Sets the currently active live dashboard."""
    global _ACTIVE_DASHBOARD
    _ACTIVE_DASHBOARD = dash
