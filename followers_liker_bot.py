import os, pickle
from random import randint, choice
from time import sleep
from instagrapi import Client
from prettytable import PrettyTable
from bot.utils import *
from bot.config import *
from bot.color_text import *

# ---------  login ------------

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

    cl = Client()
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

# ----------- get all followings --------------

try:
    followings = cl.user_following(cl.user_id)
except Exception as e:
    log_print(text_error("can`t get followings :",e))
else:
    log_print(text_success(f"all users added :{text_magenta(len(followings))}"))

# ----------- config --------------

# set delay range for requests
cl.delay_range = [int(input("set delay range num 1:")), int(input("set delay range num 2:"))]  

# set sleep after loop
hours = int(input(text_warning("Enter the hours of sleep after the last loop:")))
sleep_after_loop = hours_to_seconds(hours)

# set commenting true or false
if input(text_warning("Do you want to leave comments on posts? [Default is Y] [Y/N]: ")).lower() in ('no', 'n', 'No', 'N', 'NO'):
    commenting = False
    log_print(f"commenting is {text_red("off")}")
else:
    commenting = True
    log_print(f"commenting is {text_green("on")}")



# ------------ foreach to followings ------------
loop = 0
while True:
    for i,user in followings.values():
        log_print(text_warning(f"Iteration {i + 1}: Processing {user.username}"))
        user_posts = []
        try:
            user_posts = cl.user_medias(user.pk, 4)
        except Exception as e:
            log_print(text_error(f"to get {user.username} posts :",e))
        else:
            log_print(text_success(f"{user.username} posts getted"))
        if user_posts != []:
            all_not_liked = False
            for i, post in enumerate(user_posts):
                if post.has_liked:
                    log_print(text_warning(f"post {post.pk} before liked"))
                else:
                    all_not_liked = True
                    ############# like user post
                    try:
                        cl.media_like(post.pk)
                    except Exception as e:
                        log_print(text_error(f"to liking post {post.pk} :",e))
                    else:
                        log_print(text_success(f"post {post.pk} liked"))
                        log_sleep(randint(30, 60))
                    ############# comment user post
                    if commenting:
                        try:
                            comment = choice(comments)
                            cl.media_comment(post.pk, comment)
                        except Exception as e:
                            log_print(text_error(f"error to commenting on post {post.pk} :",e))
                        else:
                            log_print(text_success(f"commented={comment} on post {post.pk}"))
                            log_sleep(randint(60, 90))
            if all_not_liked:
                log_sleep(300) 
        else:
            log_print(text_warning(f"no posts found for {text_cyan(user.username)}"))
    loop = loop + 1
    log_print(text_warning(f"So far, we've completed {text_blue(f"{loop}")} rounds of the loop and have gotten {text_magenta(f"{hours}")} hours of sleep."))
    sleep(sleep_after_loop)

