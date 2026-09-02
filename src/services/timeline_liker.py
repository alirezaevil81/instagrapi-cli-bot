"""
Timeline Feed Liker Service: Automatically fetches all available posts from your Instagram timeline feed,
sorts them from newest to oldest, likes them, and continuously refreshes the feed in recurring cycles.
"""
import os
import sys
import time
from random import randint
import questionary
from rich.table import Table
from rich import box

from src.core.client import Bot
from src.config import load_comments
from src.database.engine import init_db
from src.database.repository import has_recent_interaction
from src.utils import (
    log_print,
    log_sleep,
    show_banner,
    show_section_divider,
    show_stats_card,
    console,
    log_error,
    log_warning,
    log_success,
    fix_persian,
    format_bilingual_prompt,
    ask_yes_no,
    ask_delay_range,
    ask_choice_or_custom,
    register_graceful_shutdown,
    em
)

def format_relative_time(timestamp: float) -> str:
    """Returns human-readable relative time like '15m ago' or '2h 10m ago'."""
    diff = max(0, int(time.time() - timestamp))
    if diff < 60:
        return f"{diff}s ago"
    elif diff < 3600:
        mins = diff // 60
        return f"{mins}m ago"
    elif diff < 86400:
        hours = diff // 3600
        mins = (diff % 3600) // 60
        return f"{hours}h {mins}m ago" if mins > 0 else f"{hours}h ago"
    else:
        days = diff // 86400
        return f"{days}d ago"

def display_timeline_posts_table(posts: list) -> None:
    """Renders a beautiful Rich Table showing all timeline posts sorted newest to oldest."""
    table = Table(
        title=em(f":newspaper: [bold cyan]{fix_persian('پست‌های استخراج‌شده فید تایم‌لاین')}[/bold cyan] [dim](Newest :arrow_right: Oldest)[/dim]"),
        box=box.ROUNDED,
        show_header=True,
        header_style="bold magenta",
        expand=True
    )
    table.add_column(em(":hash: #"), style="dim", width=4, justify="center")
    table.add_column(em(":bust_in_silhouette: Author"), style="bold cyan", width=18)
    table.add_column(em(":clock1: Published"), style="green", width=14, justify="center")
    table.add_column(em(":chart_with_upwards_trend: Stats"), style="yellow", width=16, justify="center")
    table.add_column(em(":memo: Caption"), style="white")
    table.add_column(em(":pushpin: Status"), style="bold", width=18, justify="center")

    for i, post in enumerate(posts, start=1):
        rel_time = format_relative_time(post["taken_at_ts"])
        stats_str = em(f":heart: {post.get('like_count', 0)} | :speech_balloon: {post.get('comment_count', 0)}")
        caption = (post.get("caption_text", "") or "").replace("\n", " ")
        if len(caption) > 40:
            caption = caption[:37] + "..."
        caption_disp = fix_persian(caption) if caption else "[dim]No caption[/dim]"
        
        is_already_liked = post.get("has_liked", False) or has_recent_interaction(post["pk"], "like")
        if is_already_liked:
            status = em("[dim green]:white_check_mark: Already Liked[/dim green]")
        else:
            status = em("[bold yellow]:hourglass: Pending Like[/bold yellow]")

        table.add_row(
            str(i),
            f"@{post['author_username']}",
            rel_time,
            stats_str,
            caption_disp,
            status
        )

    console.print(table)
    console.print()

def main():
    init_db()
    register_graceful_shutdown()

    # ----------------- Start & Login -----------------
    show_banner(
        "Timeline Feed Liker Bot",
        "Continuous Timeline Feed Posts Liker (Newest to Oldest) with Auto-Refresh"
    )

    bot = Bot()
    bot.start()

    if not getattr(bot, 'user_id', None):
        log_error("Not logged in. Exiting.")
        sys.exit(0)

    # ----------- Interactive Configuration (Questionary) --------------
    console.print(f"\n[bold cyan]:gear: Configure Timeline Bot Parameters[/bold cyan]\n  [dim]↪ {fix_persian('تنظیم پارامترهای تایم‌لاین فید')}[/dim]")

    # Warm-up option (Selectable Yes/No)
    enable_warmup = ask_yes_no(
        "Perform natural account warm-up actions before starting?",
        "انجام آماده‌سازی و رفتار ارگانیک قبل از شروع ربات؟",
        default=True
    )

    # Max pages to paginate per cycle (Presets + Custom)
    max_pages = ask_choice_or_custom(
        english_title="Select max feed pages to fetch per cycle",
        persian_title="حداکثر صفحات فید برای دریافت در هر دور",
        options=[
            (3, "3 pages", "سریع و سبک", ":zap:"),
            (6, "6 pages", "پیشنهادی و استاندارد", ":shield:"),
            (10, "10 pages", "عمیق‌تر", ":mag:"),
            (15, "15 pages", "حداکثر فید", ":rocket:"),
        ],
        default_val=6,
        custom_prompt_en="Enter custom max pages count",
        custom_prompt_fa="تعداد صفحات دلخواه را وارد کنید",
        val_type=int
    )

    # Like delay configuration with presets (25-50s, 60-90s, 90-150s, Custom)
    bot.like_delay_range = ask_delay_range("likes (لایک‌ها)", default_range=[60, 90])

    # Refresh cooldown between cycles (Presets + Custom)
    refresh_cooldown_min = ask_choice_or_custom(
        english_title="Select cooldown before refreshing timeline feed again (minutes)",
        persian_title="فاصله زمانی استراحت تا رفرش مجدد فید به دقیقه",
        options=[
            (1, "1 minute", "سریع", ":zap:"),
            (3, "3 minutes", "پیشنهادی و امن", ":shield:"),
            (5, "5 minutes", "محافظه‌کارانه", ":hourglass:"),
            (10, "10 minutes", "استراحت طولانی", ":sleeping:"),
        ],
        default_val=3,
        custom_prompt_en="Enter custom cooldown minutes",
        custom_prompt_fa="دقیقه استراحت دلخواه را وارد کنید",
        val_type=float
    )
    refresh_cooldown_seconds = int(refresh_cooldown_min * 60)

    # Commenting toggle (Selectable Yes/No)
    commenting = ask_yes_no(
        "Enable automated comments on timeline posts?",
        "ارسال خودکار کامنت روی پست‌های تایم‌لاین؟",
        default=False
    )
    if commenting:
        current_comments = load_comments()
        if not current_comments:
            log_warning("Notice: [bold yellow]comments.txt[/bold yellow] is currently empty. Please write your custom comments into [bold yellow]comments.txt[/bold yellow]! :warning:")
        else:
            log_print(f"Automated commenting is [bold green]ENABLED[/bold green] ({len(current_comments)} comments loaded from [bold yellow]comments.txt[/bold yellow]) :white_check_mark:")
        bot.comment_delay_range = ask_delay_range("comments (کامنت‌ها)", default_range=[60, 90])

    # Story Interaction Toggle (Selectable Yes/No)
    story_interaction = ask_yes_no(
        "Enable automated story viewing & liking for authors with active stories?",
        "مشاهده و لایک خودکار تمام استوری‌های فعال منتشرکننده پست؟",
        default=True
    )
    if story_interaction:
        log_print("Automated Story Viewing & Liking is [bold green]ENABLED (All Active Stories)[/bold green] :clapper: :heart:")
        bot.story_delay_range = ask_delay_range("story interactions (تعامل با استوری)", default_range=[2, 5])
    else:
        log_print("Automated Story Interaction is [bold red]DISABLED[/bold red] :cross_mark:")

    # Execute warm-up if enabled
    if enable_warmup:
        bot.perform_warmup_actions(max_feed_items=4, view_stories=True)

    console.print(f"\n[bold green]:rocket: Starting Continuous Timeline Liker Bot...[/bold green]\n")

    # ------------ Continuous Feed Refresh & Like Loop ------------
    round_num = 0
    total_liked_all_time = 0
    total_stories_seen_all_time = 0
    total_stories_liked_all_time = 0

    try:
        while True:
            round_num += 1
            mins_text = f"{refresh_cooldown_seconds // 60}m" if refresh_cooldown_seconds >= 60 else f"{refresh_cooldown_seconds}s"
            show_section_divider(f":repeat: Round {round_num}: Refreshing Timeline Feed", style="bold magenta")
            log_print(f"Fetching up to [bold cyan]{max_pages}[/bold cyan] pages of timeline feed... :hourglass:")

            # 1. Fetch posts from timeline feed (all available posts, no time filter)
            recent_posts = bot.fetch_timeline_feed_posts_24h(
                max_pages=max_pages,
                cutoff_hours=0.0,
                fallback_if_empty=True
            )

            if not recent_posts:
                log_warning("No posts found in your timeline feed. :warning:")
                log_sleep(
                    refresh_cooldown_seconds,
                    message=f"Waiting {mins_text} before next feed refresh"
                )
                continue

            log_success(f"Retrieved [bold cyan]{len(recent_posts)}[/bold cyan] total posts from timeline feed :newspaper:")

            # 2. Display extracted posts in table
            display_timeline_posts_table(recent_posts)

            # 3. Filter unliked posts (newest to oldest)
            unliked_posts = [
                p for p in recent_posts
                if not p.get("has_liked", False) and not has_recent_interaction(p["pk"], "like")
            ]

            if not unliked_posts:
                log_success(f":sparkles: [bold green]All {len(recent_posts)} posts in the current feed are already liked![/bold green]")
                log_print(f"Cooling down for [bold cyan]{mins_text}[/bold cyan] before refreshing timeline for new incoming posts... :sleeping:")
                log_sleep(
                    refresh_cooldown_seconds,
                    message=f"Feed up-to-date. Next refresh in {mins_text}"
                )
                continue

            log_print(f"Found [bold yellow]{len(unliked_posts)}[/bold yellow] unliked posts to process in order from [bold green]NEWEST :arrow_right: OLDEST[/bold green] :heart_eyes:")

            round_liked_count = 0
            round_stories_seen = 0
            round_stories_liked = 0

            # 4. Iterate and process authors & like posts from newest to oldest
            for idx, post in enumerate(unliked_posts, start=1):
                pk = post["pk"]
                author = post["author_username"]
                author_pk = post["author_pk"]
                rel_time = format_relative_time(post["taken_at_ts"])

                console.print(f"\n[bold cyan]─── [:camera: Post {idx}/{len(unliked_posts)}] ───[/bold cyan] @[bold yellow]{author}[/bold yellow] ([green]:clock1: {rel_time}[/green]) | :id: PK: {pk}")

                # Step 0: Process all active stories of author (View + Like non-randomly)
                if story_interaction and author_pk:
                    st_seen, st_liked = bot.process_user_stories(
                        user_pk=str(author_pk),
                        username=str(author),
                        delay_range=bot.story_delay_range,
                        like_stories=True
                    )
                    round_stories_seen += st_seen
                    round_stories_liked += st_liked
                    total_stories_seen_all_time += st_seen
                    total_stories_liked_all_time += st_liked

                # Step A: Mark post as seen (Natural Impression)
                bot.seen_user_post(pk, username=author, user_pk=author_pk)

                # Step B: Natural dwell pause (1-3s)
                view_dwell = randint(1, 3)
                log_sleep(view_dwell, message=f"Viewing feed post ({view_dwell}s)")

                # Step C: Like post
                liked = bot.like_user_post(
                    pk,
                    delay_range=bot.like_delay_range,
                    username=author,
                    user_pk=author_pk
                )

                if liked:
                    round_liked_count += 1
                    total_liked_all_time += 1

                # Step D: Optional Comment
                if commenting and liked:
                    bot.comment_user_post(
                        pk,
                        delay_range=bot.comment_delay_range,
                        username=author,
                        user_pk=author_pk
                    )

            # 5. Round Completion & Summary
            round_stats = {
                ":target: New Posts Liked This Round": f"[bold green]{round_liked_count}[/bold green]",
                ":star: Total Posts Liked (Session)": f"[bold magenta]{total_liked_all_time}[/bold magenta]"
            }
            if story_interaction:
                round_stats[":clapper: Stories Viewed (Round / Total)"] = f"[bold cyan]{round_stories_seen} / {total_stories_seen_all_time}[/bold cyan]"
                round_stats[":heart: Stories Liked (Round / Total)"] = f"[bold green]{round_stories_liked} / {total_stories_liked_all_time}[/bold green]"

            round_stats[":newspaper: Feed Posts Scanned"] = f"[bold cyan]{len(recent_posts)}[/bold cyan]"
            round_stats[":repeat: Next Refresh"] = f"[bold yellow]{mins_text}[/bold yellow]"

            show_stats_card(
                f"Round {round_num} Statistics",
                round_stats,
                border_style="green"
            )

            # 6. Cooldown before refreshing feed again
            mins_text = f"{refresh_cooldown_seconds // 60}m" if refresh_cooldown_seconds >= 60 else f"{refresh_cooldown_seconds}s"
            log_warning(f":repeat: Refreshing timeline feed in [bold cyan]{mins_text}[/bold cyan] for next batch... :coffee:")
            log_sleep(
                refresh_cooldown_seconds,
                message=f"Cooling down before refreshing timeline (Round {round_num + 1})"
            )

    except KeyboardInterrupt:
        log_warning("\n:stop_sign: Timeline Feed Liker Bot stopped safely by user.")
        summary_stats = {
            ":heart: Total Liked Posts": f"[bold green]{total_liked_all_time}[/bold green]",
            ":repeat: Total Rounds Run": f"[bold cyan]{round_num}[/bold cyan]"
        }
        if story_interaction:
            summary_stats[":clapper: Total Stories Viewed"] = f"[bold cyan]{total_stories_seen_all_time}[/bold cyan]"
            summary_stats[":heart: Total Stories Liked"] = f"[bold green]{total_stories_liked_all_time}[/bold green]"

        show_stats_card(
            "Session Summary (Stopped)",
            summary_stats,
            border_style="yellow"
        )

if __name__ == "__main__":
    main()
