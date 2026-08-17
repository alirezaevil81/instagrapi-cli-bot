import os
import pickle
import sys
from random import randint
from time import sleep
import questionary

from src.bot.bot import Bot
from src.bot.utils import (
    show_banner,
    show_user_table,
    console,
    log_print,
    log_success,
    log_error,
    log_warning,
    log_sleep,
    fix_persian
)

def main():
    os.makedirs("data/json", exist_ok=True)
    os.makedirs("data/pickle", exist_ok=True)

    show_banner("Post Likers Bot", "Extract Likers from Target Posts & Automated Follow/Like Engagement")

    cl = Bot()
    cl.start()

    if not getattr(cl, 'user_id', None):
        log_warning("Not logged in. Exiting.")
        sys.exit(0)

    # ----------------- User Queue / Pickle Handling -----------------
    pickle_path = "data/pickle/users.pkl"
    start_via_pickle = False

    if os.path.exists(pickle_path):
        use_saved_pickle = questionary.confirm(
            "A saved target users file (users.pkl) exists. Do you want to resume with it?",
            default=True
        ).ask()
        start_via_pickle = bool(use_saved_pickle)

    if start_via_pickle:
        try:
            with open(pickle_path, "rb") as f:
                users = pickle.load(f)
        except Exception as e:
            log_error("Could not load pickle: ", str(e))
            users = []
        else:
            log_success(f"Loaded [bold cyan]{len(users)}[/bold cyan] target users from saved queue.")
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

        try:
            with open(pickle_path, "wb") as f:
                pickle.dump(users, f)
        except Exception as e:
            log_error("Cannot save pickle: ", str(e))
        else:
            log_success(f"Saved [bold cyan]{len(users)}[/bold cyan] target public users to queue ({pickle_path}) :floppy_disk:")

    # ----------------- Display Target Users Table -----------------
    if users:
        show_user_table(users, title="Ready Target Users Queue")
    else:
        log_warning("No target users found after filtering.")
        sys.exit(0)

    # ----------- Interactive Configuration (Questionary) --------------
    console.print(f"\n[bold cyan]:gear: Configure Bot Parameters ({fix_persian('تنظیم پارامترهای اجرایی و تاخیرها')}):[/bold cyan]")

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

    # ----------------- Engagement Loop -----------------
    console.print(f"\n[bold green]:rocket: Starting interaction with {len(users)} target users with custom delays...[/bold green]\n")

    try:
        for i, user in enumerate(list(users), start=1):
            uname = str(getattr(user, 'username', str(user)))
            upk = str(getattr(user, 'pk', str(user)))

            log_print(f"[bold cyan]:mag: [{i}/{len(users)}][/bold cyan] Interacting with @[bold green]{uname}[/bold green] (ID: {upk})")

            user_posts = []
            try:
                user_posts = cl.user_medias(upk, amount=posts_amount)
            except Exception as e:
                log_error(f"Could not fetch posts for @{uname}: ", str(e))
            else:
                log_success(f"Fetched [bold magenta]{len(user_posts)}[/bold magenta] posts for @{uname} :package:")

            if user_posts:
                for post in user_posts:
                    post_pk = str(getattr(post, 'pk', str(post)))
                    try:
                        cl.media_like(post_pk)
                    except Exception as e:
                        log_error(f"Could not like post {post_pk}: ", str(e))
                    else:
                        log_success(f"Post {post_pk} liked :heart:")
                        min_d, max_d = like_delay_range[0], like_delay_range[1]
                        sleep_sec = randint(min_d, max_d)
                        log_sleep(sleep_sec, message=f"Cooldown after like on @{uname} ({sleep_sec}s)")
            else:
                log_warning(f"No public posts found on profile @{uname}")

            # Update queue in pickle
            if user in users:
                users.remove(user)
            with open(pickle_path, "wb") as f:
                pickle.dump(users, f)

            if not users:
                if os.path.exists(pickle_path):
                    os.remove(pickle_path)
                log_success(":tada: All target users processed! Queue cleared.")

            log_print(f"[bold blue]Remaining users in queue:[/bold blue] [bold magenta]{len(users)}[/bold magenta]")

    except KeyboardInterrupt:
        log_warning(f"\nProcess paused by user. Progress saved in {pickle_path} :floppy_disk:.")

    console.print("\n[bold blue]━━━━━━━━━━━━━━━━━━━━━━━━ :sparkles: All Done :sparkles: ━━━━━━━━━━━━━━━━━━━━━━━━[/bold blue]")


if __name__ == "__main__":
    main()
