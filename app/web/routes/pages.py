"""Page routes — GET only, thin and rendering-focused."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.domain.seeding import Querent
from app.domain.spreads import list_spreads
from app.storage.readings import fetch_recent_readings
from app.web.dependencies import get_db, get_profile, get_today
from app.web.templating import templates
import sqlite3

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def home(request: Request, today=Depends(get_today), profile: Querent | None = Depends(get_profile)) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "home.html",
        {"profile": profile, "today": today, "spreads": list_spreads()},
    )


@router.get("/history", response_class=HTMLResponse)
def history(request: Request, conn: sqlite3.Connection = Depends(get_db)) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "history.html", {"readings": fetch_recent_readings(20, conn)}
    )


@router.get("/about", response_class=HTMLResponse)
def about(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "about.html", {})


@router.get("/profile/edit")
def edit_profile_redirect(profile: Querent | None = Depends(get_profile)) -> RedirectResponse:
    return RedirectResponse(url="/" if profile else "/", status_code=303)
