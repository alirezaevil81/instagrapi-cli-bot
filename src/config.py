"""
Application Configuration and Default Constants.
Centralized paths for storage, database, logs, and account sessions.
"""
import os
import shutil
import json

# Storage root and subdirectories
STORAGE_DIR = os.getenv("STORAGE_DIR", "storage")
SESSIONS_DIR = os.path.join(STORAGE_DIR, "sessions")
DATABASE_DIR = os.path.join(STORAGE_DIR, "database")
LOGS_DIR = os.path.join(STORAGE_DIR, "logs")

# Explicit file paths
DB_PATH = os.path.join(DATABASE_DIR, "bot.db")
LOG_FILE_PATH = os.path.join(LOGS_DIR, "bot.log")
COMMENTS_FILE_PATH = os.getenv("COMMENTS_FILE_PATH", "comments.json")
COMMENTS_TEMPLATE_PATH = os.getenv("COMMENTS_TEMPLATE_PATH", "comments.example.json")

def load_env_file(filepath: str = ".env"):
    """Loads key-value pairs from a .env file into os.environ without overwriting existing vars."""
    search_paths = [
        filepath,
        os.path.join(os.getcwd(), filepath),
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), filepath),
    ]
    for path in search_paths:
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        if "=" in line:
                            key, val = line.split("=", 1)
                            key = key.strip()
                            val = val.strip()
                            if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                                val = val[1:-1]
                            if key not in os.environ:
                                os.environ[key] = val
                break
            except Exception:
                pass

# Load .env file automatically
load_env_file()

def parse_delay_range(val, default=(3, 7)) -> list:
    """Parses delay range string like '[3, 7]', '3, 7', or '3-7' into [min, max] list of integers."""
    if not val:
        return list(default)
    if isinstance(val, (list, tuple)):
        return [int(val[0]), int(val[1])]
    if isinstance(val, str):
        cleaned = val.strip().strip("'\"").strip("[]()")
        parts = [p.strip() for p in cleaned.replace("-", ",").split(",") if p.strip()]
        if len(parts) >= 2:
            try:
                return [int(parts[0]), int(parts[1])]
            except ValueError:
                pass
        elif len(parts) == 1:
            try:
                n = int(parts[0])
                return [n, n]
            except ValueError:
                pass
    return list(default)

def get_delay_range() -> list:
    """
    Returns the parsed API request delay range [min_seconds, max_seconds] (instagrapi cl.delay_range)
    from environment (.env DELAY_RANGE_MIN / DELAY_RANGE_MAX or DELAY_RANGE) or falls back to default [3, 7].
    """
    d_min = os.getenv("DELAY_RANGE_MIN") or os.getenv("DELAY_MIN")
    d_max = os.getenv("DELAY_RANGE_MAX") or os.getenv("DELAY_MAX")
    if d_min is not None and d_max is not None:
        try:
            val_min = int(d_min.strip())
            val_max = int(d_max.strip())
            return [min(val_min, val_max), max(val_min, val_max)]
        except ValueError:
            pass

    raw = os.getenv("DELAY_RANGE")
    if raw:
        return parse_delay_range(raw, default=[3, 7])
    return [3, 7]

# Default API request delay range [min_seconds, max_seconds] (instagrapi cl.delay_range)
DELAY_RANGE = get_delay_range()

def ensure_storage_directories():
    """Ensures all storage directories exist and comments file is initialized."""
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    os.makedirs(DATABASE_DIR, exist_ok=True)
    os.makedirs(LOGS_DIR, exist_ok=True)
    # Ensure comments file exists
    load_comments()

def save_comments(comment_list: list, filepath: str = None) -> bool:
    """
    Saves a list of comment strings into a JSON file with UTF-8 encoding and clean indentation.
    """
    target_path = filepath or COMMENTS_FILE_PATH
    try:
        clean_list = [str(c).strip() for c in comment_list if str(c).strip()]
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(clean_list, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False

def add_comment(new_comment: str, filepath: str = None) -> bool:
    """
    Appends a new comment string to the comments JSON storage if not already present.
    """
    comment_str = (new_comment or "").strip()
    if not comment_str:
        return False
    current = load_comments(filepath)
    if comment_str not in current:
        current.append(comment_str)
        return save_comments(current, filepath)
    return True

def load_comments(filepath: str = None) -> list:
    """
    Loads comments from a structured JSON file (or legacy text file fallback).
    If the file doesn't exist, it initializes it from comments.example.json template,
    or converts legacy comments.txt if available.
    """
    target_path = filepath or COMMENTS_FILE_PATH
    
    # Also check fallback in storage directory if root not found
    if not os.path.exists(target_path):
        alt_path = os.path.join(STORAGE_DIR, os.path.basename(target_path))
        if os.path.exists(alt_path):
            target_path = alt_path

    # Initialize from template or legacy files if not present
    if not os.path.exists(target_path):
        try:
            # Check if template JSON exists
            if os.path.exists(COMMENTS_TEMPLATE_PATH):
                shutil.copy(COMMENTS_TEMPLATE_PATH, target_path)
            elif os.path.exists("comments.example.json"):
                shutil.copy("comments.example.json", target_path)
            # Or convert from legacy comments.txt if it has content
            elif os.path.exists("comments.txt"):
                legacy_items = []
                with open("comments.txt", "r", encoding="utf-8") as lf:
                    for l in lf:
                        c = l.strip()
                        if c and not c.startswith("#"):
                            legacy_items.append(c)
                if legacy_items:
                    save_comments(legacy_items, target_path)
                else:
                    save_comments([
                        "Great post! 🔥",
                        "Love this! ❤️",
                        "Awesome content! 👏",
                        "Super inspiring! 😍",
                        "Keep up the great work! ✨"
                    ], target_path)
            else:
                save_comments([
                    "Great post! 🔥",
                    "Love this! ❤️",
                    "Awesome content! 👏",
                    "Super inspiring! 😍",
                    "Keep up the great work! ✨"
                ], target_path)
        except Exception:
            return []

    try:
        with open(target_path, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return []

        # Try parsing as JSON first
        try:
            data = json.loads(content)
            if isinstance(data, list):
                return [str(item).strip() for item in data if str(item).strip()]
            elif isinstance(data, dict):
                # If wrapped in an object e.g. {"comments": [...]}
                if "comments" in data and isinstance(data["comments"], list):
                    return [str(item).strip() for item in data["comments"] if str(item).strip()]
                return [str(v).strip() for v in data.values() if isinstance(v, str) and v.strip()]
        except json.JSONDecodeError:
            # Fallback to line-by-line text parsing if user has a plain text file
            loaded = []
            for line in content.splitlines():
                cleaned = line.strip()
                if cleaned and not cleaned.startswith("#"):
                    loaded.append(cleaned)
            return loaded
    except Exception:
        return []

# Load initial comments list
comments = load_comments()
