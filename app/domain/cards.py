"""Card models. Pure data, no I/O."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Arcana(StrEnum):
    MAJOR = "major"
    MINOR = "minor"


class Suit(StrEnum):
    WANDS = "wands"
    CUPS = "cups"
    SWORDS = "swords"
    COINS = "coins"


class Orientation(StrEnum):
    UPRIGHT = "upright"
    REVERSED = "reversed"


SUIT_ELEMENT: dict[Suit, str] = {
    Suit.WANDS: "fire",
    Suit.CUPS: "water",
    Suit.SWORDS: "air",
    Suit.COINS: "earth",
}

RANK_NAMES: dict[int, str] = {
    1: "Ace", 2: "Two", 3: "Three", 4: "Four", 5: "Five", 6: "Six", 7: "Seven",
    8: "Eight", 9: "Nine", 10: "Ten", 11: "Page", 12: "Knight", 13: "Queen", 14: "King",
}


@dataclass(frozen=True, slots=True)
class Face:
    """One interpretive side of a card."""

    summary: str
    body: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Card:
    slug: str
    name: str
    arcana: Arcana
    suit: Suit | None
    number: int
    upright: Face
    reversed: Face
    # Position in the original Java Deck array. The shuffle permutes positions, so this
    # ordering is what makes readings reproduce the original app's exactly.
    source_index: int

    def face(self, orientation: Orientation) -> Face:
        return self.upright if orientation is Orientation.UPRIGHT else self.reversed

    @property
    def element(self) -> str | None:
        return SUIT_ELEMENT.get(self.suit) if self.suit else None

    @property
    def is_major(self) -> bool:
        return self.arcana is Arcana.MAJOR
