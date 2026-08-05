"""Profile management — all client-side state, this just owns the cookie mirror."""

from __future__ import annotations

from fastapi import APIRouter, Form, HTTPException, Response

from app.domain.seeding import InvalidQuerent, Querent
from app.web.auth import clear_profile_cookie, set_profile_cookie

router = APIRouter(prefix="/profile")


@router.post("/save")
def save_profile(name: str = Form(...), age: int = Form(...), resonance: str = Form(...)) -> Response:
    """Persist the profile into a signed cookie and redirect home."""
    try:
        querent = Querent(name=name, age=age, resonance=resonance)
    except InvalidQuerent as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    response = Redirect(url="/")
    set_profile_cookie(response, querent)
    return response


@router.post("/clear")
def clear_profile() -> Response:
    response = Redirect(url="/")
    clear_profile_cookie(response)
    return response


class Redirect(Response):
    def __init__(self, url: str) -> None:
        super().__init__(status_code=303)
        self.headers["Location"] = url
