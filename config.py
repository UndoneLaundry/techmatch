import os

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    DATABASE = os.environ.get("DATABASE", os.path.join(os.getcwd(), "instance", "app.db"))

    UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", os.path.join(os.getcwd(), "app", "uploads"))
    ALLOWED_EXTENSIONS = {".pdf", ".docx"}
    # Default to 15MB to reduce false failures during local testing.
    MAX_FILE_SIZE_BYTES = int(os.environ.get("MAX_FILE_SIZE_BYTES", str(15 * 1024 * 1024)))

    # Cooldown duration after REJECTED
    COOLDOWN_DURATION_SECONDS = int(os.environ.get("COOLDOWN_DURATION_SECONDS", str(24 * 60 * 60)))  # 24h

    # Admin seed (for local demo)
    ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@techmatch.com")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Admin123")
