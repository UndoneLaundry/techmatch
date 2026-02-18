import time, json
from ..db import get_db

def create_technician_profile(user_id: int, full_name: str, skills_list, bio: str | None):
    db = get_db()
    now = int(time.time())
    db.execute(
        "INSERT INTO technician_profiles (user_id, full_name, skills_json, bio, created_at) VALUES (?,?,?,?,?)",
        (int(user_id), full_name.strip(), json.dumps(skills_list), bio, now),
    )
    db.commit()

def create_business_profile(user_id: int, company_name: str, registration_identifier: str):
    db = get_db()
    now = int(time.time())
    db.execute(
        "INSERT INTO business_profiles (user_id, company_name, registration_identifier, created_at) VALUES (?,?,?,?)",
        (int(user_id), company_name.strip(), registration_identifier.strip(), now),
    )
    db.commit()

def get_technician_profile(user_id: int):
    db = get_db()
    return db.execute("SELECT * FROM technician_profiles WHERE user_id = ?", (int(user_id),)).fetchone()

def get_business_profile(user_id: int):
    db = get_db()
    return db.execute("SELECT * FROM business_profiles WHERE user_id = ?", (int(user_id),)).fetchone()


def update_technician_profile(user_id: int, full_name: str, bio: str | None):
    db = get_db()
    db.execute(
        "UPDATE technician_profiles SET full_name = ?, bio = ? WHERE user_id = ?",
        (full_name.strip(), bio, int(user_id)),
    )
    db.commit()


def update_business_profile(user_id: int, company_name: str, registration_identifier: str):
    db = get_db()
    db.execute(
        "UPDATE business_profiles SET company_name = ?, registration_identifier = ? WHERE user_id = ?",
        (company_name.strip(), registration_identifier.strip(), int(user_id)),
    )
    db.commit()
