"""Collect Steam store games to CSV for a content-based recommender.

Steam's old ISteamApps/GetAppList/v2 endpoint is deprecated. This script
uses the API-key-protected IStoreService/GetAppList/v1 method instead.
The Store appdetails endpoint is a separate endpoint for richer metadata.
"""
import csv
import json
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "Data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
load_dotenv(BASE_DIR / ".env")

STEAM_API_KEY = os.getenv("STEAM_API_KEY", "").strip()
MAX_DETAIL_REQUESTS = int(os.getenv("MAX_DETAIL_REQUESTS", "50"))
REQUEST_DELAY_SECONDS = max(1.0, float(os.getenv("REQUEST_DELAY_SECONDS", "1.5")))

CATALOG_ENDPOINT = "https://api.steampowered.com/IStoreService/GetAppList/v1/"
DETAIL_ENDPOINT = "https://store.steampowered.com/api/appdetails"

CSV_COLUMNS = [
    "appid", "name", "type", "is_free", "short_description",
    "detailed_description", "developers", "publishers", "price",
    "genres", "categories", "release_date", "platforms",
    "metacritic_score", "recommendations", "header_image",
]


def request_json(session, url, params):
    """Try a few times on transient errors; never print the secret key."""
    for attempt in range(3):
        try:
            response = session.get(url, params=params, timeout=30)
            if response.status_code in (429, 500, 502, 503, 504):
                pause = 10 * (attempt + 1)
                print(f"Steam returned HTTP {response.status_code}; backing off {pause}s")
                time.sleep(pause)
                continue
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            print(f"Request attempt {attempt + 1}/3 failed: {type(exc).__name__}")
            if attempt < 2:
                time.sleep(2 * (attempt + 1))
            else:
                return None
    return None


def fetch_catalog(session):
    if not STEAM_API_KEY or STEAM_API_KEY.startswith("PUT_YOUR"):
        raise RuntimeError("Add a real STEAM_API_KEY to your .env file.")

    # The catalog endpoint is paginated. For a first prototype, retrieve a
    # single page, then look up detailed metadata for a limited number.
    params = {
        "key": STEAM_API_KEY,
        "include_games": 1,
        "include_dlc": 0,
        "include_software": 0,
        "max_results": max(1000, min(50000, MAX_DETAIL_REQUESTS * 4)),
    }
    payload = request_json(session, CATALOG_ENDPOINT, params)
    if payload is None:
        raise RuntimeError("Could not retrieve Steam catalog. Check key/access, network and rate limits.")
    apps = payload.get("response", {}).get("apps", [])
    if not apps:
        raise RuntimeError(f"Steam returned no apps; unexpected response keys: {list(payload)}")
    print(f"Received {len(apps)} game IDs from the first catalog page")
    return apps


def collect_games(session, apps):
    game_rows = []
    tag_rows = set()
    checked = 0
    for app in apps:
        if checked >= MAX_DETAIL_REQUESTS:
            break
        appid = app.get("appid")
        if not appid:
            continue
        checked += 1
        # Pause for every metadata lookup, including missing/failed apps.
        time.sleep(REQUEST_DELAY_SECONDS)
        payload = request_json(session, DETAIL_ENDPOINT, {"appids": appid, "l": "english", "cc": "us"})
        if payload is None:
            continue
        entry = payload.get(str(appid), {})
        if not entry.get("success"):
            continue
        details = entry.get("data") or {}
        if details.get("type") != "game":
            continue

        genres = [g.get("description", "").strip() for g in details.get("genres", [])]
        categories = [c.get("description", "").strip() for c in details.get("categories", [])]
        genres = [value for value in genres if value]
        categories = [value for value in categories if value]
        for genre in genres:
            tag_rows.add((str(appid), f"Genre: {genre}"))
        for category in categories:
            tag_rows.add((str(appid), f"Category: {category}"))

        price_data = details.get("price_overview") or {}
        price = "Free" if details.get("is_free") else price_data.get("final_formatted", "")
        row = {
            "appid": str(appid),
            "name": details.get("name") or app.get("name", f"App {appid}"),
            "type": details.get("type"),
            "is_free": details.get("is_free", False),
            "short_description": details.get("short_description") or "",
            "detailed_description": details.get("detailed_description") or "",
            "developers": ", ".join(details.get("developers") or []),
            "publishers": ", ".join(details.get("publishers") or []),
            "price": price,
            "genres": ", ".join(genres),
            "categories": ", ".join(categories),
            "release_date": (details.get("release_date") or {}).get("date", ""),
            "platforms": json.dumps(details.get("platforms") or {}),
            "metacritic_score": (details.get("metacritic") or {}).get("score"),
            "recommendations": (details.get("recommendations") or {}).get("total"),
            "header_image": details.get("header_image") or "",
        }
        game_rows.append(row)
        print(f"[{checked}/{MAX_DETAIL_REQUESTS}] {row['name']} (appid={appid})")
    return game_rows, sorted(tag_rows)


def save_csv(games, tags):
    if not games:
        raise RuntimeError("No valid games were downloaded; existing CSV files were not replaced.")
    with (DATA_DIR / "steam_games.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(games)
    with (DATA_DIR / "steam_game_tags.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["appid", "category"])
        writer.writerows(tags)
    print(f"Saved {len(games)} games and {len(tags)} game features into Data/")


def main():
    if MAX_DETAIL_REQUESTS < 1:
        raise ValueError("MAX_DETAIL_REQUESTS must be at least 1.")
    with requests.Session() as session:
        apps = fetch_catalog(session)
        games, tags = collect_games(session, apps)
        save_csv(games, tags)


if __name__ == "__main__":
    main()
