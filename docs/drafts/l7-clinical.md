# D1 intelligence: problem statement and findings (lane L7)

## Problem
After onboarding, Bubbles had no way to relate logs, labs and symptoms to vitamin, mineral, blood-marker and hormone gaps. Labs were
only read by organ_map_engine (thyroid TSH rules). Chat context carried no lab or nutrient hint. The RAG corpus (rag_sources.json, 11
sources) had no vitamin/mineral/hormone lab-test pages, so questions like "what does a ferritin test show" relied on whatever was
already stored.

## Findings
- backend/rag.py hybrid_search + rag_links.py LINK_DOCS had links only for sleep/mood/activity/cycle/fatigue-labs; nothing for
  nutrient-energy, iron-hair, vitaminD-mood, b12-diet, thyroid-cycle, hormones-cycle (rag_links.py, before this lane).
- The live store was not reachable from the sandbox: topic-tag coverage was audited from rag_sources.json and the ingest scripts only.
  No recall numbers are claimed (recall@5 1.00 / recall@1 0.85 was the last measurement, before these changes).
- WIP defects found and fixed: lab_status accepted NaN/inf/negative/huge values and reversed or half ranges (deficiency_map.py
  lab_status); free-text lab names/units were interpolated into user text and the chat context (now `_plain`, else the map's own
  name); non-dict profile lists crashed signals_from_rows; the ingest validator accepted an empty manifest, non-dict rows and
  non-list tags and crashed on odd types; 11 manifest titles had no LINK_DOCS prefix so `rag_links.py --apply` would not tag them
  (prefixes added).
- Onboarding keys `diet_style` exists (onboarding.py); `recent_blood_test` is not in the bank yet. Both are read defensively
  (missing = a gap line, never a nudge).

## What changed
- deficiency_map.py: pure map (11 entries), nudges (low/medium, max 3), lab notes against the person's own range only.
- deficiency_api.py: GET /nutrients/nudges (auth, owner-scoped, under-18 empty, best-effort sources named in `unavailable`);
  chat_block(): one sentence, cached, never waits, needs consent `ai_chat_processing`; hooked in main.py `_context_stage`.
- rag_nutrient_ingest.py + rag_nutrient_manifest.json (31 documents, MedlinePlus/NIDDK/NICHD/ODS; ICMR-NIN RDA deferred: priced,
  copyrighted). Dry run by default. rag_sources.json: + NIH ODS, NICHD. rag_links.py: 6 new link ids.
- tests/eval/retrieval_cases.jsonl: +23 cases (D101-D123).

## Open (not verified, left out)
- Per-page licence check of MedlinePlus/ODS pages before --apply (some MedlinePlus pages carry third-party credits).
- Ingest and eval re-run need network + backend/.env: `python rag_nutrient_ingest.py --check-urls`, then `--apply --from-dir pages`
  (ods_* are fetch=manual), `python rag_links.py --apply`, `python eval_retrieval.py`.
- No unit-mismatch check: Bubbles keeps no range table, so a value is compared only to the range the person entered.
- Today/Patterns closed row (frontend) is not built; API shape is ready. Android: no native work.
- Clinical sign-off: rules, thresholds (30-day window, 2 days per sign, 90-day quiet lab, 365-day freshness, 2 heavy days) and
  sentence templates are in deficiency_map.py; fold into the clinical packet.
