from flask import Flask, render_template, request
from dotenv import load_dotenv
import os
import requests as req

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

    games = data.get("results", [])[:3]

    return render_template("index.html", games=games)

if __name__ == "__main__":
    app.run(debug=True)