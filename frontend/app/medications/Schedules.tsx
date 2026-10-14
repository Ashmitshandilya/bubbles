"use client";

// Create / edit schedules, the schedule list, and the adherence summary.

import { useEffect, useState } from "react";
import { BTN_PRIMARY, BTN_SECONDARY, PILL } from "../../components/hub/HubKit";
import { Choices, DateField, LogSheet, Stepper, TextField } from "../../components/tracking/kit";
import { BTN_TEXT, EmptyNote, ErrorNotice, INPUT, LiveRegion, Notice, Panel, Switch, ToggleChips } from "../../components/wellness/ui";
import { useWellnessSend } from "../../components/wellness/useWellness";
import { KIND_OPTIONS, WEEKDAY_SHORT, blankForm, formFromSchedule, scheduleToBody, type FormErrors, type ScheduleForm } from "../../app/lib/wellness-meds";
import { localDay, plural } from "../../app/lib/wellness-format";
import type { Adherence, MedKind, Schedule, Warnings } from "../../app/lib/wellness-types";

export interface SheetTarget {
  schedule?: Schedule;
  kind?: MedKind;
}

export function ScheduleSheet({ target, suggestions, onClose, onSaved }: { target: SheetTarget | null; suggestions: string[]; onClose: () => void; onSaved: (message: string) => void }) {
  const send = useWellnessSend();
  const today = localDay();
  const [form, setForm] = useState<ScheduleForm>(() => blankForm(today));
  const [errors, setErrors] = useState<FormErrors>({});
  const editing = target?.schedule;

  useEffect(() => {
    if (!target) return;
    setErrors({});
    setForm(target.schedule ? formFromSchedule(target.schedule, localDay()) : { ...blankForm(localDay()), kind: target.kind ?? "regular", times: target.kind === "as_needed" ? [] : ["08:00"], weekdays: [] });
  }, [target]);

  const set = <K extends keyof ScheduleForm>(key: K, value: ScheduleForm[K]) => setForm((f) => ({ ...f, [key]: value }));
  const kindHint = KIND_OPTIONS.find((k) => k.value === form.kind)?.hint;

  async function submit(): Promise<string | null | false> {
    const built = scheduleToBody(form);
    if ("errors" in built) {
      setErrors(built.errors);
      return false;
    }
    setErrors({});
    const result = editing
      ? await send<{ schedule: Schedule } & Warnings>(`/wellness/meds/schedules/${editing.id}`, "PUT", built.body)
      : await send<{ schedule: Schedule } & Warnings>("/wellness/meds/schedules", "POST", built.body);
    if (!result.ok) return `${result.message} Your details are still here, so you can try again.`;
    const flagged = result.data.interactions.length + result.data.allergy_warnings.length;
    onSaved(
      `${editing ? "Updated" : "Added"} ${result.data.schedule.name}.` +
        (flagged ? ` There ${flagged === 1 ? "is 1 thing" : `are ${flagged} things`} to check with your pharmacist, shown below.` : ""),
    );
    return null;
  }

  const showTimes = form.kind !== "as_needed";
  const singleDay = form.kind === "glp1";

  return (
    <LogSheet
      open={target !== null}
      onClose={onClose}
      signal="sky"
      icon="medications"
      title={editing ? "Edit schedule" : "Add a schedule"}
      subtitle="Bubbles only records what you enter"
      submitLabel={editing ? "Save changes" : "Save schedule"}
      onSubmit={submit}
    >
      <TextField id="med-name" label="Medicine name" value={form.name} onChange={(v) => set("name", v)} error={errors.name} maxLength={120} placeholder="Name on the box" suggestions={suggestions.slice(0, 6)} signal="sky" />
      <TextField id="med-dose" label="Dose, as written on your prescription" value={form.dose_label} onChange={(v) => set("dose_label", v)} maxLength={80} placeholder="For example 500 mg" optional hint="Bubbles only displays this. It never suggests or changes a dose." />
      <Choices id="med-kind" legend="How do you take it?" options={KIND_OPTIONS.map((k) => ({ value: k.value, label: k.label }))} value={form.kind} onChange={(v) => v && set("kind", v as MedKind)} signal="sky" allowDeselect={false} hint={kindHint} />

      {showTimes && (
        <fieldset className="m-0 flex min-w-0 flex-col gap-2 border-0 p-0" aria-describedby={errors.times ? "med-times-error" : undefined}>
          <legend className="mb-2 p-0 text-body font-extrabold">{singleDay ? "Time of day" : "Times"}</legend>
          {form.times.map((t, i) => (
            <div key={i} className="flex items-center gap-2">
              <input
                type="time" value={t} aria-label={`Time ${i + 1}`} aria-invalid={errors.times ? true : undefined}
                onChange={(e) => set("times", form.times.map((x, j) => (j === i ? e.target.value : x)))} className={INPUT}
              />
              {form.times.length > 1 && (
                <button type="button" onClick={() => set("times", form.times.filter((_, j) => j !== i))} aria-label={`Remove time ${t || i + 1}`} className={BTN_TEXT}>
                  Remove
                </button>
              )}
            </div>
          ))}
          {!singleDay && form.times.length < 8 && (
            <button type="button" onClick={() => set("times", [...form.times, "20:00"])} className={`${BTN_SECONDARY} self-start`}>
              Add another time
            </button>
          )}
          {errors.times && <p id="med-times-error" className="m-0 text-body-sm font-bold text-bubbles-pink-deep">{errors.times}</p>}
        </fieldset>
      )}

      {showTimes && (
        <ToggleChips<number>
          legend={singleDay ? "Day of the week" : "Days"}
          options={WEEKDAY_SHORT.map((label, value) => ({ value, label }))}
          selected={form.weekdays}
          onToggle={(d) => set("weekdays", singleDay ? (form.weekdays.includes(d) ? [] : [d]) : form.weekdays.includes(d) ? form.weekdays.filter((x) => x !== d) : [...form.weekdays, d])}
          signal="sky"
          hint={singleDay ? "Choose the day of your weekly dose." : "Leave empty for every day."}
          error={errors.weekdays}
          optional={!singleDay}
        />
      )}

      {form.kind === "taper" && (
        <fieldset className="m-0 flex min-w-0 flex-col gap-3 border-0 p-0">
          <legend className="mb-1 p-0 text-body font-extrabold">Steps from your prescriber</legend>
          <p className="m-0 text-body-sm font-semibold text-muted">Enter each step exactly as your prescriber gave it. Bubbles never suggests or changes doses.</p>
          {form.taper_steps.map((s, i) => (
            <div key={i} className="grid gap-2 rounded-2xl bg-blush p-3 sm:grid-cols-[10rem_1fr_auto]">
              <DateField id={`taper-date-${i}`} label={`Step ${i + 1} starts`} value={s.from_date} onChange={(v) => set("taper_steps", form.taper_steps.map((x, j) => (j === i ? { ...x, from_date: v } : x)))} />
              <TextField id={`taper-dose-${i}`} label="Dose" value={s.dose_label} onChange={(v) => set("taper_steps", form.taper_steps.map((x, j) => (j === i ? { ...x, dose_label: v } : x)))} maxLength={80} />
              {form.taper_steps.length > 1 && (
                <button type="button" onClick={() => set("taper_steps", form.taper_steps.filter((_, j) => j !== i))} aria-label={`Remove step ${i + 1}`} className={`${BTN_TEXT} self-end`}>
                  Remove
                </button>
              )}
            </div>
          ))}
          {form.taper_steps.length < 12 && (
            <button type="button" onClick={() => set("taper_steps", [...form.taper_steps, { from_date: localDay(), dose_label: "" }])} className={`${BTN_SECONDARY} self-start`}>
              Add a step
            </button>
          )}
          {errors.taper && <p className="m-0 text-body-sm font-bold text-bubbles-pink-deep">{errors.taper}</p>}
        </fieldset>
      )}

      {form.kind === "cycle_pill" && (
        <>
          <Choices id="med-pack" legend="Pack type" options={[{ value: "21_7", label: "21 days on, 7 off" }, { value: "28", label: "28-day pack" }]} value={form.cycle_pattern} onChange={(v) => v && set("cycle_pattern", v as "21_7" | "28")} signal="sky" allowDeselect={false} />
          <DateField id="med-pack-start" label="First pill of this pack" value={form.cycle_pack_start} onChange={(v) => set("cycle_pack_start", v)} error={errors.cycle} />
        </>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        <DateField id="med-start" label="Starting" value={form.start_date} onChange={(v) => set("start_date", v)} />
        <DateField id="med-end" label="Ending" value={form.end_date} onChange={(v) => set("end_date", v)} error={errors.end_date} optional hint="Leave empty if there's no end date." />
      </div>

      <details className="rounded-2xl bg-blush px-4 py-3">
        <summary className="cursor-pointer text-body font-extrabold text-ink">Pill count and refill reminder</summary>
        <div className="mt-4 flex flex-col gap-4">
          <Stepper id="med-count" label="Tablets or doses left" value={form.pill_count} onChange={(v) => set("pill_count", v)} error={errors.pill_count} min={0} max={10000} step={1} fallback={30} signal="sky" optional hint="Bubbles counts down each time you mark a dose as taken." />
          <Stepper id="med-units" label="Tablets per dose" value={form.units_per_dose} onChange={(v) => set("units_per_dose", v)} error={errors.units_per_dose} min={0.25} max={10} step={0.25} fallback={1} signal="sky" optional hint="Leave empty for 1." />
          <Stepper id="med-refill" label="Remind me about a refill when about this many days are left" value={form.refill_alert_days} onChange={(v) => set("refill_alert_days", v)} error={errors.refill_alert_days} min={1} max={60} step={1} unit="days" fallback={7} signal="sky" optional />
        </div>
      </details>

      {editing && <Switch label="Active" hint="Paused medicines stay saved but leave your daily list." checked={form.active} onChange={(v) => set("active", v)} offWord="Paused" onWord="Active" />}
    </LogSheet>
  );
}

/* ── List ───────────────────────────────────────────────────────────── */

export function ScheduleList({ schedules, onEdit, onAdd, onChanged }: { schedules: Schedule[]; onEdit: (s: Schedule) => void; onAdd: () => void; onChanged: (message?: string) => void }) {
  return (
    <Panel title="Your schedules" action={<button type="button" onClick={onAdd} className={BTN_PRIMARY}>Add</button>}>
      {schedules.length === 0 ? (
        <EmptyNote title="No schedules yet" action={<button type="button" onClick={onAdd} className={BTN_PRIMARY}>Add a medicine schedule</button>}>
          Schedules give you a daily list to tick off, refill reminders and a logbook to share with your doctor. They&apos;re entirely your own record.
        </EmptyNote>
      ) : (
        <ul className="m-0 flex list-none flex-col gap-3 p-0">
          {schedules.map((s) => (
            <ScheduleCard key={s.id} s={s} onEdit={() => onEdit(s)} onChanged={onChanged} />
          ))}
        </ul>
      )}
    </Panel>
  );
}

function ScheduleCard({ s, onEdit, onChanged }: { s: Schedule; onEdit: () => void; onChanged: (message?: string) => void }) {
  const send = useWellnessSend();
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function togglePause() {
    setBusy(true);
    setError("");
    const result = await send(`/wellness/meds/schedules/${s.id}`, "PUT", { active: !s.active });
    setBusy(false);
    if (!result.ok) return setError(result.message);
    onChanged(`${s.name} ${s.active ? "paused" : "resumed"}.`);
  }
  async function remove() {
    setBusy(true);
    setError("");
    const result = await send(`/wellness/meds/schedules/${s.id}`, "DELETE");
    setBusy(false);
    if (!result.ok) return setError(result.message);
    onChanged(`${s.name} removed.`);
  }

  return (
    <li className={`rounded-2xl border p-4 ${s.active ? "border-line bg-surface" : "border-dashed border-line-strong bg-blush"}`}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="m-0 break-words font-display text-h4 text-default">
            {s.name}
            {s.dose_label ? ` · ${s.dose_label}` : ""}
          </p>
          <p className="m-0 text-body-sm text-muted">{s.describe ?? ""}</p>
        </div>
        {!s.active && <span className={`${PILL} bg-tint-grape text-bubbles-grape-deep`}>Paused</span>}
      </div>
      {s.pill_count !== undefined && (
        <p className="m-0 mt-2 text-body-sm text-ink-soft">
          {plural(s.pill_count, "dose")} left on your count
          {s.refill?.days_left != null ? `, about ${Math.floor(s.refill.days_left)} days` : ""}.
        </p>
      )}
      {s.refill?.alert && s.refill.message && <p className="m-0 mt-2 rounded-xl bg-tint-sun px-3 py-2 text-body-sm font-bold text-ink">{s.refill.message}</p>}
      <div className="mt-3 flex flex-wrap gap-2">
        <button type="button" onClick={onEdit} className={BTN_SECONDARY}>
          Edit
        </button>
        <button type="button" disabled={busy} onClick={() => void togglePause()} className={BTN_SECONDARY}>
          {s.active ? "Pause" : "Resume"}
        </button>
        {!confirming && (
          <button type="button" onClick={() => setConfirming(true)} className={BTN_TEXT}>
            Remove
          </button>
        )}
      </div>
      {confirming && (
        <div role="group" aria-label={`Remove ${s.name}`} className="mt-3 flex flex-wrap items-center gap-2 rounded-2xl bg-blush px-4 py-3">
          <p className="m-0 text-body-sm font-bold text-ink">Remove {s.name} and its schedule? This can&apos;t be undone. To keep it but stop reminders, use Pause instead.</p>
          <button type="button" disabled={busy} onClick={() => void remove()} className={BTN_PRIMARY}>
            Yes, remove
          </button>
          <button type="button" onClick={() => setConfirming(false)} className={BTN_SECONDARY}>
            Keep it
          </button>
        </div>
      )}
      {error && <div className="mt-3"><ErrorNotice message={error} /></div>}
    </li>
  );
}

/* ── Adherence ──────────────────────────────────────────────────────── */

export function AdherencePanel({ data }: { data: Adherence }) {
  const { taken, skipped, not_recorded: missing } = data.total;
  const total = taken + skipped + missing;
  const seg = (n: number) => (total ? `${(n / total) * 100}%` : "0%");
  return (
    <Panel title="Your routine" kicker={`Last ${data.window_days} days`}>
      {data.percent === null ? (
        <p className="m-0 text-body text-ink">{data.message}</p>
      ) : (
        <>
          <p className="m-0 font-display text-metric-lg text-default">{data.percent}%</p>
          <p className="m-0 -mt-3 text-body-sm font-bold text-muted">of scheduled doses recorded as taken</p>
          <p className="m-0 text-body text-ink">{data.message}</p>
        </>
      )}
      {total > 0 && (
        <>
          <div aria-hidden="true" className="flex h-3 overflow-hidden rounded-full bg-blush">
            <div className="bg-bubbles-mint" style={{ width: seg(taken) }} />
            <div className="bg-bubbles-grape" style={{ width: seg(skipped) }} />
            <div className="bg-line-strong" style={{ width: seg(missing) }} />
          </div>
          <ul className="m-0 flex list-none flex-wrap gap-x-5 gap-y-1 p-0 text-body-sm font-bold text-ink-soft">
            <li>Taken {taken}</li>
            <li>Skipped {skipped}</li>
            <li>No record {missing}</li>
          </ul>
          <p className="m-0 text-body-sm text-muted">&ldquo;No record&rdquo; only means nothing was marked. It doesn&apos;t mean a dose was missed.</p>
        </>
      )}
    </Panel>
  );
}

export function SavedLine({ message }: { message: string }) {
  return (
    <>
      <LiveRegion message={message} />
      {message && <Notice tone="info">{message}</Notice>}
    </>
  );
}
