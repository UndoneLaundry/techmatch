import sqlite3
from datetime import datetime
from typing import Optional, List
from flask import current_app

from .jobs_enum import JobStatus, ApplicationStatus


class DomainError(Exception):
    pass


def _conn():
    conn = sqlite3.connect(current_app.config["DATABASE"])
    conn.row_factory = sqlite3.Row
    return conn


# =====================================================
# JOB CREATION
# =====================================================

def create_job(
    *,
    business_id: int,
    title: str,
    description: str,
    service_category: str,
    hourly_rate_min: int,
    hourly_rate_max: int,
    location: Optional[str],
    start_date: Optional[int] = None,   # new
    end_date: Optional[int] = None,     # new
):
    if hourly_rate_min <= 0 or hourly_rate_max <= 0 or hourly_rate_min > hourly_rate_max:
        raise DomainError("Invalid hourly rate range.")

    now = datetime.utcnow().isoformat()

    conn = _conn()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO jobs (
          business_id, title, description, service_category,
          hourly_rate_min, hourly_rate_max, location,
          start_date, end_date,                -- new
          status, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            business_id,
            title.strip(),
            description.strip(),
            service_category.strip(),
            hourly_rate_min,
            hourly_rate_max,
            (location or "").strip() or None,
            start_date,                         # new
            end_date,                            # new
            JobStatus.OUTGOING.value,
            now,
            now,
        ),
    )

    conn.commit()
    job_id = cur.lastrowid
    conn.close()

    return job_id


# =====================================================
# LIST OPEN JOBS
# =====================================================

def list_open_jobs() -> List[dict]:
    conn = _conn()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT * FROM jobs
        WHERE status = ?
        ORDER BY created_at DESC
        """,
        (JobStatus.OUTGOING.value,),
    )

    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


# =====================================================
# APPLY TO JOB
# =====================================================

def apply_to_job(*, job_id: int, technician_id: int):
    conn = _conn()
    cur = conn.cursor()

    cur.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
    job = cur.fetchone()
    if not job:
        raise DomainError("Job not found.")

    if job["status"] != JobStatus.OUTGOING.value:
        raise DomainError("Job is not accepting applications.")

    cur.execute(
        """
        SELECT * FROM job_applications
        WHERE job_id = ? AND technician_id = ?
        """,
        (job_id, technician_id),
    )
    existing = cur.fetchone()

    now = datetime.utcnow().isoformat()

    if existing and existing["status"] != ApplicationStatus.WITHDRAWN.value:
        raise DomainError("Already applied.")

    if existing:
        cur.execute(
            """
            UPDATE job_applications
            SET status = ?, applied_at = ?
            WHERE id = ?
            """,
            (ApplicationStatus.APPLIED.value, now, existing["id"]),
        )
    else:
        cur.execute(
            """
            INSERT INTO job_applications (job_id, technician_id, status, applied_at)
            VALUES (?, ?, ?, ?)
            """,
            (job_id, technician_id, ApplicationStatus.APPLIED.value, now),
        )

    conn.commit()
    conn.close()


# =====================================================
# WITHDRAW APPLICATION
# =====================================================

def withdraw_application(*, job_id: int, technician_id: int):
    conn = _conn()
    cur = conn.cursor()

    cur.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
    job = cur.fetchone()
    if not job:
        raise DomainError("Job not found.")

    if job["status"] != JobStatus.OUTGOING.value:
        raise DomainError("Cannot withdraw after approval.")

    cur.execute(
        """
        SELECT * FROM job_applications
        WHERE job_id = ? AND technician_id = ?
        """,
        (job_id, technician_id),
    )
    app = cur.fetchone()
    if not app:
        raise DomainError("No application found.")

    if app["status"] != ApplicationStatus.APPLIED.value:
        raise DomainError("Application not withdrawable.")

    cur.execute(
        """
        UPDATE job_applications
        SET status = ?
        WHERE id = ?
        """,
        (ApplicationStatus.WITHDRAWN.value, app["id"]),
    )

    conn.commit()
    conn.close()


# =====================================================
# BUSINESS JOB MANAGEMENT FUNCTIONS
# =====================================================

def get_job_stats_for_business(business_id: int) -> dict:
    """Return counts of jobs by status for the dashboard."""
    conn = _conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN status = 'OUTGOING' THEN 1 ELSE 0 END) AS outgoing,
            SUM(CASE WHEN status = 'ACTIVE' THEN 1 ELSE 0 END) AS active,
            SUM(CASE WHEN status = 'PENDING_CONFIRMATION' THEN 1 ELSE 0 END) AS pending_confirmation,
            SUM(CASE WHEN status = 'COMPLETED' THEN 1 ELSE 0 END) AS completed
        FROM jobs
        WHERE business_id = ?
    """, (business_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else {}


def get_jobs_by_business(business_id: int, status: Optional[str] = None) -> list[dict]:
    """Return jobs created by this business, optionally filtered by status."""
    conn = _conn()
    cur = conn.cursor()
    if status:
        cur.execute("""
            SELECT *
            FROM jobs
            WHERE business_id = ? AND status = ?
            ORDER BY created_at DESC
        """, (business_id, status))
    else:
        cur.execute("""
            SELECT *
            FROM jobs
            WHERE business_id = ?
            ORDER BY created_at DESC
        """, (business_id,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_job_details_for_business(job_id: int, business_id: int) -> Optional[dict]:
    """Return job with its tasks and pending application count, ensuring it belongs to the business."""
    conn = _conn()
    cur = conn.cursor()
    # Get job
    cur.execute("SELECT * FROM jobs WHERE id = ? AND business_id = ?", (job_id, business_id))
    job = cur.fetchone()
    if not job:
        conn.close()
        return None
    job = dict(job)
    # Get tasks
    cur.execute("SELECT * FROM job_tasks WHERE job_id = ? ORDER BY id", (job_id,))
    tasks = [dict(t) for t in cur.fetchall()]
    job["tasks"] = tasks
    # Get pending application count
    cur.execute("SELECT COUNT(*) AS cnt FROM job_applications WHERE job_id = ? AND status = 'APPLIED'", (job_id,))
    cnt = cur.fetchone()["cnt"]
    job["application_count"] = cnt
    conn.close()
    return job


def add_job_task(job_id: int, business_id: int, title: str) -> int:
    """Add a task to a job (business must own the job)."""
    conn = _conn()
    cur = conn.cursor()
    # Verify ownership
    cur.execute("SELECT id FROM jobs WHERE id = ? AND business_id = ?", (job_id, business_id))
    if not cur.fetchone():
        conn.close()
        raise PermissionError("Job not found or not owned by you")

    now = datetime.utcnow().isoformat()
    cur.execute("""
        INSERT INTO job_tasks (job_id, title, created_at)
        VALUES (?, ?, ?)
    """, (job_id, title, now))
    task_id = cur.lastrowid
    conn.commit()
    conn.close()
    return task_id


def approve_job_completion(job_id: int, business_id: int) -> None:
    """Change job status from PENDING_CONFIRMATION to COMPLETED."""
    conn = _conn()
    cur = conn.cursor()
    # Verify ownership and current status
    cur.execute("""
        SELECT id, status FROM jobs
        WHERE id = ? AND business_id = ?
    """, (job_id, business_id))
    job = cur.fetchone()
    if not job:
        conn.close()
        raise PermissionError("Job not found")
    if job["status"] != "PENDING_CONFIRMATION":
        conn.close()
        raise ValueError("Job is not waiting for approval")
    now = datetime.utcnow().isoformat()
    cur.execute("""
        UPDATE jobs
        SET status = 'COMPLETED', updated_at = ?
        WHERE id = ?
    """, (now, job_id))
    conn.commit()
    conn.close()


def get_applications_for_job(job_id: int, business_id: int) -> list[dict]:
    """Return all pending applications for a job, verifying the job belongs to the business."""
    conn = _conn()
    cur = conn.cursor()
    # Verify job ownership
    cur.execute("SELECT id FROM jobs WHERE id = ? AND business_id = ?", (job_id, business_id))
    if not cur.fetchone():
        conn.close()
        raise PermissionError("Job not found or not owned by you")

    cur.execute("""
        SELECT ja.*, u.email, tp.full_name
        FROM job_applications ja
        JOIN users u ON u.id = ja.technician_id
        LEFT JOIN technician_profiles tp ON tp.user_id = ja.technician_id
        WHERE ja.job_id = ? AND ja.status = 'APPLIED'
        ORDER BY ja.applied_at ASC
    """, (job_id,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def approve_application(job_id: int, application_id: int, business_id: int) -> None:
    """Approve a technician's application, set job to ACTIVE and assign technician."""
    conn = _conn()
    cur = conn.cursor()
    try:
        # Verify job ownership
        cur.execute("SELECT id FROM jobs WHERE id = ? AND business_id = ?", (job_id, business_id))
        if not cur.fetchone():
            raise PermissionError("Job not found or not owned by you")

        # Get the application and verify it's for this job and still APPLIED
        cur.execute("""
            SELECT id, technician_id, status
            FROM job_applications
            WHERE id = ? AND job_id = ?
        """, (application_id, job_id))
        app = cur.fetchone()
        if not app:
            raise ValueError("Application not found")
        if app["status"] != "APPLIED":
            raise ValueError("Application is no longer pending")

        # Update application to APPROVED
        cur.execute("""
            UPDATE job_applications
            SET status = 'APPROVED'
            WHERE id = ?
        """, (application_id,))

        # Update job status to ACTIVE and assign technician
        now = datetime.utcnow().isoformat()
        cur.execute("""
            UPDATE jobs
            SET status = 'ACTIVE', assigned_technician_id = ?, updated_at = ?
            WHERE id = ?
        """, (app["technician_id"], now, job_id))

        # Deny all other applications for this job
        cur.execute("""
            UPDATE job_applications
            SET status = 'DENIED'
            WHERE job_id = ? AND id != ? AND status = 'APPLIED'
        """, (job_id, application_id))

        conn.commit()
    finally:
        conn.close()


def delete_job(job_id: int, business_id: int) -> None:
    """Delete a job and its tasks. Only allowed if status is OUTGOING."""
    conn = _conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, status FROM jobs WHERE id = ? AND business_id = ?", (job_id, business_id))
        job = cur.fetchone()
        if not job:
            raise PermissionError("Job not found or not owned by you.")
        if job["status"] != JobStatus.OUTGOING.value:
            raise ValueError("Only open jobs can be deleted.")
        cur.execute("DELETE FROM job_tasks WHERE job_id = ?", (job_id,))
        cur.execute("DELETE FROM job_applications WHERE job_id = ?", (job_id,))
        cur.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
        conn.commit()
    finally:
        conn.close()


def delete_task(task_id: int, job_id: int, business_id: int) -> None:
    """Delete a single task. Business must own the parent job."""
    conn = _conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id FROM jobs WHERE id = ? AND business_id = ?", (job_id, business_id))
        if not cur.fetchone():
            raise PermissionError("Job not found or not owned by you.")
        cur.execute("DELETE FROM job_tasks WHERE id = ? AND job_id = ?", (task_id, job_id))
        if cur.rowcount == 0:
            raise ValueError("Task not found.")
        conn.commit()
    finally:
        conn.close()


def deny_application(job_id: int, application_id: int, business_id: int) -> None:
    """Deny a specific application (keep job OUTGOING)."""
    conn = _conn()
    cur = conn.cursor()
    try:
        # Verify job ownership
        cur.execute("SELECT id FROM jobs WHERE id = ? AND business_id = ?", (job_id, business_id))
        if not cur.fetchone():
            raise PermissionError("Job not found or not owned by you")

        cur.execute("""
            UPDATE job_applications
            SET status = 'DENIED'
            WHERE id = ? AND job_id = ? AND status = 'APPLIED'
        """, (application_id, job_id))
        if cur.rowcount == 0:
            raise ValueError("Application not found or already processed")
        conn.commit()
    finally:
        conn.close()