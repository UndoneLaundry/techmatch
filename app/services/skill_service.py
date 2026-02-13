"""Skill submission + admin review service.

This module backs:
 - Technician skill submissions (PENDING)
 - Admin approval/rejection
 - Skill-to-certificate document linkage

It intentionally contains no Flask request/session logic.
"""

from __future__ import annotations

import os
import time
import uuid
from typing import Iterable

from werkzeug.utils import secure_filename
from flask import current_app

from ..db import get_db


PENDING_LIMIT = 3


def _allowed_ext(filename: str) -> bool:
    _, ext = os.path.splitext(filename.lower())
    return ext in current_app.config["ALLOWED_EXTENSIONS"]


def _file_size_bytes(f) -> int:
    f.stream.seek(0, os.SEEK_END)
    size = f.stream.tell()
    f.stream.seek(0)
    return int(size)


# =========================
# Technician actions
# =========================

def list_my_skill_items(user_id: int):
    db = get_db()
    return db.execute(
        """
        SELECT id, skill_name, skill_description, status, created_at, reviewed_at, rejection_reason
        FROM technician_skill_items
        WHERE user_id = ?
        ORDER BY created_at DESC
        """,
        (int(user_id),),
    ).fetchall()


def list_my_skills(user_id: int):
    """Backwards-compatible alias used by some routes."""
    return list_my_skill_items(user_id)


def create_skill_request(user_id: int, skill_name: str, description: str | None = None) -> int:
    skill_name = (skill_name or "").strip()
    if not skill_name:
        raise ValueError("Skill name is required.")

    from app.services.skill_suggest_service import CANONICAL_SKILLS
    if skill_name not in CANONICAL_SKILLS:
        raise ValueError("Please choose a skill from the suggested canonical list.")

    # Enforce max 3 pending at a time.
    db = get_db()
    pending_count = db.execute(
        """SELECT COUNT(1) AS c
           FROM technician_skill_items
           WHERE user_id = ? AND status = 'PENDING'""",
        (int(user_id),),
    ).fetchone()["c"]
    if int(pending_count) >= PENDING_LIMIT:
        raise ValueError("You can only have up to 3 pending skills at a time.")

    now = int(time.time())
    db.execute(
        """
        INSERT INTO technician_skill_items (user_id, skill_name, skill_description, status, created_at)
        VALUES (?, ?, ?, 'PENDING', ?)
        """,
        (int(user_id), skill_name, description, now),
    )
    db.commit()
    skill_id = db.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
    return int(skill_id)


def attach_skill_documents(skill_item_id: int, files: Iterable, upload_dir: str | None = None) -> None:
    """Attach one-or-more certificate files to a skill.

    files is an iterable of Werkzeug FileStorage objects.
    """
    upload_dir = upload_dir or current_app.config["UPLOAD_FOLDER"]
    os.makedirs(upload_dir, exist_ok=True)

    db = get_db()
    saved_any = False
    now = int(time.time())

    for f in files:
        if f is None or not getattr(f, "filename", None) or f.filename.strip() == "":
            continue

        orig = f.filename
        if not _allowed_ext(orig):
            raise ValueError("Invalid file extension. Only .pdf and .docx are allowed.")

        size = _file_size_bytes(f)
        if size > int(current_app.config["MAX_FILE_SIZE_BYTES"]):
            raise ValueError("File too large.")

        ext = os.path.splitext(orig.lower())[1]
        token = uuid.uuid4().hex
        stored = secure_filename(f"{token}{ext}")
        dest = os.path.join(upload_dir, stored)
        f.save(dest)

        db.execute(
            """
            INSERT INTO technician_skill_documents
              (skill_item_id, original_filename, stored_filename, file_extension, file_size, uploaded_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (int(skill_item_id), orig, stored, ext.lstrip("."), int(size), now),
        )
        saved_any = True

    if not saved_any:
        raise ValueError("No valid documents uploaded.")

    db.commit()


# =========================
# Admin queries
# =========================

def list_pending_skill_requests():
    db = get_db()
    return db.execute(
        """
        SELECT s.id, s.user_id, u.email, s.skill_name, s.skill_description, s.created_at
        FROM technician_skill_items s
        JOIN users u ON u.id = s.user_id
        WHERE s.status = 'PENDING'
        ORDER BY s.created_at ASC
        """
    ).fetchall()


def get_skill_request(skill_id: int):
    db = get_db()
    return db.execute(
        """SELECT * FROM technician_skill_items WHERE id = ?""",
        (int(skill_id),),
    ).fetchone()


def list_skill_documents(skill_id: int):
    db = get_db()
    return db.execute(
        """SELECT * FROM technician_skill_documents WHERE skill_item_id = ? ORDER BY uploaded_at DESC""",
        (int(skill_id),),
    ).fetchall()


def get_skill_document_by_id(doc_id: int):
    db = get_db()
    return db.execute(
        """SELECT * FROM technician_skill_documents WHERE id = ?""",
        (int(doc_id),),
    ).fetchone()


def approve_skill_request(skill_id: int, admin_id: int) -> None:
    db = get_db()
    now = int(time.time())
    db.execute(
        """
        UPDATE technician_skill_items
        SET status='APPROVED', reviewed_at=?, reviewed_by_admin_id=?, rejection_reason=NULL
        WHERE id=? AND status='PENDING'
        """,
        (now, int(admin_id), int(skill_id)),
    )
    db.commit()


def reject_skill_request(skill_id: int, admin_id: int, reason: str) -> None:
    reason = (reason or "").strip() or "Rejected"
    db = get_db()
    now = int(time.time())
    db.execute(
        """
        UPDATE technician_skill_items
        SET status='REJECTED', rejection_reason=?, reviewed_at=?, reviewed_by_admin_id=?
        WHERE id=? AND status='PENDING'
        """,
        (reason, now, int(admin_id), int(skill_id)),
    )
    db.commit()


# =========================
# Backwards-compatible names
# =========================

def create_skill(user_id: int, skill_name: str, description: str | None = None) -> int:
    return create_skill_request(user_id, skill_name, description)


def attach_documents_to_skill(skill_id: int, documents: list[dict]):
    """Legacy helper (not used by current UI).

    Accepts pre-saved dicts and inserts them. Kept to avoid breaking older code.
    """
    if not documents:
        return
    db = get_db()
    now = int(time.time())
    for doc in documents:
        db.execute(
            """
            INSERT INTO technician_skill_documents
              (skill_item_id, original_filename, stored_filename, file_extension, file_size, uploaded_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                int(skill_id),
                doc["original_filename"],
                doc["stored_filename"],
                doc["file_extension"],
                int(doc["file_size"]),
                now,
            ),
        )
    db.commit()


def list_skills_for_user(user_id: int):
    return list_my_skill_items(user_id)
