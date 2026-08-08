"""Natal chart computation from birth data, using the real Swiss-style ephemeris.

Skyfield computes actual ecliptic longitudes for the sun, moon, and planets at
the moment and place of birth. This is real astronomy — the sun was in Aries
on 1993-04-12, the moon in Capricorn, Venus in Aries, and so on. The rising
sign (ascendant) requires the exact birth location, so it is computed only when
both birth time and place are given.

The module falls back to a coarse date-based chart when skyfield is missing, so
the astrology path degrades gracefully rather than failing.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from typing import Protocol

ZODIAC = (
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
)

# Approximate lat/lon for well-known cities. Free-text birth place is resolved
# against this small table; unknown places fall back to None (no rising sign).
_CITY_COORDS: dict[str, tuple[float, float]] = {
    "london": (51.5, -0.1),
    "new york": (40.7, -74.0),
    "new york city": (40.7, -74.0),
    "nyc": (40.7, -74.0),
    "los angeles": (34.1, -118.2),
    "la": (34.1, -118.2),
    "chicago": (41.9, -87.6),
    "houston": (29.8, -95.4),
    "phoenix": (33.4, -112.1),
    "philadelphia": (39.9, -75.2),
    "san francisco": (37.8, -122.4),
    "seattle": (47.6, -122.3),
    "boston": (42.4, -71.1),
    "denver": (39.7, -105.0),
    "austin": (30.3, -97.7),
    "paris": (48.9, 2.4),
    "berlin": (52.5, 13.4),
    "madrid": (40.4, -3.7),
    "rome": (41.9, 12.5),
    "amsterdam": (52.4, 4.9),
    "brussels": (50.8, 4.3),
    "zurich": (47.4, 8.5),
    "dublin": (53.3, -6.3),
    "mexico city": (19.4, -99.1),
    "toronto": (43.7, -79.4),
    "vancouver": (49.3, -123.1),
    "montreal": (45.5, -73.6),
    "sydney": (-33.9, 151.2),
    "melbourne": (-37.8, 144.9),
    "auckland": (-36.8, 174.8),
    "mumbai": (19.1, 72.9),
    "delhi": (28.6, 77.2),
    "tokyo": (35.7, 139.7),
    "osaka": (34.7, 135.5),
    "seoul": (37.6, 127.0),
    "beijing": (39.9, 116.4),
    "hong kong": (22.3, 114.2),
    "singapore": (1.35, 103.8),
    "sao paulo": (-23.5, -46.6),
    "rio de janeiro": (-22.9, -43.2),
    "buenos aires": (-34.6, -58.4),
    "cairo": (30.0, 31.2),
    "lagos": (6.5, 3.4),
    "johannesburg": (-26.2, 28.0),
    "nairobi": (-1.3, 36.8),
}


@dataclass(frozen=True, slots=True)
class BirthChart:
    """A natal chart. Signs are names; None when not computable."""

    sun: str
    moon: str
    venus: str
    mars: str
    mercury: str
    rising: str | None = None
    # Whether this is a real ephemeris chart or a coarse fallback.
    precise: bool = False


def _sign_from_longitude(longitude: float) -> str:
    return ZODIAC[int(longitude % 360 // 30) % 12]


def _coords_for_place(place: str | None) -> tuple[float, float] | None:
    if not place:
        return None
    key = place.strip().lower()
    if key in _CITY_COORDS:
        return _CITY_COORDS[key]
    # Try "city, country" — match on the first comma part.
    city = key.split(",")[0].strip()
    return _CITY_COORDS.get(city)


def _parse_time(birth_time: str | None) -> time | None:
    if not birth_time:
        return None
    parts = birth_time.split(":")
    try:
        return time(int(parts[0]), int(parts[1]))
    except (ValueError, IndexError):
        return None


def _skyfield_chart(
    birth_date: date, birth_time: time | None, place: str | None
) -> BirthChart | None:
    try:
        from skyfield.api import Loader, wgs84  # type: ignore
    except ImportError:
        return None
    try:
        loader = Loader("/tmp/syzygy-skyfield", verbose=False)
        ts = loader.timescale()
        eph = loader("de421.bsp")
        earth = eph["earth"]

        dt = datetime.combine(birth_date, birth_time or time(12, 0))
        t = ts.from_datetime(dt.replace(tzinfo=timezone.utc))
        body_map = {
            "sun": "sun", "moon": "moon", "venus": "venus",
            "mars": "mars", "mercury": "mercury",
        }
        chart: dict[str, str] = {}
        for key, body_name in body_map.items():
            body = eph[body_name]
            app = earth.at(t).observe(body).apparent()
            lon = app.ecliptic_latlon()[1].degrees % 360
            chart[key] = _sign_from_longitude(lon)

        rising = None
        coords = _coords_for_place(place)
        if birth_time and coords:
            lat, lon = coords
            rising = _ascendant(t, lat, lon)

        return BirthChart(
            sun=chart["sun"],
            moon=chart["moon"],
            venus=chart["venus"],
            mars=chart["mars"],
            mercury=chart["mercury"],
            rising=rising,
            precise=True,
        )
    except Exception:  # noqa: BLE001
        return None


def _ascendant(t, lat: float, lon: float) -> str | None:
    """Compute the rising sign from sidereal time at the birth location.

    Uses the IAU 1982 GMST formula and the standard ascendant longitude
    formula. Returns the sign name, or None if the arithmetic fails.
    """
    try:
        # Julian centuries since J2000.0 from UT1.
        jd = t.ut1
        T = (jd - 2451545.0) / 36525.0
        gmst_sec = (
            67310.54841
            + (876600.0 * 3600 + 8640184.812866) * T
            + 0.093104 * T * T
            - 6.2e-6 * T * T * T
        )
        gmst_hours = (gmst_sec / 3600.0) % 24
        lst_hours = (gmst_hours + lon / 15) % 24
        lst_deg = lst_hours * 15

        eps = math.radians(23.44)
        lat_rad = math.radians(lat)
        lst_rad = math.radians(lst_deg)
        numerator = -math.cos(lst_rad)
        denominator = math.tan(eps) * math.cos(lat_rad) + math.sin(lst_rad) * math.sin(lat_rad)
        if denominator == 0:
            return None
        asc_longitude = math.degrees(math.atan2(numerator, denominator)) % 360
        return _sign_from_longitude(asc_longitude)
    except Exception:  # noqa: BLE001
        return None


def _coarse_chart(birth_date: date) -> BirthChart:
    """Fallback when skyfield isn't available. Sun sign from date; the rest
    are coarse estimates."""
    from app.services.ephemeris import _lookup_sun_sign
    sun = _lookup_sun_sign(birth_date)
    # Very rough: assume the moon and inner planets sit near the sun for a
    # date-based fallback. This is wrong astrologically but gives the UI
    # something to show instead of a hard failure.
    day_index = birth_date.timetuple().tm_yday
    moon = ZODIAC[int((day_index * 0.85) % 12)]
    venus = ZODIAC[int((day_index * 1.2) % 12)]
    mars = ZODIAC[int((day_index * 0.6) % 12)]
    mercury = ZODIAC[int((day_index * 1.1) % 12)]
    return BirthChart(
        sun=sun, moon=moon, venus=venus, mars=mars, mercury=mercury,
        rising=None, precise=False,
    )


def compute_birth_chart(
    birth_date: date,
    birth_time: str | None = None,
    birth_place: str | None = None,
) -> BirthChart:
    """Compute the natal chart for a birth date/time/place."""
    bt = _parse_time(birth_time)
    real = _skyfield_chart(birth_date, bt, birth_place)
    if real is not None:
        return real
    return _coarse_chart(birth_date)
