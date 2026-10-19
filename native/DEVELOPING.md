# Developing the Bubbles Android app (native/)

Everything a developer needs to pick this app up cold. Read `README.md` (what it is), `PLAN.md` (the plan), `PLAY_LISTING.md` (store submission), and the
repo's `DECISIONS.md` (standing rules). This file is the working manual. Last updated 2026-10-20.

## 1. What it is
Kotlin + Jetpack Compose app, `applicationId in.heybubbles.app`, v3.0.0 (versionCode 10), never published. A thin client of the existing FastAPI
(`backend/`). **The server owns every rule**: safety triage, consent, calorie floors, the eating-disorder screening, partner-sharing limits, memory.
The app asks, sends, and shows what the server answers. Never copy a rule into the app that the server already enforces.

## 2. Layout (`app/src/main/java/in/heybubbles/app/`)
| Path | What it holds |
|---|---|
| `BubblesApp.kt` | Builds `Session`, `Api`, `Repo` (with the `OfflineQueue`) once. |
| `data/Api.kt` | The only network client (OkHttp). Typed calls for older features, plus `getJson` / `sendJson` for features whose JSON the server owns (Fitness, Partner, Body map). Server `detail` text becomes the `ApiError` message; `friendly()` turns failures into plain words. |
| `data/Session.kt` | Tokens in EncryptedSharedPreferences. `epoch` bumps on sign-out so view models restart for the next person. |
| `data/Repo.kt` | Tracker entries shared by Today/Track; `save()` (offline-aware), `sync()`, `pending`, section flags (Cycle, Care, Fitness, body map, Community). `clear()` also empties the offline queue. |
| `data/OfflineQueue.kt` | Encrypted queue of tracker entries made offline. `QueueRules` (pure): only requests that provably never reached the server are queued. |
| `data/Js.kt` | Forgiving JSON readers (`str`, `num`, `int`, `bool`, `obj`, `objs`, `strs`, `arr`) and `fmtNum` (a gap prints as a dash, never 0). |
| `data/FitnessCalc.kt`, `PartnerCalc.kt`, `OrganStatus.kt` | Pure rules with unit tests (unit conversion, code formatting, status words and "never calmer than the safety message"). |
| `data/Trackers.kt`, `Onboarding.kt`, `Cycle.kt`, `Community.kt`, `Models.kt` | Older feature models. |
| `ui/AppRoot.kt` | Auth gate, onboarding gate, `Home` (tabs, sections, tour overlay, reminder deep links, network callback for sync). |
| `ui/screens/*` | Today, Talk, Track, Cycle, Patterns, Care, Community, Me, Choices, Reminders, Login, Onboarding, Partner, Body, TourOverlay. |
| `ui/screens/fitness/*` | `FitnessScreen` (hub + routing), `FitnessKit` (`rememberLoad`, `LoadGate`, `rememberSender`, page scaffold, clinical note), Body setup, Food log, Diet, Workouts, Transform, Progress. |
| `ui/components/*` | `Kit` (cards, pills, titles), `Forms` (fields, chips, tags, checkbox), `Charts`, `Mascot`. |
| `push/*` | Firebase Cloud Messaging reminders (consent-gated server side). |
| `assets/body/` | The 3D body page: `index.html`, `body.js`, `body.glb` (same model as the website), vendored three.js r186 (+ loaders). No network. |

## 3. Patterns to follow
- **Reading a server document**: `val loader = rememberLoad(api, "/path")` then `LoadGate(loader) { json -> ... }`. Failure shows the friendly line and a retry.
- **Writing**: `val send = rememberSender(api)`; `send.send("POST", "/path", body) { reply -> ... }`; show `send.error.value`. Success is claimed only after the server accepts.
- **Never show raw server text or stack traces except the server's own plain-language `detail`** (it is written for people).
- **Missing data is a gap**: use `fmtNum(null)` (dash), "Not logged", "No data yet". Never 0, never "healthy".
- **Copy**: plain, calm, no em-dashes in visible text, no diagnosis or dosing words. Tests (`TourTest`) hold some of this.
- **Safety wording from the server is shown in full, first**, and a safety text forces "Talk to a doctor" on the body map.
- **Targets 48dp**, every control has a label, no colour-only meaning.
- **Consent first**: partner sharing, AI chat, reminders and community each check the server's consent state; when off, say so and link to Me, Your choices.
- **JSON shapes are the server's**: check the real response before writing a parser (a Python script hitting the preview API found that `grocery.aisles` is an object keyed by aisle, not a list, and that `alternative` is a code, not text).

## 4. Build, run, test
Needs JDK 21 and the Android SDK (platform 36). On this PC: `JAVA_HOME=~/.bubbles-toolchain/jdk21`, SDK in `%LOCALAPPDATA%\Android\Sdk`.
```
cd native
./gradlew.bat assembleDebug testDebugUnitTest                      # compile + 40-odd unit tests
./gradlew.bat assembleDebug -PBUBBLES_API_URL=http://10.0.2.2:8001 # for the emulator + preview server
./gradlew.bat assembleRelease bundleRelease \
   -PBUBBLES_SUPABASE_URL=... -PBUBBLES_SUPABASE_KEY=...           # signed APK + AAB (public key only)
```
Release signing: `~/.bubbles-signing/keystore.properties` (same key as the wrapper). Firebase: `google-services.json` is gitignored (`app/`, `app/src/debug/`, `app/src/qa/`);
without it the app builds and phone reminders are off. Public values come from `D:\coco\bubbles-android\frontend\.env.local`.

**Unit tests** (`app/src/test`): Models, Trackers, OnboardingFlow, Tour, FitnessCalc, TransformGate (only `allowed` / `allowed_with_cautions` may offer Start),
PartnerCalc, OfflineQueue (what may be queued; what is dropped), OrganStatus.

**Preview server** (fake in-memory database, real API): from `backend/`, `BUBBLES_PREVIEW=1 python preview_server.py` (port 8001, token `preview`).
Its seed is out of date with the onboarding bank, so finish the demo user's setup with `PUT /onboarding/answers`
(`body, language, birth_date, preferred_name, main_goal, conditions_any, sleep_pattern, stress_level, periods`) then `POST /onboarding/complete`.

**Emulator**: AVD `bubbles_api35`, headless: `emulator -avd bubbles_api35 -no-window -gpu swiftshader_indirect -no-audio`. Stop Gradle/java first when memory is tight;
tap "Wait" on a System UI ANR dialog. Install `app-debug.apk` (package `in.heybubbles.app.debug`), then "Use demo data". Drive it with `adb shell input tap/swipe`
and `adb exec-out screencap -p`. Offline test: `adb shell svc wifi disable` and `svc data disable`, log an entry, re-enable, wait for the sync, check the server has one copy.
The emulator's software GPU cannot judge the 3D body map; test that on a real phone.

**Contract check habit**: before writing a screen, call each endpoint it needs against the preview server (a 30-line Python script) and read the real field names.

## 5. Offline logging (how it works, so nobody breaks it)
1. `Repo.save` posts the entry. If the failure is `UnknownHost`, `ConnectException`, `NoRouteToHost`, or a connect-time `SocketTimeout` ("failed to connect"), the entry is queued with `date = now` (the server honours `date` on `/health/<slug>`).
2. Read timeouts and dropped answers are **not** queued: the server may have saved them, and the server has no idempotency key on health entries, so queueing could log twice.
3. `Repo.sync()` runs at app open, on every network-available callback, and after a successful save. It stops at the first transient failure and drops entries the server refuses for good (4xx except 401/408/429).
4. Sign-out clears the queue (privacy on a shared phone) after a confirmation that names how many entries would be lost.

## 6. Body map notes
`BodyScreen` hosts `assets/body/index.html` in a WebView through `WebViewAssetLoader` (`https://appassets.androidplatform.net/assets/...`), JavaScript on, file/content access off,
`blockNetworkLoads = true`, navigation blocked. Bridge `Bubbles` (page to app): `onReady`, `onPick(organId)`, `onError`. App to page: `bodyApi.setOrgans([{id,status}])`, `select(id)`,
`setView("front"|"side"|"back")`, `setAnatomy("female"|...)`. Organs bump by scaling a pivot group (never the mesh: the quantized model keeps its size in node transforms).
A female profile drops the male groin patch from the skin shell (same maths as `frontend/components/anatomy/groin.ts`). The model is ~400k triangles: phones get no antialiasing and a 1.5 pixel ratio,
and the person can switch 3D off (remembered). **Real-phone speed is unmeasured.** Console messages from the page go to logcat tag `BodyMap`.

## 7. Server pieces added for the app
- `DELETE /me/account?confirm=true` (`backend/data_rights.py`): erases documents (holds and community posts included), then the Supabase sign-in; tables keyed by `user_id` cascade from `auth.users`. 503 if either step fails, safe to retry.
- Admin ops routes answer 404 for non-admins (PR #55).

## 8. Gotchas we already paid for
- The shell tool breaks on heredocs containing backticks or quotes: write files with an editor tool, patch with small Python scripts.
- Kotlin: `ExperimentalLayoutApi` lives in `androidx.compose.foundation.layout`. Two private `JsonObject.str/num` helpers in `Onboarding.kt` clashed with `Js.kt` and were removed.
- `rememberLoad` / `rememberSender` are composable and must not be called conditionally in a way that changes call order across recompositions (calling them inside `if` branches that stay stable per screen is fine).
- A WebView page can be blocked silently from posting to `localhost` (Private Network Access); don't plan on that for tooling.
- Gradle and the emulator together can starve memory: stop `java`/`gradle` before starting the AVD.

## 9. Status and what is next
Built: sign-in, first-run setup, tour, Today, Talk, Track (8 trackers, offline), Cycle, Patterns, Care, Community, reminders, Your choices, Delete my data, Delete my account, Fitness (food log, diet, workouts, strict transformation with screening, progress, body setup), Partner sharing, 3D body map, light/dark.
Not done: real-phone test (especially body-map speed), release rebuild copied to `D:\coco\release-native-3.0.0`, `DECISIONS.md` entries for the new features (add in PR #52), Play Console steps (`PLAY_LISTING.md`), Compose UI tests for the main flows, TalkBack pass, a Fitness unit test for the response parsers if they grow.
Open ideas: Room instead of the encrypted JSON queue if offline needs to cover more than tracker entries; show queued entries in the history list; a measured performance budget for the body map; native-side e2e in CI against the preview server.
