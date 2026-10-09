"""CLI for trusted/admin ingestion of a local evidence document.

Example:
python rag_ingest.py --file ./sources/sleep.txt --title "Sleep guideline" \
  --source-name "Example Authority" --source-url "https://..." \
  --evidence-level guideline --country global --topics sleep,brain
"""
from __future__ import annotations

import argparse
from pathlib import Path

from rag import ingest_document
from rag_sources import validate_source

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--source-name", required=True)
    parser.add_argument("--source-url")
    parser.add_argument("--publisher")
    parser.add_argument("--evidence-level", default="unknown")
    parser.add_argument("--country")
    parser.add_argument("--population")
    parser.add_argument("--publication-date")
    parser.add_argument("--document-type", default="guideline")
    parser.add_argument("--topics", default="")
    parser.add_argument("--scope", choices=["global", "user"], default="global")
    parser.add_argument("--owner-user-id")
    args = parser.parse_args()
    validate_source(
        source_name=args.source_name,
        source_url=args.source_url,
    )

    text = Path(args.file).read_text(encoding="utf-8")
    result = ingest_document(
        title=args.title,
        content=text,
        source_name=args.source_name,
        source_url=args.source_url,
        publisher=args.publisher,
        evidence_level=args.evidence_level,
        country=args.country,
        population=args.population,
        publication_date=args.publication_date,
        topic_tags=[x.strip() for x in args.topics.split(",") if x.strip()],
        scope=args.scope,
        owner_user_id=args.owner_user_id,
        document_type=args.document_type,
    )
    print(result)


if __name__ == "__main__":
    try:
        main()
    except ValueError as exc:
        print(f"ERROR: {exc}")
        raise SystemExit(2)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}")
        raise SystemExit(2)
