
from flask import Flask, render_template, request, redirect, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import json, os, datetime, openai

app = Flask(__name__)
app.secret_key = "ULTIMATE_SECRET_KEY"

openai.api_key = os.getenv("OPENAI_API_KEY")

DB = "users.json"

def load():
    if not os.path.exists(DB):
        return {}
    return json.load(open(DB))

def save(data):
    json.dump(data, open(DB, "w"), indent=2)
@app.route("/")
def base():
    return render_template("base.html")
@app.route("/", methods=["GET","POST"])
def login():
    users = load()
    if request.method=="POST":
        u=request.form["username"]
        p=request.form["password"]
        if u in users and check_password_hash(users[u]["password"],p):
            session["user"]=u
            return redirect("/dashboard")
        return render_template("login.html", error="Invalid credentials")
    return render_template("login.html")

@app.route("/register", methods=["GET","POST"])
def register():
    users=load()
    if request.method=="POST":
        u=request.form["username"]
        users[u]={
            "password":generate_password_hash(request.form["password"]),
            "data":{}
        }
        save(users)
        return redirect("/")
    return render_template("register.html")

@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/")
    return render_template("dashboard.html")

@app.route("/save", methods=["POST"])
def save_all():
    users=load()
    users[session["user"]]["data"]=request.json
    save(users)
    return jsonify({"status":"saved"})

@app.route("/ai", methods=["POST"])
def ai():
    prompt=request.json["prompt"]
    res=openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role":"user","content":prompt}]
    )
    return jsonify(res.choices[0].message.content)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


app.run(debug=True)
