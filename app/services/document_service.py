import os, time, uuid
from werkzeug.utils import secure_filename
from flask import current_app
from ..db import get_db

def _allowed_ext(filename: str) -> bool:
    _, ext = os.path.splitext(filename.lower())
    return ext in current_app.config["ALLOWED_EXTENSIONS"]

def save_uploaded_documents(files, verification_request_id: int, uploaded_by_user_id: int, document_type: str):
    # files: list[FileStorage]
    saved = []
    for f in files:
        if f is None or f.filename is None or f.filename.strip() == "":
            continue

        orig = f.filename
        if not _allowed_ext(orig):
            raise ValueError("Invalid file extension. Only .pdf and .docx are allowed.")

        # size limit
        f.stream.seek(0, os.SEEK_END)
        size = f.stream.tell()
        f.stream.seek(0)
        if size > int(current_app.config["MAX_FILE_SIZE_BYTES"]):
            raise ValueError("File too large.")

        ext = os.path.splitext(orig.lower())[1]
        token = uuid.uuid4().hex
        stored = secure_filename(f"{token}{ext}")
        dest = os.path.join(current_app.config["UPLOAD_FOLDER"], stored)
        f.save(dest)

        db = get_db()
        now = int(time.time())
        db.execute(
            """INSERT INTO uploaded_documents
            (verification_request_id, uploaded_by_user_id, document_type, original_filename, stored_filename, file_extension, file_size, uploaded_at)
            VALUES (?,?,?,?,?,?,?,?)""",
            (int(verification_request_id), int(uploaded_by_user_id), document_type, orig, stored, ext.lstrip("."), int(size), now),
        )
        db.commit()
        saved.append(stored)
    if not saved:
        raise ValueError("No valid documents uploaded.")
    return saved

def list_documents(verification_request_id: int):
    db = get_db()
    return db.execute(
        "SELECT * FROM uploaded_documents WHERE verification_request_id = ? ORDER BY uploaded_at DESC",
        (int(verification_request_id),),
    ).fetchall()


def get_document_by_id(doc_id: int):
    db = get_db()
    return db.execute("SELECT * FROM uploaded_documents WHERE id = ?", (int(doc_id),)).fetchone()

import os
from flask import current_app, send_file, abort
from ..db import get_db

def list_my_verification_docs(user_id: int):
    db = get_db()
    return db.execute(
        """
        SELECT d.id, d.original_filename, d.stored_filename, d.file_extension, d.uploaded_at
        FROM uploaded_documents d
        JOIN verification_requests vr ON vr.id = d.verification_request_id
        WHERE vr.user_id = ?
        ORDER BY d.uploaded_at DESC
        """,
        (user_id,)
    ).fetchall()

def download_my_verification_doc(user_id: int, doc_id: int):
    db = get_db()
    row = db.execute(
        """
        SELECT d.original_filename, d.stored_filename
        FROM uploaded_documents d
        JOIN verification_requests vr ON vr.id = d.verification_request_id
        WHERE d.id = ? AND vr.user_id = ?
        """,
        (doc_id, user_id)
    ).fetchone()
    if not row:
        abort(404)
    # Keep downloads consistent with where we save uploads.
    upload_dir = current_app.config.get("UPLOAD_FOLDER") or os.path.join(current_app.instance_path, "uploads")
    path = os.path.join(upload_dir, row["stored_filename"])
    if not os.path.exists(path):
        abort(404)
    return send_file(path, as_attachment=True, download_name=row["original_filename"])

def list_my_skill_docs(user_id: int):
    db = get_db()
    return db.execute(
        """
        SELECT d.id, d.original_filename, d.stored_filename, d.uploaded_at, s.skill_name
        FROM technician_skill_documents d
        JOIN technician_skill_items s ON s.id = d.skill_item_id
        WHERE s.user_id = ?
        ORDER BY d.uploaded_at DESC
        """,
        (user_id,)
    ).fetchall()

def download_my_skill_doc(user_id: int, doc_id: int):
    db = get_db()
    row = db.execute(
        """
        SELECT d.original_filename, d.stored_filename
        FROM technician_skill_documents d
        JOIN technician_skill_items s ON s.id = d.skill_item_id
        WHERE d.id = ? AND s.user_id = ?
        """,
        (doc_id, user_id)
    ).fetchone()
    if not row:
        abort(404)
    upload_dir = current_app.config.get("UPLOAD_FOLDER") or os.path.join(current_app.instance_path, "uploads")
    path = os.path.join(upload_dir, row["stored_filename"])
    if not os.path.exists(path):
        abort(404)
    return send_file(path, as_attachment=True, download_name=row["original_filename"])
