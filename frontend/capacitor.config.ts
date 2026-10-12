import type { CapacitorConfig } from "@capacitor/cli";

// Android app shell for the existing Bubbles web app. Build it with `npm run android:release`
// (scripts/build-android.mjs), never by hand: that script sets the production API and the native flag.
const config: CapacitorConfig = {
  // Stable forever: Android only installs an update over an app with the same id and signing key.
  appId: "in.heybubbles.app",
  appName: "Bubbles",
  webDir: "out",
  backgroundColor: "#FFF6FA",
  loggingBehavior: "none",
  server: {
    androidScheme: "https",
    // The bundled files are served as https://heybubbles.in, so the production API sees the same Origin as the
    // website and its existing CORS allow-list applies unchanged. Requests to this host are answered from the
    // APK's own files and never leave the device; any other host opens in the system browser.
    hostname: "heybubbles.in",
  },
  android: {
    allowMixedContent: false,
    webContentsDebuggingEnabled: false,
  },
  plugins: {
    // "native" keeps the web view between the status bar, navigation bar and keyboard (the site does not use
    // viewport-fit=cover), so the existing mobile layout needs no safe-area changes. LIGHT = dark icons.
    SystemBars: { insetsHandling: "native", style: "LIGHT" },
    // Auto-hides: holding the first frame until JS is ready made slow devices report "app not responding".
    // NativeEntry shows an on-brand "Opening Bubbles" screen underneath, and NativeBridge may hide it earlier.
    SplashScreen: { launchAutoHide: true, launchShowDuration: 1000, backgroundColor: "#FFF6FA", showSpinner: false },
  },
};

export default config;
