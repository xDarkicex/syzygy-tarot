"""Seed derivation.

The original Java app derived a deterministic seed from the querent's name, age, and the
day of the year, so the same person received the same reading all day. That behaviour is
preserved here in :class:`NumerologySeed`.

New generation schemes should implement :class:`SeedStrategy` and register themselves in
``STRATEGIES``; nothing outside this module needs to change.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol, runtime_checkable

MIN_AGE = 1
MAX_AGE = 120
MAX_NAME_LENGTH = 64

# Order is load-bearing: the original offered Male=1, Female=2 and fed that 1-based index
# into the seed. Keeping those first two positions means existing name/age/gender
# combinations still produce the reading they always did. Append new options, never insert.
RESONANCES: tuple[str, ...] = ("Male", "Female", "Nonbinary", "Fluid", "Unspecified")


class InvalidQuerent(ValueError):
    """Raised when querent details fall outside the supported range."""


@dataclass(frozen=True, slots=True)
class Querent:
    """The person receiving the reading."""

    name: str
    age: int
    resonance: str

    def __post_init__(self) -> None:
        _validate_name(self.name)
        _validate_age(self.age)
        _validate_resonance(self.resonance)

    @property
    def choice(self) -> int:
        """The original's 1-based menu index for the resonance."""
        return RESONANCES.index(self.resonance) + 1


def _validate_name(name: str) -> None:
    if not name.strip():
        raise InvalidQuerent("Name cannot be blank.")
    if len(name) > MAX_NAME_LENGTH:
        raise InvalidQuerent(f"Name cannot exceed {MAX_NAME_LENGTH} characters.")


def _validate_age(age: int) -> None:
    # The original divided by age, so zero raised an uncaught ArithmeticException.
    if not MIN_AGE <= age <= MAX_AGE:
        raise InvalidQuerent(f"Age must be between {MIN_AGE} and {MAX_AGE}.")


def _validate_resonance(resonance: str) -> None:
    if resonance not in RESONANCES:
        raise InvalidQuerent(f"Resonance must be one of: {', '.join(RESONANCES)}.")


@dataclass(frozen=True, slots=True)
class Numerology:
    """The intermediate values the original printed on its confirmation screen."""

    name_value: int
    age_value: int
    resonance_value: int
    day_of_year: int
    seed: int


def compute_numerology(querent: Querent, on: date) -> Numerology:
    """Port of the original formula, arithmetic step for step."""
    name_value = int(1.5 + len(querent.name))
    age_value = name_value + 100
    resonance_value = age_value + name_value + querent.choice
    day_of_year = on.timetuple().tm_yday
    total = name_value + age_value + resonance_value + day_of_year
    return Numerology(
        name_value=name_value,
        age_value=age_value,
        resonance_value=resonance_value,
        day_of_year=day_of_year,
        seed=total // querent.age,  # Java integer division; all terms are positive
    )


@runtime_checkable
class SeedStrategy(Protocol):
    """How a reading's shuffle is seeded."""

    slug: str
    label: str
    description: str

    def seed(self, querent: Querent, on: date) -> int: ...


@dataclass(frozen=True, slots=True)
class NumerologySeed:
    """Deterministic: the same querent gets the same reading for a whole day."""

    slug: str = "numerology"
    label: str = "Numerology (faithful)"
    description: str = "Your name, age, and today's date fix the shuffle. Stable all day."

    def seed(self, querent: Querent, on: date) -> int:
        return compute_numerology(querent, on).seed


@dataclass(frozen=True, slots=True)
class DailySeed:
    """The faithful formula folded with the day-of-year so consecutive days differ.

    The original ``NumerologySeed`` divides by age, which collapses consecutive days
    into the same seed for ~age days in a row. This strategy keeps the same numerology
    but XOR-mixes the day-of-year in, so every day of the year yields a different
    shuffle while the same querent still gets a stable reading for the same day.
    """

    slug: str = "daily"
    label: str = "Daily"
    description: str = "Numerology folded with the day-of-year. A different reading every day."

    def seed(self, querent: Querent, on: date) -> int:
        numerology = compute_numerology(querent, on)
        return (numerology.seed * 397) ^ numerology.day_of_year


STRATEGIES: dict[str, SeedStrategy] = {s.slug: s for s in (NumerologySeed(), DailySeed())}
DEFAULT_STRATEGY = "daily"


def get_strategy(slug: str | None) -> SeedStrategy:
    """Look up a strategy, falling back to the default."""
    return STRATEGIES.get(slug or DEFAULT_STRATEGY, STRATEGIES[DEFAULT_STRATEGY])
