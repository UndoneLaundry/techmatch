from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from ..services.user_service import get_user_by_email, verify_password, update_last_login
from ..services.verification_service import get_latest_request_for_user, is_cooldown_active_for_request
from ..auth.session import login_user, logout_user, current_user_role

bp = Blueprint("auth", __name__)

@bp.get("/login")
def login_get():
    # If already authenticated, never allow returning to public login page.
    if session.get("user_id"):
        if session.get("role") == "ADMIN":
            return redirect(url_for("admin.homepage"))
        return redirect(url_for("user.homepage"))
    return render_template("login.html")


@bp.post("/login")
def login_post():
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    user = get_user_by_email(email)

    if user is None or not verify_password(user, password):
        flash("Invalid credentials.", "error")
        return redirect(url_for("auth.login_get"))

    login_user(user)
    update_last_login(user["id"])

    # Force password change (used for agency/admin-created technician accounts)
    if int(user.get("force_password_change", 0)) == 1:
        return redirect(url_for("user.change_password_get"))

    if user["role"] == "ADMIN":
        return redirect(url_for("admin.homepage"))

    req = get_latest_request_for_user(user["id"])
    if req is None:
        return redirect(url_for("request.request_account_get"))

    if req["status"] == "APPROVED":
        # Split homepages by role (no generic /homepage)
        if user["role"] == "TECHNICIAN":
            return redirect(url_for("technician.homepage_page"))
        if user["role"] == "BUSINESS":
            return redirect(url_for("business.homepage_page"))
        # Fallback
        return redirect(url_for("user.homepage"))

    # REJECTED + cooldown is still routed to /pending, where the message is shown.
    return redirect(url_for("user.pending"))



@bp.post("/logout")
def logout():
    logout_user()
    return redirect(url_for("auth.login_get"))

@bp.route("/")
def landing():
    return redirect(url_for("request.request_account_get"))
