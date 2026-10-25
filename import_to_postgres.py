"""Idempotent CSV import into PostgreSQL. Run create_tables.sql first."""
import csv
import os
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

COLUMNS = [
    "appid", "name", "type", "is_free", "short_description",
    "detailed_description", "developers", "publishers", "price",
    "genres", "categories", "release_date", "platforms",
    "metacritic_score", "recommendations", "header_image",
]
NUMERIC_COLUMNS = {"metacritic_score", "recommendations"}


def main():
    games_path = BASE_DIR / "Data" / "steam_games.csv"
    tags_path = BASE_DIR / "Data" / "steam_game_tags.csv"
    if not games_path.is_file() or not tags_path.is_file():
        raise FileNotFoundError("Run fetch_steam_data.py first to create both CSV files.")

    values = ", ".join(["%s"] * len(COLUMNS))
    cols = ", ".join(COLUMNS)
    updates = ", ".join(f"{column} = EXCLUDED.{column}" for column in COLUMNS if column != "appid")
    game_query = f"INSERT INTO games ({cols}) VALUES ({values}) ON CONFLICT (appid) DO UPDATE SET {updates}"
    tag_query = "INSERT INTO game_tags (appid, category) VALUES (%s, %s) ON CONFLICT (appid, category) DO NOTHING"

    conn = psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("DB_NAME", "steam_recommender"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.environ["DB_PASSWORD"],
    )
    try:
        games_imported = 0
        tags_imported = 0
        with conn:
            with conn.cursor() as cursor:
                with games_path.open(newline="", encoding="utf-8-sig") as f:
                    for row in csv.DictReader(f):
                        row["is_free"] = (row["is_free"].lower() == "true")
                        for column in NUMERIC_COLUMNS:
                            row[column] = row[column] or None
                        cursor.execute(game_query, tuple(row[column] for column in COLUMNS))
                        games_imported += 1

                with tags_path.open(newline="", encoding="utf-8-sig") as f:
                    for row in csv.DictReader(f):
                        cursor.execute(tag_query, (row["appid"], row["category"]))
                        tags_imported += cursor.rowcount
        print(f"Upserted {games_imported} games; inserted {tags_imported} new game features.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
