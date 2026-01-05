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
from datetime import date, datetime, timedelta
import json
import os
import requests
import io
import csv
from flask import send_file, Response
# -----------------------------
# -----------------------------
# DATA STORAGE (JSON DB)
# -----------------------------
DB_FILE = "users.json"

def calculate_streak(daily_logs):
    """
    Calculates consecutive days of logging ending today or yesterday.
    Returns: integer streak count.
    """
    if not daily_logs:
        return 0
    
    # Extract unique dates from logs
    log_dates = sorted(list(set(log["date"] for log in daily_logs)), reverse=True)
    if not log_dates:
        return 0
    
    today = date.today()
    try:
        current_log_date = datetime.strptime(log_dates[0], "%Y-%m-%d").date()
    except:
        return 0
    
    # If the last log was effectively not "current" (today or yesterday), streak is broken
    if current_log_date < today - timedelta(days=1):
        return 0
        
    streak = 1
    # Check consecutive days backwards
    for i in range(len(log_dates) - 1):
        try:
            d1 = datetime.strptime(log_dates[i], "%Y-%m-%d").date()
            d2 = datetime.strptime(log_dates[i+1], "%Y-%m-%d").date()
            if (d1 - d2).days == 1:
                streak += 1
            else:
                break
        except:
            break
            
    return streak

def check_achievements(user_data):
    """
    Returns a list of unlocked badges based on user stats.
    """
    badges = []
    logs = user_data.get("daily_logs", [])
    streak = calculate_streak(logs)
    
    # 1. Rookie: First Log
    if len(logs) >= 1:
        badges.append({"id": "rookie", "icon": "🥉", "title": "Rookie", "desc": "Logged your first day."})
        
    # 2. On Fire: 3 Day Streak
    if streak >= 3:
        badges.append({"id": "fire", "icon": "🔥", "title": "On Fire", "desc": "Achieved a 3-day streak."})
        
    # 3. Beast Mode: 10+ Hours in a single day
    for entry in logs:
        total = sum(entry.get("log", {}).values())
        if total >= 10:
            badges.append({"id": "beast", "icon": "🦁", "title": "Beast Mode", "desc": "Logged 10+ hours in a day."})
            break
            
    # 4. Consistency King: 7 Day Streak
    if streak >= 7:
        badges.append({"id": "king", "icon": "👑", "title": "Consistency King", "desc": "7-day streak master."})
        
    return badges

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
        
        # Update last_seen timestamp for online status
        from datetime import datetime
        users = load_users()
        email = session["user"]
        if email in users:
            if "data" not in users[email]:
                users[email]["data"] = {}
            users[email]["data"]["last_seen"] = datetime.now().isoformat()
            save_users(users)
        
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

    streaks = users[email].get("daily_logs", [])
    current_streak = calculate_streak(streaks)
    
    # ACHIEVEMENTS
    badges = check_achievements(users[email])
    
    # GOALS vs ACTUALS (Current Week)
    goals = users[email].get("goals", {})
    # Calculate this week's actuals
    this_week_actuals = defaultdict(int)
    today = date.today()
    start_of_week = today - timedelta(days=today.weekday()) # Monday
    
    for log in users[email].get("daily_logs", []):
        log_date = datetime.strptime(log["date"], "%Y-%m-%d").date()
        if log_date >= start_of_week:
            for act, hrs in log.get("log", {}).items():
                this_week_actuals[act] += hrs

    # HEATMAP DATA PREP (Last 30 days)
    # Format: { "2026-01-01": 5, "2026-01-02": 0 }
    log_activity = {}
    for log in users[email].get("daily_logs", []):
        total_hrs = sum(log.get("log", {}).values())
        if total_hrs > 0:
            log_activity[log["date"]] = total_hrs

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
    # AI TASK ANALYSIS (ON-DEMAND)
    # -----------------------------
    # We no longer auto-generate here to save performance/cost.
    # The frontend will call /generate-insight.

    # -----------------------------
    # RENDER DASHBOARD
    # -----------------------------
    return render_template(
        "dashboard.html",
        user=users[email],
        email=email,
        tasks=tasks,
        productive=productive,
        unproductive=unproductive,
        weekly=weekly,
        monthly=monthly,
        streak=current_streak,
        heatmap_data=log_activity,
        badges=badges,
        goals=goals,
        actuals=this_week_actuals
    )

@app.route("/generate-insight", methods=["POST"])
@login_required
def generate_insight():
    users = load_users()
    email = session["user"]
    tasks = users[email].get("tasks", [])
    
    if not tasks:
        return jsonify({"success": False, "message": "No tasks to analyze yet!"})

    # Get last 5 tasks for context
    recent = tasks[-10:]
    task_text = "\n".join([f"- {t['task']} ({t['duration']} hrs) on {t['date']}" for t in recent])
    
    streak = calculate_streak(users[email].get("daily_logs", []))
    
    prompt = f"""
    You are a high-performance productivity coach.
    User Streak: {streak} days.
    Recent Activity:
    {task_text}
    
    Analyze their focus usage. Give 1 short, punchy, specific advice (max 2 sentences) to optimize their routine.
    Direct address ("You should..."). No fluff.
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": "You are a specialized productivity AI."},
                      {"role": "user", "content": prompt}]
        )
        insight = response.choices[0].message.content
        
        # Save to user profile
        users[email]["data"]["latest_insight"] = insight
        save_users(users)
        
        return jsonify({"success": True, "insight": insight})
    except Exception as e:
        print(e)
        return jsonify({"success": False, "message": "AI Service unavailable."})

@app.route("/delete-task/<int:index>", methods=["POST"])
@login_required
def delete_task(index):
    users = load_users()
    email = session["user"]
    tasks = users[email].get("tasks", [])
    
    if 0 <= index < len(tasks):
        tasks.pop(index) # Remove by index
        save_users(users)
        flash("Task deleted.", "success")
    else:
        flash("Task not found.", "error")
        
    return redirect(url_for("dashboard"))



# -----------------------------
# EXPORT DATA
# -----------------------------
@app.route("/export_data")
@login_required
def export_data():
    users = load_users()
    email = session["user"]
    user_data = users.get(email, {})
    
    # Create a simple JSON export
    # For a more complex CSV export, we could offer choices.
    # Here we default to JSON for structural integrity.
    
    return Response(
        json.dumps(user_data, indent=4),
        mimetype="application/json",
        headers={"Content-disposition": "attachment; filename=my_smartroutine_data.json"}
    )

# -----------------------------
# SET GOALS
# -----------------------------
@app.route("/set-goals", methods=["POST"])
@login_required
def set_goals():
    users = load_users()
    email = session["user"]
    
    goals = {}
    for act in users[email].get("activities", []):
        target = request.form.get(f"goal_{act}")
        if target:
            goals[act] = int(target)
            
    users[email]["goals"] = goals
    save_users(users)
    flash("Weekly goals updated!", "success")
    return redirect(url_for("dashboard"))

# -----------------------------
# SMART REPORT
# -----------------------------
@app.route("/report")
@login_required
def report():
    users = load_users()
    email = session["user"]
    u = users[email]
    
    # Calculate Summary Stats
    total_logs = len(u.get("daily_logs", []))
    streak = calculate_streak(u.get("daily_logs", []))
    
    # Mood Stats
    moods = [l.get("mood") for l in u.get("daily_logs", []) if l.get("mood")]
    top_mood = max(set(moods), key=moods.count) if moods else "N/A"
    
    return render_template("report.html", 
                           user=u, 
                           email=email,
                           stats={"total_logs": total_logs, "streak": streak, "top_mood": top_mood},
                           badges=check_achievements(u))

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
        mood_val = request.form.get("mood")
        log = {}

        for act in users[email]["activities"]:
            hours = request.form.get(act)
            log[act] = int(hours) if hours else 0

        users[email]["daily_logs"].append({
            "date": date_val,
            "mood": mood_val,
            "log": log
        })

        save_users(users)
        return redirect(url_for("dashboard"))

    return render_template(
        "daily_log.html",
        user=users[email],
        activities=users[email]["activities"],
        today_date=str(date.today())
    )

# -----------------------------
# NOTES
# -----------------------------
@app.route("/notes", methods=["GET", "POST"])
@login_required
def notes():
    users = load_users()
    email = session["user"]
    users[email].setdefault("notes", [])

    if request.method == "POST":
        title = request.form.get("title")
        content = request.form.get("content")
        # Store simplified date string
        d_str = str(date.today())
        
        users[email]["notes"].append({
            "title": title,
            "content": content,
            "date": d_str
        })
        save_users(users)
        flash("Note added successfully!", "success")
        return redirect(url_for("notes"))

    return render_template("notes.html", notes=users[email]["notes"])

# -----------------------------
# EXPENSES
# -----------------------------
@app.route("/expenses", methods=["GET", "POST"])
@login_required
def expenses():
    users = load_users()
    email = session["user"]
    users[email].setdefault("expenses", [])

    if request.method == "POST":
        try:
            amount = float(request.form.get("amount"))
        except ValueError:
            amount = 0.0
            
        desc = request.form.get("description")
        category = request.form.get("category")
        d_str = str(date.today())

        users[email]["expenses"].append({
            "amount": amount,
            "description": desc,
            "category": category,
            "date": d_str
        })
        save_users(users)
        flash("Expense added!", "success")
        return redirect(url_for("expenses"))

    return render_template("expenses.html", expenses=users[email]["expenses"])

# -----------------------------
# MANAGE ACTIVITIES
# -----------------------------
@app.route("/activities", methods=["GET", "POST"])
@login_required
def activities():
    users = load_users()
    email = session["user"]
    # Ensure default activities exist if empty
    if "activities" not in users[email] or not users[email]["activities"]:
        users[email]["activities"] = ["Coding", "Reading", "Exercise", "Sleep"] # Default set

    if request.method == "POST":
        if "new_activity" in request.form:
            new_act = request.form.get("new_activity").strip()
            if new_act and new_act not in users[email]["activities"]:
                users[email]["activities"].append(new_act)
                save_users(users)
                flash(f"Activity '{new_act}' added.", "success")
        
        elif "delete_activity" in request.form:
            act = request.form.get("delete_activity")
            if act in users[email]["activities"]:
                users[email]["activities"].remove(act)
                save_users(users)
                flash(f"Activity '{act}' removed.", "success")
                
        return redirect(url_for("activities"))

    return render_template("activities.html", activities=users[email]["activities"])

# -----------------------------
# USER PROFILE
# -----------------------------
@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    users = load_users()
    email = session["user"]
    user = users[email]
    
    # Ensure data dict exists
    user.setdefault("data", {})
    user["data"].setdefault("avatar", "👤") # Default avatar
    
    if request.method == "POST":
        # Handle Avatar Update
        if "avatar" in request.form:
            user["data"]["avatar"] = request.form.get("avatar")
            save_users(users)
            flash("Avatar updated!", "success")
        
        # Handle Password Change (Simple implementation)
        elif "new_password" in request.form:
             new_pw = request.form.get("new_password")
             if new_pw:
                 user["password"] = generate_password_hash(new_pw)
                 save_users(users)
                 flash("Password changed successfully.", "success")
                 
        return redirect(url_for("profile"))

    # Calculate Lifetime Stats for Profile
    total_logs = len(user.get("daily_logs", []))
    total_hours = 0
    for log in user.get("daily_logs", []):
         total_hours += sum(log.get("log", {}).values())
         
    stats = {
        "joined": "2024", # Placeholder, or add joined_date to register
        "logs": total_logs,
        "hours": int(total_hours),
        "streak": calculate_streak(user.get("daily_logs", []))
    }
    
    return render_template("profile.html", user=user, email=email, stats=stats)


# -----------------------------
# LEADERBOARD
# -----------------------------
@app.route("/leaderboard")
@login_required
def leaderboard():
    users = load_users()
    current_email = session["user"]
    
    # Calculate stats for all users
    leaderboard_data = []
    for email, user_data in users.items():
        # Calculate metrics
        total_hours = sum(t.get("duration", 0) for t in user_data.get("tasks", []))
        streak = calculate_streak(user_data.get("daily_logs", []))
        badges_count = len(check_achievements(user_data))
        
        # Get display name
        display_name = user_data.get("data", {}).get("first_name", email.split("@")[0])
        avatar = user_data.get("data", {}).get("avatar", "👤")
        
        leaderboard_data.append({
            "email": email,
            "name": display_name,
            "avatar": avatar,
            "total_hours": total_hours,
            "streak": streak,
            "badges": badges_count,
            "is_current": email == current_email
        })
    
    # Sort by streak (default)
    leaderboard_data.sort(key=lambda x: x["streak"], reverse=True)
    
    return render_template("leaderboard.html", 
                         leaderboard=leaderboard_data,
                         user=users[current_email],
                         email=current_email)


# -----------------------------
# CHALLENGES
# -----------------------------
CHALLENGE_TEMPLATES = {
    "daily": [
        {"id": "daily_5hrs", "title": "5-Hour Focus", "desc": "Log 5 hours of productive work today", "target": 5, "metric": "hours", "reward": "⚡"},
        {"id": "daily_3tasks", "title": "Task Master", "desc": "Complete 3 different tasks today", "target": 3, "metric": "tasks", "reward": "✅"},
        {"id": "daily_streak", "title": "Consistency King", "desc": "Maintain your daily streak", "target": 1, "metric": "streak", "reward": "🔥"},
    ],
    "weekly": [
        {"id": "weekly_30hrs", "title": "30-Hour Week", "desc": "Log 30 hours this week", "target": 30, "metric": "hours", "reward": "💪"},
        {"id": "weekly_5activities", "title": "Variety Seeker", "desc": "Try 5 different activities", "target": 5, "metric": "activities", "reward": "🌈"},
        {"id": "weekly_no_zero", "title": "No Zero Days", "desc": "Log something every day this week", "target": 7, "metric": "days", "reward": "🎯"},
    ]
}

def assign_challenges(user_data):
    """Auto-assign daily and weekly challenges if none active"""
    import random
    from datetime import datetime, timedelta
    
    if "challenges" not in user_data:
        user_data["challenges"] = {"active": [], "completed": []}
    
    today = datetime.now().date()
    
    # Remove expired challenges
    user_data["challenges"]["active"] = [
        c for c in user_data["challenges"]["active"] 
        if datetime.strptime(c["expires"], "%Y-%m-%d").date() >= today
    ]
    
    # Assign daily challenge if none
    has_daily = any(c["type"] == "daily" for c in user_data["challenges"]["active"])
    if not has_daily:
        template = random.choice(CHALLENGE_TEMPLATES["daily"])
        user_data["challenges"]["active"].append({
            **template,
            "type": "daily",
            "progress": 0,
            "expires": str(today + timedelta(days=1))
        })
    
    # Assign weekly challenge if none
    has_weekly = any(c["type"] == "weekly" for c in user_data["challenges"]["active"])
    if not has_weekly:
        template = random.choice(CHALLENGE_TEMPLATES["weekly"])
        user_data["challenges"]["active"].append({
            **template,
            "type": "weekly",
            "progress": 0,
            "expires": str(today + timedelta(days=7))
        })
    
    return user_data

def update_challenge_progress(user_data):
    """Update challenge progress based on current user data"""
    from datetime import datetime, timedelta
    
    if "challenges" not in user_data:
        return
    
    today = datetime.now().date()
    week_start = today - timedelta(days=today.weekday())
    
    for challenge in user_data["challenges"]["active"]:
        metric = challenge["metric"]
        
        if metric == "hours":
            if challenge["type"] == "daily":
                # Today's hours
                today_log = next((l for l in user_data.get("daily_logs", []) if l["date"] == str(today)), None)
                if today_log:
                    challenge["progress"] = sum(today_log.get("log", {}).values())
            else:
                # This week's hours
                week_logs = [l for l in user_data.get("daily_logs", []) 
                           if datetime.strptime(l["date"], "%Y-%m-%d").date() >= week_start]
                challenge["progress"] = sum(sum(l.get("log", {}).values()) for l in week_logs)
        
        elif metric == "tasks":
            # Today's unique tasks
            today_tasks = [t for t in user_data.get("tasks", []) if t["date"] == str(today)]
            challenge["progress"] = len(today_tasks)
        
        elif metric == "streak":
            challenge["progress"] = 1 if calculate_streak(user_data.get("daily_logs", [])) > 0 else 0
        
        elif metric == "activities":
            # This week's unique activities
            week_logs = [l for l in user_data.get("daily_logs", []) 
                       if datetime.strptime(l["date"], "%Y-%m-%d").date() >= week_start]
            unique_activities = set()
            for log in week_logs:
                unique_activities.update(log.get("log", {}).keys())
            challenge["progress"] = len(unique_activities)
        
        elif metric == "days":
            # Days logged this week
            week_logs = [l for l in user_data.get("daily_logs", []) 
                       if datetime.strptime(l["date"], "%Y-%m-%d").date() >= week_start 
                       and sum(l.get("log", {}).values()) > 0]
            challenge["progress"] = len(week_logs)
        
        # Check completion
        if challenge["progress"] >= challenge["target"] and challenge["id"] not in user_data["challenges"]["completed"]:
            user_data["challenges"]["completed"].append(challenge["id"])
            # Could add badge here

@app.route("/challenges")
@login_required
def challenges():
    users = load_users()
    email = session["user"]
    user_data = users[email]
    
    # Assign challenges if needed
    user_data = assign_challenges(user_data)
    
    # Update progress
    update_challenge_progress(user_data)
    
    # Save
    save_users(users)
    
    return render_template("challenges.html", 
                         user=user_data,
                         email=email,
                         challenges=user_data["challenges"]["active"],
                         completed_count=len(user_data["challenges"].get("completed", [])))


# -----------------------------
# FRIEND SYSTEM
# -----------------------------
@app.route("/friends")
@login_required
def friends():
    users = load_users()
    email = session["user"]
    user_data = users[email]
    
    # Initialize friends structure if not exists
    if "friends" not in user_data:
        user_data["friends"] = {"list": [], "pending_sent": [], "pending_received": []}
        save_users(users)
    
    # Get friend details
    friends_list = []
    for friend_email in user_data["friends"]["list"]:
        if friend_email in users:
            friend = users[friend_email]
            
            # Calculate online status (online if seen in last 5 minutes)
            from datetime import datetime, timedelta
            last_seen_str = friend.get("data", {}).get("last_seen")
            is_online = False
            if last_seen_str:
                try:
                    last_seen = datetime.fromisoformat(last_seen_str)
                    is_online = (datetime.now() - last_seen) < timedelta(minutes=5)
                except:
                    pass
            
            friends_list.append({
                "email": friend_email,
                "name": friend.get("data", {}).get("first_name", friend_email.split("@")[0]),
                "avatar": friend.get("data", {}).get("avatar", "👤"),
                "streak": calculate_streak(friend.get("daily_logs", [])),
                "total_hours": sum(t.get("duration", 0) for t in friend.get("tasks", [])),
                "badges": len(check_achievements(friend)),
                "is_online": is_online
            })
    
    # Get pending requests details
    pending_received = []
    for req_email in user_data["friends"]["pending_received"]:
        if req_email in users:
            requester = users[req_email]
            pending_received.append({
                "email": req_email,
                "name": requester.get("data", {}).get("first_name", req_email.split("@")[0]),
                "avatar": requester.get("data", {}).get("avatar", "👤")
            })
    
    return render_template("friends.html",
                         user=user_data,
                         email=email,
                         friends=friends_list,
                         pending_received=pending_received,
                         pending_sent=user_data["friends"]["pending_sent"])

@app.route("/friends/add", methods=["POST"])
@login_required
def add_friend():
    users = load_users()
    email = session["user"]
    friend_email = request.form.get("friend_email", "").strip().lower()
    
    # Validation
    if not friend_email:
        flash("Please enter an email address.", "error")
        return redirect(url_for("friends"))
    
    if friend_email == email:
        flash("You can't add yourself as a friend!", "error")
        return redirect(url_for("friends"))
    
    if friend_email not in users:
        flash("User not found.", "error")
        return redirect(url_for("friends"))
    
    user_data = users[email]
    if "friends" not in user_data:
        user_data["friends"] = {"list": [], "pending_sent": [], "pending_received": []}
    
    # Check if already friends
    if friend_email in user_data["friends"]["list"]:
        flash("Already friends!", "info")
        return redirect(url_for("friends"))
    
    # Check if request already sent
    if friend_email in user_data["friends"]["pending_sent"]:
        flash("Friend request already sent.", "info")
        return redirect(url_for("friends"))
    
    # Send request
    user_data["friends"]["pending_sent"].append(friend_email)
    
    # Add to friend's pending received
    friend_data = users[friend_email]
    if "friends" not in friend_data:
        friend_data["friends"] = {"list": [], "pending_sent": [], "pending_received": []}
    friend_data["friends"]["pending_received"].append(email)
    
    save_users(users)
    flash(f"Friend request sent to {friend_email}!", "success")
    return redirect(url_for("friends"))

@app.route("/friends/accept/<friend_email>")
@login_required
def accept_friend(friend_email):
    users = load_users()
    email = session["user"]
    user_data = users[email]
    
    if "friends" not in user_data:
        user_data["friends"] = {"list": [], "pending_sent": [], "pending_received": []}
    
    # Remove from pending
    if friend_email in user_data["friends"]["pending_received"]:
        user_data["friends"]["pending_received"].remove(friend_email)
        user_data["friends"]["list"].append(friend_email)
        
        # Update friend's data
        friend_data = users[friend_email]
        if "friends" not in friend_data:
            friend_data["friends"] = {"list": [], "pending_sent": [], "pending_received": []}
        
        if email in friend_data["friends"]["pending_sent"]:
            friend_data["friends"]["pending_sent"].remove(email)
        friend_data["friends"]["list"].append(email)
        
        save_users(users)
        flash(f"You are now friends with {friend_email}!", "success")
    
    return redirect(url_for("friends"))

@app.route("/friends/reject/<friend_email>")
@login_required
def reject_friend(friend_email):
    users = load_users()
    email = session["user"]
    user_data = users[email]
    
    if "friends" not in user_data:
        user_data["friends"] = {"list": [], "pending_sent": [], "pending_received": []}
    
    if friend_email in user_data["friends"]["pending_received"]:
        user_data["friends"]["pending_received"].remove(friend_email)
        
        # Remove from friend's pending sent
        friend_data = users[friend_email]
        if "friends" in friend_data and email in friend_data["friends"]["pending_sent"]:
            friend_data["friends"]["pending_sent"].remove(email)
        
        save_users(users)
        flash("Friend request rejected.", "info")
    
    return redirect(url_for("friends"))

@app.route("/friends/remove/<friend_email>")
@login_required
def remove_friend(friend_email):
    users = load_users()
    email = session["user"]
    user_data = users[email]
    
    if "friends" in user_data and friend_email in user_data["friends"]["list"]:
        user_data["friends"]["list"].remove(friend_email)
        
        # Remove from friend's list
        friend_data = users[friend_email]
        if "friends" in friend_data and email in friend_data["friends"]["list"]:
            friend_data["friends"]["list"].remove(email)
        
        save_users(users)
        flash("Friend removed.", "info")
    
    return redirect(url_for("friends"))


# -----------------------------
# HEAD-TO-HEAD CHALLENGES
# -----------------------------
@app.route("/h2h")
@login_required
def h2h():
    users = load_users()
    email = session["user"]
    user_data = users[email]
    
    # Initialize H2H structure
    if "h2h_challenges" not in user_data:
        user_data["h2h_challenges"] = {"active": [], "completed": [], "pending": []}
        save_users(users)
    
    # Get all challenges involving this user
    all_challenges = []
    
    for challenge in user_data["h2h_challenges"]["active"]:
        opponent_email = challenge["opponent"] if challenge["challenger"] == email else challenge["challenger"]
        opponent = users.get(opponent_email, {})
        
        all_challenges.append({
            **challenge,
            "opponent_name": opponent.get("data", {}).get("first_name", opponent_email.split("@")[0]),
            "opponent_avatar": opponent.get("data", {}).get("avatar", "👤"),
            "is_challenger": challenge["challenger"] == email
        })
    
    # Get pending challenges
    pending = []
    for challenge in user_data["h2h_challenges"]["pending"]:
        sender_email = challenge["challenger"]
        sender = users.get(sender_email, {})
        pending.append({
            **challenge,
            "sender_name": sender.get("data", {}).get("first_name", sender_email.split("@")[0]),
            "sender_avatar": sender.get("data", {}).get("avatar", "👤")
        })
    
    # Get friends for challenge creation
    friends_list = []
    if "friends" in user_data:
        for friend_email in user_data["friends"]["list"]:
            if friend_email in users:
                friend = users[friend_email]
                friends_list.append({
                    "email": friend_email,
                    "name": friend.get("data", {}).get("first_name", friend_email.split("@")[0]),
                    "avatar": friend.get("data", {}).get("avatar", "👤")
                })
    
    return render_template("h2h.html",
                         user=user_data,
                         email=email,
                         active_challenges=all_challenges,
                         pending_challenges=pending,
                         friends=friends_list)

@app.route("/h2h/create", methods=["POST"])
@login_required
def create_h2h():
    import uuid
    from datetime import datetime, timedelta
    
    users = load_users()
    email = session["user"]
    
    opponent_email = request.form.get("opponent")
    challenge_type = request.form.get("challenge_type")
    
    # Validation
    if not opponent_email or opponent_email not in users:
        flash("Invalid opponent.", "error")
        return redirect(url_for("h2h"))
    
    # Check if friends
    user_data = users[email]
    if "friends" not in user_data or opponent_email not in user_data["friends"]["list"]:
        flash("You can only challenge friends!", "error")
        return redirect(url_for("h2h"))
    
    # Define challenge parameters (EXPANDED)
    challenge_configs = {
        # Original 4
        "streak_battle": {"title": "7-Day Streak Battle", "target": 7, "metric": "streak", "duration": 7},
        "hour_race": {"title": "20-Hour Race", "target": 20, "metric": "hours", "duration": 7},
        "task_sprint": {"title": "15-Task Sprint", "target": 15, "metric": "tasks", "duration": 3},
        "activity_master": {"title": "5-Activity Challenge", "target": 5, "metric": "activities", "duration": 7},
        
        # Productivity Challenges
        "chase_battle": {"title": "Chase Battle: 50 Hours", "target": 50, "metric": "hours", "duration": 14},
        "speed_run": {"title": "Speed Run: 10 Hours in 24h", "target": 10, "metric": "hours", "duration": 1},
        "endurance_test": {"title": "Endurance: 14-Day Streak", "target": 14, "metric": "streak", "duration": 14},
        "perfect_week": {"title": "Perfect Week: 40 Hours", "target": 40, "metric": "hours", "duration": 7},
        "mega_sprint": {"title": "Mega Sprint: 30 Tasks", "target": 30, "metric": "tasks", "duration": 7},
        "variety_king": {"title": "Variety King: 10 Activities", "target": 10, "metric": "activities", "duration": 14},
        
        # Chess Game
        "chess_game": {"title": "Chess Match", "target": 1, "metric": "chess", "duration": 7}
    }
    
    if challenge_type not in challenge_configs:
        flash("Invalid challenge type.", "error")
        return redirect(url_for("h2h"))
    
    config = challenge_configs[challenge_type]
    challenge_id = str(uuid.uuid4())[:8]
    today = datetime.now().date()
    
    challenge = {
        "id": challenge_id,
        "challenger": email,
        "opponent": opponent_email,
        "type": challenge_type,
        "title": config["title"],
        "target": config["target"],
        "metric": config["metric"],
        "start_date": str(today),
        "end_date": str(today + timedelta(days=config["duration"])),
        "challenger_progress": 0,
        "opponent_progress": 0,
        "status": "pending",
        "winner": None
    }
    
    # Add to opponent's pending
    opponent_data = users[opponent_email]
    if "h2h_challenges" not in opponent_data:
        opponent_data["h2h_challenges"] = {"active": [], "completed": [], "pending": []}
    opponent_data["h2h_challenges"]["pending"].append(challenge)
    
    # Add to user's active (as pending from their side too)
    if "h2h_challenges" not in user_data:
        user_data["h2h_challenges"] = {"active": [], "completed": [], "pending": []}
    user_data["h2h_challenges"]["active"].append(challenge)
    
    save_users(users)
    flash(f"Challenge sent to {opponent_email}!", "success")
    return redirect(url_for("h2h"))

@app.route("/h2h/accept/<challenge_id>")
@login_required
def accept_h2h(challenge_id):
    users = load_users()
    email = session["user"]
    user_data = users[email]
    
    if "h2h_challenges" not in user_data:
        return redirect(url_for("h2h"))
    
    # Find and accept challenge
    for challenge in user_data["h2h_challenges"]["pending"]:
        if challenge["id"] == challenge_id:
            challenge["status"] = "active"
            user_data["h2h_challenges"]["pending"].remove(challenge)
            user_data["h2h_challenges"]["active"].append(challenge)
            
            # Update challenger's copy
            challenger_data = users[challenge["challenger"]]
            for c in challenger_data["h2h_challenges"]["active"]:
                if c["id"] == challenge_id:
                    c["status"] = "active"
            
            save_users(users)
            flash("Challenge accepted! Let the battle begin! 🔥", "success")
            break
    
    return redirect(url_for("h2h"))

@app.route("/h2h/decline/<challenge_id>")
@login_required
def decline_h2h(challenge_id):
    users = load_users()
    email = session["user"]
    user_data = users[email]
    
    if "h2h_challenges" not in user_data:
        return redirect(url_for("h2h"))
    
    # Find and decline
    for challenge in user_data["h2h_challenges"]["pending"]:
        if challenge["id"] == challenge_id:
            user_data["h2h_challenges"]["pending"].remove(challenge)
            
            # Remove from challenger's active
            challenger_data = users[challenge["challenger"]]
            challenger_data["h2h_challenges"]["active"] = [
                c for c in challenger_data["h2h_challenges"]["active"] if c["id"] != challenge_id
            ]
            
            save_users(users)
            flash("Challenge declined.", "info")
            break
    
    return redirect(url_for("h2h"))


# -----------------------------
# CHESS GAME
# -----------------------------
@app.route("/chess/<challenge_id>")
@login_required
def chess_game(challenge_id):
    users = load_users()
    email = session["user"]
    user_data = users[email]
    
    # Find the challenge
    challenge = None
    for c in user_data.get("h2h_challenges", {}).get("active", []):
        if c["id"] == challenge_id and c["type"] == "chess_game":
            challenge = c
            break
    
    if not challenge:
        flash("Chess game not found.", "error")
        return redirect(url_for("h2h"))
    
    # Get opponent info
    opponent_email = challenge["opponent"] if challenge["challenger"] == email else challenge["challenger"]
    opponent = users.get(opponent_email, {})
    
    return render_template("chess.html",
                         user=user_data,
                         email=email,
                         challenge=challenge,
                         opponent_name=opponent.get("data", {}).get("first_name", opponent_email.split("@")[0]),
                         opponent_avatar=opponent.get("data", {}).get("avatar", "👤"))


# -----------------------------
# RUN SERVER
# -----------------------------
if __name__ == "__main__":
    app.run(debug=True)


