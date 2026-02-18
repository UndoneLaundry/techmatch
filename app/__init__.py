import os
from flask import Flask
from .db import init_app as init_db_app
from .services.seed_service import seed_admin_if_needed
from .services.user_service import get_user_by_id


def create_app():
    # Single-root project structure:
    # - templates/ and static/ live at the project root (one level above this package)
    app = Flask(
        __name__,
        instance_relative_config=True,
        template_folder="../templates",
        static_folder="../static",
    )
    app.config.from_object("config.Config")

    # Limit request body size for uploads
    app.config.setdefault(
        "MAX_CONTENT_LENGTH",
        int(app.config["MAX_FILE_SIZE_BYTES"]) * 2
    )


    # =========================
    # Ensure folders exist
    # =========================
    os.makedirs(os.path.dirname(app.config["DATABASE"]), exist_ok=True)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # =========================
    # Database
    # =========================
    init_db_app(app)

    # =========================
    # Seed admin user
    # =========================
    # NOTE: For validation packaging, do not auto-seed/modify DB on app startup.
    # The database and its records must remain untouched unless user actions occur.
    # If your project requires an admin account, ensure it already exists in instance/app.db.
    # with app.app_context():
    #     seed_admin_if_needed()

    # =========================
    # Cache-control (prevent navigating back to public pages while authenticated)
    # =========================
    from flask import session

    @app.after_request
    def _add_no_cache_headers(response):
        # Helps prevent accessing cached public pages via browser back button.
        if session.get("user_id"):
            response.headers.setdefault("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
            response.headers.setdefault("Pragma", "no-cache")
            response.headers.setdefault("Expires", "0")
        return response

    # =========================
    # Blueprints (lazy import)
    # =========================
    from .routes.auth_routes import bp as auth_bp
    from .routes.request_routes import bp as request_bp
    from .routes.user_routes import bp as user_bp
    from .routes.notification_routes import bp as notification_bp
    from .routes.skill_routes import bp as skill_bp
    from .routes.technician_routes import bp as technician_bp
    from .routes.business_routes import bp as business_bp
    from .routes.admin_routes import bp as admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(request_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(notification_bp)
    app.register_blueprint(skill_bp)
    app.register_blueprint(technician_bp)
    app.register_blueprint(business_bp)
    app.register_blueprint(admin_bp)

    return app
