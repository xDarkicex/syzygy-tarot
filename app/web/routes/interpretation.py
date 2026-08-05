"""Streaming interpretation endpoint.

Sends a text/event-stream response where each event is one text delta from the
LLM. htmx's SSE extension consumes this and swaps the placeholder body as
tokens arrive.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.services.interpretation import stream_interpretation
from app.storage.readings import fetch_reading
from app.web.dependencies import get_db

router = APIRouter(prefix="/readings")


def _sse(event: str, data: str) -> str:
    payload = data.replace("\n", " ")
    return f"event: {event}\ndata: {payload}\n\n"


def _stream_for_reading(share_slug: str, conn: sqlite3.Connection) -> Iterator[str]:
    stored = fetch_reading(share_slug, conn)
    if stored is None:
        yield _sse("error", "Reading not found")
        return
    reading = stored.reading
    try:
        emitted_length = 0
        for chunk in stream_interpretation(reading):
            if len(chunk) <= emitted_length:
                continue
            emitted_length = len(chunk)
            yield _sse("token", chunk)
        if emitted_length == 0:
            yield _sse("error", "No interpretation was generated")
        else:
            yield _sse("done", "complete")
    except Exception as exc:  # noqa: BLE001
        yield _sse("error", f"{type(exc).__name__}: {exc}")


@router.get("/{share_slug}/interpret")
def interpret(share_slug: str, conn: sqlite3.Connection = Depends(get_db)) -> StreamingResponse:
    return StreamingResponse(
        _stream_for_reading(share_slug, conn),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
