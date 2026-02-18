import sqlite3
from flask import current_app, g

SCHEMA_SQL = '''
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('ADMIN','TECHNICIAN','BUSINESS')),
    is_active INTEGER NOT NULL DEFAULT 1,
    -- derived from verification workflow; kept for quick gating & UI consistency
    is_verified INTEGER NOT NULL DEFAULT 0,
    -- used for agency/admin created technician accounts
    force_password_change INTEGER NOT NULL DEFAULT 0,
    password_changed_at INTEGER,
    created_at INTEGER NOT NULL,
    last_login_at INTEGER
);

CREATE TABLE IF NOT EXISTS technician_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    full_name TEXT NOT NULL,
    skills_json TEXT NOT NULL,
    bio TEXT,
    created_at INTEGER NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

-- =========================
-- TECHNICIAN SKILLS (PENDING/APPROVED)
-- =========================
CREATE TABLE IF NOT EXISTS technician_skill_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    skill_name TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('PENDING','APPROVED','REJECTED')),
    created_at INTEGER NOT NULL,
    reviewed_at INTEGER,
    reviewed_by_admin_id INTEGER,
    rejection_reason TEXT,
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(reviewed_by_admin_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS technician_skill_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_item_id INTEGER NOT NULL,
    original_filename TEXT NOT NULL,
    stored_filename TEXT NOT NULL,
    file_extension TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    uploaded_at INTEGER NOT NULL,
    FOREIGN KEY(skill_item_id) REFERENCES technician_skill_items(id)
);

CREATE TABLE IF NOT EXISTS business_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    company_name TEXT NOT NULL,
    registration_identifier TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS verification_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    user_role TEXT NOT NULL CHECK(user_role IN ('TECHNICIAN','BUSINESS')),
    status TEXT NOT NULL CHECK(status IN ('PENDING','APPROVED','REJECTED')),
    submitted_at INTEGER NOT NULL,
    reviewed_at INTEGER,
    reviewed_by_admin_id INTEGER,
    rejection_reason TEXT,
    rejected_at INTEGER,
    cooldown_until INTEGER,
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(reviewed_by_admin_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS verification_flags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    verification_request_id INTEGER NOT NULL,
    flag_type TEXT NOT NULL,
    severity TEXT NOT NULL CHECK(severity IN ('LOW','MEDIUM','HIGH')),
    description TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    FOREIGN KEY(verification_request_id) REFERENCES verification_requests(id)
);

CREATE TABLE IF NOT EXISTS uploaded_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    verification_request_id INTEGER NOT NULL,
    uploaded_by_user_id INTEGER NOT NULL,
    document_type TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    stored_filename TEXT NOT NULL,
    file_extension TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    uploaded_at INTEGER NOT NULL,
    FOREIGN KEY(verification_request_id) REFERENCES verification_requests(id),
    FOREIGN KEY(uploaded_by_user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    type TEXT NOT NULL,
    message TEXT NOT NULL,
    is_read INTEGER NOT NULL DEFAULT 0,
    created_at INTEGER NOT NULL,
    read_at INTEGER,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS admin_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_user_id INTEGER NOT NULL,
    action_type TEXT NOT NULL,
    target_verification_request_id INTEGER NOT NULL,
    timestamp INTEGER NOT NULL,
    notes TEXT,
    FOREIGN KEY(admin_user_id) REFERENCES users(id),
    FOREIGN KEY(target_verification_request_id) REFERENCES verification_requests(id)
);

-- =========================
-- JOBS
-- =========================
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    service_category TEXT NOT NULL,
    hourly_rate_min INTEGER NOT NULL,
    hourly_rate_max INTEGER NOT NULL,
    location TEXT,
    start_date INTEGER,                -- new (Unix timestamp)
    end_date INTEGER,                  -- new (Unix timestamp)
    status TEXT NOT NULL CHECK(
        status IN (
            'OUTGOING',
            'ACTIVE',
            'PENDING_CONFIRMATION',
            'COMPLETED',
            'CANCELLED'
        )
    ),
    assigned_technician_id INTEGER,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    FOREIGN KEY(business_id) REFERENCES users(id),
    FOREIGN KEY(assigned_technician_id) REFERENCES users(id)
);

-- =========================
-- JOB APPLICATIONS
-- =========================
CREATE TABLE IF NOT EXISTS job_applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    technician_id INTEGER NOT NULL,
    status TEXT NOT NULL CHECK(
        status IN (
            'APPLIED',
            'APPROVED',
            'DENIED',
            'WITHDRAWN'
        )
    ),
    applied_at INTEGER NOT NULL,
    FOREIGN KEY(job_id) REFERENCES jobs(id),
    FOREIGN KEY(technician_id) REFERENCES users(id)
);

-- =========================
-- JOB TASKS
-- =========================
CREATE TABLE IF NOT EXISTS job_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    is_completed INTEGER NOT NULL DEFAULT 0,
    completed_at INTEGER,
    created_at INTEGER NOT NULL,  -- Added for task creation timestamp
    FOREIGN KEY(job_id) REFERENCES jobs(id)
);
'''


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
    return g.db

def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def init_db():
    db = get_db()
    db.executescript(SCHEMA_SQL)
    _migrate(db)
    db.commit()


def _has_column(db, table: str, column: str) -> bool:
    row = db.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r[1] == column for r in row)


def _migrate(db):
    """Best-effort migrations for existing dev DBs.

    We avoid a full migration framework for this project and keep changes additive.
    """
    # users
    if not _has_column(db, "users", "is_verified"):
        db.execute("ALTER TABLE users ADD COLUMN is_verified INTEGER NOT NULL DEFAULT 0")
    if not _has_column(db, "users", "force_password_change"):
        db.execute("ALTER TABLE users ADD COLUMN force_password_change INTEGER NOT NULL DEFAULT 0")
    if not _has_column(db, "users", "password_changed_at"):
        db.execute("ALTER TABLE users ADD COLUMN password_changed_at INTEGER")

    # notifications read_at already exists in schema, but older DBs may miss it
    if not _has_column(db, "notifications", "read_at"):
        db.execute("ALTER TABLE notifications ADD COLUMN read_at INTEGER")

    # technician_skill_items: optional description for LinkedIn-style profile cards
    if not _has_column(db, "technician_skill_items", "skill_description"):
        db.execute("ALTER TABLE technician_skill_items ADD COLUMN skill_description TEXT")

    # job_tasks: add created_at column if missing (needed for task creation timestamps)
    if not _has_column(db, "job_tasks", "created_at"):
        db.execute("ALTER TABLE job_tasks ADD COLUMN created_at INTEGER NOT NULL DEFAULT 0")

def init_app(app):
    app.teardown_appcontext(close_db)
    with app.app_context():
        init_db()



def _column_exists(cur, table, column):
    rows = cur.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r[1] == column for r in rows)

def migrate_db(conn):
    cur = conn.cursor()
    # Add optional skill_description to technician_skill_items (LinkedIn-style display)
    try:
        if not _column_exists(cur, "technician_skill_items", "skill_description"):
            cur.execute("ALTER TABLE technician_skill_items ADD COLUMN skill_description TEXT")
            conn.commit()
    except Exception:
        pass