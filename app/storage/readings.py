"""Persistence for shareable readings."""

from __future__ import annotations

import json
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import date
from typing import Any

from app.config import get_settings
from app.data.loader import load_deck
from app.domain.cards import Orientation
from app.domain.deck import DrawnCard
from app.domain.reading import Reading
from app.domain.seeding import Querent
from app.domain.spreads import Position, get_spread

SHARE_SLUG_BYTES = 8
SHARE_SLUG_CHARS = 12


def generate_share_slug() -> str:
    """Cryptographically random, URL-safe, short enough for a permalink."""
    return secrets.token_urlsafe(SHARE_SLUG_BYTES)[:SHARE_SLUG_CHARS]


@dataclass(frozen=True, slots=True)
class StoredReading:
    reading: Reading
    share_slug: str
    created_at: str


def _serialise_drawn(drawn: tuple[DrawnCard, ...]) -> str:
    payload = [
        {
            "position_key": d.position.key,
            "position_title": d.position.title,
            "position_prompt": d.position.prompt,
            "position_accent": d.position.accent,
            "card_slug": d.card.slug,
            "orientation": d.orientation.value,
        }
        for d in drawn
    ]
    return json.dumps(payload, separators=(",", ":"))


def _deserialise_drawn(payload: str) -> tuple[DrawnCard, ...]:
    deck = load_deck()
    items: list[dict[str, Any]] = json.loads(payload)
    drawn: list[DrawnCard] = []
    for item in items:
        card = deck.by_slug(item["card_slug"])
        position = Position(
            key=item["position_key"],
            title=item["position_title"],
            prompt=item["position_prompt"],
            accent=item["position_accent"],
        )
        drawn.append(DrawnCard(position=position, card=card, orientation=Orientation(item["orientation"])))
    return tuple(drawn)


def save_reading(reading: Reading, conn: sqlite3.Connection) -> str:
    slug = generate_share_slug()
    with conn:  # commits on success, rolls back on exception
        conn.execute(
            """
            INSERT INTO readings (
                share_slug, querent_name, querent_age, querent_resonance,
                spread_slug, strategy_slug, seed, drawn_on, cards_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                slug,
                reading.querent.name,
                reading.querent.age,
                reading.querent.resonance,
                reading.spread.slug,
                reading.strategy_slug,
                reading.seed,
                reading.drawn_on.isoformat(),
                _serialise_drawn(reading.drawn),
            ),
        )
    return slug


def _row_to_reading(row: sqlite3.Row) -> Reading:
    querent = Querent(name=row["querent_name"], age=row["querent_age"], resonance=row["querent_resonance"])
    spread = get_spread(row["spread_slug"])
    return Reading(
        querent=querent,
        spread=spread,
        strategy_slug=row["strategy_slug"],
        seed=row["seed"],
        drawn=_deserialise_drawn(row["cards_json"]),
        drawn_on=date.fromisoformat(row["drawn_on"]),
    )


def fetch_reading(share_slug: str, conn: sqlite3.Connection) -> StoredReading | None:
    row = conn.execute(
        "SELECT * FROM readings WHERE share_slug = ?", (share_slug,)
    ).fetchone()
    if row is None:
        return None
    return StoredReading(reading=_row_to_reading(row), share_slug=row["share_slug"], created_at=row["created_at"])


def fetch_recent_readings(limit: int, conn: sqlite3.Connection) -> list[StoredReading]:
    rows = conn.execute(
        "SELECT * FROM readings ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    return [
        StoredReading(reading=_row_to_reading(row), share_slug=row["share_slug"], created_at=row["created_at"])
        for row in rows
    ]


def get_connection() -> sqlite3.Connection:
    return sqlite3.connect(get_settings().database_path)
