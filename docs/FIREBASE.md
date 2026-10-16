# Firebase in Bubbles

Firebase adds three things to the **Android app** (`docs/ANDROID.md`). Supabase, Render and Vercel stay as they are; nothing on
the website changes except one Settings switch that only appears inside the app.

| Feature | What it does | Where |
|---|---|---|
| **Cloud Messaging (FCM)** | Phone reminders (water, medicine check-in, wind-down) while the app is closed | `backend/push_fcm.py`, `frontend/lib/firebase-native.ts`, Settings → Reminders → **On this phone** |
| **Crashlytics** | Reports native crashes of the Android app | `BubblesFirebasePlugin.java`, Settings → This device → **Send crash reports** |
| **App Distribution** | Sends a new APK to testers before it goes on the website | `npm run android:release -- --distribute` |

All three cost nothing on the free **Spark** plan. Everything is **dormant until you add the two files below**: without them the
APK builds and works exactly as before, the switches stay hidden and the server never contacts Google.

## Privacy rules (do not break)

- **Off until the person turns it on.** No notification token exists before someone turns on *On this phone*. Crash reports
  are off by default (`firebase_crashlytics_collection_enabled=false`), and reports stored while they were off are deleted.
- **Two yeses for phone reminders.** The server sends only when the reminder switch is on **and** the consent log has a
  current yes for `push_notifications` (`consent_ledger.py`; the switch records it, Privacy choices can withdraw it).
- **Plain text only.** Notifications use the fixed templates in `notifications.py` (`sanitise`), never what someone logged.
  The message data carries only the reminder kind, and the notification is marked private on the lock screen.
- **No Google Analytics, ever** (the standing "no analytics" rule in `DECISIONS.md`). Do not add `firebase-analytics`; the
  manifest switches Analytics collection off as a second guard.
- **Nothing personal in crash reports.** No user id, no custom keys, and web (JavaScript) errors are never forwarded.
- **One owner per phone.** Registering a token removes it from every other account; signing out deletes the token on the phone.
- **Not a safety system.** Urgent answers never depend on a notification.

## One-time setup (you, about 15 minutes)

1. **Firebase project.** In the [Firebase console](https://console.firebase.google.com) open your project (or create one;
   when it asks about Google Analytics, choose **not** to enable it).
2. **Android app.** Project settings → General → *Add app* → Android. Package name **`in.heybubbles.app`** (it must match
   exactly). Add the release certificate SHA-256 from `docs/ANDROID.md`
   (`FB:70:A3:F3:FE:DF:FF:A9:4B:65:15:C1:79:5F:E7:9F:18:AD:8D:5F:93:13:BE:99:B6:D8:8D:CC:21:C2:06:56`).
   Download **`google-services.json`** and put it at `frontend/android/app/google-services.json` on the build PC. It is
   gitignored on purpose; keep a copy with the signing keystore. The release script refuses a file for another package.
3. **Server key.** Project settings → Service accounts → *Generate new private key*. On Render (service `bubbles`) add
   `FIREBASE_SERVICE_ACCOUNT_JSON` and paste the whole file (or its base64). **This is a secret**: never put it in the
   frontend, the APK or git. The release script fails if it ever appears in the app bundle.
   Optional: `PUSH_SWEEP_SECONDS` (default 300) and `BUBBLES_PUSH_SWEEP=0` to stop the background check.
4. **Crashlytics.** Firebase console → Crashlytics → *Enable*. (The first report only shows after someone turns crash
   reports on and the app crashes once.)
5. **Testers (optional).** App Distribution → *Get started* → Testers & Groups → create a group with alias **`testers`** and
   add tester emails. On the build PC run `npx firebase-tools login` once.
6. **Build.** `cd frontend`, `npm ci`, bump `versionCode`/`versionName` in `android/app/build.gradle`, then
   `npm run android:release` (website download) and/or `npm run android:release -- --no-publish --distribute` (testers
   only). The script prints `Firebase: project …` when the file was picked up.

Only APKs built **after** step 2 have Firebase. People on an older APK keep everything they had; they get phone reminders after
installing the new one.

## How phone reminders flow

1. In the app, Settings → Reminders → **On this phone** asks Android for notification permission (Android 13+), gets the FCM
   token and sends it to `POST /notifications/devices`. **Save** stores the switch and logs the consent.
2. The server keeps the token as a signed document (`push_device`, no schema change), at most 5 phones per person.
3. Every `PUSH_SWEEP_SECONDS` the server creates the reminders that are due for people with a phone registered (the same
   rules as in the app: types, quiet hours, daily limit, no repeats) and sends each one through FCM HTTP v1. On Render's free
   plan the API is kept awake by `.github/workflows/keep-awake.yml`; if it sleeps anyway, reminders resume when it wakes and
   FCM drops anything more than an hour old.
4. A token FCM reports as gone is deleted. Turning the switch off, signing out or *Delete all my data* removes the phone.
5. **Send a test to this phone** (once a minute at most) checks the whole path.

Reminders created by the background check are not emailed (the check has no email address); email reminders still go out
when someone opens the app.

## Versions

`frontend/android/variables.gradle` pins `firebaseBomVersion` (Crashlytics) and `firebaseMessagingVersion` (used by
`@capacitor/push-notifications`); `frontend/android/build.gradle` pins the Crashlytics Gradle plugin. Android Studio flags
newer versions; bump them together and rebuild.

## Not used (and why)

- **App Check**: its Android check (Play Integrity) needs the app to come from Google Play, and Bubbles is downloaded from
  heybubbles.in. Its web check adds Google reCAPTCHA scripts to the site. It also cannot protect Supabase directly. Revisit
  if the app moves to Google Play.
- **Google Analytics / Firebase Analytics**: breaks the no-analytics promise.
- **SQL Connect, App Hosting, Firebase Auth**: would replace Supabase and Vercel, which already work.
- **Web push on the website**: needs a service worker and VAPID keys (`notifications.send_web_push` is still a stub).
