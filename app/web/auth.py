"""Profile cookie.

Profiles are stored in localStorage on the client and mirrored into a signed cookie so
the server can prefill the form on first paint. Nothing here is sensitive — it's just
name, age, and resonance.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date
from typing import Any

from fastapi import Response
from itsdangerous import BadSignature, URLSafeSerializer

from app.config import get_settings
from app.domain.seeding import Querent

SALT = "profile-v1"


def _signer() -> URLSafeSerializer:
    return URLSafeSerializer(get_settings().secret_key, salt=SALT)


def profile_cookie_value(querent: Querent) -> str:
    payload = {
        "name": querent.name,
        "age": querent.age,
        "resonance": querent.resonance,
        "drawn_to": querent.drawn_to,
        "birth_date": querent.birth_date.isoformat() if querent.birth_date else "",
        "birth_time": querent.birth_time or "",
        "birth_place": querent.birth_place or "",
        "mbti": querent.mbti or "",
        "focus": list(querent.focus),
        "relationship_status": querent.relationship_status or "",
        "user_id": querent.user_id or "",
    }
    return _signer().dumps(payload)


def read_profile_cookie(raw: str | None) -> Querent | None:
    if not raw:
        return None
    try:
        payload: dict[str, Any] = _signer().loads(raw)
    except BadSignature:
        return None
    try:
        return _querent_from_payload(payload)
    except Exception:
        return None


def _querent_from_payload(payload: dict[str, Any]) -> Querent:
    """Build a Querent from the cookie payload, coercing defaults."""
    birth_time = payload.get("birth_time") or None
    birth_place = payload.get("birth_place") or None
    mbti = payload.get("mbti") or None
    rel_status = payload.get("relationship_status") or None
    user_id = payload.get("user_id") or None
    return Querent(
        name=payload.get("name", ""),
        age=payload.get("age", 30),
        resonance=payload.get("resonance", "Unspecified"),
        drawn_to=payload.get("drawn_to", "Prefer not to say"),
        birth_date=_parse_date(payload.get("birth_date")),
        birth_time=birth_time,
        birth_place=birth_place,
        mbti=mbti,
        focus=tuple(payload.get("focus", []) or []),
        relationship_status=rel_status,
        user_id=user_id,
    )


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def set_profile_cookie(response: Response, querent: Querent) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.profile_cookie,
        value=profile_cookie_value(querent),
        max_age=settings.cookie_max_age,
        secure=settings.cookie_secure,
        httponly=True,
        samesite="lax",
    )


def clear_profile_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(settings.profile_cookie)


def querent_from_form(form: Any) -> Querent:
    """Adapt a FastAPI/Starlette form for :class:`Querent`."""
    return Querent(
        name=str(form.get("name", "")).strip(),
        age=int(form.get("age", 0)),
        resonance=str(form.get("resonance", "")),
    )


def querent_to_dict(querent: Querent) -> dict[str, Any]:
    return asdict(querent)


def querent_to_json(querent: Querent) -> str:
    return json.dumps(querent_to_dict(querent))
