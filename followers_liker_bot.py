import os, pickle
from random import randint, choice
from time import sleep
from instagrapi import Client
from prettytable import PrettyTable
from bot.utils import *
from bot.config import *

# ---------  login ------------

print(text_warning("If your account does not have two-step verification, Enter the input verification code blank.\n"))

login_via_session = False
login = False

while not login:

    username = input(f"Username{Fore.CYAN}(required){Style.RESET_ALL}: ")

    if os.path.exists(f"data/json/{username}.json"):
        session_input = input(text_warning(f'You have a session for {text_blue(username)}. Do you want to use it? [Default is Y] [Y/N]: '))
        if session_input.lower() in ('no', 'n', 'No', 'N', 'NO'):
            login_via_session = False
        else:
            login_via_session = True

    cl = Client()
    if login_via_session:
        try:
            cl.load_settings(f"data/json/{username}.json")
            cl.login(username, '1234')
            cl.get_timeline_feed()
        except Exception as e:
            print(text_error(f"to login via session :",e))
        else:
            login = True
            print(text_success("login via session successful!"))
    else:
        password = input(text_cyan("(required)"))
        verify_code = input(text_yellow("optional"))
        try:
            cl.login(username=username, password=password, verification_code=verify_code)
            cl.dump_settings(f"data/json/{username}.json")
        except Exception as e:
            print(text_error("error to login :",e))
        else:
            login = True
            print(text_success("login successful!"))

# ----------- get all followings --------------

cl.delay_range = [1, 2]

try:
    followings = cl.user_following(cl.user_id)
except Exception as e:
    print(text_error("can`t get followings :",e))
else:
    print(text_success("followings getted!"))

# ------------ foreach to followings ------------
while True:
    for user in followings.values():
        user_posts = []
        try:
            user_posts = cl.user_medias(user.pk, 1)
        except Exception as e:
            print(text_error(f"to get {user.username} posts :",e))
        else:
            print(text_success(f"{user.username} posts getted"))
        if user_posts != []:
            post = user_posts[0]
            if post.has_liked:
                print(text_warning(f"post {post.pk} before liked"))
            else:
                ############# like user post
                try:
                    cl.media_like(post.pk)
                except Exception as e:
                    print(text_error(f"to liking post {post.pk} :",e))
                else:
                    print(text_success(f"post {post.pk} liked"))
                    sleep(randint(60, 65))
                ############# comment user post
                try:
                    comment = choice(comments)
                    cl.media_comment(post.pk, comment)
                except Exception as e:
                    print(text_error(f"error to commenting on post {post.pk} :",e))
                else:
                    print(text_success(f"commented={comment} on post {post.pk}"))
                    sleep(randint(60, 90))
        else:
            print(text_warning(f"no posts found for {text_cyan(user.username)}"))

