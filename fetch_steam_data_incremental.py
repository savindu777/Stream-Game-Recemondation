"""Incrementally collect Steam games without re-fetching existing database/CSV games.
Run from your project folder: python fetch_steam_data_incremental.py
Then: python import_to_postgres.py
"""
import csv
import json
import os
import time
from pathlib import Path

import psycopg2
import requests
# pyrefly: ignore[missing-import]
from dotenv import load_dotenv

BASE = Path(__file__).resolve().parent
DATA = BASE / 'Data'
DATA.mkdir(exist_ok=True)
load_dotenv(BASE / '.env')
KEY = os.getenv('STEAM_API_KEY', '').strip()
LIMIT = int(os.getenv('MAX_DETAIL_REQUESTS', '500'))  # NEW metadata lookups per run
DELAY = max(1.5, float(os.getenv('REQUEST_DELAY_SECONDS', '1.5')))
PAGE_SIZE = 1000
CATALOG = 'https://api.steampowered.com/IStoreService/GetAppList/v1/'
DETAIL = 'https://store.steampowered.com/api/appdetails'
GAME_CSV = DATA / 'steam_games.csv'
TAG_CSV = DATA / 'steam_game_tags.csv'
COLUMNS = ['appid', 'name', 'type', 'is_free', 'short_description',
           'detailed_description', 'developers', 'publishers', 'price',
           'genres', 'categories', 'release_date', 'platforms',
           'metacritic_score', 'recommendations', 'header_image']


def get_json(session, url, params):
    for attempt in range(4):
        try:
            r = session.get(url, params=params, timeout=35)
            if r.status_code in (429, 500, 502, 503, 504):
                pause = min(120, 15 * 2**attempt)
                print(f'HTTP {r.status_code}; pause {pause}s')
                time.sleep(pause)
                continue
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, ValueError) as exc:
            print(f'{type(exc).__name__}; retry {attempt + 1}/4')
            if attempt < 3:
                time.sleep(5 * (attempt + 1))
    return None


def existing_ids():
    ids = set()
    if GAME_CSV.exists():
        with GAME_CSV.open(newline='', encoding='utf-8-sig') as f:
            ids.update(r['appid'] for r in csv.DictReader(f) if r.get('appid'))
    try:
        with psycopg2.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            port=int(os.getenv('DB_PORT', '5432')),
            dbname=os.getenv('DB_NAME', 'steam_recommender'),
            user=os.getenv('DB_USER', 'postgres'),
            password=os.environ['DB_PASSWORD'],
        ) as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT appid FROM games')
                ids.update(row[0] for row in cur.fetchall())
    except psycopg2.Error as exc:
        raise RuntimeError('Cannot read existing games from PostgreSQL; check .env and database') from exc
    return ids


def make_row(app, d):
    appid = str(app['appid'])
    genres = [x.get('description', '').strip() for x in (d.get('genres') or [])]
    categories = [x.get('description', '').strip() for x in (d.get('categories') or [])]
    genres = [x for x in genres if x]
    categories = [x for x in categories if x]
    price = d.get('price_overview') or {}
    row = {
        'appid': appid, 'name': d.get('name') or app.get('name') or f'App {appid}',
        'type': d.get('type') or 'game', 'is_free': bool(d.get('is_free', False)),
        'short_description': d.get('short_description') or '',
        'detailed_description': d.get('detailed_description') or '',
        'developers': ', '.join(d.get('developers') or []),
        'publishers': ', '.join(d.get('publishers') or []),
        'price': 'Free' if d.get('is_free') else price.get('final_formatted', ''),
        'genres': ', '.join(genres), 'categories': ', '.join(categories),
        'release_date': (d.get('release_date') or {}).get('date', ''),
        'platforms': json.dumps(d.get('platforms') or {}),
        'metacritic_score': (d.get('metacritic') or {}).get('score'),
        'recommendations': (d.get('recommendations') or {}).get('total'),
        'header_image': d.get('header_image') or '',
    }
    tags = [(appid, f'Genre: {v}') for v in genres] + [(appid, f'Category: {v}') for v in categories]
    return row, sorted(set(tags))


def main():
    if not KEY:
        raise ValueError('STEAM_API_KEY missing from .env')
    if LIMIT < 1:
        raise ValueError('MAX_DETAIL_REQUESTS must be positive')
    ids = existing_ids()
    print(f'Found {len(ids)} existing games (PostgreSQL and CSV).')
    # Never erase current CSVs. Appending supports interruption and resuming.
    game_has_content = GAME_CSV.exists() and GAME_CSV.stat().st_size > 0
    tag_has_content = TAG_CSV.exists() and TAG_CSV.stat().st_size > 0
    attempted = saved = 0
    last_appid = 0
    failed_catalog = False
    with GAME_CSV.open('a', newline='', encoding='utf-8') as gf, TAG_CSV.open('a', newline='', encoding='utf-8') as tf, requests.Session() as session:
        gw = csv.DictWriter(gf, fieldnames=COLUMNS)
        tw = csv.writer(tf)
        if not game_has_content:
            gw.writeheader()
        if not tag_has_content:
            tw.writerow(['appid', 'category'])
        while attempted < LIMIT:
            params = {'key': KEY, 'include_games': 1, 'include_dlc': 0,
                      'include_software': 0, 'max_results': PAGE_SIZE,
                      'last_appid': last_appid}
            payload = get_json(session, CATALOG, params)
            if payload is None:
                print('Unable to load the next catalog page; stopping safely.')
                failed_catalog = True
                break
            apps = payload.get('response', {}).get('apps') or []
            if not apps:
                print('Reached end of catalog.')
                break
            print(f'Catalog page: {len(apps)} entries, after appid={last_appid}')
            next_last = int(apps[-1]['appid'])
            if next_last <= last_appid:
                print('Catalog pagination did not advance; stopping.')
                break
            for app in apps:
                if attempted >= LIMIT:
                    break
                appid = str(app.get('appid', ''))
                if not appid or appid in ids:
                    continue
                attempted += 1
                time.sleep(DELAY)
                payload = get_json(session, DETAIL, {'appids': appid, 'l': 'english', 'cc': 'us'})
                if payload is None:
                    print(f'[{attempted}/{LIMIT}] Failed detail request {appid}')
                    continue
                info = payload.get(appid) or {}
                d = info.get('data') or {}
                if not info.get('success') or d.get('type') != 'game':
                    continue
                row, tags = make_row(app, d)
                gw.writerow(row)
                tw.writerows(tags)
                gf.flush()
                tf.flush()
                ids.add(appid)
                saved += 1
                print(f'[{attempted}/{LIMIT}] Saved: {row["name"]} ({appid})')
            last_appid = next_last
    print(f'New metadata requests: {attempted}. New valid games saved: {saved}.')
    print('Run: python import_to_postgres.py')
    if failed_catalog:
        print('Catalog request failed. You may retry later; CSV progress is retained.')


if __name__ == '__main__':
    main()
