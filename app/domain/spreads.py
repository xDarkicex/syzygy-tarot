"""Spreads, defined as data so new layouts cost one entry and no code."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Position:
    """One slot in a spread."""

    key: str
    title: str
    prompt: str
    accent: str


@dataclass(frozen=True, slots=True)
class Spread:
    slug: str
    name: str
    tagline: str
    description: str
    positions: tuple[Position, ...]

    def __len__(self) -> int:
        return len(self.positions)


class UnknownSpread(KeyError):
    """Raised when a spread slug is not registered."""


# The original's three-card reading. Titles and accent colours are carried over from the
# ANSI colours it printed: red, purple, cyan.
SIGNATURE = Spread(
    slug="hear-help-hold",
    name="Hear Me / Help Me / Hold Me",
    tagline="The original three-card reading",
    description=(
        "Three cards for what needs saying, what needs doing, and what needs keeping. "
        "This is the spread the original reader always dealt."
    ),
    positions=(
        Position(
            key="hear",
            title="Hear Me",
            prompt="What is asking to be acknowledged right now?",
            accent="ember",
        ),
        Position(
            key="help",
            title="Help Me",
            prompt="Where should your effort actually go?",
            accent="iris",
        ),
        Position(
            key="hold",
            title="Hold Me",
            prompt="What is worth protecting while the rest moves?",
            accent="aqua",
        ),
    ),
)

SINGLE = Spread(
    slug="single",
    name="Single Card",
    tagline="One card, one question",
    description="A single draw for when the question is already clear.",
    positions=(
        Position(
            key="focus",
            title="The Card",
            prompt="What matters most about this?",
            accent="ember",
        ),
    ),
)

TIMELINE = Spread(
    slug="past-present-future",
    name="Past / Present / Future",
    tagline="How the situation is moving",
    description="Three cards tracing where this came from, where it stands, and where it tends.",
    positions=(
        Position(
            key="past",
            title="Past",
            prompt="What set this in motion?",
            accent="iris",
        ),
        Position(
            key="present",
            title="Present",
            prompt="What is true at this moment?",
            accent="ember",
        ),
        Position(
            key="future",
            title="Future",
            prompt="Where is this heading if nothing changes?",
            accent="aqua",
        ),
    ),
)

SPREADS: dict[str, Spread] = {s.slug: s for s in (SIGNATURE, SINGLE, TIMELINE)}
DEFAULT_SPREAD = SIGNATURE.slug


def get_spread(slug: str | None) -> Spread:
    """Look up a spread by slug, defaulting to the signature reading."""
    if not slug:
        return SPREADS[DEFAULT_SPREAD]
    try:
        return SPREADS[slug]
    except KeyError as exc:
        raise UnknownSpread(slug) from exc


def list_spreads() -> tuple[Spread, ...]:
    return tuple(SPREADS.values())
