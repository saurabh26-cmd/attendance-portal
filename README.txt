# Online Monthly Attendance Portal — Ready-to-Deploy Prototype

## What it does
Admin creates manager Login ID + Password and assigns a warehouse.
Manager logs in and fills the entire selected month in one grid:
P = Present, A = Absent, L = Leave, WO = Weekly Off.
Manager can save/update the whole month.
Admin can manage employee master and view monthly summaries.

## Demo
Admin Login ID: admin
Admin Password: Admin@123

## Run locally
python -m venv .venv
Windows: .venv\Scripts\activate
macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python app.py
Open http://127.0.0.1:5000

## To make it genuinely online
Deploy this Flask app on a cloud host and use a persistent cloud database.
The included prototype uses SQLite for easy testing. SQLite should NOT be used for a multi-user production deployment.
For production, migrate the DB layer to PostgreSQL and add HTTPS, CSRF protection, rate limiting, password reset, backups, audit logs, and proper access controls.

This app does not collect Flipkart passwords or OTPs.
