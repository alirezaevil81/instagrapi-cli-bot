"""
Database Engine & Connection Manager.
Handles SQLite connection pooling, migrations, and schema initialization.
"""
import os
import sqlite3
from src.config import DB_PATH, DATABASE_DIR

def get_db_connection() -> sqlite3.Connection:
    """Creates and returns a thread-safe SQLite connection to storage/database/bot.db."""
    os.makedirs(DATABASE_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=20)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes SQLite tables for queues and interaction histories."""
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
        conn.commit()
