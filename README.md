1) Setup (Windows / PowerShell)

Create and activate a virtual environment, then install dependencies:

python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt


If PowerShell blocks activation, run:

Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

2) Run the Application
python run.py


The application runs at:

http://127.0.0.1:5000

3) Seeded Admin Account

On first run, the backend automatically seeds an admin user if one does not exist.

Default credentials:

Email: admin@techmatch.local

Password: Admin123!

You may override these using environment variables:

ADMIN_EMAIL
ADMIN_PASSWORD

4) Key Backend Routes
Authentication

GET /login

POST /login

POST /logout

Account Requests

GET /request-account

POST /request-account/technician

POST /request-account/business

Verification State Pages

GET /pending

GET /homepage

Admin Routes

GET /admin/homepage

GET /admin/review/<request_id>

POST /admin/approve/<request_id>

POST /admin/reject/<request_id>

Notifications (Minimal)

GET /notifications

POST /notifications/mark-read

5) System Notes

Verification states stored in the database:

PENDING

APPROVED

REJECTED

Cooldown is not a stored state

It is derived from REJECTED + cooldown_until timestamp

One active verification request per user is enforced server-side

Uploaded documents:

Allowed types: .pdf, .docx

Validated before processing