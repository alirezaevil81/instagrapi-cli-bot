"""
Post Comments Liker Service: Extracts comments from target posts, filters unliked comments,
and likes them in order with safe human-like intervals and SQLite persistence.
"""
import os
import sys
import time
from random import randint
import questionary

from src.core.exceptions import (
    MediaNotFound,
    PrivateAccount,
    FeedbackRequired,
    PleaseWaitFewMinutes,
    ClientLoginRequired,
    LoginRequired,
    ClientError
)
from src.core.client import Bot
from src.database import (
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
    em
)


def extract_comments_from_posts(cl: Bot, posts: list, amount_per_post: int = 0, skip_own: bool = True) -> list:
    """
    Extracts unliked comments from a list of post URLs or PKs.
    Returns a list of unliked Comment objects.
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
                if post_str.startswith("http") or "instagram.com" in post_str:
                    media_pk = cl.media_pk_from_url(post_str)
                else:
                    media_pk = post_str

                media_id = cl.media_id(media_pk)

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

                # 1. Skip own comments if requested
                if skip_own and self_pk and author_pk == self_pk:
                    continue

                # 2. Check if already liked on Instagram or in SQLite interaction history
                has_liked = getattr(comment, 'has_liked', False)
                if has_liked:
                    continue

                if has_recent_interaction(c_pk, "comment_like"):
                    continue

                # Attach media_pk & author info to comment object
                setattr(comment, 'media_pk', str(media_id))
                setattr(comment, 'author_username', author_uname)
                setattr(comment, 'author_pk', author_pk)

                unliked_comments.append(comment)
                post_unliked += 1

            log_success(f"Found [bold green]{post_unliked}[/bold green] unliked comments on post {media_id} :sparkles:")

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
            log_error(f"Cannot fetch comments for post {post_str}: ", str(e))
            continue

    return unliked_comments


def main():
    init_db()
    register_graceful_shutdown()

    show_banner("Post Comments Liker Bot", "Extract Unliked Comments from Target Posts & Auto-Like with SQLite Queue")

    cl = Bot()
    cl.start()

    if not getattr(cl, 'user_id', None):
        log_warning("Not logged in. Exiting.")
        sys.exit(0)

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
        posts_raw = questionary.text(
            "Enter target post URLs or PKs (separated by comma):",
            validate=lambda val: True if len(val.strip()) > 0 else "Please provide at least one post URL"
        ).ask()

        if not posts_raw:
            log_warning("No post URLs provided. Exiting.")
            sys.exit(0)

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

        skip_own_comments = ask_yes_no(
            "Skip liking comments made by your own account?",
            default=True
        )

        # Extract comments
        comments_queue = extract_comments_from_posts(
            cl=cl,
            posts=posts,
            amount_per_post=max_comments_per_post,
            skip_own=skip_own_comments
        )

        if not comments_queue:
            log_warning("No unliked comments found from the specified posts.")
            sys.exit(0)

        # Save extracted comments into SQLite queue
        saved_count = save_target_comments_queue(comments_queue, clear_existing=True)
        log_success(f"Saved [bold cyan]{saved_count}[/bold cyan] unliked comments into SQLite database :floppy_disk:")

    # ----------------- Display Comments Table -----------------
    show_comment_table(comments_queue, title="Target Unliked Comments Queue (SQLite)")

    # ----------- Interactive Configuration (Questionary) --------------
    console.print("\n[bold cyan]:gear: Configure Bot Parameters[/bold cyan]")

    # Warm-up option (Selectable Yes/No)
    enable_warmup = ask_yes_no(
        "Perform natural account warm-up actions before starting?",
        default=True
    )

    # Ordering
    order_choice = questionary.select(
        em("Select comment liking order:"),
        choices=[
            questionary.Choice(title=em(":arrow_right: Oldest to Newest (Chronological order)"), value="asc"),
            questionary.Choice(title=em(":fast_forward: Newest to Oldest (Recent comments first)"), value="desc"),
        ]
    ).ask()

    if order_choice == "desc":
        comments_queue = list(reversed(comments_queue))

    # Delay range between comment likes
    like_delay_range = ask_delay_range("comment likes", default_range=[25, 50])

    # Maximum comments to like in this session
    max_likes_total = ask_int(
        f"How many unliked comments do you want to like in this session? (-1 for all {len(comments_queue)})",
        default=-1,
        min_val=-1
    )
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

    # ----------------- Engagement Loop -----------------
    console.print(f"\n[bold green]:rocket: Starting automated comment likes for {len(comments_to_process)} comments...[/bold green]\n")
    processed_count = 0
    start_time = time.time()

    try:
        for i, comment in enumerate(list(comments_to_process), start=1):
            c_pk = str(getattr(comment, 'pk', ''))
            media_pk = str(getattr(comment, 'media_pk', ''))
            
            user = getattr(comment, 'user', None)
            uname = str(getattr(user, 'username', '') if user else getattr(comment, 'author_username', ''))
            upk = str(getattr(user, 'pk', '') if user else getattr(comment, 'author_pk', ''))
            text = str(getattr(comment, 'text', '')).strip().replace("\n", " ")
            preview_text = (text[:60] + "...") if len(text) > 60 else text

            show_section_divider(
                f":speech_balloon: Comment {i}/{len(comments_to_process)}: @{uname} (ID: {c_pk})",
                style="bold cyan"
            )
            log_print(f"Content: [italic white]\"{preview_text}\"[/italic white]")

            # Like comment
            success = cl.like_comment(
                comment_pk=c_pk,
                delay_range=like_delay_range,
                username=uname,
                user_pk=upk,
                media_pk=media_pk,
                comment_text=text
            )

            if success:
                processed_count += 1

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
            if rest_every > 0 and (processed_count % rest_every == 0) and (i < len(comments_to_process)):
                batch_sleep = randint(120, 180)
                log_print(f"\n[bold yellow]:coffee: Completed batch of {rest_every} comment likes. Taking a safety rest ({batch_sleep}s)...[/bold yellow]")
                log_sleep(batch_sleep, message=f"Batch safety cooldown ({batch_sleep}s)")

    except KeyboardInterrupt:
        log_warning("\n:stop_sign: Process paused by user (Ctrl+C). Progress safely retained in SQLite database :floppy_disk:.")

    elapsed_sec = int(time.time() - start_time)
    elapsed_str = f"{elapsed_sec // 60}m {elapsed_sec % 60}s" if elapsed_sec >= 60 else f"{elapsed_sec}s"

    show_stats_card(
        "Post Comments Liker Summary",
        {
            ":heart: Successfully Liked Comments": f"[bold green]{processed_count}[/bold green]",
            ":hourglass: Remaining in SQLite Queue": f"[bold yellow]{get_comment_queue_count()}[/bold yellow]",
            ":clock1: Total Elapsed Time": f"[bold cyan]{elapsed_str}[/bold cyan]"
        },
        border_style="magenta"
    )
    console.print("\n[bold blue]━━━━━━━━━━━━━━━━━━━━━━━━ :sparkles: All Done :sparkles: ━━━━━━━━━━━━━━━━━━━━━━━━[/bold blue]\n")


if __name__ == "__main__":
    main()
