"use client";

import { useMemo, useState } from "react";
import { BTN_SECONDARY, useBubblesQuery } from "../hub/HubKit";
import { calendarPath } from "../../app/lib/cycle-api";
import { addMonths, defaultWeekStart, monthLabel, monthOf } from "../../app/lib/cycle-calendar";
import { longDay } from "../../app/lib/cycle-format";
import { MARKER_LEGEND } from "../../app/lib/cycle-markers";
import type { CalendarDay, CalendarResponse } from "../../app/lib/cycle-types";
import { useCycle, useReloadOnRev } from "./CycleStore";
import { LengthChart } from "./LengthChart";
import { Marker } from "./Marker";
import { MonthGrid } from "./MonthGrid";
import { Card, PanelError, TabHeading } from "./shared";
import { YearView } from "./YearView";

const NAV = "bubbles-press inline-flex h-11 min-w-[44px] items-center justify-center rounded-full border-2 border-line bg-surface px-3 font-extrabold text-ink hover:border-line-strong";

function toMap(days: CalendarDay[] | undefined): Map<string, CalendarDay> {
  return new Map((days ?? []).map((d) => [d.date, d]));
}

export function CalendarTab() {
  const { today, openLog, overview, announce } = useCycle();
  const [view, setView] = useState<"month" | "year">("month");
  const [ym, setYm] = useState(monthOf(today));
  const [selected, setSelected] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [weekStart] = useState(() => defaultWeekStart());

  function select(iso: string) {
    setSelected(iso);
    if (iso > today) {
      const text = `${longDay(iso)} is in the future, so there is nothing to log yet. Marks on future days are estimates.`;
      setNote(text);
      announce(text);
      return;
    }
    setNote("");
    openLog(iso);
  }

  const year = Number(ym.slice(0, 4));

  return (
    <div className="space-y-5">
      <TabHeading id="cycle-h-calendar" title="Calendar">Logged days are solid; predicted days are outlined. All predictions are estimates.</TabHeading>

      <Card>
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <button type="button" aria-label={view === "month" ? "Previous month" : "Previous year"} className={NAV} onClick={() => setYm(addMonths(ym, view === "month" ? -1 : -12))}>
            <span aria-hidden="true">‹</span>
          </button>
          <h3 className="m-0 min-w-[8rem] flex-1 text-center font-display text-h3 text-ink" aria-live="polite">
            {view === "month" ? monthLabel(ym) : year}
          </h3>
          <button type="button" aria-label={view === "month" ? "Next month" : "Next year"} className={NAV} onClick={() => setYm(addMonths(ym, view === "month" ? 1 : 12))}>
            <span aria-hidden="true">›</span>
          </button>
          <button type="button" className={BTN_SECONDARY} onClick={() => { setYm(monthOf(today)); setView("month"); }}>Today</button>
          <div className="flex gap-1" role="group" aria-label="Calendar view">
            {(["month", "year"] as const).map((v) => (
              <button
                key={v}
                type="button"
                aria-pressed={view === v}
                onClick={() => setView(v)}
                className={`bubbles-press min-h-[44px] rounded-full border-2 px-4 text-body-sm font-extrabold ${view === v ? "border-bubbles-grape bg-tint-grape text-bubbles-grape-deep" : "border-line bg-surface text-ink-soft"}`}
              >
                {view === v && <span aria-hidden="true">✓ </span>}
                {v === "month" ? "Month" : "Year"}
              </button>
            ))}
          </div>
        </div>

        {view === "month" ? (
          <MonthPane ym={ym} weekStart={weekStart} selected={selected} onSelect={select} onMonthChange={setYm} />
        ) : (
          <YearPane year={year} weekStart={weekStart} onOpenMonth={(m) => { setYm(m); setView("month"); }} />
        )}
        {note && <p role="status" className="m-0 mt-3 rounded-2xl bg-tint-sky px-4 py-3 text-body-sm font-bold text-bubbles-sky-deep">{note}</p>}
        <Legend />
      </Card>

      <Card labelledBy="cycle-lengths-title">
        <h3 id="cycle-lengths-title" className="m-0 mb-3 font-display text-h3 text-ink">Your cycle lengths</h3>
        {overview && overview.stats.recent_lengths.length > 0 ? (
          <LengthChart lengths={overview.stats.recent_lengths} average={overview.stats.average_length} />
        ) : (
          <p className="m-0 text-body text-muted">After your first full cycle is logged, its length appears here. Anything from 21 to 35 days is common.</p>
        )}
      </Card>
    </div>
  );
}

function MonthPane({ ym, weekStart, selected, onSelect, onMonthChange }: { ym: string; weekStart: 0 | 1; selected: string | null; onSelect: (iso: string) => void; onMonthChange: (ym: string) => void }) {
  const { today, rev } = useCycle();
  const [query, reload] = useBubblesQuery<CalendarResponse>(calendarPath({ month: ym }, today));
  useReloadOnRev(reload, rev);
  const days = useMemo(() => toMap(query.status === "ready" ? query.data.days : undefined), [query]);
  const busy = query.status === "loading" || (query.status === "ready" && query.data.month !== ym);
  return (
    <>
      {query.status === "error" && <div className="mb-3"><PanelError title="The calendar didn't load" message={query.message} onRetry={reload} /></div>}
      <MonthGrid ym={ym} weekStart={weekStart} days={days} today={today} selected={selected} busy={busy} onSelect={onSelect} onMonthChange={onMonthChange} />
    </>
  );
}

function YearPane({ year, weekStart, onOpenMonth }: { year: number; weekStart: 0 | 1; onOpenMonth: (ym: string) => void }) {
  const { today, rev } = useCycle();
  const [query, reload] = useBubblesQuery<CalendarResponse>(calendarPath({ year }, today));
  useReloadOnRev(reload, rev);
  const days = useMemo(() => toMap(query.status === "ready" ? query.data.days : undefined), [query]);
  return (
    <>
      {query.status === "error" && <div className="mb-3"><PanelError title="The year didn't load" message={query.message} onRetry={reload} /></div>}
      <YearView year={year} days={days} weekStart={weekStart} onOpenMonth={onOpenMonth} busy={query.status === "loading"} />
    </>
  );
}

function Legend() {
  return (
    <ul className="m-0 mt-4 flex list-none flex-wrap gap-x-4 gap-y-2 p-0 text-chip font-bold text-ink-soft" aria-label="Legend">
      {MARKER_LEGEND.map((l) => (
        <li key={l.kind} className="flex items-center gap-1.5"><Marker kind={l.kind} size={14} />{l.label}</li>
      ))}
      <li className="flex items-center gap-1.5"><span aria-hidden="true" className="inline-block h-3.5 w-3.5 rounded border-2 border-ink" />Today</li>
    </ul>
  );
}
