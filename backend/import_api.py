"""CSV import for exports from Google Fit / Fitbit / Garmin / smart scales / spreadsheets (Apple Health users can export a CSV with a helper app).

POST /import/csv {kind: weight|sleep|hydration|activity, csv_text}. Headers are matched loosely (a date/time column and a value column,
with an optional unit in the header). Rows are validated, capped, de-duplicated against what is already saved, and written through the same
tracker domains the app uses, so insights see them. Nothing leaves the server.
"""
from __future__ import annotations

import csv
import io
import re
from datetime import datetime
from typing import Any, Callable

from fastapi import APIRouter, Header, HTTPException, Request
from starlette.concurrency import run_in_threadpool

import health_logs

MAX_CHARS = 1_000_000
MAX_ROWS = 2000
DATE_HEADERS = ("date", "day", "timestamp", "time", "start", "startdate", "start date", "start_date", "datetime", "recorded", "measured")
VALUE_HEADERS = {
    "weight": ("weight", "weight_kg", "weight (kg)", "weight (lb)", "weight (lbs)", "body mass", "bodymass", "mass", "value"),
    "sleep": ("sleep", "sleep duration", "duration", "hours", "sleep hours", "asleep", "minutes", "value"),
    "hydration": ("water", "hydration", "volume", "amount", "intake", "ml", "value"),
    "activity": ("duration", "minutes", "active minutes", "exercise minutes", "value"),
}
TYPE_HEADERS = ("type", "activity", "workout", "sport", "name")


def _norm(h: str) -> str:
    return re.sub(r"\s+", " ", h.strip().lower().lstrip("﻿"))


def _pick(headers: list[str], wanted: tuple[str, ...]) -> str | None:
    normed = {_norm(h): h for h in headers}
    for w in wanted:
        if w in normed:
            return normed[w]
    for w in wanted:
        for n, original in normed.items():
            if w in n:
                return original
    return None


def _date(raw: str) -> str | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y", "%Y/%m/%d", "%d/%m/%Y %H:%M"):
        try:
            return datetime.strptime(raw[:19] if "T" in raw or " " in raw else raw, fmt).date().isoformat()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return None


def _number(raw: str) -> float | None:
    m = re.search(r"-?\d+(?:[.,]\d+)?", (raw or "").replace(",", "."))
    if not m:
        return None
    try:
        v = float(m.group(0))
    except ValueError:
        return None
    return v if v == v and abs(v) < 1e7 else None


BAD_TABLE = "That file could not be read as a table. Check that it is a plain CSV."


def _rows(reader):
    """The rows of a DictReader. A malformed file (for example one enormous field) is a plain ValueError, never a server error."""
    try:
        yield from reader
    except csv.Error as error:
        raise ValueError(BAD_TABLE) from error


def parse_rows(kind: str, text: str) -> tuple[list[dict], list[str]]:
    """-> (form bodies for health_logs.save_domain, skipped-row reasons). Raises ValueError with a user-safe message."""
    if kind not in VALUE_HEADERS:
        raise ValueError("kind must be weight, sleep, hydration or activity")
    if not text or not text.strip():
        raise ValueError("The file is empty")
    if len(text) > MAX_CHARS:
        raise ValueError("That file is too large (1 MB limit)")
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    try:
        headers = reader.fieldnames or []
    except csv.Error as error:
        raise ValueError(BAD_TABLE) from error
    date_col, value_col = _pick(headers, DATE_HEADERS), _pick(headers, VALUE_HEADERS[kind])
    if not date_col or not value_col:
        raise ValueError(f"Could not find a date column and a {kind} column. Headers found: " + ", ".join(h.strip()[:30] for h in headers[:8]))
    type_col = _pick(headers, TYPE_HEADERS) if kind == "activity" else None
    vh = _norm(value_col)
    out: list[dict] = []
    skipped: list[str] = []
    for i, row in enumerate(_rows(reader), start=2):
        if len(out) >= MAX_ROWS:
            skipped.append(f"stopped after {MAX_ROWS} rows")
            break
        day, value = _date(str(row.get(date_col) or "")), _number(str(row.get(value_col) or ""))
        if not day or value is None or value <= 0:
            skipped.append(f"row {i}: needs a date and a positive number")
            continue
        if kind == "weight":
            lbs = value if ("lb" in vh or "pound" in vh) else value * health_logs.LBS_PER_KG
            if not 50 <= lbs <= 700:
                skipped.append(f"row {i}: weight out of range")
                continue
            out.append({"date": day + "T08:00:00Z", "weight": round(lbs, 1)})
        elif kind == "sleep":
            hours = value / 60 if ("min" in vh or value > 24) else value
            if not 0 < hours <= 24:
                skipped.append(f"row {i}: sleep out of range")
                continue
            out.append({"date": day, "duration": round(hours, 2)})
        elif kind == "hydration":
            ml = value * 1000 if re.search(r"\b(l|litre|liter|litres|liters)\b", vh) else value * 29.57 if "oz" in vh else value
            if not 1 <= ml <= 10000:
                skipped.append(f"row {i}: volume out of range")
                continue
            out.append({"date": day + "T12:00:00Z", "volume": round(ml)})
        else:
            minutes = value * 60 if "hour" in vh else value
            if not 1 <= minutes <= 1440:
                skipped.append(f"row {i}: duration out of range")
                continue
            out.append({"date": day + "T12:00:00Z", "type": (str(row.get(type_col) or "Workout").strip()[:60] or "Workout") if type_col else "Workout", "duration": round(minutes)})
    return out, skipped[:20]


def build_router(get_user: Callable[[str | None], Any], db: Any) -> APIRouter:
    router = APIRouter()
    slug = {"weight": "weight", "sleep": "sleep", "hydration": "hydration", "activity": "activity"}

    def run(uid: str, kind: str, text: str) -> dict:
        try:
            rows, skipped = parse_rows(kind, text)
        except ValueError as err:
            raise HTTPException(status_code=422, detail=str(err))
        domain = health_logs.DOMAINS[slug[kind]]
        existing = health_logs.list_domain(db, slug[kind], domain, uid, 730).get("entries", [])
        key = {"weight": lambda e: (str(e.get("date", ""))[:10], round(float(e.get("weight") or 0), 1)),
               "sleep": lambda e: (str(e.get("date", ""))[:10], round(float(e.get("duration") or 0), 2)),
               "hydration": lambda e: (str(e.get("date", ""))[:10], round(float(e.get("volume") or 0))),
               "activity": lambda e: (str(e.get("date", ""))[:10], round(float(e.get("duration") or 0)))}[kind]
        seen = {key(e) for e in existing}
        saved = duplicates = 0
        for body in rows:
            probe = {"date": body["date"], **{k: v for k, v in body.items() if k not in ("date", "type")}}
            k = key(probe)
            if k in seen:
                duplicates += 1
                continue
            health_logs.save_domain(db, slug[kind], domain, uid, body)
            seen.add(k)
            saved += 1
        return {"status": "success", "kind": kind, "imported": saved, "duplicates_skipped": duplicates, "rows_skipped": len(skipped), "skipped": skipped}

    @router.post("/import/csv", status_code=201)
    async def import_csv(request: Request, authorization: str | None = Header(default=None)):
        uid = str((await run_in_threadpool(get_user, authorization)).id)
        try:
            body = await request.json()
        except (ValueError, RecursionError):
            raise HTTPException(status_code=422, detail="Request body must be valid JSON")
        if not isinstance(body, dict) or not isinstance(body.get("csv_text"), str):
            raise HTTPException(status_code=422, detail="Send {kind, csv_text}")
        return await run_in_threadpool(run, uid, str(body.get("kind") or ""), body["csv_text"])

    return router
