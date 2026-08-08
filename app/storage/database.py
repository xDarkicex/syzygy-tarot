"""SQLite connection handling."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def connect(database_path: Path) -> sqlite3.Connection:
    """Open a connection with sensible defaults."""
    database_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(database_path, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_database(database_path: Path) -> None:
    """Apply the schema and run any pending migrations. Idempotent."""
    with closing_connection(database_path) as conn:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        _ensure_column(conn, "readings", "interpretation", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "readings", "querent_age", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "readings", "querent_resonance", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "readings", "question", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "readings", "focus", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "readings", "sky_json", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "readings", "querent_drawn_to", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "readings", "querent_birth_date", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "readings", "querent_birth_time", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "readings", "querent_birth_place", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "readings", "querent_mbti", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "readings", "querent_relationship_status", "TEXT NOT NULL DEFAULT ''")


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    """Add a column to an existing table if it isn't already there."""
    existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


@contextmanager
def closing_connection(database_path: Path) -> Iterator[sqlite3.Connection]:
    conn = connect(database_path)
    try:
        yield conn
    finally:
        conn.close()
