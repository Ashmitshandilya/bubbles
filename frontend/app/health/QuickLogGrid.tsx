"use client";

// Today-first quick-log grid for the Track hub. Each daily tracker shows when it was last logged and a 7-day rhythm.
// Everything is read from GET /health/<slug> (the same call the tracker page makes). Nothing is scored or guessed:
// a tracker with no entries says so, and one that could not be read says that instead.

import Link from "next/link";
import { useEffect, useState } from "react";
import { useApi } from "../../components/Providers";
import { BTN_PRIMARY, BTN_SECONDARY, CARD, Icon, Skeleton, TONE, type Tone } from "../../components/hub/HubKit";
import { readEntries } from "../lib/api-adapters";
import { PULSE_WINDOW_DAYS, buildPulse, checkIns, lastLoggedText, recentText, rollupToday, streakText, weekText, type Pulse } from "../lib/track-pulse";

export interface QuickItem {
  id: string;
  title: string;
  why: string;
  tone: Tone;
}

/** Cycle keeps its own page and data (/cycle/*), so the hub links to it without reading /health/cycle. */
const OWN_DATA = new Set(["cycle"]);

type PulseMap = Record<string, Pulse | null>; // null = could not be read

function useTrackerPulses(slugs: string[]) {
  const { fetchBubbles, reconnects } = useApi();
  const [pulses, setPulses] = useState<PulseMap | null>(null);
  const [tick, setTick] = useState(0);
  const key = slugs.join(",");

  useEffect(() => {
    let alive = true;
    (async () => {
      const found = await Promise.all(
        key.split(",").map(async (slug) => {
          try {
            const response = await fetchBubbles(`/health/${slug}?days=${PULSE_WINDOW_DAYS}`);
            if (!response.ok) return [slug, null] as const;
            const payload: { entries?: unknown } | null = await response.json().catch(() => null);
            return [slug, buildPulse(readEntries(payload?.entries))] as const;
          } catch {
            return [slug, null] as const;
          }
        }),
      );
      if (alive) setPulses(Object.fromEntries(found));
    })();
    return () => {
      alive = false;
    };
  }, [key, fetchBubbles, tick, reconnects]);

  // Coming back to this tab after logging elsewhere: refresh the hints.
  useEffect(() => {
    const onShow = () => {
      if (document.visibilityState === "visible") setTick((t) => t + 1);
    };
    document.addEventListener("visibilitychange", onShow);
    return () => document.removeEventListener("visibilitychange", onShow);
  }, []);

  return { pulses, retry: () => setTick((t) => t + 1) };
}

export function QuickLog({ items }: { items: QuickItem[] }) {
  const tracked = items.filter((i) => !OWN_DATA.has(i.id));
  const { pulses, retry } = useTrackerPulses(tracked.map((i) => i.id));

  return (
    <div className="space-y-6">
      <TodayStrip items={tracked} pulses={pulses} onRetry={retry} />
      <section aria-labelledby="daily-title">
        <h2 id="daily-title" className="text-h3 text-ink">
          Quick log
        </h2>
        <ul className="bubbles-stagger m-0 mt-3 grid list-none grid-cols-1 gap-3 p-0 sm:grid-cols-2 xl:grid-cols-3">
          {items.map((item) => (
            <li key={item.id}>
              <Tile item={item} pulses={OWN_DATA.has(item.id) ? undefined : pulses} />
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

/** Calm check-in days: filled dot = something was logged, dashed = a gap. The sentence carries the meaning, the dots are decoration. */
function CheckInRow({ pulses }: { pulses: Array<Pulse | null> }) {
  const c = checkIns(pulses);
  const partial = c.readable < pulses.length;
  const text = streakText(c, partial);
  if (!text) return null;
  return (
    <div data-private className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-2">
      <p className="m-0 text-body-sm font-bold text-ink-soft">{text}</p>
      <span className="flex items-center gap-1" aria-hidden="true">
        {c.recent.map((on, i) => (
          <span
            key={i}
            className={`h-2.5 w-2.5 rounded-full ${on ? "bg-bubbles-grape" : "border border-dashed border-line-strong"} ${i === c.recent.length - 1 ? "ring-2 ring-bubbles-grape/30 ring-offset-1" : ""}`}
          />
        ))}
      </span>
      <span className="sr-only">{recentText(c, partial)}</span>
    </div>
  );
}

function TodayStrip({ items, pulses, onRetry }: { items: QuickItem[]; pulses: PulseMap | null; onRetry: () => void }) {
  if (!pulses) {
    return <Skeleton className="h-[112px] rounded-3xl" />;
  }
  const roll = rollupToday(items.map((i) => ({ label: i.title, pulse: pulses[i.id] ?? null })));

  if (roll.checked === 0) {
    return (
      <div role="status" className={`${CARD} flex flex-wrap items-center gap-3 p-5`}>
        <p className="m-0 min-w-[12rem] flex-1 text-body-sm text-muted">
          Bubbles couldn&apos;t check today&apos;s logs just now. The tiles below still open every tracker.
        </p>
        <button type="button" onClick={onRetry} className={BTN_SECONDARY}>
          Try again
        </button>
      </div>
    );
  }

  const openItems = items.filter((i) => roll.open.includes(i.title));
  return (
    <section aria-labelledby="today-title" className={`${CARD} p-5`}>
      <h2 id="today-title" className="text-h3 text-ink">
        Today
      </h2>
      <p className="m-0 mt-1 font-display text-h4 text-ink">
        {roll.done.length} of {roll.checked} daily signals logged
      </p>
      <CheckInRow pulses={items.map((i) => pulses[i.id] ?? null)} />
      {openItems.length > 0 ? (
        <div className="mt-3">
          <p className="m-0 text-body-sm font-bold text-muted">Still open today. Tap one to log it.</p>
          <ul className="m-0 mt-2 flex list-none flex-wrap gap-2 p-0">
            {openItems.map((i) => (
              <li key={i.id}>
                <Link
                  href={`/${i.id}?log=1`}
                  className={`bubbles-press inline-flex min-h-[44px] items-center rounded-full px-4 text-body-sm font-extrabold no-underline ${TONE[i.tone].chip}`}
                >
                  {i.title}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <p className="m-0 mt-1 text-body-sm text-muted">Every signal that could be checked has an entry today.</p>
      )}
      {roll.unknown.length > 0 && (
        <p className="m-0 mt-3 text-body-sm text-muted">
          Couldn&apos;t check {roll.unknown.join(", ")}.{" "}
          <button type="button" onClick={onRetry} className="font-extrabold text-bubbles-pink-ink underline">
            Try again
          </button>
        </p>
      )}
    </section>
  );
}

function Tile({ item, pulses }: { item: QuickItem; pulses: PulseMap | null | undefined }) {
  const ownData = pulses === undefined;
  const pulse = pulses ? (pulses[item.id] ?? null) : null;
  const doneToday = pulse?.lastAgo === 0;

  let hint: string;
  if (ownData) hint = "Phases and estimates live on the cycle page";
  else if (pulses === null) hint = "Checking your recent logs";
  else if (!pulse) hint = "Couldn't check recent logs";
  else hint = lastLoggedText(pulse);

  return (
    <div className={`${CARD} flex h-full flex-col gap-3 p-4`}>
      <div className="flex items-start gap-3">
        <span className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl ${TONE[item.tone].bubble}`}>
          <Icon id={item.id} />
        </span>
        <div className="min-w-0 flex-1">
          <Link href={`/${item.id}`} className="font-display text-h4 text-ink no-underline hover:underline">
            {item.title}
          </Link>
          <p className={`m-0 text-body-sm font-bold ${doneToday ? TONE[item.tone].ink : "text-muted"}`}>
            {hint}
          </p>
        </div>
      </div>

      {!ownData && pulses === null && <Skeleton className="h-10 rounded-xl" />}
      {pulse && <Rhythm pulse={pulse} tone={item.tone} />}
      {ownData && <p className="m-0 flex-1 text-body-sm text-muted">{item.why}</p>}

      <Link
        href={ownData ? `/${item.id}` : `/${item.id}?log=1`}
        className={`${doneToday || ownData ? BTN_SECONDARY : BTN_PRIMARY} mt-auto w-full no-underline`}
      >
        {ownData ? "Open cycle" : doneToday ? `Log more ${item.title.toLowerCase()}` : `Log ${item.title.toLowerCase()}`}
      </Link>
    </div>
  );
}

/** 7 small bars, today on the right. A day with no entry is a dashed gap, not a zero. The text carries the meaning. */
function Rhythm({ pulse, tone }: { pulse: Pulse; tone: Tone }) {
  const max = Math.max(2, ...pulse.week);
  return (
    <div>
      <div aria-hidden="true" className="flex h-8 items-end gap-1">
        {pulse.week.map((n, i) =>
          n > 0 ? (
            <span
              key={i}
              className={`block w-full rounded-md ${TONE[tone].dot} ${i === 6 ? "" : "opacity-60"}`}
              style={{ height: `${Math.max(25, (n / max) * 100)}%` }}
            />
          ) : (
            <span key={i} className="block h-1.5 w-full rounded-full border-2 border-dashed border-line-strong" />
          ),
        )}
      </div>
      <p className="m-0 mt-1 text-[0.75rem] font-bold text-muted">{weekText(pulse)}</p>
    </div>
  );
}
