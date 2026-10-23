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

### 2026-10-23 · Safe Harbor, Hinglish people memory and the notice line (Phase 0 of the renovation) (PR #64)
- What: four small fixes that ship together (WP0.1 to WP0.4 in `D:\coco\BUBBLES_RENOVATION_PLAN.md`, Section 7.6 and 14).
  - WP0.1 Safe Harbor, server: before any AI, `safe_harbor.py` reads a message in English, Hinglish and Hindi for violence at home from a partner or family member. Tier 2 is one act of physical violence (a hit, slap, kick, a push or shove with a force, a place, a direction or a time named, burn, a threat to hit). Tier 3 adds a danger marker: choking, a threat to kill, a weapon with danger beside it, forced sex, a child hurt, pregnancy, getting worse, fear together with violence, someone breaking in, or a second tier 2 within 30 days. Both tiers are answered with fixed wording written in advance and no model call, even when the outside-AI choice is on. Control, fear or verbal abuse alone (tier 1) may still use the model, with a gentle instruction block and a quiet offer of help. A person who says they hit, slapped, punched, kicked, beat, choked or strangled, or burned their partner or child, or that they want to hurt them, gets steady, unshaming copy with a path to a counsellor (also fixed, also no model); wider wording such as "I hurt my wife" or "I threatened my husband" is not caught and may reach the model when the person allowed it. If suicide or self-harm is also present, the existing crisis reply comes first and the numbers for being unsafe at home follow it. The messages after a disclosure keep the same voice for up to a day, until the person says they are okay for now; a plain question about something else is answered as usual. State is two signed `doc_store` documents (no new table): `harbor_state` per conversation and `harbor_flag` per person (tier 1 and up; events kept 90 days, used for the 30 day repeat rule).
  - WP0.2 people memory: `people_memory.py` knows Hindi and Hinglish relation words and sentence shapes ("mera dost Rahul hai", "meri behen ka naam Asha hai", "मेरे पति का नाम राहुल है"). Questions, negations and reported speech still save nothing.
  - WP0.3 on screen: web Talk and native Talk draw Safe Harbor replies as plain text (no mascot, no pastel bubble) with a quiet "People who can help" button that opens a sheet of tap-to-call numbers (a link or the dialler; nothing dials by itself) and the follow-up choices. Web: the text is `data-private`, so the Privacy veil blurs it. Native: the screen blocks screenshots and the recent-apps preview while it holds a Safe Harbor reply.
  - WP0.4 notice: the privacy page has a Safe Harbor section, and the notice version moves from 2026-10-16 to 2026-10-23 on the website (`PRIVACY_NOTICE_VERSION`), the server (`consent.POLICY_VERSION`) and the Android app (`AuthRules.NOTICE_VERSION`), held together by tests.
- Why: a message about being hurt at home is the most dangerous and most private thing Bubbles can receive, and free-tier AI providers may let staff read prompts, so it must never leave our server. People also write their closest people in Hinglish ("mera pati Rahul"), and the memory did not recognise those words.
- Use: the person gets a calm human answer and real numbers, nothing is sent to an outside AI, no notification is made from it, and a connected partner cannot see it.
- Where:
  - `backend/safe_harbor.py` (new): reading the message, the fixed copy in three languages, the payload, the model block for tier 1, the two stored documents.
  - `backend/locale_support.py` (new): which numbers to show by country and gender.
  - `backend/chat_pipeline.py`: a `harbor` field on the turn, `assess` in `analyze_turn` (a plain keyword look if the rules ever fail), the `safe_harbor` route right after `emergency`, the `safe_harbor` reply kind, the numbers added after a crisis reply, Safe Harbor turns left out of the earlier messages shown to a model (`conversation_block`), and a stored reply replayed with its `harbor` payload.
  - `backend/main.py`: reads the harbor documents only when the message or the chat needs them and passes them to `analyze_turn`; adds `safe_harbor` to the routes answered without a model; when there is no yes to AI, a tier 1 message gets a short kind fixed line before the usual question (tier 2 and up never asks, it is already answered); for tier 1 and for someone else's story, no evidence lookup and the gentle model block is added to the safety context; no automatic weight or height saving from a Safe Harbor reply; the `harbor` payload (tier, resources, choices) is returned on `/chat` and `/chat/stream`, stored with the reply and returned on reload; the harbor state and flag are written after the reply is saved (a retry replays and writes nothing twice); the housekeeping log line calls these turns plain "deterministic" ones.
  - `backend/people_memory.py`: the Hindi and Hinglish words and shapes; `backend/tests/test_safe_harbor.py`, `backend/tests/test_people_memory.py`, `backend/tests/eval/safe_harbor_cases.jsonl`, `backend/tests/eval/people_memory_hinglish.jsonl`.
  - `backend/consent.py`: `POLICY_VERSION` only.
  - Web: `frontend/app/companion/HarborReply.tsx` (new), `ChatBits.tsx`, `CompanionClient.tsx`, `resume.ts` and `resume.test.ts`; `frontend/app/lib/safe-harbor.ts` and `safe-harbor.test.ts` (new); `frontend/app/privacy/page.tsx`; `frontend/app/lib/privacy-notice-version.ts`.
  - Native: `data/Models.kt` and `ui/screens/TalkScreen.kt`; `SafeHarborTest.kt` (new); `data/AuthRules.kt` and `AuthRulesTest.kt` (version only).
- Notes:
  - Helplines (India) were checked on 2026-10-23 against official sources. 112 emergency and 14416 Tele-MANAS were already in the app. 14490 NCW women helpline (24x7, women and girls 18 and over): PIB factsheet dated 3 July 2026. 181 Women Helpline and 1098 Childline: the Ministry of Women and Child Development answer in Parliament. The 181 line is not run by the West Bengal government (a Rajya Sabha reply of 11 December 2024), so 112 is always shown beside it. The owner should re-check all numbers before the Play Store release. Other countries get the words "your local emergency number" and no number. Bubbles shows no WhatsApp option for 14490.
  - The notice claims only what ships and what code and tests hold. Hitting, a push or shove with a force, a place, a direction or a time named, choking, forced sex, a threat to kill and a weapon, and a person saying they hit their partner or child, are answered by Bubbles itself and never sent to an outside AI, even when that choice is on. Tests send hits, choking, a threat to kill and a weapon over `/chat` and `/chat/stream` with the yes switched on and count zero model calls; the rest are pinned by the detector eval. A plain "he pushes me" with no force, place, direction or time named is not caught as a tier 2 act and may reach the model when the person allowed it, which is why the notice does not promise it. Nothing in the notification code reads chat (notifications are fixed generic templates), and partner sharing can only ever show a cycle estimate, sleep hours and the owner's own note, never chat. The notice says plainly that recognition is by wording and can miss some. It says nothing about replacing names before text goes to an outside AI, or about Orbit (later phases).
  - Tier 1 caveat: control or fear without violence may still reach the model when the person allowed it. The notice says so.
  - Known limits: a symptom named in the same message (for example a sore cheek) is logged like any other symptom, but the message words are not. The Safe Harbor voice reads only the last 10 messages of a chat, so it can be forgotten after ten messages of other talk. `harbor_flag` is read only by Safe Harbor itself for the 30 day repeat rule; nothing uses it yet to pause partner signals (that arrives with Orbit).
  - The Hindi (Devanagari) copy still needs a native speaker before release (plan D7); `safe_harbor.needs_review()` lists it. A lawyer should read the final notice before the Play Store (plan D8). No new dependency, no new table, no safety check weakened.

### 2026-10-22 · Native: in-app account creation, a faster start, and screen tests
- What: the sign-in screen has Sign in / Create account tabs and "Forgot or never set a password?". Creating an account is the website's own Supabase call (same confirm-email rules; the link opens in the browser), keeps the "read the Terms and the Privacy notice" tick until the server can record it (`POST /consents/acknowledgements`, version held to the server's by a test), and can resend the confirmation email. Faster: Today asks its two reads together, OkHttp may run 16 requests per host (the app loads about 18 tracker lists; the default of 5 queued the rest), and one quiet `/health` call at launch wakes a sleeping API host. First Compose screen tests (`app/src/androidTest`, four on the sign-in screen: tabs, validation message, 48dp targets) run on a phone or the emulator.
- Why: a new person could not start in the app without the website, and the free API host sleeps when idle.
- Where: `data/AuthRules.kt` (pure, unit-tested), `data/Api.kt`, `ui/screens/LoginScreen.kt`, `BubblesApp.kt`, `TodayScreen.kt`.

### 2026-10-18 · Native Android app in Kotlin + Compose replaces the wrapper (PR #52)
- What:  `native/` is a real Android app (same applicationId and release key as the Capacitor wrapper, so it updates it in place). It is
  a client of the existing API: no new endpoints, no new tables, no health logic copied. Built: sign-in, first-run setup from the server's
  question bank, first-run tour, Today, Talk, Track (8 trackers, offline), Cycle, Patterns, Care, Community, phone reminders, Your choices,
  Fitness, Partner sharing, the 3D body map and in-app account deletion (see the entries below). Account creation still happens on the website.
- Why:   the owner wanted an app that feels like an app (not a website in a wrapper) and a Play Store release later.
- Rules: missing data is a gap; consent changes go through the server first; no Firebase Analytics; tokens in encrypted storage and excluded
  from backup; sign-out removes the phone from the reminder list. A new person must be able to finish setup on the phone (the gate follows
  `GET /onboarding/state`).
- Where: `native/` (see `native/README.md` and `native/PLAN.md`), `.github/workflows/native.yml`.
- Fitness and in-app account deletion now exist, so the two reasons for holding it back are gone.

### 2026-10-20 · Fitness in the native app: the server keeps every safeguard
- What: full port of Fitness (hub, body setup, food log, diet planner with grocery list and swaps, workouts, strict transformation, progress). The app shows what the server answers and offers Start only when the server says `allowed` or `allowed_with_cautions` (unit-tested in `TransformGateTest`); the server re-checks on start.
- Why: the eating-disorder screening, calorie floors and clinician-clearance path are safety rules. A second copy in the app could drift from the server and let a person past a gate.
- Rules: the SCOFF-style screening and its verdict belong to the server. Workout safety questions and "how do I feel" stop rules are shown in full, first. Missing data is a dash, never 0.
- Where: `native/app/.../ui/screens/fitness/*`, `data/FitnessCalc.kt`. Response shapes were checked against the preview API before parsing.

### 2026-10-20 · Partner sharing in the native app is consent-gated
- What: invite code (48 hours), quick link, connect with a code, leave, and stop all sharing. Nothing is offered until the server reports consent; when off, the screen says so and points to Me, Your choices.
- Why: sharing health information with another person needs a clear yes from the sharer, and the limits are the server's.
- Where: `ui/screens/PartnerScreen.kt`, `data/PartnerCalc.kt` (invite text, expiry countdown, tests in `PartnerCalcTest`). Links use `https://heybubbles.in/partner/<token>`.

### 2026-10-20 · Offline logging queues only requests that never reached the server
- What: tracker entries made with no connection are held in an encrypted queue and sent when the network returns. Only connect-time failures (unknown host, no route, connection refused, connect timeout) are queued, with `date = now`. Read timeouts and dropped answers are not queued.
- Why: health entries have no idempotency key, so a request the server may have saved could be logged twice. Checked on the emulator: offline save, automatic sync, exactly one server copy.
- Rules: sync runs at app open, on network-available and after a save; it stops at the first transient failure and drops entries the server refuses for good (4xx except 401, 408, 429). Sign-out clears the queue after naming how many entries would be lost.
- Where: `data/OfflineQueue.kt` (`QueueRules` is pure and tested), `data/Repo.kt`. Upgrade path: Room, only if offline must cover more than tracker entries.

### 2026-10-20 · 3D body map runs inside the app, with a list and an off switch
- What: the body map is a three.js page and the same `body.glb` as the website, loaded from app assets in a locked-down WebView (JavaScript on; file and content access off; network blocked; navigation blocked). The organ list is always shown, "Hide 3D" is remembered, and a safety message forces "Talk to a doctor" and is never calmer than the server's wording.
- Why: it matches the website without a network call for the model. The model is about 400k triangles, so phones get no antialiasing and a 1.5 pixel ratio, and the 3D view can be turned off.
- Open: speed on real phones is unmeasured (the emulator's software GPU cannot judge it). The list is the fallback.
- Where: `ui/screens/BodyScreen.kt`, `data/OrganStatus.kt` (tested), `assets/body/`.

### 2026-10-20 · Delete my account (native app, Play requirement)
- What: `DELETE /me/account?confirm=true` erases every document (safety holds and community posts included), then removes the Supabase sign-in; every user_id table cascades from auth.users. The native app has "Delete my account" under Your choices; the privacy page says so.
- Why: Google Play requires in-app account deletion; the privacy page said it was "still being built".
- Use: success is answered only when both steps worked (503 otherwise, safe to retry). Sign-in caches are cleared.
- Where: backend/data_rights.py, tests/test_data_rights.py, native ChoicesScreen.kt

### 2026-10-20 · Refetch-loop e2e guard
- What: `npm run e2e:refetch` (frontend/scripts/e2e-refetch-guard.mjs) opens nine sections against the preview API, waits idle, and fails on more than 40 API calls or any 429 per section.
- Why: PR #53 fixed a loop where read-by-POST calls counted as data changes and every screen refetched forever; the unit tests cover the rule, this catches any new cause.
- Use: run before releases, with the preview API on :8001 and `next dev` on :3100 (header of the script has the commands). Not in CI (needs both servers).
- Where: frontend/scripts/e2e-refetch-guard.mjs, frontend/package.json

### 2026-10-17 · Caching, organ map reads in parallel, load test
- What: /organs/map reads its five sources in parallel; backend/loadtest (httpx, AI stubbed, localhost only) shows ~94 req/s on one process with 0 errors at 50 users and p95 847 ms; FirstRunTour loads on demand; /models/* cached for a week; fixed a startup crash in main._warm_database_probe (duplicate local import of threading).
- Why: speed; numbers and method in docs/LOAD_TEST.md.


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

### 2026-10 · Delete a tracker entry
- `DELETE /health/{tracker}/{id}` removes one of the signed-in person's own entries (normal table first, then this tracker's copy in the compatibility store). Someone else's id, an unknown id and an id that is already gone all answer 404.
- Every tracker history list (weight and the other `History` lists) shows a Remove button with a yes/no step; the row leaves the list only after the server agrees, and the delete refreshes Today and the other screens like any other save.
- Not done: deleting a weight the chat saved does not withdraw the matching memory note Bubbles kept from the same message.

### 2026-10 · One value everywhere (trackers, Insights, Companion)
- Where things live: each tracker saves to its own table; Insights, patterns and the doctor timeline read `extracted_health_events`, where a tracker save leaves a "mirror" event tagged with the entry id. A chat statement is a confirmed event that is also projected into the tracker table.
- `DELETE /health/{tracker}/{id}` now removes the mirror too (and retracts a chat-saved weight with the same value on the same day); the earlier version left Insights counting deleted entries. New `PUT /health/{tracker}/{id}` changes the tracker row and rebuilds its mirror, so every reader agrees. Both are own-entries-only (404 otherwise).
- Companion no longer depends on a copy: `latest_values_block.py` reads the newest weight, sleep, mood, water, activity and vitals entries straight from the tracker tables, plus height, and adds them to the chat context as "LATEST SAVED VALUES". A value saved or edited anywhere is what Companion says next; deleting it falls back to the previous real entry; an empty tracker is left out, never shown as zero.
- Saving without a confirm step stays limited to plain, specific statements (own weight, own height). Everything else Bubbles picks up still waits for Save.
- Not done: no Edit button in the apps yet (the API exists); chat-saved entries other than weight are not retracted when their tracker row is deleted; a database view or triggers were not added because the live schema has not been compared with the migrations.

### 2026-10 · Names, live refresh and a startup crash
- One name: `GET /profile` now resolves the display name as setup/settings name, then the profile row, then the sign-up name, and brings the profile row up to date when it had fallen behind (it was only copied when empty, so a changed name never reached pages that read the profile). It also fills `height_cm` from the body profile when the profile row has none.
- Live refresh: the app asks again every 60 seconds while visible, when it is seen again after 10 seconds or more, and when the network returns (`LIVE_REFRESH_MS` in `app/lib/data-sync.ts`). Finishing setup or saving body figures counts as a record change.
- Chat auto-save (plain own weight and height) now needs the "Save details Bubbles notices in chat" consent, like every other chat extraction; without it nothing is saved.
- A bare "today" from chat is stamped with the current time, not midnight, so a weight told in chat after an earlier tracker entry the same day is the latest one.
- Fixed a startup crash already on main: a stray `import threading` inside `_warm_database_probe` made the first line raise `UnboundLocalError`, so the server could not boot. A test now runs the startup hooks.
- The Android app bundles the web files in the APK: backend changes reach it at once, screen changes (live refresh, Remove button, Last updated card) need a new APK from `npm run android:release` and a signed release.

### 2026-10 · Mega task (lane decisions)

# L1 (chat backend) decision draft

For the lead to fold into DECISIONS.md (one entry per feature, newest first) and one line into CLAUDE.md conventions:
`No authority names in reply prose; sources only as links.`

### 2026-10-16 · Chat reply speed: fewer round trips, parallel reads, one model call
- What: `POST /chat` is split into a "prepare" half (sign-in to the safety gate) and a "respond" half. The conversation check and the recent
  turns are read together; the user message is inserted first (the unique client-message index refuses a repeat, the read happens only then);
  after the safety gate the person's own context, the evidence lookup and the tone settings are read side by side (two small thread pools,
  context copied so telemetry and the reply budget keep working); the facts the person stated are saved while the model thinks; the
  conversation timestamp and the turn log run after the reply is out; saving an empty event list does nothing; a message created a moment ago
  skips the duplicate-events read. Optional extras are time-boxed (evidence 2 s, the person's own context 8 s, both logged, never silent).
  The model gets the three sources the screen shows (1,200 characters each) instead of six at 2,000.
- AI quick wins: Gemini minimal-cost settings (thinking level `low`, `GEMINI_THINKING_LEVEL`; retried once without it if a model refuses the
  setting), 900 output tokens (generous on purpose: the reply is JSON), one shared Gemini client, a pooled `requests.Session` for the others
  (`max_tokens`, `reasoning_effort: low` for gpt-oss, JSON response format), `GEMINI_TIMEOUT_S` 9, `AI_REQUEST_TIMEOUT` 18 (the 50 s budget is
  still the ceiling), embedding call 3 s on a pooled session, `analyze_turn` warmed at start-up.
- Caches (ttl_cache rules, admin off switches `cache_enabled.<name>`): embedding per normalised question (1 h, no user id in the key), RAG
  handling policy per document (1 h, cleared on ingest), tone settings (2 min, cleared when the first-run setup or the name is saved, empty never
  stored), profile + preferences for replies (1 min, same invalidation). Memory items and health events are NOT cached: a just-saved symptom
  is in the next turn (tested).
- Numbers (local benchmark `backend/loadtest/chat_bench.py`, real FastAPI app on FakeDB with every database call and the embedding call
  sleeping 80 ms, AI stubbed with 0 ms; n = 30, p50): baseline origin/main d8d5add **1222 ms** for an AI-route message, branch **584 ms**
  (52 % lower); deterministic daily log 580 ms to 422 ms (27 % lower). With a 2 s stubbed model the branch's p50 is 2512 ms (about 500 ms
  of overhead around the model; the baseline was not measured at 2 s). Streaming (`/chat/stream`) total time to `done` is about the same as `/chat`.
- Why: the owner wants speed "at any cost"; an AI turn made about 17 mostly serial round trips around one blocking call.
- Where: `backend/main.py` (`_chat_prepare`, `_chat_respond`, `_context_stage`, `_evidence_stage`), `chat_pipeline.py`, `chat_cache.py`,
  `chat_concurrency.py`, `context_engine.py`, `memory_retrieval.py`, `rag.py`, `ai_provider.py`, `bubbles_ai.py`, `admin_settings.py`.
- Notes: the insert-first path trusts the unique index `uq_chat_messages_user_client_message` (migration 20260919_coco_r7_chat_write_authority);
  the owner should confirm it exists (query in docs/OWNER_TODO.md). Hedging providers (start Groq if Gemini has not answered in 3 to 4 s and
  take the first valid reply) was considered and NOT done: provider order and the allowlist are unchanged. `tests/test_production_contracts.py`
  pins the chat source; its strings were updated deliberately (`_DETERMINISTIC_ROUTES`, `state.consent_required`, `ctx_job = submit(`).

### 2026-10-16 · POST /chat/stream (server-sent events)
- What: beside the untouched `/chat`. Events: `meta` (conversation_id, user_message_id, safety, kind, consent_required) as soon as the safety gate
  is known, `delta` (pieces of the finished reply), `done` (exactly today's `/chat` JSON), `error`; `: ping` every 10 s. Deterministic routes, an
  empty message and a replayed retry send `meta` and `done` only. Headers: `Cache-Control: no-store`, `X-Accel-Buffering: no`.
- Honest limits: (1) `delta` pieces are sentences of the FINISHED reply, cut after the dose scrubber, attribution stripper, lint and the urgent
  call-to-action line, so the person never sees raw model text; this does not make the model faster (the model is still one blocking JSON
  call), it shows text sooner after the model finishes and lets the screen show the safety state before the reply. True token streaming would
  need provider streaming plus an incremental JSON-string reader and was not built. (2) **Whether the Vercel rewrite `/bubbles-api/*` passes
  chunks through is UNVERIFIED** (Vercel cannot be run here, and `next start` cannot stand in for Vercel's edge). The client must fall back to
  plain `/chat` on any error, and may call the API origin directly for the stream. (3) The stream's `api` telemetry event is written when the
  stream opens, so it carries `stage_pre_ms` and the route kind only; ctx, rag, ai and post numbers come from `/chat` turns.
- Where: `backend/main.py` (`chat_stream`, `_sse`, `_delta_chunks`), `backend/tests/test_chat_speed.py`.

### 2026-10-16 · Batch confirmation of chat details
- What: `POST /health-events/confirmation {decisions:[{id, confirmed}]}` (1 to 30) in its own router (`health_event_confirm.py`); the old
  `PATCH /health-events/{id}/confirmation` runs the same code. One read of the current statuses and one update per decision value with a
  status condition (a second press changes nothing). The decision is durable when the update commits; copying into the health record
  (batch variant `project_confirmed_events`: one read, one list insert) and into memory (the usual `promote_health_event` rules) happens after
  the response and never turns a saved decision into an error (failure is logged and retried the next time that detail is saved). Dismissing
  something already saved answers 409. A permission error from the record tables switches the answers to `compat` for 10 minutes.
- The saved state survives a reload: `GET /chat/conversations/{id}/messages`, `GET /chat/latest` and idempotent replays overlay the real status
  from `extracted_health_events` (one owner-scoped query per 100 ids). The stored cap of events per reply is 100 with `health_events_more`.
- Defaults chosen: confirming a fact also promotes it to memory (so the header count can move); a withdrawn (retracted, superseded or rejected)
  detail can never be re-saved (409); dismissing a saved detail is 409 rather than a silent half undo.

### 2026-10-16 · Resumed chats: the 48 hour rule
- What: in a resumed thread, what the person said more than 48 hours ago is history. The model sees those turns labelled "earlier, N days ago,
  not necessarily true now", their symptoms are listed as past (never as current), and an old "no X" is no longer a standing denial.
  The safety engine only ever reads the current message, so this cannot soften an alarm.
- Where: `chat_pipeline.py` (`HISTORY_NOW_HOURS`, `history_user_facts`, `conversation_block`). Clinical note: `docs/drafts/l1-clinical.md`.

### 2026-10-16 · Friend voice (finishing PR #27)
- What: `response_style_instruction()` is the single voice and format rule; the old conflicting lines are gone from `bubbles_ai.py`; the model
  is told to use the evidence silently and never name a publisher; the evidence wrapper carries the fixed sentence about Source/Publisher/URL
  lines. Output guards on AI text only, after the dose scrubber: `strip_attribution` now rewrites any SENTENCE that opens with "NHS guidance
  says", "According to the WHO,", "Studies show" (not just the first), `authority_citation` and `heavy_verdict` lint codes, and the fixed
  call-to-action line on URGENT replies. `normalize_response` no longer turns a friendly paragraph into bullets. "Detailed" users get about 160
  words (was 250), lint `max_words` 150. Care checklist copy and tags in `onboarding.py` no longer name programmes or societies.
- Freeze list: `tests/test_freeze_list.py` hashes every fixed safety text (nine messages through the four safety responses, CRISIS_LINES,
  follow-up, ai_failed, correction, consent, degraded, dose note and the two urgent organ sentences) against the values computed on d8d5add.
- Not done (optional in the brief): trimming an over-long AI reply at a sentence boundary (the prompt asks for 60 to 120 words and lint warns at 150).
- Not mine, still open for their lanes: source chip rows and "Read more" fold (L2, `ChatBits.tsx`), Insights "Sources" label and snippet (L4), the
  `rag_links.py` snippet.

### 2026-10-16 · Model tracking, cost at read time, funnel and app problems (A7)
- What: the five `stage_*_ms` numbers on chat events (numeric allow-list), `funnel` (setup steps reached, fixed names, kept 90 days) and `client`
  (app problem codes, fixed names) event kinds with migration `20261016_bubbles_ops_funnel.sql` (+ undo); until it is applied they stay in memory and the
  technical events still save (own insert, check-violation detected). `POST /telemetry/client {code}` takes one code and nothing else.
  `GET /admin/usage?range=` returns counts and rates (safety tiers per day, reply-kind mix, AI share, consent asks, fallback / degraded /
  timeout rates, route use, funnel, app problems), cost at read time (free tier shows $0 and "free tier", a model with no name or price shows
  "unknown", `if_paid_usd` shows what the tokens would cost at the published price) and distinct-active-people / signup integers (`ops_usage.py`).
- Defaults: while `ALLOW_PAID_AI` is off, every model counts as free tier; Gemini is outside `FREE_MODEL_ALLOWLIST` (documented in DEPLOY.md, `.env.example`
  and docs/admin/README.md as an asymmetry, not changed).
- Where: `ops_telemetry.py`, `ops_metrics.py`, `ops_usage.py`, `client_telemetry.py`, `admin_api.py` (`/usage`), `onboarding_api.py` (three funnel calls),
  `docs/admin/README.md`.

# L2 (chat frontend): decision entry draft

**Talk opens on the latest chat, the loader is the mascot, and a save is instant.** (A1 loader, A3, A4 frontend)

- Opening `/companion` calls `GET /chat/latest?limit=100` once and shows that chat scrolled to its last message (jump, not smooth). Smooth scrolling happens only when the last message id changes; older pages prepend without moving the reader (`resume.ts`, `scrollPlan`). The welcome cards never flash while this loads. Entry points all behave the same: plain Talk, Today ask, body map and the palette. `?new=1` starts blank, and a blank "New chat" is not remembered. No recency cutoff. A server without `/chat/latest` falls back to `/chat/history`.
- `?ask=` / `?askref=` are read once into a ref and sent as a normal message into the chat that ended up open, after resume finishes (`readAsk` deletes the stored text as it reads, so it must not be re-read).
- `degraded: true` or a failed read is an error state with "Try again" and "Start a new chat", never an empty screen that hides history.
- History and New chat buttons are in the header at every width; the palette entry is "New chat" and links to `/companion?new=1`.
- Loader: `ThinkingBubble` is the thinking mascot with a small bob (`bubbles-loader-bob`, in the reduced-motion kill list) inside the same `role="status"` element plus `sr-only` "Bubbles is replying". Caution and urgent states get three plain dots, never the mascot. The send button shows three soft dots (`bubbles-send-dot`). The "Checking memory" header line and its `/memory/diagnostics` call are gone (one call fewer per chat open); the "nothing confirmed yet" line went with it.
- Save / dismiss: `event-decisions.ts` (reducer, optimistic, rollback, settle from server, card view). Pressing a button flips the card at once and sends ONE `POST /health-events/confirmation {decisions:[{id,confirmed}]}` (chunks of 30), commits each id as the answer arrives, rolls back only failed ids, retries once on network errors, refreshes the session once on 401. Timeout or 5xx is "ambiguous": the card says "Saving, checking..." and the real status is re-read from the messages endpoint instead of assuming failure. A second press on a decided event sends nothing. An error row with code 409/410 means Bubbles withdrew the event after a correction and settles as withdrawn. The card counts server-settled events (a reloaded message shows them as saved) and says "Saved" (not "Saved to your health record") unless the projection finished.
- Optional streaming client (`stream.ts`): tries `POST /chat/stream` (events meta, delta, done, error) and falls back to plain `POST /chat` on 404/405/501, 5xx, a broken stream or a stall; the result of the probe is remembered for the page's lifetime. Only text the server already scrubbed is shown, and the real reply replaces the partial text the moment `done` arrives. The backend route does not exist on this branch yet, so today every send takes the plain `/chat` path after one cheap probe.
- Decline: the chat consent card has an equal-weight "No, not now" (`decline.ts`: remembered 14 days on this device, recorded with `PUT /consents/ai_chat_processing {granted:false, source:'chat_card'}` when the server has it). This overlaps L5's planned ConsentCard change; keep one copy when merging.

Defaults chosen: latest chat regardless of age; a missing `/chat/latest` falls back to history; day dividers not built (a quiet "Continuing your chat from <day>" line is shown instead); streaming is a no-op until the backend route lands.

# L3 (Mind): decision entry draft

**Mind is a top-level section with loneliness, anxiety and separation-anxiety support, and every tracker note is safety-screened.** (A5)

- One shared gate: `backend/safety_gate.py` (`safety_gate(*texts, crisis_only=False)`). The wellness routes, the Mind check-ins and now `health_logs` create_entry call it for free-text fields (`notes`, `description`, `reason`, `findings`; the `symptom` name only on crisis wording, because a symptom name is the thing being logged). A hit stores nothing and answers with the same `status: "safety"` shape as before. `mind_checkins.safety_gate` stays as a re-export so existing callers keep working. The old Mood form is therefore screened.
- Support copy now carries the India-first line (112, Tele-MANAS 14416) by reusing `safety_engine.CRISIS_LINES`; no new safety wording was written.
- New ordinary concepts `loneliness`, `panic_attack`, `separation_anxiety` (Hinglish forms included); `anxiety` stays the parent (`CONCEPT_PARENT`). None escalates alone. All map to the brain area.
- Quick scores are screens in `mind_checkins.SCREENS`: `loneliness` (one question, 1 to 5) and `anxiety` (0 to 10). A score only is stored (`doc_store` kind `mind_screen`, key `<kind>:<date>`); no free text, no labels. They do not move the 2 week PHQ-2 / GAD-2 offer timer (`screen_due` counts only those two).
- Brain map feed: `_ev_mood` reads the `Stress n/10; Anxiety n/10` the tracker folds into the note and exposes `stress_score` / `anxiety_score`; `organ_map_engine.observations` emits them; the brain rule watches an average anxiety score at or above `STRESS_HIGH_AVERAGE` (7) over at least `ORGAN_MIN_ENTRIES_FOR_AVERAGE` check-ins, in soft words. No new association pair was added: the data does not yet support one, and every pair makes the false-discovery correction stricter.
- Chat: `backend/mind_chat.py`. `mind_support_block(turn)` (own, current / recent / recurring loneliness, panic, separation anxiety, anxiety or low mood) is appended to the safety context: friend tone, one line of acknowledgement, one small step naming a Mind tool, at most one question, never a label, no medicine. Loneliness is answerable without the AI yes: `loneliness_no_consent_reply` returns a short fixed supportive reply followed by the unchanged frozen `consent_needed_reply` (the consent card still shows). Other topics without the yes still get the plain consent wall.
- Touch points in lane L1's file `backend/main.py` (3 lines, no restructuring): the import, one expression in the `consent_required` reply branch, and one `+ mind_support_block(turn)` on the `safety_context` argument.
- Hub: `/mind` has one primary tile (how are you feeling, with optional stress and anxiety sliders) and closed `Fold` rows: Anxiety check-in, Loneliness check-in, Missing someone / apart, Breathe and ground, Journal, Patterns (year in pixels and own patterns), Your brain on the body map. A visible "Feeling panicky? Breathe with me" button opens the one-tap panic flow (calm words, longer-exhale guide that starts at once, support line, no mascot). The first exercise in the list is now the longer-exhale one. Patterns and the brain row load only when opened.
- `/body?organ=<id>` selects that area (`app/body/organParam.ts`, plain ids only).
- Defaults chosen: loneliness positive at 4 or more (often, almost always); anxiety quick score positive at 7 or more; the standalone anxiety quick score is stored as a score only and does not feed the brain map (only the check-in's optional anxiety / stress sliders do, because the tracker needs a mood to save a row); the optional "gentle mind notification" kind was not built (notifications.py belongs to the push lane and `is_generic` blocks anxiety words).
- Navigation (lead edits once): Mind becomes the 8th top-level item (in the More sheet on phones), `/mood` and `/mind` leave the Track tabs; `/mood` keeps working and is linked from the Mind page footer.

## Insight details: one sheet, one id, one confidence word (A6)

- Every insight has a stable URL-safe id: `rec:<event_type>:<subject>` (repeated), `co:<a>|<b>` (together), `<x>-><y>` (links between logged series). The ids are on `/patterns/analyze`, `/insights/weekly`, the brief's correlations and `/wellness/associations`, and `GET /insights/{id}` (owner-scoped, `days` 7..365) returns the detail with dated entries (ISO days only, never free text).
- One detail sheet (`frontend/app/insights/InsightDetailSheet.tsx`, native `<dialog>`) with six sections in a fixed order: What Bubbles saw, The days and numbers (a real table or a gap sentence), How sure, What this does not mean, One thing to try, Ask Bubbles about it. Built by the pure `detail.ts` for Patterns, links and Today.
- One confidence scale: the server's word (low, medium, high) in `confidence_label`; older responses fall back to the same 0.75 / 0.5 cut-offs (`insights/confidence.ts`). Links between logged series never read High unless the direction repeated.
- Reach: an explicit "Details" button (44 px, name includes the headline) on every Patterns card, link card and Today pattern/also card. Deep link `/insights?item=<id>` is read once, cleared with `history.replaceState`, and says "This pattern is no longer in the last N days" if the window no longer holds it.
- "Your week" on Today never opens to an empty box: a failed call says so with Try again; a week with too little logged says it is a gap.
- Organ-map evidence: the server sends only the newest entries, so the panel says "Showing the N newest of M entries" instead of implying the list is complete.
- Wording: Insights "Sources" is now "Read more", the raw snippet is gone.
- Default chosen: Today's cards still keep the small "Why does Bubbles think this?" fold for the short reasons; Details is the full view.

# L5 draft: decision log entries (B1 database, B2 consent) and the contract for other lanes

For the lead to fold into DECISIONS.md (newest first, one entry per feature). Written on branch `lane/l5-data-trust`.

## Entry: Consent is granular, logged, and off until the person turns it on (B2)

- **Purposes** (stable ids, each separate, default off, nothing pre-ticked): `ai_chat_processing` (alias `ai_chat`), `health_memory_from_chat`, `partner_sharing`, `push_notifications`, `email_reminders`, `community_visibility`, `product_usage_metrics` (listed, `available: false`, cannot be turned on: the standing rule is no analytics; the owner decides). Keeping a person's own logs and chat is a disclosure (`service_storage`), not a consent.
- **Ledger.** `consent_events` is append only (database trigger blocks delete and any update except unlinking the person). Current state = newest row per purpose, and it counts only while its `text_version` is still the current one (changing a description or bumping `text_version` re-asks everyone for that purpose). Nothing but ids, a yes/no, versions, a text hash, a source and a time is stored: never free text.
- **Without the table.** If the migration is not applied (or the table is not granted to the backend, 42501) the same events are written as signed `consent_event` documents via `doc_store`, which `delete_everything` always keeps. The older single yes (document `consent/ai_chat`, version `2026-10b`) still counts for `ai_chat_processing` until a newer decision exists.
- **Delete my data keeps a minimised trail** (default chosen): every granted purpose is first withdrawn (a `system` row), then the ledger rows lose their `user_id` link. What stays: purpose, decision, timestamps, versions, text hash and a one-way HMAC of the user id (key: the doc-signing key). The privacy notice says so in plain words. This lets the owner show an audit trail without keeping a person's identity.
- **Wording fingerprint.** `PUT /consents/{purpose}` for a yes must quote the `text_hash` of the wording currently shown (409 if it changed, 422 if missing); a withdrawal never needs it. Server stamps `policy_version` (= the privacy notice version) and `text_version`.
- **Enforcement points** (server side, never from the client): AI provider calls (`has_ai_consent`, existing gate in `chat()`), chat-derived events (`consent.persist_chat_events`: when `health_memory_from_chat` is off nothing is extracted into storage; explicit tracker logs still save), partner sharing (every owner action, accepting an invite, the public quick link, and the partner's view; withdrawal calls `partner_sharing.stop_all`), email reminders (the channel is mirrored from the purpose; `create_notification` checks it again), push (the channel switch is mirrored; L8 gates registration with `is_granted(..., "push_notifications")`), `/privacy/consent/check` and `/sharing/plan` (they ignore any dict the browser sends). `PUT /notifications/settings` cannot turn email or push on by itself.
- **Chat card.** Equal-weight "No, not now" records a decline (source `chat_card`), shows a calm line and stops re-asking: the server asks again at most once per 14 days or when the wording changes (`consent_ask: false` in the `/chat` response; the card is not shown, the reply is the short fixed `declined_reply`). The frozen last sentence of `consent_needed_reply` ("If something feels urgent, call your local emergency number.") is unchanged; a test pins it. An urgent message still gets the fixed urgent text.
- **Defaults to flag to the owner.** In-app reminders and the three reminder types (water, medicine, wind-down) remain on by default because they only appear inside the app; they are not a processing choice. Email and push are off and need the matching purpose. The sign-up Terms/Privacy tick is an acknowledgement (ledger purpose `ack_terms_privacy`), recorded after the first signed-in request, not a bundled consent.
- **Admin.** `consent.consent_rates(db)` returns counts only per purpose (granted, declined, rate; people are counted by their one-way hash). L9 renders it. When the table is missing it returns `available: false` (the fallback documents are per person and cannot be counted across people).

## Entry: Database: indexes, register, N+1, and an optional tightening (B1)

- Migrations (all `20261016_bubbles_*`, idempotent, with undo): `indexes_v2` (earlier on main), `schema_migrations`, `lookup_indexes`, `consent_ledger`, `rls_tightening` (**optional, default off**). Run order in `docs/OWNER_TODO.md`. Findings and the owner's read-only checks: `docs/DB_AUDIT.md`.
- `bubbles_schema_migrations` records applied migrations; `GET /admin/schema` (admin gate) lists the missing ones from `schema_status.KNOWN`. Lanes with a migration add its name to `KNOWN` and end the file with the guarded insert (see the other files).
- N+1: `/chat/history` counts via `bubbles_chat_counts` (fallback: parallel counts), `/health/summary` reads concurrently and skips the compat scan for people with none (flag cached 5 min, cleared by any compat save), `/chat/feedback` one read (`doc_store.get_many`), `delete_everything` chunked deletes.
- The tightening migration replaces browser-writable `FOR ALL` policies with select-only and hides signed documents from browsers. The website never uses the Data API for tables (grep: only `supabase.auth.*`). Owner applies it deliberately.

## Contract for other lanes (exact)

- `consent.is_granted(db, uid: str, purpose: str) -> bool`. Missing, unknown, unavailable, unreadable all return `False`. 5 minute per-user cache, cleared on every write. Accepts the alias `ai_chat`. Other lanes may import it directly (it exists on this branch); the try/except ImportError shim is only needed until this branch merges.
- Purpose ids: `ai_chat_processing`, `health_memory_from_chat`, `partner_sharing`, `push_notifications`, `email_reminders`, `community_visibility`, `product_usage_metrics`. Also `consent.ACK_PURPOSE = "ack_terms_privacy"` (acknowledgement events only).
- Text hashes right now (always read them from `GET /consents`, they change when a description changes; never hard-code): ai_chat_processing `9d2ef9c15f26233c` (text_version 2026-10b), health_memory_from_chat `28f84d6ff7698c3c`, partner_sharing `f48f4cbb5702a3e8`, push_notifications `3b50bf7bee8ed9bc`, email_reminders `4a80ff6d3d6a9357`, community_visibility `c5c88ba9183cf800` (all 2026-10a), product_usage_metrics `33ed14157270f8a4` (unavailable). Server side: `consent.text_hash(purpose)`.
- Endpoints (all need the Bearer token):
  - `GET /consents` -> `{status, policy_version, purposes:[{id, title, description, text_version, text_hash, available, granted, decision: "granted"|"declined"|"none", decided_at}], disclosures:[{id,title,text}]}`
  - `PUT /consents/{purpose}` body `{granted: bool, source: "settings"|"chat_card"|"onboarding"|"system"|"signup", text_hash: string (required when granted)}` -> `{status, consent:{...purpose state}}`; 404 unknown, 409 hash mismatch or unavailable, 422 bad body.
  - `GET /consents/history?limit=100` -> `{status, events:[{purpose, title, granted, source, text_version, created_at, kind: "consent"|"acknowledgement"}]}`
  - `POST /consents/acknowledgements` body `{version}` -> `{status, acknowledged, version}`
  - `GET|PUT /me/consent` shim: `{ai_chat: bool}` (+ optional `source`) for `ai_chat_processing`.
- **L6 (onboarding consent step)**: remove the bundled `ai_consent` question; after the required questions show one unticked switch per offered purpose (suggested: `ai_chat_processing`, `health_memory_from_chat`, `push_notifications` and `email_reminders` only if the user wants reminders; not `partner_sharing`/`community_visibility`), each with `title` and `description` from `GET /consents` and a neutral "Not now" (Continue always enabled). For each switch the person turns on: `PUT /consents/{id}` with `source: "onboarding"` and that purpose's `text_hash`. A "Not now" for a purpose is recorded as `granted: false` with the same call (no hash needed). `backend/onboarding_api.py` still writes the older yes through `consent.set_ai_chat(db, uid, True)` when the old `ai_consent` answer is "yes"; delete that when the bundled question goes.
- **L8 (push)**: gate `POST /notifications/push/register` with `consent.is_granted(db, uid, "push_notifications")`; consent already mirrors `channels.push` in `notification_settings` and calls `notifications.save_settings`; on withdrawal revoke tokens (hook point: `consent._after_change`, branch `push_notifications`; add a call there). `wellness_api.settings_put` now forces `channels.email`/`channels.push` to the purpose state.
- **L9 (admin)**: `consent.consent_rates(db)` (counts only) and `schema_status.report(db)` / `GET /admin/schema`.
- **L10 (community)**: require `is_granted(db, uid, "community_visibility")` before a post or comment; withdrawal should hide the person's posts (hook point: `consent._after_change`).
- **L1/L2**: `/chat` response gained `consent_ask: bool` (true when the Yes/No card should show; false after a recent No). `CompanionClient.tsx` got two one-line changes (see below).

## Files outside this lane's ownership that were touched (smallest change; tell the lead)

- `frontend/app/companion/ChatBits.tsx` (L2): `ConsentCard` only: a "No, not now" button, reads `/consents` once to stay quiet after an answer, imports `useApi`, `Link`, `aiCardView`, `readOverview`.
- `frontend/app/companion/CompanionClient.tsx` (L2): `allowAi` sends `source: "chat_card"`; `consentRequired` also requires `payload.consent_ask !== false`.
- `backend/wellness_api.py` (L3 area): `settings_put` forces email/push to the purpose (3 lines + import).
- `frontend/components/Providers.tsx`: one effect in `ExperienceProvider` that records the sign-up acknowledgement after the first signed-in load (+ import).
- `frontend/components/wellness/NotificationSettingsCard.tsx` (L8 area): the Email switch became a line with a link to Privacy choices.
- `backend/health_logs.py`: compat flag and concurrent summary (B1). `backend/main.py`: `message_counts`, `schema_status` router, consent enforcement lines.
- `frontend/app/landing/Landing.tsx`: footer link "Privacy choices".
- Navigation: no entry needed (Privacy choices is reached from Settings > Privacy and data and the footer). Optionally add `{ href: "/privacy-choices", label: "Privacy choices" }` to the command palette.

# A6. Insight details: problem statement and what was built

Line numbers are from the session branch before this lane's change (commit 7b3b038).

## Problem

A person sees "Your sleep has moved" or "Headache came up 5 times" and cannot find out why. Every insight lives on one of five
surfaces (Today folds, Patterns page, link cards, weekly recap, organ-map evidence) and none has a detail view or an address.
Affected: everyone who logs, most of all people using a screen reader or keyboard only (links share one name, headlines are not
headings) and people on a phone, where the only path was a bare `/insights` list.

## Root causes

1. Today's "See the evidence" and "Why does Bubbles think this?" go to bare `/insights`: `TodaySections.tsx:316` (`whyHref`), `today.ts:339`
   (`whyHref: "/insights"`). `InsightsClient.tsx` read no id, hash or query, so the link landed on the top of an unrelated page.
2. No shared id. Today used positional ids (`insight-N`, `corr-N`, `today.ts:395`), Patterns used `r-<type>-<subject>` / `c-<a>-<b>`
   (`patterns.ts:73,88`), links used `x->y`. The same finding had three names.
3. Evidence was a count sentence. `source_event_ids` (`pattern_engine.py:151,204`, `weekly_insights.py:60,70`) could not be resolved: no
   `GET /insights/{id}`, no dated entries, no pairs. Fields the API returns (deviations, rho/q/lag, supporting_events,
   suggested_action) were never rendered.
4. Three confidence scales behind one chip: entry confidence in the pattern engine, a count heuristic `0.3 + 0.05 * evidence`
   (`weekly_insights.py:108-110`), and strength words for links.
5. Accessibility: card headlines were `<p>`/`<strong>`, link names were not unique, "Your week" opened to an empty box when its call failed.

## What changed

Backend (additive, no schema change)
- One stable URL-safe id per insight: `rec:<type>:<subject>`, `co:<a>|<b>`, `x->y`, `gap:week` (`pattern_engine.slug/recurrence_id/correlation_id`),
  on `/patterns/analyze`, `/insights/weekly` (`schemas.InsightItem.id`), the brief's correlations and `/wellness/associations`.
- One confidence word (`confidence_label`: low/medium/high) from `pattern_engine.recurrence_confidence/correlation_confidence`; the
  weekly number now agrees with it.
- Dated detail: `occurrences` (newest 14, ISO day + event id), correlation `pairs` (newest 12), association `pairs`, `p`, `repeated`,
  `limitations` list. Days only, never free text.
- `GET /insights/{id}?days=7..365` (`insights_api.py`): owner-scoped by `user_id`, id length capped at 120, unknown or malformed id is a
  plain 404, `source_event_ids` stripped, retracted/rejected rows never count. Registered after `/insights/weekly` so that path wins.

Frontend
- `app/insights/detail.ts` (`toDetail`, pure): six sections in one order for every kind. `confidence.ts`: one scale.
- `InsightDetailSheet.tsx`: native modal `<dialog>`, heading focus on open, `aria-labelledby`, Esc/backdrop/44 px Close, focus returns to
  the trigger, scroll lock. Android back already closes `dialog[open]` (`NativeBridge.tsx:28`), so no Android change was needed.
- Details button (44 px, name "Details about <headline>") on every Patterns card, link card and Today pattern card; headlines are
  `<h3>`. `/insights?item=<id>` is read once, cleared with `history.replaceState`, falls back to "This pattern is no longer in the last N days".
- "Your week" never opens empty; organ-map evidence says "Showing the N newest of M entries".
- Replaced the session branch's smaller frontend-only first pass (`components/InsightDetailSheet.tsx`, old `detail.ts`) with this one.

Voice and consent: no authority names anywhere (tested), no cause or diagnosis wording. Insights only read the person's own saved events;
what is saved is already governed by `consent.is_granted` at write time, and no new write path exists here.
Today's first-run tour selectors (`#today-ask`, quick-log, signals, body-map, profile-link) were not touched.

# C1 first-run setup: problem statement (lane L6)

## Problem
The first run asked 44 questions in 9 steps (about 30 answered), required 7, hid Skip, put gender third, said "About three minutes",
ran the 18+ check only when `birth_date` was in the same request (a body saved first was stored before the age was known), and held
people on a 4.5 s "Creating your personal companion" screen. Most answers changed nothing visible. There was no tour.

## Every old question, what it changed, what became of it
Real effect = it is read by a feature today. Kept = asked on first run. Later = only in Me > Your setup (`edit=1`). Dropped = gone.

| Old question(s) | What it changed in the product | Now |
|---|---|---|
| body | menu (Cycle), body map, cycle mode, profiles.gender, formula basis | Kept, FIRST screen, one tap, required |
| language | chat style (Hinglish/Hindi), Hinglish question titles | Kept, same first screen as a 3-chip row (default from browser), required |
| birth_date | profile, age-based care checklist, 18+ gate | Kept, required, saved in the same request as body |
| preferred_name | profile display name, chat greeting | Kept, required |
| goals (multi 10) | trackers_suggested, mind offer | Merged into `main_goal` (single, 9 options, cycle only for REPRO bodies), required |
| conditions (16, required) | saved to Care conditions | `conditions_any` yes/no/prefer not (required) then the 16-list only after yes |
| conditions_other | Care condition, safety-checked free text | Kept as follow-up after "other" |
| feeling_lately | mind offer | Replaced by `stress_level` (4 chips, required): drives mind check-in offer and trackers |
| sleep_hours (slider, optional) | stored, never read | Replaced by `sleep_pattern` (4 chips, required): drives sleep tracker and a Care item; old hours convert on load |
| periods (+ reason, last_period, pregnancy_plans, due_date, baby_birth_date) | cycle settings, cycle mode, body profile flags | `periods` required for a female body only (`REQUIRED_IF`); follow-ups are optional extras |
| height_weight, activity, diet_style | body profile, fitness and food plans | Kept as optional extras; `diet_style` key kept (L7) |
| (new) recent_blood_test | read by the deficiency work (L7) | Optional extra, key kept |
| allergies, allergy_types | Care allergies | Optional extra |
| takes_medicines | stored, never read | Optional extra yes/no (one tap; stored for later use) |
| avoid_topics, tone, reply_length | chat style block | Optional extras ("How Bubbles talks") |
| support_people, drains, drains_other, checkins_wanted | companion context only (comfort and stressors) | Optional extras |
| helps, mind_check, mind_note | stored, never read; mind_note was free text about distress | Dropped (mind_note removed: no reason to collect free text about distress at sign-up) |
| family_history, tobacco(4 forms), alcohol_freq/amount/heavy | stored, never read | Family history and alcohol dropped; tobacco moved to Later |
| eyes, last_eye_exam, screen_hours | stored, never read | Eyes dropped; last_eye_exam and screen_hours in Later |
| bp_sugar_check, cervical_screen, midlife_changes, urinary_changes | one care-checklist line each | Later only (never on first run) |
| ai_consent (inside the bank) | wrote a consent | REMOVED as a question. Consent is a separate "Your choices" step writing the consent ledger; setup itself never writes a consent |

Result: required core is 7 taps for a male body, 8 for a female body (body, language, date and name on one screen, main goal,
conditions yes/no, sleep, stress, periods). Optional extras are grouped on 6 screens behind one intro with "Skip all extras".

## What was built
- Server bank (`backend/onboarding.py`): screens, `REQUIRED_IF`, answer migration from the old bank, `BANK_VERSION 2026-10b` (finished people are not sent back).
- Gate ordering (`onboarding_api.py`): the age check runs on the date in the request or the date already known; no date means 422 and nothing is stored; under 18 stores only `age_gate`.
- Client (`flow.ts`, `OnboardingClient.tsx`): body is a single tap that waits; it is sent only together with a valid date. Auto-advance on single choice, explicit Skip, "Needed" lock tag, "Question n of N" then "A few extras (skip any)", honest "About a minute" copy.
- Setup screen: "Setting up your app" / "Set up my app", min 1200 ms, 250 ms per line, at most 4 lines, auto-open 2000 ms, retry state kept.
- Tour (`tour.ts`, `FirstRunTour.tsx`, `GET/PUT /onboarding/tour`): five coach marks on Today, skippable (button or Esc), focus kept inside, replay from Settings.

## Defaults chosen
Hindi browsers default `language` to Hindi, everyone else English. Tour state lives in a signed doc (`tour/v1`), no schema change.
`tone` and `reply_length` moved out of the required set (the brief asked tone stay short; it is now an optional 3-chip extra defaulting to gentle).

# E1 Android push: problem statement (lane L8)

Written against the session branch `mega/part2-chat-backend` (which already contains main's #33 Firebase and #34 Android 1.2.0). Line numbers are from that branch before this lane's changes.

## What the brief assumed, and what is really there

The brief (E1) says "today there is no push of any kind". That was true of the repo at d8d5add. It is not true of the session branch: #33 already added the phone-reminder stack. This lane therefore **builds on it and does not duplicate it**. An earlier WIP of this lane (a `device_tokens` table, `push_devices.py`, a second FCM sender, `push_api.py` with register routes) was dropped at merge for that reason.

Already present (do not redo):

| Piece | Where |
|---|---|
| FCM HTTP v1 sender, service account from `FIREBASE_SERVICE_ACCOUNT_JSON` (JSON or base64), google-auth OAuth, 5 s timeout, fail-soft | `backend/push_fcm.py` (`send_to_user` 186, `_token_is_gone` ~175) |
| Device store: signed `push_device` documents, one owner per phone (`_release_elsewhere`), max 5 per person, token regex | `backend/push_fcm.py:127` `register_device`, `:144` `remove_device` |
| Routes: `POST /notifications/devices`, `/notifications/devices/remove`, `/notifications/push/test` | `backend/wellness_api.py:564-592` |
| Push as a channel inside `create_notification` (so quiet hours, daily cap, dedupe are decided once; a push-only user is not dropped) | `backend/notifications.py:216-232` |
| Consent: `push_notifications` purpose; switch and consent mirrored | `backend/consent.py:62, 294`, `wellness_api.py:555` |
| Generic text only (`sanitise`), Android `visibility: PRIVATE`, TTL 1 h | `backend/push_fcm.py` `_message`, `notifications.py:76` |
| "Delete my data" removes `push_device` docs | `doc_store.delete_everything` (all non-trail kinds), test `test_delete_everything_forgets_the_phone` |
| Android: `BubblesFirebasePlugin`, conditional google-services plugin, manifest meta-data, `ic_stat_bubbles`, `@capacitor/push-notifications`, Settings switch "On this phone", sign-in refresh, back button | `frontend/android/**`, `frontend/lib/firebase-native.ts`, `components/wellness/NotificationSettingsCard.tsx`, `components/NativeBridge.tsx` |
| `keep-awake.yml` second step calling `/internal/push/run` | `.github/workflows/keep-awake.yml` (from this lane's WIP, kept) |

## What was actually missing (the problems this lane fixes)

1. **No scheduler that works on the free host.** The only trigger was an in-process thread (`push_fcm.start_background`, `push_fcm.py:273`). Render's free plan sleeps the process, so nothing runs while it is asleep; the keep-awake cron only pings `/health`. There was no protected endpoint for the cron to call, no `BUBBLES_CRON_SECRET`, and `ops_rollups.run_rollups` (L9) had no scheduled caller.
2. **A phone could be registered without any yes on record.** `device_add` (`wellness_api.py:564`) stored a token whether or not the switch or the consent was on; only sending checked. The brief requires a refusal (422) unless push consent is granted.
3. **Withdrawing consent left the tokens behind.** `notifications.save_settings` (`notifications.py:154`) and `consent._mirror_channel` only flipped the switch. Tokens stayed stored and (on the phone) the FCM token stayed alive.
4. **Sign-out did not tell the server.** `forgetPhoneOnSignOut()` (`firebase-native.ts:145`, called at `Providers.tsx:161`) deleted the token on the phone only; the server kept the row for the old account until FCM reported it gone.
5. **The card sent the token before the yes was saved** (`connectPhone` at toggle time), which would now be refused; and a consent withdrawn in Privacy choices never disconnected the phone.
6. **Notification tap did nothing.** No `pushNotificationActionPerformed` handler: a tap just opened the app wherever it was.
7. **Dedupe not safe against overlapping runs.** `create_notification` checks the last 200 docs, then writes with a random id (`notifications.py:219, 224`): two runs can both pass the check and both send.
8. **Windows too narrow for a best-effort cron.** Wind-down `< 30` min (`notifications.py:286`), water `< 60` min (`hydration_engine.py:142`), while GitHub cron is 5-15 min late.
9. **A lock screen is not private.** The medicine reminder pushed the title "Medicine check-in", which says the person takes medicine. Brief: no health details on the lock screen.
10. **No unbounded-run protection** in `push_fcm.sweep`: no batch size, no time budget, no overlap guard, no clean-up of phones whose owner no longer says yes.
11. **Tests**: the happy paths existed (`test_push_fcm.py`), but no tests for the negative cases in the brief (wrong/missing secret, replays, in-flight withdrawal, FCM errors, other users' tokens, garbage input, payload content), and none for the phone-side flows (denied permission, offline, sign-out).

## Decisions

- **No `device_tokens` table / migration.** The doc-store `push_device` rows already are the token store and the fan-out index (`users_with_devices` selects by kind), are signed, owner-scoped, RLS-protected like every doc, wiped by "Delete my data" and need no migration the owner has to run. A second store would duplicate #33 and add a migration for no gain. If the 5,000-row scan in `users_with_devices` ever matters, a table can be added behind the same functions.
- Cron secret env: `BUBBLES_CRON_SECRET` (also accepts `NOTIFY_CRON_SECRET`, the name in brief section 8). Unset or wrong secret, wrong method: the same plain 404 as an unknown path.
- Reminder windows: wind-down +-45 min, water 90 min; the per-slot dedupe key keeps wide windows from sending twice.
- Push text for medicine reminders is the neutral "Bubbles / You have a reminder in Bubbles." (the in-app copy keeps "Medicine check-in").

## Owner steps (for docs/OWNER_TODO.md)

1. Firebase console: create a project, add an Android app with package `in.heybubbles.app`, download `google-services.json` to `frontend/android/app/` (never commit it).
2. Project settings, Service accounts: generate a private key. Render env: `FIREBASE_SERVICE_ACCOUNT_JSON` (the JSON, or its base64). The brief's `FCM_SERVICE_ACCOUNT_B64` / `FCM_SERVICE_ACCOUNT_JSON` names are NOT what the merged code reads (#33 chose `FIREBASE_SERVICE_ACCOUNT_JSON`).
3. Render env `BUBBLES_CRON_SECRET` = a long random string (`NOTIFY_CRON_SECRET` also accepted). GitHub repository secret `BUBBLES_CRON_SECRET` = the same value; until it exists the workflow step skips itself.
4. No device-token migration is needed (tokens are signed doc-store rows).
5. Rebuild and re-sign the APK after step 1 (`npm run android:release`); older APKs keep working without phone reminders.
6. Check: Settings, Reminders, On this phone, Save, then "Send a test to this phone".

# F1 + F2: Admin Live and Overall pages (lane L9)

## Problem statement

The owner runs Bubbles from the admin portal and cannot answer four plain questions today.

1. **"Who just hit the app, and how did it go?"** The old Live tab lists technical events but by design carries no account id, so a report like "my chat was slow" cannot be matched to a request. Cause: `ops_telemetry.record()` accepted no user field (the ring held `{seq, at, kind, request_id, data}` only, `backend/ops_telemetry.py` module note) and `/admin/events/live` returned the raw ring. The tab also showed one line per event rather than one row per request, so an AI try, its fallback and the reply were three unrelated lines to stitch by hand (old `frontend/app/admin/panels.tsx`).
2. **"Where does a chat turn spend its time?"** The api event carried no stage timings. The stage field names (`stage_pre_ms`, `stage_ctx_ms`, `stage_rag_ms`, `stage_ai_ms`, `stage_post_ms`) were not on the `api` allow-list (`ops_telemetry.FIELDS["api"]`), so the pipeline's measurements would have been silently dropped.
3. **"How is Bubbles doing overall, since the start?"** Every number on the portal is computed from at most 20,000 raw events (`ops_telemetry.READ_CAP`), which are pruned after 14 days and are memory-only until the owner applies `20261013_bubbles_ops.sql`; a Render restart or sleep loses them. There was no all-time total, no 7d/30d beyond raw retention, no retention curve, no consent rate per purpose, no onboarding drop-off (`admin_api.py` had ranges up to `30d` only, all from raw events).
4. **"What should I look at next?"** Nothing exported, nothing refreshed itself while the tab was hidden or paused correctly, and nobody could tell when the page was only showing memory.

Constraints that shaped the fix: the admin gate (fresh sign-in, two-step, allow-list, byte-identical 404) stays exactly as it is; telemetry stays metadata only; the one owner-approved exception is the account id on the Live page, kept in the in-memory ring only; $0 infrastructure (no Redis, no SSE, no new dependency); the app must keep working when the owner has not applied the new migrations.

## What changed

Backend
- `ops_telemetry.py`: `bind_user` (UUID-shaped only), a top-level `uid` on `api` and `ai_attempt` events in the ring only (never in `data`, the queue, the table or the notes), `recent(with_uid=True)` as the only reader that returns it, `STAGE_FIELDS`, numeric validation of stage values in `record()`, `until` on `stored_events` (hour-by-hour reads for the rollup).
- `ops_rollups.py` (new): `count_events` (pure, tolerant of malformed rows), `run_rollups(db)` (idempotent hourly job with a watermark moved in the same upsert; exported for lane L8's cron endpoint), `collect(db, range)` for `1h/24h/7d/30d/all`, lazy refresh with a non-blocking lock.
- `ops_metrics.overall_view`, `ops_snapshots.py` (new: DAU/WAU/MAU, signups, D1/D7/D30 retention, consent rates, community and push counts, integers only), `admin_api.py`: `GET /admin/live` (alias of `/events/live`, with `since` or `after` cursor) and `GET /admin/overall?range=`.
- `supabase/migrations/20261016_bubbles_ops_rollups.sql` (+ undo): `ops_rollups_daily`, RLS on, service role only. Registered in `schema_status.py`.
- Reconciled with the session branch: one `funnel`/`client` contract (L1's `FUNNEL_STEPS = core, extras, later, completed, under_18`, `ops_telemetry.client(code)`, `/telemetry/client`); my duplicate migration and `client_events_api.py` were removed; cost uses L1's `model_cost` (A7).

Frontend (`frontend/app/admin`)
- Live: one row per request (UID with copy button, time, route, feature, provider, model, fallback, safety, status, latency, stage breakdown, error), filters, pause/resume, row detail with the request-id chain, polling every 3 s paused when the tab is hidden, a banner when events are memory only.
- Overall: totals, per-model rates, per-stage latency, funnel, retention, consent, safety, features, errors, community, push; range picker; CSV export per table (formula-safe); refresh every 20 s, paused when hidden.

Docs: `docs/admin/README.md` (named exception, Add another admin, rollup and cron contract), `DESIGN.md`, one line on `/privacy`.

## Decisions taken from defaults

- Refusals stay a byte-identical 404 (the brief says keep the gate exactly as is); the "403 for non-admin, 401 for anonymous" in the lane message was not applied because it would reveal that `/admin` exists and break the existing contract and its tests.
- Polling, not SSE (not verified on the Render free plan).
- Cost shows `$0, free tier` while paid AI is off.

## Open

- Owner: apply `20261016_bubbles_ops_rollups.sql` (and `20261016_bubbles_ops_funnel.sql`) in Supabase; until then Overall counts only what is held.
- Lane L8 must call `ops_rollups.run_rollups(db)` from its cron endpoint (optional: the page also rolls up lazily).
- Single-instance assumption for the rollup watermark (no compare-and-swap).

### 2026-10 · Community (G1)

**Community v1: text-only, consented, alias-anonymous, bot-moderated, owner-reviewed.**
- Text only. No images, video, files or link previews. Checking images for nudity needs a vision classifier, which the $0-AI policy does not provide. Images stay out of scope until the owner decides.
- Off until `COMMUNITY_ALIAS_SECRET` (16+ characters) is set on the API host. There is no default secret on purpose. Unset means every community route answers "off" and the admin Moderation tab says why.
- Aliases ("Quiet Otter 4821") come from an HMAC of (author, thread) with that secret: stable inside one thread, different across threads. No response ever carries `author_id`. Only the admin can resolve an alias (`POST /admin/community/resolve`), and the lookup is written to the moderation log before the answer leaves.
- Who can post: signed in, 18+ (birth date from setup), `community_visibility` consent granted, not banned. Reading needs only sign-in and 18+. Deleting your own posts and comments works even after withdrawing consent.
- Limits: 5 posts/hour, 20 comments/hour, 10 reports/hour, post 1,200 and comment 600 characters, duplicate text refused for 24 hours. Deleting leaves a stub so the hourly limit cannot be dodged.
- Moderation order: deterministic filters (`community_moderation.py`, word lists as data), crisis wording kept and held for the owner with the caring banner (112, Tele-MANAS 14416 / 1-800-891-4416, findahelpline.com via `safety_engine.CRISIS_LINES`), held when unsure (visible to the author only), removed when certain, 3 distinct reporters auto-hide, admin decides. No AI text classifier in v1 (consent for `ai_chat_processing` does not cover posts).
- Crisis posts are held (not on the feed) until the owner looks, then approved or removed. Frontend shows the banner without the mascot.
- The admin sees post text in the Moderation tab: the owner is the data controller of a shared space. Add one plain line to the privacy notice.
- Delete-my-data wipes posts, comments, reactions, reports and blocks (`community_api.forget`); the moderation log keeps codes only.

## Frontend

- `frontend/app/community/` (page, `CommunityClient.tsx`, pure `community.ts` + test): feed with topic chips and My posts, big "Ask or share" button opening a sheet (anonymous switch, topic, text), reactions (Me too, Helpful), closed Comments row, report / block, delete own, "Show more" cursor paging, mascot empty state, permanent line "Shared by people, not medical advice."
- Posting needs consent: the button is disabled with a link to Privacy choices (`/privacy-choices`) when `reason` is `consent_needed`.
- Admin: `frontend/app/admin/panels-moderation.tsx`, registered in `registry.tsx`, tab `moderation` in `format.ts` (queue with crisis first, approve / remove / remove and ban, "Who wrote this", audit log).


### 2026-10-22 · Site speed: fewer database trips in a row, a lighter Today, an early wake-up call
- What: `/fitness/summary` ran 15 reads one after another; its independent reads now run side by side (`backend/parallel.py` `together`, which carries the request time zone into each job) and the four plan documents come in one read (`doc_store.get_pairs`, documents of different kinds in one trip). The same helper speeds `engine()` (every Fitness screen), `/nutrients/nudges` (5 reads) and `/profile` (3 reads). `GET /health/summary?last_only=true` asks one row per tracker and sends only `last_update`; Today uses it (it only ever needed that, and read a field the server never sent, so the card always fell back to the browser's own stamp). A small `WakeApi` in the root layout sends one quiet `/health` call when someone lands on any page, so a sleeping free-plan API starts while they read the landing page or type their password instead of after sign-in.
- Why: measured with the preview server's fake database (trips per endpoint; the real cost is each trip times the Supabase round trip from Render): `/fitness/summary` 15 to 10 trips with a chain of about 2 instead of 15, `/profile` 3 to 2, `/nutrients/nudges` waits for one step instead of five. Answers are unchanged.
- Rules kept: every read is still owner-scoped and signed-document checked; a failing job raises exactly as the sequential code did; the full `/health/summary` (counts) is unchanged for the Health hub.
- Where: `backend/parallel.py`, `doc_store.py`, `fitness_api.py`, `deficiency_api.py`, `health_logs.py`, `main.py` (`/profile`), `frontend/components/WakeApi.tsx`, `app/lib/wake-api.ts`, `DashboardClient.tsx`; tests `tests/test_read_speed.py`, `test_health_logs.py`, `wake-api.test.ts`.
- Not done on purpose: one combined "Today" endpoint (a big API change for the owner to review first) and a tighter keep-awake schedule (GitHub's free minutes would not cover it).

### 2026-10-22 · Compressed answers and a palette that asks only when opened
- What: the API compresses answers over 1 KB for clients that send `Accept-Encoding: gzip` (`GZipMiddleware`; Starlette leaves `text/event-stream` alone, so the chat stream still arrives word by word). The Ctrl+K "Ask or jump" palette loads its suggestions and recent questions when it is opened (at most once a minute), not on every page load.
- Why: measured on the preview API, `/patterns/analyze` answers 147 KB, `/doctor/prepare` 72 KB, `/onboarding/questions` 15 KB of JSON, which shrinks four to six times; the Android app calls the API directly over mobile data. Every signed-in page used to make two extra calls for a palette most visits never open.
- Where: `backend/main.py`, `tests/test_compression.py`, `frontend/components/AskBubbles.tsx`.

### 2026-10-22 · Chat remembers the people and pets in a person's life, and answers back instantly
- What: "my boyfriend's name is Ashmit" was never saved (the extractor only knew name, city, job and studies). `people_memory.py` now saves partner, parents, siblings, children, grandparents, aunts and uncles, cousins, friends, roommates and pets from plain first-person statements, tolerant of fast typing ("my boyfriends name is ashmit"). Not saved: negated, hypothetical, quoted, questioning or second-hand ("she said...") phrasings, adjectives ("my boyfriend is tired"), and other people's relatives ("his boyfriend is..."). A new partner or parent name replaces the old one (like a name correction); siblings, children, friends and pets accumulate. Everything the person told Bubbles (`source = explicit_user_statement`) now always reaches the model, not only when the next message shares a keyword. Two new routes answer without a model or a consent question: `remembered` (a short message that only tells a fact gets a warm confirmation) and `recall` ("what's my boyfriend's name?", "do you remember my name?" is answered from saved facts, and a missing fact is admitted, never invented). The voice block gained REMEMBERING and best-friend rules, inside the same 450-word budget.
- Why: a girlfriend told Bubbles her boyfriend's name and it did not remember. Three causes: no pattern, keyword-gated retrieval, nothing that checks back. This is free (plain text rules, no model), instant, and the saved text is the person's own words.
- Rules kept: facts are owner-scoped rows in `memory_items` (wiped by Delete my data); only first-person plain statements; relation and name only, no health data about third parties; never claim to remember what is not saved; `recall` and `remembered` are deterministic routes after the safety, correction and daily-log routes and never right after a safety reply.
- Where: `backend/people_memory.py`, `memory_manager.py`, `memory_retrieval.py`, `chat_pipeline.py` (route_turn), `main.py` (`_recall_text`), `response_formatter.py`, `ops_telemetry.py`; tests `tests/test_people_memory.py`, `test_production_contracts.py`.

## 4. Open items

- Confirm the `/body` credit states the Z-Anatomy (CC BY-SA 4.0) and BodyParts3D (CC BY-SA 2.1 JP) licences.
- Clinician sign-off for `clinical_constants.py` before removing the "pending review" banner.
- Decide which further Figma ideas to build (see the Figma entry: only copy lines and the cue motion are in so far).
- Owner to fix `~/.claude/settings.json` model aliases only when wanting the free router back (currently reset to defaults).
