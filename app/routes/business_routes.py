from flask import Blueprint, render_template, session, request, abort, jsonify, redirect, url_for, flash
from ..auth.decorators import login_required, role_required, verification_required
from ..services.notification_service import list_notifications
from ..services.jobs import (
    create_job as create_job_service,
    get_job_stats_for_business,
    get_jobs_by_business,
    get_job_details_for_business,
    add_job_task,
    delete_job as delete_job_service,
    delete_task as delete_task_service,
    approve_job_completion,
    get_applications_for_job,
    approve_application,
    deny_application,
)

bp = Blueprint("business", __name__, url_prefix="/business")


# ======================================================
# Existing endpoints (kept as-is)
# ======================================================

@bp.get("/homepage")
@login_required
@role_required("BUSINESS")
@verification_required
def homepage_page():
    """Business homepage (role-split)."""
    user_id = session["user_id"]
    notes = list_notifications(user_id, unread_only=True)
    stats = get_job_stats_for_business(user_id)
    return render_template("business/homepage.html", unread_notifications=notes, stats=stats)


@bp.get("/profile")
@login_required
@role_required("BUSINESS")
def view_profile():
    from app.services.profile_service import get_business_profile
    profile = get_business_profile(session["user_id"])
    return render_template("business/profile_view.html", profile=profile)


@bp.get("/profile/preview")
@login_required
@role_required("BUSINESS")
def profile_preview():
    from app.services.profile_service import get_business_profile
    from app.services.document_service import list_my_verification_docs
    profile = get_business_profile(session["user_id"])
    ver_docs = list_my_verification_docs(session["user_id"])
    return render_template("business/profile_preview.html", profile=profile, ver_docs=ver_docs)


@bp.get("/certs/<int:doc_id>/download")
@login_required
@role_required("BUSINESS")
def download_own_cert(doc_id):
    from app.services.document_service import download_my_verification_doc
    return download_my_verification_doc(session["user_id"], doc_id)


# ======================================================
# NEW BUSINESS JOB MANAGEMENT ENDPOINTS
# ======================================================

@bp.get("/dashboard")
@login_required
@role_required("BUSINESS")
@verification_required
def dashboard():
    """Business dashboard with job statistics and quick actions."""
    user_id = session["user_id"]
    stats = get_job_stats_for_business(user_id)
    return render_template("business/dashboard.html", stats=stats)


@bp.get("/jobs")
@login_required
@role_required("BUSINESS")
@verification_required
def list_jobs():
    """List all jobs created by this business, optionally filtered by status."""
    user_id = session["user_id"]
    status = request.args.get("status")
    jobs = get_jobs_by_business(user_id, status)
    return render_template("business/jobs.html", jobs=jobs, current_filter=status)


@bp.get("/jobs/<int:job_id>")
@login_required
@role_required("BUSINESS")
@verification_required
def job_detail(job_id):
    """Show job details with its tasks and approve button if pending confirmation."""
    user_id = session["user_id"]
    job = get_job_details_for_business(job_id, user_id)
    if job is None:
        abort(404)
    return render_template("business/job_detail.html", job=job)


@bp.route("/jobs/create", methods=["GET", "POST"])
@login_required
@role_required("BUSINESS")
@verification_required
def create_job():
    """Display form (GET) and handle job creation (POST)."""
    if request.method == "GET":
        from app.services.skill_suggest_service import CANONICAL_SKILLS
        return render_template("business/create_job.html", categories=CANONICAL_SKILLS)

    # POST: create the job
    user_id = session["user_id"]
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    category = request.form.get("service_category", "").strip()
    rate_min = request.form.get("hourly_rate_min", type=int)
    rate_max = request.form.get("hourly_rate_max", type=int)
    location = request.form.get("location", "").strip() or None

    # Parse estimated_duration as days; convert to start/end using epoch 0 as anchor
    estimated_days = request.form.get("estimated_duration", type=int)
    start_date = None
    end_date = None
    if estimated_days and estimated_days > 0:
        start_date = 0
        end_date = estimated_days * 86400

    if not all([title, description, category, rate_min, rate_max]):
        flash("All fields except location are required.", "error")
        return redirect(url_for("business.create_job"))

    try:
        job_id = create_job_service(
            business_id=user_id,
            title=title,
            description=description,
            service_category=category,
            hourly_rate_min=rate_min,
            hourly_rate_max=rate_max,
            location=location,
            start_date=start_date,   # <-- new
            end_date=end_date         # <-- new
        )
        flash("Job created successfully. You can now add tasks.", "success")
        return redirect(url_for("business.job_detail", job_id=job_id))
    except Exception as e:
        flash(str(e), "error")
        return redirect(url_for("business.create_job"))


@bp.post("/jobs/<int:job_id>/tasks")
@login_required
@role_required("BUSINESS")
@verification_required
def add_task(job_id):
    """Add a task to a job (AJAX or form post)."""
    user_id = session["user_id"]
    title = request.form.get("title", "").strip()
    if not title:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify(success=False, error="Task title required"), 400
        flash("Task title required.", "error")
        return redirect(url_for("business.job_detail", job_id=job_id))

    try:
        task_id = add_job_task(job_id, user_id, title)
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify(success=True, task_id=task_id)
        flash("Task added.", "success")
        return redirect(url_for("business.job_detail", job_id=job_id))
    except PermissionError:
        abort(403)
    except Exception as e:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify(success=False, error=str(e)), 400
        flash(str(e), "error")
        return redirect(url_for("business.job_detail", job_id=job_id))


@bp.post("/jobs/<int:job_id>/delete")
@login_required
@role_required("BUSINESS")
@verification_required
def delete_job(job_id):
    """Delete an OUTGOING job and redirect to jobs list."""
    user_id = session["user_id"]
    try:
        delete_job_service(job_id, user_id)
        flash("Job deleted.", "success")
        return redirect(url_for("business.list_jobs"))
    except PermissionError:
        abort(403)
    except ValueError as e:
        flash(str(e), "error")
        return redirect(url_for("business.job_detail", job_id=job_id))


@bp.post("/jobs/<int:job_id>/tasks/<int:task_id>/delete")
@login_required
@role_required("BUSINESS")
@verification_required
def delete_task(job_id, task_id):
    """Delete a single task from a job."""
    user_id = session["user_id"]
    try:
        delete_task_service(task_id, job_id, user_id)
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify(success=True)
        flash("Task deleted.", "success")
    except PermissionError:
        abort(403)
    except ValueError as e:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify(success=False, error=str(e)), 400
        flash(str(e), "error")
    return redirect(url_for("business.job_detail", job_id=job_id))


@bp.patch("/jobs/<int:job_id>/approve")
@login_required
@role_required("BUSINESS")
@verification_required
def approve_job(job_id):
    """Approve a completed job (move from PENDING_CONFIRMATION to COMPLETED)."""
    user_id = session["user_id"]
    try:
        approve_job_completion(job_id, user_id)
        return jsonify(success=True)
    except PermissionError:
        abort(403)
    except ValueError as e:
        return jsonify(success=False, error=str(e)), 400


@bp.get("/jobs/<int:job_id>/applications")
@login_required
@role_required("BUSINESS")
@verification_required
def list_applications(job_id):
    """Show all pending applications for a job (for approval)."""
    user_id = session["user_id"]
    try:
        applications = get_applications_for_job(job_id, user_id)
        job = get_job_details_for_business(job_id, user_id)
        return render_template("business/applications.html", job=job, applications=applications)
    except PermissionError:
        abort(403)
    except Exception as e:
        flash(str(e), "error")
        return redirect(url_for("business.list_jobs"))


@bp.post("/jobs/<int:job_id>/applications/<int:app_id>/approve")
@login_required
@role_required("BUSINESS")
@verification_required
def approve_application_route(job_id, app_id):
    """Approve a technician's application."""
    user_id = session["user_id"]
    try:
        approve_application(job_id, app_id, user_id)
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify(success=True)
        flash("Application approved. Job is now active.", "success")
        return redirect(url_for("business.job_detail", job_id=job_id))
    except (PermissionError, ValueError) as e:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify(success=False, error=str(e)), 400
        flash(str(e), "error")
        return redirect(url_for("business.job_detail", job_id=job_id))


@bp.post("/jobs/<int:job_id>/applications/<int:app_id>/deny")
@login_required
@role_required("BUSINESS")
@verification_required
def deny_application_route(job_id, app_id):
    """Deny a technician's application."""
    user_id = session["user_id"]
    try:
        deny_application(job_id, app_id, user_id)
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify(success=True)
        flash("Application denied.", "info")
        return redirect(url_for("business.job_detail", job_id=job_id))
    except (PermissionError, ValueError) as e:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify(success=False, error=str(e)), 400
        flash(str(e), "error")
        return redirect(url_for("business.job_detail", job_id=job_id))