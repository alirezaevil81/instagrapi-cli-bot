import os
from random import randint, choice
from instagrapi import Client
from bot.config import *
from bot.utils import *
from bot.color_text import *

class Bot(Client):
    def start(self):
        log_print(text_warning("If your account does not have two-step verification, Enter the input verification code blank.\n"))
        
        login_via_session = False
        login = False

        while not login:

            username = input(f"Username{text_cyan("(required)")}: ")

            if os.path.exists(f"data/json/{username}.json"):
                session_input = input(text_warning(f'You have a session for {text_blue(username)}. Do you want to use it? [Default is Y] [Y/N]: '))
                if session_input.lower() in ('no', 'n', 'No', 'N', 'NO'):
                    login_via_session = False
                else:
                    login_via_session = True

            cl = self
            if login_via_session:
                try:
                    cl.load_settings(f"data/json/{username}.json")
                    cl.login(username, '1234')
                    cl.get_timeline_feed()
                except Exception as e:
                    log_print(text_error(f"to login via session :",e))
                else:
                    login = True
                    log_print(text_success("login via session successful!"))
            else:
                password = input(f"Password{text_cyan("(required)")}:")
                verify_code = input(f"Verify code{text_cyan("(optional)")}:")
                try:
                    cl.login(username=username, password=password, verification_code=verify_code)
                    cl.dump_settings(f"data/json/{username}.json")
                except Exception as e:
                    log_print(text_error("error to login :",e))
                else:
                    login = True
                    log_print(text_success("login successful!"))

    def get_all_self_following(self):
        try:
            return self.user_following(self.user_id)
        except Exception as e:
            log_print(text_error("can`t get followings :",e))
        else:
            log_print(text_success(f"all users added :{text_magenta(len(followings))}"))

    def get_user_posts(self,user_id: str,amount: int = 0,sleep: int = 0):
        user_posts = []
        try:
            user_posts = self.user_medias(user_id, amount, sleep)
        except Exception as e:
            log_print(text_error(f"to get {self.username} posts :",e))
        else:
            log_print(text_success(f"{self.username} posts getted"))
        return user_posts

    def seen_user_post(self,media_id):
        try:
            self.media_seen([media_id])
        except Exception as e:
            log_print(text_error(f"to seen post {media_id} :",e))
        else:
            log_print(text_success(f"post {media_id} seen"))
        
    def like_user_post(self,media_id):
        try:
            self.media_like(media_id)
        except Exception as e:
            log_print(text_error(f"to liking post {media_id} :",e))
        else:
            log_print(text_success(f"post {media_id} liked"))
            log_sleep(randint(30, 60))

    def comment_user_post(self,media_id,comments: list = comments):
        try:
            comment = choice(comments)
            self.media_comment(media_id, comment)
        except Exception as e:
            log_print(text_error(f"error to commenting on post {media_id} :",e))
        else:
            log_print(text_success(f"commented={comment} on post {media_id}"))
            log_sleep(randint(60, 90))