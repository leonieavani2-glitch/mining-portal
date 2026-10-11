import os, sqlite3
from functools import wraps
from flask import Flask, g, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(APP_DIR, "portal.db")
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-local-demo-secret")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(_error=None):
    conn = g.pop("db", None)
    if conn:
        conn.close()

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      username TEXT UNIQUE NOT NULL,
      email TEXT UNIQUE NOT NULL,
      password_hash TEXT NOT NULL,
      demo_balance REAL NOT NULL DEFAULT 0,
      is_admin INTEGER NOT NULL DEFAULT 0,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS tickets (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL,
      subject TEXT NOT NULL,
      message TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'Open',
      reply TEXT DEFAULT '',
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(user_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS balance_log (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL,
      amount REAL NOT NULL,
      note TEXT NOT NULL,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """)
    admin_user = os.environ.get("ADMIN_USERNAME", "admin")
    admin_pass = os.environ.get("ADMIN_PASSWORD", "ChangeMe123!")
    row = conn.execute("SELECT id FROM users WHERE username=?", (admin_user,)).fetchone()
    if not row:
        conn.execute("INSERT INTO users(username,email,password_hash,is_admin) VALUES(?,?,?,1)",
                     (admin_user, "admin@example.invalid", generate_password_hash(admin_pass)))
    conn.commit()
    conn.close()

def login_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in to continue.")
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapped

def admin_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login"))
        user = db().execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone()
        if not user or not user["is_admin"]:
            flash("Admin access required.")
            return redirect(url_for("dashboard"))
        return fn(*args, **kwargs)
    return wrapped

@app.context_processor
def inject_user():
    user = None
    if session.get("user_id"):
        user = db().execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone()
    return {"current_user": user}

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if len(username) < 3 or "@" not in email or len(password) < 8:
            flash("Use a username of 3+ characters, a valid email, and a password of at least 8 characters.")
            return render_template("register.html")
        try:
            db().execute("INSERT INTO users(username,email,password_hash) VALUES(?,?,?)",
                         (username, email, generate_password_hash(password)))
            db().commit()
        except sqlite3.IntegrityError:
            flash("That username or email is already registered.")
            return render_template("register.html")
        flash("Account created. This portal uses simulated balances only.")
        return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        ident = request.form.get("ident", "").strip()
        password = request.form.get("password", "")
        user = db().execute("SELECT * FROM users WHERE username=? OR email=?", (ident, ident.lower())).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            return redirect(url_for("admin" if user["is_admin"] else "dashboard"))
        flash("Incorrect username/email or password.")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.route("/dashboard")
@login_required
def dashboard():
    user = db().execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone()
    tickets = db().execute("SELECT * FROM tickets WHERE user_id=? ORDER BY id DESC", (user["id"],)).fetchall()
    logs = db().execute("SELECT * FROM balance_log WHERE user_id=? ORDER BY id DESC LIMIT 10", (user["id"],)).fetchall()
    return render_template("dashboard.html", user=user, tickets=tickets, logs=logs)

@app.route("/support", methods=["GET", "POST"])
@login_required
def support():
    if request.method == "POST":
        subject = request.form.get("subject", "").strip()
        message = request.form.get("message", "").strip()
        if subject and message:
            db().execute("INSERT INTO tickets(user_id,subject,message) VALUES(?,?,?)",
                         (session["user_id"], subject[:120], message[:3000]))
            db().commit()
            flash("Support request submitted.")
            return redirect(url_for("dashboard"))
        flash("Please enter a subject and message.")
    return render_template("support.html")

@app.route("/admin")
@admin_required
def admin():
    users = db().execute("SELECT id,username,email,demo_balance,created_at FROM users WHERE is_admin=0 ORDER BY id DESC").fetchall()
    tickets = db().execute("""SELECT tickets.*, users.username FROM tickets JOIN users ON users.id=tickets.user_id
                              ORDER BY CASE status WHEN 'Open' THEN 0 ELSE 1 END, tickets.id DESC""").fetchall()
    return render_template("admin.html", users=users, tickets=tickets)

@app.route("/admin/balance", methods=["POST"])
@admin_required
def adjust_balance():
    try:
        user_id = int(request.form.get("user_id", ""))
        amount = float(request.form.get("amount", ""))
        note = request.form.get("note", "").strip()[:200]
        if amount == 0 or abs(amount) > 100000000 or not note:
            raise ValueError()
        target = db().execute("SELECT * FROM users WHERE id=? AND is_admin=0", (user_id,)).fetchone()
        if not target or target["demo_balance"] + amount < 0:
            flash("Invalid user or balance adjustment.")
            return redirect(url_for("admin"))
        db().execute("UPDATE users SET demo_balance=demo_balance+? WHERE id=?", (amount, user_id))
        db().execute("INSERT INTO balance_log(user_id,amount,note) VALUES(?,?,?)", (user_id, amount, note))
        db().commit()
        flash("Simulated balance updated. No real money or crypto was moved.")
    except (ValueError, TypeError):
        flash("Enter a valid non-zero amount and note.")
    return redirect(url_for("admin"))

@app.route("/admin/ticket/<int:ticket_id>", methods=["POST"])
@admin_required
def update_ticket(ticket_id):
    status = request.form.get("status", "Open")
    reply = request.form.get("reply", "").strip()[:3000]
    if status not in ("Open", "In progress", "Resolved"):
        status = "Open"
    db().execute("UPDATE tickets SET status=?, reply=? WHERE id=?", (status, reply, ticket_id))
    db().commit()
    flash("Support ticket updated.")
    return redirect(url_for("admin"))

@app.route("/packages")
def packages():
    return render_template("packages.html")

if __name__ == "__main__":
    init_db()
    app.run(host="127.0.0.1", port=5000, debug=False)
