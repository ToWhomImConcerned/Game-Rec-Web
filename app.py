from flask import Flask, render_template, request, redirect, url_for, session
from dotenv import load_dotenv
import os
import requests as req
import sqlite3

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
api_key = os.getenv("RAWG_KEY")

app = Flask(__name__)
app.secret_key = "GameLab"
details_cache = {}
search_cache = {}

genre_map = {
    "Action": "action",
    "Adventure": "adventure",
    "Family": "family,card,board-games,educational",
    "Puzzle": "puzzle",
    "Role-Playing(RPG)": "role-playing-games-rpg",
    "Shooter/FPS": "shooter",
    "Simulation": "simulation",
    "Sports & Racing": "sports,racing,fishing",
    "Strategy": "strategy"
}

platform_map = {
    "PC": "4",
    "Playstation 4": "18",
    "Playstation 5": "187",
    "Xbox One": "1",
    "Nintendo Switch": "7"
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
        CREATE TABLE IF NOT EXISTS ratings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_name TEXT NOT NULL UNIQUE,
            rating INTEGER NOT NULL,
            rawg_id INTEGER
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

def add_or_update_rating(game_name, rating, rawg_id=None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO ratings (game_name, rating, rawg_id)
        VALUES (?, ?, ?)
        ON CONFLICT(game_name) DO UPDATE SET rating=excluded.rating
    """, (game_name, rating, rawg_id))
    conn.commit()
    conn.close()

def get_ratings():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT game_name, rating, rawg_id FROM ratings ORDER BY rating DESC")
    rows = cursor.fetchall()
    conn.close()
    return rows

def delete_rating(game_name):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM ratings WHERE game_name = ?", (game_name,))
    conn.commit()
    conn.close()

# ─── ROUTES ───────────────────────────────────────────────────────────────────

@app.route("/")
def landing():
    return render_template("landing.html")

@app.route("/choice", methods=["POST"])
def choice():
    path = request.form.get("path")
    if path == "taste":
        return redirect(url_for("taste"))
    else:
        return redirect(url_for("new_search"))

@app.route("/taste")
def taste():
    ratings = get_ratings()
    return render_template("taste.html", ratings=ratings)

@app.route("/taste_recommend", methods=["POST"])
def taste_recommend():
    ratings = get_ratings()

    if not ratings:
        return render_template("taste.html", ratings=ratings, error="Add some rated games first!")

    top_games = [(name, score, rawg_id) for name, score, rawg_id in ratings if rawg_id][:3]

    if not top_games:
        return render_template("taste.html", ratings=ratings, error="Rate some games through search first so we have enough info to go on.")

    played = get_played_games()
    rated_games = {name for name, score, rawg_id in ratings}
    seen = set()
    pool = []

    for name, score, rawg_id in top_games:
        url = f"https://api.rawg.io/api/games/{rawg_id}?key={api_key}"
        response = req.get(url)
        if response.status_code != 200:
            continue
        data = response.json()
        genre_pool = set()
        for genre in data.get("genres", []):
            genre_pool.add(genre["slug"])

        if not genre_pool:
            continue

        genres_param = ",".join(list(genre_pool)[:3])
        url = f"https://api.rawg.io/api/games?key={api_key}&genres={genres_param}&ordering=-rating&page_size=20&metacritic=80,100"
        response = req.get(url)
        data = response.json()

        for game in data.get("results", []):
            if game['name'] not in played and game['name'] not in seen and game['name'] not in rated_games:
                seen.add(game['name'])
                pool.append({
                    "name": game['name'],
                    "rating": game.get('rating', 0),
                    "rawg_id": game.get('id'),
                })

    if not pool:
        return render_template("taste.html", ratings=ratings, error="Couldn't find suggestions this time — try rating more games.")
    
    pool = pool[:21]
    session['taste_pool'] = pool
    session['taste_offset'] = 0

    displayed = pool[:3]
    has_more = len(pool) >=6
    is_end = False

    return render_template("taste.html", ratings=ratings, games=displayed, has_more=has_more, is_end = is_end)

@app.route("/more_taste", methods=["POST"])
def more_taste():
    ratings = get_ratings()
    pool = session.get('taste_pool', [])
    offset = session.get('taste_offset', 0)

    if offset == 0:
        new_offset = 3
        displayed = pool[:6]
    else:
        new_offset = offset + 3
        displayed = pool[new_offset - 3:new_offset + 3]

    session['taste_offset'] = new_offset

    has_more = (new_offset + 6) <= len(pool)
    is_end = not has_more

    return render_template("taste.html", ratings=ratings, games=displayed, has_more=has_more, is_end=is_end)

@app.route("/autocomplete")
def autocomplete():
    query = request.args.get("q", "")
    if len(query) < 3:
        return {"results": []}
    
    url = f"https://api.rawg.io/api/games?key={api_key}&search={query}&page_size=6"
    response = req.get(url)
    data = response.json()

    names = [g['name'] for g in data.get("results", [])]
    return {"results": names}

@app.route("/search")
def new_search():
    return render_template("search.html")

@app.route("/recommend", methods=["POST"])
def recommend():
    genre_selection = request.form.get("genre")
    platform_selection = request.form.get("platform")
    keyword = request.form.get("keyword", "")

    if not genre_selection or not platform_selection:
        return render_template("search.html", error="Please select a genre and platform!")
    
    cache_key = f"{genre_selection}_{platform_selection}_{keyword}"
    if cache_key in search_cache:
        pool = search_cache[cache_key]
        played = get_played_games()
        pool = [g for g in pool if g['name'] not in played]
    else:
        if genre_selection == "Horror":
            genre = "action"
            tags = "&tags=horror"
        else:
            genre = genre_map.get(genre_selection, "action")
            tags = ""

        platform = platform_map.get(platform_selection)
        search_param = f"&search={keyword}" if keyword else ""

        url = f"https://api.rawg.io/api/games?key={api_key}&genres={genre}&platforms={platform}{tags}{search_param}&page_size=21"
        response = req.get(url)
        data = response.json()

        played = get_played_games()
        all_games = [g for g in data.get("results", []) if g['name'] not in played]

        pool = []
        for game in all_games:
            pool.append({
                "name": game['name'],
                "rating": game.get('rating', 0),
                "rawg_id": game['id'],
            })

        search_cache[cache_key] = pool

    session['search_pool'] = pool
    session['search_offset'] = 0
    session['last_search'] = {
        "genre_selection": genre_selection,
        "platform_selection": platform_selection,
        "keyword": keyword,
        "genre": genre_map.get(genre_selection, "action") if genre_selection != "Horror" else "action",
        "platform": platform_map.get(platform_selection),
        "tags": "&tags=horror" if genre_selection == "Horror" else ""
    }
    
    displayed = pool[:3]
    session['last_results'] = displayed
    has_more = len(pool) > 3
    is_end = False

    return render_template("search.html", games=displayed, has_more=has_more, is_end=is_end)

@app.route("/details/<int:rawg_id>")
def game_details(rawg_id):
    if rawg_id in details_cache:
        return{"details": details_cache[rawg_id]}
    
    url = f"https://api.rawg.io/api/games/{rawg_id}?key={api_key}"
    response = req.get(url)
    data = response.json()

    details = {
        "name": data.get("name", "Unknown"),
        "background_image": data.get("background_image", ""),
        "released": data.get("released", "Unknown"),
        "metacritic": data.get("metacritic", None),
        "rawg_rating": data.get("rating", None),
        "esrb": data.get("esrb_rating", {}).get("name", "Not Rated") if data.get("esrb_rating") else "Not Rated",
        "developers": ", ".join([d["name"] for d in data.get("developers", [])]) or "unknown",
        "publishers": ", ".join([p["name"] for p in data.get("publishers", [])]) or "Unknown",
        "genres": ", ".join([g["name"] for g in data.get("genres", [])]) or "Unknown",
        "platforms": ", ".join([p["platform"]["name"] for p in data.get("platforms", [])]) or "Unknown",
        "website": data.get("website", ""),
        "description": data.get("description_raw", ""),
    }

    details_cache[rawg_id] = details
    return {"details": details}

@app.route("/more", methods=['POST'])
def more():
    pool = session.get('search_pool', [])
    offset = session.get('search_offset', 0)

    if offset == 0:
        new_offset = 3
        displayed = pool[:6]
    else:
        new_offset = offset + 3
        displayed = pool[new_offset - 3:new_offset + 3]

    session['search_offset'] = new_offset
    session['last_results'] = displayed[-3:]

    has_more = (new_offset + 6) <= len(pool)
    is_end = not has_more

    return render_template("search.html", games=displayed, has_more=has_more, is_end=is_end)

@app.route("/played", methods=["POST"])
def mark_played():
    game_name = request.form.get("game_name")
    source = request.form.get("source", "new_search")
    add_played_game(game_name)

    if source == "new_search":
        pool = session.get('search_pool', [])
        pool = [g for g in pool if g['name'] != game_name]
        session['search_pool'] = pool

        games = session.get('last_results', [])
        games = [g for g in games if g['name'] != game_name]

        last_search = session.get('last_search', {})
        if last_search and len(games) < 3:
            played = get_played_games()
            current_names = [g['name'] for g in games]
            keyword = last_search['keyword']
            search_param = f"&search={keyword}" if keyword else ""
            url = f"https://api.rawg.io/api/games?key={api_key}&genres={last_search['genre']}&platforms={last_search['platform']}{last_search['tags']}{search_param}&page_size=30&ordering=-added"
            response = req.get(url)
            data = response.json()

            for g in data.get("results", []):
                if g['name'] not in played and g['name'] not in current_names:
                    games.append({
                        "name": g['name'],
                        "rating": g.get('rating', 0),
                        "rawg_id": g['id'],
                    })
                    break

        session['last_results'] = games
        return render_template("search.html", games=games, has_more=len(pool) > 3, is_end=False)
    
    return redirect(url_for(source))

@app.route("/rate", methods=["POST"])
def rate_game():
    game_name = request.form.get("game_name")
    rating = request.form.get("rating", "0")
    rawg_id = request.form.get("rawg_id")
    source = request.form.get("source", "taste")

    if not rating or int(rating) == 0:
        ratings = get_ratings()
        return render_template("taste.html", ratings=ratings, error="Please select a star rating first.")

    if not rawg_id:
        search_url = f"https://api.rawg.io/api/games?key={api_key}&search={game_name}&page_size=1"
        response = req.get(search_url)
        data = response.json()
        results = data.get("results", [])
        if results:
            rawg_id = results[0]["id"]

    add_or_update_rating(game_name, int(rating), rawg_id if rawg_id else None)

    if source == "new_search":
        games = session.get('last_results', [])
        pool = session.get('search_pool', [])
        return render_template("search.html", games=games, has_more=len(pool) > 3, is_end=False)
    
    return redirect(url_for("taste"))

@app.route("/delete_rating", methods=["POST"])
def remove_rating():
    game_name = request.form.get("game_name")
    delete_rating(game_name)
    return redirect(url_for("taste"))

if __name__ == "__main__":
    app.run(debug=True)