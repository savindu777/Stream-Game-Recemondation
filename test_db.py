"""Read-only database connection test."""
import os
from dotenv import load_dotenv
import psycopg2
load_dotenv()
with psycopg2.connect(
    host=os.getenv("DB_HOST", "localhost"),
    port=int(os.getenv("DB_PORT", "5432")),
    dbname=os.getenv("DB_NAME", "steam_recommender"),
    user=os.getenv("DB_USER", "postgres"),
    password=os.environ["DB_PASSWORD"],
) as conn:
    with conn.cursor() as cursor:
        for table in ("games", "game_tags", "users", "user_games", "user_recommendations"):
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            print(f"{table}: {cursor.fetchone()[0]} rows")
        cursor.execute("SELECT appid, name, genres FROM games ORDER BY name LIMIT 5")
        print("Example games:")
        for row in cursor.fetchall():
            print(row)
