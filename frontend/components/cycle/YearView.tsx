"use client";

// Twelve compact month strips. Each month is one button (opens that month); the shapes match the month grid.

import { useMemo } from "react";
import { buildMonthGrid, monthLabel, yearMonths } from "../../app/lib/cycle-calendar";
import { monthSummary, primaryMarker } from "../../app/lib/cycle-markers";
import type { CalendarDay } from "../../app/lib/cycle-types";
import { MarkerShapes } from "./Marker";

const CELL = 15;

export function YearView({ year, days, weekStart, onOpenMonth, busy }: { year: number; days: Map<string, CalendarDay>; weekStart: 0 | 1; onOpenMonth: (ym: string) => void; busy: boolean }) {
  const months = useMemo(() => yearMonths(year), [year]);
  return (
    <ul className="m-0 grid list-none grid-cols-2 gap-3 p-0 sm:grid-cols-3 lg:grid-cols-4" aria-busy={busy}>
      {months.map((ym) => {
        const rows = buildMonthGrid(ym, weekStart);
        const inMonth = rows.flat().filter((c) => c.inMonth).map((c) => days.get(c.iso)).filter((d): d is CalendarDay => !!d);
        const name = monthLabel(ym, undefined, false);
        return (
          <li key={ym}>
            <button
              type="button"
              onClick={() => onOpenMonth(ym)}
              aria-label={`${monthLabel(ym)}: ${monthSummary(inMonth)}. Open month`}
              className="bubbles-press block min-h-[44px] w-full rounded-3xl border border-line bg-surface p-3 text-left hover:border-line-strong"
            >
              <span className="block font-display text-h4 text-ink">{name}</span>
              <svg viewBox={`0 0 ${7 * CELL} ${rows.length * CELL}`} className="mt-2 block w-full" aria-hidden="true" focusable="false">
                {rows.map((row, r) =>
                  row.map((cell, c) => {
                    if (!cell.inMonth) return null;
                    const kind = primaryMarker(days.get(cell.iso));
                    return (
                      <g key={cell.iso} transform={`translate(${c * CELL + 1.5} ${r * CELL + 1.5})`}>
                        <rect width="12" height="12" rx="3" fill="var(--bubbles-blush)" stroke="var(--bubbles-line)" strokeWidth="0.6" />
                        {kind && <MarkerShapes kind={kind} />}
                      </g>
                    );
                  }),
                )}
              </svg>
              <span className="mt-1 block text-[0.8125rem] font-semibold text-muted">{monthSummary(inMonth)}</span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}
