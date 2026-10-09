// Medication schedule form <-> API body, plus labels. Pure and unit-tested (wellness-meds.test.ts).
// Bubbles only stores what the person enters. Nothing here suggests, calculates or changes a dose.

import type { DoseStatus, MedKind, Schedule } from "./wellness-types";
import { isClock } from "./wellness-format";

export const WEEKDAY_SHORT = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"] as const;
export const WEEKDAY_FULL = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"] as const;

export const KIND_OPTIONS: { value: MedKind; label: string; hint: string }[] = [
  { value: "regular", label: "Regular", hint: "Taken at set times, every day or on chosen days." },
  { value: "as_needed", label: "When needed", hint: "No fixed times. You record each time you take it." },
  { value: "taper", label: "Stepped plan", hint: "A plan with changing doses that your prescriber gave you." },
  { value: "glp1", label: "Weekly injection", hint: "One day a week, for example a GLP-1 medicine." },
  { value: "cycle_pill", label: "Pill pack", hint: "A 21+7 or 28-day pack, for example a contraceptive pill." },
];

export const SKIP_REASON_LABELS: Record<string, string> = {
  side_effects: "Side effects",
  ran_out: "Ran out",
  forgot: "Forgot",
  felt_unwell: "Felt unwell",
  advised_by_clinician: "My clinician advised it",
  travelling: "Travelling",
  other: "Something else",
};

export const SITE_LABELS: Record<string, string> = {
  abdomen_left: "Left side of the tummy",
  abdomen_right: "Right side of the tummy",
  thigh_left: "Left thigh",
  thigh_right: "Right thigh",
  upper_arm_left: "Left upper arm",
  upper_arm_right: "Right upper arm",
};

/** Words for a dose status. Always shown as text next to any colour or icon. */
export const STATUS_WORDS: Record<DoseStatus, string> = {
  upcoming: "Coming up",
  due: "Due now",
  late: "Not recorded yet",
  taken: "Taken",
  skipped: "Skipped",
  snoozed: "Snoozed",
};

export interface TaperStepForm {
  from_date: string;
  dose_label: string;
}

export interface ScheduleForm {
  name: string;
  dose_label: string;
  kind: MedKind;
  times: string[];
  weekdays: number[];
  start_date: string;
  end_date: string;
  pill_count: string;
  units_per_dose: string;
  refill_alert_days: string;
  taper_steps: TaperStepForm[];
  cycle_pattern: "21_7" | "28";
  cycle_pack_start: string;
  active: boolean;
}

export function blankForm(today: string): ScheduleForm {
  return {
    name: "", dose_label: "", kind: "regular", times: ["08:00"], weekdays: [], start_date: today, end_date: "",
    pill_count: "", units_per_dose: "", refill_alert_days: "", taper_steps: [{ from_date: today, dose_label: "" }],
    cycle_pattern: "21_7", cycle_pack_start: today, active: true,
  };
}

export function formFromSchedule(s: Schedule, today: string): ScheduleForm {
  return {
    name: s.name, dose_label: s.dose_label ?? "", kind: s.kind, times: s.times.length ? [...s.times] : s.kind === "as_needed" ? [] : ["08:00"],
    weekdays: [...(s.weekdays ?? [])], start_date: s.start_date ?? today, end_date: s.end_date ?? "",
    pill_count: s.pill_count === undefined ? "" : String(s.pill_count),
    units_per_dose: s.units_per_dose !== undefined && s.units_per_dose !== 1 ? String(s.units_per_dose) : "",
    refill_alert_days: s.refill_alert_days === undefined ? "" : String(s.refill_alert_days),
    taper_steps: s.taper_steps?.length ? s.taper_steps.map((t) => ({ from_date: t.from_date, dose_label: t.dose_label })) : [{ from_date: today, dose_label: "" }],
    cycle_pattern: s.cycle?.pattern ?? "21_7", cycle_pack_start: s.cycle?.pack_start ?? today, active: s.active,
  };
}

export type FormErrors = Partial<Record<"name" | "times" | "weekdays" | "taper" | "pill_count" | "refill_alert_days" | "units_per_dose" | "end_date" | "cycle", string>>;

function wholeNumber(raw: string, min: number, max: number): number | null | "bad" {
  if (!raw.trim()) return null;
  const n = Number(raw);
  return Number.isInteger(n) && n >= min && n <= max ? n : "bad";
}

/** Validates the form the same way the server will and builds the request body. Server messages still win if they disagree. */
export function scheduleToBody(form: ScheduleForm): { body: Record<string, unknown> } | { errors: FormErrors } {
  const errors: FormErrors = {};
  const name = form.name.trim();
  if (!name) errors.name = "Add the medicine's name.";
  const times = [...new Set(form.times.map((t) => t.trim()).filter(Boolean))];
  if (form.kind !== "as_needed") {
    if (times.length === 0) errors.times = "Add at least one time, like 08:00.";
    else if (times.length > 8) errors.times = "Up to 8 times a day.";
    else if (times.some((t) => !isClock(t))) errors.times = "Times need to look like 08:00.";
  }
  if (form.kind === "glp1") {
    if (form.weekdays.length > 1) errors.weekdays = "A weekly injection has one day of the week.";
    if (times.length > 1) errors.times = "Add one time of day for the dose.";
  }
  if (form.end_date && form.start_date && form.end_date < form.start_date) errors.end_date = "The end date can't be before the start date.";
  const pills = wholeNumber(form.pill_count, 0, 10000);
  if (pills === "bad") errors.pill_count = "Use a whole number from 0 to 10000.";
  const alert = wholeNumber(form.refill_alert_days, 1, 60);
  if (alert === "bad") errors.refill_alert_days = "Use a whole number from 1 to 60 days.";
  let units: number | null = null;
  if (form.units_per_dose.trim()) {
    units = Number(form.units_per_dose);
    if (!Number.isFinite(units) || units < 0.25 || units > 10) errors.units_per_dose = "Use a number from 0.25 to 10.";
  }
  if (form.kind === "taper") {
    const steps = form.taper_steps;
    if (steps.length < 1 || steps.length > 12) errors.taper = "Add the steps your prescriber gave you (1 to 12).";
    else if (steps.some((s) => !s.from_date || !s.dose_label.trim())) errors.taper = "Each step needs a start date and the dose written on your plan.";
  }
  if (form.kind === "cycle_pill" && !form.cycle_pack_start) errors.cycle = "Add the day this pack started.";
  if (Object.keys(errors).length) return { errors };

  // Blank optional fields are sent as ""/null on purpose: the server merges an edit over the saved schedule, so
  // leaving them out would silently keep the old value.
  const body: Record<string, unknown> = {
    name, kind: form.kind, active: form.active, weekdays: form.kind === "as_needed" ? [] : [...form.weekdays].sort((a, b) => a - b),
    times: form.kind === "as_needed" ? [] : times, start_date: form.start_date || undefined, dose_label: form.dose_label.trim(),
    end_date: form.end_date, pill_count: typeof pills === "number" ? pills : null, refill_alert_days: typeof alert === "number" ? alert : null,
    units_per_dose: units,
  };
  if (form.kind === "taper") body.taper_steps = form.taper_steps.map((s) => ({ from_date: s.from_date, dose_label: s.dose_label.trim() }));
  if (form.kind === "cycle_pill") body.cycle = { pattern: form.cycle_pattern, pack_start: form.cycle_pack_start };
  return { body };
}

/** Sort key so "Due now" and "Not recorded yet" come before things already finished, then by time. */
const STATUS_ORDER: Record<DoseStatus, number> = { late: 0, due: 1, snoozed: 2, upcoming: 3, taken: 4, skipped: 5 };
export function byDoseUrgency<T extends { status: DoseStatus; time: string }>(a: T, b: T): number {
  return STATUS_ORDER[a.status] - STATUS_ORDER[b.status] || a.time.localeCompare(b.time);
}

/** "Mon, Wed" / "Every day". */
export function weekdaysText(weekdays: number[]): string {
  if (!weekdays.length || weekdays.length === 7) return "Every day";
  return weekdays.map((d) => WEEKDAY_SHORT[d] ?? "").filter(Boolean).join(", ");
}

/** Appetite 1-5 in words. */
export function appetiteWords(n: number): string {
  return ["", "Very low", "Low", "Normal", "Good", "Strong"][Math.round(n)] ?? String(n);
}
