"use client";

import { livingSignalLine, plainMetric } from "./today";
import type { LivingMapData } from "./types";

const label = (raw: string) => plainMetric(raw).replace(/^./, (c) => c.toUpperCase());

/** What Bubbles' intelligence layer extracted from chat (GET /intelligence/living-map). */
export function LivingSignalMap({ state, map, onRetry }: { state: "loading" | "error" | "ready"; map: LivingMapData | null; onRetry: () => void }) {
  return (
    <section aria-labelledby="today-living-map" className="flex min-w-0 flex-col gap-4 rounded-[24px] border-2 border-line bg-surface p-5">
      <div className="flex flex-col gap-1">
        <h2 id="today-living-map" className="m-0 font-display text-h3">What Bubbles picked up from your chats</h2>
        <p className="m-0 text-body-sm font-semibold text-ink-soft">From your conversations with Bubbles · last 14 days</p>
      </div>

      {state === "loading" && <div className="bubbles-skeleton h-24 rounded-[18px]" aria-label="Loading signals from your chats" />}

      {state === "error" && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-[18px] bg-blush p-4">
          <p className="m-0 text-body-sm font-bold">Bubbles couldn&apos;t load this right now.</p>
          <button type="button" onClick={onRetry} className="bubbles-press min-h-[44px] rounded-full border-2 border-ink bg-surface px-4 text-body-sm font-extrabold">Try again</button>
        </div>
      )}

      {state === "ready" && map && (
        <>
          <dl className="m-0 grid grid-cols-3 gap-2.5">
            {[
              ["Signals mentioned", map.observed_signal_count],
              ["Changes vs usual", map.baseline_change_count],
              ["Not mentioned", map.data_gap_count],
            ].map(([name, value]) => (
              <div key={name} className="flex min-w-0 flex-col gap-0.5 rounded-[18px] bg-blush p-3">
                <dt className="order-2 text-chip font-bold text-ink-soft">{name}</dt>
                <dd data-private className="order-1 m-0 font-display text-metric">{value}</dd>
              </div>
            ))}
          </dl>

          {map.signals.length > 0 ? (
            <ul className="m-0 flex list-none flex-col gap-2 p-0">
              {map.signals.slice(0, 4).map((signal, index) => (
                <li key={`${signal.label}-${index}`} data-private className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-[18px] bg-blush px-4 py-3">
                  <strong className="text-body-sm font-extrabold">{label(signal.label)}</strong>
                  <span className="rounded-full bg-surface px-2.5 py-0.5 text-chip font-extrabold text-ink-soft">{signal.confidence} confidence</span>
                  <span className="w-full text-body-sm text-ink-soft">{livingSignalLine(signal)}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="m-0 text-body-sm leading-relaxed text-ink-soft">No changes spotted in your chats yet. Tell Bubbles how you slept or how you feel and it will start to notice.</p>
          )}

          {map.data_gaps.length > 0 && (
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-body-sm font-bold text-ink-soft">Not mentioned lately:</span>
              {map.data_gaps.map((gap) => (
                <span key={gap} className="rounded-full border-2 border-dashed border-line-sky-strong px-2.5 py-0.5 text-chip font-extrabold text-bubbles-sky-deep">{label(gap)}</span>
              ))}
            </div>
          )}

          <p className="m-0 text-chip leading-relaxed text-ink-soft">{map.interpretation_policy}</p>
        </>
      )}
    </section>
  );
}
