"use client";

import { useState, type ReactNode } from "react";
import Link from "next/link";
import { useApi, useAuth, useExperience } from "../../components/Providers";
import {
  BTN_PRIMARY,
  BTN_SECONDARY,
  CARD,
  ErrorCard,
  HubPage,
  Icon,
  PILL,
  SignOutButton,
  Skeleton,
  TONE,
  humanize,
  useBubblesQuery,
  type Tone,
} from "../../components/hub/HubKit";
import { formatWhen, parseWhen } from "../lib/dates";
import { countLabel, memoryItems, type MemoryItem, type MemoryRow } from "./memory";

interface Profile {
  display_name?: string | null;
  date_of_birth?: string | null;
  height_cm?: number | null;
  gender?: string | null;
  timezone?: string | null;
}

interface MemoryResponse {
  memory?: {
    L1?: number;
    L1_confirmed?: number;
    L1_pending?: number;
    L2?: number;
    L3?: number;
    recent?: MemoryRow[];
    errors?: string[];
  };
}

function age(dob: string): number | null {
  const born = parseWhen(dob); // a date of birth is a calendar day: never shift it through UTC
  if (Number.isNaN(born.getTime())) return null;
  const now = new Date();
  const years = now.getFullYear() - born.getFullYear();
  return now < new Date(now.getFullYear(), born.getMonth(), born.getDate()) ? years - 1 : years;
}

export function ProfileClient() {
  return (
    <HubPage title="Me">
      <Me />
    </HubPage>
  );
}

function Me() {
  const { user } = useAuth();
  const { fetchBubbles } = useApi();
  const { experience } = useExperience();
  const [profileQuery, reloadProfile] = useBubblesQuery<{ profile?: Profile }>("/profile");
  const [memoryQuery, reloadMemory] = useBubblesQuery<MemoryResponse>("/memory/diagnostics");
  const [busy, setBusy] = useState<string | null>(null);
  const [problem, setProblem] = useState<{ id: string; message: string } | null>(null);

  const profile = profileQuery.status === "ready" ? profileQuery.data.profile ?? {} : null;
  const memory = memoryQuery.status === "ready" ? memoryQuery.data.memory ?? {} : null;
  const loadingMemory = memoryQuery.status === "loading";
  const name = profile?.display_name || user?.display_name;
  const years = profile?.date_of_birth ? age(profile.date_of_birth) : null;
  const items = memoryItems(memory?.recent);
  const pending = items.filter((item) => !item.confirmed);

  const details: Array<[string, string | null | undefined]> = profile
    ? [
        ["Name", profile.display_name],
        ["Date of birth", profile.date_of_birth && `${formatWhen(profile.date_of_birth, true)}${years != null ? ` · ${years} years` : ""}`],
        ["Height", profile.height_cm != null ? `${profile.height_cm} cm` : null],
        ["Gender", profile.gender && humanize(profile.gender)],
        ["Time zone", profile.timezone],
      ]
    : [];
  const coreSet = details.filter(([, value]) => value).length;

  async function decide(item: MemoryItem, confirmed: boolean) {
    if (!item.id) return;
    setBusy(item.id);
    setProblem(null);
    try {
      const response = await fetchBubbles(`/health-events/${encodeURIComponent(item.id)}/confirmation`, { method: "PATCH", body: JSON.stringify({ confirmed }) }, { timeoutMs: 65000, retries: 0 });
      if (response.ok) {
        reloadMemory();
      } else if (response.status === 409 || response.status === 410) {
        setProblem({ id: item.id, message: "Bubbles withdrew this after a correction, so it can't be saved." });
        reloadMemory();
      } else {
        setProblem({ id: item.id, message: `Bubbles couldn't ${confirmed ? "confirm" : "dismiss"} this just now. Nothing changed. Try again.` });
      }
    } catch {
      setProblem({ id: item.id, message: `Bubbles couldn't ${confirmed ? "confirm" : "dismiss"} this just now. Nothing changed. Try again.` });
    } finally {
      setBusy(null);
    }
  }

  const pill = (value: string | null, suffix: string, tone: Tone) =>
    loadingMemory ? <Skeleton className="h-7 w-28 rounded-full" /> : value === null ? <span className={`${PILL} ${TONE.plain.chip}`}>Count unavailable</span> : <span className={`${PILL} ${TONE[tone].chip}`}>{value} {suffix}</span>;

  const memoryDetail = (
    <>
      {memoryQuery.status === "error" && <ErrorCard title="Memory didn't load" message={memoryQuery.message} onRetry={reloadMemory} inset />}
      {memory?.errors?.length ? (
        <p role="status" className="m-0 text-body-sm font-bold text-bubbles-sun-deep">Some counts couldn&apos;t be read. A missing count is unknown, not zero.</p>
      ) : null}
      {memory && pending.length === 0 && <p className="m-0 rounded-2xl bg-blush p-4 text-body-sm text-muted">Nothing waiting for you. New details Bubbles notices will show here.</p>}
      {pending.length > 0 && (
        <ul className="m-0 list-none space-y-2 p-0">
          {pending.map((item, i) => (
            <li key={item.id ?? i} className="rounded-2xl bg-blush p-3">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="break-words font-bold text-ink">{item.title}</p>
                  <p className="break-words text-body-sm text-muted">
                    {[item.kind !== item.title ? item.kind : "", item.detail, item.when ? formatWhen(item.when) : ""].filter(Boolean).join(" · ")}
                  </p>
                </div>
                {item.confirmed && <span className={`${PILL} ${TONE.mint.chip}`}>Confirmed</span>}
              </div>
              {!item.confirmed && item.id && (
                <div className="mt-2 flex flex-wrap gap-2">
                  <button type="button" disabled={busy === item.id} onClick={() => void decide(item, true)} className={BTN_PRIMARY}>
                    Confirm
                  </button>
                  <button type="button" disabled={busy === item.id} onClick={() => void decide(item, false)} className={BTN_SECONDARY}>
                    Not right
                  </button>
                </div>
              )}
              {problem?.id === item.id && (
                <p role="alert" className="mt-2 text-body-sm font-bold text-bubbles-peach-deep">
                  {problem.message}
                </p>
              )}
            </li>
          ))}
        </ul>
      )}
    </>
  );

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <header className="bubbles-rise">
        <h1 className="text-h1 text-ink">{name ? `Hi, ${name}` : "Me"}</h1>
        <p className="mt-1 break-words text-body-sm font-semibold text-muted">
          {user?.email}
          {user?.created_at ? ` · since ${formatWhen(user.created_at, true)}` : ""}
        </p>
        <div className="mt-4 flex flex-wrap items-center gap-2">
          <Link href="/onboarding?edit=1" className={`${BTN_SECONDARY} no-underline`}>
            Your setup
          </Link>
          {experience?.cycleVisible !== false && (
            <Link href="/partner" className={`${BTN_SECONDARY} no-underline`}>
              Partner sharing
            </Link>
          )}
          <Link href="/profile/understanding" className={`${BTN_SECONDARY} no-underline`}>
            How Bubbles understands you
          </Link>
          <Link href="/settings" className={`${BTN_SECONDARY} no-underline`}>
            Settings
          </Link>
          <SignOutButton />
        </div>
      </header>

      <section aria-labelledby="details-title" className={`${CARD} p-5`}>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 id="details-title" className="text-h4 text-ink">Your details</h2>
          {profile && <span className={`${PILL} ${TONE.mint.chip}`}>{coreSet} of {details.length} set</span>}
        </div>
        {profileQuery.status === "loading" && <Skeleton className="mt-3 h-40" />}
        {profileQuery.status === "error" && (
          <div className="mt-3">
            <ErrorCard title="Your details didn't load" message={profileQuery.message} onRetry={reloadProfile} inset />
          </div>
        )}
        {profile && (
          <>
            <dl className="m-0 mt-3 divide-y-2 divide-line">
              {details.map(([label, value]) => (
                <div key={label} className="flex flex-wrap justify-between gap-x-4 gap-y-1 py-2.5">
                  <dt className="text-body-sm font-extrabold text-ink-soft">{label}</dt>
                  <dd className={`m-0 text-body ${value ? "font-bold text-ink" : "text-muted"}`}>{value || "Not set"}</dd>
                </div>
              ))}
            </dl>
            <p className="mt-2 text-chip text-muted">
              Height and weight goals live in{" "}
              <Link href="/fitness/setup" className="font-extrabold text-bubbles-grape-deep underline">
                Fitness setup
              </Link>
              .
            </p>
          </>
        )}
      </section>

      <section aria-labelledby="memory-title" className={`${CARD} p-5`}>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 id="memory-title" className="text-h4 text-ink">What Bubbles remembers</h2>
          {pill(countLabel(memory?.L1_pending), "to review", "sky")}
        </div>
        <p className="mt-1 text-body-sm text-muted">Only what you confirm becomes lasting memory.</p>
        <div className="mt-3 space-y-3">{memoryDetail}</div>
        {memory && (
          <p className="mt-3 text-chip text-muted">
            Confirmed so far: {countLabel(memory.L2) ?? "unknown"} health facts, {countLabel(memory.L3) ?? "unknown"} everyday signals.
          </p>
        )}
        <details className="group mt-3">
          <summary className="flex min-h-[44px] cursor-pointer list-none items-center gap-2 text-body-sm font-extrabold text-bubbles-grape-deep [&::-webkit-details-marker]:hidden">
            How memory works
            <span className="transition-transform group-open:rotate-90"><Icon id="arrow" size={16} /></span>
          </summary>
          <ol className="m-0 mt-3 list-none space-y-4 border-l-2 border-line p-0 pl-6">
            <Level level="L0" title="This conversation" tone="plain" badge={<span className={`${PILL} ${TONE.plain.chip}`}>Not stored</span>}>
              Used in the moment, not kept.
            </Level>
            <Level level="L1" title="Noticed, waiting for you" tone="sky" badge={null}>
              Suggestions until you confirm them.
            </Level>
            <Level level="L2" title="Lasting health facts" tone="pink" badge={pill(countLabel(memory?.L2), "confirmed", "pink")}>
              Conditions, allergies and history you confirmed.
            </Level>
            <Level level="L3" title="Everyday signals" tone="grape" badge={pill(countLabel(memory?.L3), "confirmed", "grape")}>
              Confirmed sleep, mood and symptoms that patterns use.
            </Level>
            <Level level="L4" title="Core profile" tone="mint" badge={null}>
              The basics above.
            </Level>
          </ol>
        </details>
      </section>

      <p className="m-0 flex items-start gap-2 px-1 text-chip text-muted">
        <span className="mt-0.5 shrink-0 text-bubbles-mint-deep"><Icon id="shield" size={16} /></span>
        Bubbles never diagnoses, urgent words get a safety check first, and missing data is never read as all clear.
      </p>
    </div>
  );
}

function Level({ level, title, tone, badge, extra, children }: { level: string; title: string; tone: Tone; badge: ReactNode; extra?: ReactNode; children: ReactNode }) {
  return (
    <li className="relative">
      <span className={`absolute -left-[2.75rem] top-0 flex h-8 w-8 items-center justify-center rounded-xl font-display text-sm font-semibold ring-4 ring-white ${TONE[tone].bubble}`}>{level}</span>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="font-display text-h4 text-ink">{title}</h3>
        {badge}
      </div>
      <p className="m-0 mt-1 text-body-sm text-muted">{children}</p>
      {extra}
    </li>
  );
}
