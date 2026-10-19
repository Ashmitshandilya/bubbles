# Google Play listing: Bubbles 3.0.0 (in.heybubbles.app)

Everything the Play Console asks for, written from what the app really does (code in `native/`, privacy notice at https://heybubbles.in/privacy).
Items marked **OWNER** need a person's decision or an account only the owner has. Items marked **VERIFY** are my best reading; check them
against the privacy notice and your legal advice before you submit. Nothing here has been submitted.

## 1. Store listing text

**App name** (30 max): `Bubbles: your health companion`

**Short description** (80 max): `Log sleep, mood, cycle and more. A kind companion that helps you see your own patterns.`

**Full description** (4000 max):

> Bubbles is a calm, kind health companion. Tell it how you are in your own words, log the things that matter, and see what your own entries say, with no judgement and no pressure.
>
> WHAT YOU CAN DO
> • Talk: chat in English, Hinglish or Hindi. Bubbles keeps replies short and gentle, and checks for urgent signs before anything else.
> • Track: sleep, mood, water, food, activity, weight, symptoms and vitals. One tap each. Logging works offline and sends itself when you are back online.
> • Cycle: where you are in your cycle, and what is estimated, never promised.
> • Patterns: links between what you log, shown honestly. An association is not a cause, and gaps are shown as gaps.
> • Fitness: say what you ate in your own words and get an estimate you confirm, a week of meals, gentle workouts after a short safety check, and progress. A strict plan is offered only after a careful screening, and Bubbles will say no when it is not the right fit.
> • Body map: see your logged entries on a 3D body. Tap a part to read about it.
> • Care: prepare questions and a summary for a doctor visit.
> • Partner sharing: choose exactly what one trusted person can see, and stop at any time.
> • Community: ask or share, kindly.
> • Reminders: gentle nudges on your phone, only if you turn them on.
>
> YOUR DATA IS YOURS
> • Nothing is shared unless you say so. Every choice starts off, and you can change it in Me, Your choices.
> • Delete my data and Delete my account are inside the app.
> • Missing data is never treated as healthy, and Bubbles does not diagnose or give doses.
>
> Bubbles is not a medical device and does not replace a doctor. In an emergency in India call 112. For emotional support, Tele-MANAS is free on 14416.

**Category**: Health & Fitness. **Tags**: health tracking, cycle tracker, sleep, wellbeing.
**Contact email**: hello@heybubbles.in. **Website**: https://heybubbles.in. **Privacy policy URL**: https://heybubbles.in/privacy

## 2. Graphics

| Asset | Size | Status |
|---|---|---|
| App icon | 512 x 512 PNG | **OWNER**: export from the adaptive icon (`res/mipmap-xxxhdpi/ic_launcher.png` is 192 px; make a 512 px version from the brand artwork) |
| Feature graphic | 1024 x 500 | **OWNER**: not made yet |
| Phone screenshots (2 to 8) | 1080 x 2400 | Done: `D:\coco\play-assets\01-today.png` to `05-me.png` (emulator, demo data) |
| Tablet screenshots | optional | not needed to publish |

## 3. App content declarations

- **Target audience**: 18 and over (the app asks for date of birth in setup and does not continue for under 18). Not designed for children.
- **Ads**: none. **In-app purchases**: none. **Account required**: yes (email and password).
- **Health apps declaration**: select "Health and fitness" and "Medical" features are not claimed; the app is wellness tracking, not a medical device. **VERIFY** the exact wording Play shows for "health features" and tick only what applies (tracking, fitness, mental wellbeing, reproductive health, medication tracking).
- **Government / financial / news**: no.
- **Content rating (IARC questionnaire)**: expected rating Everyone / PEGI 3. Answer no to violence, sexual content, profanity, gambling and controlled substances. Mention that the app has user-generated content (Community, moderated) and discusses health topics. **VERIFY** the Community moderation answer (reporting and blocking exist; see `docs` for moderation).
- **Permissions**: `INTERNET` (everything), `POST_NOTIFICATIONS` (reminders, asked only when you turn reminders on). No location, contacts, camera, microphone or storage permissions.
- **Backups**: `allowBackup=false` (health data is not copied to Google backup).

## 4. Data safety form

Data is encrypted in transit (HTTPS) and the account/health data is stored in a managed database. **Users can request deletion**: yes, in the app (Me, Your choices, Delete my account) and by email.

| Data type | Collected | Shared | Purpose | Optional |
|---|---|---|---|---|
| Name (first name given in setup) | Yes | No | App functionality, personalisation | Yes |
| Email address | Yes | No | Account management | No |
| Health info (sleep, mood, symptoms, vitals, medications, labs) | Yes | See note | App functionality | Yes |
| Fitness info (activity, food, weight, workouts) | Yes | See note | App functionality | Yes |
| Reproductive health (cycle, period dates) | Yes | See note | App functionality | Yes |
| Messages (in-app chat and Community posts) | Yes | See note | App functionality | Yes |
| Device or other IDs (push token for reminders) | Yes | No | App functionality | Yes (off by default) |
| Crash logs / diagnostics | **VERIFY**: the native app does not include Firebase Crashlytics; if you add it, declare it | | | |

**Note on sharing**: when a person turns on the "AI chat" choice, the text of a chat message and a short summary of recent entries go to an
AI provider from an approved free-tier list (Gemini, Groq, NVIDIA, Mistral), only as much as needed, never when the safety check finds an urgent
sign. Play treats sending data to another company for processing on your behalf as "not shared" only if the provider acts as your service
provider under terms that forbid other use. **VERIFY** each provider's free-tier terms, then answer "shared: yes, with service providers" if
any of them may keep or train on the text. Partner sharing sends summaries only to the one person the owner picks.

**Does the app follow the Families policy / is it for children?** No.

## 5. Release

- **Package**: `in.heybubbles.app`, signed with the same upload key as the website APK (certificate FB:70:A3...), so Play App Signing can adopt it. **OWNER**: enrol in Play App Signing and upload the key when Console asks.
- **Bundle**: `bundleRelease` makes the AAB. Version 3.0.0 (versionCode 10).
- **Testing track**: a new personal developer account needs a closed test with **12 testers for 14 days** before production. **OWNER**: collect 12 Gmail addresses, create the closed test, share the opt-in link.
- **Release notes (first release)**: `A new, native Bubbles for Android: faster, works offline for logging, with Fitness, Partner sharing, the 3D body map, and Delete my account built in.`
- **Do not replace the website download (2.1.0) until** the 3.0.0 build has been on a real phone and the closed test has run.

## 6. Pre-submission checklist

- [ ] 512 px icon and 1024 x 500 feature graphic made
- [ ] Data safety form answered (section 4) and the **VERIFY** rows settled
- [ ] Content rating questionnaire done
- [ ] Privacy policy URL live and mentions the Android app and in-app deletion (done on the site once PR #52's privacy edit is merged)
- [ ] Tested on a real phone: sign-in, setup, offline log then sync, Fitness (including the strict-plan screening), Partner sharing, body map speed, Delete my account on a throwaway account
- [ ] Closed test with 12 testers for 14 days
