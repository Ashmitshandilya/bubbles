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
