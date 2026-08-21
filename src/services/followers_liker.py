"""
Followers Liker Service: Automated engagement and interactions for accounts you follow.
"""
import os
import sys
from random import randint
import questionary

from src.core.client import Bot
from src.database.engine import init_db
from src.utils import (
    log_print,
    log_sleep,
    show_banner,
    console,
    log_error,
    log_warning,
    fix_persian,
    register_graceful_shutdown
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
    console.print(f"\n[bold cyan]:gear: Configure Bot Parameters ({fix_persian('تنظیم پارامترهای اجرایی و تاخیرها')}):[/bold cyan]")

    # Warm-up option
    enable_warmup = questionary.confirm(
        f"Perform natural account warm-up actions before starting? ({fix_persian('انجام آماده‌سازی و رفتار ارگانیک قبل از شروع')})",
        default=True
    ).ask()

    # Like delay configuration
    min_like_delay_str = questionary.text(f"Min delay between likes ({fix_persian('حداقل تاخیر بین لایک‌ها به ثانیه')}):", default="30").ask() or "30"
    max_like_delay_str = questionary.text(f"Max delay between likes ({fix_persian('حداکثر تاخیر بین لایک‌ها به ثانیه')}):", default="60").ask() or "60"
    try:
        l1 = max(1, int(min_like_delay_str.strip()))
        l2 = max(1, int(max_like_delay_str.strip()))
        bot.like_delay_range = [min(l1, l2), max(l1, l2)]
    except ValueError:
        bot.like_delay_range = [30, 60]

    # Posts to check per user
    posts_amount_str = questionary.text(f"Number of recent posts to check per user ({fix_persian('تعداد پست‌های هر کاربر')}):", default="4").ask() or "4"
    try:
        posts_amount = max(1, int(posts_amount_str.strip()))
    except ValueError:
        posts_amount = 4

    # Commenting toggle and delay
    commenting = questionary.confirm(f"Enable automated comments on posts? ({fix_persian('ارسال خودکار کامنت')})", default=True).ask()
    if commenting:
        log_print("Automated commenting is [bold green]ENABLED[/bold green] :white_check_mark:")
        min_com_delay_str = questionary.text(f"Min delay between comments ({fix_persian('حداقل تاخیر بین کامنت‌ها')}):", default="60").ask() or "60"
        max_com_delay_str = questionary.text(f"Max delay between comments ({fix_persian('حداکثر تاخیر بین کامنت‌ها')}):", default="90").ask() or "90"
        try:
            c1 = max(1, int(min_com_delay_str.strip()))
            c2 = max(1, int(max_com_delay_str.strip()))
            bot.comment_delay_range = [min(c1, c2), max(c1, c2)]
        except ValueError:
            bot.comment_delay_range = [60, 90]
    else:
        log_print("Automated commenting is [bold red]DISABLED[/bold red] :cross_mark:")

    # Sleep after user with actions
    sleep_iter_str = questionary.text(f"Cooldown after processing each user ({fix_persian('استراحت بعد از هر کاربر به دقیقه')}):", default="2").ask() or "2"
    try:
        sleep_after_iteration = int(float(sleep_iter_str.strip()) * 60)
    except ValueError:
        sleep_after_iteration = 120

    # Sleep after full loop
    sleep_loop_str = questionary.text(f"Cooldown after completing a full round ({fix_persian('استراحت پایان هر دور به ساعت')}):", default="1").ask() or "1"
    try:
        sleep_after_loop = int(float(sleep_loop_str.strip()) * 3600)
    except ValueError:
        sleep_after_loop = 3600

    # API Request Delay range
    min_delay_str = questionary.text(f"Base API request delay min ({fix_persian('حداقل تاخیر ریکوئست‌ها به ثانیه')}):", default="3").ask() or "3"
    max_delay_str = questionary.text(f"Base API request delay max ({fix_persian('حداکثر تاخیر ریکوئست‌ها به ثانیه')}):", default="7").ask() or "7"
    try:
        d1 = int(min_delay_str.strip())
        d2 = int(max_delay_str.strip())
        bot.delay_range = [min(d1, d2), max(d1, d2)]
    except ValueError:
        bot.delay_range = [3, 7]

    # Execute warm-up if enabled
    if enable_warmup:
        bot.perform_warmup_actions(max_feed_items=4, view_stories=True)

    console.print(f"\n[bold green]:rocket: Bot is starting for {len(followings)} following users with custom delays...[/bold green]\n")

    # ------------ Processing Loop ------------
    loop = 0
    try:
        while True:
            following_list = list(followings.values())
            for i, user in enumerate(following_list, start=1):
                username = getattr(user, 'username', str(user))
                user_pk = getattr(user, 'pk', str(user))
                log_print(f"[bold cyan]:mag: User {i}/{len(following_list)}:[/bold cyan] Checking @[bold cyan]{username}[/bold cyan]")

                user_posts = bot.get_user_posts(str(user_pk), amount=posts_amount)
                if user_posts:
                    action_performed = False
                    for post in user_posts:
                        post_pk = str(getattr(post, 'pk', str(post)))
                        has_liked = getattr(post, 'has_liked', False)
                        if has_liked:
                            log_warning(f"Post {post_pk} already liked previously")
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
                            # 4. Comment on post
                            if commenting:
                                bot.comment_user_post(post_pk, username=username, user_pk=str(user_pk))

                    if action_performed:
                        log_sleep(sleep_after_iteration, message=f"Cooling down after processing @{username}")
                else:
                    log_warning(f"No recent posts found for @{username}")

            loop += 1
            hours_str = str(round(sleep_after_loop / 3600, 2))
            log_warning(f":repeat: Completed [bold blue]{loop}[/bold blue] rounds. Sleeping for [bold magenta]{hours_str}[/bold magenta] hours. :sleeping:")
            log_sleep(sleep_after_loop, message=f"Round {loop} complete, waiting for next cycle")

    except KeyboardInterrupt:
        log_warning("\nBot stopped by user safely. :hand:")

if __name__ == "__main__":
    main()
