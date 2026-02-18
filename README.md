# TechMatch – Technician & Business Matching Platform

**NYP School of Information Technology**

TechMatch is a web-based service-matching platform that connects technicians with businesses seeking technical services. The system includes role-based access control, account verification workflows, job tracking, skill management, and an administrative oversight panel.

---

## Team

| Name | Role |
|---|---|
| Tan I-Je | Account system, UI, Admin/Technician/Business homepage & Business dashboard |
| Ethan Tan | Technician dashboard & job workflow |
| Leu Haoen | Admin audit logs, technician & business listing |

---

## Setup & Running the Project

> All commands below assume you are inside the project folder.

### 1. Create and activate a virtual environment

**Windows (PowerShell)**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

**macOS / Linux**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the application

```bash
python run.py
```

The application will be available at: **http://127.0.0.1:5000**

---

## If the database instance is missing or reset

If the `instance/` folder is deleted or the database is blank, you will need to seed the admin account before logging in.

**Step 1 — Run the app once to initialise the database:**
```bash
python run.py
```
Stop it after it starts (`Ctrl + C`).

**Step 2 — Open a Flask shell and seed the admin:**
```bash
flask shell
```
Then inside the shell:
```python
from app.services.seed_service import seed_admin_if_needed
seed_admin_if_needed()
exit()
```

**Step 3 — Run the app again:**
```bash
python run.py
```

---

## Test Accounts

| Role | Email | Password |
|---|---|---|
| Admin | admin@techmatch.com | admin123 |
| Technician | hirono@gmail.com | labubu |
| Business | bduds@gmail.com | boomboom |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python, Flask 3.0 |
| Database | SQLite (via Flask's built-in sqlite3) |
| Frontend | HTML, Bootstrap 5.3, JavaScript |
| Auth | Server-side sessions (Werkzeug) |
| Config | python-dotenv |

---

## What Each Member Built

### Tan I-Je

Designed and implemented the complete account and identity system for the platform, which underpins everything else in the project.

**Account creation & authentication**
- Technician and Business sign-up flows with server-side validation
- Secure login, logout, and session handling
- Role-based access control across all routes (`TECHNICIAN`, `BUSINESS`, `ADMIN`)
- Password change and email change functionality

**Verification workflow**
- Multi-state verification pipeline: `PENDING → APPROVED / REJECTED`
- Cooldown logic on rejected accounts (derived from timestamp, no extra DB state)
- Document upload system for verification submissions (`.pdf`, `.docx`)
- One active verification request enforced per user at all times
- Admin review interface: approve, reject, flag, and audit submissions
- **Inline PDF viewer** embedded directly in the admin review page, allowing admins to read submitted verification documents without downloading them — designed to support informed, empathetic decision-making during the approval process

**Skill system**
- Technicians can submit skills with supporting certification documents
- Admin approval queue for new skill submissions
- Skill document management and download

**UI & homepages**
- Designed and built the shared visual language for the entire application using Bootstrap 5
- Built the Admin, Business, and Technician homepages
- Notification system displayed across all dashboards

**Business dashboard & job workflow simulation**
- The business dashboard, job management, and end-to-end workflow simulation were originally assigned to a fourth team member. As that contribution was not deliverable in time for integration, these features were independently implemented to ensure the assessment could demonstrate a complete job lifecycle.
- Full business-facing job management: create, view, and delete jobs
- Task creation and deletion per job with real-time updates
- Application review: approve or deny technician applications
- Job completion approval flow (business confirms technician's completion request)
- Note: the fourth member's payment and feedback modules, if functional, will be submitted separately as an additional zip file

---

### Ethan Tan

Built the complete technician-facing experience, covering everything a technician sees and does once logged in.

**Active Jobs**
- Displays all jobs the technician is currently assigned to
- View full job details including tasks set by the business
- Mark job as complete to send it to the business for confirmation

**Completed Jobs**
- Archive view of all jobs the technician has finished
- Full detail view available for each completed job

**Recommended Jobs**
- Surfaces open jobs matching service categories the technician has previously completed
- Personalised to each technician's history

**Find Jobs (Search)**
- Browse all open jobs posted by businesses
- Client-side search bar to filter by job title, category, or location
- Sign up for a job directly from the listing

**Task viewing**
- Technicians can see the task checklist set by the business on each job
- Tasks show completion status so the technician knows what has been verified

---

### Leu Haoen

Built the administrative monitoring and oversight tools used by admins to manage the platform.

**Audit logs**
- Tracks and displays key actions performed by admins, businesses, and technicians
- Provides a chronological activity record for accountability

**Admin search**
- Search for specific user accounts by name across the platform

**Technician listing**
- Review technician certifications and submitted skills
- Updates automatically when technicians add new skills for verification
- View each technician's current job status and active assignment

**Business listing**
- Displays all businesses registered on the platform
- Shows job postings with duration posted, business information, and uploaded certificates

---

## Note on Payment & Feedback

Payment processing and a feedback/rating system were scoped for this project and assigned to a fourth team member. Due to a lack of cooperation and code being submitted too late for integration, these modules are not included in this submission. The business dashboard and job workflow simulation presented here were independently built to ensure a complete, assessable end-to-end experience.

If the fourth member's work is functional, it will be provided as a separate zip file alongside this submission.