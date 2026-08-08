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
    interpretation: str = ""
    focus: tuple[str, ...] = ()
    sky: dict[str, str] | None = None


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


def save_reading(reading: Reading, conn: sqlite3.Connection, interpretation: str = "") -> str:
    slug = generate_share_slug()
    sky = _sky_for(reading.drawn_on)
    with conn:  # commits on success, rolls back on exception
        conn.execute(
            """
            INSERT INTO readings (
                share_slug, querent_name, querent_age, querent_resonance,
                spread_slug, strategy_slug, seed, drawn_on, cards_json, interpretation,
                question, focus, sky_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                interpretation,
                reading.question or "",
                ", ".join(sorted(reading.querent.focus)),
                json.dumps(sky) if sky else "",
            ),
        )
        # Persist the full querent (birth data, mbti, drawn-to, status) so the
        # share page can recompute the chart without re-asking the user.
        conn.execute(
            """
            UPDATE readings SET
                querent_drawn_to = ?, querent_birth_date = ?, querent_birth_time = ?,
                querent_birth_place = ?, querent_mbti = ?, querent_relationship_status = ?
            WHERE share_slug = ?
            """,
            (
                reading.querent.drawn_to,
                reading.querent.birth_date.isoformat() if reading.querent.birth_date else "",
                reading.querent.birth_time or "",
                reading.querent.birth_place or "",
                reading.querent.mbti or "",
                reading.querent.relationship_status or "",
                slug,
            ),
        )
    return slug


def _sky_for(on: date) -> dict[str, str] | None:
    """Capture the sky snapshot at the reading date for the dashboard."""
    try:
        from app.services.ephemeris import sky_snapshot
        snap = sky_snapshot(on)
        if snap is None:
            return None
        return {
            "sun": snap.sun_sign,
            "moon": snap.moon_sign,
            "phase": snap.moon_phase,
            "hour": snap.planetary_hour,
        }
    except Exception:  # noqa: BLE001
        return None


def update_interpretation(share_slug: str, interpretation: str, conn: sqlite3.Connection) -> None:
    with conn:
        conn.execute(
            "UPDATE readings SET interpretation = ? WHERE share_slug = ?",
            (interpretation, share_slug),
        )


def _row_to_reading(row: sqlite3.Row) -> Reading:
    querent = _querent_from_row(row)
    spread = get_spread(row["spread_slug"])
    question = _row_get(row, "question") or None
    return Reading(
        querent=querent,
        spread=spread,
        strategy_slug=row["strategy_slug"],
        seed=row["seed"],
        drawn=_deserialise_drawn(row["cards_json"]),
        drawn_on=date.fromisoformat(row["drawn_on"]),
        question=question,
    )


def _row_get(row: sqlite3.Row, key: str) -> str:
    """Read a column, tolerating rows that predate a migration."""
    return row[key] if key in row.keys() else ""


def _querent_from_row(row: sqlite3.Row) -> Querent:
    """Rebuild the full querent, including birth data and personality fields."""
    raw_birth = _row_get(row, "querent_birth_date")
    birth_date = date.fromisoformat(raw_birth) if raw_birth else None
    drawn_to = _row_get(row, "querent_drawn_to") or "Prefer not to say"
    return Querent(
        name=row["querent_name"],
        age=row["querent_age"],
        resonance=row["querent_resonance"],
        drawn_to=drawn_to,
        birth_date=birth_date,
        birth_time=_row_get(row, "querent_birth_time") or None,
        birth_place=_row_get(row, "querent_birth_place") or None,
        mbti=_row_get(row, "querent_mbti") or None,
        focus=_parse_focus(_row_get(row, "focus")),
        relationship_status=_row_get(row, "querent_relationship_status") or None,
    )


def fetch_reading(share_slug: str, conn: sqlite3.Connection) -> StoredReading | None:
    row = conn.execute(
        "SELECT * FROM readings WHERE share_slug = ?", (share_slug,)
    ).fetchone()
    if row is None:
        return None
    return StoredReading(
        reading=_row_to_reading(row),
        share_slug=row["share_slug"],
        created_at=row["created_at"],
        interpretation=row["interpretation"] or "",
        focus=_parse_focus(row["focus"]),
        sky=_parse_sky(row["sky_json"]),
    )


def fetch_recent_readings(limit: int, conn: sqlite3.Connection) -> list[StoredReading]:
    rows = conn.execute(
        "SELECT * FROM readings ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    return [
        StoredReading(
            reading=_row_to_reading(row),
            share_slug=row["share_slug"],
            created_at=row["created_at"],
            interpretation=row["interpretation"] or "",
            focus=_parse_focus(row["focus"]),
            sky=_parse_sky(row["sky_json"]),
        )
        for row in rows
    ]


def _parse_focus(raw: str) -> tuple[str, ...]:
    if not raw:
        return ()
    return tuple(part.strip() for part in raw.split(",") if part.strip())


def _parse_sky(raw: str) -> dict[str, str] | None:
    if not raw:
        return None
    try:
        value = json.loads(raw)
        return value if isinstance(value, dict) else None
    except ValueError:
        return None


def get_connection() -> sqlite3.Connection:
    return sqlite3.connect(get_settings().database_path)
