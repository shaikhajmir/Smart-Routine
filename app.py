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
@app.route("/dashboard", methods=["GET", "POST"])
@login_required
def dashboard():
    users = load_users()
    email = session["user"]

    # Ensure user data exists
    if "tasks" not in users[email]:
        users[email]["tasks"] = []

    # ADD TASK
    if request.method == "POST":
        task = request.form.get("task")
        duration = request.form.get("duration")

        users[email]["tasks"].append({
            "task": task,
            "duration": duration,
            "date": str(date.today())
        })

        save_users(users)
        return redirect(url_for("dashboard"))

    return render_template(
        "dashboard.html",
        user=email,
        tasks=users[email]["tasks"]
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

# -----------------------------
# RUN SERVER
# -----------------------------
if __name__ == "__main__":
    app.run(debug=True)
