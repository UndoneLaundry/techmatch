import sqlite3
from flask import current_app
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime


# =====================================================
# CREATE USER
# =====================================================

def create_user(email: str, password: str, role: str):
    email = email.strip().lower()
    password_hash = generate_password_hash(password)
    created_at = int(datetime.utcnow().timestamp())

    db_path = current_app.config["DATABASE"]
    print("CREATE_USER DB PATH:", db_path)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO users (email, password_hash, role, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (email, password_hash, role, created_at),
    )

    conn.commit()

    user_id = cur.lastrowid
    cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()

    if row is None:
        raise RuntimeError("User creation failed")

    return dict(row)


# =====================================================
# GET USER BY EMAIL
# =====================================================

def get_user_by_email(email: str):
    email = email.strip().lower()
    db_path = current_app.config["DATABASE"]
    print("GET_USER DB PATH:", db_path)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT * FROM users WHERE email = ?", (email,))
    row = cur.fetchone()
    conn.close()

    return dict(row) if row else None


# =====================================================
# GET USER BY ID
# =====================================================

def get_user_by_id(user_id: int):
    db_path = current_app.config["DATABASE"]

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()

    return dict(row) if row else None


# =====================================================
# UPDATE LAST LOGIN
# =====================================================

def update_last_login(user_id: int):
    db_path = current_app.config["DATABASE"]
    now = int(datetime.utcnow().timestamp())
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("UPDATE users SET last_login_at = ? WHERE id = ?", (now, int(user_id)))
    conn.commit()
    conn.close()




# =====================================================
# CHANGE EMAIL (USERNAME)
# =====================================================

def change_email(user_id: int, password: str, new_email: str) -> tuple[bool, str]:
    """Change login email (username) with password verification."""
    new_email = (new_email or "").strip().lower()
    if not new_email:
        return False, "Email is required."
    user = get_user_by_id(int(user_id))
    if not user:
        return False, "User not found."
    if not verify_password(user, password):
        return False, "Password is incorrect."

    # enforce unique
    existing = get_user_by_email(new_email)
    if existing and int(existing["id"]) != int(user_id):
        return False, "That email is already in use."

    db_path = current_app.config["DATABASE"]
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("UPDATE users SET email = ? WHERE id = ?", (new_email, int(user_id)))
    conn.commit()
    conn.close()
    return True, "Email updated."

# =====================================================
# CHANGE PASSWORD
# =====================================================

def change_password(user_id: int, old_password: str, new_password: str) -> tuple[bool, str]:
    """Change password with old-password verification.

    Returns (ok, message).
    """
    user = get_user_by_id(int(user_id))
    if not user:
        return False, "User not found."
    if not verify_password(user, old_password):
        return False, "Current password is incorrect."

    db_path = current_app.config["DATABASE"]
    new_hash = generate_password_hash(new_password)
    now = int(datetime.utcnow().timestamp())
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET password_hash = ?, force_password_change = 0, password_changed_at = ? WHERE id = ?",
        (new_hash, now, int(user_id)),
    )
    conn.commit()
    conn.close()
    return True, "Password updated."


def set_force_password_change(user_id: int, required: bool = True):
    db_path = current_app.config["DATABASE"]
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET force_password_change = ? WHERE id = ?",
        (1 if required else 0, int(user_id)),
    )
    conn.commit()
    conn.close()


# =====================================================
# VERIFY PASSWORD
# =====================================================

def verify_password(user_row, password: str) -> bool:
    if not user_row:
        return False
    return check_password_hash(user_row["password_hash"], password)