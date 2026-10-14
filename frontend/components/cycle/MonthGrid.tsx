"use client";

// Month calendar as an ARIA grid: one tab stop (roving tabindex), arrow keys move by day/week, Home/End jump to the
// week's ends, PageUp/PageDown change month. Enter or Space opens the day. Padding days are inert.

import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { addDays, addMonths, buildMonthGrid, daysInMonth, monthOf, parseMonth, toISO, weekdayLabels, weekdayIndex } from "../../app/lib/cycle-calendar";
import { dayAriaLabel } from "../../app/lib/cycle-format";
import { markersFor } from "../../app/lib/cycle-markers";
import type { CalendarDay } from "../../app/lib/cycle-types";
import { Marker } from "./Marker";

export function MonthGrid({
  ym, weekStart, days, today, selected, busy, onSelect, onMonthChange,
}: {
  ym: string;
  weekStart: 0 | 1;
  days: Map<string, CalendarDay>;
  today: string;
  selected: string | null;
  busy: boolean;
  onSelect: (iso: string) => void;
  onMonthChange: (ym: string) => void;
}) {
  const rows = useMemo(() => buildMonthGrid(ym, weekStart), [ym, weekStart]);
  const labels = useMemo(() => weekdayLabels(weekStart), [weekStart]);
  const [focusIso, setFocusIso] = useState(today);
  const shouldFocus = useRef(false);
  const gridRef = useRef<HTMLTableElement>(null);

  const fallback = monthOf(today) === ym ? today : toISO(parseMonth(ym)?.y ?? 2000, parseMonth(ym)?.m ?? 1, 1);
  const tabbable = monthOf(focusIso) === ym ? focusIso : fallback;

  useEffect(() => {
    if (!shouldFocus.current) return;
    const el = gridRef.current?.querySelector<HTMLButtonElement>(`button[data-iso="${tabbable}"]`);
    if (el) {
      shouldFocus.current = false;
      el.focus();
    }
  }, [tabbable, ym, rows]);

  function move(to: string) {
    shouldFocus.current = true;
    setFocusIso(to);
    if (monthOf(to) !== ym) onMonthChange(monthOf(to));
  }

  function onKeyDown(event: KeyboardEvent, iso: string) {
    const offsetInWeek = (weekdayIndex(iso) - weekStart + 7) % 7;
    const p = parseMonth(ym);
    let to: string | null = null;
    switch (event.key) {
      case "ArrowLeft": to = addDays(iso, -1); break;
      case "ArrowRight": to = addDays(iso, 1); break;
      case "ArrowUp": to = addDays(iso, -7); break;
      case "ArrowDown": to = addDays(iso, 7); break;
      case "Home": to = addDays(iso, -offsetInWeek); break;
      case "End": to = addDays(iso, 6 - offsetInWeek); break;
      case "PageUp":
      case "PageDown": {
        if (!p) break;
        const next = addMonths(ym, event.key === "PageUp" ? -1 : 1);
        const np = parseMonth(next);
        if (np) to = toISO(np.y, np.m, Math.min(Number(iso.slice(8)), daysInMonth(np.y, np.m)));
        break;
      }
    }
    if (to) {
      event.preventDefault();
      move(to);
    }
  }

  return (
    <table ref={gridRef} role="grid" aria-busy={busy} aria-label="Cycle calendar" className="w-full table-fixed border-separate border-spacing-1">
      <thead>
        <tr>
          {labels.map((l) => (
            <th key={l.long} scope="col" abbr={l.long} className="pb-1 text-center text-[0.75rem] font-extrabold text-muted">
              {l.short}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row[0].iso}>
            {row.map((cell) => {
              if (!cell.inMonth) {
                return <td key={cell.iso} className="h-14 rounded-2xl text-center align-top text-body-sm text-ink-faint opacity-50" aria-hidden="true">{cell.day}</td>;
              }
              const day = days.get(cell.iso);
              const markers = markersFor(day);
              const isToday = cell.iso === today;
              const isSelected = cell.iso === selected;
              return (
                <td key={cell.iso} className="p-0 align-top">
                  <button
                    type="button"
                    data-iso={cell.iso}
                    tabIndex={cell.iso === tabbable ? 0 : -1}
                    aria-current={isToday ? "date" : undefined}
                    aria-label={dayAriaLabel(cell.iso, day)}
                    onClick={() => {
                      setFocusIso(cell.iso);
                      onSelect(cell.iso);
                    }}
                    onKeyDown={(e) => onKeyDown(e, cell.iso)}
                    className={`flex h-14 min-h-[44px] w-full flex-col items-center justify-start gap-0.5 rounded-2xl border pt-1 text-body-sm ${
                      day?.period === "logged" ? "bg-tint-pink" : "bg-surface"
                    } ${isToday ? "border-ink font-extrabold" : "border-line"} ${isSelected ? "outline outline-[3px] outline-offset-1 outline-bubbles-grape" : ""} ${
                      day?.is_future ? "text-ink-soft" : "text-ink"
                    }`}
                  >
                    <span aria-hidden="true">{cell.day}</span>
                    <span className="flex min-h-3 flex-wrap items-center justify-center gap-px" aria-hidden="true">
                      {markers.slice(0, 3).map((k) => <Marker key={k} kind={k} size={11} />)}
                    </span>
                  </button>
                </td>
              );
            })}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
