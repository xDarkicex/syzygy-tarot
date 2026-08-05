"""Reading routes: deal, persist, share."""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Iterator

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.config import get_settings
from app.data.loader import load_deck
from app.domain.deck import Deck
from app.domain.reading import build_reading
from app.services.interpretation import generate_interpretation
import markdown as _markdown
from app.domain.seeding import (
    InvalidQuerent,
    Querent,
    SeedStrategy,
    get_strategy,
)
from app.domain.spreads import Spread, UnknownSpread, get_spread
from app.storage.database import connect
from app.storage.readings import fetch_reading, save_reading, update_interpretation
from app.web.auth import set_profile_cookie
from app.web.dependencies import get_db, get_today

router = APIRouter(prefix="/readings")
templates = Jinja2Templates(directory=str(get_settings().templates_dir))


def _md(text: str) -> str:
    """Render the model's markdown-flavoured text to HTML for the share page.

    We pass the raw text through the python-markdown library with a small
    extension set: paragraphs split on blank lines, ``**bold**`` rendered as
    <strong>, single line breaks preserved as <br>. No other syntax is enabled.
    """
    return _markdown.markdown(
        text,
        extensions=["extra", "sane_lists"],
        output_format="html5",
    )


@router.post("/", response_class=HTMLResponse)
def deal_reading(
    request: Request,
    name: str = Form(...),
    age: int = Form(...),
    resonance: str = Form(...),
    spread_slug: str = Form(...),
    strategy_slug: str = Form("daily"),
    save: str = Form("on"),
    conn: sqlite3.Connection = Depends(get_db),
    today=Depends(get_today),
) -> HTMLResponse:
    """Deal the cards and return the full reading page.

    The LLM interpretation is generated in a background thread and stored
    against the reading. The deal page renders immediately with empty
    interpretation body and an inline script that opens an EventSource to
    stream the LLM tokens as they arrive. The share page picks up the
    stored interpretation on next visit.
    """
    querent, spread, strategy = _form_parts(name, age, resonance, spread_slug, strategy_slug)
    reading = build_reading(load_deck(), spread, querent, strategy, today)
    share_slug = save_reading(reading, conn) if save == "on" else None

    if share_slug:
        _kick_off_interpretation(share_slug, reading)

    response = templates.TemplateResponse(
        request,
        "partials/reading.html",
        {
            "reading": reading,
            "share_slug": share_slug,
            "querent_dict": {"name": querent.name, "age": querent.age, "resonance": querent.resonance},
            "querent": querent,
            "interpretation": "",
        },
    )
    if save == "on":
        set_profile_cookie(response, querent)
    return response


def _kick_off_interpretation(share_slug: str, reading) -> None:
    """Generate the LLM interpretation in a background thread, store it.

    One LLM call per reading. The thread is daemonised so it dies with the
    process. The share page reads the stored result on the next visit; the
    deal page's EventSource streams the same result if the user is still on
    the page when the LLM finishes.
    """
    settings = get_settings()

    def _worker() -> None:
        worker_conn = connect(settings.database_path)
        try:
            existing = worker_conn.execute(
                "SELECT interpretation FROM readings WHERE share_slug = ?",
                (share_slug,),
            ).fetchone()
            if existing and existing["interpretation"]:
                return
            from app.services.interpretation import generate_interpretation
            text = generate_interpretation(reading)
            if text:
                update_interpretation(share_slug, text, worker_conn)
        except Exception:  # noqa: BLE001
            pass
        finally:
            worker_conn.close()

    threading.Thread(target=_worker, daemon=True).start()


@router.get("/{share_slug}", response_class=HTMLResponse)
def view_reading(
    request: Request,
    share_slug: str,
    conn: sqlite3.Connection = Depends(get_db),
) -> HTMLResponse:
    stored = fetch_reading(share_slug, conn)
    if stored is None:
        raise HTTPException(status_code=404, detail="Reading not found")
    return templates.TemplateResponse(
        request,
        "reading.html",
        {
            "reading": stored.reading,
            "share_slug": stored.share_slug,
            "created_at": stored.created_at,
            "querent": stored.reading.querent,
            "interpretation": _md(stored.interpretation) if stored.interpretation else "",
        },
    )


@router.get("/{share_slug}/card/{index}", response_class=HTMLResponse)
def reveal_card(
    request: Request,
    share_slug: str,
    index: int,
    conn: sqlite3.Connection = Depends(get_db),
) -> HTMLResponse:
    """htmx endpoint — returns just the card panel so the rest of the page stays static."""
    stored = fetch_reading(share_slug, conn)
    if stored is None:
        raise HTTPException(status_code=404, detail="Reading not found")
    if not 0 <= index < len(stored.reading.drawn):
        raise HTTPException(status_code=404, detail="No card at that position")
    return templates.TemplateResponse(
        request,
        "partials/card_panel.html",
        {"drawn": stored.reading.drawn[index], "position": index + 1, "total": len(stored.reading.drawn)},
    )


def _form_parts(
    name: str,
    age: int,
    resonance: str,
    spread_slug: str,
    strategy_slug: str,
) -> tuple[Querent, Spread, SeedStrategy]:
    """Validate the form and return typed pieces. Raises HTTPException on bad input."""
    try:
        querent = Querent(name=name, age=age, resonance=resonance)
    except InvalidQuerent as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        spread = get_spread(spread_slug)
    except UnknownSpread as exc:
        raise HTTPException(status_code=404, detail="Unknown spread") from exc
    return querent, spread, get_strategy(strategy_slug)
