"use client";

// Today-first quick-log grid for the Track hub. Each daily tracker shows when it was last logged and a 7-day rhythm.
// Everything is read from GET /health/<slug> (the same call the tracker page makes). Nothing is scored or guessed:
// a tracker with no entries says so, and one that could not be read says that instead.

import Link from "next/link";
import { useEffect, useState } from "react";
import { useApi } from "../../components/Providers";
import { BTN_SECONDARY, Icon, Skeleton, TONE, type Tone } from "../../components/hub/HubKit";
import { readEntries } from "../lib/api-adapters";
import { PULSE_WINDOW_DAYS, buildPulse, lastLoggedText, rollupToday, type Pulse } from "../lib/track-pulse";

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
  const { fetchBubbles, reconnects, dataVersion } = useApi();
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
  }, [key, fetchBubbles, tick, reconnects, dataVersion]);

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
        <h2 id="daily-title" className="sr-only">
          Quick log
        </h2>
        <ul className="bubbles-stagger m-0 flex list-none flex-col p-0">
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

function TodayStrip({ items, pulses, onRetry }: { items: QuickItem[]; pulses: PulseMap | null; onRetry: () => void }) {
  if (!pulses) {
    return <Skeleton className="h-[72px] rounded-2xl" />;
  }
  const roll = rollupToday(items.map((i) => ({ label: i.title, pulse: pulses[i.id] ?? null })));

  if (roll.checked === 0) {
    return (
      <div role="status" className="flex flex-wrap items-center gap-3 py-2">
        <p className="m-0 min-w-[12rem] flex-1 text-body-sm text-muted">
          Couldn&apos;t check today&apos;s logs just now.
        </p>
        <button type="button" onClick={onRetry} className={BTN_SECONDARY}>
          Try again
        </button>
      </div>
    );
  }

  const openItems = items.filter((i) => roll.open.includes(i.title));
  return (
    <section aria-labelledby="today-title" className="border-b border-[color:var(--hairline)] pb-5">
      <h2 id="today-title" className="m-0 font-display text-h4 text-ink">
        Today: {roll.done.length} of {roll.checked} logged
      </h2>
      {openItems.length > 0 ? (
        <div className="mt-3">
          <ul className="m-0 flex list-none flex-wrap gap-2 p-0">
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
        <p className="m-0 mt-1 text-body-sm text-muted">All done for today.</p>
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

  let hint = "";
  if (ownData) hint = "";
  else if (pulses === null) hint = "Checking…";
  else if (!pulse) hint = "Couldn't check";
  else hint = lastLoggedText(pulse);

  return (
    <div className="flex items-center gap-3 border-b border-[color:var(--hairline)] py-3">
      <span aria-hidden="true" className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full ${TONE[item.tone].bubble}`}>
        <Icon id={item.id} />
      </span>
      <div className="min-w-0 flex-1">
        <Link href={`/${item.id}`} className="-my-[11px] inline-block py-[11px] font-display text-h4 text-ink no-underline hover:underline">
          {item.title}
        </Link>
        {hint && (
          <p className={`m-0 truncate text-chip font-bold ${doneToday ? TONE[item.tone].ink : "text-muted"}`}>{hint}</p>
        )}
      </div>
      <Link href={ownData ? `/${item.id}` : `/${item.id}?log=1`} className="pearl-link no-underline" style={{ textDecoration: "none" }}>
        {ownData ? "Open" : doneToday ? "Log more" : "Log"}
      </Link>
    </div>
  );
}
