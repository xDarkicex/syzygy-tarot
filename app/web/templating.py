"""Single shared Jinja2Templates with all template helpers registered."""

from __future__ import annotations

from fastapi.templating import Jinja2Templates

from app.config import get_settings


def _querent_name(querent) -> str:
    if querent is None:
        return "you"
    name = getattr(querent, "name", None) or ""
    return name.strip() or "you"


def build_templates() -> Jinja2Templates:
    templates = Jinja2Templates(directory=str(get_settings().templates_dir))
    templates.env.filters["querent_name"] = _querent_name
    return templates


templates = build_templates()
