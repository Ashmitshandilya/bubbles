"use client";

import { useState, type ReactNode } from "react";
import Link from "next/link";
import { BubblesMascot } from "../../components/BubblesMascot";
import { useApi, useAuth } from "../../components/Providers";
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

  return (
    <div className="space-y-8">
      <header className="bubbles-rise flex flex-wrap items-center gap-4">
        <div className="bubbles-breathe flex h-[72px] w-[72px] items-center justify-center rounded-[24px] bg-tint-pink">
          <BubblesMascot size={60} mood="happy" animated={false} />
        </div>
        <div className="min-w-0 flex-1">
          <h1 className="text-h1 text-ink">{name ? `Hi, ${name}` : "Me"}</h1>
          <p className="mt-1 break-words text-body font-semibold text-muted">
            {user?.email}
            {user?.created_at ? ` · with Bubbles since ${formatWhen(user.created_at, true)}` : ""}
          </p>
        </div>
      </header>

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
        <section aria-labelledby="memory-title" className={`${CARD} p-5 sm:p-6`}>
          <h2 id="memory-title" className="text-h3 text-ink">
            What Bubbles knows about you
          </h2>
          <p className="mt-1 text-body text-muted">Five levels, from this moment to your core profile. Only what you confirm becomes lasting memory.</p>
          {memoryQuery.status === "error" && (
            <div className="mt-4">
              <ErrorCard title="Memory didn't load" message={memoryQuery.message} onRetry={reloadMemory} inset />
            </div>
          )}
          {memory?.errors?.length ? (
            <p role="status" className="mt-3 text-body-sm font-bold text-bubbles-sun-deep">
              Some memory counts couldn&apos;t be read right now. A missing count is unknown, not zero.
            </p>
          ) : null}

          <ol className="m-0 mt-6 list-none space-y-6 border-l-2 border-line p-0 pl-8">
            <Level level="L0" title="This conversation" tone="plain" badge={<span className={`${PILL} ${TONE.plain.chip}`}>Not stored</span>}>
              What you&apos;re saying right now. Bubbles uses it in the moment and doesn&apos;t keep it as memory.
            </Level>

            <Level
              level="L1"
              title="Noticed, waiting for you"
              tone="sky"
              badge={pill(countLabel(memory?.L1_pending), "to review", "sky")}
              extra={
                memory && (
                  <>
                    <p className="m-0 mt-2 text-body-sm text-muted">
                      Confirmed: {countLabel(memory.L1_confirmed) ?? "unknown"}. Noticed in total: {countLabel(memory.L1) ?? "unknown"}. The latest ten are below.
                    </p>
                    {items.length === 0 ? (
                      <p className="mt-3 rounded-2xl bg-blush p-4 text-body-sm text-muted">Nothing noticed yet. As you chat or log, details Bubbles picks up will appear here for you to review.</p>
                    ) : (
                      <ul className="m-0 mt-3 list-none space-y-2 p-0">
                        {items.map((item, i) => (
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
                                  Not right, dismiss
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
                    <p className="mt-3 text-body-sm text-muted">Confirmed items can&apos;t be changed from this page. If a suggestion looks wrong, dismiss it instead of confirming.</p>
                  </>
                )
              }
            >
              Health details Bubbles picked up from your chats and logs. They stay suggestions until you confirm them.
            </Level>

            <Level level="L2" title="Lasting health facts" tone="pink" badge={pill(countLabel(memory?.L2), "confirmed", "pink")}>
              Conditions, allergies and history you confirmed. Bubbles keeps these in mind. This page shows the count, not the individual facts.
            </Level>

            <Level level="L3" title="Everyday signals" tone="grape" badge={pill(countLabel(memory?.L3), "confirmed", "grape")}>
              Confirmed sleep, mood, symptom and other signals that patterns are built from. This page shows the count, not the individual signals.
            </Level>

            <Level
              level="L4"
              title="Your core profile"
              tone="mint"
              badge={profile ? <span className={`${PILL} ${TONE.mint.chip}`}>{coreSet} of {details.length} set</span> : null}
              extra={
                <>
                  {profileQuery.status === "loading" && <Skeleton className="mt-3 h-40" />}
                  {profileQuery.status === "error" && (
                    <div className="mt-3">
                      <ErrorCard title="Your details didn't load" message={profileQuery.message} onRetry={reloadProfile} inset />
                    </div>
                  )}
                  {profile && (
                    <>
                      <dl className="m-0 mt-3 divide-y-2 divide-line rounded-2xl bg-blush px-4">
                        {details.map(([label, value]) => (
                          <div key={label} className="flex flex-wrap justify-between gap-x-4 gap-y-1 py-3">
                            <dt className="text-body-sm font-extrabold text-ink-soft">{label}</dt>
                            <dd className={`m-0 text-body ${value ? "font-bold text-ink" : "text-muted"}`}>{value || "Not set"}</dd>
                          </div>
                        ))}
                      </dl>
                      <p className="mt-3 text-body-sm text-muted">
                        These are the details saved on your account. Body details such as height and weight goals are set in{" "}
                        <Link href="/fitness/setup" className="font-extrabold text-bubbles-grape-deep underline">
                          Fitness setup
                        </Link>
                        .
                      </p>
                    </>
                  )}
                </>
              }
            >
              The basics saved on your account.
            </Level>
          </ol>
        </section>

        <aside className="space-y-6">
          <section aria-labelledby="privacy-title" className="rounded-3xl bg-tint-mint p-5 sm:p-6">
            <div className="flex items-center gap-2 text-bubbles-mint-deep">
              <span className="shrink-0">
                <Icon id="shield" />
              </span>
              <h2 id="privacy-title" className="text-h3 text-bubbles-mint-deep">
                Your word wins
              </h2>
            </div>
            <ul className="m-0 mt-4 list-none space-y-3 p-0 text-body text-ink">
              <li>Bubbles may notice health details when you chat or log. They stay suggestions until you confirm them.</li>
              <li>If something sounds urgent, Bubbles&apos; built-in safety check answers first and points you to real help.</li>
              <li>Bubbles never diagnoses, and never treats missing data as &ldquo;all clear&rdquo;.</li>
            </ul>
          </section>

          <section aria-labelledby="account-title" className={`${CARD} p-5`}>
            <h2 id="account-title" className="text-h4 text-ink">
              Account
            </h2>
            <div className="mt-3 flex flex-wrap items-center gap-3">
              <Link href="/partner" className={`${BTN_SECONDARY} no-underline`}>
                Partner sharing
              </Link>
              <Link href="/settings" className={`${BTN_SECONDARY} no-underline`}>
                Settings
              </Link>
              <SignOutButton />
            </div>
          </section>
        </aside>
      </div>
    </div>
  );
}

function Level({ level, title, tone, badge, extra, children }: { level: string; title: string; tone: Tone; badge: ReactNode; extra?: ReactNode; children: ReactNode }) {
  return (
    <li className="relative">
      <span className={`absolute -left-[3.25rem] top-0 flex h-10 w-10 items-center justify-center rounded-2xl font-display font-semibold ring-4 ring-white ${TONE[tone].bubble}`}>{level}</span>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="font-display text-h4 text-ink">{title}</h3>
        {badge}
      </div>
      <p className="m-0 mt-1 text-body-sm text-muted">{children}</p>
      {extra}
    </li>
  );
}
