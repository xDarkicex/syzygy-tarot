"""Reading routes: deal, persist, share."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
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
from app.services.interpretation import stream_interpretation
from app.storage.readings import fetch_reading, save_reading, update_interpretation
from app.web.auth import set_profile_cookie
from app.web.dependencies import get_db, get_today

router = APIRouter(prefix="/readings")
templates = Jinja2Templates(directory=str(get_settings().templates_dir))


@router.post("/")
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
) -> StreamingResponse:
    querent, spread, strategy = _form_parts(name, age, resonance, spread_slug, strategy_slug)
    reading = build_reading(load_deck(), spread, querent, strategy, today)
    share_slug = save_reading(reading, conn) if save == "on" else None

    # The cards are rendered first into a string. The LLM interpretation
    # streams in afterward, one chunked HTML fragment at a time, all in a
    # single chunked transfer-encoding response. The browser receives the
    # cards immediately (so the flip animation can start) and the
    # interpretation fills in as the model produces it.
    cards_html = _render_cards_html(request, reading, querent, share_slug)

    def _stream() -> Iterator[bytes]:
        yield cards_html.encode("utf-8")
        if not share_slug:
            return
        for fragment in _stream_interpretation(reading, share_slug, conn):
            yield fragment

    response = StreamingResponse(_stream(), media_type="text/html")
    if save == "on":
        set_profile_cookie(response, querent)
    return response


def _render_cards_html(request: Request, reading, querent: Querent, share_slug: str | None) -> str:
    """Render just the cards + the (initially empty) interpretation section.

    The interpretation section has an empty body and an error line, both
    addressed by stable element ids that the streaming script fragments
    update as the LLM produces text.
    """
    return templates.get_template("partials/reading.html").render(
        request=request,
        reading=reading,
        share_slug=share_slug,
        querent_dict={"name": querent.name, "age": querent.age, "resonance": querent.resonance},
        querent=querent,
        interpretation="",
    )


def _stream_interpretation(reading, share_slug: str, conn: sqlite3.Connection) -> Iterator[bytes]:
    """Yield script fragments that update the interpretation body as the LLM streams.

    Each fragment is a small self-executing IIFE that updates ``#interpretation-body``
    with the cumulative text-so-far. Falls back to writing the error into
    ``#interpretation-error`` if the LLM raises.
    """
    accumulated: list[str] = []
    try:
        for chunk in stream_interpretation(reading):
            if not chunk:
                continue
            prev_len = _accumulated_length(accumulated)
            if len(chunk) <= prev_len:
                continue
            delta = chunk[prev_len:]
            accumulated.append(delta)
            yield _swap_script("interpretation-body", json.dumps("".join(accumulated)))
    except Exception as exc:  # noqa: BLE001
        yield _swap_script(
            "interpretation-error",
            f'"The interpretation failed: {type(exc).__name__}: {exc}"',
        )
    else:
        full_text = "".join(accumulated).strip()
        if full_text:
            try:
                update_interpretation(share_slug, full_text, conn)
            except Exception:  # noqa: BLE001
                pass


def _accumulated_length(parts: list[str]) -> int:
    return sum(len(p) for p in parts)


def _swap_script(element_id: str, payload_json: str) -> bytes:
    """A self-executing <script> that updates one element's textContent."""
    return (
        f'<script>(function(){{'
        f'var el=document.getElementById("{element_id}");'
        f'if(el)el.textContent={payload_json};'
        f'}})();</script>'
    ).encode("utf-8")


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
