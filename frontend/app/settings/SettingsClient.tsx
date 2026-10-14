"use client";

import { useState, useSyncExternalStore, type ReactNode } from "react";
import Link from "next/link";
import { useApi, useAuth } from "../../components/Providers";
import { BTN_SECONDARY, CARD, HubPage, Icon, PILL, SignOutButton, Skeleton, useBubblesQuery } from "../../components/hub/HubKit";
import { COMPAT_FIX_FILE, MESSAGES, databaseSummary } from "../lib/connection";
import type { PartnerSharingStatus } from "../lib/partner-sharing";
import { VeilSwitch } from "../../components/PrivacyVeil";
import { KeepSignedInRow, TwoStepCard } from "../../components/settings/SignInSecurity";
import { AiConsentRow } from "../../components/settings/AiConsentRow";
import { NotificationSettingsCard } from "../../components/wellness/NotificationSettingsCard";
import { YourDataCard } from "../../components/wellness/YourDataCard";
import { partnerSummary } from "./summary";

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

const GROUPS = [
  ["account", "Account"],
  ["partner", "Partner sharing"],
  ["notifications", "Reminders"],
  ["privacy", "Privacy and data"],
  ["device", "This device"],
] as const;

export function SettingsClient() {
  return (
    <HubPage title="Settings">
      <Settings />
    </HubPage>
  );
}

const ROW = "flex min-h-[56px] flex-wrap items-center justify-between gap-x-4 gap-y-1 px-5 py-3";

function Group({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <section id={id} aria-labelledby={`${id}-title`} className="scroll-mt-24">
      <h2 id={`${id}-title`} className="mb-2 px-1 text-body-sm font-extrabold uppercase tracking-wide text-ink-soft">
        {title}
      </h2>
      {children}
    </section>
  );
}

/** A tappable row that opens another page. */
function LinkRow({ href, label, hint, value }: { href: string; label: string; hint?: string; value?: string | null }) {
  return (
    <li>
      <Link href={href} className={`${ROW} bubbles-press text-ink no-underline hover:bg-blush`}>
        <span className="min-w-0">
          <span className="block font-bold">{label}</span>
          {hint && <span className="block text-body-sm text-muted">{hint}</span>}
        </span>
        <span className="flex items-center gap-2 text-body-sm font-bold text-bubbles-sky-deep">
          {value}
          <Icon id="arrow" size={18} />
        </span>
      </Link>
    </li>
  );
}

function Settings() {
  const { user } = useAuth();
  const { apiStatus, checkApiHealth, connectionError, health, databaseStatus } = useApi();
  const [partner] = useBubblesQuery<PartnerSharingStatus>("/partner-sharing");
  const [checking, setChecking] = useState(false);
  // Offline: the last health answer is stale, so the database is simply not known.
  const database = databaseSummary(apiStatus === "online" ? databaseStatus : "unknown");
  const reducedMotion = useSyncExternalStore(subscribeMotion, () => window.matchMedia(REDUCED_MOTION).matches, () => false);
  const partnerValue = partner.status === "ready" ? partnerSummary(partner.data) : null;

  return (
    <div className="max-w-3xl space-y-8">
      <header className="bubbles-rise">
        <h1 className="text-h1 text-ink">Settings</h1>
        <nav aria-label="Jump to a section" className="mt-3">
          <ul className="m-0 flex list-none flex-wrap gap-2 p-0">
            {GROUPS.map(([id, label]) => (
              <li key={id}>
                <a href={`#${id}`} className="bubbles-press inline-flex min-h-[44px] items-center rounded-full border-2 border-line bg-surface px-4 text-body-sm font-extrabold text-ink no-underline hover:border-line-strong">
                  {label}
                </a>
              </li>
            ))}
          </ul>
        </nav>
      </header>

      <Group id="account" title="Account">
        <ul className={`${CARD} m-0 list-none divide-y-2 divide-line overflow-hidden p-0`}>
          <li className={ROW}>
            <span className="font-bold text-ink">Signed in as</span>
            <span className="min-w-0 break-words text-body font-bold text-ink-soft">{user?.email || "Email unknown"}</span>
          </li>
          <LinkRow href="/profile" label="Your details and memory" hint="See what Bubbles knows and confirm or dismiss it" />
          {/* The Android app signs in with email + password only (no email links). */}
          <LinkRow href="/password" label="Set or change password" hint="Needed to sign in to the Android app" />
          <li className={ROW}>
            <span className="font-bold text-ink">Sign out of this device</span>
            <SignOutButton />
          </li>
        </ul>
        <div className="mt-4">
          <TwoStepCard />
        </div>
      </Group>

      <Group id="partner" title="Partner sharing">
        <ul className={`${CARD} m-0 list-none overflow-hidden p-0`}>
          {partner.status === "loading" ? (
            <li className="p-5">
              <Skeleton className="h-8" />
            </li>
          ) : (
            <LinkRow href="/partner" label="Choose what a partner can see" hint="Nothing is shared until you switch it on. You can stop any time." value={partnerValue} />
          )}
        </ul>
      </Group>

      <NotificationSettingsCard />

      <Group id="privacy" title="Privacy and data">
        <div className="space-y-4">
          <ul className={`${CARD} m-0 list-none divide-y-2 divide-line overflow-hidden p-0`}>
            <LinkRow href="/privacy" label="Privacy notice" hint="What Bubbles keeps and why" />
            <LinkRow href="/terms" label="Terms of use" />
          </ul>
          <AiConsentRow />
          <YourDataCard />
        </div>
      </Group>

      <Group id="device" title="This device">
        <div className={`${CARD} divide-y-2 divide-line overflow-hidden`}>
          <dl className="m-0 divide-y-2 divide-line">
            <div className={ROW}>
              <dt className="font-bold text-ink">Bubbles server</dt>
              <dd className="m-0">
                <span role="status" className={`${PILL} ${CONNECTION[apiStatus].style}`}>
                  {CONNECTION[apiStatus].label}
                </span>
                {apiStatus === "online" && health?.version && <span className="ml-2 text-body-sm text-muted">version {health.version}</span>}
              </dd>
            </div>
            <div className={ROW}>
              <dt className="font-bold text-ink">Database</dt>
              <dd className="m-0">
                <span role="status" className={`${PILL} ${DATABASE_STYLE[database.tone]}`}>
                  {database.label}
                </span>
              </dd>
            </div>
            <div className={ROW}>
              <dt className="font-bold text-ink">Reduce motion</dt>
              <dd className="m-0 text-body-sm text-muted">{reducedMotion ? "On, following your device" : "Off, following your device"}</dd>
            </div>
            <div className={ROW}>
              <dt className="min-w-0 max-w-[26rem] font-bold text-ink">
                <span id="keep-label">Keep me signed in on this device</span>
                <span id="keep-hint" className="block text-body-sm font-normal text-muted">
                  Off by default: you sign in again after closing the tab, and your sign-in is not kept on this device. Applies from the next time your sign-in is refreshed, or when you sign in again.
                </span>
              </dt>
              <dd className="m-0">
                <KeepSignedInRow labelledBy="keep-label" describedBy="keep-hint" />
              </dd>
            </div>
            <div className={ROW}>
              <dt className="min-w-0 max-w-[26rem] font-bold text-ink">
                <span id="veil-label">Privacy veil</span>
                <span id="veil-hint" className="block text-body-sm font-normal text-muted">
                  Blurs health values and chats when you switch tabs or press Hide in the top bar. Tap a blurred area to show it. Off by default, saved on this device only.
                </span>
              </dt>
              <dd className="m-0">
                <VeilSwitch labelledBy="veil-label" describedBy="veil-hint" />
              </dd>
            </div>
          </dl>

          {(apiStatus === "offline" || (apiStatus === "online" && (databaseStatus === "permission_denied" || databaseStatus === "unreachable"))) && (
            <div className="space-y-2 bg-blush px-5 py-4 text-body-sm text-muted">
              {apiStatus === "offline" && <p className="m-0">{connectionError ?? MESSAGES.offline}</p>}
              {apiStatus === "online" && databaseStatus === "unreachable" && <p className="m-0">{MESSAGES.databaseDown}</p>}
              {apiStatus === "online" && databaseStatus === "permission_denied" && (
                <>
                  <p className="m-0">
                    <strong className="text-ink">Compatibility mode.</strong> Bubbles is running and your entries are still being saved, but the database needs a one-time permission update.
                  </p>
                  <p className="m-0">
                    The fix: the database owner runs <code className="break-all font-bold text-ink">{COMPAT_FIX_FILE}</code> once in the Supabase SQL editor, then press Check again.
                  </p>
                  {health && health.denied_tables.length > 0 && (
                    <details>
                      <summary className="-my-[11px] cursor-pointer py-[11px] font-extrabold text-ink">
                        {health.denied_tables.length} {health.denied_tables.length === 1 ? "table needs" : "tables need"} access
                      </summary>
                      <p className="m-0 mt-1 break-words">{health.denied_tables.join(", ")}</p>
                    </details>
                  )}
                </>
              )}
            </div>
          )}

          <div className={ROW}>
            <span className="text-body-sm text-muted">Whether this app can reach Bubbles, and whether it can reach its database.</span>
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
        </div>
      </Group>
    </div>
  );
}
