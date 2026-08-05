"""Thin route dependencies that hide request parsing behind typed values."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date

import sqlite3
from fastapi import Cookie, Depends, Request

from app.config import get_settings
from app.data.loader import load_deck
from app.domain.deck import Deck
from app.domain.seeding import Querent
from app.storage.readings import StoredReading, fetch_reading
from app.web.auth import read_profile_cookie


def get_db() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(get_settings().database_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def get_deck() -> Deck:
    return load_deck()


def get_today() -> date:
    return date.today()


def get_profile(profile_cookie: str | None = Cookie(default=None)) -> Querent | None:
    return read_profile_cookie(profile_cookie)


def get_querent_form(request: Request) -> dict[str, str]:
    """Read form fields once; routes consume the dict instead of poking at request."""
    if request.method == "GET":
        return {}
    return {key: value for key, value in (await_or_sync_form(request)).items()}


async def await_or_sync_form(request: Request) -> dict[str, str]:
    """Be tolerant of sync/async test callers; FastAPI always provides await form()."""
    form = await request.form()
    return {key: str(value) for key, value in form.items() if isinstance(value, str)}


def get_stored_reading(slug: str, conn: sqlite3.Connection = Depends(get_db)) -> StoredReading | None:
    return fetch_reading(slug, conn)
