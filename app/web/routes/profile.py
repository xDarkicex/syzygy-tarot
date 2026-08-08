"""Profile management. Client-side state in localStorage, mirrored into a signed
cookie so the server can prefill pages. No auth yet — the profile is per-browser.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config import get_settings
from app.domain.seeding import InvalidQuerent, Querent, RESONANCES, DRAWN_TO
from app.services.birth_chart import compute_birth_chart
from app.web.auth import clear_profile_cookie, set_profile_cookie
from app.web.dependencies import get_profile
from app.web.templating import templates

router = APIRouter(prefix="/profile")


def _chart(querent: Querent | None):
    if querent and querent.birth_date:
        return compute_birth_chart(querent.birth_date, querent.birth_time, querent.birth_place)
    return None


@router.get("", response_class=HTMLResponse)
def profile_page(request: Request, querent: Querent | None = Depends(get_profile)) -> HTMLResponse:
    """View + edit the profile. Shows the computed birth chart when birth data exists."""
    return templates.TemplateResponse(
        request,
        "profile.html",
        {
            "profile": querent,
            "chart": _chart(querent),
            "resonances": RESONANCES,
            "drawn_to_options": DRAWN_TO,
            "today": date.today(),
        },
    )


def _redirect(url: str) -> Response:
    return Response(status_code=303, headers={"Location": url})


@router.post("/save")
def save_profile(
    name: str = Form(...),
    age: int = Form(...),
    resonance: str = Form(...),
    drawn_to: str = Form("Prefer not to say"),
    birth_date: str = Form(""),
    birth_time: str = Form(""),
    birth_place: str = Form(""),
) -> Response:
    """Update the profile and mirror it into the cookie."""
    try:
        querent = Querent(
            name=name,
            age=age,
            resonance=resonance,
            drawn_to=drawn_to or "Prefer not to say",
            birth_date=_parse_date(birth_date),
            birth_time=birth_time or None,
            birth_place=birth_place or None,
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
