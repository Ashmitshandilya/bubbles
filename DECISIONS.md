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

### 2026-10-16 · Weight in kg or lbs (direct push to main, owner request)
- What: the weight tracker has an lbs / kg switch above the stats. The form, history and stats follow the chosen unit. The unit is remembered on this device only.
- Why: the owner asked to see and enter weight in kilograms as well as pounds.
- Use: people who think in kg can log and read weight in kg; nothing changes for people who keep pounds.
- Where: `frontend/app/lib/unit-switch.ts` (+ `.test.ts`), `frontend/components/GenericTrackingClient.tsx` (`altUnit` field option), `frontend/components/tracking/kit.tsx` (`SIGNALS` exported), `frontend/app/weight/page.tsx`.
- Notes: the API still stores and receives pounds, so no backend or schema change. Converting kg to lbs and back can shift a value by about 0.1 lb. Pushed straight to `main` at the owner's explicit request, which departs from the "work on a branch, open a PR" rule above; the change had passed the frontend gates on its feature branch first. No browser click-through was done.

### 2026-10-17 · Android 2.0: its own opening and app feel (this PR)
- What: app-only redesign, about half the website look kept (pink, fonts, Bubbles). New welcome with three swipeable intro cards and page dots (`app/IntroSlides.tsx`); app bar with a big title and frosted glass; floating frosted dock with an active pill and icon pop; lilac-to-blush backdrop, rounder cards, pink-to-grape primary buttons; screens rise into place and everything presses. First-run permission step: a full screen right after setup, once per phone, that shows a sample reminder and three reasons before Android's own prompt ("Turn on reminders" is the consent; crash reports are a separate box, off by default; "Maybe later" or Back never asks again here). New premium app icon: the same mascot on a grape-to-pink gradient with a glow, soap bubbles and a soft shadow (`scripts/android-assets.mjs`; the website keeps `app/icon.svg`). Version 2.0.0 (5).
- Why: the owner wants the app to feel like an app, not the website, while keeping the same accounts and setup.
- Use: same account, same server-driven setup questions and same data as the website (one Supabase project, one API).
- Where: `frontend/app/globals.css` (html[data-native], "Android 2.0"), `app/IntroSlides.tsx`, `app/NativeWelcome.tsx`, `components/Navigation.tsx` (data-dock, data-tab, data-app-bar hooks), `components/PhoneReminderPrompt.tsx`, `lib/firebase-native.ts`, `components/Providers.tsx`.
- Premium pass (same PR): Today opens with a body-map hero tile and a feature grid that follows the person's setup (`components/AppHome.tsx`, `app/lib/app-home.ts`, tested); the dock is personal (Today, Body or Cycle or Mind, Talk, Track, More); glass cards, a segmented sub-tab control, sheets that slide up, shimmering placeholders.
- Notes: everything is scoped to the app build; the website is unchanged. All motion is off under reduced motion. Needs an APK build on the owner's PC (`npm run android:release`).

### 2026-10-16 · Firebase for the Android app: phone reminders, crash reports, tester builds (this PR)
- What: (1) Phone reminders through Firebase Cloud Messaging: Settings → Reminders → "On this phone" (app only), device tokens as signed `push_device` documents, a background sweep that creates due reminders while the app is closed, "Send a test to this phone". The "Reminders on your phone" consent is now offered (wording version `2026-10b`). (2) Crashlytics crash reports, opt-in per phone (Settings → This device). (3) `npm run android:release -- --distribute` sends the APK to Firebase App Distribution testers. Privacy notice updated.
- Why: the owner asked to add Firebase; the Android push gap was listed as not done in the chat-fixes entry below.
- Use: people get water, medicine check-in and wind-down reminders on a closed phone; the owner sees native crashes and can test builds with testers first.
- Where: `backend/push_fcm.py`, `notifications.py`, `wellness_api.py` (`POST /notifications/devices`, `/notifications/devices/remove`, `/notifications/push/test`), `consent_ledger.py`, `main.py` (startup); `frontend/lib/firebase-native.ts`, `app/lib/phone-reminders.ts`, `components/wellness/NotificationSettingsCard.tsx`, `components/settings/CrashReportsRow.tsx`, `components/Providers.tsx`; `frontend/android/**` (`BubblesFirebasePlugin.java`, manifest, Gradle); `scripts/build-android.mjs`; `docs/FIREBASE.md`.
- Notes: dormant until the owner adds `android/app/google-services.json` (gitignored) and `FIREBASE_SERVICE_ACCOUNT_JSON` on Render; see `docs/FIREBASE.md`. Sending needs both the switch and a consent-log yes; text is only the fixed templates; one owner per phone (registering takes it from other accounts, sign-out deletes the token). No Google Analytics (manifest switches it off; never add `firebase-analytics`). No schema change and no new Python dependency (`google-auth` + `httpx` were already pinned). Rejected: App Check (needs Google Play distribution; adds reCAPTCHA to the site), SQL Connect / App Hosting / Firebase Auth (would replace working Supabase and Vercel), forwarding JavaScript errors to Crashlytics (could carry typed text). Reminders made by the background sweep are not emailed. The Android build could not be run in the cloud session (Google's Maven was unreachable); it needs one build on the owner's PC.

### 2026-10-16 · Granular consent with a log (this PR)
- What: seven separate choices, all OFF until the person turns them on: outside AI for open questions, save details noticed in chat, partner sharing, reminders by email (live), and phone reminders, community, usage counts (listed as "coming soon", cannot be granted yet). Every change appends one `consent_event` document (purpose, on/off, wording version, where it was changed: settings, chat card, onboarding, system; no free text). New screen `/privacy-choices` (switch per choice, "what you agreed to, and when"); the chat consent card has an equal "No, not now"; onboarding records a "not now" too.
- Why: the owner wants no blanket or automatic consent, clear and granular choices, and a log.
- Use: `consent_ledger.is_granted(db, uid, purpose)` (missing = not granted) is the one check other features call. Chat-noticed events (`persist_events` on the AI path) are saved only when "Save details I notice in chat" is on. The old `/me/consent` keeps working and writes the same record; the AI answer keeps its old key so nobody who already said yes loses it.
- Where: `backend/consent_ledger.py`, `consent_api.py` (`GET /consents`, `GET /consents/history`, `PUT /consents/{purpose}`), `doc_store.py` (the trail survives "delete all my data"), `frontend/app/privacy-choices/*`, `app/companion/*` (decline button).
- Notes: stored as signed documents, so no migration is needed. People who had already allowed AI keep it, but chat-noticed suggestions stay off until they turn that choice on (default off, as asked). Partner sharing and email reminders are logged when switched through their existing screens; they are not blocked by the ledger. Not built yet: the separate "Your choices" onboarding step, a Terms acknowledgement at sign-up, admin consent rates, and the privacy notice update.

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

### 2026-10 · Lean first-run setup
- Gender (`body`) is the first question, then date of birth (the 18+ gate), then name. Required is now only body, birth date, name, goals and conditions; language and tone default to English and gentle.
- Everything else sits in an optional "A little more" stage (`extra` steps in `onboarding.STEPS`) behind one "Skip all extras" screen; optional steps have a Skip button and required questions carry a "Needed" tag.
- AI consent moved to its own "Your choices" step. The setup screen is "Setting up your app" and takes about 3 seconds.
- Not done yet: skippable app tour, per-purpose consent toggles inside setup, tap-to-advance for single choices.

### 2026-10 · Mind: loneliness, panic, separation, safer notes
- One shared crisis gate (`safety_gate.py`) now covers every tracker note, not only `/wellness/*`; a hit stores nothing and shows the support message (112, Tele-MANAS 14416). New passive-ideation phrases are crisis language (draft in the clinical packet, awaiting sign-off).
- New plain concepts `loneliness`, `panic_attack`, `separation_anxiety` (never an emergency alone, all mapped to the brain). `mind_chat.py` gives the model a friend-style block and gives a short fixed kind reply even without AI consent.
- Mind is a top-level section (Mind, Mood log). Hub has a loneliness check-in and four closed topic rows; `/body?organ=brain` opens the brain.
- Not done: anxiety/stress scores into the brain map and patterns, a mind notification kind.

### 2026-10 · Insight details
- One `InsightDetailSheet` (native dialog) opens from a Details button on every Patterns card, every link between logs and every Today pattern. `app/insights/detail.ts` builds one shape for all three: what Bubbles saw, the days and numbers (a table or a stated gap), how sure (one scale: Early, Fairly steady, Steadier), what it does not mean, one thing to try, Ask Bubbles.
- `/insights?item=<id>` opens one insight and cleans the address; an id no longer in the window shows a calm notice.
- Not done: stable backend ids, `GET /insights/{id}` and per-day occurrence lists. The sheet uses numbers the pages already receive; Today items show a gap sentence for the table.

### 2026-10 · One record, updated everywhere
- `ApiProvider` now exposes `dataVersion` and `lastUpdate`. Any successful write that `app/lib/data-sync.ts` `describeWrite` counts as a change to the record (tracker saves, chat, confirming picked-up events, profile) bumps `dataVersion`, remembers a label and time per person, and tells other tabs over `BroadcastChannel`. Consents, probes, feedback and onboarding never count.
- Today refetches quietly on a bump (old data stays until the newer answer arrives; a failed quiet refresh never replaces good data with an error). `useTracker`, `useBubblesQuery` and the Track hub pulses refetch too, and a newer request always wins over an older one.
- Today shows a "Last updated" card: the newer of this browser's last change and the server's `last_update` from `/health/summary`, so a change made on another device shows as well.
- Not done: the Android app does not yet listen for changes made on another device while it is open (it picks them up on the next load).

### 2026-10 · Plain weight and height from chat are saved at once
- `backend/body_stats.py`: when someone plainly states their own weight ("I weigh 110 kg", already parsed and staged) or height ("my height is 6'1", "I am 185 cm tall"), chat saves it without a Save tap. Weight goes through the same confirm path as the Save button (only pending, present-tense, confidence 0.9 or more); height is written to `profiles.height_cm` and the body profile document. The reply says what was saved.
- Everything else Bubbles picks up (symptoms, medicines, moods, food) still waits for Save. Questions, negations, other people's heights and implausible values (120-230 cm) are ignored.
- Not done: no undo button in the chat reply. Weight can be removed on the Weight page; height can be corrected by saying it again or in Fitness setup.

## 4. Open items

- Confirm the `/body` credit states the Z-Anatomy (CC BY-SA 4.0) and BodyParts3D (CC BY-SA 2.1 JP) licences.
- Clinician sign-off for `clinical_constants.py` before removing the "pending review" banner.
- Decide which further Figma ideas to build (see the Figma entry: only copy lines and the cue motion are in so far).
- Owner to fix `~/.claude/settings.json` model aliases only when wanting the free router back (currently reset to defaults).
