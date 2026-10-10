# Bubbles autonomous plan (read this first in every session)

Owner: the founder (away from the laptop; has granted administrator-level access and asked for unattended, careful progress).
Repo: D:\COCO\bubbles (GitHub Ashmitshandilya/bubbles). Live: https://heybubbles.in (Vercel) and https://bubbles-dk3v.onrender.com (Render).
Work branch: `ui-intelligence-overhaul-2026-10-10`. `main` deploys automatically: merge to main ONLY when every gate below is green, then verify live.

## Operating rules (never break)
1. Safety first: no diagnosis or dosing, safety_engine.py and health_semantics.py behaviour unchanged, missing data is never "healthy".
2. Never print, log, copy or commit secrets. Never read backend/.env or frontend/.env.local except through code that loads them silently.
3. $0 AI default stays (no paid or keyless health-data routing). No Supabase schema changes, no RLS weakening.
4. No fabricated testimonials, user counts, press logos, reviews or medical claims. No em-dashes in visible copy.
5. Cautious with the live system: additive changes only to the live RAG store; never delete data; no force-push; no changes to DNS, billing, auth providers or env secrets.
6. Do not sign in or create accounts on the live site.
7. The 3D Bubbles figure is NOT built in code. The approved character is concept 2 (see Assets). Put real art on the page, not procedural 3D.
8. Pace: use usage evenly. About one focused chunk per scheduled wake-up, one or two agents at most (SIR NOAH reviews and accepts, LIXIE art-directs and plans). No giant bursts. If a limit message appears, stop and wait for the next wake-up.
9. Gates before merging to main: backend `pytest tests -q -p no:cacheprovider` (python: D:/COCO/coco/backend/venv/Scripts/python.exe, run from D:\COCO\bubbles\backend), frontend `npx tsc --noEmit`, `npm run lint`, `npx vitest run`, `npm run build`. Then push, wait for Vercel and Render, smoke test live (health GET and HEAD, landing 200, partner fake token page, CORS).

## Assets
- Approved character: concept 2 ("hero portrait"), Canva media id MAHXkCa2C0k. The original file must be downloaded by the founder from Canva; look in C:\Users\ACER\Downloads for the newest png/jpg and copy it to frontend/public/brand/bubbles-hero.jpg (optimise to about 1600px wide, quality 82). Until then a 149x199 placeholder is in that path: it looks soft, so replace it as soon as the real file appears.
- Other concepts: 1 (full body), 3 (seated), 4 (cute hybrid) in Canva (ids MAHXkFRRhgg, MAHXkBs8d_w, MAHXkHjZvCk).
- Character spec: docs/brand/BUBBLES_CHARACTER_SPEC_V2.md.
- Contact mailbox the founder chose: hey@heybubbles.in (add to footer and privacy pages ONLY after the founder confirms it exists).

## Task list (tick as done, newest status at the top of each item)
- [x] Landing v2 built (frontend/app/landing/v2). Verify visually desktop and mobile, fix issues, then switch off the old landing code (frontend/app/landing/story, world, Landing.tsx, landing.css; keep BubblesMark, BubblesHead, BubblesFigure because the app uses BubblesMark).
- [ ] Landing polish: real hero image swap, Lighthouse pass (LCP under 2.5s on mobile), accessibility pass (axe), reduced-motion check, dark-mode stance documented (app is light-only).
- [ ] Navigation: reduce about 29 entries to 7 primary entries with section tab bars; keep every URL working (redirects). Files: frontend/components/Navigation.tsx, components/hub/*.
- [ ] Dashboard and inner pages: remove the generic "AI-made" look. Specialist pass per area: dashboard, chat (companion), trackers, cycle, care, profile/settings. Realistic, calm, premium, consistent. Every button must do something visible; remove placeholders ("not available yet").
- [ ] Fitness: minimise (one Today screen, 3-step setup, advanced mode behind a disclosure; old routes redirect).
- [ ] Chat intelligence and replies: better system prompt and formatting, response-quality rubric tests (deterministic), source chips, quick replies, thumbs feedback, friendlier deterministic replies. Safety invariants unchanged.
- [ ] RAG: turn the 559-record lay-term sheet (D:/COCO/COCO_RAG_FINAL/output/COCO_RAG_DOCUMENTS.jsonl, source_sheet 33_LAY_TERMS) into validated expansions in backend/query_expand.py; collapse duplicate-page chunks in top results; add 40 harder eval cases; keep recall@5 at 1.00. Read-only against the live store except additive tags via rag_links.py.
- [ ] More features worth shipping (research, then build the best): daily check-in streak, doctor-visit summary export, gentle reminders, weekly "what changed" digest, Hinglish voice, medication adherence view, shareable partner summary. Keep each small, safe and tested.
- [ ] Privacy and terms pages (drafts marked "pending legal review"), footer links, contact address once confirmed.
- [ ] Keep docs current: README, DEPLOY.md, CLAUDE.md, docs/intelligence-engine/HANDOFF_BUBBLES.md.

## Review roles
- SIR NOAH (agent `sir-noah`, also called JEv): acceptance. Before any merge to main he checks scope, safety, preservation rules and the acceptance list. He does not write code.
- LIXIE (agent `lixie`): CTO and art director. Plans each chunk, owns the visual language (pearl blush, one pink accent, pill buttons, 28px containers, soft realistic imagery, motion only where it explains something).
- Pass `model: "sonnet"` when starting these two agents.

## Log (append one line per chunk: date time, what changed, gates result, commit)
- 2026-10-10 06:50 plan created; landing v2 files written, not yet verified.
