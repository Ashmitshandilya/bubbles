# BUBBLES

A cycle-aware, chat-first personal health companion. Bubbles listens, remembers and connects the dots over time.
It is **not** a diagnostic engine: urgent symptoms get fixed, deterministic safety guidance before any AI is involved.

## Run it (Windows)

Double-click `start_bubbles.bat`. It uses `backend\venv` if present, otherwise a Python that already has the
dependencies, otherwise it builds the venv once; starts the backend (auto-restarting) on <http://127.0.0.1:8000> and the
frontend on <http://localhost:3000>, waits until both answer, prints the database status and opens the browser.

Manual:

```powershell
cd backend;  python -m uvicorn main:app --host 127.0.0.1 --port 8000     # API  (docs at /docs)
cd frontend; npm ci; npm run dev                                         # app
```

Needs `backend/.env` (Supabase URL + service key, AI provider keys, policy flags; see `backend/.env.example`) and
`frontend/.env.local` (`NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`, `NEXT_PUBLIC_API_URL`).
Never commit these files.

## Whole-Health OS (Fitness, Cycle and the trackers)

Fitness (diet planner, workout planner, calorie / whole-meal calculator, strict Transformation mode), the Cycle section, and
richer Sleep, Water, Medications, Mind and Notifications are built on the same chat-first core. Chat can answer
"how many calories do I have left?" and logs meals ("2 rotis, dal and curd") with quantities.

* No Supabase schema change is needed: data is stored as owner-scoped JSON documents (`backend/doc_store.py`). A proper-tables proposal is in `docs/proposals/whole-health-os-schema.sql` (not applied).
* **Clinician review:** every calorie, pace, protein, exercise, cycle and medication rule lives in `backend/clinical_constants.py`. Give `docs/clinical/BUBBLES_CLINICAL_REVIEW_PACKET.html` (print it to PDF) to a doctor, a registered dietitian and a pharmacist. Until it is signed off, every plan shows a "pending clinician review" notice. After sign-off set `BUBBLES_CLINICALLY_REVIEWED=true` in `backend/.env`.
* Hard safety rules: calories never below the floor, loss never faster than the cap, strict mode refused for the exclusions in the packet, restriction language in chat gets a supportive reply and pauses the plan.
* Recommended once: run `docs/proposals/lock-bubbles-doc-rows.sql` in the Supabase SQL editor (after reading it) so browsers cannot write the feature documents directly. The server already ignores forged documents (they are signed), so this is defence in depth.
* Free by default: no paid API. Optional free adapters: Open Food Facts barcode lookup (`BUBBLES_ENABLE_OPENFOODFACTS`, default on), email via your own SMTP (off by default).

## Is it healthy?

`GET http://127.0.0.1:8000/health` reports `services.database`: `ok`, `permission_denied`, `unreachable` or `unknown`.
If it says `permission_denied` the app keeps working in a compatibility mode, but you should run
`supabase/migrations/20261006_coco_service_role_grants.sql` once in the Supabase SQL editor.

"Can't reach Bubbles" in the UI means the backend process is not running (the banner reconnects by itself once it is).

## Tests

```powershell
cd backend;  python -m pytest tests -q          # backend (safety engine, chat pipeline, trackers, contracts)
cd frontend; npx tsc --noEmit; npm run lint; npx vitest run; npm run build
```

## How Bubbles understands a message

`backend/health_semantics.py` reads negation, tense, questions, quotations and who a symptom belongs to;
`backend/safety_engine.py` decides `NO_REDFLAG` / `POTENTIAL_REDFLAG_NEEDS_CLARIFICATION` / `URGENT` / `EMERGENCY` from that
(RED is a hard gate with no model call); `backend/chat_pipeline.py` orchestrates a chat turn (history, corrections,
event reconciliation, daily-log parsing). The independent language corpus lives in `backend/tests/health_language_corpus.py`.

Brand: the approved character is `docs/brand/bubbles-identity-final.png`; the drawing lives in `frontend/app/landing/BubblesMark.tsx`.

## Hosting and partner sharing

* Deploy checklist (database rename first, env vars, DNS, smoke tests): `DEPLOY.md`. Public site: https://heybubbles.in.
* Partner sharing (`/partner`): you pick exactly which summaries one trusted person can see (cycle estimate with gentle tips for them, 7-night sleep average, a note from you). They can connect with their own Bubbles account using a one-time invite code (48 hours), or you can send a quick link that expires in 7/30/90 days. Either side can end it instantly, and nothing from chat, symptoms, medications, labs, reports or notes can ever be shared. Backend: `backend/partner_sharing.py`; no database change needed.
