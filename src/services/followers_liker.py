"""
Followers Liker Service: Automated engagement and interactions for accounts you follow.
"""
import os
import sys
from random import randint
import questionary

from src.core.client import Bot
from src.config import load_comments, COMMENTS_FILE_PATH
from src.database.engine import init_db
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
    format_bilingual_prompt,
    ask_yes_no,
    ask_delay_range,
    ask_choice_or_custom,
    register_graceful_shutdown,
    em
)

def main():
    init_db()
    register_graceful_shutdown()

    # ----------------- Start & Login -----------------
    show_banner("Followers Liker Bot", "Automated Post Liker & Engagement for Your Following List")

    bot = Bot()
    bot.start()

    if not getattr(bot, 'user_id', None):
        log_error("Not logged in. Exiting.")
        sys.exit(0)

    # ----------- Fetch Following List --------------
    followings = bot.get_all_self_following()

    if not followings:
        log_warning("No followings found or unable to fetch followings.")
        sys.exit(0)

    # ----------- Interactive Configuration (Questionary) --------------
    console.print("\n[bold cyan]:gear: Configure Bot Parameters[/bold cyan]")

    # Warm-up option (Selectable Yes/No)
    enable_warmup = ask_yes_no(
        "Perform natural account warm-up actions before starting?",
        default=True
    )

    # Like delay configuration with presets
    bot.like_delay_range = ask_delay_range("likes", default_range=[60, 90])

    # Posts to check per user (Presets + Custom)
    posts_amount = ask_choice_or_custom(
        english_title="Select number of recent posts to check per user",
        options=[
            (2, "2 posts", "Fast & Light", ":zap:"),
            (4, "4 posts", "Recommended & Standard", ":shield:"),
            (6, "6 posts", "Deeper Check", ":mag:"),
            (10, "10 posts", "Thorough Check", ":star:"),
        ],
        default_val=4,
        custom_prompt_en="Enter custom number of posts to check",
        val_type=int
    )

    # Commenting toggle and delay (Selectable Yes/No)
    commenting = ask_yes_no(
        "Enable automated comments on posts?",
        default=False
    )
    if commenting:
        current_comments = load_comments()
        if not current_comments:
            log_warning(f"Notice: [bold yellow]{COMMENTS_FILE_PATH}[/bold yellow] is currently empty. Please write your custom comments into [bold yellow]{COMMENTS_FILE_PATH}[/bold yellow]! :warning:")
        else:
            log_print(f"Automated commenting is [bold green]ENABLED[/bold green] ({len(current_comments)} comments loaded from [bold yellow]{COMMENTS_FILE_PATH}[/bold yellow]) :white_check_mark:")
        bot.comment_delay_range = ask_delay_range("comments", default_range=[60, 90])
    else:
        log_print("Automated commenting is [bold red]DISABLED[/bold red] :cross_mark:")

    # Story Interaction Toggle (Selectable Yes/No)
    story_interaction = ask_yes_no(
        "Enable automated story viewing (all) & liking (last story) for followings with active stories?",
        default=True
    )
    if story_interaction:
        log_print("Automated Story Viewing & Liking Last Story is [bold green]ENABLED[/bold green] :clapper: :heart:")
        bot.story_delay_range = ask_delay_range("last story like cooldown", default_range=[30, 60])
    else:
        log_print("Automated Story Interaction is [bold red]DISABLED[/bold red] :cross_mark:")

    # Sleep after user with actions (Presets + Custom)
    sleep_iter_min = ask_choice_or_custom(
        english_title="Select cooldown after processing each user (minutes)",
        options=[
            (1, "1 minute", "Fast", ":zap:"),
            (2, "2 minutes", "Recommended & Safe", ":shield:"),
            (4, "4 minutes", "Conservative", ":hourglass:"),
            (6, "6 minutes", "Long Rest", ":sleeping:"),
        ],
        default_val=2,
        custom_prompt_en="Enter custom cooldown minutes after each user",
        val_type=float
    )
    sleep_after_iteration = int(sleep_iter_min * 60)

    # Sleep after full loop (Presets + Custom)
    sleep_loop_hours = ask_choice_or_custom(
        english_title="Select cooldown after completing a full round (hours)",
        options=[
            (0.5, "0.5 hour (30 mins)", "Half Hour", ":zap:"),
            (1.0, "1.0 hour", "1 Hour (Recommended)", ":shield:"),
            (2.0, "2.0 hours", "2 Hours (Safe)", ":hourglass:"),
            (4.0, "4.0 hours", "4 Hours (Long)", ":sleeping:"),
        ],
        default_val=1.0,
        custom_prompt_en="Enter custom cooldown hours after full loop",
        val_type=float
    )
    sleep_after_loop = int(sleep_loop_hours * 3600)

    # Execute warm-up if enabled
    if enable_warmup:
        bot.perform_warmup_actions(max_feed_items=4, view_stories=True)

    console.print(f"\n[bold green]:rocket: Bot is starting for {len(followings)} following users with custom delays...[/bold green]\n")

    # ------------ Processing Loop ------------
    loop = 0
    total_actions_all_time = 0
    try:
        while True:
            loop += 1
            show_section_divider(f":repeat: Loop {loop}: Processing Following Accounts", style="bold magenta")
            following_list = list(followings.values())
            loop_liked_count = 0

            for i, user in enumerate(following_list, start=1):
                username = getattr(user, 'username', str(user))
                user_pk = getattr(user, 'pk', str(user))
                console.print(f"\n[bold cyan]─── [:bust_in_silhouette: User {i}/{len(following_list)}] ───[/bold cyan] @[bold green]{username}[/bold green] (ID: [yellow]{user_pk}[/yellow])")

                # Process all active stories (View all stories & like last story)
                if story_interaction and user_pk:
                    st_seen, st_liked = bot.process_user_stories(
                        user_pk=str(user_pk),
                        username=str(username),
                        delay_range=bot.story_delay_range,
                        like_last_story=True
                    )
                    if st_liked > 0:
                        total_actions_all_time += st_liked

                user_posts = bot.get_user_posts(str(user_pk), amount=posts_amount)
                if user_posts:
                    action_performed = False
                    for post in user_posts:
                        post_pk = str(getattr(post, 'pk', str(post)))
                        has_liked = getattr(post, 'has_liked', False)
                        if has_liked:
                            log_warning(f"Post {post_pk} already liked previously :fast_forward:")
                        else:
                            # 1. Mark post as seen (Impression)
                            bot.seen_user_post(post_pk, username=username, user_pk=str(user_pk))
                            # 2. Natural viewing dwell pause (1 to 2 seconds)
                            view_dwell = randint(1, 2)
                            log_sleep(view_dwell, message=f"Viewing post naturally ({view_dwell}s)")
                            # 3. Like post
                            liked = bot.like_user_post(post_pk, username=username, user_pk=str(user_pk))
                            if liked:
                                action_performed = True
                                loop_liked_count += 1
                                total_actions_all_time += 1
                            # 4. Comment on post
                            if commenting:
                                bot.comment_user_post(post_pk, username=username, user_pk=str(user_pk))

                    if action_performed:
                        log_sleep(sleep_after_iteration, message=f"Cooling down after processing @{username}")
                else:
                    log_warning(f"No recent public posts found for @{username} :warning:")

            hours_str = str(round(sleep_after_loop / 3600, 2))
            show_stats_card(
                f"Loop {loop} Completed",
                {
                    ":target: New Posts Liked This Loop": f"[bold green]{loop_liked_count}[/bold green]",
                    ":star: Total Lifetime Actions": f"[bold magenta]{total_actions_all_time}[/bold magenta]",
                    ":busts_in_silhouette: Total Following Processed": f"[bold cyan]{len(following_list)}[/bold cyan]",
                    ":sleeping: Cooldown Before Next Cycle": f"[bold yellow]{hours_str} hours[/bold yellow]"
                },
                border_style="green"
            )
            log_warning(f":repeat: Completed [bold blue]{loop}[/bold blue] loops. Sleeping for [bold magenta]{hours_str}[/bold magenta] hours. :sleeping:")
            log_sleep(sleep_after_loop, message=f"Loop {loop} complete, waiting for next cycle")

    except KeyboardInterrupt:
        log_warning("\n:stop_sign: Bot stopped by user safely. :wave:")
        show_stats_card(
            "Session Summary (Stopped)",
            {
                ":heart: Total Posts Liked": f"[bold green]{total_actions_all_time}[/bold green]",
                ":repeat: Total Loops Run": f"[bold cyan]{loop}[/bold cyan]"
            },
            border_style="yellow"
        )

if __name__ == "__main__":
    main()
