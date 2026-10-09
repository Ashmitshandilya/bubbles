"use client";

import { useId, useMemo, useState } from "react";
import { chartModel, chartSummary, formatWeight, kgToLb, type Units } from "../../app/lib/fitness-calc";
import { formatWhen } from "../../app/lib/dates";
import { BTN_SECONDARY } from "../hub/HubKit";

const W = 600;
const H = 240;

/**
 * Raw weigh-ins (hollow dots, no line) against the smoothed trend (solid line). The two differ by SHAPE as well as colour,
 * a plain-language summary sits beside the picture, and a data table is one button away.
 */
export function WeightTrendChart({ weights, trend, units = "metric" }: {
  weights: { date: string; weight_kg: number }[];
  trend: { date: string; trend_kg: number }[];
  units?: Units;
}) {
  const [table, setTable] = useState(false);
  const summaryId = useId();
  const tableId = useId();
  const model = useMemo(() => chartModel(weights, trend, W, H, undefined, units), [weights, trend, units]);
  const summary = chartSummary(weights, trend, units);
  const unit = units === "imperial" ? "lb" : "kg";
  const trendBy = new Map(trend.map((t) => [t.date.slice(0, 10), t.trend_kg]));

  if (weights.length === 0) return <p className="m-0 rounded-2xl bg-blush p-4 text-body-sm text-muted">{summary}</p>;

  return (
    <figure className="m-0 flex flex-col gap-3">
      <p id={summaryId} className="m-0 text-body-sm text-ink-soft">
        {summary}
      </p>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-labelledby={summaryId} className="h-auto w-full max-w-full overflow-visible">
        {model.ticks.map((t) => (
          <g key={t.y}>
            <line x1={44} x2={W - 12} y1={t.y} y2={t.y} stroke="var(--bubbles-line)" strokeWidth="1" />
            <text x={40} y={t.y + 4} textAnchor="end" fontSize="11" fill="var(--bubbles-ink-soft)">
              {t.label}
            </text>
          </g>
        ))}
        {model.xTicks.map((t) => (
          <text key={t.date} x={t.x} y={H - 8} textAnchor="middle" fontSize="11" fill="var(--bubbles-ink-soft)">
            {formatWhen(t.date)}
          </text>
        ))}
        <path d={model.trendPath} fill="none" stroke="var(--bubbles-grape-deep)" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round" />
        {model.points.filter((p) => p.raw !== null).map((p) => (
          <circle key={p.date} cx={p.x} cy={p.y} r="4.5" fill="var(--bubbles-white)" stroke="var(--bubbles-ink)" strokeWidth="2" />
        ))}
      </svg>
      <ul className="m-0 flex list-none flex-wrap gap-x-5 gap-y-1 p-0 text-body-sm text-ink-soft" aria-label="Chart key">
        <li className="flex items-center gap-2">
          <svg width="22" height="10" aria-hidden="true"><line x1="1" x2="21" y1="5" y2="5" stroke="var(--bubbles-grape-deep)" strokeWidth="3.5" strokeLinecap="round" /></svg>
          Smoothed trend ({unit})
        </li>
        <li className="flex items-center gap-2">
          <svg width="14" height="14" aria-hidden="true"><circle cx="7" cy="7" r="4.5" fill="var(--bubbles-white)" stroke="var(--bubbles-ink)" strokeWidth="2" /></svg>
          Each weigh-in
        </li>
      </ul>
      <div>
        <button type="button" className={BTN_SECONDARY} aria-expanded={table} aria-controls={tableId} onClick={() => setTable((v) => !v)}>
          {table ? "Hide data table" : "Show data table"}
        </button>
      </div>
      {table && (
        <div id={tableId} className="max-h-72 overflow-auto rounded-2xl border-2 border-line">
          <table className="w-full border-collapse text-left text-body-sm">
            <caption className="sr-only">Weigh-ins and smoothed trend</caption>
            <thead className="sticky top-0 bg-blush">
              <tr>
                <th scope="col" className="px-3 py-2">Date</th>
                <th scope="col" className="px-3 py-2">Weigh-in</th>
                <th scope="col" className="px-3 py-2">Trend</th>
              </tr>
            </thead>
            <tbody>
              {[...weights].reverse().map((w) => {
                const t = trendBy.get(w.date.slice(0, 10));
                return (
                  <tr key={w.date} className="border-t border-line">
                    <th scope="row" className="px-3 py-2 font-bold">{formatWhen(w.date, true)}</th>
                    <td className="px-3 py-2">{formatWeight(w.weight_kg, units)}</td>
                    <td className="px-3 py-2">{t == null ? "—" : units === "imperial" ? `${kgToLb(t)} lb` : `${Math.round(t * 10) / 10} kg`}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </figure>
  );
}
