from flask import Blueprint, render_template, session

from ..auth.decorators import login_required, role_required, verification_required
from ..services.notification_service import list_notifications


bp = Blueprint("business", __name__, url_prefix="/business")


@bp.get("/homepage")
@login_required
@role_required("BUSINESS")
@verification_required
def homepage_page():
    """Business homepage (role-split).

    UI details are owned by the homepage teammate; this route only enforces
    access control + provides a stable endpoint.
    """
    user_id = session["user_id"]
    notes = list_notifications(user_id, unread_only=True)
    return render_template("business/homepage.html", unread_notifications=notes)

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
