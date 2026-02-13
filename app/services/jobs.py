import sqlite3
from datetime import datetime
from typing import Optional, List
from flask import current_app

from .job_enums import JobStatus, ApplicationStatus


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
          status, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            business_id,
            title.strip(),
            description.strip(),
            service_category.strip(),
            hourly_rate_min,
            hourly_rate_max,
            (location or "").strip() or None,
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
