"""Assembling a complete reading. Pure domain logic; persistence lives elsewhere."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.domain.deck import Deck, DrawnCard, deal
from app.domain.seeding import Numerology, Querent, SeedStrategy, compute_numerology
from app.domain.spreads import Spread


@dataclass(frozen=True, slots=True)
class Reading:
    """A dealt spread plus everything needed to explain and reproduce it."""

    querent: Querent
    spread: Spread
    strategy_slug: str
    seed: int
    drawn: tuple[DrawnCard, ...]
    drawn_on: date
    numerology: Numerology | None = None

    @property
    def reversed_count(self) -> int:
        return sum(1 for card in self.drawn if card.is_reversed)

    @property
    def major_count(self) -> int:
        return sum(1 for card in self.drawn if card.card.is_major)


def build_reading(
    deck: Deck,
    spread: Spread,
    querent: Querent,
    strategy: SeedStrategy,
    on: date,
) -> Reading:
    """Deal a reading for a querent on a given day."""
    seed = strategy.seed(querent, on, spread.slug)
    numerology = compute_numerology(querent, on) if strategy.slug == "numerology" else None
    return Reading(
        querent=querent,
        spread=spread,
        strategy_slug=strategy.slug,
        seed=seed,
        drawn=deal(deck, spread, seed),
        drawn_on=on,
        numerology=numerology,
    )
