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
    interpretation    TEXT    NOT NULL DEFAULT '',
    question          TEXT    NOT NULL DEFAULT '',
    focus             TEXT    NOT NULL DEFAULT '',   -- comma-joined focus areas
    sky_json          TEXT    NOT NULL DEFAULT '',   -- sun/moon/phase/hour at deal
    querent_drawn_to  TEXT    NOT NULL DEFAULT '',
    querent_birth_date TEXT   NOT NULL DEFAULT '',
    querent_birth_time TEXT   NOT NULL DEFAULT '',
    querent_birth_place TEXT  NOT NULL DEFAULT '',
    querent_mbti      TEXT    NOT NULL DEFAULT '',
    querent_relationship_status TEXT NOT NULL DEFAULT '',
    querent_user_id   TEXT    NOT NULL DEFAULT '',
    created_at        TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_readings_created_at ON readings (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_readings_share_slug ON readings (share_slug);
