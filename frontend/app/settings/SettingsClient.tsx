"use client";

import { useState, type ReactNode } from "react";
import Link from "next/link";
import { useApi, useAuth } from "../../components/Providers";
import { BTN_SECONDARY, HubPage, Icon, PILL, SignOutButton, Skeleton, useBubblesQuery } from "../../components/hub/HubKit";
import { COMPAT_FIX_FILE, MESSAGES, databaseSummary } from "../lib/connection";
import type { PartnerSharingStatus } from "../lib/partner-sharing";
import { VeilSwitch } from "../../components/PrivacyVeil";
import { KeepSignedInRow, TwoStepCard } from "../../components/settings/SignInSecurity";
import { NotificationSettingsCard } from "../../components/wellness/NotificationSettingsCard";
import { YourDataCard } from "../../components/wellness/YourDataCard";
import { partnerSummary } from "./summary";

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

const ROW = "flex min-h-[56px] flex-wrap items-center justify-between gap-x-4 gap-y-1 px-5 py-3";

/** One calm row per area; the detail opens only when asked for. Account stays open. */
function Group({ id, title, open = false, children }: { id: string; title: string; open?: boolean; children: ReactNode }) {
  return (
    <details id={id} open={open} className="group scroll-mt-24 rounded-[24px] border border-line bg-surface shadow-sm">
      <summary className="flex min-h-[56px] cursor-pointer list-none items-center justify-between gap-3 px-5 py-3 font-display text-lg font-semibold text-ink [&::-webkit-details-marker]:hidden">
        {title}
        <span className="transition-transform group-open:rotate-90"><Icon id="arrow" size={18} /></span>
      </summary>
      <div className="space-y-4 px-3 pb-4 sm:px-4">{children}</div>
    </details>
  );
}

/** A tappable row that opens another page. */
function LinkRow({ href, label, value }: { href: string; label: string; value?: string | null }) {
  return (
    <li>
      <Link href={href} className={`${ROW} bubbles-press text-ink no-underline hover:bg-blush`}>
        <span className="min-w-0">
          <span className="block font-bold">{label}</span>
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
  const partnerValue = partner.status === "ready" ? partnerSummary(partner.data) : null;

  return (
    <div className="max-w-3xl space-y-8">
      <h1 className="bubbles-rise text-h1 text-ink">Settings</h1>

      <Group id="account" title="Account" open>
        <ul className="m-0 list-none divide-y-2 divide-line overflow-hidden p-0">
          <li className={ROW}>
            <span className="font-bold text-ink">Signed in as</span>
            <span className="min-w-0 break-words text-body font-bold text-ink-soft">{user?.email || "Email unknown"}</span>
          </li>
          <LinkRow href="/profile" label="Your details and memory" />
          {/* The Android app signs in with email + password only (no email links). */}
          <LinkRow href="/password" label="Password" />
          {partner.status === "loading" ? (
            <li className="p-5">
              <Skeleton className="h-8" />
            </li>
          ) : (
            <LinkRow href="/partner" label="Partner sharing" value={partnerValue} />
          )}
          <li className={ROW}>
            <span className="font-bold text-ink">Sign out of this device</span>
            <SignOutButton />
          </li>
        </ul>
        <TwoStepCard />
      </Group>

      <Group id="notifications" title="Reminders">
        <NotificationSettingsCard />
      </Group>

      <Group id="privacy" title="Privacy and data">
        <ul className="m-0 list-none divide-y-2 divide-line overflow-hidden p-0">
          <LinkRow href="/privacy" label="Privacy notice" />
          <LinkRow href="/terms" label="Terms of use" />
        </ul>
        <ul className="m-0 list-none divide-y-2 divide-line overflow-hidden p-0">
          <LinkRow href="/privacy-choices" label="Privacy choices" />
        </ul>
        <YourDataCard />
      </Group>

      <Group id="device" title="This device">
        <div className="divide-y-2 divide-line overflow-hidden">
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
              <dt className="min-w-0 max-w-[26rem] font-bold text-ink">
                <span id="keep-label">Keep me signed in on this device</span>
                <span id="keep-hint" className="block text-body-sm font-normal text-muted">
                  Off: you sign in again after closing the tab.
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
                  Blurs your data when you switch tabs.
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

          <div className={`${ROW} justify-end`}>
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
              {checking ? "Checking…" : "Check connection"}
            </button>
          </div>
        </div>
      </Group>
    </div>
  );
}
