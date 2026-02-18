from __future__ import annotations

from flask import Blueprint, session, redirect, url_for, render_template

from ..auth.decorators import login_required
from ..services.notification_service import list_notifications, mark_all_read
from ..db import get_db


bp = Blueprint("notifications", __name__)


def _extract_skill_name(message: str) -> str | None:
    """Extract skill name from existing notification messages.

    Current messages follow one of these patterns:
      - "✅ Skill approved: <SKILL>"
      - "❌ Skill rejected: <SKILL>. Reason: ..."

    We cannot change stored data, so we parse what already exists.
    """
    if not message:
        return None

    if ":" not in message:
        return None

    # Keep the parsing conservative and tailored to existing messages.
    try:
        tail = message.split(":", 1)[1].strip()
        if not tail:
            return None
        # Remove optional reason clause.
        if ". Reason:" in tail:
            tail = tail.split(". Reason:", 1)[0].strip()
        return tail or None
    except Exception:
        return None


def _find_skill_item_id_for_user(user_id: int, skill_name: str) -> int | None:
    db = get_db()
    row = db.execute(
        """
        SELECT id
        FROM technician_skill_items
        WHERE user_id = ? AND skill_name = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (int(user_id), skill_name),
    ).fetchone()
    return int(row["id"]) if row else None


@bp.get("/notifications")
@login_required
def notifications_list():
    """Render notifications page."""
    user_id = session["user_id"]
    notes = list_notifications(user_id, unread_only=False)
    return render_template("notifications.html", notifications=notes)


@bp.get("/notifications/go/<int:notification_id>")
@login_required
def notification_go(notification_id: int):
    """Resolve a notification into an appropriate destination page."""
    user_id = session["user_id"]
    role = session.get("role")

    db = get_db()
    n = db.execute(
        "SELECT * FROM notifications WHERE id = ? AND user_id = ?",
        (int(notification_id), int(user_id)),
    ).fetchone()

    if n is None:
        # Invalid or not-owned notification. Never leak anything.
        return redirect(url_for("notifications.notifications_list"))

    n_type = (n["type"] or "").strip().upper()
    message = n["message"] or ""

    # Skill-related notifications.
    if n_type in {"SKILL_APPROVED", "SKILL_REJECTED"}:
        skill_name = _extract_skill_name(message)
        if skill_name:
            skill_id = _find_skill_item_id_for_user(user_id, skill_name)
            if skill_id is not None:
                if role == "ADMIN":
                    return redirect(url_for("admin.skills_review", skill_id=skill_id))
                # Technician can view their own skill detail + status.
                return redirect(url_for("technician.skill_detail", skill_id=skill_id))
        # Fallback: go somewhere intentional (no dead end).
        if role == "ADMIN":
            return redirect(url_for("admin.skills_pending"))
        return redirect(url_for("user.profile_get"))

    # Verification notifications.
    if n_type == "VERIFICATION_APPROVED":
        return redirect(url_for("user.homepage"))
    if n_type == "VERIFICATION_REJECTED":
        return redirect(url_for("user.pending"))

    # Default fallback.
    return redirect(url_for("notifications.notifications_list"))


@bp.post("/notifications/mark-read")
@login_required
def notifications_mark_read():
    user_id = session["user_id"]
    mark_all_read(user_id)
    return redirect(url_for("user.homepage"))
