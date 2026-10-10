"use client";

import { useState, useSyncExternalStore } from "react";
import Link from "next/link";
import { useApi, useAuth } from "../../components/Providers";
import { BTN_SECONDARY, CARD, HubPage, PILL, SignOutButton } from "../../components/hub/HubKit";
import { COMPAT_FIX_FILE, MESSAGES, databaseSummary } from "../lib/connection";
import { NotificationSettingsCard } from "../../components/wellness/NotificationSettingsCard";
import { YourDataCard } from "../../components/wellness/YourDataCard";

const REDUCED_MOTION = "(prefers-reduced-motion: reduce)";

function subscribeMotion(onChange: () => void) {
  const media = window.matchMedia(REDUCED_MOTION);
  media.addEventListener("change", onChange);
  return () => media.removeEventListener("change", onChange);
}

const CONNECTION = {
  online: { label: "Online", style: "bg-tint-mint text-bubbles-mint-deep" },
  checking: { label: "Checking…", style: "bg-tint-sun text-bubbles-sun-deep" },
  offline: { label: "Offline", style: "bg-tint-peach text-bubbles-peach-deep" },
} as const;

const DATABASE_STYLE = {
  good: "bg-tint-mint text-bubbles-mint-deep",
  warn: "bg-tint-sky text-bubbles-sky-deep",
  bad: "bg-tint-peach text-bubbles-peach-deep",
  idle: "bg-tint-sun text-bubbles-sun-deep",
} as const;

export function SettingsClient() {
  return (
    <HubPage title="Settings">
      <Settings />
    </HubPage>
  );
}

function Settings() {
  const { user } = useAuth();
  const { apiStatus, checkApiHealth, connectionError, health, databaseStatus } = useApi();
  const [checking, setChecking] = useState(false);
  // Offline: the last health answer is stale, so the database is simply not known.
  const database = databaseSummary(apiStatus === "online" ? databaseStatus : "unknown");
  const reducedMotion = useSyncExternalStore(subscribeMotion, () => window.matchMedia(REDUCED_MOTION).matches, () => false);

  return (
    <div className="space-y-8">
      <header className="bubbles-rise">
        <h1 className="text-h1 text-ink">Settings</h1>
        <p className="mt-1 text-body font-semibold text-muted">Only the things that work today. Nothing pretend.</p>
      </header>

      <div className="bubbles-stagger grid items-start gap-6 lg:grid-cols-2">
        <section aria-labelledby="account-title" className={`${CARD} p-5 sm:p-6`}>
          <h2 id="account-title" className="text-h3 text-ink">
            Account
          </h2>
          <dl className="m-0 mt-4">
            <dt className="text-body-sm font-extrabold text-ink-soft">Signed in as</dt>
            <dd className="m-0 mt-1 break-words text-body font-bold text-ink">{user?.email || "Unknown email"}</dd>
          </dl>
          <div className="mt-5 flex flex-wrap items-center gap-3">
            <Link href="/profile" className={`${BTN_SECONDARY} no-underline`}>
              Your details & memory
            </Link>
            <SignOutButton />
          </div>
        </section>

        <section aria-labelledby="partner-title" className={`${CARD} p-5 sm:p-6`}>
          <h2 id="partner-title" className="text-h3 text-ink">
            Partner sharing
          </h2>
          <p className="mt-1 text-body text-muted">
            Choose what a partner can see, connect with an invite code or a link, and stop sharing any time. Nothing is shared until you switch it on.
          </p>
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <Link href="/partner" className={`${BTN_SECONDARY} no-underline`}>
              Manage partner sharing
            </Link>
          </div>
        </section>

        <section aria-labelledby="connection-title" className={`${CARD} p-5 sm:p-6`}>
          <h2 id="connection-title" className="text-h3 text-ink">
            Connection
          </h2>
          <p className="mt-1 text-body text-muted">Whether this app can reach Bubbles&apos; server, and whether the server can reach its database.</p>
          <dl className="m-0 mt-4 space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <dt className="text-body-sm font-extrabold text-ink-soft">Backend</dt>
              <dd className="m-0">
                <span role="status" className={`${PILL} ${CONNECTION[apiStatus].style}`}>
                  {CONNECTION[apiStatus].label}
                </span>
                {apiStatus === "online" && health?.version && <span className="ml-2 text-body-sm text-muted">version {health.version}</span>}
              </dd>
            </div>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <dt className="text-body-sm font-extrabold text-ink-soft">Database</dt>
              <dd className="m-0">
                <span role="status" className={`${PILL} ${DATABASE_STYLE[database.tone]}`}>
                  {database.label}
                </span>
              </dd>
            </div>
          </dl>

          {apiStatus === "offline" && <p className="mt-4 text-body-sm text-muted">{connectionError ?? MESSAGES.offline}</p>}

          {apiStatus === "online" && databaseStatus === "permission_denied" && (
            <div className="mt-4 rounded-2xl bg-blush px-4 py-3 text-body-sm text-muted">
              <p className="m-0">
                <strong className="text-ink">Compatibility mode.</strong> Bubbles is running and your entries are still being saved, but the
                database needs a one-time permission update.
              </p>
              <p className="m-0 mt-2">
                The fix: the database owner runs <code className="break-all font-bold text-ink">{COMPAT_FIX_FILE}</code> once in the
                Supabase SQL editor, then press Check again.
              </p>
              {health && health.denied_tables.length > 0 && (
                <details className="mt-2">
                  <summary className="cursor-pointer font-extrabold text-ink">
                    {health.denied_tables.length} {health.denied_tables.length === 1 ? "table needs" : "tables need"} access
                  </summary>
                  <p className="m-0 mt-1 break-words">{health.denied_tables.join(", ")}</p>
                </details>
              )}
            </div>
          )}

          {apiStatus === "online" && databaseStatus === "unreachable" && <p className="mt-4 text-body-sm text-muted">{MESSAGES.databaseDown}</p>}

          <div className="mt-4 flex flex-wrap items-center gap-3">
            <button
              type="button"
              disabled={checking}
              onClick={async () => {
                setChecking(true);
                try {
                  await checkApiHealth();
                } finally {
                  setChecking(false);
                }
              }}
              className={BTN_SECONDARY}
            >
              {checking ? "Checking…" : "Check again"}
            </button>
          </div>
        </section>

        <section aria-labelledby="motion-title" className={`${CARD} p-5 sm:p-6`}>
          <h2 id="motion-title" className="text-h3 text-ink">
            Motion
          </h2>
          <p className="mt-1 text-body text-muted">
            Bubbles follows your device&apos;s &ldquo;reduce motion&rdquo; setting. It&apos;s{" "}
            <strong className="text-ink">{reducedMotion ? "on" : "off"}</strong> right now
            {reducedMotion ? ", so animations are switched off." : ", so you'll see gentle animations."} Change it in your
            device&apos;s accessibility settings.
          </p>
        </section>

        <NotificationSettingsCard />

        <YourDataCard />

        <section aria-labelledby="later-title" className="rounded-3xl border-2 border-dashed border-line-strong p-5 sm:p-6">
          <h2 id="later-title" className="text-h3 text-ink">
            Not in the app yet
          </h2>
          <p className="mt-1 text-body text-muted">These aren&apos;t available here yet, so there are no switches for them.</p>
          <ul className="m-0 mt-4 list-none space-y-2 p-0">
            {["Delete my account"].map((item) => (
              <li key={item} className="flex flex-wrap items-center justify-between gap-2 rounded-2xl bg-blush px-4 py-3">
                <span className="font-bold text-ink-soft">{item}</span>
                <span className={`${PILL} border-2 border-dashed border-line-strong text-ink-soft`}>Not available yet</span>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  );
}
