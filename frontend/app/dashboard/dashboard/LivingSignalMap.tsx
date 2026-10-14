"use client";

import type { LivingMapData } from "./types";

const METRIC_LABEL: Record<string, string> = {
  sleep_hours: "Sleep",
  water_ml: "Water",
  activity_minutes: "Activity",
  weight_kg: "Weight",
  mood: "Mood",
};

const label = (raw: string) => METRIC_LABEL[raw] ?? raw.replaceAll("_", " ").replace(/^./, (c) => c.toUpperCase());

/** What Bubbles' intelligence layer extracted from chat (GET /intelligence/living-map). */
export function LivingSignalMap({ state, map, onRetry }: { state: "loading" | "error" | "ready"; map: LivingMapData | null; onRetry: () => void }) {
  return (
    <section aria-labelledby="today-living-map" className="flex min-w-0 flex-col gap-4 rounded-[24px] border border-line bg-surface p-5 shadow-sm">
      <div className="flex flex-col gap-1">
        <h2 id="today-living-map" className="m-0 font-display text-xl font-semibold">What Bubbles picked up from your chats</h2>
        <p className="m-0 font-mono text-xs text-ink-soft">from your chats with Bubbles, last 14 days</p>
      </div>

      {state === "loading" && <div className="bubbles-skeleton bubbles-skeleton-card h-24" aria-label="Loading signals from your chats" />}

      {state === "error" && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-[20px] bg-blush p-4">
          <p className="m-0 text-[0.9375rem] font-bold">Bubbles couldn&apos;t load this right now.</p>
          <button type="button" onClick={onRetry} className="bubbles-press min-h-[44px] rounded-full border border-line-strong bg-surface px-4 text-sm font-extrabold">Try again</button>
        </div>
      )}

      {state === "ready" && map && (
        <>
          <dl className="m-0 flex flex-wrap gap-x-8 gap-y-3 border-y border-line py-4">
            {[
              ["Signals mentioned", map.observed_signal_count],
              ["Changes vs usual", map.baseline_change_count],
              ["Not mentioned", map.data_gap_count],
            ].map(([name, value]) => (
              <div key={name} className="flex min-w-0 items-baseline gap-2">
                <dt className="order-2 text-sm font-medium text-ink-soft">{name}</dt>
                <dd className="order-1 m-0 font-display text-[2rem] leading-none">{value}</dd>
              </div>
            ))}
          </dl>

          {map.signals.length > 0 ? (
            <ul className="m-0 flex list-none flex-col gap-2 p-0">
              {map.signals.slice(0, 4).map((signal, index) => (
                <li key={`${signal.label}-${index}`} className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-[20px] border border-line px-4 py-3">
                  <strong className="text-[0.9375rem]">{label(signal.label)}</strong>
                  {signal.direction && <span className="rounded-full bg-tint-grape px-2.5 py-0.5 text-xs font-extrabold text-bubbles-grape-deep">{signal.direction}</span>}
                  <span className="rounded-full bg-tint-sun px-2.5 py-0.5 text-xs font-extrabold text-bubbles-sun-deep">{signal.confidence} confidence</span>
                  <span className="w-full text-sm text-ink-soft">{signal.evidence}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="m-0 text-[0.9375rem] leading-relaxed text-ink-soft">No changes spotted in your chats yet. Tell Bubbles how you slept or how you feel and it will start to notice.</p>
          )}

          {map.data_gaps.length > 0 && (
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-bold text-ink-soft">Not mentioned lately:</span>
              {map.data_gaps.map((gap) => (
                <span key={gap} className="rounded-full border border-dashed border-[#CDB9DA] px-2.5 py-0.5 text-xs font-extrabold text-bubbles-sky-deep">{label(gap)}</span>
              ))}
            </div>
          )}

          <p className="m-0 text-[0.8125rem] leading-relaxed text-ink-soft">{map.interpretation_policy}</p>
        </>
      )}
    </section>
  );
}
