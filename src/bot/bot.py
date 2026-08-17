import os
from random import randint, choice
from instagrapi import Client
from instagrapi.exceptions import (
    TwoFactorRequired,
    BadPassword,
    PleaseWaitFewMinutes
)
import questionary
from src.bot.config import comments
from src.bot.utils import log_print, log_sleep, show_banner, fix_persian, log_success, log_error, log_warning

class Bot(Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.like_delay_range = [30, 60]
        self.comment_delay_range = [60, 90]
        self.posts_per_user = 3

    def get_saved_sessions(self) -> list:
        """Returns a sorted list of saved session usernames from data/json/."""
        if not os.path.exists("data/json"):
            return []
        sessions = [
            f[:-5] for f in os.listdir("data/json")
            if f.endswith(".json") and os.path.isfile(os.path.join("data/json", f))
        ]
        return sorted(sessions)

    def start(self):
        os.makedirs("data/json", exist_ok=True)
        os.makedirs("data/pickle", exist_ok=True)
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
                session_path = f"data/json/{username}.json"
                if os.path.exists(session_path):
                    login_via_session = questionary.confirm(
                        f"Saved session found for @{username}. Do you want to use it?",
                        default=True
                    ).ask()
                else:
                    login_via_session = False

            session_path = f"data/json/{username}.json"

            if login_via_session:
                try:
                    self.load_settings(session_path)
                    self.login(username, '1234')
                    self.get_timeline_feed()
                except Exception as e:
                    log_error(f"Failed to login via session for @{username}: ", str(e))
                    retry_pwd = questionary.confirm(
                        f"Session expired for @{username}. Enter password to log in and renew session?",
                        default=True
                    ).ask()
                    if not retry_pwd:
                        continue
                    login_via_session = False
                else:
                    login = True
                    log_success(f"Session login successful for @{username}! :sparkles:")
            
            if not login and not login_via_session:
                password = questionary.password(
                    f"Enter Instagram password for @{username}:",
                    validate=lambda val: True if len(val) > 0 else "Password cannot be empty"
                ).ask()

                if password is None:
                    log_warning("Login canceled by user.")
                    continue

                try:
                    # Attempt standard login first without 2FA code to check if 2FA is needed
                    self.login(username=username, password=password)
                    self.dump_settings(session_path)
                    login = True
                    log_success(f"Login successful for @{username}! Session saved to {session_path} :floppy_disk:")
                except TwoFactorRequired:
                    log_warning("Two-Factor Authentication (2FA) is required for this account. :key:")
                    verify_code = questionary.text(
                        "Enter 2FA Verification Code (SMS / Authenticator App / Backup code):",
                        validate=lambda val: True if len(val.strip()) > 0 else "Verification code cannot be empty"
                    ).ask()

                    if verify_code is None or not verify_code.strip():
                        log_warning("2FA code was not entered. Returning to login.")
                        continue

                    try:
                        self.login(
                            username=username,
                            password=password,
                            verification_code=verify_code.strip()
                        )
                        self.dump_settings(session_path)
                        login = True
                        log_success(f"Login successful with 2FA for @{username}! Session saved to {session_path} :floppy_disk:")
                    except Exception as err_2fa:
                        log_error("2FA Login failed: ", str(err_2fa))
                except BadPassword:
                    log_error(f"Incorrect password for @{username}. Please check your credentials.")
                except PleaseWaitFewMinutes:
                    log_warning("Instagram temporary rate limit: Please wait a few minutes before trying again.")
                except Exception as e:
                    # Fallback check if 2FA was returned via generic exception
                    err_msg = str(e).lower()
                    if "two_factor" in err_msg or "2fa" in err_msg or "two-factor" in err_msg or "checkpoint" in err_msg:
                        log_warning("Two-Factor Authentication (2FA) is required for this account. :key:")
                        verify_code = questionary.text(
                            "Enter 2FA Verification Code (SMS / Authenticator App / Backup code):",
                            validate=lambda val: True if len(val.strip()) > 0 else "Verification code cannot be empty"
                        ).ask()

                        if verify_code is None or not verify_code.strip():
                            log_warning("2FA code was not entered. Returning to login.")
                            continue

                        try:
                            self.login(
                                username=username,
                                password=password,
                                verification_code=verify_code.strip()
                            )
                            self.dump_settings(session_path)
                            login = True
                            log_success(f"Login successful with 2FA for @{username}! Session saved to {session_path} :floppy_disk:")
                        except Exception as err_2fa:
                            log_error("2FA Login failed: ", str(err_2fa))
                    else:
                        log_error("Login failed: ", str(e))

    def get_all_self_following(self):
        try:
            followings = self.user_following(self.user_id)
            count = len(followings) if followings else 0
            log_success(f"Total followings fetched: [bold magenta]{count}[/bold magenta] :busts_in_silhouette:")
            return followings or {}
        except Exception as e:
            log_error("Cannot fetch followings: ", str(e))
            return {}

    def get_user_posts(self, user_id: str, amount: int = 4, sleep: int = 0):
        user_posts = []
        try:
            user_posts = self.user_medias(user_id, amount, sleep)
            log_success(f"User {user_id} posts fetched ({len(user_posts)} posts) :package:")
        except Exception as e:
            log_error(f"Cannot fetch posts for user {user_id}: ", str(e))
        return user_posts

    def seen_user_post(self, media_id):
        try:
            self.media_seen([media_id])
            log_success(f"Post {media_id} marked as seen :eye:")
        except Exception as e:
            log_error(f"Cannot mark post {media_id} as seen: ", str(e))

    def like_user_post(self, media_id, delay_range=None):
        try:
            self.media_like(media_id)
            log_success(f"Post {media_id} liked :heart:")
            rng = delay_range or self.like_delay_range
            min_d, max_d = min(rng[0], rng[1]), max(rng[0], rng[1])
            sleep_sec = randint(min_d, max_d)
            log_sleep(sleep_sec, message=f"Cooldown after like ({sleep_sec}s)")
        except Exception as e:
            log_error(f"Cannot like post {media_id}: ", str(e))

    def comment_user_post(self, media_id, comment_list: list = None, delay_range=None):
        if comment_list is None:
            comment_list = comments
        try:
            comment = choice(comment_list)
            self.media_comment(media_id, comment)
            log_success(f"Commented: '{fix_persian(comment)}' on post {media_id} :speech_balloon:")
            rng = delay_range or self.comment_delay_range
            min_d, max_d = min(rng[0], rng[1]), max(rng[0], rng[1])
            sleep_sec = randint(min_d, max_d)
            log_sleep(sleep_sec, message=f"Cooldown after comment ({sleep_sec}s)")
        except Exception as e:
            log_error(f"Error commenting on post {media_id}: ", str(e))
