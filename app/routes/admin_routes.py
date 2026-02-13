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

    # Status counts (UI-only; no logic/routing changes)
    approved_count = count_requests_by_status("APPROVED")
    rejected_count = count_requests_by_status("REJECTED")
    # "RETRIEVED" may not exist in this MVP; count will naturally be 0.
    retrieved_count = count_requests_by_status("RETRIEVED")

    approved = list_requests_by_status("APPROVED")
    rejected = list_requests_by_status("REJECTED")
    retrieved = list_requests_by_status("RETRIEVED")

    # Company-wide stats (UI-only)
    db = get_db()
    tech_count = db.execute("SELECT COUNT(1) AS c FROM users WHERE role='TECHNICIAN'").fetchone()["c"]
    biz_count = db.execute("SELECT COUNT(1) AS c FROM users WHERE role='BUSINESS'").fetchone()["c"]
    # Agencies not in this scope; keep derived count for UI parity.
    agency_count = db.execute("SELECT COUNT(1) AS c FROM users WHERE role='AGENCY'").fetchone()["c"]

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
        agency_count=int(agency_count),
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
    user = get_user_by_id(req["user_id"])
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
