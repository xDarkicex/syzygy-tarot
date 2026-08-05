"""On-demand interpretation endpoint.

Replaces the streaming SSE approach: the deal partial no longer auto-subscribes
to a stream (which was leaking EventSources across re-deals and burning the LLM
budget). The share page renders any pre-stored interpretation directly; the
deal page exposes a 'Generate interpretation' button that POSTs here. The
endpoint runs the LLM synchronously, stores the result, and returns the
rendered body partial — bounded to one LLM call per reading.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config import get_settings
from app.services.interpretation import generate_interpretation
from app.storage.readings import fetch_reading, update_interpretation
from app.web.dependencies import get_db

router = APIRouter(prefix="/readings")
templates = Jinja2Templates(directory=str(get_settings().templates_dir))


@router.post("/{share_slug}/interpret", response_class=HTMLResponse)
def interpret(request: Request, share_slug: str, conn: sqlite3.Connection = Depends(get_db)) -> HTMLResponse:
    stored = fetch_reading(share_slug, conn)
    if stored is None:
        return HTMLResponse("<p>Reading not found.</p>", status_code=404)

    existing = conn.execute(
        "SELECT interpretation FROM readings WHERE share_slug = ?", (share_slug,)
    ).fetchone()
    if existing and existing["interpretation"]:
        return templates.TemplateResponse(
            request,
            "partials/interpretation_body.html",
            {"interpretation": existing["interpretation"]},
        )

    try:
        text = generate_interpretation(stored.reading)
    except Exception as exc:  # noqa: BLE001
        return HTMLResponse(
            f"<p>The interpretation could not be generated: {type(exc).__name__}.</p>",
            status_code=500,
        )

    update_interpretation(share_slug, text, conn)
    return templates.TemplateResponse(
        request,
        "partials/interpretation_body.html",
        {"interpretation": text},
    )
