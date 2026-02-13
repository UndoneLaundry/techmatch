import time
from ..db import get_db

def create_notification(user_id: int, type_: str, message: str):
    db = get_db()
    now = int(time.time())
    db.execute(
        "INSERT INTO notifications (user_id, type, message, is_read, created_at) VALUES (?,?,?,?,?)",
        (int(user_id), type_, message, 0, now),
    )
    db.commit()

def list_notifications(user_id: int, unread_only: bool = False):
    db = get_db()
    if unread_only:
        return db.execute(
            "SELECT * FROM notifications WHERE user_id = ? AND is_read = 0 ORDER BY created_at DESC",
            (int(user_id),),
        ).fetchall()
    return db.execute(
        "SELECT * FROM notifications WHERE user_id = ? ORDER BY created_at DESC",
        (int(user_id),),
    ).fetchall()

def mark_all_read(user_id: int):
    db = get_db()
    now = int(time.time())
    db.execute(
        "UPDATE notifications SET is_read = 1, read_at = ? WHERE user_id = ? AND is_read = 0",
        (now, int(user_id)),
    )
    db.commit()
