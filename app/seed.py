from .extensions import db
from .models import User, Role, TechnicianProfile, BusinessProfile, Notification

def seed_if_empty():
    if User.query.first():
        return

    # Demo admin
    admin = User(email="admin@techmatch.local", role=Role.ADMIN.value, is_verified=True)
    admin.set_password("admin1234")

    # Demo business
    biz = User(email="business@techmatch.local", role=Role.BUSINESS.value, is_verified=False)
    biz.set_password("business1234")
    biz_profile = BusinessProfile(user=biz, company_name="Acme Office Supplies", contact_name="Alex Tan", phone="9123 4567", address="Singapore")

    # Demo tech
    tech = User(email="tech@techmatch.local", role=Role.TECHNICIAN.value, is_verified=False)
    tech.set_password("tech1234")
    tech_profile = TechnicianProfile(user=tech, display_name="Jordan Lim", skills="printers,laptops,networking", bio="Freelance IT technician.")

    db.session.add_all([admin, biz, tech, biz_profile, tech_profile])
    db.session.commit()

    db.session.add(Notification(user_id=biz.id, title="Welcome to TechMatch", message="Create your first job request to get started!"))
    db.session.add(Notification(user_id=tech.id, title="Welcome to TechMatch", message="Complete verification to unlock job signups."))
    db.session.commit()
