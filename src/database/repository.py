"""
Database Repository: CRUD operations for target users queue and audit records.
"""
from typing import List, Any
from src.database.engine import get_db_connection, init_db

class SimpleUserObject:
    """User representation with instagrapi user attributes (pk, username, full_name, is_private)."""
    def __init__(self, pk: str, username: str, full_name: str = "", is_private: bool = False):
        self.pk = str(pk)
        self.username = str(username)
        self.full_name = str(full_name)
        self.is_private = bool(is_private)

    def __repr__(self):
        return f"<User @{self.username} (PK: {self.pk})>"

def save_target_users_queue(users: List[Any], clear_existing: bool = True) -> int:
    """
    Saves a list of target users into the SQLite database.
    """
    init_db()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if clear_existing:
            cursor.execute("DELETE FROM target_users_queue WHERE status = 'pending'")

        count = 0
        for u in users:
            pk = str(getattr(u, 'pk', u))
            username = str(getattr(u, 'username', u))
            full_name = str(getattr(u, 'full_name', ''))
            is_private = 1 if getattr(u, 'is_private', False) else 0

            cursor.execute("""
                INSERT OR REPLACE INTO target_users_queue (pk, username, full_name, is_private, status, added_at)
                VALUES (?, ?, ?, ?, 'pending', CURRENT_TIMESTAMP)
            """, (pk, username, full_name, is_private))
            count += 1

        conn.commit()
        return count

def get_pending_target_users() -> List[SimpleUserObject]:
    """
    Retrieves all pending users from the target queue.
    """
    init_db()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT pk, username, full_name, is_private FROM target_users_queue WHERE status = 'pending' ORDER BY added_at ASC")
        rows = cursor.fetchall()
        return [
            SimpleUserObject(
                pk=row['pk'],
                username=row['username'],
                full_name=row['full_name'],
                is_private=bool(row['is_private'])
            ) for row in rows
        ]

def remove_user_from_queue(pk: str) -> bool:
    """
    Removes a user from the active queue.
    """
    init_db()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM target_users_queue WHERE pk = ?", (str(pk),))
        conn.commit()
        return cursor.rowcount > 0

def clear_target_queue() -> None:
    """Clears all records in target_users_queue."""
    init_db()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM target_users_queue")
        conn.commit()

def get_queue_count() -> int:
    """Returns number of pending target users."""
    init_db()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM target_users_queue WHERE status = 'pending'")
        row = cursor.fetchone()
        return row[0] if row else 0

def record_interaction(
    account_username: str,
    action_type: str,
    target_user_pk: str = "",
    target_username: str = "",
    media_pk: str = "",
    comment_text: str = "",
    success: bool = True
) -> None:
    """
    Records an action (like, comment, seen, follow) into SQLite audit table.
    """
    init_db()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO interaction_history (
                account_username, target_user_pk, target_username, media_pk, action_type, comment_text, success, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            str(account_username),
            str(target_user_pk),
            str(target_username),
            str(media_pk),
            str(action_type),
            str(comment_text),
            1 if success else 0
        ))
        conn.commit()

def has_recent_interaction(media_pk: str, action_type: str) -> bool:
    """Checks if a post was already interacted with in SQLite history."""
    init_db()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id FROM interaction_history 
            WHERE media_pk = ? AND action_type = ? AND success = 1
            LIMIT 1
        """, (str(media_pk), str(action_type)))
        return cursor.fetchone() is not None
