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
    stored = fetch_reading(share_slug, conn)
    if stored is None:
        yield _sse("error", "Reading not found")
        return
    reading = stored.reading

    cached = _cache.get(share_slug)
    if cached is not None:
        # Replay the cached text as a single token event so the page fills in.
        yield _sse("token", cached)
        yield _sse("done", "complete")
        return

    try:
        deltas = stream_interpretation(reading)
    except Exception as exc:  # noqa: BLE001
        yield _sse("error", f"{type(exc).__name__}: {exc}")
        return

    if not deltas:
        yield _sse("error", "No interpretation was generated")
        return

    full_text = "".join(deltas)
    _cache[share_slug] = full_text
    try:
        update_interpretation(share_slug, full_text, conn)
    except Exception:  # noqa: BLE001
        pass

    # Send each delta as a separate SSE event so the browser typewriter is smooth.
    for delta in deltas:
        yield _sse("token", delta)
    yield _sse("done", "complete")


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
