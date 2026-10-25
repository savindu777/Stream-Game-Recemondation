-- Run against the steam_recommender database using pgAdmin 4 Query Tool.
-- No existing table is dropped. Requires PostgreSQL 13+ for gen_random_uuid().

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(255) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,  -- store only a strong password hash
    email VARCHAR(255) UNIQUE NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'user'
);

CREATE TABLE IF NOT EXISTS games (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    appid VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    type VARCHAR(255),
    is_free BOOLEAN,
    short_description TEXT,
    detailed_description TEXT,
    developers TEXT,
    publishers TEXT,
    price VARCHAR(255),
    genres TEXT,
    categories TEXT,
    release_date VARCHAR(255),
    platforms TEXT,
    metacritic_score DOUBLE PRECISION,
    recommendations INTEGER,
    header_image TEXT
);

CREATE TABLE IF NOT EXISTS game_tags (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    appid VARCHAR(255) NOT NULL REFERENCES games(appid) ON DELETE CASCADE,
    category VARCHAR(255) NOT NULL,
    UNIQUE (appid, category)
);

CREATE TABLE IF NOT EXISTS user_games (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(255) NOT NULL REFERENCES users(username) ON DELETE CASCADE,
    appid VARCHAR(255) NOT NULL REFERENCES games(appid) ON DELETE CASCADE,
    shelf VARCHAR(50) DEFAULT 'Wish_List',
    rating DOUBLE PRECISION DEFAULT 0.0,
    review TEXT,
    UNIQUE (username, appid)
);

CREATE TABLE IF NOT EXISTS user_recommendations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(255) NOT NULL REFERENCES users(username) ON DELETE CASCADE,
    appid VARCHAR(255) NOT NULL REFERENCES games(appid) ON DELETE CASCADE,
    similarity DOUBLE PRECISION,
    UNIQUE (username, appid)
);

CREATE TABLE IF NOT EXISTS game_similarity (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    game1 VARCHAR(255) NOT NULL REFERENCES games(appid) ON DELETE CASCADE,
    game2 VARCHAR(255) NOT NULL REFERENCES games(appid) ON DELETE CASCADE,
    similarity DOUBLE PRECISION NOT NULL,
    UNIQUE (game1, game2)
);

CREATE INDEX IF NOT EXISTS idx_game_tags_category ON game_tags(category);
CREATE INDEX IF NOT EXISTS idx_user_games_username ON user_games(username);
CREATE INDEX IF NOT EXISTS idx_user_recs_username ON user_recommendations(username);
