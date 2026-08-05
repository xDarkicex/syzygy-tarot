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

YOU_THEM_CONNECTION = Spread(
    slug="you-them-connection",
    name="You · Them · Connection",
    tagline="Two people, one bond",
    description=(
        "Three cards for the dynamic between two people. You, them, and the energy "
        "that runs between."
    ),
    positions=(
        Position(
            key="you",
            title="You",
            prompt="What you bring to this",
            accent="ember",
        ),
        Position(
            key="them",
            title="Them",
            prompt="What they bring, or withhold",
            accent="iris",
        ),
        Position(
            key="connection",
            title="The Connection",
            prompt="What runs between you, the bond, the obstacle, the potential",
            accent="aqua",
        ),
    ),
)

HERE_THERE_NOWHERE = Spread(
    slug="here-there-nowhere",
    name="Here · There · Nowhere",
    tagline="Where you are, where you're going, what to release",
    description=(
        "Three cards for when something feels stuck. The current moment, the possible "
        "direction, and the place you should not go."
    ),
    positions=(
        Position(
            key="here",
            title="Here",
            prompt="Where you stand right now",
            accent="ember",
        ),
        Position(
            key="there",
            title="There",
            prompt="Where this is heading, if you keep going",
            accent="iris",
        ),
        Position(
            key="nowhere",
            title="Nowhere",
            prompt="What to release, the path to avoid, the void that lacks grounding",
            accent="aqua",
        ),
    ),
)

SITUATION_CHALLENGE_ADVICE = Spread(
    slug="situation-challenge-advice",
    name="Situation · Challenge · Advice",
    tagline="What's happening, what's in the way, what to do",
    description=(
        "Three cards for a specific decision or stuck situation. The current state, "
        "the obstacle, and the path forward."
    ),
    positions=(
        Position(
            key="situation",
            title="Situation",
            prompt="The current state, the heart of the matter",
            accent="ember",
        ),
        Position(
            key="challenge",
            title="Challenge",
            prompt="What blocks you, the tension, the difficulty",
            accent="iris",
        ),
        Position(
            key="advice",
            title="Advice",
            prompt="What to do next, the guidance to act on",
            accent="aqua",
        ),
    ),
)

MIND_BODY_SPIRIT = Spread(
    slug="mind-body-spirit",
    name="Mind · Body · Spirit",
    tagline="A holistic check-in",
    description=(
        "Three cards for a daily self-check. Where the mind is, where the body is, "
        "where the spirit is."
    ),
    positions=(
        Position(
            key="mind",
            title="Mind",
            prompt="Your mental state, what you are thinking, what is on your mind",
            accent="ember",
        ),
        Position(
            key="body",
            title="Body",
            prompt="Your physical state, your energy, the material and practical",
            accent="iris",
        ),
        Position(
            key="spirit",
            title="Spirit",
            prompt="Your deeper state, your intuition, what wants to emerge",
            accent="aqua",
        ),
    ),
)

QUESTION_CARD = Spread(
    slug="question",
    name="Single Card with a Question",
    tagline="One card, one question",
    description=(
        "A single draw for when you have a specific question. The card answers "
        "what you asked. Use the question field that appears when this spread "
        "is selected."
    ),
    positions=(
        Position(
            key="answer",
            title="The Card",
            prompt="The answer to the question you brought",
            accent="ember",
        ),
    ),
)

SPREADS: dict[str, Spread] = {
    s.slug: s
    for s in (
        SIGNATURE,
        SINGLE,
        TIMELINE,
        YOU_THEM_CONNECTION,
        HERE_THERE_NOWHERE,
        SITUATION_CHALLENGE_ADVICE,
        MIND_BODY_SPIRIT,
    )
}
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
