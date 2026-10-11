# Mining Portal Starter (local prototype)

This is a simple editable front-end + back-end starter. It supports:
- Customer registration and login
- Customer dashboard
- **Simulated-only** balances that an admin can adjust
- Customer support tickets and admin replies
- Mining information and package-information pages

## Important
- The balance is a display/testing number only. It is not money, crypto, a deposit, a withdrawal, or a promise of profit.
- There is no blockchain connection, wallet connection, payment gateway, mining engine, or real investment functionality.
- Do not collect customer deposits or market returns as guaranteed.
- This starter is for local testing. Before public deployment, add HTTPS, secure production secrets, rate limiting, email verification, backups, security review, and legal review.
- Do not use the default admin password on any internet-accessible deployment.

## Run on Windows
1. Install Python 3.10 or newer from https://www.python.org/downloads/
2. Extract this ZIP to a folder.
3. Open Command Prompt in that folder.
4. Run:
   ```
   py -m venv .venv
   .venv\\Scripts\\activate
   pip install -r requirements.txt
   py app.py
   ```
5. Open http://127.0.0.1:5000 in your browser.

## Admin login for local testing
- Username: `admin`
- Password: `ChangeMe123!`

Change these before first run if desired by setting environment variables `ADMIN_USERNAME` and `ADMIN_PASSWORD`. The admin user is created only if it does not already exist in the database. To reset a fresh local demo, stop the server and delete `portal.db`, then start it again with your chosen environment variables.

## Edit the design
Edit the HTML files in `templates/` and styling in `static/style.css`.
