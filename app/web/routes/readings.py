"""Reading routes: deal, persist, share."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.config import get_settings
from app.data.loader import load_deck
from app.domain.deck import Deck
from app.domain.reading import build_reading
from app.domain.seeding import (
    InvalidQuerent,
    Querent,
    SeedStrategy,
    get_strategy,
)
from app.domain.spreads import Spread, UnknownSpread, get_spread
from app.services.interpretation import generate_interpretation
from app.storage.readings import fetch_reading, save_reading, update_interpretation
from app.web.auth import set_profile_cookie
from app.web.dependencies import get_db, get_today

router = APIRouter(prefix="/readings")
templates = Jinja2Templates(directory=str(get_settings().templates_dir))


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
    querent, spread, strategy = _form_parts(name, age, resonance, spread_slug, strategy_slug)
    reading = build_reading(load_deck(), spread, querent, strategy, today)
    share_slug = save_reading(reading, conn) if save == "on" else None

    # Generate the LLM interpretation synchronously. The model is fast (3-8s),
    # one call per reading, and the result is stored so the share page is
    # instant. The deal response therefore carries cards + interpretation in
    # one round-trip — no SSE, no EventSource, no risk of double-subscription
    # burning the budget.
    interpretation = ""
    if share_slug:
        try:
            interpretation = generate_interpretation(reading)
            if interpretation:
                update_interpretation(share_slug, interpretation, conn)
        except Exception:  # noqa: BLE001
            interpretation = ""

    response = templates.TemplateResponse(
        request,
        "partials/reading.html",
        {
            "reading": reading,
            "share_slug": share_slug,
            "querent_dict": {"name": querent.name, "age": querent.age, "resonance": querent.resonance},
            "querent": querent,
            "interpretation": interpretation,
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
            "interpretation": stored.interpretation,
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
