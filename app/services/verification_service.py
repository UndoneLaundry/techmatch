import time
from ..db import get_db

def get_latest_request_for_user(user_id: int):
    db = get_db()
    return db.execute(
        "SELECT * FROM verification_requests WHERE user_id = ? ORDER BY submitted_at DESC, id DESC LIMIT 1",
        (int(user_id),),
    ).fetchone()

def is_cooldown_active_for_request(req_row) -> bool:
    if req_row is None:
        return False
    if req_row["status"] != "REJECTED":
        return False
    cooldown_until = req_row["cooldown_until"]
    if cooldown_until is None:
        return False
    return int(time.time()) < int(cooldown_until)

def create_verification_request(user_id: int, user_role: str):
    """Create a new PENDING verification request.

    Enforces the one-active-request rule and cooldown rule server-side.

    Active request =:
      - PENDING
      - REJECTED with now < cooldown_until
    """
    db = get_db()

    latest = get_latest_request_for_user(int(user_id))
    if latest is not None:
        if latest["status"] == "PENDING":
            raise ValueError("You already have a pending verification request.")
        if latest["status"] == "REJECTED" and is_cooldown_active_for_request(latest):
            raise ValueError("You are on cooldown after a rejection. Please wait before resubmitting.")

    now = int(time.time())
    cur = db.execute(
        "INSERT INTO verification_requests (user_id, user_role, status, submitted_at) VALUES (?,?,?,?)",
        (int(user_id), user_role, "PENDING", now),
    )
    db.commit()
    return cur.lastrowid

def attach_flag(verification_request_id: int, flag_type: str, severity: str, description: str):
    db = get_db()
    now = int(time.time())
    db.execute(
        "INSERT INTO verification_flags (verification_request_id, flag_type, severity, description, created_at) VALUES (?,?,?,?,?)",
        (int(verification_request_id), flag_type, severity, description, now),
    )
    db.commit()

def list_flags(verification_request_id: int):
    db = get_db()
    return db.execute(
        "SELECT * FROM verification_flags WHERE verification_request_id = ? ORDER BY created_at DESC",
        (int(verification_request_id),),
    ).fetchall()

def approve_request(request_id: int, admin_id: int):
    db = get_db()
    now = int(time.time())
    # Transaction-safe approval
    with db:
        cur = db.execute(
            "UPDATE verification_requests SET status='APPROVED', reviewed_at=?, reviewed_by_admin_id=? WHERE id=? AND status='PENDING'",
            (now, int(admin_id), int(request_id)),
        )
        if cur.rowcount != 1:
            raise ValueError("Invalid request state for approval")

        # Mark user verified for fast gating & UI consistency
        db.execute(
            "UPDATE users SET is_verified = 1 WHERE id = (SELECT user_id FROM verification_requests WHERE id = ?)",
            (int(request_id),),
        )

        db.execute(
            "INSERT INTO admin_actions (admin_user_id, action_type, target_verification_request_id, timestamp) VALUES (?,?,?,?)",
            (int(admin_id), "APPROVE_VERIFICATION", int(request_id), now),
        )

def reject_request(request_id: int, admin_id: int, reason: str, cooldown_seconds: int):
    db = get_db()
    now = int(time.time())
    cooldown_until = now + int(cooldown_seconds)
    # Transaction-safe rejection
    with db:
        cur = db.execute(
            "UPDATE verification_requests SET status='REJECTED', reviewed_at=?, reviewed_by_admin_id=?, rejection_reason=?, rejected_at=?, cooldown_until=? WHERE id=? AND status='PENDING'",
            (now, int(admin_id), reason, now, cooldown_until, int(request_id)),
        )
        if cur.rowcount != 1:
            raise ValueError("Invalid request state for rejection")

        # Ensure user remains unverified
        db.execute(
            "UPDATE users SET is_verified = 0 WHERE id = (SELECT user_id FROM verification_requests WHERE id = ?)",
            (int(request_id),),
        )

        db.execute(
            "INSERT INTO admin_actions (admin_user_id, action_type, target_verification_request_id, timestamp, notes) VALUES (?,?,?,?,?)",
            (int(admin_id), "REJECT_VERIFICATION", int(request_id), now, reason),
        )

def get_request_by_id(request_id: int):
    db = get_db()
    return db.execute("SELECT * FROM verification_requests WHERE id = ?", (int(request_id),)).fetchone()

def list_pending_requests():
    db = get_db()
    return db.execute(
        "SELECT vr.*, u.email FROM verification_requests vr JOIN users u ON u.id = vr.user_id WHERE vr.status='PENDING' ORDER BY vr.submitted_at ASC"
    ).fetchall()


def list_requests_by_status(status: str):
    """List verification requests by status.

    UI helper only (does not change routing or state transitions).
    """
    db = get_db()
    return db.execute(
        """
        SELECT vr.*, u.email
        FROM verification_requests vr
        JOIN users u ON u.id = vr.user_id
        WHERE vr.status = ?
        ORDER BY COALESCE(vr.reviewed_at, vr.submitted_at) DESC, vr.id DESC
        """,
        (status,),
    ).fetchall()


def count_requests_by_status(status: str) -> int:
    db = get_db()
    row = db.execute(
        "SELECT COUNT(1) AS c FROM verification_requests WHERE status = ?",
        (status,),
    ).fetchone()
    return int(row["c"]) if row else 0
