"""Single shared Jinja2Templates with all template helpers registered."""

from __future__ import annotations

from fastapi.templating import Jinja2Templates

from app.config import get_settings

# Moon sign → recommended focus vector, for the dashboard's "what the sky
# suggests today" line.
_MOON_VECTOR = {
    "Aries": "Career & Work",
    "Taurus": "Money & Security",
    "Gemini": "Career & Work",
    "Cancer": "Love & Relationships",
    "Leo": "Self & Growth",
    "Virgo": "Money & Security",
    "Libra": "Love & Relationships",
    "Scorpio": "Love & Relationships",
    "Sagittarius": "Self & Growth",
    "Capricorn": "Career & Work",
    "Aquarius": "Self & Growth",
    "Pisces": "Family",
}


def _querent_name(querent) -> str:
    if querent is None:
        return "you"
    name = getattr(querent, "name", None) or ""
    return name.strip() or "you"


def _vector_focus(moon_sign: str | None) -> str:
    return _MOON_VECTOR.get(moon_sign or "", "Self & Growth")


def build_templates() -> Jinja2Templates:
    templates = Jinja2Templates(directory=str(get_settings().templates_dir))
    templates.env.filters["querent_name"] = _querent_name
    templates.env.filters["vector_focus"] = _vector_focus
    return templates


templates = build_templates()
