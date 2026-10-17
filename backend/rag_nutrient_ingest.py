"""Load the nutrient / blood-test / hormone reading list (rag_nutrient_manifest.json) into the RAG store.

DRY RUN BY DEFAULT: prints the plan and writes nothing. Nothing is fetched unless asked.

    python rag_nutrient_ingest.py                          # plan only (no network, no database, no .env needed)
    python rag_nutrient_ingest.py --check-urls             # also fetch every page and report status and extracted size
    python rag_nutrient_ingest.py --apply                  # fetch and ingest (needs backend/.env with the service key)
    python rag_nutrient_ingest.py --apply --from-dir pages # use <dir>/<id>.txt where present (saved by hand), fetch the rest
    python rag_nutrient_ingest.py --apply --only ferritin,tsh

Safe to repeat: ingest_document() skips text it already stored (content hash). Every document passes rag_sources.validate_source(),
carries its topic tags (nutrient:<x>, link:<a>-<b>, policy:<key>, batch:nutrients-v1) and is global (no user data). To undo a batch,
delete the documents tagged batch:nutrients-v1 (chunks cascade). Afterwards run `python rag_links.py --apply` and
`python eval_retrieval.py` to tag by title and measure recall.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from rag_sources import get_enabled_sources, validate_source

MANIFEST = Path(__file__).with_name("rag_nutrient_manifest.json")
BATCH_TAG = "batch:nutrients-v1"
MIN_CHARS = 800          # a page that extracts to less than this is a block page or an error page, never ingested
CHUNK, OVERLAP = 1600, 180
UA = "Mozilla/5.0 (compatible; BubblesIngest/1.0; +https://heybubbles.in)"
_TAG = re.compile(r"^(nutrient|link|policy|batch):[a-z0-9_:\-]+$|^[a-z0-9_\-]+$")


def load_manifest(path: Path = MANIFEST) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate(manifest: dict[str, Any]) -> list[str]:
    """Problems with the manifest (empty list = fine). Pure: no network, no database."""
    import rag
    import rag_links
    problems: list[str] = []
    seen_ids: set[str] = set()
    seen_urls: set[str] = set()
    entries = manifest.get("entries") if isinstance(manifest, dict) else None
    if not isinstance(entries, list) or not entries:
        return ["manifest has no entries"]
    for e in entries:
        if not isinstance(e, dict):
            problems.append(f"entry is not an object: {str(e)[:40]!r}")
            continue
        eid = e.get("id") or "?"
        if eid in seen_ids:
            problems.append(f"{eid}: duplicate id")
        seen_ids.add(eid)
        if e.get("source_url") in seen_urls:
            problems.append(f"{eid}: duplicate url")
        seen_urls.add(e.get("source_url"))
        try:
            validate_source(e["source_name"], e["source_url"])
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            problems.append(f"{eid}: {exc}")
        for key in ("title", "document_type", "evidence_level", "fetch"):
            if not e.get(key):
                problems.append(f"{eid}: missing {key}")
        if e.get("fetch") not in ("auto", "manual"):
            problems.append(f"{eid}: fetch must be auto or manual")
        tags = e.get("topic_tags") if isinstance(e.get("topic_tags"), list) else []
        if not tags:
            problems.append(f"{eid}: topic_tags must be a non-empty list")
        if BATCH_TAG not in tags:
            problems.append(f"{eid}: missing {BATCH_TAG}")
        for t in tags:
            if not isinstance(t, str) or not _TAG.match(t):
                problems.append(f"{eid}: odd tag {t!r}")
                continue
            if t.startswith("link:") and t[5:] not in rag_links.LINK_DOCS:
                problems.append(f"{eid}: unknown link tag {t}")
            if t.startswith("policy:") and t[7:] not in rag.POLICY_NOTES:
                problems.append(f"{eid}: unknown policy {t}")
        if not any(t.startswith("nutrient:") for t in map(str, tags)):
            problems.append(f"{eid}: no nutrient: tag")
        if not any(str(e.get("title")).startswith(p) for p in sum(rag_links.LINK_DOCS.values(), [])) and any(str(t).startswith("link:") for t in tags):
            problems.append(f"{eid}: title does not start with any LINK_DOCS prefix, so rag_links.py --apply would not tag it by title")
    return problems


class _Text(HTMLParser):
    SKIP = {"script", "style", "noscript", "nav", "footer", "header", "aside", "form", "svg", "button", "iframe"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.main: list[str] = []
        self.skip = 0
        self.in_main = 0

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in self.SKIP:
            self.skip += 1
        if tag in ("main", "article"):
            self.in_main += 1
        if tag in ("p", "li", "h1", "h2", "h3", "h4", "br", "tr"):
            self._add("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP and self.skip:
            self.skip -= 1
        if tag in ("main", "article") and self.in_main:
            self.in_main -= 1

    def _add(self, text: str) -> None:
        if self.skip:
            return
        self.parts.append(text)
        if self.in_main:
            self.main.append(text)

    def handle_data(self, data: str) -> None:
        self._add(data)


def extract_text(html: str) -> str:
    """Readable text of a page: the <main>/<article> part when there is one, else the whole body, minus navigation."""
    p = _Text()
    p.feed(html)
    raw = "".join(p.main) if len("".join(p.main)) >= MIN_CHARS else "".join(p.parts)
    lines = [re.sub(r"[ \t\r\f\v]+", " ", ln).strip() for ln in raw.split("\n")]
    return "\n".join(ln for ln in lines if ln)


def fetch_text(url: str, timeout: int = 30) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,application/xhtml+xml"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - only manifest URLs that passed validate_source
        return extract_text(resp.read().decode("utf-8", errors="replace"))


def to_doc(e: dict[str, Any], text: str) -> dict[str, Any]:
    publisher = next((s.get("publisher") for s in get_enabled_sources() if s["source_name"] == e["source_name"]), None)
    return dict(title=e["title"][:300], content=text, source_name=e["source_name"], source_url=e["source_url"], publisher=publisher,
                evidence_level=e["evidence_level"], country=e.get("country"), population=None, publication_date=None,
                topic_tags=list(e["topic_tags"]), document_type=e["document_type"], chunk_size=CHUNK, overlap=OVERLAP)


def text_for(e: dict[str, Any], from_dir: Path | None) -> tuple[str | None, str]:
    """(text, where it came from) or (None, why not)."""
    if from_dir is not None and (from_dir / f"{e['id']}.txt").is_file():
        return (from_dir / f"{e['id']}.txt").read_text(encoding="utf-8"), "file"
    if e["fetch"] == "manual":
        return None, "manual: save the page text to <dir>/<id>.txt and pass --from-dir"
    try:
        return fetch_text(e["source_url"]), "web"
    except Exception as exc:  # noqa: BLE001 - one bad page must not stop the batch
        return None, f"fetch failed: {type(exc).__name__}: {str(exc)[:80]}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="really write to the database (default: dry run)")
    ap.add_argument("--check-urls", action="store_true", help="fetch each page and report status and size (dry run only)")
    ap.add_argument("--from-dir", type=Path, help="folder with <id>.txt files saved by hand")
    ap.add_argument("--only", default="", help="comma-separated ids")
    a = ap.parse_args(argv)

    manifest = load_manifest()
    problems = validate(manifest)
    if problems:
        print("MANIFEST PROBLEMS:")
        for p in problems:
            print("  -", p)
        return 2
    only = {x.strip() for x in a.only.split(",") if x.strip()}
    todo = [e for e in manifest["entries"] if not only or e["id"] in only]
    print(f"manifest {manifest['version']}: {len(todo)} documents, {sum(e['fetch'] == 'manual' for e in todo)} need a hand-saved page")
    for d in manifest.get("deferred", []):
        print(f"  deferred {d['id']}: {d['reason']}")
    fetch = a.apply or a.check_urls
    stats: dict[str, int] = {}
    ingest = None
    if a.apply:
        from rag import ingest_document as ingest  # late: needs backend/.env
    for e in todo:
        if not fetch:
            print(f"  {e['id']:<14} {e['fetch']:<6} {e['source_url']}")
            continue
        text, how = text_for(e, a.from_dir)
        if text is None:
            print(f"  SKIP {e['id']}: {how}")
            stats["skipped"] = stats.get("skipped", 0) + 1
            continue
        if len(text) < MIN_CHARS:
            print(f"  SKIP {e['id']}: only {len(text)} characters extracted (block page or empty), nothing ingested")
            stats["too_short"] = stats.get("too_short", 0) + 1
            continue
        if not a.apply:
            print(f"  OK   {e['id']:<14} {how:<4} {len(text):>6} chars")
            stats["ok"] = stats.get("ok", 0) + 1
            continue
        try:
            res = ingest(**to_doc(e, text))
            stats[res["status"]] = stats.get(res["status"], 0) + 1
            print(f"  {res['status']:<14} {e['id']}")
        except Exception as exc:  # noqa: BLE001 - report the id, never the content
            stats["error"] = stats.get("error", 0) + 1
            print(f"  ERROR {e['id']}: {type(exc).__name__}: {str(exc)[:120]}")
    print("DONE" if a.apply else "DRY RUN - nothing written. Re-run with --apply.", stats or "")
    if a.apply:
        print("Next: python rag_links.py --apply   then   python eval_retrieval.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
