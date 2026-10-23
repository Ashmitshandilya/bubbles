"""Stars lens astronomy: Meeus's own worked examples, within the tolerances the plan names, plus geometry checks for the ascendant."""
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import stars_astro as sa  # noqa: E402


def test_julian_day_matches_meeus_examples():
    assert sa.julian_day(datetime(2000, 1, 1, 12)) == pytest.approx(2451545.0)
    assert sa.julian_day(datetime(1987, 1, 27)) == pytest.approx(2446822.5)      # Meeus 7.a
    assert sa.julian_day(datetime(1992, 10, 13)) == pytest.approx(2448908.5)     # Meeus 25.a


def test_sun_longitude_meeus_25a():
    jd = sa.julian_day(datetime(1992, 10, 13))
    assert sa.sun_longitude(jd) == pytest.approx(199.9099, abs=0.01)


def test_moon_longitude_meeus_47a():
    # 1992 April 12, 0h TD: geometric longitude 133.162655, apparent (with nutation) 133.167265. The 0.01 tolerance holds either way.
    jd = sa.julian_day(datetime(1992, 4, 12))
    assert sa.moon_longitude(jd) == pytest.approx(133.162655, abs=0.01)


def test_ayanamsa_lahiri_is_about_24_degrees_today():
    jd = sa.julian_day(datetime(2026, 10, 24))
    assert 24.1 < sa.ayanamsa(jd) < 24.3
    assert sa.ayanamsa(sa.J2000) == pytest.approx(23.853)


def test_sidereal_sun_is_in_libra_in_mid_october():
    jd = sa.julian_day(datetime(2026, 10, 24, 6))
    assert 180 <= sa.sidereal(sa.sun_longitude(jd), jd) < 210   # Libra (Tula) in this month


def test_greenwich_sidereal_time_meeus_12a():
    jd = sa.julian_day(datetime(1987, 4, 10, 19, 21))
    assert sa.greenwich_sidereal_degrees(jd) == pytest.approx(128.7378734, abs=0.01)   # 8h 34m 57.0896s


def test_ascendant_geometry_at_the_equator():
    # at the equator the ascendant is 90 degrees ahead of the midheaven; with RAMC 0 the midheaven is 0 Aries
    # build a jd whose local sidereal time is 0: search a day for it
    jd0 = sa.julian_day(datetime(2026, 3, 20))
    best = min((abs(((sa.greenwich_sidereal_degrees(jd0 + k / 1440.0) + 180) % 360) - 180), k) for k in range(1440))
    jd = jd0 + best[1] / 1440.0
    assert sa.ascendant(jd, 0.0, 0.0) == pytest.approx(90.0, abs=0.5)


def test_ascendant_moves_through_the_zodiac_in_a_day():
    jd = sa.julian_day(datetime(2026, 10, 24))
    seen = [sa.ascendant(jd + h / 24.0, 28.6, 77.2) for h in range(0, 24, 2)]
    steps = [(b - a) % 360 for a, b in zip(seen, seen[1:])]
    assert all(0 < s < 120 for s in steps) and 300 < sum(steps) + ((seen[0] - seen[-1]) % 360) < 420


def test_ascendant_is_undefined_in_the_polar_circle():
    assert sa.ascendant(sa.J2000, 70.0, 20.0) is None


def test_local_time_falls_back_to_the_standard_offset():
    out = sa.local_to_utc(1999, 3, 14, 6, 30, tz_name="No/Such_Zone", fallback_offset_minutes=330)
    assert out == datetime(1999, 3, 14, 1, 0, tzinfo=timezone.utc)
