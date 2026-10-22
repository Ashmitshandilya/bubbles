# Bubbles native (Android, Kotlin + Jetpack Compose)

The real Android app. It replaces the Capacitor wrapper in `frontend/android` (same `applicationId` `in.heybubbles.app` and the same
release key, so it updates the wrapper in place). It is a client of the existing FastAPI: the server still owns safety triage,
consent, memory, associations and every estimate. See `PLAN.md` for the design and what is left.

## What is in it (3.0.0)
Sign-in, first-run setup (driven by the server's question bank), Today, Talk (chat with the safety result and the consent card),
Track (8 trackers: sleep, mood, water, food, activity, weight, symptoms, vitals), Cycle (drawn ring, predictions, log a period),
Patterns, Care (visit prep, six record types, share summary), Community (feed, compose, comments, reactions, report/block/delete,
crisis support), Reminders (phone push through Firebase), Your choices (consent switches, Delete my data), light and dark themes.
Fitness opens on the website (see "Not built yet").

## Build and test
Needs JDK 21 and the Android SDK (platform 36). On this PC: `~/.bubbles-toolchain/jdk21` and `%LOCALAPPDATA%\Android\Sdk`.

```
cd native
./gradlew testDebugUnitTest          # unit tests (pure logic and JSON models)
./gradlew assembleDebug              # debug app (applicationId in.heybubbles.app.debug)
./gradlew assembleQa                 # the release code, minified by R8, with demo sign-in and the debug key
./gradlew assembleRelease bundleRelease   # signed APK and the Play Store bundle (AAB)
```

Public build values are passed as Gradle properties, never committed: `-PBUBBLES_API_URL`, `-PBUBBLES_SUPABASE_URL`,
`-PBUBBLES_SUPABASE_KEY` (the publishable key only). Release signing is read from `~/.bubbles-signing/keystore.properties`
(or `BUBBLES_SIGNING_PROPERTIES`), the same file the wrapper uses.

## Try it without an account
`debug` and `qa` builds show "Use demo data". Run the preview server (`BUBBLES_PREVIEW=1 python backend/preview_server.py`, a fake
in-memory database) and build with `-PBUBBLES_API_URL=http://10.0.2.2:8001` so the emulator reaches it.
`COMMUNITY_ALIAS_SECRET=...` turns Community on in the preview; `FIREBASE_SERVICE_ACCOUNT_JSON=...` makes the server report phone
notifications as available.

## Firebase (phone reminders)
Built in only when `native/app/google-services.json` exists (gitignored, like the signing key). For `debug` and `qa` builds put copies
with the package renamed under `app/src/debug/` and `app/src/qa/`. Without the file the app builds and phone reminders are off, so CI
and a fresh clone still work. See `docs/FIREBASE.md`.

## Rules the code keeps
- No health logic is copied from the server. Missing data is shown as a gap, never as healthy or zero.
- Every change to consent goes through the server's endpoints, after the server accepts it (the switch shows what is on record).
- Nothing about the person is put in a notification, a log or a crash report. Tokens live in encrypted storage and are excluded
  from backup. Sign-out takes this phone off the server's reminder list first.
- No Firebase Analytics, no ads, no tracking.

## Not built yet
Fitness (body setup with its eating-disorder screening, calorie floors, plans, transform) opens on the website: it must be ported
with every safeguard, not approximated. Partner sharing, the body map (3D), offline logging with sync, the first-run tour, and
in-app account deletion (the server only has "delete my data" today; Google Play requires account deletion for apps with sign-up).
