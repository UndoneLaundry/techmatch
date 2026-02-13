from flask import Blueprint, jsonify, request, abort

from app.services.skill_suggest_service import (
    suggest_skills,
    is_canonical,
)

bp = Blueprint("skills", __name__)

@bp.get("/api/skills/suggest")
def skill_suggest():
    q = request.args.get("q", "").strip()
    suggestions = suggest_skills(q)
    return jsonify({"suggestions": suggestions})


@bp.post("/api/skills/add")
def add_skill():
    data = request.get_json() or {}
    skill = data.get("skill")

    if not is_canonical(skill):
        abort(400, "Skill must be a canonical skill")

    # TODO: save skill to DB
    return jsonify({"ok": True, "skill": skill})
