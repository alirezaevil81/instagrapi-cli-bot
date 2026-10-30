"""
Database Engine & Connection Manager.
Handles SQLite connection pooling, migrations, and schema initialization.
"""
import os
import sqlite3
from src.config import DB_PATH, DATABASE_DIR

_DB_INITIALIZED = False

def get_db_connection() -> sqlite3.Connection:
    """Creates and returns a thread-safe SQLite connection to storage/database/bot.db with WAL mode."""
    os.makedirs(DATABASE_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA busy_timeout=30000;")
    except Exception:
        pass
    return conn

def init_db(force: bool = False):
    """Initializes SQLite tables and indexes once for queues and interaction histories."""
    global _DB_INITIALIZED
    if _DB_INITIALIZED and not force:
        return

    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Table for target users queue
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS target_users_queue (
                pk TEXT PRIMARY KEY,
                username TEXT NOT NULL,
                full_name TEXT DEFAULT '',
                is_private INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending',
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Table for target comments queue
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS target_comments_queue (
                pk TEXT PRIMARY KEY,
                media_pk TEXT NOT NULL,
                author_username TEXT NOT NULL,
                author_pk TEXT DEFAULT '',
                text TEXT DEFAULT '',
                like_count INTEGER DEFAULT 0,
                is_private INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending',
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Migration: ensure like_count & is_private columns exist in existing databases
        cursor.execute("PRAGMA table_info(target_comments_queue)")
        existing_cols = [c[1] for c in cursor.fetchall()]
        if "like_count" not in existing_cols:
            try:
                cursor.execute("ALTER TABLE target_comments_queue ADD COLUMN like_count INTEGER DEFAULT 0")
            except Exception:
                pass
        if "is_private" not in existing_cols:
            try:
                cursor.execute("ALTER TABLE target_comments_queue ADD COLUMN is_private INTEGER DEFAULT 0")
            except Exception:
                pass

        # Table for interaction history and audit logging
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS interaction_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_username TEXT,
                target_user_pk TEXT,
                target_username TEXT,
                media_pk TEXT,
                action_type TEXT NOT NULL,
                comment_text TEXT DEFAULT '',
                success INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Performance indexes for instant O(1) deduplication lookups
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_interaction_media_action 
            ON interaction_history (media_pk, action_type, success)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_interaction_user_action 
            ON interaction_history (target_user_pk, action_type, success)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_target_users_status 
            ON target_users_queue (status)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_target_comments_status 
            ON target_comments_queue (status)
        """)
        conn.commit()

    _DB_INITIALIZED = True
