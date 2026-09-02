"""
Core Bot Client implementation.
Extends instagrapi.Client with 2FA, session management, organic warm-up, and safe actions.
"""
import os
from random import randint, choice
from instagrapi import Client
from src.core.exceptions import (
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
from src.config import comments, SESSIONS_DIR, ensure_storage_directories, load_comments, COMMENTS_FILE_PATH, DELAY_RANGE
from src.database.repository import record_interaction, has_recent_interaction
from src.utils.console import (
    log_print,
    log_sleep,
    show_banner,
    fix_persian,
    format_bilingual_prompt,
    ask_yes_no,
    log_success,
    log_error,
    log_warning,
    console,
    em
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
        self.delay_range = list(DELAY_RANGE)
        self.like_delay_range = [30, 60]
        self.comment_delay_range = [60, 90]
        self.story_delay_range = [2, 5]
        self.posts_per_user = 3
        self.challenge_code_handler = default_challenge_code_handler
        # Ensure bloks_versioning_id is never empty to prevent CAA/Bloks hash errors
        if not getattr(self, "bloks_versioning_id", None):
            self.bloks_versioning_id = "ce555e5500576acd8e84a66018f54a05720f2dce29f0bb5a1f97f0c10d6fac48"

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
                        title=em(f":bust_in_silhouette: @{u}\n   ↪ {fix_persian('نشست و سشن ذخیره‌شده')}"),
                        value=u
                    ) for u in saved_sessions
                ]
                choices.append(
                    questionary.Choice(
                        title=em(f":key: Login via SessionID Cookie\n   ↪ {fix_persian('ورود مستقیم با SessionID کوکی اینستاگرام')}"),
                        value="__sessionid__"
                    )
                )
                choices.append(
                    questionary.Choice(
                        title=em(f":heavy_plus_sign: Login with new account\n   ↪ {fix_persian('ورود با اکانت جدید')}"),
                        value="__new__"
                    )
                )
                choices.append(
                    questionary.Choice(
                        title=em(f":door: Exit\n   ↪ {fix_persian('انصراف و خروج')}"),
                        value="__exit__"
                    )
                )

                selected = questionary.select(
                    em("Select an Instagram account / session to login:\n  ↪ " + fix_persian("یک اکانت یا سشن را جهت ورود انتخاب کنید:")),
                    choices=choices
                ).ask()

                if not selected or selected == "__exit__":
                    log_warning("Exiting login flow.")
                    break
                elif selected == "__sessionid__":
                    sessionid_val = questionary.password(
                        format_bilingual_prompt(
                            "Paste your Instagram SessionID cookie value",
                            "مقدار SessionID کوکی اکانت اینستاگرام خود را وارد کنید"
                        ),
                        validate=lambda val: True if len(val.strip()) > 0 else "SessionID cannot be empty"
                    ).ask()
                    if not sessionid_val:
                        log_warning("SessionID login canceled.")
                        continue

                    uname_for_sid = questionary.text(
                        format_bilingual_prompt(
                            "Enter the Username for this SessionID",
                            "نام کاربری مربوط به این SessionID را وارد کنید"
                        ),
                        validate=lambda val: True if len(val.strip()) > 0 else "Username cannot be empty"
                    ).ask()
                    if not uname_for_sid:
                        log_warning("Login canceled.")
                        continue

                    username = uname_for_sid.strip().lower()
                    try:
                        self.login_by_sessionid(sessionid_val.strip())
                        self.get_timeline_feed()
                    except Exception as se:
                        log_error("Failed to login via SessionID: ", str(se))
                        continue
                    else:
                        session_path = self.get_session_path(username)
                        self.dump_settings(session_path)
                        log_success(f"Logged in successfully via SessionID: @[bold cyan]{username}[/bold cyan] :key:")
                        log_success(f"Session saved to [bold green]{session_path}[/bold green] :floppy_disk:")
                        login = True
                        break

                elif selected == "__new__":
                    username = questionary.text(
                        format_bilingual_prompt(
                            "Enter your Instagram Username",
                            "نام کاربری اینستاگرام خود را وارد کنید"
                        ),
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
                login_method = questionary.select(
                    em("Select login method:\n  ↪ " + fix_persian("روش ورود به اکانت را انتخاب کنید:")),
                    choices=[
                        questionary.Choice(
                            title=em(f":bust_in_silhouette: Username & Password\n   ↪ {fix_persian('ورود با نام‌کاربری و رمز عبور')}"),
                            value="password"
                        ),
                        questionary.Choice(
                            title=em(f":key: SessionID Cookie (Recommended)\n   ↪ {fix_persian('ورود مستقیم با SessionID کوکی اینستاگرام (پیشنهادی)')}"),
                            value="sessionid"
                        ),
                        questionary.Choice(
                            title=em(f":door: Exit\n   ↪ {fix_persian('انصراف و خروج')}"),
                            value="exit"
                        ),
                    ]
                ).ask()

                if not login_method or login_method == "exit":
                    log_warning("Exiting login flow.")
                    break

                if login_method == "sessionid":
                    sessionid_val = questionary.password(
                        format_bilingual_prompt(
                            "Paste your Instagram SessionID cookie value",
                            "مقدار SessionID کوکی اینستاگرام خود را وارد کنید"
                        ),
                        validate=lambda val: True if len(val.strip()) > 0 else "SessionID cannot be empty"
                    ).ask()
                    if not sessionid_val:
                        log_warning("Login canceled.")
                        continue
                    uname_for_sid = questionary.text(
                        format_bilingual_prompt(
                            "Enter your Instagram Username",
                            "نام کاربری اکانت اینستاگرام خود را وارد کنید"
                        ),
                        validate=lambda val: True if len(val.strip()) > 0 else "Username cannot be empty"
                    ).ask()
                    if not uname_for_sid:
                        log_warning("Login canceled.")
                        continue
                    username = uname_for_sid.strip().lower()
                    try:
                        self.login_by_sessionid(sessionid_val.strip())
                        self.get_timeline_feed()
                    except Exception as se:
                        log_error("Failed to login via SessionID: ", str(se))
                        continue
                    else:
                        session_path = self.get_session_path(username)
                        self.dump_settings(session_path)
                        log_success(f"Logged in successfully via SessionID: @[bold cyan]{username}[/bold cyan] :key:")
                        log_success(f"Session saved to [bold green]{session_path}[/bold green] :floppy_disk:")
                        login = True
                        break

                username = questionary.text(
                    format_bilingual_prompt(
                        "Enter your Instagram Username",
                        "نام کاربری اینستاگرام خود را وارد کنید"
                    ),
                    validate=lambda val: True if len(val.strip()) > 0 else "Username cannot be empty"
                ).ask()

                if not username:
                    log_warning("Exiting login flow.")
                    break

                username = username.strip()
                session_path = self.get_session_path(username)
                if os.path.exists(session_path):
                    login_via_session = ask_yes_no(
                        f"Saved session found for @{username}. Do you want to use it?",
                        f"نشست ذخیره‌شده برای @{username} یافت شد. آیا مایل به استفاده از آن هستید؟",
                        default=True
                    )
                else:
                    login_via_session = False

            session_path = self.get_session_path(username)

            if login_via_session:
                try:
                    self.load_settings(session_path)
                    self.username = username
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
                    format_bilingual_prompt(
                        f"Enter password for @{username}",
                        f"رمز عبور اکانت @{username} را وارد کنید"
                    ),
                    validate=lambda val: True if len(val.strip()) > 0 else "Password cannot be empty"
                ).ask()

                if not password:
                    log_warning("Login canceled by user.")
                    continue

                try:
                    # Attempt standard login
                    self.login(username=username, password=password)
                except TwoFactorRequired:
                    log_warning(f"Two-Factor Authentication (2FA) required for @{username} :lock:")
                    two_factor_code = questionary.text(
                        format_bilingual_prompt(
                            "Enter your 6-digit 2FA / Authentication Code",
                            "کد ۶ رقمی احراز هویت دو مرحله‌ای (2FA) را وارد کنید"
                        ),
                        validate=lambda val: True if len(val.strip()) > 0 else "2FA code cannot be empty"
                    ).ask()

                    if not two_factor_code:
                        log_error("2FA canceled by user.")
                        continue

                    try:
                        # In instagrapi, 2FA code is passed via verification_code to login method
                        self.login(username=username, password=password, verification_code=two_factor_code.strip())
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

                self.username = username
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

    def fetch_timeline_feed_posts_24h(self, max_pages: int = 6, cutoff_hours: float = 24.0, fallback_if_empty: bool = True) -> list:
        """
        Fetches timeline feed posts paginating through multiple pages,
        filters for posts published in the last `cutoff_hours` (default 24h),
        skips ads/promotions, and sorts them from newest to oldest.
        If cutoff_hours <= 0, returns all fetched feed posts without time limit.
        """
        import time
        from datetime import datetime, timezone

        posts = []
        all_scanned_posts = []
        seen_pks = set()
        now_ts = time.time()
        cutoff_ts = now_ts - (cutoff_hours * 3600) if cutoff_hours > 0 else 0

        max_id = None
        feed_seen_posts = []
        consecutive_old_pages = 0

        for page in range(1, max_pages + 1):
            try:
                reason = "pull_to_refresh" if page == 1 else "pagination"
                
                # Fetch timeline feed using direct private request with proper POST body pagination
                feed_data = None
                try:
                    post_data = {
                        "_uuid": getattr(self, "uuid", ""),
                        "_uid": str(getattr(self, "user_id", "") or ""),
                        "_csrftoken": getattr(self, "token", ""),
                        "is_prefetch": "0",
                        "feed_view_info": "[]",
                        "seen_posts": ",".join([str(p) for p in feed_seen_posts[-20:]]) if feed_seen_posts else "",
                        "phone_id": getattr(self, "phone_id", ""),
                        "battery_level": "100",
                        "is_charging": "1",
                        "is_pull_to_refresh": "0" if max_id else "1",
                        "reason": reason,
                        "will_sound_on": "0",
                    }
                    if max_id:
                        post_data["max_id"] = str(max_id)
                        post_data["next_max_id"] = str(max_id)
                    
                    feed_data = self.private_request("feed/timeline/", data=post_data)
                except Exception as req_err:
                    # Fallback to get_timeline_feed if private_request fails
                    try:
                        feed_data = self.get_timeline_feed(reason=reason)
                    except Exception as priv_err:
                        log_error(f"Timeline feed request error: {priv_err}")
                        break

                if not feed_data or not isinstance(feed_data, dict):
                    break
                    
                # Support various response containers
                raw_items = (
                    feed_data.get("feed_items")
                    or feed_data.get("items")
                    or feed_data.get("ranked_items")
                    or []
                )

                if not raw_items:
                    break

                page_new_count = 0
                page_old_count = 0

                def extract_all_medias(it):
                    if not isinstance(it, dict):
                        return [it]
                    found = []
                    # 1. Direct media_or_ad
                    if isinstance(it.get("media_or_ad"), dict):
                        found.append(it["media_or_ad"])
                    # 2. Clips item
                    if isinstance(it.get("clips_item"), dict):
                        clip_media = it["clips_item"].get("media") or it["clips_item"]
                        if isinstance(clip_media, dict):
                            found.append(clip_media)
                    # 3. Clips netego
                    if isinstance(it.get("clips_netego"), dict):
                        for c in it["clips_netego"].get("items", []):
                            if isinstance(c, dict):
                                found.append(c.get("media") or c)
                    # 4. Direct media
                    if isinstance(it.get("media"), dict):
                        found.append(it["media"])
                    # 5. Nested items / carousel
                    if isinstance(it.get("items"), list):
                        for sub_it in it["items"]:
                            found.extend(extract_all_medias(sub_it))
                    if isinstance(it.get("carousel_media"), list):
                        for sub_it in it["carousel_media"]:
                            found.extend(extract_all_medias(sub_it))
                    # 6. Fallback: it has pk/id/code or it's a raw dict
                    if not found and ("pk" in it or "id" in it or "code" in it):
                        found.append(it)
                    return found

                for item in raw_items:
                    if not item:
                        continue

                    candidate_medias = extract_all_medias(item)
                    for media_data in candidate_medias:
                        if not media_data:
                            continue

                        # Extract PK / ID
                        raw_pk = (
                            (media_data.get("pk") if isinstance(media_data, dict) else None)
                            or (media_data.get("id") if isinstance(media_data, dict) else None)
                            or getattr(media_data, "pk", None)
                            or getattr(media_data, "id", None)
                            or (item.get("pk") if isinstance(item, dict) else None)
                            or (item.get("id") if isinstance(item, dict) else None)
                        )
                        
                        if raw_pk is None or str(raw_pk).strip().lower() in ("", "none", "0"):
                            continue

                        pk_str = str(raw_pk).split("_")[0].strip()
                        if not pk_str:
                            continue

                        pk = pk_str

                        # Track in feed_seen_posts for IG pagination cursor
                        if pk not in feed_seen_posts:
                            feed_seen_posts.append(pk)

                        if pk in seen_pks:
                            continue

                        # Extract timestamp
                        taken_at_raw = (
                            getattr(media_data, "taken_at", None)
                            if not isinstance(media_data, dict)
                            else (
                                media_data.get("taken_at")
                                or media_data.get("device_timestamp")
                                or (media_data.get("caption", {}) or {}).get("created_at")
                                or (media_data.get("caption", {}) or {}).get("created_at_utc")
                            )
                        )

                        taken_at_ts = None
                        if isinstance(taken_at_raw, datetime):
                            taken_at_ts = taken_at_raw.timestamp()
                        elif isinstance(taken_at_raw, (int, float)):
                            taken_at_ts = float(taken_at_raw)
                        elif isinstance(taken_at_raw, str) and taken_at_raw.replace(".", "", 1).isdigit():
                            taken_at_ts = float(taken_at_raw)

                        if taken_at_ts:
                            if taken_at_ts > 100_000_000_000_000:
                                taken_at_ts = taken_at_ts / 1_000_000
                            elif taken_at_ts > 100_000_000_000:
                                taken_at_ts = taken_at_ts / 1_000
                        else:
                            taken_at_ts = now_ts

                        # Extract author info
                        user_info = (
                            (getattr(media_data, "user", {}) if not isinstance(media_data, dict) else media_data.get("user", {}))
                            or (getattr(media_data, "owner", {}) if not isinstance(media_data, dict) else media_data.get("owner", {}))
                        )
                        author_username = getattr(user_info, "username", "") if not isinstance(user_info, dict) else user_info.get("username", "")
                        author_pk = str(getattr(user_info, "pk", "") if not isinstance(user_info, dict) else (user_info.get("pk") or user_info.get("id") or ""))
                        author_full_name = getattr(user_info, "full_name", "") if not isinstance(user_info, dict) else user_info.get("full_name", "")

                        # Extract like status (only check if liked or not)
                        has_liked = bool(getattr(media_data, "has_liked", False) if not isinstance(media_data, dict) else media_data.get("has_liked", False))

                        caption_raw = getattr(media_data, "caption", "") if not isinstance(media_data, dict) else media_data.get("caption")
                        caption_text = ""
                        if isinstance(caption_raw, dict):
                            caption_text = caption_raw.get("text", "")
                        elif isinstance(caption_raw, str):
                            caption_text = caption_raw
                        elif hasattr(caption_raw, "text"):
                            caption_text = getattr(caption_raw, "text", "")

                        code = getattr(media_data, "code", "") if not isinstance(media_data, dict) else media_data.get("code", "")
                        like_count = getattr(media_data, "like_count", 0) if not isinstance(media_data, dict) else media_data.get("like_count", 0)
                        comment_count = getattr(media_data, "comment_count", 0) if not isinstance(media_data, dict) else media_data.get("comment_count", 0)

                        seen_pks.add(pk)

                        post_obj = {
                            "pk": pk,
                            "code": code,
                            "author_username": author_username or "instagram_user",
                            "author_pk": author_pk,
                            "author_full_name": author_full_name,
                            "taken_at_ts": taken_at_ts,
                            "taken_at_dt": datetime.fromtimestamp(taken_at_ts, tz=timezone.utc),
                            "has_liked": has_liked,
                            "caption_text": caption_text,
                            "like_count": like_count,
                            "comment_count": comment_count,
                        }

                        all_scanned_posts.append(post_obj)
                        page_new_count += 1
                        posts.append(post_obj)

                log_print(f"Feed Page [bold cyan]{page}[/bold cyan]: {len(raw_items)} items retrieved | [bold green]{page_new_count}[/bold green] posts found")

                # Check pagination cursor
                next_max_id = (
                    feed_data.get("next_max_id")
                    or feed_data.get("max_id")
                    or (feed_data.get("pagination_info") or {}).get("next_max_id")
                    or (feed_data.get("pagination_info") or {}).get("group_next_max_id")
                )
                if not next_max_id:
                    break

                max_id = next_max_id

                if cutoff_hours > 0 and page_old_count > 5 and page_new_count == 0:
                    consecutive_old_pages += 1
                    if consecutive_old_pages >= 2:
                        break
                else:
                    consecutive_old_pages = 0

                time.sleep(randint(1, 3))

            except FeedbackRequired as fb:
                log_error(f"Instagram Feedback Required during feed fetch: {fb}")
                break
            except PleaseWaitFewMinutes:
                log_warning("Rate limit hit during feed fetch. Instagram requested cooldown.")
                break
            except (LoginRequired, ClientLoginRequired):
                log_error("Session expired during feed fetch.")
                break
            except Exception as e:
                log_error(f"Error fetching timeline page {page}: ", str(e))
                break

        # Fallback to scanned posts if 24h filter produced 0 items but feed has posts
        if not posts and all_scanned_posts and fallback_if_empty:
            log_warning(
                f"No posts within the strict {cutoff_hours:g}h window, but found [bold cyan]{len(all_scanned_posts)}[/bold cyan] recent posts in your feed. Applying fallback..."
            )
            posts = all_scanned_posts

        # Sort posts from newest to oldest (descending timestamp)
        posts.sort(key=lambda p: p["taken_at_ts"], reverse=True)
        return posts

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
                # Use user_stories or get_timeline_feed stories tray
                tray = None
                if hasattr(self, "get_timeline_stories"):
                    tray = self.get_timeline_stories()
                elif hasattr(self, "reels_tray"):
                    tray = self.reels_tray()

                if tray and isinstance(tray, list):
                    story_count = 0
                    for story_tray in tray[:3]:
                        items = getattr(story_tray, 'items', []) or []
                        for story_item in items[:2]:
                            story_pk = str(getattr(story_item, 'pk', ''))
                            if story_pk and story_pk.isdigit():
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
        from rich.emoji import Emoji
        if comment_list is None:
            comment_list = load_comments()
        if not comment_list:
            log_warning("No comments found in comments.txt! Please add your comments to comments.txt. :warning:")
            return False
        try:
            raw_comment = choice(comment_list)
            comment_text = Emoji.replace(raw_comment)
            self.media_comment(media_id, comment_text)
            log_success(f"Commented: '{fix_persian(raw_comment)}' on post {media_id} :speech_balloon:")
            record_interaction(
                account_username=getattr(self, "username", "self"),
                action_type="comment",
                target_user_pk=str(user_pk),
                target_username=str(username),
                media_pk=str(media_id),
                comment_text=comment_text,
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

    def get_user_active_stories(self, user_pk: str) -> list:
        """Fetches active stories for a given user_pk safely."""
        try:
            stories = []
            pk_int = int(user_pk)
            if hasattr(self, "user_stories"):
                stories = self.user_stories(pk_int) or []
            elif hasattr(self, "user_stories_v1"):
                stories = self.user_stories_v1(pk_int) or []
            return stories
        except (LoginRequired, ClientLoginRequired):
            log_error("Login session expired while fetching user stories.")
            return []
        except FeedbackRequired as fb:
            log_error(f"Instagram Feedback Required when fetching stories: {fb}")
            return []
        except PleaseWaitFewMinutes:
            log_warning("Instagram rate limit hit while checking stories.")
            return []
        except Exception as e:
            log_warning(f"Could not retrieve active stories for user {user_pk}: {e}")
            return []

    def seen_story(self, story_pk: str, username: str = "", user_pk: str = "") -> bool:
        """Marks a story as seen with error catching and SQLite audit logging."""
        try:
            str_pk = str(story_pk)
            if hasattr(self, "story_seen"):
                try:
                    self.story_seen([int(str_pk)])
                except Exception:
                    self.media_seen([str_pk])
            else:
                self.media_seen([str_pk])

            record_interaction(
                account_username=getattr(self, "username", "self"),
                action_type="story_seen",
                target_user_pk=str(user_pk),
                target_username=str(username),
                media_pk=str_pk,
                success=True
            )
            return True
        except MediaNotFound:
            log_warning(f"Story {story_pk} was deleted or expired.")
            return False
        except FeedbackRequired as fb:
            log_error(f"Instagram Feedback Required on story seen: {fb}")
            return False
        except PleaseWaitFewMinutes:
            log_warning("Rate limit hit on seen story.")
            return False
        except (LoginRequired, ClientLoginRequired):
            log_error("Session expired while marking story as seen.")
            return False
        except Exception as e:
            log_warning(f"Could not mark story {story_pk} as seen: {e}")
            return False

    def like_story(self, story_pk: str, delay_range=None, username: str = "", user_pk: str = "") -> bool:
        """Likes a story with instagrapi exception handling, SQLite logging and customizable delay."""
        try:
            str_pk = str(story_pk)
            liked_successfully = False
            if hasattr(self, "story_like"):
                try:
                    res = self.story_like(str_pk)
                    liked_successfully = (res is not False)
                except Exception:
                    res = self.media_like(str_pk)
                    liked_successfully = (res is not False)
            else:
                res = self.media_like(str_pk)
                liked_successfully = (res is not False)

            if liked_successfully:
                log_success(f"Liked story {story_pk} of @{username} :heart:")
                record_interaction(
                    account_username=getattr(self, "username", "self"),
                    action_type="story_like",
                    target_user_pk=str(user_pk),
                    target_username=str(username),
                    media_pk=str_pk,
                    success=True
                )
                rng = delay_range or self.story_delay_range
                min_d, max_d = min(rng[0], rng[1]), max(rng[0], rng[1])
                sleep_sec = randint(min_d, max_d)
                log_sleep(sleep_sec, message=f"Resting after story like ({sleep_sec}s)")
                return True
            return False
        except MediaNotFound:
            log_warning(f"Story {story_pk} was deleted or expired.")
            return False
        except FeedbackRequired as fb:
            log_error(f"Instagram Action Block / Feedback Required on story like: {fb}")
            return False
        except PleaseWaitFewMinutes:
            log_warning("Rate limit hit: Instagram requested a cooldown on story like. Pausing...")
            log_sleep(300, message="Instagram rate limit cooldown (5 mins)")
            return False
        except RateLimitError:
            log_warning("Instagram RateLimitError encountered on story like. Pausing...")
            log_sleep(180, message="Rate limit cooldown (3 mins)")
            return False
        except (LoginRequired, ClientLoginRequired):
            log_error("Login session expired while liking story.")
            return False
        except Exception as e:
            log_error(f"Cannot like story {story_pk}: ", str(e))
            return False

    def process_user_stories(self, user_pk: str, username: str = "", delay_range=None, like_stories: bool = True) -> tuple[int, int]:
        """
        Non-randomly processes ALL active stories for a user:
        1. Views every story of the user (unless already marked seen in DB).
        2. Likes every story of the user (if like_stories is True and not already liked in DB).
        Returns (stories_seen_count, stories_liked_count).
        """
        stories = self.get_user_active_stories(user_pk)
        if not stories:
            return 0, 0

        seen_count = 0
        liked_count = 0
        total_stories = len(stories)
        log_print(f"Found [bold magenta]{total_stories}[/bold magenta] active stories for @[bold yellow]{username}[/bold yellow] :clapper:")

        for s_idx, story in enumerate(stories, start=1):
            story_pk = str(getattr(story, "pk", ""))
            if not story_pk:
                continue

            # 1. View story
            if not has_recent_interaction(story_pk, "story_seen"):
                seen = self.seen_story(story_pk, username=username, user_pk=user_pk)
                if seen:
                    seen_count += 1
                    # Natural story viewing dwell time (1 to 2 seconds)
                    dwell = randint(1, 2)
                    log_sleep(dwell, message=f"Watching story {s_idx}/{total_stories} ({dwell}s)")
            else:
                log_print(f"Story {story_pk} of @{username} was already viewed previously :eye:")

            # 2. Like story (if requested and not already liked)
            if like_stories:
                if not has_recent_interaction(story_pk, "story_like"):
                    liked = self.like_story(
                        story_pk,
                        delay_range=delay_range or self.story_delay_range,
                        username=username,
                        user_pk=user_pk
                    )
                    if liked:
                        liked_count += 1
                else:
                    log_print(f"Story {story_pk} of @{username} is already liked :heart:")

        if seen_count > 0 or liked_count > 0:
            log_success(f"Completed stories for @[bold yellow]{username}[/bold yellow]: [bold cyan]{seen_count}[/bold cyan] viewed, [bold green]{liked_count}[/bold green] liked :sparkles:")

        return seen_count, liked_count

