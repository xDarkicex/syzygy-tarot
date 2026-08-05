"""The deck and the deal.

``deal`` reproduces the original ``Deck`` class exactly: seed a Java-compatible RNG,
shuffle the whole deck once, then take cards off the top, consuming one ``nextDouble()``
per card to decide its orientation. The interleaving of shuffle and orientation draws
matters, because both come from the same RNG stream.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.cards import Card, Orientation
from app.domain.java_random import JavaRandom, java_shuffle
from app.domain.spreads import Position, Spread

REVERSAL_THRESHOLD = 0.5


class DeckExhausted(RuntimeError):
    """Raised when a spread needs more cards than the deck holds."""


@dataclass(frozen=True, slots=True)
class Deck:
    cards: tuple[Card, ...]

    def __len__(self) -> int:
        return len(self.cards)

    def by_slug(self, slug: str) -> Card:
        for card in self.cards:
            if card.slug == slug:
                return card
        raise KeyError(slug)

    @property
    def index(self) -> dict[str, Card]:
        return {card.slug: card for card in self.cards}


@dataclass(frozen=True, slots=True)
class DrawnCard:
    position: Position
    card: Card
    orientation: Orientation

    @property
    def is_reversed(self) -> bool:
        return self.orientation is Orientation.REVERSED

    @property
    def summary(self) -> str:
        return self.card.face(self.orientation).summary

    @property
    def body(self) -> tuple[str, ...]:
        return self.card.face(self.orientation).body


def _orientation(rng: JavaRandom) -> Orientation:
    """Original: ``card.setReverse(rng.nextDouble() > 0.5)``."""
    reversed_up = rng.next_double() > REVERSAL_THRESHOLD
    return Orientation.REVERSED if reversed_up else Orientation.UPRIGHT


def deal(deck: Deck, spread: Spread, seed: int) -> tuple[DrawnCard, ...]:
    """Deal a spread from a seeded deck, reproducing the original's RNG consumption."""
    if len(spread) > len(deck):
        raise DeckExhausted(f"{spread.slug} needs {len(spread)} cards, deck holds {len(deck)}")

    rng = JavaRandom(seed)
    remaining = list(deck.cards)
    java_shuffle(remaining, rng)

    drawn = []
    for position in spread.positions:
        card = remaining.pop(0)
        drawn.append(DrawnCard(position=position, card=card, orientation=_orientation(rng)))
    return tuple(drawn)
