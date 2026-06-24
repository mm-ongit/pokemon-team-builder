# Import dependencies
from flask import Flask, render_template, redirect, url_for, flash, request, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from pathlib import Path
import requests

# Create the application object
app = Flask(__name__)
app.config["SECRET_KEY"] = "dev_secret_change_later"
app.config["SESSION_PERMANENT"] = False

# Database Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "database" / "app.db"

# Helper fuctions to ensure DB and users table exist when server is run


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = get_db_connection()
    conn.execute("""CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL);""")
    conn.execute("""CREATE TABLE IF NOT EXISTS teams (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 user_id INTEGER NOT NULL,
                 name TEXT NOT NULL,
                 date_created TEXT NOT NULL DEFAULT (datetime('now')),
                 FOREIGN KEY (user_id) REFERENCES users (id));
                 """)
    conn.execute("""CREATE TABLE IF NOT EXISTS team_pokemon (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 team_id INTEGER NOT NULL,
                 slot INTEGER NOT NULL,
                 pokemon_id INTEGER NOT NULL,
                 pokemon_name TEXT NOT NULL,
                 sprite_url TEXT,
                 types TEXT NOT NULL,
                 FOREIGN KEY (team_id) REFERENCES teams (id),
                 UNIQUE (team_id, slot));
                 """)

    conn.commit()
    conn.close()


# Create routes, define functions to call when route is accessed

# -- Render the home page
@app.route("/")
def home():
    return render_template("home.html")

# -- if GET render the register page, if POST


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or not password:
            flash("Email and password are required.")
            return redirect(url_for("register"))

        password_hash = generate_password_hash(password)

        try:
            conn = get_db_connection()
            conn.execute(
                "INSERT INTO users (email, password_hash) VALUES (?, ?)", (
                    email, password_hash)
            )
            conn.commit()
            conn.close()
        except sqlite3.IntegrityError:
            flash("That email is already registered. Try logging in.")
            return redirect(url_for("register"))

        flash("Account created! Please log in.")
        return redirect(url_for("login"))

    return render_template("register.html")

# -- if GET render the login page, if POST determine what happens to data submitted through the login form


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        # Connect to app.db and pull user data
        conn = get_db_connection()
        user = conn.execute(
            "SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        conn.close()

        if user is None:
            flash("No account associated with that email.")
            return redirect(url_for("login"))

        if not check_password_hash(user["password_hash"], password):
            flash("Incorrect password.")
            return redirect(url_for("login"))

        # Store user's id and email in the session cookie and makes it expire with browser session
        session["user_id"] = user["id"]
        session["user_email"] = user["email"]
        session.permanent = False

        flash("Logged in successfully.")
        return redirect(url_for("team"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.")
    return redirect(url_for("home"))


@app.route("/team")
def team():
    if not session.get("user_id"):
        flash("Must be logged in to access the Team Builder.")
        return redirect(url_for("login"))

    return render_template("team.html")


@app.route("/api/pokemon/<name>")
def api_pokemon(name):
    # Basic protection for the route
    if not session.get("user_id"):
        return jsonify({"error": "Unauthorized"}), 401

    # Clean user submission
    name = name.strip().lower()
    # If no name entered return error message
    if not name:
        return jsonify({"error": "Missing Pokémon name"}), 400

    # Append user submission to API url, store url
    url = f"https://pokeapi.co/api/v2/pokemon/{name}"
    # Ping API to fetch webpage located at url with requests, store response
    r = requests.get(url, timeout=10)

    # Check response for errors
    if r.status_code == 404:
        return jsonify({"error": "Pokémon not found"}), 404
    if not r.ok:
        return jsonify({"error": "PokéAPI error"}), 502

    # Store Pokémon JSON data in response
    data = r.json()

    # Create JSON dictionary containing selected data
    result = {
        "id": data["id"],  # Get Pokêmon id number
        "name": data["name"],  # Get Pokémon name
        # Get front facing Pokémon sprite
        "sprite": (data.get("sprites") or {}).get("front_default"),
        # Get Pokémon type(s)
        "types": [t["type"]["name"] for t in data["types"]]
    }

    # Return selected Pokémon JSON data for use with JavaScript
    return jsonify(result)

# Saves teams to the database


@app.route("/api/teams", methods=["POST"])
def api_save_team():
    if not session.get("user_id"):
        return jsonify({"error": "Unauthorized"}), 401

    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or {}).strip()
    pokemon = payload.get("pokemon") or []

    if not name:
        return jsonify({"error": "Team name is required"}), 400
    if not isinstance(pokemon, list) or len(pokemon) == 0:
        return jsonify({"error": "Add at least 1 Pokémon"}), 400
    if len(pokemon) > 6:
        return jsonify({"error": "Team cannot exceed 6 Pokémon"}), 400

    required_keys = {"id", "name", "sprite", "types"}
    for i, p in enumerate(pokemon, start=1):
        if not isinstance(p, dict) or not required_keys.issubset(p.keys()):
            return jsonify({"error": f"Invalid Pokémon data at slot {i}"}), 400

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(
        "INSERT INTO teams (user_id, name) VALUES (?, ?)", (
            session["user_id"], name)
    )
    team_id = cur.lastrowid

    for slot, p in enumerate(pokemon, start=1):
        types_str = ", ".join(p["types"])
        cur.execute(
            """
            INSERT INTO team_pokemon (team_id, slot, pokemon_id, pokemon_name, sprite_url, types)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (team_id, slot, p["id"], p["name"], p.get("sprite"), types_str)
        )

    conn.commit()
    conn.close()

    return jsonify({"ok": True, "team_id": team_id})


@app.route("/my-teams")
def my_teams():
    if not session.get("user_id"):
        flash("Please log in to view your teams")
        return redirect(url_for("login"))

    conn = get_db_connection()
    teams = conn.execute(
        "SELECT id, name, date_created FROM teams WHERE user_id = ? ORDER BY id DESC",
        (session["user_id"],),
    ).fetchall()
    conn.close()

    return render_template("my_teams.html", teams=teams)


@app.route("/teams/<int:team_id>")
def view_team(team_id):
    if not session.get("user_id"):
        flash("Please log in to view teams")
        return redirect(url_for("login"))

    conn = get_db_connection()
    team_row = conn.execute(
        "SELECT * FROM teams WHERE id = ? AND user_id = ?",
        (team_id, session["user_id"]),
    ).fetchone()

    if team_row is None:
        conn.close()
        flash("Team  not found")
        return redirect(url_for("my_teams"))

    pokemon_rows = conn.execute(
        "SELECT * FROM team_pokemon WHERE team_id = ? ORDER BY slot ASC",
        (team_id,),
    ).fetchall()
    conn.close

    return render_template("view_team.html", team=team_row, pokemon=pokemon_rows)


# Initialiize database, auto-restart app when code is changed, and initiate web server at 127.0.0.1 using port 5001 and a mobile server at 0.0.0.0 using port 5001
if __name__ == "__main__":
    init_db()
    app.run(debug=True, host="0.0.0.0", port=5001)
