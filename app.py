from flask import Flask, render_template, request, redirect, url_for
from dotenv import load_dotenv
import os
import requests as req
import sqlite3

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
api_key = os.getenv("RAWG_KEY")

app = Flask(__name__)

genre_map = {
    "Action": "action",
    "Adventure": "adventure",
    "Family": "family,card,board-games,educational",
    "Puzzle": "puzzle",
    "Role-Playing(RPG)": "role-playing-games-rpg",
    "Shooter/FPS": "shooter",
    "Simulation": "simulation",
    "Sports & Racing": "sports,racing,fighting",
    "Strategy": "strategy"
}

platform_map = {
    "PC": "4",
    "Playstation 4": "18",
    "Playstation 5": "187",
    "Xbox One": "1",
    "Xbox Series S": "186",
    "Xbox Series X": "186",
    "Nintendo Switch": "7"
}

perspective_map = {
    "First Person": "first-person",
    "Isometric": "isometric",
    "Side Scrolling/2D": "2d",
    "Third Person": "third-person",
    "Top-Down": "top-down",
    "Virtual Reality": "vr"
}

difficulty_map = {
    "Easy": "relaxing",
    "Moderate": "",
    "Hard": "difficult",
    "Brutal": "hardcore"
}

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "games.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS played_games (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_name TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS favorites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_name TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()

init_db()

def get_played_games():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT game_name FROM played_games")
    rows = cursor.fetchall()
    conn.close()
    return set(row[0] for row in rows)

def add_played_game(game_name):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO played_games (game_name) VALUES (?)", (game_name,))
    conn.commit()
    conn.close()

def get_favorite():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT game_name FROM favorites")
    rows = cursor.fetchall()
    conn.close()
    return set(row[0] for row in rows)

def add_favorite(game_name):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO favorites (game_name) VALUES (?)", (game_name,))
    conn.commit()
    conn.close()

def remove_favorite(game_name):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM favorites WHERE game_name = ?", (game_name,))
    conn.commit()
    conn.close()

def get_ai_explanation(game_name, genre, platform, keyword):
    keyword_part = f" with a focus on '{keyword}'" if keyword else ""
    return f"Recommended as a top {genre.lower()} title on {platform}{keyword_part} that matches your search criteria."

@app.route("/played", methods=["POST"])
def mark_played():
    game_name = request.form.get("game_name")
    add_played_game(game_name)
    return redirect(url_for("index"))

@app.route("/favorite", methods=["POST"])
def toggle_favorite():
    game_name = request.form.get("game_name")
    current_favorites = get_favorite()
    if game_name in current_favorites:
        remove_favorite(game_name)
    else:
        add_favorite(game_name)
    return redirect(url_for("index"))

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/recommend", methods=["POST"])
def recommend():
    genre_selection = request.form.get("genre")
    platform_selection = request.form.get("platform")
    keyword = request.form.get("keyword", "")

    if not genre_selection or not platform_selection:
        return render_template("index.html", error="Please select a genre and platform!")
    
    genre = genre_map.get(genre_selection, "action")
    platform = platform_map.get(platform_selection)

    url = f"https://api.rawg.io/api/games?key={api_key}&genres={genre}&platforms={platform}&search={keyword}&page_size=10"
    response = req.get(url)
    data = response.json()

    played = get_played_games()
    favorites = get_favorite()

    games = [g for g in data.get("results", []) if g['name'] not in played][:3]

    recommendations = []
    for game in games:
        explanation = get_ai_explanation(game['name'], genre_selection, platform_selection, keyword)
        recommendations.append({
            "name": game['name'],
            "rating": game.get('rating', 0),
            "explanation": explanation,
            "is_favorite": game['name'] in favorites
        })

    return render_template("index.html", games=recommendations)

if __name__ == "__main__":
    app.run(debug=True)