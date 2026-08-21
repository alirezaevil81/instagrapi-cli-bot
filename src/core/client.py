"""
Core Bot Client implementation.
Extends instagrapi.Client with 2FA, session management, organic warm-up, and safe actions.
"""
import os
from random import randint, choice
from instagrapi import Client
from instagrapi.exceptions import (
    ClientError,
    ClientLoginRequired,
    LoginRequired,
    TwoFactorRequired,
    BadPassword,
    InvalidUsername,
    AccountDisabled,
    ChallengeRequired,
    ChallengeUnknownStep,
    FeedbackRequired,
    PleaseWaitFewMinutes,
    RateLimitError,
    MediaNotFound,
    UserNotFound,
    PrivateAccount,
    ClientConnectionError,
    ClientBadRequestError,
    ClientForbiddenError,
    ClientThrottledError,
    ClientNotFoundError,
    ClientJSONDecodeError,
    ProxyAddressIsBlocked
)
import questionary
from src.config import comments, SESSIONS_DIR, ensure_storage_directories
from src.database.repository import record_interaction
from src.core.device import setup_client_device
from src.utils.console import (
    log_print,
    log_sleep,
    show_banner,
    fix_persian,
    log_success,
    log_error,
    log_warning,
    console
)

def default_challenge_code_handler(username: str, choice_method=None) -> str:
    """Handles Instagram security challenge code input interactively."""
    method_name = "SMS" if choice_method == 0 else "Email" if choice_method == 1 else "Security Code"
    log_warning(f"Instagram security challenge triggered for @{username} via {method_name}. :lock:")
    code = questionary.text(
        f"Enter the verification code sent to your {method_name}:",
        validate=lambda val: True if len(val.strip()) > 0 else "Verification code cannot be empty"
    ).ask()
    return (code or "").strip()

class Bot(Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.like_delay_range = [30, 60]
        self.comment_delay_range = [60, 90]
        self.posts_per_user = 3
        self.challenge_code_handler = default_challenge_code_handler

    def get_saved_sessions(self) -> list:
        """Returns a sorted list of saved session usernames from storage/sessions/."""
        ensure_storage_directories()
        if not os.path.exists(SESSIONS_DIR):
            return []
        sessions = [
            f[:-5] for f in os.listdir(SESSIONS_DIR)
            if f.endswith(".json") and os.path.isfile(os.path.join(SESSIONS_DIR, f))
        ]
        return sorted(sessions)

    def get_session_path(self, username: str) -> str:
        """Returns the full file path for an account session."""
        ensure_storage_directories()
        return os.path.join(SESSIONS_DIR, f"{username}.json")

    def start(self):
        ensure_storage_directories()
        show_banner("Instagram CLI Bot", "Automated Instagram Engagement & Liker Bot")

        login = False

        while not login:
            saved_sessions = self.get_saved_sessions()
            login_via_session = False
            username = None

            if saved_sessions:
                choices = [
                    questionary.Choice(
                        title=f"👤 @{u} ({fix_persian('سشن ذخیره‌شده')})",
                        value=u
                    ) for u in saved_sessions
                ]
                choices.append(
                    questionary.Choice(
                        title=f"➕ {fix_persian('ورود با اکانت جدید')} (Login with new account)",
                        value="__new__"
                    )
                )
                choices.append(
                    questionary.Choice(
                        title=f"🚪 {fix_persian('خروج')} (Exit)",
                        value="__exit__"
                    )
                )

                selected = questionary.select(
                    "Select an Instagram account / session to login:",
                    choices=choices
                ).ask()

                if not selected or selected == "__exit__":
                    log_warning("Exiting login flow.")
                    break
                elif selected == "__new__":
                    username = questionary.text(
                        "Enter your Instagram Username:",
                        validate=lambda val: True if len(val.strip()) > 0 else "Username cannot be empty"
                    ).ask()
                    if not username:
                        log_warning("Login canceled.")
                        break
                    username = username.strip()
                    login_via_session = False
                else:
                    username = selected.strip()
                    login_via_session = True
            else:
                username = questionary.text(
                    "Enter your Instagram Username:",
                    validate=lambda val: True if len(val.strip()) > 0 else "Username cannot be empty"
                ).ask()

                if not username:
                    log_warning("Exiting login flow.")
                    break

                username = username.strip()
                session_path = self.get_session_path(username)
                if os.path.exists(session_path):
                    login_via_session = questionary.confirm(
                        f"Saved session found for @{username}. Do you want to use it?",
                        default=True
                    ).ask()
                else:
                    login_via_session = False

            session_path = self.get_session_path(username)

            if login_via_session:
                try:
                    self.load_settings(session_path)
                    setup_client_device(self, username, session_loaded=True)
                    self.login(username, '1234')
                    self.get_timeline_feed()
                except (LoginRequired, ClientLoginRequired):
                    log_error("Session is invalid or expired. Re-authenticating...")
                    login_via_session = False
                except Exception as e:
                    log_error(f"Cannot login with session for @{username}: ", str(e))
                    login_via_session = False
                else:
                    log_success(f"Logged in successfully via saved session: @[bold cyan]{username}[/bold cyan] :key:")
                    login = True
                    break

            if not login_via_session:
                password = questionary.password(
                    f"Enter password for @{username}:",
                    validate=lambda val: True if len(val.strip()) > 0 else "Password cannot be empty"
                ).ask()

                if not password:
                    log_warning("Login canceled by user.")
                    continue

                # Apply persistent device fingerprint or real Termux device properties
                setup_client_device(self, username, session_loaded=False)

                try:
                    # Attempt standard login
                    self.login(username=username, password=password)
                except TwoFactorRequired:
                    log_warning(f"Two-Factor Authentication (2FA) required for @{username} :lock:")
                    two_factor_code = questionary.text(
                        "Enter your 6-digit 2FA / Authentication Code:",
                        validate=lambda val: True if len(val.strip()) > 0 else "2FA code cannot be empty"
                    ).ask()

                    if not two_factor_code:
                        log_error("2FA canceled by user.")
                        continue

                    try:
                        self.two_factor_login(two_factor_code.strip())
                    except Exception as e:
                        log_error("2FA Verification failed: ", str(e))
                        continue
                    else:
                        log_success(f"2FA verification successful for @{username} :unlock:")
                except BadPassword:
                    log_error(f"Incorrect password for @{username}. Please verify your credentials.")
                    continue
                except InvalidUsername:
                    log_error(f"Username @{username} does not exist.")
                    continue
                except AccountDisabled:
                    log_error(f"Account @{username} has been disabled by Instagram.")
                    break
                except ChallengeRequired as cr:
                    log_warning(f"Security challenge required: {cr}")
                    try:
                        self.challenge_resolve(self.last_json)
                    except Exception as ce:
                        log_error("Failed to resolve security challenge automatically: ", str(ce))
                        continue
                except ChallengeUnknownStep as cus:
                    log_error(f"Unsupported challenge step: {cus}")
                    continue
                except FeedbackRequired as fr:
                    log_error(f"Instagram action block / feedback required: {fr}")
                    continue
                except PleaseWaitFewMinutes:
                    log_warning("Rate limited by Instagram. Please wait a few minutes before trying again.")
                    continue
                except ClientConnectionError as cce:
                    log_error(f"Network connection error: {cce}")
                    continue
                except ClientForbiddenError as cfe:
                    log_error(f"Access forbidden: {cfe}")
                    continue
                except ProxyAddressIsBlocked:
                    log_error("Your IP or proxy address is blocked by Instagram.")
                    break
                except ClientError as ce:
                    log_error(f"Instagram ClientError: {ce}")
                    continue
                except Exception as e:
                    log_error(f"Unexpected error during login for @{username}: ", str(e))
                    continue

                log_success(f"Logged in successfully: @[bold cyan]{username}[/bold cyan] :white_check_mark:")
                self.dump_settings(session_path)
                log_success(f"Session saved to [bold green]{session_path}[/bold green] :floppy_disk:")
                login = True
                break

    def get_all_self_following(self) -> dict:
        """Fetches all followings of the logged-in user with status spinner."""
        followings = {}
        with console.status(f"[bold cyan]:hourglass_flowing_sand: {fix_persian('در حال دریافت لیست فالووینگ‌ها...')} (Fetching following list)...[/bold cyan]"):
            try:
                followings = self.user_following(self.user_id)
            except FeedbackRequired as fb:
                log_error(f"Instagram Feedback Required while fetching following: {fb}")
            except PleaseWaitFewMinutes:
                log_warning("Rate limit hit: Instagram requested to wait a few minutes.")
            except (LoginRequired, ClientLoginRequired):
                log_error("Login session expired. Please restart and re-login.")
            except Exception as e:
                log_error("Cannot fetch following: ", str(e))
            else:
                log_success(f"Found [bold magenta]{len(followings)}[/bold magenta] followings :heavy_check_mark:")
        return followings

    def get_user_posts(self, user_id: str, amount: int = 4) -> list:
        """Fetches posts of a specific user with error catching."""
        user_posts = []
        try:
            user_posts = self.user_medias(user_id, amount=amount)
        except MediaNotFound:
            log_warning(f"Media not found for user {user_id}")
        except UserNotFound:
            log_error(f"User {user_id} not found.")
        except PrivateAccount:
            log_warning(f"User {user_id} has a private account.")
        except FeedbackRequired as fb:
            log_error(f"Instagram Action Block / Feedback Required: {fb}")
        except PleaseWaitFewMinutes:
            log_warning("Rate limit hit: Please wait a few minutes.")
        except (LoginRequired, ClientLoginRequired):
            log_error("Session expired while fetching user posts.")
        except Exception as e:
            log_error(f"Cannot fetch posts for user {user_id}: ", str(e))
        return user_posts

    def perform_warmup_actions(self, max_feed_items: int = 4, view_stories: bool = True) -> None:
        """
        Human-like warm-up: reads timeline feed and marks recent stories as seen
        to mimic realistic organic browsing activity before starting automated tasks.
        """
        console.print(f"\n[bold magenta]:fire: {fix_persian('اقدامات گرم‌کردن طبیعی اکانت (Warm-up Actions)')}[/bold magenta]")
        log_print("Simulating organic user session: Browsing timeline feed & stories... :coffee:")

        # 1. Browse timeline feed
        try:
            feed = self.get_timeline_feed()
            feed_items = feed.get("feed_items", []) if isinstance(feed, dict) else []
            count = min(len(feed_items), max_feed_items)
            if count > 0:
                log_print(f"Viewing [bold cyan]{count}[/bold cyan] timeline posts naturally...")
                for item in feed_items[:count]:
                    browse_pause = randint(2, 4)
                    log_sleep(browse_pause, message=f"Reading timeline post ({browse_pause}s)")
            else:
                log_print("Timeline feed checked. :white_check_mark:")
        except Exception as e:
            log_warning(f"Warm-up feed browsing skipped: {e}")

        # 2. View stories if requested
        if view_stories:
            try:
                tray = self.get_timeline_stories()
                if tray and isinstance(tray, list):
                    story_count = 0
                    for story_tray in tray[:3]:
                        items = getattr(story_tray, 'items', []) or []
                        for story_item in items[:2]:
                            story_pk = str(getattr(story_item, 'pk', ''))
                            if story_pk:
                                self.media_seen([story_pk])
                                story_count += 1
                                sleep_sec = randint(1, 3)
                                time_rem = f"Story view pause ({sleep_sec}s)"
                                log_sleep(sleep_sec, message=time_rem)
                    if story_count > 0:
                        log_success(f"Organic warm-up complete: [bold magenta]{story_count}[/bold magenta] stories viewed :eyes:")
            except Exception as e:
                log_warning(f"Warm-up stories viewing skipped: {e}")

        log_success(f"{fix_persian('فاز آماده‌سازی اکانت با موفقیت به پایان رسید!')} :sparkles:")

    def seen_user_post(self, media_id: str, username: str = "", user_pk: str = "") -> bool:
        """Marks a post as seen with error catching and SQLite audit logging."""
        try:
            self.media_seen([media_id])
            log_success(f"Post {media_id} marked as seen :eye:")
            record_interaction(
                account_username=getattr(self, "username", "self"),
                action_type="seen",
                target_user_pk=str(user_pk),
                target_username=str(username),
                media_pk=str(media_id),
                success=True
            )
            return True
        except MediaNotFound:
            log_warning(f"Post {media_id} was deleted or not found.")
            return False
        except FeedbackRequired as fb:
            log_error(f"Instagram Feedback Required: {fb}")
            return False
        except PleaseWaitFewMinutes:
            log_warning("Rate limit hit on seen post: Instagram requested a cooldown.")
            return False
        except (LoginRequired, ClientLoginRequired):
            log_error("Session expired while marking post as seen.")
            return False
        except Exception as e:
            log_error(f"Cannot mark post {media_id} as seen: ", str(e))
            return False

    def like_user_post(self, media_id: str, delay_range=None, username: str = "", user_pk: str = "") -> bool:
        """Likes a post with proper instagrapi exception handling for spam detection and rate limits."""
        try:
            self.media_like(media_id)
            log_success(f"Liked post {media_id} :heart:")
            record_interaction(
                account_username=getattr(self, "username", "self"),
                action_type="like",
                target_user_pk=str(user_pk),
                target_username=str(username),
                media_pk=str(media_id),
                success=True
            )
            rng = delay_range or self.like_delay_range
            min_d, max_d = min(rng[0], rng[1]), max(rng[0], rng[1])
            sleep_sec = randint(min_d, max_d)
            log_sleep(sleep_sec, message="Resting after like")
            return True
        except MediaNotFound:
            log_warning(f"Post {media_id} was deleted or not found.")
            return False
        except FeedbackRequired as fb:
            log_error(f"Instagram Action Block / Feedback Required: {fb}")
            return False
        except PleaseWaitFewMinutes:
            log_warning("Rate limit hit: Instagram requested a cooldown. Pausing...")
            log_sleep(300, message="Instagram rate limit cooldown (5 mins)")
            return False
        except RateLimitError:
            log_warning("Instagram RateLimitError encountered. Pausing...")
            log_sleep(180, message="Rate limit cooldown")
            return False
        except (LoginRequired, ClientLoginRequired):
            log_error("Login session expired while liking post. Please restart and login.")
            return False
        except Exception as e:
            log_error(f"Cannot like post {media_id}: ", str(e))
            return False

    def comment_user_post(self, media_id: str, comment_list: list = None, delay_range=None, username: str = "", user_pk: str = "") -> bool:
        """Comments on a post with instagrapi exception handling and SQLite audit logging."""
        if comment_list is None:
            comment_list = comments
        try:
            comment = choice(comment_list)
            self.media_comment(media_id, comment)
            log_success(f"Commented: '{fix_persian(comment)}' on post {media_id} :speech_balloon:")
            record_interaction(
                account_username=getattr(self, "username", "self"),
                action_type="comment",
                target_user_pk=str(user_pk),
                target_username=str(username),
                media_pk=str(media_id),
                comment_text=comment,
                success=True
            )
            rng = delay_range or self.comment_delay_range
            min_d, max_d = min(rng[0], rng[1]), max(rng[0], rng[1])
            sleep_sec = randint(min_d, max_d)
            log_sleep(sleep_sec, message="Resting after comment")
            return True
        except MediaNotFound:
            log_warning(f"Post {media_id} was deleted or not found.")
            return False
        except FeedbackRequired as fb:
            log_error(f"Instagram Action Block on Comment: {fb}")
            return False
        except PleaseWaitFewMinutes:
            log_warning("Rate limit hit on commenting. Pausing...")
            log_sleep(300, message="Comment rate limit cooldown")
            return False
        except (LoginRequired, ClientLoginRequired):
            log_error("Session expired while commenting on post.")
            return False
        except Exception as e:
            log_error(f"Cannot comment on post {media_id}: ", str(e))
            return False
