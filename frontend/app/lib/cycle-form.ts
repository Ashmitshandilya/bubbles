// DayLog <-> form state, validation, and the settings payload. Pure.

import { isISODate } from "./cycle-calendar";
import { addTag } from "./cycle-chips";
import { cToF, fToC, parseTemp, validateBbt } from "./cycle-format";
import type {
  CycleMode, CycleSettings, DayLog, Discharge, Flow, OvulationTest, PregnancyTest, Product, Protection,
} from "./cycle-types";

export const NOTES_MAX = 2000;
export const MEDS_MAX = 10;
export const MED_LENGTH = 60;

/** Shown the moment "soaking a pad or tampon every hour" is ticked; the server's flag text follows after saving. */
export const STATIC_URGENT_HINT =
  "Soaking through a pad or tampon every hour for 2 hours or more can mean very heavy bleeding. Please contact a clinician or urgent care now. If you feel faint, dizzy or very unwell, call your local emergency number.";

type YesNo = "yes" | "no";

export interface FormState {
  flow: Flow | null;
  products: Product[];
  soaking: boolean;
  pain: number | null;
  painTypes: string[];
  energy: number | null;
  sleep: number | null;
  factors: string[];
  custom: string[];
  discharge: Discharge | null;
  sex: YesNo | null;
  protection: Protection | null;
  ovTest: OvulationTest | null;
  pregTest: PregnancyTest | null;
  bbt: string;
  meds: string[];
  bcTaken: YesNo | null;
  periodStart: boolean;
  periodEnd: boolean;
  notes: string;
}

export function toForm(log: DayLog | null, unit: "c" | "f"): FormState {
  const l = log;
  return {
    flow: l?.flow ?? null,
    products: [...(l?.products ?? [])],
    soaking: l?.soaking_hourly ?? false,
    pain: l?.pain_level ?? null,
    painTypes: [...(l?.pain_types ?? [])],
    energy: l?.energy ?? null,
    sleep: l?.sleep_quality ?? null,
    factors: [...(l?.factors ?? [])],
    custom: [...(l?.custom_factors ?? [])],
    discharge: l?.discharge ?? null,
    sex: l?.sex ? (l.sex.had ? "yes" : "no") : null,
    protection: l?.sex?.had ? l.sex.protection : null,
    ovTest: l?.ovulation_test ?? null,
    pregTest: l?.pregnancy_test ?? null,
    bbt: l?.bbt_c == null ? "" : unit === "f" ? cToF(l.bbt_c).toFixed(1) : String(l.bbt_c),
    meds: [...(l?.medications ?? [])],
    bcTaken: l?.birth_control_taken == null ? null : l.birth_control_taken ? "yes" : "no",
    periodStart: l?.period_start ?? false,
    periodEnd: l?.period_end ?? false,
    notes: l?.notes ?? "",
  };
}

export function fromForm(f: FormState, unit: "c" | "f"): DayLog {
  const typed = parseTemp(f.bbt);
  const bbt_c = typed === null ? null : unit === "f" ? fToC(typed) : typed;
  const notes = f.notes.trim();
  return {
    flow: f.flow,
    products: f.products,
    soaking_hourly: f.soaking,
    pain_level: f.pain,
    pain_types: f.painTypes,
    energy: f.energy,
    sleep_quality: f.sleep,
    factors: f.factors,
    custom_factors: f.custom,
    discharge: f.discharge,
    sex: f.sex === null ? null : f.sex === "yes" ? { had: true, protection: f.protection } : { had: false, protection: null },
    ovulation_test: f.ovTest,
    pregnancy_test: f.pregTest,
    bbt_c,
    medications: f.meds,
    birth_control_taken: f.bcTaken === null ? null : f.bcTaken === "yes",
    period_start: f.periodStart,
    period_end: f.periodEnd,
    notes: notes ? notes : null,
  };
}

/** Re-expresses the typed temperature when the unit toggle flips; text that is not a number is left alone. */
export function convertBbtText(text: string, from: "c" | "f", to: "c" | "f"): string {
  if (from === to) return text;
  const value = parseTemp(text);
  if (value === null) return text;
  return to === "f" ? cToF(value).toFixed(1) : fToC(value).toFixed(1);
}

export type FormErrors = Partial<Record<"bbt" | "notes" | "meds" | "period", string>>;

export function validateForm(f: FormState, unit: "c" | "f"): FormErrors {
  const errors: FormErrors = {};
  const bbt = validateBbt(f.bbt, unit);
  if (bbt) errors.bbt = bbt;
  if (f.notes.length > NOTES_MAX) errors.notes = `Notes can be up to ${NOTES_MAX} characters.`;
  if (f.meds.length > MEDS_MAX || f.meds.some((m) => m.length > MED_LENGTH)) errors.meds = "Keep the list to 10 items of 60 characters or fewer.";
  return errors;
}

export const addMedication = (list: readonly string[], text: string) => addTag(list, text, MEDS_MAX, MED_LENGTH);

/* ── Settings ───────────────────────────────────────────── */

export interface SettingsDraft {
  mode: CycleMode;
  age_group: "adult" | "teen";
  luteal: string;
  temp_unit: "c" | "f";
  lmp: string;
  due: string;
  delivery: string;
  breastfeeding: "yes" | "no" | "skip";
}

export function draftFromSettings(s: CycleSettings): SettingsDraft {
  return {
    mode: s.mode,
    age_group: s.age_group,
    luteal: s.luteal_days === null ? "" : String(s.luteal_days),
    temp_unit: s.temp_unit,
    lmp: s.pregnancy.lmp ?? "",
    due: s.pregnancy.due_date ?? "",
    delivery: s.postpartum.delivery_date ?? "",
    breastfeeding: s.postpartum.breastfeeding === null ? "skip" : s.postpartum.breastfeeding ? "yes" : "no",
  };
}

export type SettingsPayload = Record<string, unknown>;

/** A partial CycleSettings body for PUT /cycle/settings, or a kind error message. Dates may not be in the future. */
export function buildSettingsPayload(d: SettingsDraft, today: string): { payload: SettingsPayload } | { error: string } {
  let lutealDays: number | null = null;
  if (d.luteal.trim()) {
    const n = Number(d.luteal);
    if (!Number.isInteger(n) || n < 10 || n > 16) return { error: "Luteal length should be a whole number from 10 to 16 days, or left blank for the default of 14." };
    lutealDays = n;
  }
  const payload: SettingsPayload = { mode: d.mode, age_group: d.age_group, luteal_days: lutealDays, temp_unit: d.temp_unit };

  if (d.mode === "pregnancy") {
    if (!d.lmp && !d.due) return { error: "Add the first day of your last period or your due date." };
    if (d.lmp && (!isISODate(d.lmp) || d.lmp > today)) return { error: "The first day of your last period cannot be in the future." };
    if (d.due && !isISODate(d.due)) return { error: "Check the due date." };
    payload.pregnancy = { lmp: d.lmp || null, due_date: d.due || null };
  }
  if (d.mode === "postpartum") {
    if (!d.delivery || !isISODate(d.delivery)) return { error: "Add the date you gave birth. A past date is fine." };
    if (d.delivery > today) return { error: "The delivery date cannot be in the future." };
    payload.postpartum = { delivery_date: d.delivery, breastfeeding: d.breastfeeding === "skip" ? null : d.breastfeeding === "yes" };
  }
  return { payload };
}
