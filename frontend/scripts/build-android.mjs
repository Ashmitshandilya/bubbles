// Builds, signs, verifies and publishes the Bubbles Android APK from this same frontend.
//
//   npm run android:release
//
// 1. Static-exports the app with the production API (NEXT_PUBLIC_BUBBLES_NATIVE=1 switches next.config.ts to
//    output: "export"; the website build is untouched).
// 2. Refuses to continue if the bundle is not pointed at https endpoints or contains a server-side secret.
// 3. Syncs Capacitor, runs Gradle assembleRelease, verifies the signature, version and signing key.
// 4. Copies the APK to public/android/bubbles.apk and rewrites public/android/latest.json (the /android page).
//
// `--no-publish` builds and verifies the signed APK but leaves public/android untouched (for device testing).
//
// Overrides: BUBBLES_ANDROID_API_URL (default: the live backend), JAVA_HOME, ANDROID_HOME, BUBBLES_SIGNING_PROPERTIES.
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { copyFileSync, existsSync, readFileSync, readdirSync, rmSync, statSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { join, resolve } from "node:path";

const root = resolve(import.meta.dirname, "..");
const androidDir = join(root, "android");
const outDir = join(root, "out");
const publicApk = join(root, "public", "android", "bubbles.apk");
const manifestPath = join(root, "public", "android", "latest.json");
const builtApk = join(androidDir, "app", "build", "outputs", "apk", "release", "app-release.apk");

const publish = !process.argv.includes("--no-publish");
const API_URL = (process.env.BUBBLES_ANDROID_API_URL || "https://bubbles-dk3v.onrender.com").replace(/\/$/, "");
const SITE_URL = "https://heybubbles.in";
const APP_ID = "in.heybubbles.app";
// Android version names for the minSdk values Capacitor has used; shown on the download page.
const ANDROID_NAMES = { 23: "6.0", 24: "7.0", 25: "7.1", 26: "8.0", 27: "8.1", 28: "9", 29: "10" };

function fail(message) {
  console.error(`\n✖ ${message}`);
  process.exit(1);
}

function run(command, args, options = {}) {
  console.log(`\n▶ ${command} ${args.join(" ")}`);
  const result = spawnSync(command, args, { stdio: options.capture ? "pipe" : "inherit", shell: true, encoding: "utf8", ...options });
  if (result.status !== 0) fail(`${command} failed${options.capture ? `:\n${result.stdout}\n${result.stderr}` : ""}`);
  return result.stdout ?? "";
}

/** KEY=VALUE pairs from the env files Next loads for a production build (later files lose to earlier ones). */
function readEnv(dir, files) {
  const env = {};
  for (const name of files) {
    const path = join(dir, name);
    if (!existsSync(path)) continue;
    for (const line of readFileSync(path, "utf8").split(/\r?\n/)) {
      const match = line.match(/^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$/);
      if (match && !(match[1] in env)) env[match[1]] = match[2].replace(/^(['"])(.*)\1$/, "$2");
    }
  }
  return env;
}

function* walk(dir) {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) yield* walk(path);
    else yield path;
  }
}

// ---- toolchain -------------------------------------------------------------------------------------------------
const javaHome = process.env.JAVA_HOME || join(homedir(), ".bubbles-toolchain", "jdk21");
const androidHome = process.env.ANDROID_HOME || process.env.ANDROID_SDK_ROOT || join(process.env.LOCALAPPDATA || "", "Android", "Sdk");
if (!existsSync(join(javaHome, "bin"))) fail(`No JDK at ${javaHome}. Install JDK 21 or set JAVA_HOME.`);
if (!existsSync(join(androidHome, "platforms"))) fail(`No Android SDK at ${androidHome}. Install it or set ANDROID_HOME.`);
const buildToolsDir = join(androidHome, "build-tools");
const buildTools = readdirSync(buildToolsDir).sort((a, b) => a.localeCompare(b, undefined, { numeric: true })).at(-1);
const tool = (name) => join(buildToolsDir, buildTools, process.platform === "win32" ? (name === "apksigner" ? "apksigner.bat" : `${name}.exe`) : name);
writeFileSync(join(androidDir, "local.properties"), `sdk.dir=${androidHome.replaceAll("\\", "/")}\n`);
const toolEnv = { ...process.env, JAVA_HOME: javaHome, ANDROID_HOME: androidHome };

// ---- production configuration ------------------------------------------------------------------------------------
const env = { ...readEnv(root, [".env.production.local", ".env.local", ".env.production", ".env"]), ...process.env };
const supabaseUrl = env.NEXT_PUBLIC_SUPABASE_URL || "";
const supabaseKey = env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY || "";
if (!/^https:\/\/[a-z0-9-]+\.supabase\.co\/?$/.test(supabaseUrl)) fail("NEXT_PUBLIC_SUPABASE_URL must be the https URL of the production Supabase project.");
if (!supabaseKey) fail("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY is not set.");
if (/^sb_secret_/.test(supabaseKey) || /service_role/.test(Buffer.from(supabaseKey.split(".")[1] || "", "base64url").toString())) {
  fail("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY is a secret/service-role key. Only the publishable (anon) key may ship in an app.");
}
if (!API_URL.startsWith("https://")) fail(`The API URL must be https (got ${API_URL}).`);

console.log(`API:      ${API_URL}\nSupabase: ${supabaseUrl}\nJDK:      ${javaHome}\nSDK:      ${androidHome} (build-tools ${buildTools})`);
const health = await fetch(`${API_URL}/health`, { signal: AbortSignal.timeout(90_000) }).then((r) => r.json()).catch((e) => fail(`API health check failed: ${e.message}`));
if (health?.status !== "healthy") fail(`API is not healthy: ${JSON.stringify(health)}`);

// ---- 1. static export ------------------------------------------------------------------------------------------
rmSync(outDir, { recursive: true, force: true });
run("npx", ["next", "build"], {
  cwd: root,
  env: {
    ...process.env,
    NEXT_PUBLIC_BUBBLES_NATIVE: "1",
    NEXT_PUBLIC_API_URL: API_URL,
    NEXT_PUBLIC_SUPABASE_URL: supabaseUrl,
    NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: supabaseKey,
    NEXT_PUBLIC_SITE_URL: SITE_URL,
    // In export mode Next treats a custom distDir as the export folder and still builds into .next, so it cannot
    // isolate this build: stop `next dev` first. The export lands in out/ (capacitor.config.ts webDir).
    NEXT_DIST_DIR: "",
  },
});
if (!existsSync(join(outDir, "index.html"))) fail("Static export produced no out/index.html.");
// public/ is copied into the export: never ship the previous APK inside the new one.
rmSync(join(outDir, "android"), { recursive: true, force: true });

// ---- 2. bundle checks ------------------------------------------------------------------------------------------
const backendEnv = readEnv(join(root, "..", "backend"), [".env"]);
const secrets = Object.entries(backendEnv).filter(([key, value]) => /KEY|SECRET|TOKEN|PASSWORD/i.test(key) && value.length >= 16);
let sawApi = false;
for (const file of walk(outDir)) {
  if (!/\.(html|js|txt|json|css)$/.test(file)) continue;
  const text = readFileSync(file, "utf8");
  if (text.includes(API_URL)) sawApi = true;
  if (/sb_secret_[A-Za-z0-9_-]{8,}/.test(text)) fail(`A Supabase secret key is in ${file}.`);
  for (const [key, value] of secrets) if (text.includes(value)) fail(`The backend secret ${key} is in ${file}.`);
}
if (!sawApi) fail(`The export does not reference ${API_URL}; NEXT_PUBLIC_API_URL was not applied.`);
console.log(`\n✔ Bundle checked: production API present, no server secrets (${secrets.length} backend values scanned).`);

// ---- 3. native build -------------------------------------------------------------------------------------------
run("npx", ["cap", "sync", "android"], { cwd: root });
rmSync(builtApk, { force: true });
run(`"${join(androidDir, process.platform === "win32" ? "gradlew.bat" : "gradlew")}"`, ["assembleRelease", "--no-daemon"], { cwd: androidDir, env: toolEnv });
if (!existsSync(builtApk)) fail("Gradle did not produce app-release.apk. Is the release keystore configured (see android/app/build.gradle)?");

const certs = run(`"${tool("apksigner")}"`, ["verify", "--verbose", "--print-certs", `"${builtApk}"`], { env: toolEnv, capture: true });
if (!/Verified using v2 scheme \(APK Signature Scheme v2\): true/.test(certs)) fail(`APK is not v2-signed:\n${certs}`);
const certSha = certs.match(/Signer #1 certificate SHA-256 digest: ([0-9a-f]+)/)?.[1];
if (!certSha) fail(`Could not read the signing certificate:\n${certs}`);
const signingCertSha256 = certSha.toUpperCase().match(/../g).join(":");

const badging = run(`"${tool("aapt2")}"`, ["dump", "badging", `"${builtApk}"`], { capture: true });
const packageName = badging.match(/package: name='([^']+)'/)?.[1];
const versionCode = Number(badging.match(/versionCode='(\d+)'/)?.[1]);
const versionName = badging.match(/versionName='([^']+)'/)?.[1];
const minSdk = Number(badging.match(/minSdkVersion:'(\d+)'/)?.[1]);
const targetSdk = Number(badging.match(/targetSdkVersion:'(\d+)'/)?.[1]);
if (packageName !== APP_ID) fail(`Package is ${packageName}, expected ${APP_ID}.`);
if (/android:debuggable/.test(badging) || /application-debuggable/.test(badging)) fail("The release APK is debuggable.");

if (!publish) {
  console.log(`
✔ Verified ${packageName} ${versionName} (${versionCode}), signed by ${signingCertSha256}
  ${builtApk}
  Not published (--no-publish).`);
  process.exit(0);
}

const previous = existsSync(manifestPath) ? JSON.parse(readFileSync(manifestPath, "utf8")) : { published: false };
if (previous.published) {
  // Android only installs an update signed by the same key with a higher versionCode.
  if (previous.signingCertSha256 !== signingCertSha256) fail(`Signing key changed (${previous.signingCertSha256} → ${signingCertSha256}); installed apps could not update.`);
  if (versionCode <= previous.versionCode) fail(`versionCode ${versionCode} must be higher than the published ${previous.versionCode} (android/app/build.gradle).`);
}

// ---- 4. publish to the website ---------------------------------------------------------------------------------
copyFileSync(builtApk, publicApk);
const bytes = readFileSync(publicApk);
const today = new Date();
const release = {
  published: true,
  appName: "Bubbles",
  applicationId: packageName,
  versionName,
  versionCode,
  releaseDate: `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`,
  minSdk,
  minAndroid: ANDROID_NAMES[minSdk] || `API ${minSdk}`,
  targetSdk,
  file: "/android/bubbles.apk",
  sizeBytes: statSync(publicApk).size,
  sha256: createHash("sha256").update(bytes).digest("hex"),
  signingCertSha256,
};
writeFileSync(manifestPath, `${JSON.stringify(release, null, 2)}\n`);
console.log(`\n✔ ${release.appName} ${versionName} (${versionCode}) → public/android/bubbles.apk`);
console.log(`  ${(release.sizeBytes / 1048576).toFixed(1)} MB, SHA-256 ${release.sha256}`);
console.log(`  signing cert ${signingCertSha256}`);
console.log("  Deploy the website to publish it at https://heybubbles.in/android");
