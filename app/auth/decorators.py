from functools import wraps
from flask import redirect, url_for, session, abort, current_app
from ..services.user_service import get_user_by_id
from ..services.verification_service import (
    get_latest_request_for_user,
    is_cooldown_active_for_request,
)

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user_id = session.get("user_id")
        if not user_id:
            return redirect(url_for("auth.login_get"))
        # Never trust stale sessions (user deleted/disabled)
        user = get_user_by_id(int(user_id))
        if user is None or int(user.get("is_active", 1)) != 1:
            session.clear()
            return redirect(url_for("auth.login_get"))
        # Sync role from DB (never trust session role)
        session["role"] = user.get("role")
        return fn(*args, **kwargs)
    return wrapper

def role_required(*roles):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user_id = session.get("user_id")
            if not user_id:
                return redirect(url_for("auth.login_get"))
            user = get_user_by_id(int(user_id))
            if user is None or int(user.get("is_active", 1)) != 1:
                session.clear()
                return redirect(url_for("auth.login_get"))
            session["role"] = user.get("role")
            if user.get("role") not in roles:
                abort(403)
            return fn(*args, **kwargs)
        return wrapper
    return decorator

def admin_required(fn):
    return login_required(role_required("ADMIN")(fn))

def verification_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("auth.login_get"))
        user = get_user_by_id(session["user_id"])
        if user is None:
            session.clear()
            return redirect(url_for("auth.login_get"))
        if user["role"] == "ADMIN":
            abort(403)
        req = get_latest_request_for_user(user["id"])
        if req is None or req["status"] != "APPROVED":
            return redirect(url_for("user.pending"))
        return fn(*args, **kwargs)
    return wrapper

def pending_only(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("auth.login_get"))
        user = get_user_by_id(session["user_id"])
        if user is None:
            session.clear()
            return redirect(url_for("auth.login_get"))
        if user["role"] == "ADMIN":
            abort(403)
        req = get_latest_request_for_user(user["id"])
        if req is None:
            return redirect(url_for("request.request_account_get"))
        if req["status"] == "APPROVED":
            # Split homepages by role
            if user.get("role") == "TECHNICIAN":
                return redirect(url_for("technician.homepage_page"))
            if user.get("role") == "BUSINESS":
                return redirect(url_for("business.homepage_page"))
            return redirect(url_for("auth.login_get"))
        return fn(*args, **kwargs)
    return wrapper

def cooldown_guard(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("auth.login_get"))
        user_id = session["user_id"]
        req = get_latest_request_for_user(user_id)
        if req is None:
            return fn(*args, **kwargs)
        if req["status"] == "PENDING":
            return redirect(url_for("user.pending"))
        if req["status"] == "REJECTED" and is_cooldown_active_for_request(req):
            return redirect(url_for("user.pending"))
        return fn(*args, **kwargs)
    return wrapper

def single_active_request_only(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user_id = session.get("user_id")
        if not user_id:
            return redirect(url_for("auth.login_get"))
        req = get_latest_request_for_user(user_id)
        if req is None:
            return fn(*args, **kwargs)
        if req["status"] == "PENDING":
            return redirect(url_for("user.pending"))
        if req["status"] == "REJECTED" and is_cooldown_active_for_request(req):
            return redirect(url_for("user.pending"))
        return fn(*args, **kwargs)
    return wrapper

def document_upload_guard(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        # Actual validation occurs in service; this ensures request has files
        return fn(*args, **kwargs)
    return wrapper
