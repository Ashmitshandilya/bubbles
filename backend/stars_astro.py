"""Low-precision astronomy for the Stars lens (renovation plan 8.3). Pure, standard library only, no network.

Sun: Meeus, Astronomical Algorithms, ch. 25 (low accuracy). Moon: ch. 47, the main periodic terms. Sidereal time: ch. 12. Ascendant: the
standard formula from the local sidereal time. Sidereal signs use Lahiri ayanamsa (23.853 degrees at J2000.0, plus 50.29 arc seconds a year).
Good to a few hundredths of a degree for 1900 to 2100, which is far finer than a sign (30 degrees) or a nakshatra (13.33 degrees) and is the
only precision this ever claims. Nothing here predicts anything.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

J2000 = 2451545.0
AYANAMSA_J2000 = 23.853
AYANAMSA_RATE_DEG_PER_YEAR = 50.29 / 3600.0

# Meeus table 47.A, longitude terms: (D, M, M', F, coefficient in 1e-6 degrees)
_MOON_TERMS = (
    (0, 0, 1, 0, 6288774), (2, 0, -1, 0, 1274027), (2, 0, 0, 0, 658314), (0, 0, 2, 0, 213618), (0, 1, 0, 0, -185116), (0, 0, 0, 2, -114332),
    (2, 0, -2, 0, 58793), (2, -1, -1, 0, 57066), (2, 0, 1, 0, 53322), (2, -1, 0, 0, 45758), (0, 1, -1, 0, -40923), (1, 0, 0, 0, -34720),
    (0, 1, 1, 0, -30383), (2, 0, 0, -2, 15327), (0, 0, 1, 2, -12528), (0, 0, 1, -2, 10980), (4, 0, -1, 0, 10675), (0, 0, 3, 0, 10034),
    (4, 0, -2, 0, 8548), (2, 1, -1, 0, -7888), (2, 1, 0, 0, -6766), (1, 0, -1, 0, -5163), (1, 1, 0, 0, 4987), (2, -1, 1, 0, 4036),
    (2, 0, 2, 0, 3994), (4, 0, 0, 0, 3861), (2, 0, -3, 0, 3665), (0, 1, -2, 0, -2689), (2, 0, -1, 2, -2602), (2, -1, -2, 0, 2390),
    (1, 0, 1, 0, -2348), (2, -2, 0, 0, 2236), (0, 1, 2, 0, -2120), (0, 2, 0, 0, -2069), (2, -2, -1, 0, 2048), (2, 0, 1, -2, -1773),
    (2, 0, 0, 2, -1595), (4, -1, -1, 0, 1215), (0, 0, 2, 2, -1110), (3, 0, -1, 0, -892), (2, 1, 1, 0, -810), (4, -1, -2, 0, 759),
    (0, 2, -1, 0, -713), (2, 2, -1, 0, -700), (2, 1, -2, 0, 691), (2, -1, 0, -2, 596), (4, 0, 1, 0, 549), (0, 0, 4, 0, 537),
    (4, -1, 0, 0, 520), (1, 0, -2, 0, -487), (2, 1, 0, -2, -399), (0, 0, 2, -2, -381), (1, 1, 1, 0, 351), (3, 0, -2, 0, -340),
    (4, 0, -3, 0, 330), (2, -1, 2, 0, 327), (0, 2, 1, 0, -323), (1, 1, -1, 0, 299), (2, 0, 3, 0, 294),
)


def _rad(x: float) -> float:
    return math.radians(x)


def julian_day(moment: datetime) -> float:
    """Julian day of an aware or naive-UTC datetime (Gregorian calendar)."""
    if moment.tzinfo is not None:
        moment = moment.astimezone(timezone.utc)
    y, m = moment.year, moment.month
    d = moment.day + (moment.hour + (moment.minute + (moment.second + moment.microsecond / 1e6) / 60.0) / 60.0) / 24.0
    if m <= 2:
        y, m = y - 1, m + 12
    a = y // 100
    b = 2 - a + a // 4
    return math.floor(365.25 * (y + 4716)) + math.floor(30.6001 * (m + 1)) + d + b - 1524.5


def _t(jd: float) -> float:
    return (jd - J2000) / 36525.0


def _norm(x: float) -> float:
    return x % 360.0


def sun_longitude(jd: float) -> float:
    """Apparent geocentric ecliptic longitude of the Sun, degrees, tropical (Meeus ch. 25)."""
    t = _t(jd)
    l0 = 280.46646 + 36000.76983 * t + 0.0003032 * t * t
    m = _rad(357.52911 + 35999.05029 * t - 0.0001537 * t * t)
    c = ((1.914602 - 0.004817 * t - 0.000014 * t * t) * math.sin(m) + (0.019993 - 0.000101 * t) * math.sin(2 * m) + 0.000289 * math.sin(3 * m))
    omega = _rad(125.04 - 1934.136 * t)
    return _norm(l0 + c - 0.00569 - 0.00478 * math.sin(omega))


def moon_longitude(jd: float) -> float:
    """Geocentric ecliptic longitude of the Moon, degrees, tropical, with nutation (Meeus ch. 47, longitude terms)."""
    t = _t(jd)
    lp = 218.3164477 + 481267.88123421 * t - 0.0015786 * t * t + t ** 3 / 538841.0
    d = 297.8501921 + 445267.1114034 * t - 0.0018819 * t * t + t ** 3 / 545868.0
    m = 357.5291092 + 35999.0502909 * t - 0.0001536 * t * t
    mp = 134.9633964 + 477198.8675055 * t + 0.0087414 * t * t + t ** 3 / 69699.0
    f = 93.2720950 + 483202.0175233 * t - 0.0036539 * t * t
    e = 1.0 - 0.002516 * t - 0.0000074 * t * t
    a1, a2 = _rad(119.75 + 131.849 * t), _rad(53.09 + 479264.290 * t)
    total = 0.0
    for td, tm, tmp, tf, coef in _MOON_TERMS:
        arg = _rad(td * d + tm * m + tmp * mp + tf * f)
        total += coef * (e ** abs(tm)) * math.sin(arg)
    total += 3958 * math.sin(a1) + 1962 * math.sin(_rad(lp - f)) + 318 * math.sin(a2)
    omega = _rad(125.04452 - 1934.136261 * t)
    nutation = -0.00478 * math.sin(omega)   # the main term, degrees
    return _norm(lp + total / 1e6 + nutation)


def ayanamsa(jd: float) -> float:
    """Lahiri ayanamsa, degrees."""
    return AYANAMSA_J2000 + (jd - J2000) / 365.25 * AYANAMSA_RATE_DEG_PER_YEAR


def sidereal(tropical_longitude: float, jd: float) -> float:
    return _norm(tropical_longitude - ayanamsa(jd))


def mean_obliquity(jd: float) -> float:
    t = _t(jd)
    return 23.439291 - 0.0130042 * t - 1.64e-7 * t * t


def greenwich_sidereal_degrees(jd: float) -> float:
    t = _t(jd)
    return _norm(280.46061837 + 360.98564736629 * (jd - J2000) + 0.000387933 * t * t - t ** 3 / 38710000.0)


def ascendant(jd: float, latitude: float, longitude_east: float) -> float | None:
    """Tropical ecliptic longitude of the ascendant, degrees. None where the horizon formula is undefined (inside the polar circles)."""
    if abs(latitude) > 66.0:
        return None
    theta = _rad(greenwich_sidereal_degrees(jd) + longitude_east)
    eps = _rad(mean_obliquity(jd))
    phi = _rad(latitude)
    y = math.cos(theta)
    x = -(math.sin(theta) * math.cos(eps) + math.tan(phi) * math.sin(eps))
    return _norm(math.degrees(math.atan2(y, x)))


def local_to_utc(year: int, month: int, day: int, hour: int, minute: int, *, tz_name: str | None, fallback_offset_minutes: int) -> datetime:
    """A wall-clock time at the birth place as UTC. Uses the time-zone database when the machine has it, otherwise the place's standard offset."""
    naive = datetime(year, month, day, hour, minute)
    if tz_name:
        try:
            from zoneinfo import ZoneInfo
            return naive.replace(tzinfo=ZoneInfo(tz_name)).astimezone(timezone.utc)
        except Exception:  # noqa: BLE001 - no tz database here: the standard offset is used
            pass
    return (naive - timedelta(minutes=fallback_offset_minutes)).replace(tzinfo=timezone.utc)
