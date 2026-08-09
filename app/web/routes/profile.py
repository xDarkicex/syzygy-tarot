"""Profile management. Client-side state in localStorage, mirrored into a signed
cookie so the server can prefill pages. No auth yet — the profile is per-browser.
"""

from __future__ import annotations

import json
from datetime import date

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse

from app.domain.seeding import (
    InvalidQuerent,
    Querent,
    RESONANCES,
    DRAWN_TO,
    FOCUS_AREAS,
    RELATIONSHIP_STATUSES,
)
from app.services.birth_chart import compute_birth_chart
from app.services.quiz import QUESTIONS, archetype_for, compute_type
from app.services.ephemeris import sky_snapshot
from app.storage.readings import fetch_recent_readings
from app.web.auth import clear_profile_cookie, set_profile_cookie
from app.web.dependencies import get_db, get_profile
from app.web.templating import templates


router = APIRouter(prefix="/profile")


def _chart(querent: Querent | None):
    if querent and querent.birth_date:
        return compute_birth_chart(querent.birth_date, querent.birth_time, querent.birth_place)
    return None


def _profile_stats(history) -> dict:
    """Small stats for the profile dashboard's KPI tiles."""
    card_counts: dict[str, int] = {}
    element_counts: dict[str, int] = {}
    for stored in history:
        for drawn in stored.reading.drawn:
            card_counts[drawn.card.name] = card_counts.get(drawn.card.name, 0) + 1
            element = drawn.card.element
            if element:
                element_counts[element] = element_counts.get(element, 0) + 1
    most_card = max(card_counts.items(), key=lambda kv: kv[1]) if card_counts else (None, 0)
    element = max(element_counts.items(), key=lambda kv: kv[1]) if element_counts else (None, 0)
    return {
        "readings": len(history),
        "most_card": most_card[0],
        "most_card_count": most_card[1],
        "element": element[0],
        "element_count": element[1],
        "elements": element_counts,
    }


@router.get("", response_class=HTMLResponse)
def profile_page(
    request: Request,
    querent: Querent | None = Depends(get_profile),
    conn: sqlite3.Connection = Depends(get_db),
) -> HTMLResponse:
    """View + edit the profile. Shows the chart, archetype, and a reading dashboard."""
    archetype = archetype_for(querent.mbti) if querent and querent.mbti else None
    history = fetch_recent_readings(50, conn)
    history_json = json.dumps([
        {
            "focus": list(h.focus),
            "sky": h.sky,
            "date": h.reading.drawn_on.isoformat(),
        }
        for h in history
    ])
    stats = _profile_stats(history)
    return templates.TemplateResponse(
        request,
        "profile.html",
        {
            "profile": querent,
            "chart": _chart(querent),
            "archetype": archetype,
            "resonances": RESONANCES,
            "drawn_to_options": DRAWN_TO,
            "focus_areas": FOCUS_AREAS,
            "relationship_statuses": RELATIONSHIP_STATUSES,
            "history": history,
            "history_json": history_json,
            "stats": stats,
            "elements_json": json.dumps(stats.get("elements", {})),
            "today_sky": sky_snapshot(date.today()),
            "today": date.today(),
        },
    )


@router.get("/quiz", response_class=HTMLResponse)
def quiz_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "quiz.html", {"questions": QUESTIONS})


@router.post("/quiz")
async def quiz_submit(
    request: Request,
    profile: Querent | None = Depends(get_profile),
) -> Response:
    """Compute the MBTI type from the quiz answers and save it to the profile."""
    form = await request.form()
    answers = {
        key[len("q_"):]: value
        for key, value in form.items()
        if key.startswith("q_") and isinstance(value, str)
    }
    type_code = compute_type(answers)
    existing = profile or Querent(name="You", age=30, resonance="Unspecified")
    querent = Querent(
        name=existing.name or "You",
        age=existing.age,
        resonance=existing.resonance,
        drawn_to=existing.drawn_to,
        birth_date=existing.birth_date,
        birth_time=existing.birth_time,
        birth_place=existing.birth_place,
        mbti=type_code,
    )
    response = _redirect("/profile")
    set_profile_cookie(response, querent)
    return response


def _redirect(url: str) -> Response:
    return Response(status_code=303, headers={"Location": url})


@router.post("/save")
def save_profile(
    name: str = Form(...),
    age: int = Form(0),
    resonance: str = Form(...),
    drawn_to: str = Form("Prefer not to say"),
    birth_date: str = Form(""),
    birth_time: str = Form(""),
    birth_place: str = Form(""),
    mbti: str = Form(""),
    focus: list[str] = Form(default=[]),
    relationship_status: str = Form(""),
) -> Response:
    """Update the profile and mirror it into the cookie.

    Age is derived from birth_date inside Querent; the form no longer
    collects it, so the submitted age (0 by default) is overridden when
    a birth date is present.
    """
    try:
        querent = Querent(
            name=name,
            age=age or 30,
            resonance=resonance,
            drawn_to=drawn_to or "Prefer not to say",
            birth_date=_parse_date(birth_date),
            birth_time=birth_time or None,
            birth_place=birth_place or None,
            mbti=mbti or None,
            focus=tuple(f for f in focus if f),
            relationship_status=relationship_status or None,
        )
    except InvalidQuerent as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    response = _redirect("/profile")
    set_profile_cookie(response, querent)
    return response


@router.post("/clear")
def clear_profile() -> Response:
    response = _redirect("/profile")
    clear_profile_cookie(response)
    return response


def _parse_date(value: str) -> date | None:
    if not value or not value.strip():
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Birth date must be YYYY-MM-DD.") from exc
