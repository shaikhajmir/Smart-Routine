from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import date

import json
import os
import requests

app = Flask(__name__)
app.secret_key = "CHANGE_THIS_SECRET_KEY"

# -----------------------------
# DATA STORAGE (JSON DB)
# -----------------------------
DB_FILE = "users.json"

def load_users():
    if not os.path.exists(DB_FILE):
        return {}
    with open(DB_FILE, "r") as f:
        return json.load(f)

def save_users(users):
    with open(DB_FILE, "w") as f:
        json.dump(users, f, indent=4)

# -----------------------------
# LOGIN REQUIRED DECORATOR
# -----------------------------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

# -----------------------------
# ROUTES
# -----------------------------

# BASE PAGE
@app.route("/")
def base():
    return render_template("base.html")

# -----------------------------
# REGISTER
# -----------------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    users = load_users()

    if request.method == "POST":
        email = request.form.get("email").lower()
        password = request.form.get("password")

        if email in users:
            flash("User already exists. Please login.", "error")
            return redirect(url_for("login"))

        users[email] = {
            "password": generate_password_hash(password),
            "data": {}
        }

        save_users(users)
        flash("Account created successfully. Please login.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")

# -----------------------------
# LOGIN
# -----------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    users = load_users()

    if request.method == "POST":
        email = request.form.get("email").lower().strip()
        password = request.form.get("password")

        # DEBUG PRINT (optional)
        print("Trying login:", email)

        if email in users:
            print("User exists")

            if users[email]["password"] and check_password_hash(users[email]["password"], password):
                print("Password correct")
                session["user"] = email
                return redirect(url_for("dashboard"))  # ✅ REDIRECT

            else:
                print("Password incorrect")

        else:
            print("User not found")

        flash("Invalid email or password", "error")

    return render_template("login.html")


# -----------------------------
# DASHBOARD (PROTECTED)
# -----------------------------
from datetime import date, datetime
from collections import defaultdict
from flask import render_template, request, redirect, url_for, session
from openai import OpenAI

# Initialize OpenAI client (set OPENAI_API_KEY in environment)
client = OpenAI()

@app.route("/dashboard", methods=["GET", "POST"])
@login_required
def dashboard():
    users = load_users()
    email = session["user"]

    # Ensure user structure
    if email not in users:
        users[email] = {}
    users[email].setdefault("tasks", [])

    # -----------------------------
    # ADD TASK (FROM LEFT PANEL)
    # -----------------------------
    if request.method == "POST":
        task = request.form.get("task")
        duration = int(request.form.get("duration"))   # ✅ FIXED (int)
        task_date = request.form.get("date") or str(date.today())

        users[email]["tasks"].append({
            "task": task,
            "duration": duration,
            "date": task_date
        })

        save_users(users)
        return redirect(url_for("dashboard"))

    tasks = users[email]["tasks"]

    # -----------------------------
    # AUTO-UPDATE CHART DATA
    # -----------------------------
    total_hours = sum(int(t["duration"]) for t in tasks)

    productive = int(total_hours * 0.7)
    unproductive = total_hours - productive

    # -----------------------------
    # WEEKLY & MONTHLY REPORTS
    # -----------------------------
    weekly = defaultdict(int)
    monthly = defaultdict(int)

    for t in tasks:
        d = datetime.strptime(t["date"], "%Y-%m-%d")
        week_key = f"{d.year}-W{d.isocalendar().week}"
        month_key = d.strftime("%Y-%m")

        weekly[week_key] += int(t["duration"])
        monthly[month_key] += int(t["duration"])

    # -----------------------------
    # AI TASK ANALYSIS (OPENAI)
    # -----------------------------
    ai_tip = "Add tasks to get AI productivity feedback."

    if tasks:
        task_text = "\n".join(
            f"{t['task']} - {t['duration']} hrs on {t['date']}"
            for t in tasks
        )

        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a productivity coach."},
                    {"role": "user", "content": f"Analyze my daily tasks:\n{task_text}"}
                ]
            )
            ai_tip = response.choices[0].message.content
        except Exception as e:
            ai_tip = "AI service temporarily unavailable."

    # -----------------------------
    # RENDER DASHBOARD
    # -----------------------------
    return render_template(
        "dashboard.html",
        user=email,
        tasks=tasks,
        productive=productive,
        unproductive=unproductive,
        weekly=weekly,
        monthly=monthly,
        ai_tip=ai_tip
    )

# -----------------------------
# LOGOUT
# -----------------------------
@app.route("/logout")
@login_required
def logout():
    session.clear()
    return redirect(url_for("base"))

# -----------------------------
# GOOGLE SIGN-IN (BACKEND READY)
# -----------------------------
@app.route("/google-login", methods=["POST"])
def google_login():
    """
    Frontend sends:
    { token: "google_id_token" }
    """

    token = request.json.get("token")

    # Verify token with Google
    response = requests.get(
        "https://oauth2.googleapis.com/tokeninfo",
        params={"id_token": token}
    )

    if response.status_code != 200:
        return {"error": "Invalid Google token"}, 401

    data = response.json()
    email = data.get("email")

    users = load_users()

    if email not in users:
        users[email] = {
            "password": None,
            "data": {}
        }
        save_users(users)

    session["user"] = email
    return {"success": True}
from openai import OpenAI
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def ai_analysis(tasks):
    if not tasks:
        return "Add tasks to get AI feedback."

    text = "\n".join([f"{t['task']} - {t['duration']} hrs" for t in tasks])

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role":"system","content":"You are a productivity coach."},
            {"role":"user","content":f"Analyze my tasks:\n{text}"}
        ]
    )
    return response.choices[0].message.content
@app.route("/daily-log", methods=["GET", "POST"])
@login_required
def daily_log():
    users = load_users()
    email = session["user"]

    users[email].setdefault("activities", [])
    users[email].setdefault("daily_logs", [])

    if request.method == "POST":
        date_val = request.form.get("date")
        log = {}

        for act in users[email]["activities"]:
            hours = request.form.get(act)
            log[act] = int(hours) if hours else 0

        users[email]["daily_logs"].append({
            "date": date_val,
            "log": log
        })

        save_users(users)
        return redirect(url_for("dashboard"))

    return render_template(
        "daily_log.html",
        activities=users[email]["activities"]
    )

# -----------------------------
# RUN SERVER
# -----------------------------
if __name__ == "__main__":
    app.run(debug=True)
