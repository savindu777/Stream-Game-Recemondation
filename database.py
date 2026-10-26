
import os

import psycopg2
from dotenv import load_dotenv

load_dotenv() # Raed existing environment variables from a .env file


def get_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME", "steam_recommender"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.environ["DB_PASSWORD"]  # Using environment variable
    )
