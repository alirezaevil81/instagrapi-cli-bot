"""
Post Likers Service: Extracts likers from specific target post URLs and engages automatically.
"""
import os
import sys
import time
from random import randint
from time import sleep
import questionary
from src.core.exceptions import (
    MediaNotFound,
    UserNotFound,
    PrivateAccount,
    FeedbackRequired,
    PleaseWaitFewMinutes,
    ClientLoginRequired,
    LoginRequired,
    ClientError,
    is_network_error
)

from src.core.client import Bot
from src.config import load_comments, COMMENTS_FILE_PATH
from src.database.repository import (
    save_target_users_queue,
    get_pending_target_users,
    remove_user_from_queue,
    clear_target_queue,
    get_queue_count,
    has_recent_interaction
)
from src.database.engine import init_db
from src.utils import (
    show_banner,
    show_user_table,
    show_section_divider,
    show_stats_card,
    show_session_plan,
    console,
    log_print,
    log_success,
    log_error,
    log_warning,
    log_sleep,
    format_bilingual_prompt,
    ask_yes_no,
    ask_delay_range,
    ask_choice_or_custom,
    register_graceful_shutdown,
    em,
    QUESTIONARY_STYLE,
    notify_task_completed,
    handle_connection_recovery
)
from src.utils.config_memory import prompt_config_mode, save_bot_preferences

def main():
    init_db()
    register_graceful_shutdown()

    show_banner("Post Likers Bot", "Extract Likers from Target Posts & Automated SQLite-backed Engagement")

    cl = Bot()
    cl.start()

    if not getattr(cl, 'user_id', None):
        log_warning("Not logged in. Returning to main menu.")
        return

    # ----------------- Smart Memory Check -----------------
    config_mode, saved_pref = prompt_config_mode("Post Likers Bot", "post_liker")
    if config_mode == "back":
        log_print("Returning to main menu... :back:")
        return

    # ----------------- User Queue / SQLite Database Handling -----------------
    pending_count = get_queue_count()
    start_via_saved_queue = False

    if pending_count > 0:
        use_saved_db = ask_yes_no(
            f"Found {pending_count} pending target users in SQLite database. Do you want to resume?",
            default=True
        )
        start_via_saved_queue = bool(use_saved_db)

    if start_via_saved_queue:
        users = get_pending_target_users()
        log_success(f"Loaded [bold cyan]{len(users)}[/bold cyan] target users from SQLite database queue.")
    else:
        kwargs = {"style": QUESTIONARY_STYLE} if QUESTIONARY_STYLE else {}
        posts_raw = questionary.text(
            "Enter target post URLs (separated by comma, or 'back' to return):",
            validate=lambda val: True if len(val.strip()) > 0 else "Please provide at least one post URL",
            **kwargs
        ).ask()

        if not posts_raw or posts_raw.strip().lower() in ["back", "0", "exit", "b"]:
            log_warning("Returning to main menu.")
            return

        posts = [p.strip() for p in posts_raw.split(",") if p.strip()]
        users_extracted = []

        with console.status("[bold cyan]:mag: Fetching likers from target posts...[/bold cyan]"):
            for post in posts:
                try:
                    pk, post_id = cl.resolve_media_pk_and_id(post)
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
                    if is_network_error(e):
                        log_error(f":satellite: Network/DNS error extracting likers for {post}: {e}")
                        if handle_connection_recovery(e, action_name=f"استخراج لایک‌کننده‌های پست {post}"):
                            # Retry this post
                            posts.insert(i, post)
                    else:
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
        log_success(f"Saved [bold cyan]{saved_count}[/bold cyan] target public users to SQLite database :floppy_disk:")

    # ----------------- Display Target Users Table -----------------
    if users:
        show_user_table(users, title="Ready Target Users Queue (SQLite)")
    else:
        log_warning("No target users found after filtering.")
        return

    # ----------- Configuration: Quick vs Custom --------------
    if config_mode == "quick" and saved_pref:
        like_posts = saved_pref.get("like_posts", True)
        interact_story = saved_pref.get("interact_story", True)
        comment_posts = saved_pref.get("comment_posts", False)
        enable_warmup = saved_pref.get("enable_warmup", True)
        posts_amount = saved_pref.get("posts_amount", 3)
        like_delay_range = saved_pref.get("like_delay_range", [60, 90])
        story_delay_range = saved_pref.get("story_delay_range", [30, 60])
        comment_delay_range = saved_pref.get("comment_delay_range", [60, 90])
        log_success("Loaded saved preferences for 1-click execution! :rocket:")
    else:
        console.print("\n[bold cyan]:gear: Configure Bot Actions & Parameters[/bold cyan]")

        kwargs = {"style": QUESTIONARY_STYLE} if QUESTIONARY_STYLE else {}
        selected_actions = questionary.checkbox(
            em("Select interaction actions to perform for target users: (Space to toggle, Enter to confirm)"),
            choices=[
                questionary.Choice(
                    title=em(":heart: Like Recent Posts (لایک پست‌های اخیر مخاطب)"),
                    value="like_posts",
                    checked=True
                ),
                questionary.Choice(
                    title=em(":clapper: View & Like Latest Story (تماشا و لایک آخرین استوری مخاطب)"),
                    value="interact_story",
                    checked=True
                ),
                questionary.Choice(
                    title=em(":speech_balloon: Comment on Recent Posts (ارسال کامنت خودکار روی پست‌ها)"),
                    value="comment_posts",
                    checked=False
                ),
                questionary.Choice(
                    title=em(":zap: Account Warm-up (گرم کردن طبیعی اکانت قبل از شروع)"),
                    value="warmup",
                    checked=True
                ),
            ],
            **kwargs
        ).ask()

        if selected_actions is None:
            log_warning("Operation cancelled. Returning to main menu.")
            return

        like_posts = "like_posts" in selected_actions
        interact_story = "interact_story" in selected_actions
        comment_posts = "comment_posts" in selected_actions
        enable_warmup = "warmup" in selected_actions

        if not like_posts and not interact_story and not comment_posts:
            log_warning("No engagement actions selected. Enabling default post likes.")
            like_posts = True

        # 1. Post settings (if like_posts or comment_posts enabled)
        posts_amount = 3
        like_delay_range = [60, 90]
        comment_delay_range = [60, 90]

        if like_posts or comment_posts:
            posts_amount = ask_choice_or_custom(
                english_title="Select number of recent posts to check per target user",
                options=[
                    (1, "1 post", "Fast & Light", ":zap:"),
                    (3, "3 posts", "Recommended & Standard", ":shield:"),
                    (5, "5 posts", "Deeper Engagement", ":mag:"),
                    (8, "8 posts", "Maximum Likes", ":star:"),
                ],
                default_val=3,
                custom_prompt_en="Enter custom number of posts to check per user",
                val_type=int
            )

        if like_posts:
            like_delay_range = ask_delay_range("post likes", default_range=[60, 90])

        # 2. Story settings (if interact_story enabled)
        story_delay_range = [30, 60]
        if interact_story:
            story_delay_range = ask_delay_range("story likes", default_range=[30, 60])

        # 3. Comment settings (if comment_posts enabled)
        if comment_posts:
            current_comments = load_comments()
            if not current_comments:
                log_warning(f"Notice: [bold yellow]{COMMENTS_FILE_PATH}[/bold yellow] is currently empty! Please write your custom comments into [bold yellow]{COMMENTS_FILE_PATH}[/bold yellow]! :warning:")
            else:
                log_print(f"Loaded [bold green]{len(current_comments)}[/bold green] comments from [bold yellow]{COMMENTS_FILE_PATH}[/bold yellow] :speech_balloon:")
            comment_delay_range = ask_delay_range("comments", default_range=[60, 90])

        # Save preferences for future 1-click Quick Launch
        save_bot_preferences("post_liker", {
            "like_posts": like_posts,
            "interact_story": interact_story,
            "comment_posts": comment_posts,
            "enable_warmup": enable_warmup,
            "posts_amount": posts_amount,
            "like_delay_range": like_delay_range,
            "story_delay_range": story_delay_range,
            "comment_delay_range": comment_delay_range,
        })

    # Execute warm-up if enabled
    if enable_warmup:
        cl.perform_warmup_actions(max_feed_items=3, view_stories=True)

    # Display Pre-Flight Mission Plan
    session_plan = {
        "Target Public Users": f"{len(users)} users in SQLite queue",
        "Post Likes": f"Enabled ({posts_amount} posts | {like_delay_range[0]}-{like_delay_range[1]}s)" if like_posts else "[red]Disabled[/red]",
        "Story Interaction": f"Enabled (Latest story | {story_delay_range[0]}-{story_delay_range[1]}s)" if interact_story else "[red]Disabled[/red]",
        "Automated Comments": f"Enabled ({comment_delay_range[0]}-{comment_delay_range[1]}s)" if comment_posts else "[red]Disabled[/red]",
        "Account Warm-up": "Completed" if enable_warmup else "Skipped",
    }
    show_session_plan("Post Likers Engagement Mission Plan", session_plan)

    # ----------------- Engagement Loop -----------------
    console.print(f"\n[bold green]:rocket: Starting interaction with {len(users)} target users...[/bold green]\n")
    processed_count = 0
    posts_liked_count = 0
    stories_seen_count = 0
    stories_liked_count = 0
    comments_sent_count = 0
    start_time = time.time()

    try:
        for i, user in enumerate(list(users), start=1):
            uname = str(getattr(user, 'username', str(user)))
            upk = str(getattr(user, 'pk', str(user)))
            is_priv = bool(getattr(user, 'is_private', False))

            privacy_badge = "[red]:lock: Private[/red]" if is_priv else "[green]:globe_with_meridians: Public[/green]"
            show_section_divider(f":bust_in_silhouette: Target User {i}/{len(users)}: @{uname} ({privacy_badge})", style="bold cyan")

            if is_priv:
                log_warning(f"User @{uname} has a private profile. Skipping interaction :lock:")
                remove_user_from_queue(upk)
                if user in users:
                    users.remove(user)
                continue

            # Step 1: Optional Story Interaction (View & Like Latest Story)
            if interact_story and upk:
                with console.status(f"[bold cyan]Checking active stories for @{uname}...[/bold cyan]", spinner="dots"):
                    stories = cl.get_user_active_stories(upk)

                if stories:
                    latest_story = stories[-1]
                    s_pk = str(getattr(latest_story, "pk", ""))
                    if s_pk:
                        # Mark latest story as seen
                        if not has_recent_interaction(s_pk, "story_seen"):
                            st_seen = cl.seen_story(s_pk, username=uname, user_pk=upk)
                            if st_seen:
                                stories_seen_count += 1
                                dwell = randint(2, 4)
                                log_sleep(dwell, message=f"Watching latest story of @{uname} ({dwell}s)")
                        else:
                            log_print(f"Latest story ({s_pk}) of @{uname} was already viewed :eye:")

                        # Like latest story
                        if not has_recent_interaction(s_pk, "story_like"):
                            log_print(f"Liking latest story ({s_pk}) for @{uname} :sparkles: :heart:")
                            st_liked = cl.like_story(
                                s_pk,
                                delay_range=story_delay_range,
                                username=uname,
                                user_pk=upk
                            )
                            if st_liked:
                                stories_liked_count += 1
                        else:
                            log_print(f"Latest story ({s_pk}) of @{uname} is already liked :heart:")
                else:
                    log_print(f"No active public stories found for @{uname} :clapper:")

            # Step 2: Optional Posts Interaction (Like & Comment)
            if (like_posts or comment_posts) and upk:
                with console.status(f"[bold cyan]Fetching recent posts for @{uname}...[/bold cyan]", spinner="dots"):
                    user_posts = cl.get_user_posts(upk, amount=posts_amount)

                if user_posts:
                    log_print(f"Found [bold cyan]{len(user_posts)}[/bold cyan] posts for @{uname}. Engaging... :camera:")
                    user_acted = False
                    for p_idx, post in enumerate(user_posts, start=1):
                        post_pk = str(getattr(post, 'pk', str(post)))
                        if not post_pk:
                            continue

                        has_liked = getattr(post, 'has_liked', False) or has_recent_interaction(post_pk, "like")

                        # 2a. Mark post as seen (Impression)
                        cl.seen_user_post(post_pk, username=uname, user_pk=upk)
                        view_dwell = randint(1, 3)
                        log_sleep(view_dwell, message=f"Viewing post {p_idx}/{len(user_posts)} ({view_dwell}s)")

                        # 2b. Like post
                        if like_posts:
                            if has_liked:
                                log_print(f"Post {post_pk} was already liked previously :white_check_mark:")
                            else:
                                p_liked = cl.like_user_post(post_pk, delay_range=like_delay_range, username=uname, user_pk=upk)
                                if p_liked:
                                    posts_liked_count += 1
                                    user_acted = True

                        # 2c. Comment on post
                        if comment_posts:
                            c_sent = cl.comment_user_post(post_pk, delay_range=comment_delay_range, username=uname, user_pk=upk)
                            if c_sent:
                                comments_sent_count += 1
                                user_acted = True

                    if user_acted:
                        processed_count += 1
                else:
                    log_warning(f"No public posts found on profile @{uname} :warning:")
            elif interact_story:
                processed_count += 1

            # Remove completed user from SQLite queue
            remove_user_from_queue(upk)
            if user in users:
                users.remove(user)

            rem_count = get_queue_count()
            if rem_count == 0:
                log_success(":tada: All target users processed! SQLite queue cleared.")
            else:
                log_print(f":bar_chart: [bold blue]Remaining users in queue:[/bold blue] [bold magenta]{rem_count}[/bold magenta]")

    except KeyboardInterrupt:
        log_warning(f"\n:stop_sign: Process paused by user. Progress safely retained in SQLite database :floppy_disk:.")

    elapsed_sec = int(time.time() - start_time)
    elapsed_str = f"{elapsed_sec // 60}m {elapsed_sec % 60}s" if elapsed_sec >= 60 else f"{elapsed_sec}s"

    summary_metrics = {
        ":busts_in_silhouette: Processed Target Users": f"[bold green]{processed_count}[/bold green]",
    }
    if like_posts:
        summary_metrics[":heart: Liked Posts"] = f"[bold green]{posts_liked_count}[/bold green]"
    if interact_story:
        summary_metrics[":clapper: Stories Viewed"] = f"[bold cyan]{stories_seen_count}[/bold cyan]"
        summary_metrics[":heart: Stories Liked"] = f"[bold green]{stories_liked_count}[/bold green]"
    if comment_posts:
        summary_metrics[":speech_balloon: Comments Sent"] = f"[bold magenta]{comments_sent_count}[/bold magenta]"

    summary_metrics[":hourglass: Remaining in Queue"] = f"[bold yellow]{get_queue_count()}[/bold yellow]"
    summary_metrics[":clock1: Total Elapsed Time"] = f"[bold cyan]{elapsed_str}[/bold cyan]"

    show_stats_card(
        "Post Likers Engagement Summary",
        summary_metrics,
        border_style="magenta"
    )
    console.print("\n[bold blue]━━━━━━━━━━━━━━━━━━━━━━━━ :sparkles: All Done :sparkles: ━━━━━━━━━━━━━━━━━━━━━━━━[/bold blue]\n")
    notify_task_completed(
        "ربات لایک‌کننده پست‌ها (Post Likers Bot)",
        f"پردازش به پایان رسید. تعداد {processed_count} کاربر هدف با موفقیت پردازش شدند."
    )


if __name__ == "__main__":
    main()
