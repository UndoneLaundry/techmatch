from __future__ import annotations

from typing import Optional, Tuple, List, Dict, Any
from flask import abort

from ..db import get_db


def get_job_window_for_technician(job_id: int, technician_id: int) -> dict:
    """Return job + application + tasks and whether tasks should be visible.

    Visibility rule (as requested):
      - If application status is APPROVED -> show tasks
      - If application status is APPLIED -> hide tasks
      - If job is ACTIVE -> show tasks (even if application isn't present)
    """
    db = get_db()

    job = db.execute("SELECT * FROM jobs WHERE id = ?", (int(job_id),)).fetchone()
    if job is None:
        abort(404)

    app_row = db.execute(
        """
        SELECT * FROM job_applications
        WHERE job_id = ? AND technician_id = ?
        ORDER BY id DESC LIMIT 1
        """,
        (int(job_id), int(technician_id)),
    ).fetchone()

    # Security: technician can only view if they applied or are assigned.
    assigned_id = job["assigned_technician_id"]
    if app_row is None and (assigned_id is None or int(assigned_id) != int(technician_id)):
        abort(403)

    job_status = job["status"]
    app_status = app_row["status"] if app_row else None

    show_tasks = (job_status == "ACTIVE") or (app_status == "APPROVED")

    tasks = []
    if show_tasks:
        tasks = db.execute(
            "SELECT * FROM job_tasks WHERE job_id = ? ORDER BY id ASC",
            (int(job_id),),
        ).fetchall()

    return {
        "job": job,
        "application": app_row,
        "show_tasks": show_tasks,
        "tasks": tasks,
    }
