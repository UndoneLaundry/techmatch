import json
from flask import Blueprint, render_template, request, redirect, url_for, flash, session

from ..auth.session import login_user
from ..services.validation_service import (
    validate_name,
    validate_email,
    validate_password,
    validate_registration_identifier,
)
from ..services.user_service import get_user_by_email, create_user
from ..services.profile_service import (
    create_technician_profile,
    create_business_profile,
)
from ..services.verification_service import (
    create_verification_request,
    attach_flag,
    get_latest_request_for_user,
    is_cooldown_active_for_request,
)
from ..services.document_service import save_uploaded_documents
from ..services.flag_service import (
    compute_common_flags,
    compute_technician_flags,
)

bp = Blueprint("request", __name__)

# =========================================================
# ROLE SELECTION
# =========================================================

@bp.get("/request-account")
def request_account_get():
    # While authenticated, users must not be able to access public pages.
    if session.get("user_id"):
        if session.get("role") == "ADMIN":
            return redirect(url_for("admin.homepage"))
        return redirect(url_for("user.homepage"))
    return render_template("request_account.html")


# =========================================================
# TECHNICIAN SIGNUP
# =========================================================

@bp.get("/request-account/technician")
def technician_signup_get():
    if session.get("user_id"):
        if session.get("role") == "ADMIN":
            return redirect(url_for("admin.homepage"))
        return redirect(url_for("user.homepage"))
    return render_template("technician_signup.html")


@bp.post("/request-account/technician")
def request_technician_post():
    full_name = request.form.get("full_name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    skills_raw = request.form.get("skills", "")
    bio = request.form.get("bio", "")

    ok, err = validate_name(full_name)
    if not ok:
        flash(err, "error")
        return redirect(url_for("request.request_account_get"))

    ok, err = validate_email(email)
    if not ok:
        flash(err, "error")
        return redirect(url_for("request.request_account_get"))

    ok, err = validate_password(password)
    if not ok:
        flash(err, "error")
        return redirect(url_for("request.request_account_get"))

    existing = get_user_by_email(email)
    if existing:
        # Enforce single active request + cooldown even for guests
        req = get_latest_request_for_user(existing["id"])
        if req and req["status"] == "PENDING":
            flash("This email already has a pending verification request. Please log in to view status.", "error")
            return redirect(url_for("auth.login_get"))
        if req and req["status"] == "REJECTED" and is_cooldown_active_for_request(req):
            flash("This email is on cooldown after a rejection. Please log in to view details.", "error")
            return redirect(url_for("auth.login_get"))
        flash("Email already exists. Please log in.", "error")
        return redirect(url_for("auth.login_get"))

    skills_list = [s.strip() for s in skills_raw.split(",") if s.strip()]
    if not skills_list:
        flash("At least one skill is required.", "error")
        return redirect(url_for("request.request_account_get"))

    user = create_user(email=email, password=password, role="TECHNICIAN")

    create_technician_profile(
        user_id=user["id"],
        full_name=full_name,
        skills_list=skills_list,
        bio=bio or None,
    )

    req_id = create_verification_request(
        user_id=user["id"],
        user_role="TECHNICIAN",
    )

    files = request.files.getlist("cert_docs")
    try:
        save_uploaded_documents(
            files,
            verification_request_id=req_id,
            uploaded_by_user_id=user["id"],
            document_type="CERTIFICATION",
        )
    except ValueError as e:
        flash(str(e), "error")
        # Leave the account created, but keep the user on the signup page
        # so they can retry with a smaller file.
        return redirect(url_for("request.technician_signup_get"))

    for ft, sev, desc in compute_common_flags(full_name):
        attach_flag(req_id, ft, sev, desc)
    for ft, sev, desc in compute_technician_flags(skills_list):
        attach_flag(req_id, ft, sev, desc)

    login_user(user)
    flash("Account created. Verification is pending admin approval.", "info")
    return redirect(url_for("user.pending"))


# =========================================================
# BUSINESS SIGNUP
# =========================================================

@bp.get("/request-account/business")
def business_signup_get():
    if session.get("user_id"):
        if session.get("role") == "ADMIN":
            return redirect(url_for("admin.homepage"))
        return redirect(url_for("user.homepage"))
    return render_template("business_signup.html")


@bp.post("/request-account/business")
def request_business_post():
    company_name = request.form.get("company_name", "").strip()
    registration_identifier = request.form.get("registration_identifier", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    if not company_name:
        flash("Company name is required.", "error")
        return redirect(url_for("request.request_account_get"))

    ok, err = validate_registration_identifier(registration_identifier)
    if not ok:
        flash(err, "error")
        return redirect(url_for("request.request_account_get"))

    ok, err = validate_email(email)
    if not ok:
        flash(err, "error")
        return redirect(url_for("request.request_account_get"))

    ok, err = validate_password(password)
    if not ok:
        flash(err, "error")
        return redirect(url_for("request.request_account_get"))

    existing = get_user_by_email(email)
    if existing:
        req = get_latest_request_for_user(existing["id"])
        if req and req["status"] == "PENDING":
            flash("This email already has a pending verification request. Please log in to view status.", "error")
            return redirect(url_for("auth.login_get"))
        if req and req["status"] == "REJECTED" and is_cooldown_active_for_request(req):
            flash("This email is on cooldown after a rejection. Please log in to view details.", "error")
            return redirect(url_for("auth.login_get"))
        flash("Email already exists. Please log in.", "error")
        return redirect(url_for("auth.login_get"))

    user = create_user(email=email, password=password, role="BUSINESS")

    create_business_profile(
        user_id=user["id"],
        company_name=company_name,
        registration_identifier=registration_identifier,
    )

    req_id = create_verification_request(
        user_id=user["id"],
        user_role="BUSINESS",
    )

    files = request.files.getlist("support_docs")
    try:
        save_uploaded_documents(
            files,
            verification_request_id=req_id,
            uploaded_by_user_id=user["id"],
            document_type="BUSINESS_SUPPORT",
        )
    except ValueError as e:
        flash(str(e), "error")
        return redirect(url_for("request.business_signup_get"))

    for ft, sev, desc in compute_common_flags(company_name):
        attach_flag(req_id, ft, sev, desc)

    login_user(user)
    flash("Account created. Verification is pending admin approval.", "info")
    return redirect(url_for("user.pending"))
