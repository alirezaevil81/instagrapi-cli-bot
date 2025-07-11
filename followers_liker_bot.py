from random import randint
from time import sleep
from bot.bot import Bot
from bot.utils import *
from bot.color_text import *

# ---------  login ------------
bot = Bot()
bot.start()

# ----------- get all followings --------------

followings = bot.get_all_self_following()

# ----------- config --------------

# set delay range for requests
bot.delay_range = [int(input("set delay range num 1:")), int(input("set delay range num 2:"))] 

# set sleep after iteration
sleep_after_iteration = int(input(text_warning("Enter the minutes of sleep after the iteration:"))) * 60

# set sleep after loop
sleep_after_loop = int(input(text_warning("Enter the hours of sleep after the last loop:"))) * 60 * 60

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
    for i,user in enumerate(followings.values()):
        log_print(text_warning(f"Iteration {i + 1}: Processing {user.username}"))
        user_posts = bot.get_user_posts(user.pk, 4)
        if user_posts != []:
            all_not_liked = False
            for i, post in enumerate(user_posts):
                if post.has_liked:
                    log_print(text_warning(f"post {post.pk} before liked"))
                else:
                    all_not_liked = True
                    ############# seen user post
                    bot.seen_user_post(post.pk)
                    ############# like user post
                    bot.like_user_post(post.pk)
                    ############# comment user post
                    if commenting:
                        bot.comment_user_post(post.pk)
            if all_not_liked:
                log_sleep(sleep_after_iteration) 
        else:
            log_print(text_warning(f"no posts found for {text_cyan(user.username)}"))
    loop = loop + 1
    log_print(text_warning(f"So far, we've completed {text_blue(f"{loop}")} rounds of the loop and have gotten {text_magenta(f"{sleep_after_loop}")} hours of sleep."))
    sleep(sleep_after_loop)

