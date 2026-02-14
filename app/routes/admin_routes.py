import os

from flask import Blueprint, render_template, redirect, url_for, request, flash, session, current_app, send_from_directory, send_file, abort
from ..auth.decorators import admin_required, login_required
from ..services.verification_service import (
    list_pending_requests, list_requests_by_status, count_requests_by_status,
    get_request_by_id, list_flags, approve_request, reject_request
)
from ..services.document_service import list_documents, get_document_by_id
from ..services.notification_service import create_notification
from ..services.user_service import get_user_by_id
from ..db import get_db
from ..services.skill_service import (
    get_skill_document_by_id,
    list_pending_skill_requests,
    get_skill_request,
    list_skill_documents,
    approve_skill_request,
    reject_skill_request,
)

bp = Blueprint("admin", __name__, url_prefix="/admin")

@bp.get("/homepage")
@admin_required
def homepage():
    pending = list_pending_requests()
    pending_skills = list_pending_skill_requests()

    approved_count = count_requests_by_status("APPROVED")
    rejected_count = count_requests_by_status("REJECTED")

    retrieved_count = count_requests_by_status("RETRIEVED")

    approved = list_requests_by_status("APPROVED")
    rejected = list_requests_by_status("REJECTED")
    retrieved = list_requests_by_status("RETRIEVED")

    # Company-wide stats (UI-only)
    db = get_db()
    tech_count = db.execute("SELECT COUNT(1) AS c FROM users WHERE role='TECHNICIAN'").fetchone()["c"]
    biz_count = db.execute("SELECT COUNT(1) AS c FROM users WHERE role='BUSINESS'").fetchone()["c"]

    return render_template(
        "admin_homepage.html",
        pending=pending,
        pending_skills=pending_skills,
        approved=approved,
        rejected=rejected,
        retrieved=retrieved,
        approved_count=int(approved_count),
        rejected_count=int(rejected_count),
        retrieved_count=int(retrieved_count),
        tech_count=int(tech_count),
        biz_count=int(biz_count),
        
    )




@bp.get("/skills/pending")
@admin_required
def skills_pending():
    rows = list_pending_skill_requests()
    return render_template("admin_skills_pending.html", rows=rows)


@bp.get("/skills/review/<int:skill_id>")
@admin_required
def skills_review(skill_id: int):
    skill = get_skill_request(skill_id)
    if skill is None:
        flash("Skill request not found.", "error")
        return redirect(url_for("admin.skills_pending"))
    docs = list_skill_documents(skill_id)
    user = get_user_by_id(skill["user_id"])
    return render_template("admin_skill_review.html", skill=skill, docs=docs, user=user)


@bp.post("/skills/approve/<int:skill_id>")
@admin_required
def skills_approve(skill_id: int):
    try:
        approve_skill_request(skill_id, session["user_id"])
    except Exception as e:
        flash(str(e), "error")
        return redirect(url_for("admin.skills_review", skill_id=skill_id))
    skill = get_skill_request(skill_id)
    if skill:
        create_notification(skill["user_id"], "SKILL_APPROVED", f"✅ Skill approved: {skill['skill_name']}")
    flash("Skill approved.", "info")
    return redirect(url_for("admin.skills_review", skill_id=skill_id))


@bp.post("/skills/reject/<int:skill_id>")
@admin_required
def skills_reject(skill_id: int):
    reason = request.form.get("reason", "").strip() or "Rejected by admin."
    try:
        reject_skill_request(skill_id, session["user_id"], reason)
    except Exception as e:
        flash(str(e), "error")
        return redirect(url_for("admin.skills_review", skill_id=skill_id))
    skill = get_skill_request(skill_id)
    if skill:
        create_notification(skill["user_id"], "SKILL_REJECTED", f"❌ Skill rejected: {skill['skill_name']}. Reason: {reason}")
    flash("Skill rejected.", "info")
    return redirect(url_for("admin.skills_review", skill_id=skill_id))

@bp.get("/review/<int:request_id>")
@admin_required
def review_request(request_id: int):
    req = get_request_by_id(request_id)
    if req is None:
        flash("Request not found.", "error")
        return redirect(url_for("admin.homepage"))
    flags = list_flags(request_id)
    docs = list_documents(request_id)
    urow = get_user_by_id(req["user_id"]) or {}
    # Merge profile fields so templates can display name/registration
    db = get_db()
    user = {"email": urow.get("email") if hasattr(urow, 'get') else (urow["email"] if urow else None)}
    if req["user_role"] == "TECHNICIAN":
        prow = db.execute("SELECT full_name FROM technician_profiles WHERE user_id = ?", (req["user_id"],)).fetchone()
        user["full_name"] = prow["full_name"] if prow else "-"
    else:
        prow = db.execute("SELECT company_name, registration_identifier FROM business_profiles WHERE user_id = ?", (req["user_id"],)).fetchone()
        user["company_name"] = prow["company_name"] if prow else "-"
        user["registration_identifier"] = prow["registration_identifier"] if prow else "-"
    return render_template("review_request.html", req=req, user=user, flags=flags, docs=docs)

@bp.post("/approve/<int:request_id>")
@admin_required
def approve(request_id: int):
    req = get_request_by_id(request_id)
    if req is None or req["status"] != "PENDING":
        flash("Invalid request state.", "error")
        return redirect(url_for("admin.homepage"))

    approve_request(request_id, session["user_id"])
    create_notification(req["user_id"], "VERIFICATION_APPROVED", "🎉 Your account has been verified! You may now proceed.")
    flash("Approved.", "info")
    return redirect(url_for("admin.review_request", request_id=request_id))

@bp.post("/reject/<int:request_id>")
@admin_required
def reject(request_id: int):
    req = get_request_by_id(request_id)
    if req is None or req["status"] != "PENDING":
        flash("Invalid request state.", "error")
        return redirect(url_for("admin.homepage"))

    reason = request.form.get("reason", "").strip() or "Rejected by admin."
    reject_request(request_id, session["user_id"], reason, current_app.config["COOLDOWN_DURATION_SECONDS"])
    create_notification(req["user_id"], "VERIFICATION_REJECTED", f"Your account verification was rejected. Reason: {reason}")
    flash("Rejected (cooldown started).", "info")
    return redirect(url_for("admin.review_request", request_id=request_id))


@bp.get("/documents/download/<int:doc_id>")
@login_required
def download_document(doc_id: int):
    doc = get_document_by_id(doc_id)
    if doc is None:
        abort(404)
    folder = current_app.config["UPLOAD_FOLDER"]
    return send_from_directory(folder, doc["stored_filename"], as_attachment=True, download_name=doc["original_filename"])


@bp.get("/documents/view/<int:doc_id>")
@admin_required
def view_document(doc_id: int):
    doc = get_document_by_id(doc_id)
    if doc is None:
        abort(404)
    if (doc["file_extension"] or "").lower() != "pdf":
        abort(404)
    folder = current_app.config["UPLOAD_FOLDER"]
    path = os.path.join(folder, doc["stored_filename"])
    if not os.path.exists(path):
        abort(404)
    return send_file(path, mimetype="application/pdf", as_attachment=False)


@bp.get("/skills/documents/download/<int:doc_id>")
@login_required
def download_skill_document(doc_id: int):
    doc = get_skill_document_by_id(doc_id)
    if doc is None:
        abort(404)
    folder = current_app.config["UPLOAD_FOLDER"]
    return send_from_directory(folder, doc["stored_filename"], as_attachment=True, download_name=doc["original_filename"])


@bp.get("/skills/documents/view/<int:doc_id>")
@admin_required
def view_skill_document(doc_id: int):
    doc = get_skill_document_by_id(doc_id)
    if doc is None:
        abort(404)
    if (doc["file_extension"] or "").lower() != "pdf":
        abort(404)
    folder = current_app.config["UPLOAD_FOLDER"]
    path = os.path.join(folder, doc["stored_filename"])
    if not os.path.exists(path):
        abort(404)
    return send_file(path, mimetype="application/pdf", as_attachment=False)



# ===============================
# Admin Listings + Search + Audit Logs (V4)
# ===============================

from flask import request, jsonify
from datetime import datetime

def _fmt_ts(ts: int | None) -> str:
    if not ts:
        return "-"
    try:
        return datetime.utcfromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(ts)

@bp.get("/technicians")
@admin_required
def admin_technicians():

    """
    List approved/active technicians.
    Adds current job (description + status) if they are assigned to an ACTIVE / PENDING_CONFIRMATION job.
    Supports optional ?q=<name> filtering.
    """
    conn = get_db()
    q = (request.args.get("q") or "").strip()

    status = (request.args.get("status") or "approved").lower().strip()
    if status not in ("approved","rejected"):
        status = "approved"


    sql = """
    SELECT
      tp.user_id AS technician_user_id,
      tp.full_name AS technician_name,
      u.email AS email,

      j.title AS job_title,
      j.description AS job_description,
      j.status AS job_status,
      j.updated_at AS job_updated_at,

      vr.id AS latest_verification_request_id,
      vr.status AS verification_status,
      vr.rejection_reason AS rejection_reason
    FROM technician_profiles tp
    JOIN users u ON u.id = tp.user_id
    LEFT JOIN verification_requests vr
      ON vr.id = (
        SELECT vr2.id
        FROM verification_requests vr2
        WHERE vr2.user_id = tp.user_id
        ORDER BY vr2.submitted_at DESC
        LIMIT 1
      )
    LEFT JOIN jobs j
      ON j.id = (
        SELECT j2.id
        FROM jobs j2
        WHERE j2.assigned_technician_id = tp.user_id
          AND j2.status IN ('ACTIVE','PENDING_CONFIRMATION')
        ORDER BY j2.updated_at DESC
        LIMIT 1
      )
    WHERE u.role = 'TECHNICIAN'
      AND u.is_active = 1
      AND (
            (? = 'approved' AND vr.status = 'APPROVED')
         OR (? = 'rejected' AND vr.status = 'REJECTED')
      )
    """
    params = [status, status]
    if q:
        sql += " AND tp.full_name LIKE ?"
        params.append(f"%{q}%")

    sql += " ORDER BY tp.full_name ASC"

    technicians = conn.execute(sql, params).fetchall()

    return render_template("admin/technicians.html", technicians=technicians, q=q, status=status, fmt_ts=_fmt_ts)







@bp.get("/technicians/search")
@admin_required
def admin_technician_search():
    conn = get_db()
    q = (request.args.get("q") or "").strip()
    if not q:
        return jsonify([])

    rows = conn.execute(
        "SELECT tp.full_name AS name, vr.id AS request_id "
        "FROM technician_profiles tp "
        "JOIN users u ON u.id = tp.user_id "
        "JOIN verification_requests vr ON vr.user_id = tp.user_id "
        "WHERE u.role = 'TECHNICIAN' AND tp.full_name LIKE ? "
        "ORDER BY tp.full_name ASC LIMIT 8",
        (f"%{q}%",),
    ).fetchall()

    return jsonify([{"name": r["name"], "request_id": r["request_id"]} for r in rows if r["name"] and r["request_id"]])

    


@bp.get("/businesses")
@admin_required
def admin_businesses():
    status = (request.args.get("status") or "approved").upper().strip()
    if status not in ("APPROVED", "REJECTED"):
        status = "APPROVED"

    conn = get_db()

    rows = conn.execute(
        """
        SELECT
          bp.user_id AS business_user_id,
          bp.company_name AS business_name,
          u.email AS email,
          bp.registration_identifier AS registration_identifier,

          j.title AS latest_job_title,
          j.created_at AS latest_job_created_at,

          vr.id AS latest_verification_request_id,
          vr.status AS verification_status,
          vr.rejection_reason AS rejection_reason,

          (
            SELECT COUNT(*)
            FROM uploaded_documents d
            WHERE d.uploaded_by_user_id = bp.user_id
              AND d.document_type = 'BUSINESS_SUPPORT'
          ) AS business_cert_doc_count

        FROM business_profiles bp
        JOIN users u ON u.id = bp.user_id
        LEFT JOIN verification_requests vr
          ON vr.id = (
            SELECT vr2.id
            FROM verification_requests vr2
            WHERE vr2.user_id = bp.user_id
            ORDER BY vr2.submitted_at DESC
            LIMIT 1
          )
        LEFT JOIN jobs j
          ON j.id = (
            SELECT j2.id
            FROM jobs j2
            WHERE j2.business_id = bp.user_id
            ORDER BY j2.created_at DESC
            LIMIT 1
          )
        WHERE u.role = 'BUSINESS'
          AND u.is_active = 1
          AND vr.status = ?
        ORDER BY bp.company_name ASC
        """,
        (status,),
    ).fetchall()

    return render_template("admin/businesses.html", businesses=rows, status=status.lower(), fmt_ts=_fmt_ts)


@bp.get("/audit-logs")
@admin_required
def audit_logs():
    """
    General audit log built from existing tables (no schema changes):
      - Admin actions (admin_actions)
      - Business actions inferred from jobs table
      - Technician actions inferred from job_applications table
    Filter: ?actor=all|admin|business|technician  (default: all)
    """
    actor = (request.args.get("actor") or "all").lower()
    if actor not in ("all","admin","business","technician"):
        actor = "all"

    conn = get_db()

    events = []

    # ADMIN events
    if actor in ("all","admin"):
        rows = conn.execute(
            """
            SELECT
              aa.timestamp AS ts,
              'ADMIN' AS actor_role,
              u.email AS actor_name,
              aa.action_type AS action,
              aa.target_verification_request_id AS target_id,
              aa.notes AS details
            FROM admin_actions aa
            LEFT JOIN users u ON u.id = aa.admin_user_id
            ORDER BY aa.timestamp DESC
            LIMIT 500
            """
        ).fetchall()
        events.extend([dict(r) for r in rows])

    # BUSINESS events (JOB_CREATED + JOB_UPDATED + JOB_ASSIGNED)
    if actor in ("all","business"):
        rows = conn.execute(
            """
            SELECT
              j.created_at AS ts,
              'BUSINESS' AS actor_role,
              bp.company_name AS actor_name,
              'JOB_CREATED' AS action,
              j.id AS target_id,
              j.title AS details
            FROM jobs j
            LEFT JOIN business_profiles bp ON bp.user_id = j.business_id
            ORDER BY j.created_at DESC
            LIMIT 500
            """
        ).fetchall()
        events.extend([dict(r) for r in rows])

        # assignment events
        rows2 = conn.execute(
            """
            SELECT
              j.updated_at AS ts,
              'BUSINESS' AS actor_role,
              bp.company_name AS actor_name,
              'JOB_UPDATED' AS action,
              j.id AS target_id,
              ('status=' || j.status || ', assigned_technician_id=' || COALESCE(j.assigned_technician_id, 'NULL')) AS details
            FROM jobs j
            LEFT JOIN business_profiles bp ON bp.user_id = j.business_id
            WHERE j.updated_at IS NOT NULL
              AND j.updated_at != j.created_at
            ORDER BY j.updated_at DESC
            LIMIT 500
            """
        ).fetchall()
        events.extend([dict(r) for r in rows2])

    # TECHNICIAN events (job_applications)
    if actor in ("all","technician"):
        rows = conn.execute(
            """
            SELECT
              ja.applied_at AS ts,
              'TECHNICIAN' AS actor_role,
              tp.full_name AS actor_name,
              ('JOB_APPLICATION_' || ja.status) AS action,
              ja.job_id AS target_id,
              (j.title) AS details
            FROM job_applications ja
            LEFT JOIN technician_profiles tp ON tp.user_id = ja.technician_id
            LEFT JOIN jobs j ON j.id = ja.job_id
            ORDER BY ja.applied_at DESC
            LIMIT 500
            """
        ).fetchall()
        events.extend([dict(r) for r in rows])

    # sort merged events
    def _ts(e):
        try:
            return int(e.get("ts") or 0)
        except Exception:
            return 0
    events.sort(key=_ts, reverse=True)

    # trim
    events = events[:800]

    return render_template("admin/audit_logs.html", events=events, actor=actor, fmt_ts=_fmt_ts)



@bp.get("/review-view/<int:request_id>")
@admin_required
def review_view(request_id: int):
    req = get_request_by_id(request_id)
    if not req:
        flash("Request not found.", "error")
        return redirect(url_for("admin.homepage"))

    flags = list_flags(request_id)
    docs = list_documents(request_id)

    db = get_db()
    base_user = get_user_by_id(req["user_id"])

    user = {"email": base_user["email"]}

    if req["user_role"] == "TECHNICIAN":
        row = db.execute(
            "SELECT full_name, bio FROM technician_profiles WHERE user_id = ?",
            (req["user_id"],),
        ).fetchone()
        if row:
            user["full_name"] = row["full_name"]
            user["bio"] = row["bio"]
    else:
        row = db.execute(
            "SELECT company_name, registration_identifier FROM business_profiles WHERE user_id = ?",
            (req["user_id"],),
        ).fetchone()
        if row:
            user["company_name"] = row["company_name"]
            user["registration_identifier"] = row["registration_identifier"]

    if req["user_role"] == "TECHNICIAN":
        row = db.execute(
            "SELECT full_name FROM technician_profiles WHERE user_id = ?",
            (req["user_id"],),
        ).fetchone()
        user["full_name"] = row["full_name"] if row else "-"
    else:
        row = db.execute(
            "SELECT company_name, registration_identifier FROM business_profiles WHERE user_id = ?",
            (req["user_id"],),
        ).fetchone()
        if row:
            user["company_name"] = row["company_name"]
            user["registration_identifier"] = row["registration_identifier"]

    return render_template(
        "review_request_view.html",
        req=req,
        user=user,
        flags=flags,
        docs=docs,
    )
