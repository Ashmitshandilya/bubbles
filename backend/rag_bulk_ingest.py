"""Bulk-load the BUBBLES knowledge export (BUBBLES_RAG_DOCUMENTS.jsonl) into the RAG store via ingest_document().

DRY RUN BY DEFAULT: prints what would load and why the rest is skipped. Nothing is written without --apply.

    python rag_bulk_ingest.py                      # dry run (no database, no .env needed)
    python rag_bulk_ingest.py --apply --limit 50   # small test load: use a TEST Supabase project first
    python rag_bulk_ingest.py --apply --batch v1.1b

Re-running is safe: ingest_document() skips text it already stored (content hash) before embedding.
Every document is tagged batch:<name>, rec:<id>, safety:<level>, policy:<response_policy>, review:<status>, sheet:<sheet>
so the backend can look the policy up by document id and a bad batch can be deleted (chunks cascade).
Only global, trusted-backend writes. No user data. Sources must pass rag_sources.validate_source().
"""
from __future__ import annotations

import argparse
import collections
import datetime
import json
import math
import os
import re
import time
from urllib.parse import urlparse

from rag_sources import get_enabled_sources, validate_source

DEFAULT_JSONL = "knowledge/BUBBLES_RAG_DOCUMENTS.jsonl"  # kept outside git (22 MB); pass --jsonl to use another path
EDITORIAL = "Bubbles editorial (authored, unreviewed)"
COUNTRY = {"UK": "UK", "USA": "US", "India": "IN", "Global": "GLOBAL"}
REVIEW_RE = re.compile(r"Next review due: (\d{1,2} \w+ \d{4})")
CHUNK = 1600  # gte-small handles ~2,000 characters; keeps most records in one chunk


def source_for(url: str | None) -> str | None:
    """Name of the enabled source whose domain matches the URL (URL-less records are editorial)."""
    if not url:
        return EDITORIAL
    host = urlparse(url).hostname or ""
    for s in get_enabled_sources():
        base = urlparse(s["base_url"]).hostname or ""
        if host == base or host.endswith("." + base):
            return s["source_name"]
    return None


def nhs_overdue(r: dict) -> bool:
    m = REVIEW_RE.search(r["text_for_embedding"])
    if not m or "nhs.uk" not in (r.get("source_url") or ""):
        return False
    try:
        return datetime.datetime.strptime(m.group(1), "%d %B %Y").date() < datetime.date.today()
    except ValueError:
        return False


def skip_reason(r: dict, a: argparse.Namespace) -> str | None:
    if r["source_sheet"] == "33_LAY_TERMS":
        return "lay-term sheet (use for query expansion in code, not as answer text)"
    if r["response_policy"].startswith("BYPASS_LLM") and not a.include_l7:
        return "L7 emergency record (stays out of LLM context)"
    if r["review_status"] == "source_known_not_refetched" and not a.include_unverified:
        return "source not re-read (review_status=source_known_not_refetched)"
    if nhs_overdue(r) and not a.include_overdue_nhs:
        return "NHS page past its own review date"
    return None


def to_doc(r: dict, name: str, batch: str) -> dict:
    tags = [t.strip().lower()[:40] for t in (r.get("tags") or "").split(";") if t.strip()][:10]
    tags += [f"rec:{r['record_id']}", f"safety:{r['safety_level']}", f"policy:{r['response_policy']}",
             f"review:{r['review_status']}", f"sheet:{r['source_sheet']}", f"batch:{batch}"]
    pub = r.get("publication_date") or ""
    ev = (r.get("evidence_level") or "").lower()
    publisher = next((s.get("publisher") for s in get_enabled_sources() if s["source_name"] == name), None)
    return dict(
        title=r["title"][:300], content=r["text_for_embedding"], source_name=name,
        source_url=r.get("source_url") or None, publisher=publisher,
        evidence_level=ev if ev not in ("", "n/a") else "unknown",
        country=COUNTRY.get(r.get("jurisdiction") or ""), population=None,
        publication_date=pub if re.fullmatch(r"\d{4}-\d{2}-\d{2}", pub) else None,
        topic_tags=tags, document_type=r.get("knowledge_type") or "guideline", chunk_size=CHUNK, overlap=180,
    )


def plan(records: list[dict], a: argparse.Namespace):
    todo, skipped = [], collections.Counter()
    for r in records:
        why = skip_reason(r, a)
        name = None
        if not why:
            name = source_for(r.get("source_url"))
            if name is None:
                why = "source domain not approved: " + (urlparse(r["source_url"]).hostname or "?")
            else:
                try:
                    validate_source(name, r.get("source_url") or None)
                except ValueError as e:
                    why = str(e)[:90]
        if why:
            skipped[why] += 1
        else:
            todo.append((r, name))
    return todo, skipped


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--jsonl", default=DEFAULT_JSONL)
    p.add_argument("--apply", action="store_true", help="really write to the database (default: dry run)")
    p.add_argument("--limit", type=int, default=0, help="load only the first N eligible records")
    p.add_argument("--batch", default="v1.1b")
    p.add_argument("--include-unverified", action="store_true")
    p.add_argument("--include-overdue-nhs", action="store_true")
    p.add_argument("--include-l7", action="store_true")
    p.add_argument("--sleep", type=float, default=0.05, help="seconds between documents")
    a = p.parse_args()

    if not os.path.exists(a.jsonl):
        raise SystemExit(f"Knowledge file not found: {a.jsonl}. Pass --jsonl <path to the exported documents file>.")
    with open(a.jsonl, encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]
    todo, skipped = plan(records, a)
    if a.limit:
        todo = todo[: a.limit]

    by_sheet = collections.Counter(r["source_sheet"] for r, _ in todo)
    chunks = sum(max(1, math.ceil(len(r["text_for_embedding"]) / (CHUNK - 180))) for r, _ in todo)
    print(f"records in file: {len(records)} | eligible: {len(todo)} | skipped: {sum(skipped.values())} | est. chunks/embeddings: ~{chunks}")
    print("eligible by sheet:", dict(by_sheet))
    for why, n in skipped.most_common():
        print(f"  skipped {n:5d}  {why}")
    if not a.apply:
        print("DRY RUN - nothing written. Re-run with --apply (test project first).")
        return

    from rag import ingest_document  # imported late: needs backend/.env (service key)
    print("target Supabase:", urlparse(os.getenv("SUPABASE_URL", "")).hostname)
    stats = collections.Counter()
    for i, (r, name) in enumerate(todo, 1):
        try:
            res = ingest_document(**to_doc(r, name, a.batch))
            stats[res["status"]] += 1
            if res["status"] == "ingested" and res["embedded_chunks"] < res["chunks"]:
                stats["chunks_without_embedding"] += 1
        except Exception as e:  # keep going; report the id, never the content
            stats["error"] += 1
            print(f"ERROR {r['record_id']}: {type(e).__name__}: {str(e)[:120]}")
        if i % 100 == 0:
            print(f"{i}/{len(todo)} {dict(stats)}")
        time.sleep(a.sleep)
    print("DONE", dict(stats))


if __name__ == "__main__":
    main()
