# DECISIONS.md — Bubbles decision log

Read this first. It records what we changed, what we added, why, and the rules we decided to keep, so any session
(human or Claude) can pick up without re-deriving context. **Update it in the same PR as the change.**
Newest entries first. Keep each entry short: *what*, *why*, *use case*, *where*.

Entry template:

```
### YYYY-MM-DD · Title (PR #n)
- What:  the change, one or two lines
- Why:   the reason or the owner's request
- Use:   what it is for / who benefits
- Where: files or folders
- Notes: trade-offs, rejected options, follow-ups
```

---

## 1. Standing rules (do not break without the owner saying so)

| Rule | Why |
|---|---|
| Bubbles (this repo, `main` → heybubbles.in) is the main product. `D:\COCO\coco` and the old GitHub COCO repo are an archive: no commits, no pushes. | One source of truth. |
| Work on a branch, pass the gates, open a PR, then merge. Never push to `main` directly. | `main` deploys the live site. |
| Gates before any merge: backend `pytest`, frontend `tsc --noEmit`, `eslint`, `vitest`, `next build`. CI runs backend + frontend + Vercel preview. | Catch regressions early. |
| Bubbles is not a diagnostic engine. Copy keeps uncertainty ("how sure", "missing data") and never claims diagnosis or treatment. | Safety and honesty. |
| RED/AMBER/GREEN safety triage runs before any AI. RED never sends the message to a model. | Urgent symptoms get fixed, reliable guidance. |
| $0 AI by default: `ALLOW_PAID_AI`, `ALLOW_KEYLESS_AI`, `ALLOW_KEYLESS_HEALTH_DATA` stay `false`. | Privacy and cost. |
| No analytics, no ad or tracking cookies. The privacy notice promises it. Do **not** merge the Vercel Web Analytics branch (`vercel/install-vercel-web-analytics-cayiic`). | Promise to users. |
| No Supabase schema or RLS weakening without an explicit decision. New tables enable RLS, owner-scoped reads, backend-only writes. | Health data isolation. |
| No secrets, `.env` files, real health records, screenshots of private data in git. | Security. |
| Do not use the other Claude session's folder `D:\COCO\bubbles`. Isolated clone `D:\COCO\bubbles-organ` is used for this session's work. | Avoids clobbering parallel work. |
| Merges are the owner's call: Claude opens the PR and reports green checks; Claude merges only when the owner says so in chat. | Auto-mode blocked an unreviewed merge once; the owner now merges or says "merge it". |

## 2. Design system snapshot (current, live)

- **Palette (pink "bright & cute"):** pink `#FF5FA2`, deep pink `#D6246F` (buttons, 4.9:1 on white), ink `#2B1A3F`, blush `#FFF6FA`, grape `#6A45F5`, sun `#FFC83D`, mint `#22C39A`, sky `#1F7FD6`, peach `#FF9F6B`, urgent `#C42B3B`.
- **Fonts:** Fraunces (headlines, big numbers), Figtree (UI and body), JetBrains Mono (tiny data labels), Bricolage Grotesque 650 (filled buttons, landing display). Tokens live in `frontend/app/tokens.css`; font loading in `frontend/app/layout.tsx`.
- **Shape and depth:** pill buttons, 20–24px card radius, pink-tinted shadows (never grey), soft inset highlight on filled buttons (`--press-highlight`).
- **Landing:** scroll-driven story in 10 chapters (`frontend/app/landing/story/store.ts`): enter, body, noise, track, cycle, connect, remember, companion, care, start. Sky is a WebGL canvas, bubbles are CSS/WebGL, motion respects reduced-motion.

---

## 3. Decision log

### 2026-10-16 · Chat fixes: friend voice, saved decisions stay saved, latest chat, mascot loader (this PR)
- What: (1) Replies use one style block: short, soft, a friend, no authority names ("NHS says") in prose, never a heavy verdict; a deterministic guard strips a leading "NHS guidance says" and lints authority names and heavy verdicts; an URGENT reply always ends with "speak to a clinician or an urgent-care service today"; source links sit behind a closed "Read more" and show titles only; WHO wording removed from fitness notes. (2) Confirm/save: the decision is overlaid on reloaded messages (cards no longer ask again), `POST /health-events/confirmation` saves many in one request, a projection failure no longer turns a saved decision into an error (it reports `queued`), the card flips at once and rolls back only the ids that failed. (3) Talk opens on the latest conversation (`GET /chat/latest`, `before` cursor and `has_more` on messages), History and New chat are labelled buttons, `?new=1` starts blank, a handoff question lands in the latest chat. (4) The "Checking your history and trusted sources" line and the "Checking memory" header line are gone: the mascot is the loader. (5) Gemini replies use minimal thinking, a 900-token cap and a 12 s timeout (fallbacks 20 s), `persist_events` skips its read when there is nothing to save. (6) New migration `20261016_bubbles_indexes_v2.sql` (indexes for document, chat and memory reads; two exact duplicates dropped).
- Why: the owner asked for no scary authority names, a cute loader, faster replies, opening the last chat, and fixed saving ("press twice", resets when reopened).
- Root causes found: the decision was written to `extracted_health_events` but never overlaid on the stored message snapshot (always "pending"); a projection error after the status commit returned HTTP 500, so the UI rolled back although the row was saved.
- Where: `backend/response_formatter.py`, `response_quality.py`, `bubbles_ai.py`, `rag.py`, `chat_pipeline.py` (`overlay_event_status`), `main.py` (`_confirm_event`, batch route, `/chat/latest`), `frontend/app/companion/*` (`event-decisions.ts`), `supabase/migrations/20261016_bubbles_indexes_v2.sql`.
- Notes: not done in this pass (brief kept in the session): granular consent ledger, onboarding rewrite (gender first), Mind section, insight detail sheet, deficiency intelligence, Android push, admin Live/Overall pages, community, dead-code removal, load test, SSE streaming. The migration is applied by the owner in the Supabase SQL editor.

### 2026-10-15 · Eyes in the 3D body, and a quieter app (this PR)
- What: (1) two eyes are now part of the live body model (globe, cornea, painted iris and pupil, optic nerves to the chiasm), selectable like any organ, with an **Eyes** area on the body map read from Track > Eyes and chat words. (2) A minimal pass over Today, Settings, Me, My health, Patterns, Care, Sleep and the body map: one clear thing first, everything else one tap away in a closed row, almost no explanatory paragraphs. (3) On a phone the body stays pinned under the header while the list scrolls, so a tap on a part is always seen.
- Why: the owner asked for the eye part inside the model and for a calmer, friendlier, minimal app ("too many paras all over the website").
- Use: Today opens on the greeting, one next step, quick logs and this week; Patterns, Your week, Coming up, Whole health and the rest sit in rows that open on tap. Settings opens on Account; Reminders, Privacy and data and This device are closed rows. Long tracker histories show the latest seven with "Show all".
- Where: `scripts/anatomy/eyes.mjs` + `add_eyes.mjs` (run after `build_body_model.mjs`; idempotent), `frontend/public/models/body.glb`, `components/anatomy/BodyViewer.tsx` (painted parts, own pivot), `app/lib/organ-map.ts`, `BodyFallback2D.tsx`; backend `organ_map_engine.py` (`_eyes`), `clinical_constants.py` (`ORGAN_EYE_*`); UI: `app/dashboard/dashboard/*`, `app/settings/SettingsClient.tsx`, `app/profile/ProfileClient.tsx`, `app/health/*`, `app/care/CareClient.tsx`, `app/insights`, `app/sleep`, `components/tracking/kit.tsx` (`Fold`, history cap), `components/anatomy/OrganPanel.tsx`.
- Notes: the eyes are illustrative (BodyParts3D has none); credits in `scripts/anatomy/CREDITS.md` and the body page's "Model credits". The eye rule: screen time averaging 6 h or more on 3+ logged days, or eye symptoms / low comfort on 3+ of the last 14 days = worth watching; sudden sight loss and severe eye pain still go through the safety engine (urgent); an eye-exam date is only a note, never evidence of healthy eyes (pending clinician review, section 13e of the clinical packet). Rule for new screens: one primary thing, detail behind a tap, no paragraph that restates the heading. The older body-systems list on My health is kept, closed, under "Body systems".

### 2026-10-15 · First-run setup, body-aware app, eyes and body-system words (this PR)
- What: after sign-in a new person answers a short, age- and body-aware question set (`/onboarding`), then sees "Creating your personal companion" while their setup is saved; the app then follows their answers. The body question is Female / Male / Transgender / Other / Prefer not to say. **Female:** cycle features, uterus and ovaries on the map, a female profile for the 3D model (the model's male groin patch is left out of its skin shell in the browser). **Male:** a male body map, no Cycle section, no period, pregnancy or cervical questions, no Cycle or Partner cards. **Other / prefer not to say:** the general model exactly as before. **Transgender:** no body map for that profile. Also: Track > Eyes, new symptom words for eyes, ears, mouth, urine and breasts (two of them urgent), and the companion's tone, reply length, language and topics to avoid.
- Why: the owner wanted the app set up from the person's answers and clearly different by body, with nothing shown that does not apply (a male body had been shown period options and the model had shown a female uterus next to male anatomy).
- Use: a person's Today, menu, body map, Care checklist, fitness formulas and chat style all follow their setup. Edit any time from Me > Your setup.
- Where: backend `onboarding.py` (bank, rules, experience profile, style block, pure) and `onboarding_api.py` (routes, stores), `organ_map_engine.py` (`reproductive`), `health_logs.py` (eyes), `health_semantics.py`; frontend `app/onboarding/*`, `app/lib/experience.ts`, the gate in `components/Providers.tsx` (`ExperienceProvider`), `components/Navigation.tsx`, `components/anatomy/BodyViewer.tsx` + `groin.ts` + `motion.ts`, `app/body/BodyClient.tsx`, Today cards. Plan and research: `docs/autonomy/ONBOARDING_AND_BODY_MAP_PLAN.md`. Clinical rules: `docs/clinical` section 13c to 13d.
- Notes: 18 and over only (the Terms say so; India's DPDP Act needs verifiable parental consent for minors, which Bubbles cannot do): a younger person's answers are never stored. No schema change: answers are signed documents (`onboarding` / `v1`, `experience` / `main`) and the existing stores. Free text goes through the safety engine first and crisis wording is never stored. No AI model is used by setup; only style lines (never health answers) reach the model. The browser's rules are checked against the server's own cases (`bank.fixture.json`; regenerate with `UPDATE_FIXTURE=1 pytest tests/test_onboarding.py -k fixture`). **Not done:** eyes on the live 3D model (it has no eye parts; Eyes works as a tracker and in the older body-systems list), a true female anatomy model (the female profile is the same model with the male groin patch removed and the illustrative uterus and ovaries), and the 20-20-20 reminder (needs background push). The first attempt at a body map here was a basic procedural body built on a stale checkout; it was dropped in favour of the live realistic model.

### 2026-10-15 · Figma pass: chapter eyebrows and scroll cue (this PR)
- What: every landing headline (except the two swapping ones) gets a small mono line above it, e.g. `01 / 10 · CYCLE-AWARE. ALWAYS HUMAN.`; the hero gets a "Scroll to continue ↓" cue that drifts 5px over 2.5s (ease-in-out).
- Why: the owner designed a landing in Figma (`Untitled.fig`) and asked to bring over only the parts that are useful. We decoded the file: it contained the six-chapter copy, mono eyebrow labels, honest "illustrative" captions, and ambient keyframes (ease-in-out cubic, 0→5→0 over ~2.5s). The 105 bitmaps inside were Figma's stock Apple-icon kit and were ignored.
- Use: gives the story an editorial "chapter x of y" rhythm and tells visitors the page scrolls, without changing the existing scroll engine.
- Where: `frontend/app/landing/eyebrow.ts` (+ test), `Landing.tsx` (`data-eyebrow` on headings, `.cw-scroll-cue`), `landing.css` (bottom block).
- Notes: eyebrow is CSS generated content with empty alt text (`content: attr(data-eyebrow) / ""`) so headings keep clean accessible names. Hidden on `.cw-swap` headings (body, noise) because it sat under the swapping text. Taken from Figma: copy lines, cue motion. **Not** taken: its layouts (they drop the body/noise/companion chapters we already have), stock imagery, Roboto/SF Pro UI-kit styles.

### 2026-10-15 · Filled app buttons use the landing button look (PR #23)
- What: in-app filled buttons (`.bubbles-glow`, `.bg-bubbles-pink-ink`) use Bricolage Grotesque 650 and a stronger inset highlight.
- Why: owner: "keep a little button and font theme of the landing page inside".
- Use: the app and the landing feel like one product; only buttons changed, headings and body keep Fraunces/Figtree.
- Where: `layout.tsx` (font), `tokens.css` (`--press-highlight`), `globals.css` (bottom rule).
- Notes: the first attempt was cut from a stale local `main` and conflicted with PR #22 (it would have reintroduced violet tokens). Rebuilt on fresh `origin/main`. Lesson: always `git fetch` before branching.

### 2026-10-15 · Revert landing and in-app theme to pink, keep new fonts (PR #22)
- What: restored the previous pink landing (`frontend/app/landing/**`, `NativeWelcome.tsx`) and the pink in-app palette; kept Fraunces / Figtree / JetBrains Mono; kept the organ tracker and restyled screens' structure. Removed `pearl-contrast.test.ts` (it tested the violet palette).
- Why: owner after seeing the "Pearl Lab" redesign live: change the landing back, fonts are good, inside theme back to pink, everything else looks good.
- Use: brand continuity (pink unicorn identity) and a faster first load (home page cold load was ~9.8s on the heavy Pearl Lab landing; ~0.3s after revert, measured with curl).
- Where: `frontend/app/tokens.css`, `globals.css`, `manifest.ts`, `layout.tsx` (theme colour `#FFF6FA`), landing folder.
- Notes: Pearl Lab (pearl `#FBF8F6`, plum `#1E1B2E`, violet `#6B46D6`, lilac `#C9B6F2`, gold `#E9C98B`) is kept only as a reference checkout (commit `b48b7cd`, folder `D:\COCO\bubbles-pearl-landing`).

### 2026-10 · 3D organ tracker (merged via release PR #21)
- What: `/body` page with a premium 3D anatomy viewer and an organ intelligence engine (per-organ context from the user's own logs).
- Why: owner wanted a living body map that connects tracked signals to organs.
- Use: users explore organs and see what their logged data does and does not say about them.
- Where: `frontend/app/body/`, `frontend/components/Anatomy3D.tsx`, `public/models/`, `docs/organ-tracker/`, `HANDOFF-ORGAN.md`.
- Notes: model from BodyParts3D (CC BY-SA 2.1 JP) and Z-Anatomy (CC BY-SA 4.0), compressed with meshopt/quantization. **Open:** the `/body` credit links both sources; confirm it also states the CC BY-SA 4.0 / 2.1 JP licences.

### 2026-10 · Whole-Health OS (Fitness, Cycle, wellness)
- What: fitness (diet, exercise, calories, strict Transformation mode), cycle section, sleep, hydration, medications, mind check-ins, notifications, chat integration, clinician review packet, schema proposal kept as separate files.
- Why: owner asked for a whole-health companion beyond chat.
- Use: daily tracking that feeds longitudinal insights; strict mode has hard safety exclusions.
- Where: backend modules `clinical_constants.py`, `plan_engine.py`, `transformation.py`, `doc_store.py`, routers `fitness_api.py`, `cycle_api.py`, `wellness_api.py`; docs under `docs/plans`, `docs/clinical`, `docs/proposals`.
- Notes: **clinical constants still need clinician sign-off** (pending banner stays until `BUBBLES_CLINICALLY_REVIEWED=true`). Schema is only proposed (`docs/proposals/whole-health-os-schema.sql`); data is stored as signed JSON documents in the existing events table.

### 2026-10 · Working method decisions
- Isolated clone for this session (`D:\COCO\bubbles-organ`) so two Claude sessions do not edit the same working tree.
- Heavy but simple chores (screenshots, uploading, dragging files into Figma) are handed to the owner with exact steps when they would cost many tokens; Claude does reasoning and code.
- Figma cannot produce real scroll effects. Plan: owner generates frames in Figma; Claude analyses them, keeps only what helps, and builds motion in code on the existing scroll engine (`ScrollDirector`, sky canvas, soap bubbles), polished with the Emil Kowalski / taste / impeccable skills when available.
- Figma kit: `D:\COCO\bubbles-figma-kit` (10 upload images, final prompt `upload-10/PROMPT-FINAL.txt`, decoded `.fig` notes in `fig/`).

---

## 4. Open items

- Confirm the `/body` credit states the Z-Anatomy (CC BY-SA 4.0) and BodyParts3D (CC BY-SA 2.1 JP) licences.
- Clinician sign-off for `clinical_constants.py` before removing the "pending review" banner.
- Decide which further Figma ideas to build (see the Figma entry: only copy lines and the cue motion are in so far).
- Owner to fix `~/.claude/settings.json` model aliases only when wanting the free router back (currently reset to defaults).
