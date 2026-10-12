# Bubbles for Android

The Android app is the existing Bubbles web app (`frontend/`) packaged with [Capacitor 8](https://capacitorjs.com).
It is not a separate product: same code, same FastAPI backend, same Supabase project, same accounts and user IDs.

| | |
|---|---|
| Application ID | `in.heybubbles.app` (permanent: Android only updates an app with the same ID and signing key) |
| App name | Bubbles |
| Min / target Android | 7.0 (API 24) / Android 16 (API 36) |
| Backend | `https://bubbles-dk3v.onrender.com` (the API the live website uses) |
| Supabase | the website's project (`ryfwkdnbhwhkpuiaegyo`), publishable key only |
| Download page | `https://heybubbles.in/android` → APK at `https://heybubbles.in/android/bubbles.apk` |

## How it works

- **One codebase.** `NEXT_PUBLIC_BUBBLES_NATIVE=1` makes `next.config.ts` produce a static export (`output: "export"`)
  that Capacitor bundles into the APK. The website build never sets the flag, so it is unchanged. Native-only code is
  gated by `isNativeApp` (`frontend/lib/native.ts`), a build-time constant, so the web bundle never loads Capacitor.
- **Same origin as the website.** Capacitor serves the bundled files as `https://heybubbles.in`
  (`server.hostname` in `frontend/capacitor.config.ts`). The production API therefore sees the same `Origin` as the
  website and its existing CORS allow-list applies; no backend change was needed. Requests to `heybubbles.in` are
  answered from the APK's own files and never leave the phone; links to any other site open in the system browser.
- **No duplicated logic.** The app calls the same API through the same `fetchBubbles` helper (timeouts, retries,
  offline banner). The deterministic safety check, RAG and the $0-AI policy run on the backend exactly as for the web.
- **Sign-in.** Email + password and sign-up use the same Supabase Auth. The magic-link option is hidden in the app
  because its email link would open the website in the browser instead of the app. Users without a password (they
  only ever used email links) tap **"Forgot or never set a password?"** on the sign-in screen, or **Settings → Set or
  change password** on the website, and choose one on `/password`. The session is kept in the WebView's app-private
  storage and refreshed when the app returns to the foreground.
- **Root screen.** The APK opens `/dashboard` (signed-out users are sent to `/login` by the existing guards) instead
  of the marketing landing page (`app/NativeEntry.tsx`). Capacitor answers any extensionless path with the root
  document, so a full page load at another path bounces through `/?to=<path>` and is routed client-side.
- **Native glue** (`components/NativeBridge.tsx`): Android back button (closes open sheets/dialogs, then goes back,
  then backgrounds the app on the first screen), splash hand-off (the splash auto-hides after 1 s; holding the first
  frame until JS was ready made slow devices report "app not responding"), `window.print()` → Android print dialog
  (`PrintPlugin.java`, offers "Save as PDF"), session refresh on resume. The data export (Profile → Your data) is
  written to the app-private cache and handed to the share sheet.
- **System bars / keyboard.** `SystemBars.insetsHandling = "native"` keeps the web view between the status bar,
  navigation bar and keyboard, so the existing mobile layout is used as-is.

## Security and privacy

- Only public values ship in the APK: the API URL, the Supabase URL and the publishable key. The release script
  fails the build if any value from `backend/.env` that looks like a key/secret/token appears in the bundle, or if the
  Supabase key is a secret/service-role key.
- `allowBackup="false"` plus `data_extraction_rules.xml`: the session and cached health data are excluded from cloud
  backup and device-to-device transfer.
- No cleartext HTTP, no mixed content, WebView debugging off, Capacitor logging off, release build not debuggable.
- Only the `INTERNET` permission. No deep links / intent filters besides the launcher (no link-hijack surface).
- The file provider exposes only the app's cache directory (used for the data-export share).
- All data access goes through the backend with the user's bearer token, so RLS and owner scoping are identical to
  the website.

## Building a release

Prerequisites (already installed on the build PC): JDK 21 at `%USERPROFILE%\.bubbles-toolchain\jdk21`, Android SDK at
`%LOCALAPPDATA%\Android\Sdk` (platform 36, build-tools 36), and the release keystore (below). Override with
`JAVA_HOME`, `ANDROID_HOME`, `BUBBLES_SIGNING_PROPERTIES` or `BUBBLES_ANDROID_API_URL`.

```powershell
cd frontend
npm ci
npm run android:release
```

`npm run android:release -- --no-publish` builds and verifies without touching `public/android` (for device tests).
`scripts/build-android.mjs` then:

1. checks the production API `/health`, the Supabase URL/key, and that the API URL is https;
2. static-exports the app into `out/` and removes the previous APK from the export (the build uses `.next`, so stop
   `next dev` first);
3. scans the export for server secrets;
4. runs `npx cap sync android` and `gradlew assembleRelease`;
5. verifies the APK signature (v2), package ID, version and that it is not debuggable; refuses a changed signing key
   or a versionCode that is not higher than the published one;
6. copies the APK to `frontend/public/android/bubbles.apk` and rewrites `frontend/public/android/latest.json`
   (version, date, size, SHA-256, signing-certificate fingerprint), which the `/android` page renders.

Then deploy the website as usual; the APK is served from `public/`.

## Signing (keep this safe)

- Keystore: `%USERPROFILE%\.bubbles-signing\bubbles-release.jks` (alias `bubbles`, RSA 4096, valid until 2054).
- Passwords: `%USERPROFILE%\.bubbles-signing\keystore.properties` (read by `android/app/build.gradle`).
- Certificate SHA-256: `FB:70:A3:F3:FE:DF:FF:A9:4B:65:15:C1:79:5F:E7:9F:18:AD:8D:5F:93:13:BE:99:B6:D8:8D:CC:21:C2:06:56`
- **Back up both files to two safe places (e.g. a password manager and an offline drive).** If the keystore is lost,
  no update can ever be installed over the existing app; every user would have to uninstall and reinstall.
- Never commit them (`.gitignore` blocks `*.jks`, `*.keystore`, `keystore.properties`).

## Releasing an update

1. Bump `versionCode` (must increase) and `versionName` in `frontend/android/app/build.gradle`.
2. `npm run android:release` (same machine/keystore).
3. Deploy the website. Users download from `/android` and install over the existing app — no uninstall, and their
   data stays because it lives in their Bubbles account. Android rejects an "update" signed by any other key.

Web-only changes reach the app only through a new APK, because the APK bundles the frontend. The backend can change
at any time, so keep API changes backward compatible with the last published app version.
