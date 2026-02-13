import re

_NAME_RE = re.compile(r"^[A-Za-z\s\-\']+$")

def validate_name(name: str):
    if not name or len(name.strip()) < 2 or len(name.strip()) > 60:
        return False, "Name must be 2-60 characters."
    if not any(c.isalpha() for c in name):
        return False, "Name must contain at least one letter."
    if not _NAME_RE.match(name.strip()):
        return False, "Name contains invalid characters."
    return True, None

def validate_email(email: str):
    if not email:
        return False, "Email is required."
    email = email.strip()
    # simple format check
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        return False, "Invalid email format."
    return True, None

def validate_password(password: str):
    if not password or len(password) < 6:
        return False, "Password must be at least 6 characters."
    return True, None

def validate_registration_identifier(reg: str):
    if not reg or len(reg.strip()) < 4 or len(reg.strip()) > 40:
        return False, "Registration identifier must be 4-40 characters."
    # format-checked (light)
    if not re.match(r"^[A-Za-z0-9\-\/]+$", reg.strip()):
        return False, "Registration identifier contains invalid characters."
    return True, None
