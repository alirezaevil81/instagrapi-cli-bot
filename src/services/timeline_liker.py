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
from src.config import load_comments, COMMENTS_FILE_PATH
from src.database.engine import init_db
from src.database.repository import has_recent_interaction
from src.utils import (
    log_print,
    log_sleep,
    show_banner,
    show_section_divider,
    show_stats_card,
    show_session_plan,
    console,
    log_error,
    log_warning,
    log_success,
    format_bilingual_prompt,
    ask_yes_no,
    ask_delay_range,
    ask_choice_or_custom,
    ask_int,
    register_graceful_shutdown,
    em,
    QUESTIONARY_STYLE,
    notify_task_completed,
    handle_connection_recovery,
    LiveDashboard
)
from src.utils.config_memory import prompt_config_mode, save_bot_preferences

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
        title=em(":newspaper: [bold cyan]Extracted Timeline Feed Posts[/bold cyan] [dim](Newest :arrow_right: Oldest)[/dim]"),
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
        caption_disp = caption if caption else "[dim]No caption[/dim]"
        
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
        log_error("Not logged in. Returning to main menu.")
        return

    # ----------------- Smart Memory Check -----------------
    config_mode, saved_pref = prompt_config_mode("Timeline Feed Liker", "timeline_liker")
    if config_mode == "back":
        log_print("Returning to main menu... :back:")
        return

    # ----------- Configuration: Quick vs Custom --------------
    if config_mode == "quick" and saved_pref:
        like_posts = saved_pref.get("like_posts", True)
        story_interaction = saved_pref.get("interact_story", True)
        commenting = saved_pref.get("commenting", False)
        enable_warmup = saved_pref.get("enable_warmup", True)
        max_pages = saved_pref.get("max_pages", 6)
        bot.like_delay_range = saved_pref.get("like_delay_range", [60, 90])
        bot.comment_delay_range = saved_pref.get("comment_delay_range", [60, 90])
        bot.story_delay_range = saved_pref.get("story_delay_range", [30, 60])
        refresh_cooldown_seconds = saved_pref.get("refresh_cooldown_seconds", 180)
        bot.story_view_count = -1 if story_interaction else 0
        bot.story_like_count = 1 if story_interaction else 0
        log_success("Loaded saved preferences for 1-click execution! :rocket:")
    else:
        console.print("\n[bold cyan]:gear: Configure Timeline Bot Modules & Parameters[/bold cyan]")

        kwargs = {"style": QUESTIONARY_STYLE} if QUESTIONARY_STYLE else {}
        selected_actions = questionary.checkbox(
            em("Select timeline interaction actions to perform: (Space to toggle, Enter to confirm)"),
            choices=[
                questionary.Choice(
                    title=em(":heart: Like Feed Posts (Engage home timeline posts)"),
                    value="like_posts",
                    checked=True
                ),
                questionary.Choice(
                    title=em(":clapper: View & Like Author Stories (Watch author's stories)"),
                    value="interact_story",
                    checked=True
                ),
                questionary.Choice(
                    title=em(":speech_balloon: Comment on Feed Posts (Post comments on feed)"),
                    value="commenting",
                    checked=False
                ),
                questionary.Choice(
                    title=em(":zap: Account Warm-up (Simulate natural browsing before start)"),
                    value="warmup",
                    checked=True
                ),
            ],
            **kwargs
        ).ask()

        if selected_actions is None:
            log_warning("Operation cancelled by user.")
            return

        like_posts = "like_posts" in selected_actions
        story_interaction = "interact_story" in selected_actions
        commenting = "commenting" in selected_actions
        enable_warmup = "warmup" in selected_actions

        if not like_posts and not story_interaction and not commenting:
            log_warning("No engagement actions selected. Enabling default feed post likes.")
            like_posts = True

        # Max pages to paginate per cycle (Presets + Custom)
        max_pages = ask_choice_or_custom(
            english_title="Select max feed pages to fetch per cycle",
            options=[
                (3, "3 pages", "Fast & Light", ":zap:"),
                (6, "6 pages", "Recommended & Standard", ":shield:"),
                (10, "10 pages", "Deeper Feed", ":mag:"),
                (15, "15 pages", "Maximum Feed", ":rocket:"),
            ],
            default_val=6,
            custom_prompt_en="Enter custom max pages count",
            val_type=int
        )

        # Like delay configuration with presets
        if like_posts:
            bot.like_delay_range = ask_delay_range("likes", default_range=[60, 90])
        else:
            bot.like_delay_range = [60, 90]

        # Refresh cooldown between cycles (Presets + Custom)
        refresh_cooldown_min = ask_choice_or_custom(
            english_title="Select cooldown before refreshing timeline feed again (minutes)",
            options=[
                (1, "1 minute", "Fast", ":zap:"),
                (3, "3 minutes", "Recommended & Safe", ":shield:"),
                (5, "5 minutes", "Conservative", ":hourglass:"),
                (10, "10 minutes", "Long Rest", ":sleeping:"),
            ],
            default_val=3,
            custom_prompt_en="Enter custom cooldown minutes",
            val_type=float
        )
        refresh_cooldown_seconds = int(refresh_cooldown_min * 60)

        # Commenting configuration
        if commenting:
            current_comments = load_comments()
            if not current_comments:
                log_warning(f"Notice: [bold yellow]{COMMENTS_FILE_PATH}[/bold yellow] is currently empty. Please write your custom comments into [bold yellow]{COMMENTS_FILE_PATH}[/bold yellow]! :warning:")
            else:
                log_print(f"Automated commenting is [bold green]ENABLED[/bold green] ({len(current_comments)} comments loaded from [bold yellow]{COMMENTS_FILE_PATH}[/bold yellow]) :white_check_mark:")
            bot.comment_delay_range = ask_delay_range("comments", default_range=[60, 90])

        # Story Interaction configuration
        if story_interaction:
            log_print("Automated Story Viewing & Liking is [bold green]ENABLED[/bold green] :clapper: :heart:")
            bot.story_view_count = -1
            bot.story_like_count = 1
            bot.story_delay_range = ask_delay_range("story like cooldown", default_range=[30, 60])
        else:
            bot.story_view_count = 0
            bot.story_like_count = 0

        # Save preferences for smart memory
        save_bot_preferences("timeline_liker", {
            "like_posts": like_posts,
            "interact_story": story_interaction,
            "commenting": commenting,
            "enable_warmup": enable_warmup,
            "max_pages": max_pages,
            "like_delay_range": bot.like_delay_range,
            "comment_delay_range": getattr(bot, 'comment_delay_range', [60, 90]),
            "story_delay_range": getattr(bot, 'story_delay_range', [30, 60]),
            "refresh_cooldown_seconds": refresh_cooldown_seconds,
        })
        log_success("Saved configuration to smart memory! :floppy_disk:")

    # Execute warm-up if enabled
    if enable_warmup:
        bot.perform_warmup_actions(max_feed_items=4, view_stories=True)

    # Display Pre-Flight Mission Plan
    session_plan = {
        "Max Pages Per Cycle": f"{max_pages} pages",
        "Post Likes": f"Enabled ({bot.like_delay_range[0]}-{bot.like_delay_range[1]}s)" if like_posts else "[red]Disabled[/red]",
        "Refresh Cooldown": f"{refresh_cooldown_min} minutes ({refresh_cooldown_seconds}s)",
        "Automated Commenting": "Enabled" if commenting else "[red]Disabled[/red]",
        "Story Interaction": f"Enabled (View: {bot.story_view_count}, Like: {bot.story_like_count})" if story_interaction else "[red]Disabled[/red]",
        "Account Warm-up": "Completed" if enable_warmup else "Skipped",
    }
    show_session_plan("Timeline Feed Liker Mission Plan", session_plan)

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

            # 4. Process posts inside Live Operational Dashboard
            with LiveDashboard(
                bot_title="Timeline Feed Liker",
                total_items=len(unliked_posts),
                account_name=getattr(bot, 'username', 'You')
            ) as dash:
                dash.set_round(round_num)
                dash.liked_count = total_liked_all_time
                dash.stories_viewed_count = total_stories_seen_all_time
                dash.stories_liked_count = total_stories_liked_all_time

                for idx, post in enumerate(unliked_posts, start=1):
                    pk = post["pk"]
                    author = post["author_username"]
                    author_pk = post["author_pk"]
                    rel_time = format_relative_time(post["taken_at_ts"])

                    dash.set_target(author, step=f"Checking post {idx}/{len(unliked_posts)} ({rel_time})")

                    # Step 0: Process active stories of author
                    if story_interaction and author_pk:
                        dash.set_target(author, step=f"Scanning active stories")
                        st_seen, st_liked = bot.process_user_stories(
                            user_pk=str(author_pk),
                            username=str(author),
                            delay_range=bot.story_delay_range,
                            view_count=bot.story_view_count,
                            like_count=bot.story_like_count
                        )
                        if st_seen > 0:
                            dash.record_action("story_view", author, f"{st_seen} stories seen")
                        if st_liked > 0:
                            dash.record_action("story_like", author, f"{st_liked} stories liked")
                        round_stories_seen += st_seen
                        round_stories_liked += st_liked
                        total_stories_seen_all_time += st_seen
                        total_stories_liked_all_time += st_liked

                    # Step A: Mark post as seen (Natural Impression)
                    dash.set_target(author, step=f"Viewing feed post {pk}")
                    bot.seen_user_post(pk, username=author, user_pk=author_pk)

                    # Step B: Natural dwell pause (1-3s)
                    view_dwell = randint(1, 3)
                    dash.live_sleep(view_dwell, message=f"Viewing feed post")

                    # Step C: Like post (if enabled)
                    liked = False
                    if like_posts:
                        dash.set_target(author, step=f"Sending like for post {pk}")
                        liked = bot.like_user_post(
                            pk,
                            delay_range=bot.like_delay_range,
                            username=author,
                            user_pk=author_pk
                        )
                        if liked:
                            round_liked_count += 1
                            total_liked_all_time += 1
                            dash.record_action("like", author, f"PK: {pk}", success=True)
                        else:
                            dash.record_action("like", author, f"PK: {pk}", success=False)

                    # Step D: Optional Comment
                    if commenting:
                        dash.set_target(author, step=f"Leaving comment on post {pk}")
                        commented = bot.comment_user_post(
                            pk,
                            delay_range=bot.comment_delay_range,
                            username=author,
                            user_pk=author_pk
                        )
                        if commented:
                            dash.record_action("comment", author, f"PK: {pk}", success=True)

                    dash.advance_processed(1)

                dash.set_status("FINISHED", step="Round processing complete")

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
        notify_task_completed(
            "Timeline Feed Liker",
            f"Bot stopped. Total liked: {total_liked_all_time} feed posts."
        )

if __name__ == "__main__":
    main()
