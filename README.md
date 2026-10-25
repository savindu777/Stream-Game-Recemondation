# Steam Game Recommender — Steam API + PostgreSQL Starter

The original repo is https://github.com/pinstripezebra/recommender_system. This is a **new data-ingestion starter**, not a copy of its application, and creates compatible table names for its recommendation pipeline. The original source still needs small changes before it can be run end-to-end.

## 1. Create PostgreSQL database

Open **pgAdmin 4** > Servers > PostgreSQL > Databases. Right-click **Databases**, choose **Create > Database**, and use `steam_recommender` as the database name. Save.

Select the new database, open **Query Tool**, open `create_tables.sql`, and execute (F5).

The script creates `users`, `games`, `game_tags`, `user_games`, `user_recommendations`, and `game_similarity`. No `DROP TABLE` is run.

## 2. Python setup (Windows PowerShell)

In the extracted project directory:

```powershell
py --list
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Using `python.exe` directly avoids PowerShell script-activation policy errors.

## 3. Steam API key and PostgreSQL credentials

Sign in at https://steamcommunity.com/dev/apikey and request a user Steam Web API key if you are eligible. Never paste or commit the key. Copy `.env.example` to `.env`:

```powershell
Copy-Item .env.example .env
```

Edit `.env`. Enter your key and PostgreSQL password. The project uses a public Steam Web API host for IStoreService because the partner host requires a publisher key.

## 4. Fetch app metadata to CSV

```powershell
.\.venv\Scripts\python.exe fetch_steam_data.py
```

Two files are created:

- `Data/steam_games.csv` — game metadata: `appid`, name, descriptions, developers, genres, categories, platforms, price, etc.
- `Data/steam_game_tags.csv` — one row per (`appid`, feature), with `Genre:` or `Category:` prefixes.

The initial request scans the first catalog page and attempts at most `MAX_DETAIL_REQUESTS=50` detailed lookups. Some entries may be skipped because of missing Store data. Increase limits carefully and obey Steam's terms/rate limits. The Store `appdetails` endpoint is separate from IStoreService, and its availability may vary.

## 5. Import to PostgreSQL

```powershell
.\.venv\Scripts\python.exe import_to_postgres.py
.\.venv\Scripts\python.exe test_db.py
```

Re-running imports updates existing `games` by `appid` and avoids duplicate `(appid,category)` rows. It does not delete any existing user profiles or recommendations. It does not prune tags that were removed upstream.

## 6. Verify in pgAdmin

```sql
SELECT COUNT(*) FROM games;
SELECT COUNT(*) FROM game_tags;
SELECT appid, name, genres, categories FROM games LIMIT 10;
SELECT g.name, t.category
FROM games g
JOIN game_tags t ON g.appid = t.appid
ORDER BY g.name
LIMIT 20;
```

## 7. Continue with the recommender

The original `src/similarity_pipeline.py` queries a `category` table while the loader creates `game_tags`; change that query to `SELECT appid, category FROM game_tags`. The original `src/models.py` maps game model to `optigame_products` although ingestion creates `games`; correct it to `games`. The original `src/main.py` uses `Internal_Database_Url` while its README documents `External_Database_Url`; set a consistent local connection URL when integrating FastAPI. The original loader drops tables and uses a Render SSL mode; **do not run it** on a database you wish to preserve.

### Notes

- These features are store-provided **genres and categories**; they are *not* crowd-sourced Steam community tags.
- The script reads US price presentation (`cc=us`), not user-local prices. Missing prices remain blank, not necessarily free.
- User-owned game libraries require separate API calls and may be limited by Steam profile privacy settings.
- The `users.password` column is kept for compatibility; always store a strong password hash, never plaintext.
- Prices are stored as display strings to match the repository; for price filtering or analytics, also store numeric minor units + currency.
