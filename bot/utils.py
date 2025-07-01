from datetime import timedelta
import datetime
import time

def log_print(*args, **kwargs):
    iran_offset = 3.5
    current_time = datetime.datetime.fromtimestamp(time.time() + iran_offset * 3600)
    formatted_time = current_time.strftime('%Y-%m-%d %H:%M:%S')
    message = ' '.join(str(arg) for arg in args)
    formatted_message = f"[{formatted_time}] {message}"
    print(formatted_message, **kwargs)


def hours_to_seconds(hours):
    return timedelta(hours=hours).total_seconds()