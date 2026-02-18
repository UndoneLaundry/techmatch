from __future__ import annotations

from ..extensions import db
from ..models import Payment, PaymentStatus, Job, JobStatus, Feedback, TechnicianProfile, Notification, NotificationType
from ..utils import utcnow

class DomainError(Exception):
    pass

def get_payment_for_job(job_id: int) -> Payment | None:
    return Payment.query.filter_by(job_id=job_id).first()

def business_pay_for_job(*, job_id: int, business_id: int, hourly_rate_final: int, hours_billed: float) -> Payment:
    job = Job.query.get(job_id)
    if not job or job.business_id != business_id:
        raise DomainError("Job not found.")
    if job.status != JobStatus.COMPLETED.value:
        raise DomainError("Payment is only allowed after job completion confirmation.")
    pay = get_payment_for_job(job_id)
    if not pay:
        raise DomainError("Payment record not found.")
    if pay.status == PaymentStatus.PAID.value:
        raise DomainError("Job is already paid.")

    if hourly_rate_final < job.hourly_rate_min or hourly_rate_final > job.hourly_rate_max:
        raise DomainError("Final hourly rate must be within the agreed range.")
    if hours_billed <= 0:
        raise DomainError("Hours billed must be positive.")

    pay.hourly_rate_final = int(hourly_rate_final)
    pay.hours_billed = float(hours_billed)
    pay.amount_total = int(round(pay.hourly_rate_final * pay.hours_billed))
    pay.status = PaymentStatus.PAID.value
    pay.paid_at = utcnow()

    db.session.add(Notification(
        user_id=pay.technician_id,
        ntype=NotificationType.PAYMENT.value,
        title="Payment received",
        message=f"Payment for job #{job.id} has been completed.",
    ))
    db.session.commit()
    return pay

def business_leave_feedback(*, job_id: int, business_id: int, rating: int, comment: str | None) -> Feedback:
    job = Job.query.get(job_id)
    if not job or job.business_id != business_id:
        raise DomainError("Job not found.")
    pay = get_payment_for_job(job_id)
    if not pay or pay.status != PaymentStatus.PAID.value:
        raise DomainError("Feedback is only allowed after payment is completed.")

    if rating < 1 or rating > 5:
        raise DomainError("Rating must be between 1 and 5.")
    existing = Feedback.query.filter_by(job_id=job_id).first()
    if existing:
        raise DomainError("Feedback already submitted for this job.")

    fb = Feedback(
        job_id=job_id,
        business_id=business_id,
        technician_id=pay.technician_id,
        rating=int(rating),
        comment=(comment or "").strip() or None,
    )
    db.session.add(fb)

    # update technician cached rating
    prof = TechnicianProfile.query.filter_by(user_id=pay.technician_id).first()
    if prof:
        total = prof.average_rating * prof.review_count
        prof.review_count += 1
        prof.average_rating = (total + fb.rating) / prof.review_count

    db.session.add(Notification(
        user_id=pay.technician_id,
        ntype=NotificationType.FEEDBACK.value,
        title="New feedback received",
        message=f"You received a {fb.rating}/5 rating for job #{job.id}.",
    ))
    db.session.commit()
    return fb
