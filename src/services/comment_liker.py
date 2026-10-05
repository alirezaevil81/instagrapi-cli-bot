"""
Post Comments Liker Service: Extracts 0-like comments from target posts,
and optionally likes the commenter's recent posts and views/likes their latest active story
with safe human-like intervals, private account handling, and SQLite persistence.
"""
import os
import sys
import time
from random import randint
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
from src.database import (
    SimpleCommentObject,
    save_target_comments_queue,
    get_pending_target_comments,
    remove_comment_from_queue,
    clear_comment_queue,
    get_comment_queue_count,
    has_recent_interaction,
    init_db
)
from src.utils import (
    show_banner,
    show_comment_table,
    show_section_divider,
    show_stats_card,
    show_session_plan,
    console,
    log_print,
    log_success,
    log_error,
    log_warning,
    log_sleep,
    ask_yes_no,
    ask_delay_range,
    ask_choice_or_custom,
    ask_int,
    register_graceful_shutdown,
    em,
    QUESTIONARY_STYLE,
    notify_task_completed,
    handle_connection_recovery
)
from src.utils.config_memory import prompt_config_mode, save_bot_preferences


def extract_comments_from_posts(
    cl: Bot,
    posts: list,
    amount_per_post: int = 0,
    skip_own: bool = True,
    only_zero_likes: bool = True
) -> list:
    """
    Extracts comments from target post URLs or PKs.
    Filters:
      - Has 0 likes (if only_zero_likes is True)
      - Not already liked by current account
      - Not in interaction_history (SQLite)
      - Skips own comments if skip_own is True
    Returns a list of SimpleCommentObject.
    """
    unliked_comments = []
    seen_comment_pks = set()
    self_pk = str(getattr(cl, 'user_id', '') or '')

    for idx, post in enumerate(posts, start=1):
        post_str = post.strip()
        if not post_str:
            continue

        show_section_divider(f":camera: Post {idx}/{len(posts)}: {post_str}", style="bold cyan")

        try:
            with console.status(f"[bold cyan]:mag: Resolving post URL & media ID...[/bold cyan]", spinner="dots"):
                media_pk, media_id = cl.resolve_media_pk_and_id(post_str)

            with console.status(f"[bold cyan]:speech_balloon: Fetching comments for media ID {media_id}...[/bold cyan]", spinner="dots"):
                comments = cl.get_post_comments(media_id, amount=amount_per_post)

            log_print(f"Retrieved [bold magenta]{len(comments)}[/bold magenta] total comments for post {media_id} :speech_balloon:")

            post_unliked = 0
            for comment in comments:
                c_pk = str(getattr(comment, 'pk', ''))
                if not c_pk or c_pk in seen_comment_pks:
                    continue

                seen_comment_pks.add(c_pk)

                # Author info
                user = getattr(comment, 'user', None)
                author_pk = str(getattr(user, 'pk', '') if user else '')
                author_uname = str(getattr(user, 'username', '') if user else '')
                is_priv = bool(getattr(user, 'is_private', False)) if user else False
                text = str(getattr(comment, 'text', ''))
                
                raw_likes = getattr(comment, 'like_count', getattr(comment, 'comment_like_count', 0))
                like_count = int(raw_likes or 0)

                # 1. Zero likes condition (Strictly only unliked comments)
                if only_zero_likes and like_count > 0:
                    continue

                # 2. Skip own comments if requested
                if skip_own and self_pk and author_pk == self_pk:
                    continue

                # 3. Check if already liked on Instagram or in SQLite interaction history
                has_liked = getattr(comment, 'has_liked', False)
                if has_liked:
                    continue

                if has_recent_interaction(c_pk, "comment_like"):
                    continue

                # Create lightweight SimpleCommentObject
                comment_obj = SimpleCommentObject(
                    pk=c_pk,
                    media_pk=str(media_id),
                    author_username=author_uname,
                    author_pk=author_pk,
                    text=text,
                    like_count=like_count,
                    is_private=is_priv
                )

                unliked_comments.append(comment_obj)
                post_unliked += 1

            filter_label = "0 likes" if only_zero_likes else "unliked"
            log_success(f"Found [bold green]{post_unliked}[/bold green] matching comments ({filter_label}) on post {media_id} :sparkles:")

        except MediaNotFound:
            log_error(f"Post {post_str} not found or was removed.")
            continue
        except PrivateAccount:
            log_error(f"Target post {post_str} is from a private account.")
            continue
        except FeedbackRequired as fb:
            log_error(f"Instagram Action Block / Feedback Required: {fb}")
            break
        except PleaseWaitFewMinutes:
            log_warning("Rate limit hit while extracting comments. Instagram requested a cooldown.")
            break
        except (LoginRequired, ClientLoginRequired):
            log_error("Session expired while extracting comments. Please re-login.")
            break
        except ClientError as ce:
            log_error(f"Instagram ClientError for post {post_str}: {ce}")
            continue
        except Exception as e:
            if is_network_error(e):
                log_error(f":satellite: Network/DNS error extracting comments for {post_str}: {e}")
                if handle_connection_recovery(e, action_name=f"استخراج کامنت‌های پست {post_str}"):
                    # Retry this post
                    posts.insert(idx, post_str)
            else:
                log_error(f"Cannot fetch comments for post {post_str}: ", str(e))
            continue

    return unliked_comments


def main():
    init_db()
    register_graceful_shutdown()

    show_banner(
        "Post Comments Liker Bot",
        "Extract 0-Like Comments, Auto-Like, & Optional Commenter Posts and Story Engagement"
    )

    cl = Bot()
    cl.start()

    if not getattr(cl, 'user_id', None):
        log_warning("Not logged in. Returning to main menu.")
        return

    # ----------------- Smart Memory Check -----------------
    config_mode, saved_pref = prompt_config_mode("Post Comments Liker", "comment_liker")
    if config_mode == "back":
        log_print("Returning to main menu... :back:")
        return

    # ----------------- Comment Queue / SQLite Database Handling -----------------
    pending_count = get_comment_queue_count()
    start_via_saved_queue = False

    if pending_count > 0:
        use_saved_db = ask_yes_no(
            f"Found {pending_count} pending unliked comments in SQLite database. Do you want to resume?",
            default=True
        )
        start_via_saved_queue = bool(use_saved_db)

    if start_via_saved_queue:
        comments_queue = get_pending_target_comments()
        log_success(f"Loaded [bold cyan]{len(comments_queue)}[/bold cyan] unliked comments from SQLite database queue.")
    else:
        kwargs = {"style": QUESTIONARY_STYLE} if QUESTIONARY_STYLE else {}
        posts_raw = questionary.text(
            "Enter target post URLs or PKs (separated by comma, or 'back' to return):",
            validate=lambda val: True if len(val.strip()) > 0 else "Please provide at least one post URL",
            **kwargs
        ).ask()

        if not posts_raw or posts_raw.strip().lower() in ["back", "0", "exit", "b"]:
            log_warning("Returning to main menu.")
            return

        posts = [p.strip() for p in posts_raw.split(",") if p.strip()]

        # Amount of comments to fetch per post
        max_comments_per_post = ask_choice_or_custom(
            english_title="Select max comments to fetch per post",
            options=[
                (30, "30 comments", "Fast & Light", ":zap:"),
                (100, "100 comments", "Recommended & Standard", ":shield:"),
                (300, "300 comments", "Deep Extraction", ":mag:"),
                (0, "All available comments", "Unlimited", ":star:"),
            ],
            default_val=100,
            custom_prompt_en="Enter custom number of comments to fetch per post (0 for all)",
            val_type=int
        )

        # Checkbox for extraction filters
        extract_filters = questionary.checkbox(
            em("Select comment extraction filters: (Space to toggle, Enter to confirm)"),
            choices=[
                questionary.Choice(
                    title=em(":white_check_mark: 0-Likes Only (فقط کامنت‌های بدون لایک)"),
                    value="zero_likes",
                    checked=True
                ),
                questionary.Choice(
                    title=em(":shield: Skip Own Comments (رد کردن کامنت‌های پیج خودتان)"),
                    value="skip_own",
                    checked=True
                ),
            ],
            **kwargs
        ).ask() or ["zero_likes", "skip_own"]

        filter_zero_likes = "zero_likes" in extract_filters
        skip_own_comments = "skip_own" in extract_filters

        # Extract comments
        comments_queue = extract_comments_from_posts(
            cl=cl,
            posts=posts,
            amount_per_post=max_comments_per_post,
            skip_own=skip_own_comments,
            only_zero_likes=filter_zero_likes
        )

        if not comments_queue:
            log_warning("No unliked comments found from the specified posts.")
            return

        # Save extracted comments into SQLite queue
        saved_count = save_target_comments_queue(comments_queue, clear_existing=True)
        log_success(f"Saved [bold cyan]{saved_count}[/bold cyan] matching 0-like comments into SQLite database :floppy_disk:")

    # ----------------- Display Comments Table -----------------
    show_comment_table(comments_queue, title="Target 0-Like Comments Queue (SQLite)")

    # ----------- Configuration: Quick vs Custom --------------
    if config_mode == "quick" and saved_pref:
        like_comments = saved_pref.get("like_comments", True)
        interact_with_latest_story = saved_pref.get("interact_story", True)
        like_author_posts = saved_pref.get("like_author_posts", False)
        enable_warmup = saved_pref.get("enable_warmup", True)
        order_choice = saved_pref.get("order_choice", "asc")
        like_delay_range = saved_pref.get("like_delay_range", [25, 45])
        posts_per_author = saved_pref.get("posts_per_author", 2)
        author_post_delay_range = saved_pref.get("author_post_delay_range", [15, 30])
        story_like_delay_range = saved_pref.get("story_like_delay_range", [15, 30])
        max_likes_total = saved_pref.get("max_likes_total", -1)
        rest_every = saved_pref.get("rest_every", 10)
        log_success("Loaded saved preferences for 1-click execution! :rocket:")
    else:
        console.print("\n[bold cyan]:gear: Configure Bot Engagement Modules & Parameters[/bold cyan]")

        kwargs = {"style": QUESTIONARY_STYLE} if QUESTIONARY_STYLE else {}
        selected_actions = questionary.checkbox(
            em("Select interaction actions to perform: (Space to toggle, Enter to confirm)"),
            choices=[
                questionary.Choice(
                    title=em(":heart: Like Target Comments (لایک کامنت‌های استخراج‌شده)"),
                    value="like_comments",
                    checked=True
                ),
                questionary.Choice(
                    title=em(":clapper: View & Like Commenter's Latest Story (تماشا و لایک آخرین استوری کامنت‌گذار)"),
                    value="interact_story",
                    checked=True
                ),
                questionary.Choice(
                    title=em(":camera: Like Commenter's Recent Posts (لایک پست‌های اخیر کامنت‌گذار)"),
                    value="like_author_posts",
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
            log_warning("Operation cancelled by user.")
            return

        like_comments = "like_comments" in selected_actions
        interact_with_latest_story = "interact_story" in selected_actions
        like_author_posts = "like_author_posts" in selected_actions
        enable_warmup = "warmup" in selected_actions

        # Ordering
        order_choice = questionary.select(
            em("Select comment processing order:"),
            choices=[
                questionary.Choice(title=em(":arrow_right: Oldest to Newest (Chronological order)"), value="asc"),
                questionary.Choice(title=em(":fast_forward: Newest to Oldest (Recent comments first)"), value="desc"),
            ],
            **kwargs
        ).ask() or "asc"

        # Delay range between comment likes
        like_delay_range = [25, 45]
        if like_comments:
            like_delay_range = ask_delay_range("comment likes", default_range=[25, 45])

        # ----------------- Commenter's Recent Posts Configuration -----------------
        posts_per_author = 2
        author_post_delay_range = [15, 30]
        if like_author_posts:
            log_print("Commenter Post Liking is [bold green]ENABLED[/bold green] :camera: :heart:")
            posts_per_author = ask_choice_or_custom(
                english_title="Select number of recent posts to like per commenter",
                options=[
                    (1, "1 post", "Quick & Safe", ":zap:"),
                    (2, "2 posts", "Recommended & Balanced", ":shield:"),
                    (3, "3 posts", "Thorough Engagement", ":mag:"),
                    (5, "5 posts", "Deep Engagement", ":star:"),
                ],
                default_val=2,
                custom_prompt_en="Enter custom number of posts to like per commenter",
                val_type=int
            )
            author_post_delay_range = ask_delay_range("commenter post likes", default_range=[15, 30])
        else:
            log_print("Commenter Post Liking is [bold red]DISABLED[/bold red] :cross_mark:")

        # ----------------- Commenter's Latest Story Configuration -----------------
        story_like_delay_range = [15, 30]
        if interact_with_latest_story:
            log_print("Commenter Latest Story Interaction is [bold green]ENABLED[/bold green] (Seen -> Like) :clapper: :heart:")
            story_like_delay_range = ask_delay_range("story like cooldown", default_range=[15, 30])
        else:
            log_print("Commenter Latest Story Interaction is [bold red]DISABLED[/bold red] :cross_mark:")

        # Maximum comments to like in this session
        max_likes_total = ask_int(
            f"How many unliked comments do you want to like in this session? (-1 for all {len(comments_queue)})",
            default=-1,
            min_val=-1
        )

        # Optional batch rest pause
        rest_every = ask_choice_or_custom(
            english_title="Take an extra resting pause after every N comment likes",
            options=[
                (10, "Every 10 likes (Rest 2-3 mins)", "Recommended & Safe", ":shield:"),
                (25, "Every 25 likes (Rest 4-5 mins)", "Standard", ":hourglass:"),
                (50, "Every 50 likes (Rest 5-8 mins)", "Long Batches", ":sleeping:"),
                (0, "No extra batch pause", "Continuous", ":zap:"),
            ],
            default_val=10,
            custom_prompt_en="Enter custom batch size for rest pause (0 to disable)",
            val_type=int
        )

        # Save preferences for smart memory
        save_bot_preferences("comment_liker", {
            "like_comments": like_comments,
            "interact_story": interact_with_latest_story,
            "like_author_posts": like_author_posts,
            "enable_warmup": enable_warmup,
            "order_choice": order_choice,
            "like_delay_range": like_delay_range,
            "posts_per_author": posts_per_author,
            "author_post_delay_range": author_post_delay_range,
            "story_like_delay_range": story_like_delay_range,
            "max_likes_total": max_likes_total,
            "rest_every": rest_every,
        })
        log_success("Saved configuration to smart memory! :floppy_disk:")
    if max_likes_total != -1 and max_likes_total < len(comments_queue):
        comments_to_process = comments_queue[:max_likes_total]
    else:
        comments_to_process = comments_queue

    # Optional batch rest pause
    rest_every = ask_choice_or_custom(
        english_title="Take an extra resting pause after every N comment likes",
        options=[
            (10, "Every 10 likes (Rest 2-3 mins)", "Recommended & Safe", ":shield:"),
            (25, "Every 25 likes (Rest 4-5 mins)", "Standard", ":hourglass:"),
            (50, "Every 50 likes (Rest 5-8 mins)", "Long Batches", ":sleeping:"),
            (0, "No extra batch pause", "Continuous", ":zap:"),
        ],
        default_val=10,
        custom_prompt_en="Enter custom batch size for rest pause (0 to disable)",
        val_type=int
    )

    # Execute warm-up if enabled
    if enable_warmup:
        cl.perform_warmup_actions(max_feed_items=3, view_stories=True)

    # Display Pre-Flight Session Plan Card
    session_plan = {
        "Target Comments to Like": f"{len(comments_to_process)} unliked comments (0 likes)",
        "Liking Order": "Oldest to Newest (Chronological)" if order_choice == "asc" else "Newest to Oldest (Recent first)",
        "Comment Like Delay": f"{like_delay_range[0]} - {like_delay_range[1]} seconds",
        "Commenter Post Likes": f"Enabled ({posts_per_author} posts, {author_post_delay_range[0]}-{author_post_delay_range[1]}s delay)" if like_author_posts else "[red]Disabled[/red]",
        "Commenter Story Engagement": f"Enabled (Seen -> Like, {story_like_delay_range[0]}-{story_like_delay_range[1]}s delay)" if interact_with_latest_story else "[red]Disabled[/red]",
        "Batch Resting Pause": f"Every {rest_every} likes" if rest_every > 0 else "Continuous",
        "Account Warm-up": "Completed" if enable_warmup else "Skipped",
    }
    show_session_plan("Pre-Flight Engagement Mission Plan", session_plan)

    # ----------------- Engagement Loop -----------------
    console.print(f"\n[bold green]:rocket: Starting automated engagement loop for {len(comments_to_process)} comments...[/bold green]\n")
    processed_comments_count = 0
    author_posts_liked_count = 0
    stories_seen_count = 0
    stories_liked_count = 0
    start_time = time.time()

    try:
        for i, comment in enumerate(list(comments_to_process), start=1):
            c_pk = str(getattr(comment, 'pk', ''))
            media_pk = str(getattr(comment, 'media_pk', ''))
            
            user = getattr(comment, 'user', None)
            uname = str(getattr(user, 'username', '') if user else getattr(comment, 'author_username', ''))
            upk = str(getattr(user, 'pk', '') if user else getattr(comment, 'author_pk', ''))
            is_priv = bool(getattr(comment, 'is_private', False) or (getattr(user, 'is_private', False) if user else False))
            text = str(getattr(comment, 'text', '')).strip().replace("\n", " ")
            preview_text = (text[:60] + "...") if len(text) > 60 else text

            privacy_badge = "[red]:lock: Private[/red]" if is_priv else "[green]:globe_with_meridians: Public[/green]"
            show_section_divider(
                f":speech_balloon: Comment {i}/{len(comments_to_process)}: @{uname} ({privacy_badge}) | ID: {c_pk}",
                style="bold cyan"
            )
            log_print(f"Content: [italic white]\"{preview_text}\"[/italic white]")

            # ----------------- 1. Like Comment (if enabled) -----------------
            success = True
            if like_comments:
                success = cl.like_comment(
                    comment_pk=c_pk,
                    delay_range=like_delay_range,
                    username=uname,
                    user_pk=upk,
                    media_pk=media_pk,
                    comment_text=text
                )

            if success:
                processed_comments_count += 1

                # ----------------- 2. Optional: View and Like Latest Story -----------------
                if interact_with_latest_story and upk:
                    if is_priv:
                        log_warning(f"Commenter @{uname} has a private account. Skipping story interaction :lock:")
                    else:
                        with console.status(f"[bold cyan]Checking active stories for @{uname}...[/bold cyan]", spinner="dots"):
                            stories = cl.get_user_active_stories(upk)

                        if stories:
                            # Extract latest story (last item in chronological story list)
                            latest_story = stories[-1]
                            s_pk = str(getattr(latest_story, "pk", ""))
                            if s_pk:
                                # Step 2a: Mark latest story as seen
                                if not has_recent_interaction(s_pk, "story_seen"):
                                    st_seen = cl.seen_story(s_pk, username=uname, user_pk=upk)
                                    if st_seen:
                                        stories_seen_count += 1
                                        dwell = randint(2, 4)
                                        log_sleep(dwell, message=f"Watching latest story of @{uname} ({dwell}s)")
                                else:
                                    log_print(f"Latest story ({s_pk}) of @{uname} was already viewed :eye:")

                                # Step 2b: Like latest story
                                if not has_recent_interaction(s_pk, "story_like"):
                                    log_print(f"Liking latest story ({s_pk}) for @{uname} :sparkles: :heart:")
                                    st_liked = cl.like_story(
                                        s_pk,
                                        delay_range=story_like_delay_range,
                                        username=uname,
                                        user_pk=upk
                                    )
                                    if st_liked:
                                        stories_liked_count += 1
                                else:
                                    log_print(f"Latest story ({s_pk}) of @{uname} is already liked :heart:")
                        else:
                            log_print(f"No active public stories found for @{uname} :clapper:")

                # ----------------- 3. Optional: Like Commenter's Recent Posts -----------------
                if like_author_posts and upk:
                    if is_priv:
                        log_warning(f"Commenter @{uname} has a private account. Skipping post likes :lock:")
                    else:
                        with console.status(f"[bold cyan]Fetching recent posts for @{uname}...[/bold cyan]", spinner="dots"):
                            author_posts = cl.get_user_posts(upk, amount=posts_per_author)

                        if author_posts:
                            log_print(f"Found [bold cyan]{len(author_posts)}[/bold cyan] posts for @{uname}. Engaging... :camera:")
                            for p_idx, post in enumerate(author_posts, start=1):
                                p_pk = str(getattr(post, 'pk', ''))
                                if not p_pk:
                                    continue

                                has_liked = getattr(post, 'has_liked', False) or has_recent_interaction(p_pk, "like")
                                if has_liked:
                                    log_print(f"Post {p_pk} of @{uname} was already liked previously :white_check_mark:")
                                    continue

                                # Impression
                                cl.seen_user_post(p_pk, username=uname, user_pk=upk)
                                dwell_sec = randint(1, 2)
                                log_sleep(dwell_sec, message=f"Viewing @{uname}'s post {p_idx}/{len(author_posts)} ({dwell_sec}s)")

                                # Like post
                                p_liked = cl.like_user_post(
                                    p_pk,
                                    delay_range=author_post_delay_range,
                                    username=uname,
                                    user_pk=upk
                                )
                                if p_liked:
                                    author_posts_liked_count += 1
                        else:
                            log_print(f"No recent public posts found on @{uname}'s profile :warning:")

            # Remove from SQLite database queue
            remove_comment_from_queue(c_pk)
            if comment in comments_queue:
                comments_queue.remove(comment)

            rem_count = get_comment_queue_count()
            if rem_count == 0:
                log_success(":tada: All unliked comments in queue have been processed!")
            else:
                log_print(f":bar_chart: [bold blue]Remaining unliked comments in SQLite queue:[/bold blue] [bold magenta]{rem_count}[/bold magenta]")

            # Batch pause if enabled
            if rest_every > 0 and (processed_comments_count % rest_every == 0) and (i < len(comments_to_process)):
                batch_sleep = randint(120, 180)
                log_print(f"\n[bold yellow]:coffee: Completed batch of {rest_every} comment likes. Taking a safety rest ({batch_sleep}s)...[/bold yellow]")
                log_sleep(batch_sleep, message=f"Batch safety cooldown ({batch_sleep}s)")

    except KeyboardInterrupt:
        log_warning("\n:stop_sign: Process paused by user (Ctrl+C). Progress safely retained in SQLite database :floppy_disk:.")

    elapsed_sec = int(time.time() - start_time)
    elapsed_str = f"{elapsed_sec // 60}m {elapsed_sec % 60}s" if elapsed_sec >= 60 else f"{elapsed_sec}s"

    summary_metrics = {
        ":heart: Successfully Liked Comments": f"[bold green]{processed_comments_count}[/bold green]",
    }
    if interact_with_latest_story:
        summary_metrics[":clapper: Commenter Stories Viewed"] = f"[bold cyan]{stories_seen_count}[/bold cyan]"
        summary_metrics[":heart: Commenter Stories Liked"] = f"[bold green]{stories_liked_count}[/bold green]"
    if like_author_posts:
        summary_metrics[":camera: Commenter Posts Liked"] = f"[bold magenta]{author_posts_liked_count}[/bold magenta]"

    summary_metrics[":hourglass: Remaining in SQLite Queue"] = f"[bold yellow]{get_comment_queue_count()}[/bold yellow]"
    summary_metrics[":clock1: Total Elapsed Time"] = f"[bold cyan]{elapsed_str}[/bold cyan]"

    show_stats_card(
        "Post Comments Liker Summary",
        summary_metrics,
        border_style="magenta"
    )
    console.print("\n[bold blue]━━━━━━━━━━━━━━━━━━━━━━━━ :sparkles: All Done :sparkles: ━━━━━━━━━━━━━━━━━━━━━━━━[/bold blue]\n")
    notify_task_completed(
        "لایک‌کننده کامنت‌ها (Post Comments Liker)",
        f"تعداد {processed_comments_count} کامنت لایک شد. زمان: {elapsed_str}."
    )


if __name__ == "__main__":
    main()
