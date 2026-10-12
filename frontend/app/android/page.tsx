import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";
import { isNativeApp } from "../../lib/native";
// Written by scripts/build-android.mjs next to the signed APK, so this page always describes the file it serves.
import release from "../../public/android/latest.json";

export const metadata: Metadata = {
  title: "Download for Android | Bubbles",
  description:
    "Download the Bubbles Android app, install it outside Google Play, check that the file is genuine and keep it up to date. Same account as the website.",
};

const HASH_COMMANDS = [
  { os: "Windows (Command Prompt or PowerShell)", command: "certutil -hashfile bubbles.apk SHA256" },
  { os: "macOS (Terminal)", command: "shasum -a 256 bubbles.apk" },
  { os: "Linux", command: "sha256sum bubbles.apk" },
];

const CARD = "rounded-[32px] border-2 border-line bg-surface p-6 shadow-md sm:p-8";
const CODE = "block select-all wrap-anywhere rounded-[18px] bg-blush px-4 py-3 font-mono text-body-sm text-ink";
const LINK = "font-extrabold text-bubbles-pink-ink underline underline-offset-2";

export default function AndroidPage() {
  return (
    <main className="relative min-h-dvh overflow-hidden bg-blush px-5 py-10">
      <div className="bubbles-drift pointer-events-none absolute -left-24 -top-24 h-72 w-72 rounded-full bg-tint-pink" aria-hidden="true" />
      <div className="bubbles-drift-slow pointer-events-none absolute -bottom-28 -right-20 h-80 w-80 rounded-full bg-tint-grape" aria-hidden="true" />

      <div className="relative z-base mx-auto flex w-full max-w-[640px] flex-col gap-6 bubbles-rise">
        <Link href="/" className="self-start text-body-sm font-extrabold text-bubbles-pink-ink">
          <span aria-hidden="true">← </span>Back to Bubbles
        </Link>

        <header className="flex flex-col items-center gap-3 text-center">
          {/* eslint-disable-next-line @next/next/no-img-element -- a static SVG; next/image adds nothing and needs config in the static export */}
          <img src="/icon.svg" alt="The Bubbles app icon" width={96} height={96} />
          <h1 className="m-0 font-display text-h1">Bubbles for Android</h1>
          <p className="m-0 text-body text-ink-soft">
            Your health companion as an app on your phone. Sign in with the same account you use on the website, and your health story is already there.
          </p>
        </header>

        {isNativeApp ? <InApp /> : release.published ? <Published /> : <NotPublished />}

        {!isNativeApp && (
          <Section title="On an iPhone?">
            <p className="m-0">
              The app is Android-only. On an iPhone or iPad, use Bubbles in your browser at{" "}
              <Link href="/" className={LINK}>
                heybubbles.in
              </Link>
              : it&apos;s the same Bubbles and the same account.
            </p>
          </Section>
        )}

        <p className="m-0 text-center text-body-sm font-semibold text-ink-soft">
          Bubbles is a wellness companion, not a medical device, and it does not diagnose. The app is the same Bubbles as the website, with the same
          privacy: your health story stays in your Bubbles account, behind your sign-in. In an emergency, contact your local emergency number.
        </p>
      </div>
    </main>
  );
}

/* The APK bundles a copy of this page, so it never offers itself for download (its copy of the manifest may be older). */
function InApp() {
  return (
    <div className={`${CARD} text-center`}>
      <p className="m-0 text-h4 font-extrabold text-ink">You&apos;re already using the app.</p>
      <p className="mb-0 mt-2 text-body text-ink-soft">To get a newer version, open heybubbles.in/android in your phone&apos;s browser.</p>
    </div>
  );
}

function NotPublished() {
  return (
    <div className={`${CARD} text-center`}>
      <h2 className="m-0 text-h3">The Android app isn&apos;t published yet.</h2>
      <p className="mb-0 mt-2 text-body text-ink-soft">
        When it is, you&apos;ll be able to download it right here. Until then, Bubbles works in your phone&apos;s browser:{" "}
        <Link href="/login" className={LINK}>
          sign in
        </Link>{" "}
        at heybubbles.in.
      </p>
    </div>
  );
}

function Published() {
  const released = new Date(`${release.releaseDate}T00:00:00Z`).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  });
  // Same unit as the release script's summary.
  const sizeMb = (release.sizeBytes / 1048576).toFixed(1);

  return (
    <>
      <section aria-labelledby="android-download" className={CARD}>
        <h2 id="android-download" className="m-0 text-h3">
          Get the app
        </h2>
        <a
          href={release.file}
          download
          type="application/vnd.android.package-archive"
          className="bubbles-press mt-4 inline-flex min-h-[56px] w-full items-center justify-center gap-2 rounded-full bg-bubbles-pink-ink px-6 text-[1.0625rem] font-extrabold text-white shadow-[0_5px_0_var(--bubbles-pink-deep)] sm:w-auto"
        >
          <DownloadIcon />
          Download for Android
        </a>
        <dl className="mb-0 mt-5 grid grid-cols-2 gap-x-4 gap-y-3 text-body-sm">
          <Fact label="Version">{release.versionName}</Fact>
          <Fact label="Released">
            <time dateTime={release.releaseDate}>{released}</time>
          </Fact>
          <Fact label="Size">{sizeMb} MB</Fact>
          <Fact label="Needs">Android {release.minAndroid} or newer</Fact>
        </dl>
      </section>

      <Section title="Installing outside Google Play">
        <p className="m-0">
          Open this page on your Android phone. Bubbles is installed straight from here rather than from Google Play, so Android asks one or two extra
          questions the first time.
        </p>
        <ol className="m-0 flex list-none flex-col gap-4 p-0">
          <Step n={1} title="Download">
            Tap Download for Android above. If your browser warns that this type of file can harm your device, that&apos;s its standard warning for any
            app from outside Google Play: choose to download it anyway.
          </Step>
          <Step n={2} title="Open the file">
            When it finishes, tap the download notification, or open bubbles.apk from your browser&apos;s Downloads or your Files app.
          </Step>
          <Step n={3} title="Allow the install, if asked">
            Android may say your browser or file manager isn&apos;t allowed to install unknown apps. Tap Settings, turn on Allow from this source, then
            go back. The same switch lives in Settings → Apps → Special app access → Install unknown apps (names vary a little between phones).
          </Step>
          <Step n={4} title="Install">
            Tap Install, then Open, and sign in with your Bubbles account.
          </Step>
        </ol>
        <p className="m-0 rounded-[18px] bg-tint-sun px-4 py-3 text-body-sm font-bold text-bubbles-sun-deep">
          Google Play Protect may say it doesn&apos;t recognise the app or its developer, because Bubbles doesn&apos;t come from Google Play. To be sure
          your file is the real one before you continue, check it with Verify your download below.
        </p>
        <p className="m-0 text-body-sm">
          Once Bubbles is installed you can turn Install unknown apps off again. You&apos;ll only need it to install an update.
        </p>
      </Section>

      <Section title="Verify your download">
        <p className="m-0">
          Optional, but it&apos;s the surest way to know the file came from Bubbles and wasn&apos;t changed on the way. On a computer, run the command for
          your system in the folder where bubbles.apk is saved, and compare the result with this SHA-256. Letter case doesn&apos;t matter.
        </p>
        <div className="flex flex-col gap-2">
          <h3 className="m-0 text-h4">SHA-256 of bubbles.apk</h3>
          <code className={CODE}>{release.sha256}</code>
        </div>
        <dl className="m-0 flex flex-col gap-3">
          {HASH_COMMANDS.map((c) => (
            <div key={c.os} className="flex flex-col gap-1">
              <dt className="text-body-sm font-extrabold">{c.os}</dt>
              <dd className="m-0">
                <code className={CODE}>{c.command}</code>
              </dd>
            </div>
          ))}
        </dl>
        <div className="flex flex-col gap-2">
          <h3 className="m-0 text-h4">Signing certificate (advanced)</h3>
          <p className="m-0 text-body-sm">
            Every Bubbles release is signed with the same key. With the Android SDK build tools installed, run this and compare the line ending in
            &ldquo;certificate SHA-256 digest&rdquo; with the fingerprint below. apksigner prints it in lowercase without the colons.
          </p>
          <code className={CODE}>apksigner verify --print-certs bubbles.apk</code>
          <code className={CODE}>{release.signingCertSha256}</code>
        </div>
      </Section>

      <Section title="Updates">
        <ul className="m-0 flex flex-col gap-3 pl-5">
          <li>New versions are published on this page, and it always shows the latest one. You can see which version you have in Settings → Apps → Bubbles.</li>
          <li>
            To update, download the new version and install it over the app you have. There&apos;s no need to uninstall first, and nothing is lost: your
            health story lives in your Bubbles account.
          </li>
          <li>
            Android only accepts an update signed with the same key as the app you already have. That&apos;s how you know an update is genuine. If Android
            ever refuses to install an update over Bubbles, don&apos;t uninstall to force it: download it again from this page and verify it.
          </li>
        </ul>
      </Section>
    </>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  const id = `android-${title.toLowerCase().replace(/[^a-z]+/g, "-")}`;
  return (
    <section aria-labelledby={id} className={`${CARD} flex flex-col gap-4 text-body text-ink`}>
      <h2 id={id} className="m-0 text-h3">
        {title}
      </h2>
      {children}
    </section>
  );
}

function Step({ n, title, children }: { n: number; title: string; children: ReactNode }) {
  return (
    <li className="flex gap-3">
      <span
        aria-hidden="true"
        className="flex h-8 w-8 flex-none items-center justify-center rounded-full bg-tint-grape font-display text-body font-semibold text-bubbles-grape-deep"
      >
        {n}
      </span>
      <div>
        <p className="m-0 font-extrabold">
          <span className="sr-only">Step {n}: </span>
          {title}
        </p>
        <p className="m-0 text-body-sm text-ink-soft">{children}</p>
      </div>
    </li>
  );
}

function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-caption text-ink-faint">{label}</dt>
      <dd className="m-0 font-extrabold text-ink">{children}</dd>
    </div>
  );
}

function DownloadIcon() {
  return (
    <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 4v11M7 10l5 5 5-5M5 20h14" />
    </svg>
  );
}
