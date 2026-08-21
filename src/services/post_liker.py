"""
Post Likers Service: Extracts likers from specific target post URLs and engages automatically.
"""
import os
import sys
from random import randint
from time import sleep
import questionary
from instagrapi.exceptions import (
    MediaNotFound,
    UserNotFound,
    PrivateAccount,
    FeedbackRequired,
    PleaseWaitFewMinutes,
    ClientLoginRequired,
    LoginRequired,
    ClientError
)

from src.core.client import Bot
from src.database import (
    save_target_users_queue,
    get_pending_target_users,
    remove_user_from_queue,
    clear_target_queue,
    get_queue_count,
    init_db
)
from src.utils import (
    show_banner,
    show_user_table,
    console,
    log_print,
    log_success,
    log_error,
    log_warning,
    log_sleep,
    fix_persian,
    register_graceful_shutdown
)

def main():
    init_db()
    register_graceful_shutdown()

    show_banner("Post Likers Bot", "Extract Likers from Target Posts & Automated SQLite-backed Engagement")

    cl = Bot()
    cl.start()

    if not getattr(cl, 'user_id', None):
        log_warning("Not logged in. Exiting.")
        sys.exit(0)

    # ----------------- User Queue / SQLite Database Handling -----------------
    pending_count = get_queue_count()
    start_via_saved_queue = False

    if pending_count > 0:
        use_saved_db = questionary.confirm(
            f"Found {pending_count} pending target users in SQLite database. Do you want to resume?",
            default=True
        ).ask()
        start_via_saved_queue = bool(use_saved_db)

    if start_via_saved_queue:
        users = get_pending_target_users()
        log_success(f"Loaded [bold cyan]{len(users)}[/bold cyan] target users from SQLite database queue.")
    else:
        posts_raw = questionary.text(
            "Enter target post URLs (separated by comma):",
            validate=lambda val: True if len(val.strip()) > 0 else "Please provide at least one post URL"
        ).ask()

        if not posts_raw:
            log_warning("No post URLs provided. Exiting.")
            sys.exit(0)

        posts = [p.strip() for p in posts_raw.split(",") if p.strip()]
        users_extracted = []

        with console.status("[bold cyan]:mag: Fetching likers from target posts...[/bold cyan]"):
            for post in posts:
                try:
                    pk = cl.media_pk_from_url(post)
                    post_id = cl.media_id(pk)
                    likers = cl.media_likers(post_id)
                except MediaNotFound:
                    log_error(f"Post {post} not found or was removed.")
                    continue
                except PrivateAccount:
                    log_error(f"Target post {post} is from a private account.")
                    continue
                except FeedbackRequired as fb:
                    log_error(f"Instagram Action Block / Feedback Required: {fb}")
                    break
                except PleaseWaitFewMinutes:
                    log_warning("Rate limit hit while extracting likers. Instagram requested a cooldown.")
                    break
                except (LoginRequired, ClientLoginRequired):
                    log_error("Session expired while extracting likers. Please re-login.")
                    break
                except ClientError as ce:
                    log_error(f"Instagram ClientError for post {post}: {ce}")
                    continue
                except Exception as e:
                    log_error(f"Cannot fetch likers for post {post}: ", str(e))
                    likers = []
                else:
                    log_success(f"Extracted [bold magenta]{len(likers)}[/bold magenta] likers from post ID {post_id} :sparkles:")

                for liker in likers:
                    if liker not in users_extracted:
                        users_extracted.append(liker)

        # Fetch self following to filter out
        with console.status("[bold cyan]:busts_in_silhouette: Fetching your following list for filtering...[/bold cyan]"):
            try:
                following = cl.user_following(cl.user_id)
            except Exception as e:
                log_error("Cannot fetch followings: ", str(e))
                following = {}
            else:
                log_success(f"Your following count: [bold magenta]{len(following)}[/bold magenta] :busts_in_silhouette:")

        dicts = {}
        for item in users_extracted:
            uid = str(getattr(item, 'pk', str(item)))
            dicts[uid] = item

        # Filter private and already-followed accounts
        for uid, user in list(dicts.items()):
            try:
                is_priv = getattr(user, 'is_private', False)
                if uid in following or is_priv:
                    dicts.pop(uid, None)
            except Exception as e:
                log_error(f"Error filtering user {uid}: ", str(e))

        users = list(dicts.values())

        # Save extracted target users into SQLite database
        saved_count = save_target_users_queue(users, clear_existing=True)
        log_success(f"Saved [bold cyan]{saved_count}[/bold cyan] target public users to SQLite database ({cl.get_session_path('')}) :floppy_disk:")

    # ----------------- Display Target Users Table -----------------
    if users:
        show_user_table(users, title="Ready Target Users Queue (SQLite)")
    else:
        log_warning("No target users found after filtering.")
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
        like_delay_range = [min(l1, l2), max(l1, l2)]
    except ValueError:
        like_delay_range = [30, 60]

    # Posts to check per target user
    posts_amount_str = questionary.text(f"Number of recent posts to like per target user ({fix_persian('تعداد پست‌های هر تارگت')}):", default="3").ask() or "3"
    try:
        posts_amount = max(1, int(posts_amount_str.strip()))
    except ValueError:
        posts_amount = 3

    # API Request Delay range
    min_delay_str = questionary.text(f"Base API request delay min ({fix_persian('حداقل تاخیر ریکوئست‌ها به ثانیه')}):", default="3").ask() or "3"
    max_delay_str = questionary.text(f"Base API request delay max ({fix_persian('حداکثر تاخیر ریکوئست‌ها به ثانیه')}):", default="7").ask() or "7"
    try:
        d1 = int(min_delay_str.strip())
        d2 = int(max_delay_str.strip())
        cl.delay_range = [min(d1, d2), max(d1, d2)]
    except ValueError:
        cl.delay_range = [3, 7]

    # Execute warm-up if enabled
    if enable_warmup:
        cl.perform_warmup_actions(max_feed_items=3, view_stories=True)

    # ----------------- Engagement Loop -----------------
    console.print(f"\n[bold green]:rocket: Starting interaction with {len(users)} target users with custom delays...[/bold green]\n")

    try:
        for i, user in enumerate(list(users), start=1):
            uname = str(getattr(user, 'username', str(user)))
            upk = str(getattr(user, 'pk', str(user)))

            log_print(f"[bold cyan]:mag: [{i}/{len(users)}][/bold cyan] Interacting with @[bold green]{uname}[/bold green] (ID: {upk})")

            user_posts = cl.get_user_posts(upk, amount=posts_amount)

            if user_posts:
                for post in user_posts:
                    post_pk = str(getattr(post, 'pk', str(post)))
                    # 1. Mark post as seen (Impression)
                    cl.seen_user_post(post_pk, username=uname, user_pk=upk)
                    # 2. Natural human viewing pause (1 to 3 seconds)
                    view_dwell = randint(1, 3)
                    log_sleep(view_dwell, message=f"Viewing post naturally ({view_dwell}s)")
                    # 3. Perform like action
                    cl.like_user_post(post_pk, delay_range=like_delay_range, username=uname, user_pk=upk)
            else:
                log_warning(f"No public posts found on profile @{uname}")

            # Remove completed user from SQLite queue
            remove_user_from_queue(upk)
            if user in users:
                users.remove(user)

            rem_count = get_queue_count()
            if rem_count == 0:
                log_success(":tada: All target users processed! SQLite queue cleared.")
            else:
                log_print(f"[bold blue]Remaining users in queue:[/bold blue] [bold magenta]{rem_count}[/bold magenta]")

    except KeyboardInterrupt:
        log_warning(f"\nProcess paused by user. Progress safely retained in SQLite database :floppy_disk:.")

    console.print("\n[bold blue]━━━━━━━━━━━━━━━━━━━━━━━━ :sparkles: All Done :sparkles: ━━━━━━━━━━━━━━━━━━━━━━━━[/bold blue]")


if __name__ == "__main__":
    main()
