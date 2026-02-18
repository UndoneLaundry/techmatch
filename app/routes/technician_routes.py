import os
import sqlite3
from datetime import datetime
from pathlib import Path

from flask import (
    Blueprint,
    render_template,
    session,
    request,
    redirect,
    url_for,
    flash,
    current_app,
    jsonify,
)

from ..auth.decorators import login_required, role_required, verification_required
from ..services.notification_service import list_notifications
from ..services.profile_service import get_technician_profile
from ..services.jobs_enum import JobStatus

bp = Blueprint("technician", __name__, url_prefix="/technician")


# ======================================================
# DB helpers (keep DB schema untouched)
# ======================================================

def _db_path() -> str:
    db = current_app.config.get("DATABASE")
    if db:
        return str(db)
    return str(Path(current_app.instance_path) / "app.db")


def _conn():
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def list_available_jobs_for_search():
    """List jobs that are available for technicians to browse/apply.

    IMPORTANT: Uses existing schema only; no extra fields.
    """
    conn = _conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT *
        FROM jobs
        WHERE status = ?
        ORDER BY created_at DESC
        """,
        (JobStatus.OUTGOING.value,),
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


# ======================================================
# Technician homepage (kept from main project)
# ======================================================


@bp.get("/homepage")
@login_required
@role_required("TECHNICIAN")
@verification_required
def homepage_page():
    """Technician homepage (role-split)."""
    user_id = session["user_id"]
    notes = list_notifications(user_id, unread_only=True)
    return render_template("technician/homepage.html", unread_notifications=notes)


# ======================================================
# Technician dashboard (REPLACED with CLEAN dashboard logic)
# Route path remains: /technician/dashboard
# ======================================================


@bp.get("/dashboard")
@login_required
@verification_required
@role_required("TECHNICIAN")
def dashboard_page():
    """Technician dashboard (Active / Completed / Recommended jobs)."""
    user_id = session["user_id"]

    tech = get_technician_profile(user_id)
    notifications = list_notifications(user_id, unread_only=True)

    active_jobs = list_active_jobs_for_technician(user_id)
    completed_jobs = list_completed_jobs_for_technician(user_id)
    recommended_jobs = list_recommended_jobs_for_technician(user_id)

    return render_template(
        "technician/dashboard.html",
        tech=tech,
        unread_notifications=notifications,
        active_jobs=active_jobs,
        completed_jobs=completed_jobs,
        recommended_jobs=recommended_jobs,
    )


# Alias endpoint expected by CLEAN templates: url_for('technician.dashboard')
# Keep existing endpoint: technician.dashboard_page (used by base.html / legacy)
# This adds a second endpoint name without changing routing.
# NOTE: This must be defined after dashboard_page.

bp.add_url_rule(
    "/dashboard",
    endpoint="dashboard",
    view_func=dashboard_page,
    methods=["GET"],
)


# ======================================================
# Search (from CLEAN zip) - /technician/search
# ======================================================


@bp.get("/search")
@login_required
@verification_required
@role_required("TECHNICIAN")
def search_page():
    tech = get_technician_profile(session["user_id"])
    jobs = list_available_jobs_for_search()

    conn = _conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT job_id
        FROM job_applications
        WHERE technician_id = ?
        """,
        (session["user_id"],),
    )
    applied_job_ids = {row["job_id"] for row in cur.fetchall()}
    conn.close()

    return render_template(
        "technician/search.html",
        tech=tech,
        jobs=jobs,
        applied_job_ids=applied_job_ids,
    )


# ======================================================
# Profile (keep route path /technician/profile)
# Provide alias endpoint technician.profile for CLEAN templates.
# ======================================================


@bp.get("/profile", endpoint="profile")
@login_required
@role_required("TECHNICIAN")
def view_profile():
    profile = get_technician_profile(session["user_id"])
    return render_template("technician/profile_view.html", tech=profile, profile=profile)


@bp.get("/profile/preview")
@login_required
@role_required("TECHNICIAN")
def profile_preview():
    from app.services.skill_service import list_my_skills
    from app.services.document_service import (
        list_my_verification_docs,
        list_my_skill_docs,
    )

    profile = get_technician_profile(session["user_id"])
    skills = list_my_skills(session["user_id"])
    ver_docs = list_my_verification_docs(session["user_id"])
    skill_docs = list_my_skill_docs(session["user_id"])
    return render_template(
        "technician/profile_preview.html",
        profile=profile,
        skills=skills,
        ver_docs=ver_docs,
        skill_docs=skill_docs,
    )


@bp.get("/certs/<int:doc_id>/download")
@login_required
@role_required("TECHNICIAN")
def download_own_cert(doc_id):
    from app.services.document_service import download_my_verification_doc

    return download_my_verification_doc(session["user_id"], doc_id)


@bp.get("/skill-certs/<int:doc_id>/download")
@login_required
@role_required("TECHNICIAN")
def download_own_skill_cert(doc_id):
    from app.services.document_service import download_my_skill_doc

    return download_my_skill_doc(session["user_id"], doc_id)


# ======================================================
# Apply to job (Sign up) - used by dashboard/search modals
# ======================================================


@bp.post("/jobs/<int:job_id>/apply")
@login_required
@verification_required
@role_required("TECHNICIAN")
def apply_to_job(job_id):
    technician_id = session["user_id"]
    conn = _conn()
    cur = conn.cursor()
    try:
        # 1. Verify job exists and is still OUTGOING
        cur.execute("SELECT status FROM jobs WHERE id = ?", (job_id,))
        job = cur.fetchone()
        if not job:
            return jsonify({"error": "Job not found"}), 404
        if job["status"] != JobStatus.OUTGOING.value:
            return jsonify({"error": "Job is no longer accepting applications"}), 400

        # 2. Insert application
        created_at = datetime.utcnow().isoformat()
        cur.execute(
            """
            INSERT INTO job_applications (job_id, technician_id, status, applied_at)
            VALUES (?, ?, 'APPLIED', ?)
            """,
            (job_id, technician_id, created_at),
        )
        conn.commit()
        return jsonify({"success": True}), 201

    except sqlite3.IntegrityError as e:
        # Likely duplicate (if you have a unique constraint)
        return jsonify({"error": "You have already applied to this job"}), 409
    except Exception as e:
        # Catch any other error and return it
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


# ======================================================
# Mark job complete
# ======================================================


@bp.post("/jobs/<int:job_id>/complete")
@bp.post("/jobs/<int:job_id>/request-approval")  # alias for frontend
@login_required
@verification_required
@role_required("TECHNICIAN")
def mark_job_complete(job_id):
    """Mark an active job as complete (moves to PENDING_CONFIRMATION)."""
    technician_id = session["user_id"]
    conn = _conn()
    cur = conn.cursor()
    try:
        # Verify job exists, is ACTIVE, and assigned to this technician
        cur.execute(
            """
            SELECT id, status, assigned_technician_id
            FROM jobs
            WHERE id = ?
            """,
            (job_id,),
        )
        job = cur.fetchone()
        if not job:
            return jsonify({"error": "Job not found"}), 404

        if job["status"] != JobStatus.ACTIVE.value:
            return jsonify({"error": "Job is not active"}), 400

        if job["assigned_technician_id"] != technician_id:
            return jsonify({"error": "You are not assigned to this job"}), 403

        # Update job status
        cur.execute(
            """
            UPDATE jobs
            SET status = ?, updated_at = ?
            WHERE id = ? AND status = ?
            """,
            (
                JobStatus.PENDING_CONFIRMATION.value,
                datetime.utcnow().isoformat(),
                job_id,
                JobStatus.ACTIVE.value,
            ),
        )

        if cur.rowcount == 0:
            return jsonify({"error": "Failed to update job status"}), 500

        conn.commit()
        return jsonify({"success": True}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


# ======================================================
# Existing job window (kept from main project)
# ======================================================


@bp.get("/jobs/<int:job_id>")
@login_required
@role_required("TECHNICIAN")
@verification_required
def job_view(job_id: int):
    from app.services.job_window_service import get_job_window_for_technician

    user_id = session["user_id"]
    data = get_job_window_for_technician(job_id=job_id, technician_id=user_id)
    return render_template(
        "technician/job_view.html",
        job=data["job"],
        application=data["application"],
        show_tasks=data["show_tasks"],
        tasks=data["tasks"],
    )


# ======================================================
# Skills submission (kept from main project)
# ======================================================


@bp.post("/skills/add")
@login_required
@role_required("TECHNICIAN")
@verification_required
def add_skill():
    from app.services.skill_service import create_skill_request, attach_skill_documents

    skill_name = (request.form.get("skill_name") or "").strip()
    skill_description = (request.form.get("skill_description") or "").strip() or None

    files = request.files.getlist("certs")
    if not files or all((f is None or f.filename == "") for f in files):
        flash("Please upload at least one certificate file.", "error")
        return redirect(url_for("technician.homepage_page"))

    try:
        skill_item_id = create_skill_request(session["user_id"], skill_name, skill_description)
        upload_dir = current_app.config.get("UPLOAD_FOLDER") or (current_app.instance_path + "/uploads")
        os.makedirs(upload_dir, exist_ok=True)
        attach_skill_documents(skill_item_id, files, upload_dir)
        flash("Skill submitted for approval.", "success")
    except ValueError as e:
        flash(str(e), "error")
    except Exception:
        flash("Upload failed. Please try again.", "error")

    return redirect(url_for("technician.homepage_page"))


@bp.get("/skills/<int:skill_id>")
@login_required
@role_required("TECHNICIAN")
def skill_detail(skill_id: int):
    from ..db import get_db

    db = get_db()
    row = db.execute(
        """
        SELECT *
        FROM technician_skill_items
        WHERE id = ? AND user_id = ?
        """,
        (int(skill_id), int(session["user_id"])),
    ).fetchone()
    if row is None:
        flash("Skill not found.", "error")
        return redirect(url_for("user.profile_get"))

    from app.services.skill_service import list_skill_documents

    docs = list_skill_documents(int(skill_id))
    return render_template("technician/skill_detail.html", skill=row, docs=docs)


# ======================================================
# Queries for dashboard sections (CLEAN logic)
# ======================================================


def _attach_tasks(conn, jobs: list) -> list:
    """For each job dict in the list, fetch and attach its real tasks from job_tasks."""
    cur = conn.cursor()
    for job in jobs:
        cur.execute(
            "SELECT id, title, is_completed FROM job_tasks WHERE job_id = ? ORDER BY id ASC",
            (job["id"],),
        )
        job["tasks"] = [dict(t) for t in cur.fetchall()]
    return jobs


def list_active_jobs_for_technician(technician_id: int):
    conn = _conn()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT j.*
        FROM jobs j
        JOIN job_applications ja ON ja.job_id = j.id
        WHERE ja.technician_id = ?
          AND ja.status = 'APPROVED'
          AND j.status = ?
        ORDER BY j.created_at DESC
        """,
        (technician_id, JobStatus.ACTIVE.value),
    )

    rows = [dict(r) for r in cur.fetchall()]
    _attach_tasks(conn, rows)
    conn.close()
    return rows


def list_completed_jobs_for_technician(technician_id: int):
    conn = _conn()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT j.*
        FROM jobs j
        JOIN job_applications ja ON ja.job_id = j.id
        WHERE ja.technician_id = ?
          AND ja.status = 'APPROVED'
          AND j.status = ?
        ORDER BY j.created_at DESC
        """,
        (technician_id, JobStatus.COMPLETED.value),
    )

    rows = [dict(r) for r in cur.fetchall()]
    _attach_tasks(conn, rows)
    conn.close()
    return rows


def list_recommended_jobs_for_technician(technician_id: int):
    """Recommended = outgoing jobs not yet applied to, biased towards categories
    the technician has successfully completed before.

    IMPORTANT: Uses only columns already present in the main project's `jobs` table.
    """
    conn = _conn()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT j.*
        FROM jobs j
        WHERE j.status IN ('OUTGOING')
          AND j.id NOT IN (
            SELECT job_id
            FROM job_applications
            WHERE technician_id = ?
          )
          AND j.service_category IN (
            SELECT jj.service_category
            FROM jobs jj
            JOIN job_applications ja ON ja.job_id = jj.id
            WHERE ja.technician_id = ?
              AND ja.status = 'APPROVED'
              AND jj.status = 'COMPLETED'
          )
        ORDER BY j.created_at DESC
        """,
        (technician_id, technician_id),
    )

    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows