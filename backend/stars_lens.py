"""The Stars lens (renovation plan 8.3): a traditional lens, opt-in, for fun and reflection.

From a birth date, an optional birth time and a place from the bundled city list, this works out the sidereal Moon sign (rashi) and nakshatra,
the Sun sign, and, with a birth time, the ascendant, then lists the traditional temperament words for them. Each word is checked against
what Bubbles has actually seen about the person (the Person Model); "Matches what we've seen" is only ever said when the person's own
evidence agrees. A match or a mismatch never changes anything Bubbles does except which words it chooses. Controlled studies find that charts
do not predict personality, so nothing here predicts anything, and the lens is never used in safety, medical, Safe Harbor or relationship-decision
answers (the chat only reads it when the person brings up astrology).

Everything runs on the server from files in ``data/``: no geocoding service, nothing leaves the machine.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

import person_model as pm
import stars_astro as sa

DATA = Path(__file__).with_name("data")
RASHI = ["Mesha", "Vrishabha", "Mithuna", "Karka", "Simha", "Kanya", "Tula", "Vrishchika", "Dhanu", "Makara", "Kumbha", "Meena"]
NAKSHATRA = ["Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra", "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni",
             "Uttara Phalguni", "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha", "Jyeshtha", "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana",
             "Dhanishta", "Shatabhisha", "Purva Bhadrapada", "Uttara Bhadrapada", "Revati"]
NAK_SPAN = 360.0 / 27.0
CUSP_DEGREES = 0.5
KIND, KEY = "stars_lens", "main"
PRIOR_WEIGHT = 0.2
NOTE_SOURCE = "stars"
TRADITION_LINE = "A traditional lens, for fun and reflection. Bubbles learns who you are from you; the stars only help with the words."
MIN_YEAR, MAX_YEAR = 1900, 2100


# ---- places ------------------------------------------------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _cities() -> tuple[dict[str, Any], ...]:
    rows = json.loads((DATA / "cities.json").read_text(encoding="utf8"))
    out = []
    for i, r in enumerate(rows):
        out.append({**r, "id": f"{i:03d}-{re.sub(r'[^a-z]+', '-', (r['name'] + ' ' + r['country']).lower()).strip('-')}"})
    return tuple(out)


def city(city_id: str) -> dict[str, Any] | None:
    return next((c for c in _cities() if c["id"] == city_id), None)


def search_cities(query: str, limit: int = 8) -> list[dict[str, Any]]:
    q = re.sub(r"\s+", " ", str(query or "").strip().lower())[:40]
    if len(q) < 2:
        return []
    starts, within = [], []
    for c in _cities():
        name = c["name"].lower()
        (starts if name.startswith(q) else within if q in name or q in c["region"].lower() or q in c["country"].lower() else []).append(c)
    return [{"id": c["id"], "name": c["name"], "region": c["region"], "country": c["country"]} for c in (starts + within)[:limit]]


# ---- positions ---------------------------------------------------------------------------------------------------------------

def _place(sidereal_longitude: float) -> dict[str, Any]:
    lon = sidereal_longitude % 360.0
    sign, within = divmod(lon, 30.0)
    nak, nak_within = divmod(lon, NAK_SPAN)
    cusp = min(within, 30.0 - within, nak_within, NAK_SPAN - nak_within) < CUSP_DEGREES
    return {"rashi": RASHI[int(sign)], "degrees": round(within, 1), "nakshatra": NAKSHATRA[int(nak)], "pada": int(nak_within // (NAK_SPAN / 4)) + 1, "cusp": cusp}


def _spread(longitudes: list[float]) -> dict[str, Any]:
    """The moon or sun on a day with no birth time: every sign and nakshatra it could have been in."""
    places = [_place(x) for x in longitudes]
    rashis = list(dict.fromkeys(p["rashi"] for p in places))
    naks = list(dict.fromkeys(p["nakshatra"] for p in places))
    return {"rashi": rashis[0], "nakshatra": naks[0], "rashi_options": rashis, "nakshatra_options": naks, "pada": None, "degrees": None, "cusp": len(rashis) > 1 or len(naks) > 1}


def compute_chart(birth: date, birth_time: str | None, place: dict[str, Any]) -> dict[str, Any]:
    """{moon, sun, ascendant|None, time_known, place}. ``birth_time`` is "HH:MM" on the clock at the birth place, or None for unknown."""
    if not (MIN_YEAR <= birth.year <= MAX_YEAR):
        raise ValueError("year_out_of_range")
    tz, off = place.get("tz"), int(place.get("offset", 0))
    if birth_time:
        m = re.fullmatch(r"([01]?\d|2[0-3]):([0-5]\d)", birth_time.strip())
        if not m:
            raise ValueError("bad_time")
        utc = sa.local_to_utc(birth.year, birth.month, birth.day, int(m.group(1)), int(m.group(2)), tz_name=tz, fallback_offset_minutes=off)
        jd = sa.julian_day(utc)
        moon = _place(sa.sidereal(sa.moon_longitude(jd), jd))
        sun = _place(sa.sidereal(sa.sun_longitude(jd), jd))
        asc_tropical = sa.ascendant(jd, float(place["lat"]), float(place["lon"]))
        ascendant = _place(sa.sidereal(asc_tropical, jd)) if asc_tropical is not None else None
        return {"moon": moon, "sun": sun, "ascendant": ascendant, "time_known": True, "place": {"name": place["name"], "country": place["country"]}}
    moons, suns = [], []
    for hour in (0, 4, 8, 12, 16, 20, 24):
        day = birth + timedelta(days=1) if hour == 24 else birth
        utc = sa.local_to_utc(day.year, day.month, day.day, hour % 24, 0, tz_name=tz, fallback_offset_minutes=off)
        jd = sa.julian_day(utc)
        moons.append(sa.sidereal(sa.moon_longitude(jd), jd))
        suns.append(sa.sidereal(sa.sun_longitude(jd), jd))
    return {"moon": _spread(moons), "sun": _spread(suns), "ascendant": None, "time_known": False, "place": {"name": place["name"], "country": place["country"]}}


# ---- traditional words and matching ------------------------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _traits() -> dict[str, Any]:
    return json.loads((DATA / "stars_traits.json").read_text(encoding="utf8"))


def associations(chart: dict[str, Any]) -> list[dict[str, Any]]:
    """The traditional words for each placement. When the birth time is unknown and a placement could be two signs, both are listed and none is mapped."""
    data = _traits()
    out: list[dict[str, Any]] = []

    def add(label: str, rashi_names: list[str], nakshatra_names: list[str]) -> None:
        ambiguous = len(rashi_names) > 1 or len(nakshatra_names) > 1
        for rashi in rashi_names:
            for i, item in enumerate(data["rashi"][rashi]["items"]):
                out.append({"id": f"{label}:{rashi}:{i}", "source": f"{label} in {rashi} ({data['rashi'][rashi]['english']})", "text": item["text"],
                            "maps_to": None if ambiguous else item.get("maps_to"), "uncertain": ambiguous})
        for nak in nakshatra_names:
            for i, text in enumerate(data["nakshatra"][nak]):
                out.append({"id": f"{label}:{nak}:{i}", "source": f"{label} nakshatra {nak}", "text": text, "maps_to": None, "uncertain": ambiguous})

    moon, sun, asc = chart["moon"], chart["sun"], chart.get("ascendant")
    add("Moon", moon.get("rashi_options") or [moon["rashi"]], moon.get("nakshatra_options") or [moon["nakshatra"]])
    add("Sun", sun.get("rashi_options") or [sun["rashi"]], [])
    if asc:
        add("Ascendant", [asc["rashi"]], [])
    return out


def match_for(model: dict[str, Any], maps_to: dict[str, str] | None, now: datetime) -> str:
    """"matches", "differs" or "unknown": only evidence the person gave (not a prior) can say one or the other."""
    if not maps_to:
        return "unknown"
    reading = pm.resolve(maps_to["trait"], model["traits"].get(maps_to["trait"]), now)
    if not reading or not reading["used"]:
        return "unknown"
    return "matches" if maps_to["value"] in reading["values"] else "differs"


def view(chart: dict[str, Any], model: dict[str, Any], now: datetime) -> dict[str, Any]:
    items = []
    for a in associations(chart):
        status = match_for(model, a["maps_to"], now)
        items.append({"id": a["id"], "source": a["source"], "text": a["text"], "uncertain": a["uncertain"],
                      "match": {"matches": "Matches what we've seen", "differs": "Not what we've seen", "unknown": "Not enough to tell"}[status]})
    return {"intro": TRADITION_LINE, "chart": chart, "items": items}


def apply_priors(model: dict[str, Any], chart: dict[str, Any], now: datetime) -> int:
    """Replace the Stars priors in the Person Model with 0.2-weight ones for the associations that map to a trait value. By rule 6.2 a prior can
    never decide anything alone. Returns how many were added."""
    for tid in pm.TRAITS:
        pm.forget_source(model, tid, NOTE_SOURCE)
    added = 0
    for a in associations(chart):
        m = a["maps_to"]
        if m and not a["uncertain"] and pm.add_evidence(model, m["trait"], m["value"], NOTE_SOURCE, "stars", PRIOR_WEIGHT, now, prior=True):
            added += 1
    return added


def clear_priors(model: dict[str, Any]) -> None:
    for tid in pm.TRAITS:
        pm.forget_source(model, tid, NOTE_SOURCE)
