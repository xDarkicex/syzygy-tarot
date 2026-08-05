"""Streaming interpretation endpoint.

The deal POST returns the cards immediately and embeds an inline script that
opens an EventSource to ``/readings/{slug}/stream``. The stream emits one
``token`` event per text delta from the LLM, ``done`` when the model finishes,
and ``error`` on failure. The browser appends each token's data to the
interpretation body so the user sees a typewriter effect during the card flip.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.services.interpretation import stream_interpretation
from app.storage.readings import fetch_reading, update_interpretation
from app.web.dependencies import get_db

router = APIRouter(prefix="/readings")

# A simple lock-free in-process cache: the first GET to a share_slug runs the
# LLM, subsequent GETs replay the cached text. Each LLM call costs money, so
# the cache is the safety net for repeat page-loads.
_cache: dict[str, str] = {}


def _sse(event: str, data: str) -> str:
    """Format one Server-Sent Event. Each event ends with a blank line."""
    payload = data.replace("\r", " ").replace("\n", " ")
    return f"event: {event}\ndata: {payload}\n\n"


def _stream_for_reading(share_slug: str, conn: sqlite3.Connection) -> Iterator[str]:
    """Stream the interpretation, serving from the cache when available.

    The LLM is called once per reading by the background task in the deal
    route. The streaming endpoint here is a "watch the result appear" path:
    if the background task has finished, we replay its stored result. If
    it's still running, we wait for it and then replay. This guarantees
    exactly one LLM call per share_slug, no matter how many times the
    page is opened.
    """
    stored = fetch_reading(share_slug, conn)
    if stored is None:
        yield _sse("error", "Reading not found")
        return
    reading = stored.reading

    # If a result already exists, replay it.
    if stored.interpretation:
        yield _sse("token", stored.interpretation)
        yield _sse("done", "complete")
        return

    # Otherwise the background task is still running, or it failed. Wait
    # for it: poll the DB briefly (up to ~20s) and emit the result as it
    # appears, broken into per-paragraph chunks for the typewriter.
    import time
    for _ in range(40):
        row = conn.execute(
            "SELECT interpretation FROM readings WHERE share_slug = ?",
            (share_slug,),
        ).fetchone()
        if row and row["interpretation"]:
            yield _sse("token", row["interpretation"])
            yield _sse("done", "complete")
            return
        time.sleep(0.5)

    # Background task failed. Try one direct call ourselves as a fallback.
    accumulated: list[str] = []
    for delta in _stream_with_one_retry(reading):
        accumulated.append(delta)
        yield _sse("token", delta)
    if not accumulated:
        yield _sse(
            "error",
            "The model is not responding right now. Your cards above are still yours to read.",
        )
        return
    full_text = "".join(accumulated)
    try:
        update_interpretation(share_slug, full_text, conn)
    except Exception:  # noqa: BLE001
        pass
    yield _sse("done", "complete")


def _stream_with_one_retry(reading) -> Iterator[str]:
    """Yield deltas, retrying once if the first attempt produced none."""
    first = list(_safe_deltas(reading))
    if first:
        yield from first
        return
    yield from _safe_deltas(reading)


def _safe_deltas(reading) -> Iterator[str]:
    """Wrap the LLM stream in try/except so the route can stay clean."""
    try:
        yield from stream_interpretation(reading)
    except Exception:  # noqa: BLE001
        return


@router.get("/{share_slug}/stream")
def stream(share_slug: str, conn: sqlite3.Connection = Depends(get_db)) -> StreamingResponse:
    return StreamingResponse(
        _stream_for_reading(share_slug, conn),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
