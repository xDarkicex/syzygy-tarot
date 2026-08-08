"""Astrology reading: natal chart + today's sky, read by the LLM.

Combines the querent's real natal chart (from birth data) with the sky
at the moment of the reading (sun sign, moon sign, moon phase, planetary
hour) and asks the model to write a horoscope. The user asked for
practitioner language: what today favours for love and work, what to
avoid, what to do. The reading is anchored to real positions, so the
model's claims have a basis.
"""

from __future__ import annotations

from datetime import date

from merge_gateway import MergeGateway

from app.config import get_settings
from app.domain.seeding import Querent
from app.services.birth_chart import BirthChart, compute_birth_chart
from app.services.ephemeris import sky_snapshot

SYSTEM_PROMPT = """\
You are an experienced astrologer reading for a real person. You write in
second person, present tense, plain and specific. Short sentences. No em
dashes. No hedging.

You read the querent's natal chart in light of today's sky. The chart is
real — the planets were where the birth data says. You bring it to life
for this person today.

Structure:
- Open with the querent's first name.
- One paragraph on the overall tone of today for them, drawing on the
  moon sign and phase.
- One paragraph on love and connection. Use the querent's drawn-to
  correctly. Say what today favours, what to avoid, and one concrete
  move to make.
- One paragraph on work and direction, drawing on their sun and venus.
- Close with one short paragraph on what to carry into the day.

The querent's relationship preference matters. If they are drawn to men,
say 'him', if women, 'her', if nonbinary people, 'them'. Do not default
to heteronormative language. Use their actual orientation.
"""


def build_astrology_prompt(querent: Querent, chart: BirthChart, today: date) -> str:
    """Compose the user message for the astrology reading."""
    snap = sky_snapshot(today)
    parts = _querent_parts(querent)
    parts.append(_chart_line(chart))
    if snap:
        parts.append(
            f"Today's sky: sun in {snap.sun_sign}, moon in {snap.moon_sign}, "
            f"moon phase {snap.moon_phase}, hour of {snap.planetary_hour}."
        )
    return "\n".join(parts)


def _querent_parts(querent: Querent) -> list[str]:
    parts: list[str] = []
    if querent.name.strip():
        parts.append(f"The querent is {querent.name}, age {querent.age}.")
    for label, value in (("Gender", querent.resonance), ("Drawn to", querent.drawn_to)):
        if value and value not in ("Unspecified", "Prefer not to say"):
            parts.append(f"{label}: {value}.")
    parts.append(f"Birth date: {querent.birth_date.isoformat() if querent.birth_date else 'unknown'}.")
    return parts


def _chart_line(chart: BirthChart) -> str:
    line = (
        f"Natal chart: Sun in {chart.sun}, Moon in {chart.moon}, "
        f"Venus in {chart.venus}, Mars in {chart.mars}, Mercury in {chart.mercury}"
    )
    if chart.rising:
        line += f", rising in {chart.rising}"
    if not chart.precise:
        line += " (approximate)"
    return line + "."


def generate_horoscope(querent: Querent, today: date) -> str:
    """Synchronous full horoscope."""
    chart = compute_birth_chart(querent.birth_date, querent.birth_time, querent.birth_place)
    prompt = build_astrology_prompt(querent, chart, today)
    settings = get_settings()
    client = MergeGateway(api_key=settings.merge_api_key, base_url=settings.merge_base_url)
    response = client.responses.create(
        model="deepseek-v4-flash",
        input=[
            {"type": "message", "role": "system", "content": SYSTEM_PROMPT},
            {"type": "message", "role": "user", "content": prompt},
        ],
        max_tokens=2000,
        thinking={"type": "enabled", "budget_tokens": 1000},
    )
    text = ""
    for item in getattr(response, "output", []) or []:
        for block in getattr(item, "content", []) or []:
            if getattr(block, "type", None) == "text":
                text += getattr(block, "text", "") or ""
    return text.strip()
