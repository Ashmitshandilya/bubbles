# Bubbles native (Kotlin + Jetpack Compose)

Replaces the Capacitor wrapper (`frontend/android`) with a real Android app. Same backend, same Supabase accounts, same
consent and safety rules. The website stays as it is.

## Identity and release
- `applicationId` `in.heybubbles.app`, same release keystore as the wrapper, so users update in place. Debug builds use
  the `.debug` suffix so they sit next to the installed app. Version 3.0.0 (versionCode 10) for the first release.
- Play Store: build an AAB (`bundleRelease`). Enrol in Play App Signing and upload with the existing key. Needs the
  privacy policy URL, the data-safety form and the 12-tester closed test for new personal accounts.

## Stack
- Kotlin 2.x, Compose Material 3 (our own Bubbles theme on top), Navigation-Compose, ViewModel + StateFlow.
- OkHttp + kotlinx.serialization (no heavy framework). Supabase Auth over its REST API (password sign-in, refresh).
- Tokens in EncryptedSharedPreferences. Room later for offline logging with a sync queue.
- FCM push (project `bubbles-c67cb`), the same server schedule and consent gate as today.
- One module `app` to start; split into `core`/`feature` modules only when build time asks for it.

## Data: one source of truth
The app is a client of the existing FastAPI. No new tables, no logic copied that the server owns. It calls the same
endpoints as `useApi().fetchBubbles`: `/chat`, `/chat/latest`, `/chat/conversations/{id}/messages`, `/chat/feedback`,
`/health/*`, `/onboarding/*`, `/experience`, `/consents*`, `/me/consent`, `/intelligence/*`, `/insights/*`,
`/wellness/associations`, `/cycle`, `/fitness`, `/community/*`, `/doctor/*`, `/privacy/*`. Safety triage, memory,
associations and consent stay on the server, so the phone and the website always agree.
Rules carried over: missing data is a gap and never "healthy"; no diagnosis or dosing language; consent ask before any
outside model; Delete my data wipes everything (including Community); crisis copy names India lines (112, Tele-MANAS 14416).

## Look and feel: an app, not a website
Same brand (pink / grape / sun / mint tokens from `DESIGN.md`, Fredoka headings, Nunito body), different grammar:
- Bottom navigation bar with four places (Today, Talk, Track, Me) plus a "Patterns" and "Care" entry reached from Today,
  not seven tabs and not a sticky web header. Predictive back, edge-to-edge, large top app bars that collapse on scroll.
- Talk is the home of the app: a bubble-shaped composer pinned to the bottom, quick chips above the keyboard, replies
  stream in, haptic ticks on send and confirm. Logging by chat is one thumb away from every screen.
- Cards use big radii, soft tinted fills (the `tint-*` tokens) and one accent per card. Charts and the cycle ring are
  drawn natively on Canvas. Motion: spring-based, short, respects "remove animations".
- Material You is not used for colour (Bubbles keeps its own palette) but light / dark and font scaling are honoured.
- Accessibility from the start: 48dp targets, TalkBack labels, contrast checked against the tokens, no colour-only meaning.

## Phases
1. **Slice 1 (first run on a device):** theme, navigation shell, sign-in (password), session refresh, Today (companion
   daily + week), Talk (history, send, safety result, feedback), Settings with consent list and Delete my data.
2. Onboarding (server bank), trackers (sleep, mood, water, food, weight, vitals, symptoms), edit/delete entries.
3. Patterns / Insights, Cycle, Fitness, Care (doctor summary, share), Partner sharing.
4. Push (FCM), reminders, Community, offline logging with sync.
5. Body map (3D, Filament) and polish. Release: AAB, Play listing, closed test.

## Testing
Unit tests for mappers and view models, Compose UI tests for the main flows, API contract tests against the preview
server (`backend/preview_server.py`, token `preview`), TalkBack pass, and a run on the emulator before every merge.

## Decisions still open
- Bottom bar contents (above is the proposal). Font files: bundle Fredoka and Nunito (OFL) in the app.
- Whether the Play build keeps the wrapper's APK download page or hides it once the native app is live.
