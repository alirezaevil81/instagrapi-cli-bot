"""
Application Configuration and Default Constants.
Centralized paths for storage, database, logs, and account sessions.
"""
import os

# Storage root and subdirectories
STORAGE_DIR = "storage"
SESSIONS_DIR = os.path.join(STORAGE_DIR, "sessions")
DATABASE_DIR = os.path.join(STORAGE_DIR, "database")
LOGS_DIR = os.path.join(STORAGE_DIR, "logs")

# Explicit file paths
DB_PATH = os.path.join(DATABASE_DIR, "bot.db")
LOG_FILE_PATH = os.path.join(LOGS_DIR, "bot.log")

def ensure_storage_directories():
    """Ensures all storage directories exist."""
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    os.makedirs(DATABASE_DIR, exist_ok=True)
    os.makedirs(LOGS_DIR, exist_ok=True)

# Default Persian comments for automated interactions
comments = [
    "عالی 😊👍",
    "فوق‌العاده ✨🌟",
    "بی‌نظیر 😍👌",
    "شگفت‌انگیز 🤩🎉",
    "جذاب 😘💖",
    "دوست‌داشتنی 🥰❤️",
    "معرکه 😎🔥",
    "تحسین‌برانگیز 👏🌈",
    "ستودنی 🚀💫",
    "درخشان 🌟😍"
]
