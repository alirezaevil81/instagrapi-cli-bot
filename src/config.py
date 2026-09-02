"""
Application Configuration and Default Constants.
Centralized paths for storage, database, logs, and account sessions.
"""
import os
import shutil

# Storage root and subdirectories
STORAGE_DIR = "storage"
SESSIONS_DIR = os.path.join(STORAGE_DIR, "sessions")
DATABASE_DIR = os.path.join(STORAGE_DIR, "database")
LOGS_DIR = os.path.join(STORAGE_DIR, "logs")

# Explicit file paths
DB_PATH = os.path.join(DATABASE_DIR, "bot.db")
LOG_FILE_PATH = os.path.join(LOGS_DIR, "bot.log")
COMMENTS_FILE_PATH = "comments.txt"
COMMENTS_TEMPLATE_PATH = "comments.example.txt"

# Default API request delay range [min_seconds, max_seconds] (instagrapi cl.delay_range)
DELAY_RANGE = [3, 7]

def ensure_storage_directories():
    """Ensures all storage directories exist and comments file is initialized."""
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    os.makedirs(DATABASE_DIR, exist_ok=True)
    os.makedirs(LOGS_DIR, exist_ok=True)
    # Ensure comments.txt exists
    load_comments()

def load_comments(filepath: str = None) -> list:
    """
    Loads comments from a customizable text file (1 comment per line).
    If the file doesn't exist, it initializes it from comments.example.txt template.
    Lines starting with # or empty lines are ignored.
    """
    target_path = filepath or COMMENTS_FILE_PATH
    
    # Also check fallback in storage directory if root not found
    if not os.path.exists(target_path):
        alt_path = os.path.join(STORAGE_DIR, "comments.txt")
        if os.path.exists(alt_path):
            target_path = alt_path

    # Initialize from template if not present
    if not os.path.exists(target_path):
        try:
            if os.path.exists(COMMENTS_TEMPLATE_PATH):
                shutil.copy(COMMENTS_TEMPLATE_PATH, target_path)
            else:
                open(target_path, "a", encoding="utf-8").close()
        except Exception:
            return []

    try:
        loaded = []
        with open(target_path, "r", encoding="utf-8") as f:
            for line in f:
                cleaned = line.strip()
                if cleaned and not cleaned.startswith("#"):
                    loaded.append(cleaned)
        return loaded
    except Exception:
        return []

# Load initial comments list
comments = load_comments()
