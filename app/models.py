from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum

from werkzeug.security import generate_password_hash, check_password_hash
from .utils import utcnow

class Role(str, Enum):
    ADMIN = "ADMIN"
    TECHNICIAN = "TECHNICIAN"
    BUSINESS = "BUSINESS"

class VerificationStatus(str, Enum):
    DRAFT = "DRAFT"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

class JobStatus(str, Enum):
    DRAFT = "DRAFT"
    OUTGOING = "OUTGOING"          # posted & accepting applications
    APPROVAL_PENDING = "APPROVAL_PENDING"  # business reviewing applicants
    ACTIVE = "ACTIVE"
    PENDING_CONFIRMATION = "PENDING_CONFIRMATION"  # technician says done, business to confirm
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"

class ApplicationStatus(str, Enum):
    APPLIED = "APPLIED"
    WITHDRAWN = "WITHDRAWN"
    APPROVED = "APPROVED"
    DENIED = "DENIED"

class PaymentStatus(str, Enum):
    UNPAID = "UNPAID"
    AUTHORIZED = "AUTHORIZED"   # reserved (conceptual)
    PAID = "PAID"

class NotificationType(str, Enum):
    SYSTEM = "SYSTEM"
    VERIFICATION = "VERIFICATION"
    JOB = "JOB"
    PAYMENT = "PAYMENT"
    FEEDBACK = "FEEDBACK"

class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(32), nullable=False, index=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_verified = db.Column(db.Boolean, default=False, nullable=False)  # for TECHNICIAN/BUSINESS
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    last_login_at = db.Column(db.DateTime, nullable=True)

    technician_profile = db.relationship("TechnicianProfile", uselist=False, back_populates="user")
    business_profile = db.relationship("BusinessProfile", uselist=False, back_populates="user")

    def set_password(self, raw: str):
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw: str) -> bool:
        return check_password_hash(self.password_hash, raw)

    def is_admin(self) -> bool:
        return self.role == Role.ADMIN.value

    def is_technician(self) -> bool:
        return self.role == Role.TECHNICIAN.value

    def is_business(self) -> bool:
        return self.role == Role.BUSINESS.value

class TechnicianProfile(db.Model):
    __tablename__ = "technician_profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)

    display_name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(40), nullable=True)
    skills = db.Column(db.String(500), nullable=True)  # comma-separated for demo
    bio = db.Column(db.String(1000), nullable=True)

    average_rating = db.Column(db.Float, default=0.0, nullable=False)
    review_count = db.Column(db.Integer, default=0, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    user = db.relationship("User", back_populates="technician_profile")

class BusinessProfile(db.Model):
    __tablename__ = "business_profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)

    company_name = db.Column(db.String(200), nullable=False)
    contact_name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(40), nullable=True)
    address = db.Column(db.String(300), nullable=True)

    user = db.relationship("User", back_populates="business_profile")

class VerificationRequest(db.Model):
    __tablename__ = "verification_requests"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    status = db.Column(db.String(32), nullable=False, default=VerificationStatus.DRAFT.value, index=True)

    submitted_at = db.Column(db.DateTime, nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    reviewed_by_admin_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    rejection_reason = db.Column(db.String(500), nullable=True)
    rejected_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    user = db.relationship("User", foreign_keys=[user_id])
    reviewed_by = db.relationship("User", foreign_keys=[reviewed_by_admin_id])

    def cooldown_until(self, cooldown_hours: int) -> datetime | None:
        if self.status != VerificationStatus.REJECTED.value or not self.rejected_at:
            return None
        return self.rejected_at + timedelta(hours=cooldown_hours)

class UploadedDocument(db.Model):
    __tablename__ = "uploaded_documents"

    id = db.Column(db.Integer, primary_key=True)
    verification_request_id = db.Column(db.Integer, db.ForeignKey("verification_requests.id"), nullable=False, index=True)

    doc_type = db.Column(db.String(80), nullable=False)  # e.g. ID_FRONT, BIZ_REG
    filename = db.Column(db.String(255), nullable=False)
    storage_path = db.Column(db.String(500), nullable=False)  # for demo: local path
    uploaded_at = db.Column(db.DateTime, default=utcnow, nullable=False)

class VerificationFlag(db.Model):
    __tablename__ = "verification_flags"

    id = db.Column(db.Integer, primary_key=True)
    verification_request_id = db.Column(db.Integer, db.ForeignKey("verification_requests.id"), nullable=False, index=True)
    flag_type = db.Column(db.String(80), nullable=False)  # e.g. DUPLICATE_EMAIL, INCONSISTENT_NAME
    details = db.Column(db.String(800), nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

class Job(db.Model):
    __tablename__ = "jobs"

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.String(2000), nullable=False)
    service_category = db.Column(db.String(120), nullable=False)
    hourly_rate_min = db.Column(db.Integer, nullable=False)
    hourly_rate_max = db.Column(db.Integer, nullable=False)
    location = db.Column(db.String(200), nullable=True)

    status = db.Column(db.String(40), nullable=False, default=JobStatus.OUTGOING.value, index=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    assigned_technician_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)

    business = db.relationship("User", foreign_keys=[business_id])
    assigned_technician = db.relationship("User", foreign_keys=[assigned_technician_id])

class JobApplication(db.Model):
    __tablename__ = "job_applications"

    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey("jobs.id"), nullable=False, index=True)
    technician_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    status = db.Column(db.String(40), nullable=False, default=ApplicationStatus.APPLIED.value, index=True)
    applied_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    job = db.relationship("Job")
    technician = db.relationship("User")

    __table_args__ = (
        db.UniqueConstraint("job_id", "technician_id", name="uq_job_technician_one_application"),
    )

class JobTask(db.Model):
    __tablename__ = "job_tasks"

    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey("jobs.id"), nullable=False, index=True)

    title = db.Column(db.String(200), nullable=False)
    is_completed = db.Column(db.Boolean, default=False, nullable=False)
    completed_at = db.Column(db.DateTime, nullable=True)

    job = db.relationship("Job")

class Payment(db.Model):
    __tablename__ = "payments"

    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey("jobs.id"), unique=True, nullable=False)

    business_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    technician_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    status = db.Column(db.String(40), nullable=False, default=PaymentStatus.UNPAID.value, index=True)
    hourly_rate_final = db.Column(db.Integer, nullable=True)  # locked on completion/payment
    hours_billed = db.Column(db.Float, nullable=True)
    amount_total = db.Column(db.Integer, nullable=True)  # cents for real apps, dollars for demo

    paid_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    job = db.relationship("Job")
    business = db.relationship("User", foreign_keys=[business_id])
    technician = db.relationship("User", foreign_keys=[technician_id])

class Feedback(db.Model):
    __tablename__ = "feedback"

    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey("jobs.id"), unique=True, nullable=False)

    business_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    technician_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    rating = db.Column(db.Integer, nullable=False)  # 1..5
    comment = db.Column(db.String(1200), nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    ntype = db.Column(db.String(40), nullable=False, default=NotificationType.SYSTEM.value, index=True)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.String(1200), nullable=False)
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

class AdminAction(db.Model):
    __tablename__ = "admin_actions"

    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    action_type = db.Column(db.String(80), nullable=False)  # e.g. VERIFY_APPROVE, JOB_FORCE_CANCEL
    target_type = db.Column(db.String(80), nullable=False)  # e.g. VerificationRequest
    target_id = db.Column(db.Integer, nullable=False)
    details = db.Column(db.String(1200), nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
