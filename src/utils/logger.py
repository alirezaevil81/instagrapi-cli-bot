import logging
from logging.handlers import RotatingFileHandler
import os
import re
from src.config import LOG_FILE_PATH, LOGS_DIR

_file_logger: logging.Logger = None

def get_file_logger() -> logging.Logger:
    """Initializes and returns rotating file logger writing clean text to storage/logs/bot.log."""
    global _file_logger
    if _file_logger is not None:
        return _file_logger

    os.makedirs(LOGS_DIR, exist_ok=True)
    logger = logging.getLogger("instabot")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if not logger.handlers:
        file_handler = RotatingFileHandler(
            LOG_FILE_PATH,
            maxBytes=5 * 1024 * 1024,  # 5 MB per log file
            backupCount=3,
            encoding="utf-8"
        )
        formatter = logging.Formatter(
            fmt="[%(asctime)s] [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    _file_logger = logger
    return _file_logger

def clean_rich_markup(text: str) -> str:
    """Strips Rich console tags and emojis for clean file logging."""
    if not isinstance(text, str):
        text = str(text)
    clean = re.sub(r'\[/?[a-zA-Z0-9_\s#]+\]', '', text)
    clean = re.sub(r':[a-zA-Z0-9_+-]+:', '', clean).strip()
    return clean
