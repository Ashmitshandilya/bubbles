"""Build data/lay_synonyms.json from the knowledge export's lay-terms sheet (source_sheet 33_LAY_TERMS, MedlinePlus "Also called" names).

    python build_lay_synonyms.py D:/COCO/COCO_RAG_FINAL/output/COCO_RAG_DOCUMENTS.jsonl

Keeps only clear one-to-one mappings (synonym -> the topic's usual name). Dropped: ambiguous names, very short ones, generic everyday
words, odd characters, very long topic names. Query-time use is in query_expand.py (added as OR alternatives, never as extra requirements).
"""
import collections
import json
import re
import sys

GENERIC = set(
    "cold pain ache aches fever test tests drug drugs pill pills condition problem problems disease diseases disorder disorders syndrome infection "
    "injury injuries care health growth fat sugar gas weight blood heart skin eye eyes ear ears nose mouth throat stomach back neck head hand hands "
    "foot feet leg legs arm arms bone bones muscle muscles joint joints air water food diet exercise sleep stress fear anger mood".split()
)
PATTERN = re.compile(r"^Also called: (?P<canon>.+?)\. '.+?' is also known as: (?P<syn>.+?)\. When a user uses", re.S)


def build(path: str) -> dict[str, str]:
    maps: dict[str, set[str]] = collections.defaultdict(set)
    with open(path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get("source_sheet") != "33_LAY_TERMS":
                continue
            m = PATTERN.match(r["text_for_embedding"])
            if not m:
                continue
            canon = m.group("canon").strip().lower()
            for s in m.group("syn").split(";"):
                s = " ".join(s.strip().lower().split())
                if s:
                    maps[s].add(canon)
    keep: dict[str, str] = {}
    for s, cs in maps.items():
        if len(cs) != 1:
            continue
        c = next(iter(cs))
        if s == c or (len(s) < 4 and not re.search(r"\d", s)) or s in GENERIC or len(c.split()) > 6 or re.search(r"[^a-z0-9 \-'/]", s):
            continue
        keep[s] = c
    return dict(sorted(keep.items()))


if __name__ == "__main__":
    out = build(sys.argv[1])
    with open("data/lay_synonyms.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=0, ensure_ascii=False)
    print(len(out), "synonyms written to data/lay_synonyms.json")
