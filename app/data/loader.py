"""Loading the deck from disk."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.domain.cards import Arcana, Card, Face, Suit
from app.domain.deck import Deck

CARDS_PATH = Path(__file__).parent / "cards.json"
FULL_DECK_SIZE = 78


class DeckDataError(RuntimeError):
    """Raised when the card data file is malformed."""


def _face(raw: dict[str, Any], card_slug: str, side: str) -> Face:
    summary = raw.get("summary", "")
    body = raw.get("body", [])
    if not summary or not body:
        raise DeckDataError(f"{card_slug}: {side} face is missing summary or body")
    return Face(summary=summary, body=tuple(body))


def _card(raw: dict[str, Any]) -> Card:
    slug = raw["slug"]
    suit = raw.get("suit")
    return Card(
        slug=slug,
        name=raw["name"],
        arcana=Arcana(raw["arcana"]),
        suit=Suit(suit) if suit else None,
        number=raw["number"],
        upright=_face(raw["upright"], slug, "upright"),
        reversed=_face(raw["reversed"], slug, "reversed"),
        source_index=raw["source_index"],
    )


def _validate(cards: tuple[Card, ...]) -> None:
    if len(cards) != FULL_DECK_SIZE:
        raise DeckDataError(f"expected {FULL_DECK_SIZE} cards, found {len(cards)}")
    slugs = {card.slug for card in cards}
    if len(slugs) != FULL_DECK_SIZE:
        raise DeckDataError("duplicate card slugs in deck data")
    if sorted(card.source_index for card in cards) != list(range(FULL_DECK_SIZE)):
        raise DeckDataError("source_index is not a clean permutation of 0..77")


@lru_cache(maxsize=1)
def load_deck(path: Path | None = None) -> Deck:
    """Load and validate the deck. Cached, since the data is immutable.

    Cards are ordered by ``source_index`` so the shuffle reproduces the original app.
    """
    source = path or CARDS_PATH
    raw = json.loads(source.read_text(encoding="utf-8"))
    cards = tuple(sorted((_card(entry) for entry in raw), key=lambda c: c.source_index))
    _validate(cards)
    return Deck(cards=cards)
