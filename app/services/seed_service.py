from datetime import datetime
from .user_service import get_user_by_email, create_user

ADMIN_EMAIL = "admin@techmatch.com"
ADMIN_PASSWORD = "admin123"

def seed_admin_if_needed():
    existing = get_user_by_email(ADMIN_EMAIL)
    if existing:
        return

    admin = create_user(
        email=ADMIN_EMAIL,
        password=ADMIN_PASSWORD,
        role="ADMIN",
    )

    print("✅ Admin account created")
    print("   Email:", ADMIN_EMAIL)
    print("   Password:", ADMIN_PASSWORD)
