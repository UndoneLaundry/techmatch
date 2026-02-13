from flask import session

def login_user(user_row):
    session.clear()
    session["user_id"] = int(user_row["id"])
    session["role"] = user_row["role"]
    session["email"] = user_row.get("email") or user_row["email"]

def logout_user():
    session.clear()

def current_user_id():
    return session.get("user_id")

def current_user_role():
    return session.get("role")
    