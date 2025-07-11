import datetime
import time
from bot.color_text import text_green

def log_print(*args, **kwargs):
    iran_offset = 3.5
    current_time = datetime.datetime.fromtimestamp(time.time() + iran_offset * 3600)
    formatted_time = current_time.strftime('%Y-%m-%d %H:%M:%S')
    message = ' '.join(str(arg) for arg in args)
    formatted_message = f"[{formatted_time}] {message}"
    print(formatted_message, **kwargs)

def log_sleep(arg):
    log_print(f"{text_green(f"{arg} seconds ")}of sleep")
    time.sleep(arg)