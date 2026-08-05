PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS readings (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    share_slug        TEXT    NOT NULL UNIQUE,
    querent_name      TEXT    NOT NULL,
    querent_age       INTEGER NOT NULL,
    querent_resonance TEXT    NOT NULL,
    spread_slug       TEXT    NOT NULL,
    strategy_slug     TEXT    NOT NULL,
    seed              INTEGER NOT NULL,
    drawn_on          TEXT    NOT NULL,
    cards_json        TEXT    NOT NULL,
    created_at        TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_readings_created_at ON readings (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_readings_share_slug ON readings (share_slug);
