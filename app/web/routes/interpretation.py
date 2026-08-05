"""Streaming interpretation endpoint.

The deal POST returns the cards immediately. The deal page's inline script
opens an EventSource to ``/readings/{slug}/stream``. The streaming endpoint
here starts the LLM itself on the first connection for a slug, streams the
deltas, and stores the result. A per-slug lock makes the call idempotent
across concurrent connections: re-deals, multiple browser tabs, share
pages all attach to the same in-flight call instead of triggering
separate LLM calls.
"""

from __future__ import annotations

import sqlite3
import threading
import time
from collections.abc import Iterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.services.interpretation import stream_interpretation
from app.storage.database import connect
from app.storage.readings import fetch_reading, update_interpretation
from app.web.dependencies import get_db

router = APIRouter(prefix="/readings")

# Per-slug state: lock, done-event, and a list of accumulated deltas. The
# first connection that asks for a slug starts the LLM in a background
# thread; subsequent connections share the same state.
_state: dict[str, tuple[threading.Lock, threading.Event, list[str]]] = {}
_state_lock = threading.Lock()


def _sse(event: str, data: str) -> str:
    """Format one Server-Sent Event. Each event ends with a blank line."""
    payload = data.replace("\r", " ").replace("\n", " ")
    return f"event: {event}\ndata: {payload}\n\n"


def _get_or_start_state(share_slug: str, conn: sqlite3.Connection) -> tuple[threading.Lock, threading.Event, list[str]]:
    """Return (lock, done_event, delta_buffer) for a slug.

    If a stored result already exists in the DB, return it as a single
    completed delta and mark done. Otherwise, if no call is in flight,
    start the LLM in a background thread. Concurrent connections share
    the same state.
    """
    with _state_lock:
        existing = _state.get(share_slug)
        if existing is not None:
            return existing
        lock = threading.Lock()
        done = threading.Event()
        buf: list[str] = []
        _state[share_slug] = (lock, done, buf)

        # Check the DB: if a result is already stored, no LLM call needed.
        row = conn.execute(
            "SELECT interpretation FROM readings WHERE share_slug = ?",
            (share_slug,),
        ).fetchone()
        if row and row["interpretation"]:
            buf.append(row["interpretation"])
            done.set()
            return lock, done, buf

        stored = fetch_reading(share_slug, conn)
        if stored is None:
            done.set()
            return lock, done, buf

        def _worker() -> None:
            worker_conn = connect(_db_path())
            try:
                deltas: list[str] = []
                try:
                    deltas = list(stream_interpretation(stored.reading))
                except Exception:  # noqa: BLE001
                    # The model occasionally fails. Retry once — the second
                    # call often succeeds where the first stalled.
                    deltas = list(stream_interpretation(stored.reading))
                with lock:
                    buf.clear()
                    buf.extend(deltas)
                    full = "".join(buf)
                    buf.clear()
                    buf.append(full)
                try:
                    update_interpretation(share_slug, full, worker_conn)
                except Exception:  # noqa: BLE001
                    pass
            except Exception:  # noqa: BLE001
                pass
            finally:
                done.set()
                worker_conn.close()

        threading.Thread(target=_worker, daemon=True).start()
        return lock, done, buf


def _db_path():
    from app.config import get_settings
    return get_settings().database_path


def _stream_for_reading(share_slug: str, conn: sqlite3.Connection) -> Iterator[str]:
    stored = fetch_reading(share_slug, conn)
    if stored is None:
        yield _sse("error", "Reading not found")
        return

    # Fast path: a result is already stored. Replay and exit.
    if stored.interpretation:
        yield _sse("token", stored.interpretation)
        yield _sse("done", "complete")
        return

    lock, done, buf = _get_or_start_state(share_slug, conn)

    # Stream tokens as they arrive. While the LLM is running, the worker
    # thread appends deltas to buf under the lock. We read buf on each
    # tick and emit anything new. When the worker is done, buf is
    # collapsed to a single joined text and we emit the final.
    emitted_len = 0
    while not done.is_set():
        with lock:
            current = "".join(buf)
        if len(current) > emitted_len:
            yield _sse("token", current[emitted_len:])
            emitted_len = len(current)
        time.sleep(0.05)

    with lock:
        final = "".join(buf)
    if len(final) > emitted_len:
        yield _sse("token", final[emitted_len:])
    if final.strip():
        yield _sse("done", "complete")
    else:
        yield _sse(
            "error",
            "The model is not responding right now. Your cards above are still yours to read.",
        )


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
