"use client";

// Date picker + the day's saved log + the form. Used by the Log sheet and the Log tab.

import { useId } from "react";
import { ErrorCard, Skeleton, useBubblesQuery } from "../hub/HubKit";
import { dayPath } from "../../app/lib/cycle-api";
import { isISODate } from "../../app/lib/cycle-calendar";
import { fullDay } from "../../app/lib/cycle-format";
import type { DayResponse } from "../../app/lib/cycle-types";
import { useCycle } from "./CycleStore";
import { DayForm } from "./DayForm";
import { INPUT } from "./fields";

export function DayEditor({ date, onDateChange, onDone }: { date: string; onDateChange: (date: string) => void; onDone?: () => void }) {
  const { today } = useCycle();
  const [query, reload] = useBubblesQuery<DayResponse>(dayPath(date, today));
  const id = useId();
  const loaded = query.status === "ready" && query.data.date === date ? query.data : null;

  return (
    <div className="space-y-5">
      <div>
        <label htmlFor={id} className="block text-body-sm font-extrabold text-ink">Date</label>
        <input
          id={id}
          type="date"
          value={date}
          max={today}
          onChange={(e) => {
            const next = e.target.value;
            if (isISODate(next) && next <= today) onDateChange(next);
          }}
          className={`${INPUT} mt-2 max-w-[16rem]`}
        />
        <p className="m-0 mt-1 text-body-sm text-muted" aria-live="polite">
          {fullDay(date)}
          {loaded?.cycle_day ? ` · Day ${loaded.cycle_day}` : ""}
          {loaded?.phase ? ` · ${loaded.phase.label}` : ""}
        </p>
      </div>

      {query.status === "error" && <ErrorCard inset title="That day didn't load" message={query.message} onRetry={reload} />}
      {!loaded && query.status !== "error" && (
        <div role="status" aria-label="Loading this day" className="space-y-3">
          <Skeleton className="h-28 rounded-3xl" />
          <Skeleton className="h-40 rounded-3xl" />
        </div>
      )}
      {loaded && <DayForm key={date} date={date} initial={loaded} onDone={onDone} />}
    </div>
  );
}
