"""Reading routes: deal, persist, share."""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Iterator
from datetime import date

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
    drawn_to: str = Form("Prefer not to say"),
    birth_date: str = Form(""),
    birth_time: str = Form(""),
    birth_place: str = Form(""),
    spread_slug: str = Form(...),
    strategy_slug: str = Form("daily"),
    question: str = Form(""),
    save: str = Form("on"),
    conn: sqlite3.Connection = Depends(get_db),
    today=Depends(get_today),
) -> HTMLResponse:
    """Deal the cards and return the full reading page.

    The LLM interpretation is generated lazily: the deal page's inline script
    opens an EventSource to /readings/{slug}/stream, and that endpoint
    starts the LLM on first connection (idempotent across re-deals and
    multiple tabs via a per-slug lock). So the deal POST itself is just
    cards + share link, fast.
    """
    querent, spread, strategy = _form_parts(
        name, age, resonance, drawn_to,
        birth_date, birth_time, birth_place,
        spread_slug, strategy_slug,
    )
    # The question belongs to single-card draws. For multi-card spreads the
    # positions ARE the question, so drop it even if the form submitted one
    # (e.g. a leftover value in the persisted profile).
    question_text = (question.strip() or None) if len(spread) == 1 else None
    reading = build_reading(load_deck(), spread, querent, strategy, today, question=question_text)
    share_slug = save_reading(reading, conn) if save == "on" else None

    response = templates.TemplateResponse(
        request,
        "partials/reading.html",
        {
            "reading": reading,
            "share_slug": share_slug,
            "querent_dict": {
                "name": querent.name,
                "age": querent.age,
                "resonance": querent.resonance,
                "drawn_to": querent.drawn_to,
            },
            "querent": querent,
            "interpretation": "",
        },
    )
    if save == "on":
        set_profile_cookie(response, querent)
    return response


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
    drawn_to: str,
    birth_date: str,
    birth_time: str,
    birth_place: str,
    spread_slug: str,
    strategy_slug: str,
) -> tuple[Querent, Spread, SeedStrategy]:
    """Validate the form and return typed pieces. Raises HTTPException on bad input."""
    parsed_birth_date = _parse_birth_date(birth_date)
    try:
        querent = Querent(
            name=name,
            age=age,
            resonance=resonance,
            drawn_to=drawn_to or "Prefer not to say",
            birth_date=parsed_birth_date,
            birth_time=birth_time or None,
            birth_place=birth_place or None,
        )
    except InvalidQuerent as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        spread = get_spread(spread_slug)
    except UnknownSpread as exc:
        raise HTTPException(status_code=404, detail="Unknown spread") from exc
    return querent, spread, get_strategy(strategy_slug)


def _parse_birth_date(value: str) -> date | None:
    if not value or not value.strip():
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Birth date must be YYYY-MM-DD.") from exc
