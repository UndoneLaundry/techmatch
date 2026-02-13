from __future__ import annotations

from typing import List, Dict

from ..models import Job, JobStatus, TechnicianProfile
from ..extensions import db

def recommend_jobs_for_technician(technician_id: int, limit: int = 8) -> List[Dict]:
    """
    Simple rule-based recommender (matches your PDF intent, without ML):
    - Pull technician skills (comma-separated)
    - Score jobs by whether category keywords appear in skills/title/description
    - Return top jobs that are OUTGOING
    """
    prof = TechnicianProfile.query.filter_by(user_id=technician_id).first()
    skills = set()
    if prof and prof.skills:
        skills = {s.strip().lower() for s in prof.skills.split(",") if s.strip()}

    jobs = Job.query.filter_by(status=JobStatus.OUTGOING.value).order_by(Job.created_at.desc()).limit(50).all()

    def score(job: Job) -> int:
        text = f"{job.service_category} {job.title} {job.description}".lower()
        return sum(1 for s in skills if s and s in text)

    ranked = sorted(jobs, key=score, reverse=True)
    out = []
    for j in ranked[:limit]:
        out.append({
            "id": j.id,
            "title": j.title,
            "service_category": j.service_category,
            "hourly_rate_min": j.hourly_rate_min,
            "hourly_rate_max": j.hourly_rate_max,
            "location": j.location,
            "score": score(j),
        })
    return out
