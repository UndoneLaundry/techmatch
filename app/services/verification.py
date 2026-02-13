from __future__ import annotations

from datetime import timedelta
from flask import current_app

from ..extensions import db
from ..models import (
    User, VerificationRequest, VerificationStatus, UploadedDocument,
    Notification, NotificationType, AdminAction
)
from ..utils import utcnow

class DomainError(Exception):
    pass

def cooldown_hours() -> int:
    return int(current_app.config.get("VERIFICATION_COOLDOWN_HOURS", 24))

def get_latest_request(user_id: int) -> VerificationRequest | None:
    return VerificationRequest.query.filter_by(user_id=user_id).order_by(VerificationRequest.created_at.desc()).first()

def can_submit_new_request(user_id: int) -> tuple[bool, str | None]:
    vr = get_latest_request(user_id)
    if not vr:
        return True, None

    if vr.status in [VerificationStatus.DRAFT.value, VerificationStatus.PENDING.value]:
        return False, "You already have an active verification request."

    if vr.status == VerificationStatus.APPROVED.value:
        return False, "Your account is already verified."

    if vr.status == VerificationStatus.REJECTED.value:
        until = vr.cooldown_until(cooldown_hours())
        if until and utcnow() < until:
            remaining = until - utcnow()
            hours = int(remaining.total_seconds() // 3600) + 1
            return False, f"Please wait {hours} hour(s) before reapplying."
        # after cooldown, allow creating a new request
        return True, None

    return True, None

def create_draft_request(user_id: int) -> VerificationRequest:
    allowed, reason = can_submit_new_request(user_id)
    if not allowed:
        raise DomainError(reason or "Cannot create request.")
    vr = VerificationRequest(user_id=user_id, status=VerificationStatus.DRAFT.value)
    db.session.add(vr)
    db.session.commit()
    return vr

def attach_document(*, verification_request_id: int, doc_type: str, filename: str, storage_path: str):
    vr = VerificationRequest.query.get(verification_request_id)
    if not vr or vr.status != VerificationStatus.DRAFT.value:
        raise DomainError("Documents can only be attached in DRAFT.")
    doc = UploadedDocument(
        verification_request_id=verification_request_id,
        doc_type=doc_type,
        filename=filename,
        storage_path=storage_path,
    )
    db.session.add(doc)
    db.session.commit()

def submit_request(user_id: int, verification_request_id: int):
    vr = VerificationRequest.query.get(verification_request_id)
    if not vr or vr.user_id != user_id:
        raise DomainError("Request not found.")
    if vr.status != VerificationStatus.DRAFT.value:
        raise DomainError("Only DRAFT requests can be submitted.")

    docs = UploadedDocument.query.filter_by(verification_request_id=verification_request_id).count()
    if docs == 0:
        raise DomainError("Please upload at least one document before submitting.")

    vr.status = VerificationStatus.PENDING.value
    vr.submitted_at = utcnow()

    db.session.add(Notification(
        user_id=user_id,
        ntype=NotificationType.VERIFICATION.value,
        title="Verification submitted",
        message="Your verification request has been submitted and is pending admin review.",
    ))
    db.session.commit()

def admin_list_pending():
    return VerificationRequest.query.filter_by(status=VerificationStatus.PENDING.value).order_by(VerificationRequest.submitted_at.asc()).all()

def admin_approve(*, admin_id: int, verification_request_id: int):
    vr = VerificationRequest.query.get(verification_request_id)
    if not vr or vr.status != VerificationStatus.PENDING.value:
        raise DomainError("Request not found or not pending.")
    vr.status = VerificationStatus.APPROVED.value
    vr.reviewed_at = utcnow()
    vr.reviewed_by_admin_id = admin_id

    user = User.query.get(vr.user_id)
    if user:
        user.is_verified = True

    db.session.add(AdminAction(
        admin_id=admin_id,
        action_type="VERIFY_APPROVE",
        target_type="VerificationRequest",
        target_id=vr.id,
        details=None,
    ))

    db.session.add(Notification(
        user_id=vr.user_id,
        ntype=NotificationType.VERIFICATION.value,
        title="Verification approved",
        message="Your account has been verified. You can now access all features.",
    ))
    db.session.commit()

def admin_reject(*, admin_id: int, verification_request_id: int, reason: str):
    vr = VerificationRequest.query.get(verification_request_id)
    if not vr or vr.status != VerificationStatus.PENDING.value:
        raise DomainError("Request not found or not pending.")
    vr.status = VerificationStatus.REJECTED.value
    vr.reviewed_at = utcnow()
    vr.reviewed_by_admin_id = admin_id
    vr.rejected_at = utcnow()
    vr.rejection_reason = (reason or "").strip()[:500] or "No reason provided."

    db.session.add(AdminAction(
        admin_id=admin_id,
        action_type="VERIFY_REJECT",
        target_type="VerificationRequest",
        target_id=vr.id,
        details=vr.rejection_reason,
    ))

    db.session.add(Notification(
        user_id=vr.user_id,
        ntype=NotificationType.VERIFICATION.value,
        title="Verification rejected",
        message="Your verification request was rejected. Please review the reason and reapply after the cooldown period.",
    ))
    db.session.commit()
