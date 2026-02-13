import difflib

# =========================
# CANONICAL SKILL LIST
# =========================
CANONICAL_SKILLS = [
    "Plumbing",
    "Electrical Wiring",
    "Router Configuration",
    "Printer Repair",
    "Network Troubleshooting",
    "Aircon Servicing",
    "CCTV Installation",
    "Server Maintenance",
    "Cable Termination",
    "Switch Configuration",
]

# =========================
# Skill suggestion logic
# =========================
def suggest_skills(query: str, limit: int = 6):
    query = (query or "").strip().lower()

    scored = []
    for skill in CANONICAL_SKILLS:
        score = difflib.SequenceMatcher(
            None,
            query,
            skill.lower()
        ).ratio()
        scored.append((score, skill))

    # sort by similarity DESC
    scored.sort(key=lambda x: x[0], reverse=True)

    # 🔒 ALWAYS return suggestions (even if query is nonsense)
    return [skill for _, skill in scored[:limit]]


def is_canonical(skill: str) -> bool:
    return skill in CANONICAL_SKILLS
