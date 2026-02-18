import time
import json
from flask import Blueprint, render_template, session, request, redirect, url_for, flash
from ..auth.decorators import login_required, pending_only, verification_required, role_required, cooldown_guard, single_active_request_only
from ..services.verification_service import get_latest_request_for_user, is_cooldown_active_for_request, create_verification_request, attach_flag
from ..services.notification_service import list_notifications
from ..services.document_service import save_uploaded_documents
from ..services.flag_service import compute_common_flags
from ..db import get_db
from ..services.profile_service import (
    get_technician_profile,
    get_business_profile,
    update_technician_profile,
    update_business_profile,
)
from ..services.user_service import change_password, change_email
from ..services.validation_service import validate_name, validate_email
from ..services.skill_service import (
    list_my_skill_items,
    create_skill_request,
    attach_skill_documents,
)
from flask import current_app

bp = Blueprint("user", __name__)

@bp.get("/pending")
@login_required
@pending_only
def pending():
    user_id = session["user_id"]
    req = get_latest_request_for_user(user_id)
    cooldown_active = False
    cooldown_until_human = None
    if req and req["status"] == "REJECTED":
        cooldown_active = is_cooldown_active_for_request(req)
        if req["cooldown_until"]:
            cooldown_until_human = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(req["cooldown_until"])))
    return render_template("pending.html", req=req, cooldown_active=cooldown_active, cooldown_until_human=cooldown_until_human)

@bp.get("/homepage")
@login_required
@verification_required
def homepage():
    # Legacy endpoint: keep for backward links, but never render a mixed homepage.
    role = session.get("role")
    if role == "TECHNICIAN":
        return redirect(url_for("technician.homepage_page"))
    if role == "BUSINESS":
        return redirect(url_for("business.homepage_page"))
    if role == "ADMIN":
        return redirect(url_for("admin.homepage"))
    return redirect(url_for("auth.login_get"))


@bp.get("/profile")
@login_required
def profile_get():
    user_id = session["user_id"]
    role = session.get("role")
    tech = get_technician_profile(user_id) if role == "TECHNICIAN" else None
    biz = get_business_profile(user_id) if role == "BUSINESS" else None
    skill_items = list_my_skill_items(user_id) if role == "TECHNICIAN" else []
    skill_docs = []
    if role == "TECHNICIAN":
        from app.services.document_service import list_my_skill_docs
        skill_docs = list_my_skill_docs(user_id)
    from app.services.skill_suggest_service import CANONICAL_SKILLS
    canonical_skills = CANONICAL_SKILLS if role == "TECHNICIAN" else []
    return render_template(
        "profile.html",
        role=role,
        tech=tech,
        biz=biz,
        skill_items=skill_items,
        skill_docs=skill_docs,
        canonical_skills=canonical_skills,
    )


@bp.post("/profile/update")
@login_required
def profile_update_post():
    user_id = session["user_id"]
    role = session.get("role")
    if role == "TECHNICIAN":
        full_name = request.form.get("full_name", "").strip()
        bio = request.form.get("bio", "").strip() or None
        ok, err = validate_name(full_name)
        if not ok:
            flash(err, "error")
            return redirect(url_for("user.profile_get"))
        update_technician_profile(user_id, full_name, bio)
        flash("Profile updated.", "info")
        return redirect(url_for("user.profile_get"))

    if role == "BUSINESS":
        company_name = request.form.get("company_name", "").strip()
        registration_identifier = request.form.get("registration_identifier", "").strip()
        update_business_profile(user_id, company_name, registration_identifier)
        flash("Profile updated.", "info")
        return redirect(url_for("user.profile_get"))

    flash("Forbidden.", "error")
    return redirect(url_for("user.homepage"))




@bp.post("/profile/change-email")
@login_required
def profile_change_email_post():
    user_id = session["user_id"]
    new_email = (request.form.get("new_email") or "").strip().lower()
    password = request.form.get("password", "")

    ok, err = validate_email(new_email)
    if not ok:
        flash(err, "error")
        return redirect(url_for("user.profile_get"))

    ok, msg = change_email(user_id, password, new_email)
    if not ok:
        flash(msg, "error")
        return redirect(url_for("user.profile_get"))

    session["email"] = new_email
    flash("Email updated.", "info")
    return redirect(url_for("user.profile_get"))


@bp.post("/profile/submit-verification")
@login_required
@cooldown_guard
@single_active_request_only
def profile_submit_verification_post():
    """(Re)submit verification documents from profile/settings."""
    user_id = session["user_id"]
    role = session.get("role")

    if role == "TECHNICIAN":
        tech = get_technician_profile(user_id)
        if tech is None:
            flash("Technician profile not found.", "error")
            return redirect(url_for("user.profile_get"))
        try:
            req_id = create_verification_request(user_id=user_id, user_role="TECHNICIAN")
        except ValueError as e:
            flash(str(e), "error")
            return redirect(url_for("user.pending"))
        files = request.files.getlist("cert_docs")
        try:
            save_uploaded_documents(files, req_id, user_id, "CERTIFICATION")
        except Exception as e:
            flash(str(e), "error")
            return redirect(url_for("user.profile_get"))
        for ft, sev, desc in compute_common_flags(tech["full_name"]):
            attach_flag(req_id, ft, sev, desc)

    elif role == "BUSINESS":
        biz = get_business_profile(user_id)
        if biz is None:
            flash("Business profile not found.", "error")
            return redirect(url_for("user.profile_get"))
        try:
            req_id = create_verification_request(user_id=user_id, user_role="BUSINESS")
        except ValueError as e:
            flash(str(e), "error")
            return redirect(url_for("user.pending"))
        files = request.files.getlist("support_docs")
        try:
            save_uploaded_documents(files, req_id, user_id, "BUSINESS_SUPPORT")
        except Exception as e:
            flash(str(e), "error")
            return redirect(url_for("user.profile_get"))
        for ft, sev, desc in compute_common_flags(biz["company_name"]):
            attach_flag(req_id, ft, sev, desc)
    else:
        flash("Forbidden.", "error")
        return redirect(url_for("user.homepage"))

    db = get_db()
    with db:
        db.execute("UPDATE users SET is_verified = 0 WHERE id = ?", (int(user_id),))

    flash("Verification submitted. Status is now pending admin approval.", "info")
    return redirect(url_for("user.pending"))

@bp.get("/change-password")
@login_required
def change_password_get():
    return render_template("change_password.html")


@bp.post("/change-password")
@login_required
def change_password_post():
    user_id = session["user_id"]
    old_pw = request.form.get("old_password", "")
    new_pw = request.form.get("new_password", "")
    confirm = request.form.get("confirm_password", "")
    if not new_pw or len(new_pw) < 6:
        flash("New password must be at least 6 characters.", "error")
        return redirect(request.referrer or url_for("user.profile_get"))
    if new_pw != confirm:
        flash("Passwords do not match.", "error")
        return redirect(request.referrer or url_for("user.profile_get"))
    ok, msg = change_password(user_id, old_pw, new_pw)
    if not ok:
        flash(msg, "error")
        return redirect(request.referrer or url_for("user.profile_get"))
    flash("Password updated.", "info")
    return redirect(url_for("user.profile_get"))
    # Go to the correct role homepage
    role = session.get("role")
    if role == "TECHNICIAN":
        return redirect(url_for("technician.homepage_page"))
    if role == "BUSINESS":
        return redirect(url_for("business.homepage_page"))
    if role == "ADMIN":
        return redirect(url_for("admin.homepage"))
    return redirect(url_for("auth.login_get"))


@bp.post("/technician/skills/submit")
@login_required
@verification_required
@role_required("TECHNICIAN")
def technician_skill_submit_post():
    user_id = session["user_id"]
    skill_name = request.form.get("skill_name", "").strip()
    files = request.files.getlist("cert_docs")
    try:
        skill_id = create_skill_request(user_id=user_id, skill_name=skill_name)
        attach_skill_documents(skill_item_id=skill_id, files=files, upload_dir=current_app.config["UPLOAD_FOLDER"])
    except Exception as e:
        flash(str(e), "error")
        return redirect(url_for("user.profile_get"))
    flash("Skill submitted for admin approval.", "info")
    return redirect(url_for("user.profile_get"))
