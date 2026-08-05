"""Seed derivation.

The original Java app derived a deterministic seed from the querent's name, age, and the
day of the year, so the same person received the same reading all day. That behaviour is
preserved here in :class:`NumerologySeed`.

New generation schemes should implement :class:`SeedStrategy` and register themselves in
``STRATEGIES``; nothing outside this module needs to change.
"""

from __future__ import annotations

import dataclasses
import hashlib
from dataclasses import dataclass
from datetime import date
from typing import Protocol, runtime_checkable

from app.services.ephemeris import sky_snapshot

MIN_AGE = 1
MAX_AGE = 120
MAX_NAME_LENGTH = 64

# Order is load-bearing: the original offered Male=1, Female=2 and fed that 1-based index
# into the seed. Keeping those first two positions means existing name/age/gender
# combinations still produce the reading they always did. Append new options, never insert.
RESONANCES: tuple[str, ...] = ("Male", "Female", "Nonbinary", "Fluid", "Unspecified")

# Sexuality is a separate field — used by the LLM for relationship/connection
# advice, not by the seed. The label is "Drawn to" to make the intent
# obvious without sounding clinical. The "Prefer not to say" option keeps
# the field optional without forcing a label.
DRAWN_TO: tuple[str, ...] = (
    "Men",
    "Women",
    "Nonbinary people",
    "All / exploring",
    "No preference",
    "Prefer not to say",
)


class InvalidQuerent(ValueError):
    """Raised when querent details fall outside the supported range."""


@dataclass(frozen=True, slots=True)
class Querent:
    """The person receiving the reading."""

    name: str
    age: int
    resonance: str
    drawn_to: str = "Prefer not to say"
    birth_date: date | None = None
    birth_time: str | None = None  # "HH:MM" 24-hour, optional
    birth_place: str | None = None  # free-text city name, optional

    def __post_init__(self) -> None:
        _validate_name(self.name)
        _validate_age(self.age)
        _validate_resonance(self.resonance)
        _validate_drawn_to(self.drawn_to)
        _validate_birth_date(self.birth_date)
        _validate_birth_time(self.birth_time)

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
    if not MIN_AGE <= age <= MAX_AGE:
        raise InvalidQuerent(f"Age must be between {MIN_AGE} and {MAX_AGE}.")


def _validate_resonance(resonance: str) -> None:
    if resonance not in RESONANCES:
        raise InvalidQuerent(f"Resonance must be one of: {', '.join(RESONANCES)}.")


def _validate_drawn_to(drawn_to: str) -> None:
    if drawn_to not in DRAWN_TO:
        raise InvalidQuerent(f"Drawn to must be one of: {', '.join(DRAWN_TO)}.")


def _validate_birth_date(birth_date: date | None) -> None:
    if birth_date is None:
        return
    if birth_date > date.today():
        raise InvalidQuerent("Birth date cannot be in the future.")


def _validate_birth_time(birth_time: str | None) -> None:
    if birth_time is None or birth_time == "":
        return
    parts = birth_time.split(":")
    if len(parts) != 2:
        raise InvalidQuerent("Birth time must be HH:MM in 24-hour format.")
    try:
        h, m = int(parts[0]), int(parts[1])
    except ValueError as exc:
        raise InvalidQuerent("Birth time must be HH:MM in 24-hour format.") from exc
    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise InvalidQuerent("Birth time must be HH:MM in 24-hour format.")


# ─────── Numerology ───────

# Pythagorean letter values. A=1, B=2, ..., I=9, J=1, K=2, ..., R=9, S=1, ..., Z=8.
# This is the standard Western numerology table, used by most numerology systems.
_PYTHAGOREAN_VALUES: dict[str, int] = {
    "A": 1, "B": 2, "C": 3, "D": 4, "E": 5, "F": 6, "G": 7, "H": 8, "I": 9,
    "J": 1, "K": 2, "L": 3, "M": 4, "N": 5, "O": 6, "P": 7, "Q": 8, "R": 9,
    "S": 1, "T": 2, "U": 3, "V": 4, "W": 5, "X": 6, "Y": 7, "Z": 8,
}
MASTER_NUMBERS = (11, 22, 33)


def _reduce_to_digit(n: int) -> int:
    """Reduce a number to a single digit, preserving master numbers 11/22/33."""
    while n > 9 and n not in MASTER_NUMBERS:
        n = sum(int(d) for d in str(n))
    return n


def name_vibration(name: str) -> int:
    """Sum the Pythagorean letter values of a name, reduced to a digit or master number."""
    total = 0
    for ch in name.upper():
        if ch in _PYTHAGOREAN_VALUES:
            total += _PYTHAGOREAN_VALUES[ch]
    return _reduce_to_digit(total)


def life_path(birth: date) -> int:
    """Life path from the birth date: sum of month, day, and reduced year, all reduced."""
    year_reduced = _reduce_to_digit(birth.year)
    month_reduced = _reduce_to_digit(birth.month)
    day_reduced = _reduce_to_digit(birth.day)
    return _reduce_to_digit(year_reduced + month_reduced + day_reduced)


def day_vibration(on: date) -> int:
    """Day-of-year reduced to a single digit or master number."""
    return _reduce_to_digit(on.timetuple().tm_yday)


# ─────── Seed components ───────

@dataclass(frozen=True, slots=True)
class SeedComponents:
    """All the inputs that feed into the seed, plus the final seed value.

    Visible to the user as a 'reading computed from' block. The seed itself is
    the only thing the deal uses.
    """

    name_vibration: int
    life_path: int
    day_vibration: int
    resonance_index: int
    # Astronomical components are optional. None if birth data wasn't given
    # or the ephemeris isn't installed.
    sun_sign: str | None = None
    moon_sign: str | None = None
    moon_phase: str | None = None
    planetary_hour: str | None = None
    seed: int = 0


def compute_seed(components: SeedComponents) -> int:
    """Deterministic seed: SHA-256 over the component values, reduced to int32.

    The same components always produce the same seed. Different components
    produce different seeds with high probability.
    """
    parts = [
        str(components.name_vibration),
        str(components.life_path),
        str(components.day_vibration),
        str(components.resonance_index),
        components.sun_sign or "",
        components.moon_sign or "",
        components.moon_phase or "",
        components.planetary_hour or "",
    ]
    payload = "|".join(parts).encode("utf-8")
    digest = hashlib.sha256(payload).digest()
    # Take 4 bytes as the seed. Big-endian, signed 32-bit.
    return int.from_bytes(digest[:4], byteorder="big", signed=True)


# ─────── Backward-compat path ───────

@dataclass(frozen=True, slots=True)
class Numerology:
    """The intermediate values the original printed on its confirmation screen."""

    name_value: int
    age_value: int
    resonance_value: int
    day_of_year: int
    seed: int


def compute_numerology(querent: Querent, on: date) -> Numerology:
    """Port of the original formula, kept for backward compat with existing tests."""
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
        seed=total // querent.age,
    )


@runtime_checkable
class SeedStrategy(Protocol):
    """How a reading's shuffle is seeded."""

    slug: str
    label: str
    description: str

    def seed(self, querent: Querent, on: date, spread_slug: str) -> int: ...


@dataclass(frozen=True, slots=True)
class NumerologySeed:
    """The faithful original formula. Same querent+day = same reading, always,
    regardless of spread. Bit-exact to the Java source.
    """

    slug: str = "numerology"
    label: str = "Numerology (faithful)"
    description: str = "Your name, age, and today's date fix the shuffle. Stable all day."

    def seed(self, querent: Querent, on: date, spread_slug: str) -> int:
        # spread_slug is intentionally ignored: this strategy reproduces the original
        # Java behaviour exactly, where there was only one spread.
        _ = spread_slug
        return compute_numerology(querent, on).seed


@dataclass(frozen=True, slots=True)
class LayeredSeed:
    """The new layered seed. Numerology + astronomical positions + spread slug.

    The same components always produce the same seed. Different components
    produce different seeds with high probability. The components are also
    returned for display in the 'reading computed from' block.
    """

    slug: str = "layered"
    label: str = "Daily Reading"
    description: str = "Your name, birth path, today's date, and the sky at the time of the reading."

    def seed(self, querent: Querent, on: date, spread_slug: str) -> int:
        return _build_components(querent, on, spread_slug).seed

    def components(self, querent: Querent, on: date, spread_slug: str) -> SeedComponents:
        return _build_components(querent, on, spread_slug)


def _build_components(querent: Querent, on: date, spread_slug: str) -> SeedComponents:
    name_vib = name_vibration(querent.name)
    life = life_path(querent.birth_date) if querent.birth_date else 0
    day = day_vibration(on)
    snapshot = sky_snapshot(on)
    sun = moon = phase = hour = None
    if snapshot is not None:
        sun = snapshot.sun_sign
        moon = snapshot.moon_sign
        phase = snapshot.moon_phase
        hour = snapshot.planetary_hour
    base = SeedComponents(
        name_vibration=name_vib,
        life_path=life,
        day_vibration=day,
        resonance_index=querent.choice,
        sun_sign=sun,
        moon_sign=moon,
        moon_phase=phase,
        planetary_hour=hour,
    )
    spread_salt = _spread_salt(spread_slug)
    salted_seed = (compute_seed(base) ^ spread_salt) & 0xFFFFFFFF
    return dataclasses.replace(base, seed=salted_seed)


def _spread_salt(slug: str) -> int:
    """Stable, deterministic salt derived from the spread slug."""
    h = 0
    for ch in slug:
        h = (h * 131 + ord(ch)) & 0xFFFFFFFF
    return h


STRATEGIES: dict[str, SeedStrategy] = {
    s.slug: s for s in (NumerologySeed(), LayeredSeed())
}
DEFAULT_STRATEGY = "layered"


def get_strategy(slug: str | None) -> SeedStrategy:
    """Look up a strategy, falling back to the default."""
    return STRATEGIES.get(slug or DEFAULT_STRATEGY, STRATEGIES[DEFAULT_STRATEGY])
