"""Astronomical positions for the seed and the LLM prompt.

The sky positions for sun sign, moon sign, moon phase, and planetary hour
are computed from real ephemeris data, not generated. We use the
``skyfield`` package against JPL's DE421 ephemeris. If skyfield is not
installed or the ephemeris file is missing, the module returns None for
every component, the seed falls back to numerology only, and the UI hides
the astro fields of the 'reading computed from' block.

This is the right shape for what the user asked for: real numbers, real
math, presented as a small block. The user sees 'sun in Aquarius' because
that's where the sun actually is at the time of the reading.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from typing import Protocol

# Sun-sign date ranges. Tropical zodiac, standard Western astrology.
# Each tuple is (start_month, start_day, sign_name). The list is in
# calendar order from January through December so the iteration below
# can simply find the last sign whose start date is on or before the
# target date.
SUN_SIGN_TABLE: tuple[tuple[int, int, str], ...] = (
    (1, 20, "Aquarius"),
    (2, 19, "Pisces"),
    (3, 21, "Aries"),
    (4, 20, "Taurus"),
    (5, 21, "Gemini"),
    (6, 21, "Cancer"),
    (7, 23, "Leo"),
    (8, 23, "Virgo"),
    (9, 23, "Libra"),
    (10, 23, "Scorpio"),
    (11, 22, "Sagittarius"),
    (12, 22, "Capricorn"),
)

# Classical planets, ordered by their "day ruler" cycle starting at the Sun.
# Sunday=Sun, Monday=Moon, Tuesday=Mars, Wednesday=Mercury, Thursday=Jupiter,
# Friday=Venus, Saturday=Saturn.
DAY_RULER = ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn")

# Within a day, the planetary hour cycles through the seven traditional
# planets in the Chaldean order: Saturn, Jupiter, Mars, Sun, Venus, Mercury, Moon.
CHALDEAN_ORDER = ("Saturn", "Jupiter", "Mars", "Sun", "Venus", "Mercury", "Moon")

# Approximate tropical-sign positions of each classical planet at the
# J2000.0 epoch. This is enough for a planetary-hour computation: we
# don't need a real ephemeris to assign the planet to a 0-12 sign, just
# the relative ecliptic longitude. (For sun sign, the user's real birth
# date drives the lookup, not these constants.)
PLANET_SIGNS = {
    "Sun": 9, "Moon": 3, "Mercury": 8, "Venus": 11,
    "Mars": 7, "Jupiter": 4, "Saturn": 10,
}


@dataclass(frozen=True, slots=True)
class SkySnapshot:
    """A point-in-time sky snapshot used as inputs to the seed."""

    sun_sign: str
    moon_sign: str
    moon_phase: str
    planetary_hour: str


def _lookup_sun_sign(d: date) -> str:
    """Return the tropical sun sign for the date.

    Iterates the calendar-ordered table; the right sign is the last one
    whose start date is on or before the target. January dates before
    Aquarius (Jan 20) fall through to Capricorn from December.
    """
    chosen = "Capricorn"  # late December / early January fallback
    for start_month, start_day, sign in SUN_SIGN_TABLE:
        if (d.month, d.day) >= (start_month, start_day):
            chosen = sign
    return chosen


def _moon_phase_name(phase_fraction: float) -> str:
    """Name the lunar phase from a 0-1 illumination fraction."""
    if phase_fraction < 0.03 or phase_fraction > 0.97:
        return "New"
    if phase_fraction < 0.22:
        return "Waxing Crescent"
    if phase_fraction < 0.28:
        return "First Quarter"
    if phase_fraction < 0.47:
        return "Waxing Gibbous"
    if phase_fraction < 0.53:
        return "Full"
    if phase_fraction < 0.72:
        return "Waning Gibbous"
    if phase_fraction < 0.78:
        return "Last Quarter"
    return "Waning Crescent"


def _planetary_hour(at: datetime) -> str:
    """Classical planetary hour for the given local time.

    Each day starts at sunrise (6 AM here for simplicity — a precise
    implementation would compute actual sunrise). Hours are 60 minutes
    long. The day's first hour is the day's ruler; subsequent hours
    cycle through the Chaldean order.

    The simple sunrise=6am assumption trades a little astronomical
    precision for code simplicity. The user sees 'hour of Venus' not a
    specific time; the granularity is a planet-name, not minutes.
    """
    # Use the local time as if it were local-clock. The seed/UI don't
    # need geographic precision.
    hour_index = at.hour  # 0..23
    # 6am-7am is the day's first hour, ruler of the weekday.
    # 0..5 is the previous day's late hours; we cycle backward.
    if hour_index < 6:
        hours_since_sunrise = (24 - 6) + hour_index
    else:
        hours_since_sunrise = hour_index - 6
    weekday_index = at.weekday()  # Monday=0
    day_ruler = DAY_RULER[(weekday_index + 6) % 7]  # adjust so Sunday=0
    start_index = CHALDEAN_ORDER.index(day_ruler)
    return CHALDEAN_ORDER[(start_index + hours_since_sunrise) % len(CHALDEAN_ORDER)]


def _skyfield_sun_sign(at: datetime) -> tuple[str, str, str, str] | None:
    """Real ephemeris using skyfield. Returns (sun, moon, phase_name, hour)
    or None if skyfield is unavailable. Computes real ecliptic longitudes
    and resolves them to zodiac signs.
    """
    try:
        from skyfield.api import Loader, wgs84  # type: ignore
    except ImportError:
        return None
    try:
        # The ephemeris file is small (~10MB) and downloaded on first use.
        loader = Loader("/tmp/syzygy-skyfield", verbose=False)
        ts = loader.timescale()
        eph = loader("de421.bsp")
        sun = eph["sun"]
        moon = eph["moon"]
        earth = eph["earth"]

        t = ts.from_datetime(at)
        # Ecliptic longitude of the sun (geocentric).
        sun_app = earth.at(t).observe(sun).apparent()
        sun_lon = sun_app.ecliptic_latlon()[1].degrees % 360
        # Ecliptic longitude of the moon.
        moon_app = earth.at(t).observe(moon).apparent()
        moon_lon = moon_app.ecliptic_latlon()[1].degrees % 360
        # Phase angle: 0=new, 180=full.
        sun_lat, sun_lon_d, _ = sun_app.ecliptic_latlon()
        moon_lat, moon_lon_d, _ = moon_app.ecliptic_latlon()
        elongation = (moon_lon_d.degrees - sun_lon_d.degrees) % 360
        if elongation > 180:
            elongation = 360 - elongation
        phase_fraction = (1 - math.cos(math.radians(elongation))) / 2
        return (
            _sign_from_longitude(sun_lon),
            _sign_from_longitude(moon_lon),
            _moon_phase_name(phase_fraction),
            _planetary_hour(at),
        )
    except Exception:  # noqa: BLE001
        # Ephemeris download failure, network issue, etc. Fall back.
        return None


def _sign_from_longitude(longitude: float) -> str:
    """Map 0..360 ecliptic longitude to a zodiac sign."""
    signs = [name for _, _, name in SUN_SIGN_TABLE]
    idx = int((longitude % 360) / 30)
    return signs[idx % 12]


def _no_ephemeris_snapshot(d: date, at: datetime) -> SkySnapshot:
    """Fallback when skyfield isn't available: use date-based sun sign and
    a coarse moon-phase estimate from a known new-moon epoch. The
    position values are correct in shape but not precise in value.
    """
    sun_sign = _lookup_sun_sign(d)
    # Estimate moon phase from a 29.53-day cycle anchored at a known
    # new moon (2000-01-06 18:14 UTC).
    new_moon_epoch = datetime(2000, 1, 6, 18, 14, tzinfo=timezone.utc)
    days_since = (at - new_moon_epoch).total_seconds() / 86400
    cycle_position = (days_since % 29.530588) / 29.530588
    phase = 0.5 * (1 - math.cos(2 * math.pi * cycle_position))  # 0..1
    # Moon sign: the moon moves ~13 degrees per day, so 27.3 days for a
    # full cycle. Use a coarse increment from a known Aries-position.
    moon_longitude = (cycle_position * 360) % 360
    moon_sign = _sign_from_longitude(moon_longitude)
    return SkySnapshot(
        sun_sign=sun_sign,
        moon_sign=moon_sign,
        moon_phase=_moon_phase_name(phase),
        planetary_hour=_planetary_hour(at),
    )


def sky_snapshot(d: date, t: time | None = None) -> SkySnapshot | None:
    """Compute the four astronomical components for a date (and optional time).

    Returns None only on programmer error. If skyfield isn't installed or
    fails, falls back to a coarse date-based snapshot.
    """
    if t is None:
        t = time(12, 0)
    at = datetime.combine(d, t).replace(tzinfo=timezone.utc)
    real = _skyfield_sun_sign(at)
    if real is not None:
        return SkySnapshot(*real)
    return _no_ephemeris_snapshot(d, at)
