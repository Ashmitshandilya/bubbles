"""Retrieval baseline against the LIVE RAG store (read-only; needs backend/.env). Not part of pytest.

    ./venv/Scripts/python.exe eval_retrieval.py            # prints recall@1/@5 and misses, writes the report JSON
    RAG_EXPAND=0 ./venv/Scripts/python.exe eval_retrieval.py   # A/B: same run without lay/Hinglish query expansion

Case file: tests/eval/retrieval_cases.jsonl. A hit = any of the top-k titles matches expect_title_regex.
Cases come from the public-facing question types, not from the engine's output. Re-run after every ingest/ranking change.
"""
import json
import re
import sys
import uuid
from pathlib import Path

import rag

K = 5
cases = [json.loads(l) for l in Path(__import__("os").environ.get("EVAL_CASES", "tests/eval/retrieval_cases.jsonl")).read_text(encoding="utf-8").splitlines() if l.strip()]
uid, rows, h1, hk = str(uuid.uuid4()), [], 0, 0
for c in cases:
    res = rag.hybrid_search(query=c["query"], user_id=uid, limit=K)
    titles = [r["title"] for r in res]
    hit = [bool(re.search(c["expect_title_regex"], t, re.I)) for t in titles]
    h1 += bool(hit and hit[0]); hk += any(hit)
    rows.append(dict(id=c["id"], query=c["query"], hit_at_1=bool(hit and hit[0]), hit_at_k=any(hit), top_titles=titles))
summary = dict(k=K, n=len(cases), recall_at_1=round(h1 / len(cases), 2), recall_at_k=round(hk / len(cases), 2))
print(summary)
for r in rows:
    if not r["hit_at_k"]:
        print("MISS", r["id"], r["query"], "->", r["top_titles"][:3])
Path(sys.argv[1] if len(sys.argv) > 1 else "retrieval_baseline.json").write_text(json.dumps(dict(summary=summary, cases=rows), indent=1, ensure_ascii=False), encoding="utf-8")
