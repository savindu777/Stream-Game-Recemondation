from fastapi import FastAPI, HTTPException, Query
from psycopg2.extras import RealDictCursor
from functools import lru_cache
from recommendation_model import GameRecommender
from pydantic import BaseModel, Field
from pathlib import Path
from fastapi.responses import FileResponse

from database import get_connection

app = FastAPI(title="Steam Game Recommender")


class FavoriteGames(BaseModel):

    appids: list[str] = Field(
        min_length=1,
        max_length=30
    )


@lru_cache(maxsize=1)
def get_model():

    model = GameRecommender()

    model.load_data()

    return model



BASE_DIR = Path(__file__).resolve().parent


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(BASE_DIR / "index.html")



@app.get("/games")
def get_games(
    limit: int = Query(default=20, ge=1, le=100)
):

    conn = get_connection()

    try:
        with conn.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:

            cursor.execute(
                """
                SELECT appid, name, genres, categories
                FROM games
                ORDER BY name
                LIMIT %s
                """,
                (limit,)
            )

            games = cursor.fetchall()

            return {
                "count": len(games),
                "games": games
            }

    finally:
        conn.close()


@app.get("/games/search")
def search_games(
    name: str = Query(min_length=1),
    limit: int = Query(default=20, ge=1, le=100)
):
    conn = get_connection()

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:

            cursor.execute(
                """
                SELECT appid, name, genres, categories
                FROM games
                WHERE name ILIKE %s
                ORDER BY name
                LIMIT %s
                """,
                (f"%{name}%", limit)
            )

            results = cursor.fetchall()

            return {
                "count": len(results),
                "results": results
            }

    finally:
        conn.close()



@app.get("/games/{appid}")
def get_game(appid: str):

    conn = get_connection()

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:

            cursor.execute(
                """
                SELECT *
                FROM games
                WHERE appid = %s
                """,
                (appid,)
            )

            game = cursor.fetchone()

            if game is None:
                raise HTTPException(
                    status_code=404,
                    detail="Game not found"
                )

            return game

    finally:
        conn.close()


@app.get("/recommend/{appid}")
def recommend_game(
    appid: str,
    top_n: int = Query(default=10, ge=1, le=50)
):

    model = get_model()

    if appid not in model.appids:
        raise HTTPException(
            status_code=404,
            detail="Game not found or has no features"
        )

    results = model.recommend(
        favorite_appids=[appid],
        top_n=top_n
    )

    return {
        "selected_game": {
            "appid": appid,
            "name": model.games[appid]
        },
        "recommendations": results
    }



@app.post("/recommend")
def recommend_multiple(favorites: FavoriteGames):

    model = get_model()

    unknown = [
        appid
        for appid in favorites.appids
        if appid not in model.appids
    ]

    if unknown:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "Some games were not found or have no features",
                "appids": unknown
            }
        )

    results = model.recommend(
        favorite_appids=favorites.appids,
        top_n=10
    )

    return {
        "favorite_games": favorites.appids,
        "recommendations": results
    }
@app.get("/health")
def health():

    model = get_model()

    return {
        "status": "ok",
        "games_with_features": len(model.appids),
        "unique_features": len(model.encoder.classes_)
    }

    
