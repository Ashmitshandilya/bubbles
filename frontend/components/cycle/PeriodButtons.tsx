"use client";

// One-tap "Period started" / "Period ended", with an "on another day" date for backfilling. Future dates are blocked.

import { useId, useState } from "react";
import { BTN_PRIMARY, BTN_SECONDARY } from "../hub/HubKit";
import { isISODate } from "../../app/lib/cycle-calendar";
import { longDay } from "../../app/lib/cycle-format";
import type { DayResponse } from "../../app/lib/cycle-types";
import { useCycle } from "./CycleStore";
import { INPUT } from "./fields";
import { FlagList, InlineError, SafetyAlert } from "./shared";

export function PeriodButtons({ onResult }: { onResult?: (r: DayResponse) => void }) {
  const { today, postPeriod, announce } = useCycle();
  const [other, setOther] = useState(false);
  const [date, setDate] = useState(today);
  const [busy, setBusy] = useState<"start" | "end" | null>(null);
  const [error, setError] = useState("");
  const [done, setDone] = useState("");
  const [last, setLast] = useState<DayResponse | null>(null);
  const dateId = useId();

  async function send(kind: "start" | "end") {
    const day = other ? date : today;
    if (!isISODate(day) || day > today) {
      setError("Pick a date up to today.");
      return;
    }
    setBusy(kind);
    setError("");
    const result = await postPeriod(kind, day === today ? null : day);
    setBusy(null);
    if (!result.ok) {
      setError(result.error);
      return;
    }
    const text = `Period ${kind === "start" ? "start" : "end"} saved for ${day === today ? "today" : longDay(day)}.`;
    setDone(text);
    announce(text);
    setLast(result.data);
    onResult?.(result.data);
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-3">
        <button type="button" disabled={busy !== null} onClick={() => send("start")} className={BTN_PRIMARY}>
          {busy === "start" ? "Saving…" : "Period started"}
        </button>
        <button type="button" disabled={busy !== null} onClick={() => send("end")} className={BTN_SECONDARY}>
          {busy === "end" ? "Saving…" : "Period ended"}
        </button>
        <button type="button" aria-expanded={other} onClick={() => setOther((v) => !v)} className="min-h-[44px] rounded-full px-3 text-body-sm font-extrabold text-bubbles-pink-ink underline">
          On another day
        </button>
      </div>
      {other && (
        <div>
          <label htmlFor={dateId} className="block text-body-sm font-extrabold text-ink">Which day? A past date is fine.</label>
          <input id={dateId} type="date" value={date} max={today} onChange={(e) => e.target.value && setDate(e.target.value)} className={`${INPUT} mt-2 max-w-[16rem]`} />
          <p className="m-0 mt-1 text-body-sm text-muted">The two buttons above will use this date.</p>
        </div>
      )}
      {error && <InlineError message={error} />}
      <p className="m-0 text-body-sm font-bold text-bubbles-mint-deep" aria-hidden={done ? undefined : true}>{done}</p>
      {last?.safety && <SafetyAlert safety={last.safety} />}
      {last && last.flags.length > 0 && <FlagList flags={last.flags} />}
    </div>
  );
}
