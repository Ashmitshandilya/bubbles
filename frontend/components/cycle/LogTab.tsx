"use client";

import { useMemo, useState } from "react";
import { useBubblesQuery } from "../hub/HubKit";
import { calendarPath } from "../../app/lib/cycle-api";
import { addMonths, monthOf } from "../../app/lib/cycle-calendar";
import { fmtDay } from "../../app/lib/cycle-format";
import type { CalendarDay, CalendarResponse } from "../../app/lib/cycle-types";
import { useCycle, useReloadOnRev } from "./CycleStore";
import { DayEditor } from "./DayEditor";
import { Card, TabHeading } from "./shared";

function describe(d: CalendarDay): string {
  const parts: string[] = [];
  if (d.period_start) parts.push("period started");
  else if (d.flow && d.flow !== "none") parts.push(`flow ${d.flow}`);
  if (d.pain_level !== null) parts.push(`pain ${d.pain_level} of 10`);
  if (d.symptom_count) parts.push(`${d.symptom_count} ${d.symptom_count === 1 ? "symptom" : "symptoms"}`);
  return parts.join(" · ") || "logged";
}

export function LogTab() {
  const { today } = useCycle();
  const [date, setDate] = useState(today);
  return (
    <div className="space-y-5">
      <TabHeading id="cycle-h-log" title="Log">Add or edit any day up to today. Skip whatever does not apply.</TabHeading>
      <div className="grid items-start gap-5 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <Card labelledBy="cycle-h-log-form">
          <h3 id="cycle-h-log-form" className="sr-only">Day log form</h3>
          <DayEditor date={date} onDateChange={setDate} />
        </Card>
        <Recent selected={date} onPick={(iso) => { setDate(iso); window.scrollTo({ top: 0 }); }} />
      </div>
    </div>
  );
}

function Recent({ selected, onPick }: { selected: string; onPick: (iso: string) => void }) {
  const { today, rev } = useCycle();
  const [current, reloadCurrent] = useBubblesQuery<CalendarResponse>(calendarPath({ month: monthOf(today) }, today));
  const [previous, reloadPrevious] = useBubblesQuery<CalendarResponse>(calendarPath({ month: addMonths(monthOf(today), -1) }, today));
  useReloadOnRev(reloadCurrent, rev);
  useReloadOnRev(reloadPrevious, rev);

  const logged = useMemo(() => {
    const all = [...(current.status === "ready" ? current.data.days : []), ...(previous.status === "ready" ? previous.data.days : [])];
    return all.filter((d) => d.has_log && d.date <= today).sort((a, b) => b.date.localeCompare(a.date)).slice(0, 8);
  }, [current, previous, today]);
  const loading = current.status === "loading" || previous.status === "loading";

  return (
    <Card labelledBy="cycle-recent-title">
      <h3 id="cycle-recent-title" className="m-0 font-display text-h3 text-ink">Recent logs</h3>
      {loading && logged.length === 0 && <p className="m-0 mt-2 text-body text-muted" role="status">Loading…</p>}
      {!loading && logged.length === 0 && <p className="m-0 mt-2 text-body text-muted">Nothing logged in the last two months yet.</p>}
      {logged.length > 0 && (
        <ul className="m-0 mt-3 list-none space-y-2 p-0">
          {logged.map((d) => (
            <li key={d.date}>
              <button
                type="button"
                onClick={() => onPick(d.date)}
                aria-current={d.date === selected ? "true" : undefined}
                className={`bubbles-press flex min-h-[44px] w-full flex-col rounded-2xl border px-4 py-2 text-left ${d.date === selected ? "border-bubbles-grape bg-tint-grape" : "border-line bg-surface"}`}
              >
                <span className="text-body-sm font-extrabold text-ink">{fmtDay(d.date, { weekday: "short", day: "numeric", month: "short" })}</span>
                <span className="text-body-sm text-muted">{describe(d)}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
