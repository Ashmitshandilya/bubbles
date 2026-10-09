"use client";

// The day log form (used in the Log sheet and in the Log tab). Sections are fieldsets; every control has a label.

import { useRef, useState, type FormEvent } from "react";
import { BTN_PRIMARY, BTN_SECONDARY, ErrorCard, Skeleton } from "../hub/HubKit";
import { dayPath } from "../../app/lib/cycle-api";
import {
  STATIC_URGENT_HINT, addMedication, convertBbtText, fromForm, toForm, validateForm, MED_LENGTH, NOTES_MAX,
  type FormErrors, type FormState,
} from "../../app/lib/cycle-form";
import {
  DISCHARGES, FLOW_LEVELS, OVULATION_TESTS, PAIN_TYPES, PREGNANCY_TESTS, PRODUCTS, PROTECTIONS,
  type DayResponse, type Flow,
} from "../../app/lib/cycle-types";
import { toggleId } from "../../app/lib/cycle-chips";
import { useCycle } from "./CycleStore";
import { ChipPicker } from "./ChipPicker";
import { CheckRow, FieldSection, INPUT, Segmented, TagInput, ToggleChip } from "./fields";
import { FlagList, InlineError, SafetyAlert } from "./shared";

const words = (id: string) => id.replaceAll("_", " ").replace(/^./, (c) => c.toUpperCase());
const options = <T extends string>(list: readonly T[], label: (v: T) => string = words) => list.map((v) => ({ value: v, label: label(v) }));
const scale = [1, 2, 3, 4, 5].map((n) => ({ value: n, label: String(n) }));
const YES_NO = [{ value: "yes" as const, label: "Yes" }, { value: "no" as const, label: "No" }];
const FLOW_LABEL: Record<Flow, string> = { none: "No bleeding", spotting: "Spotting", light: "Light", medium: "Medium", heavy: "Heavy" };

export function DayForm({ date, initial, onDone }: { date: string; initial: DayResponse; onDone?: () => void }) {
  const { tempUnit, factors, factorsStatus, reloadFactors, today, call, applyOverview, reloadOverview, bump, announce } = useCycle();
  const [unit, setUnit] = useState<"c" | "f">(tempUnit);
  const [form, setForm] = useState<FormState>(() => toForm(initial.log, tempUnit));
  const [errors, setErrors] = useState<FormErrors>({});
  const [serverError, setServerError] = useState("");
  const [saving, setSaving] = useState(false);
  const [result, setResult] = useState<DayResponse | null>(null);
  const resultRef = useRef<HTMLDivElement>(null);

  const set = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    setForm((f) => ({ ...f, [key]: value }));
    setResult(null);
  };

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (saving) return;
    const found = validateForm(form, unit);
    setErrors(found);
    setServerError("");
    if (Object.keys(found).length) {
      announce("Please fix the highlighted fields before saving.");
      return;
    }
    setSaving(true);
    const response = await call<DayResponse>(dayPath(date, today), { method: "PUT", body: JSON.stringify(fromForm(form, unit)) });
    setSaving(false);
    if (!response.ok) {
      setServerError(response.error);
      return;
    }
    if (response.data.overview) applyOverview(response.data.overview);
    else reloadOverview();
    bump();
    setResult(response.data);
    announce("Saved.");
    window.setTimeout(() => resultRef.current?.focus(), 0);
  }

  const safety = result?.safety ?? null;
  const flags = result?.flags ?? [];

  return (
    <form onSubmit={submit} noValidate className="space-y-5">
      {(result || serverError) && (
        <div ref={resultRef} tabIndex={-1} className="space-y-3 outline-none">
          {serverError && <InlineError message={serverError} />}
          {safety && <SafetyAlert safety={safety} />}
          {result && (
            <p role="status" className="m-0 rounded-2xl bg-tint-mint px-4 py-3 text-body font-extrabold text-bubbles-mint-deep">
              {safety ? "Your entry was saved." : "Saved. Thank you for logging."}
            </p>
          )}
          <FlagList flags={flags} />
          {onDone && result && (
            <button type="button" onClick={onDone} className={BTN_SECONDARY}>Done</button>
          )}
        </div>
      )}
      {Object.keys(errors).length > 0 && <InlineError message={Object.values(errors).join(" ")} />}

      <FieldSection legend="Period">
        <div className="flex flex-wrap gap-2">
          <ToggleChip pressed={form.periodStart} onClick={() => set("periodStart", !form.periodStart)}>Period started</ToggleChip>
          <ToggleChip pressed={form.periodEnd} onClick={() => set("periodEnd", !form.periodEnd)}>Period ended</ToggleChip>
        </div>
      </FieldSection>

      <FieldSection legend="Bleeding">
        <Segmented legend="Flow" options={FLOW_LEVELS.map((f) => ({ value: f, label: FLOW_LABEL[f] }))} value={form.flow} onChange={(v) => set("flow", v)} />
        <fieldset className="m-0 min-w-0 border-0 p-0">
          <legend className="mb-2 p-0 text-body-sm font-extrabold text-ink">Products used</legend>
          <div className="flex flex-wrap gap-2">
            {PRODUCTS.map((p) => (
              <ToggleChip key={p} pressed={form.products.includes(p)} onClick={() => set("products", toggleId(form.products, p) as FormState["products"])}>
                {words(p)}
              </ToggleChip>
            ))}
          </div>
        </fieldset>
        <CheckRow checked={form.soaking} onChange={(v) => set("soaking", v)} describedBy="cycle-soak-hint">
          Soaking a pad or tampon every hour for 2 hours or more
        </CheckRow>
        {form.soaking && (
          <p id="cycle-soak-hint" role="alert" className="m-0 rounded-2xl border-2 border-bubbles-urgent bg-tint-urgent px-4 py-3 text-body font-extrabold text-ink">
            {STATIC_URGENT_HINT}
          </p>
        )}
      </FieldSection>

      <FieldSection legend="Pain">
        <div>
          <label htmlFor="cycle-pain" className="block text-body-sm font-extrabold text-ink">
            Pain level: <span className="font-display text-h4">{form.pain === null ? "not logged" : `${form.pain} of 10`}</span>
          </label>
          <input
            id="cycle-pain"
            type="range"
            min={0}
            max={10}
            step={1}
            value={form.pain ?? 0}
            aria-valuetext={form.pain === null ? "not logged" : `${form.pain} of 10`}
            onChange={(e) => set("pain", Number(e.target.value))}
            className="mt-2 h-11 w-full accent-[var(--bubbles-pink-ink)]"
          />
          <div className="mt-1 flex flex-wrap items-center gap-2">
            <ToggleChip pressed={form.pain === 0} onClick={() => set("pain", form.pain === 0 ? null : 0)}>No pain</ToggleChip>
            {form.pain !== null && (
              <button type="button" onClick={() => set("pain", null)} className="min-h-[44px] rounded-full px-3 text-body-sm font-bold text-bubbles-pink-ink underline">
                Clear<span className="sr-only"> pain level</span>
              </button>
            )}
          </div>
        </div>
        <fieldset className="m-0 min-w-0 border-0 p-0">
          <legend className="mb-2 p-0 text-body-sm font-extrabold text-ink">Where or what kind</legend>
          <div className="flex flex-wrap gap-2">
            {PAIN_TYPES.map((p) => (
              <ToggleChip key={p.id} pressed={form.painTypes.includes(p.id)} onClick={() => set("painTypes", toggleId(form.painTypes, p.id))}>{p.label}</ToggleChip>
            ))}
          </div>
        </fieldset>
      </FieldSection>

      <FieldSection legend="Feelings & body" hint="Pick anything you noticed. Patterns appear over several cycles.">
        {factorsStatus === "loading" && <Skeleton className="h-32 rounded-2xl" />}
        {factorsStatus === "error" && <ErrorCard inset title="The list didn't load" message="You can still add things in your own words after trying again." onRetry={reloadFactors} />}
        {factors && (
          <ChipPicker groups={factors} selected={form.factors} custom={form.custom} onSelected={(ids) => set("factors", ids)} onCustom={(list) => set("custom", list)} />
        )}
      </FieldSection>

      <FieldSection legend="Energy & sleep">
        <Segmented legend="Energy (1 low, 5 high)" options={scale} value={form.energy} onChange={(v) => set("energy", v)} />
        <Segmented legend="Sleep quality (1 poor, 5 great)" options={scale} value={form.sleep} onChange={(v) => set("sleep", v)} />
      </FieldSection>

      <FieldSection legend="Discharge">
        <Segmented legend="What you noticed" options={options(DISCHARGES)} value={form.discharge} onChange={(v) => set("discharge", v)} />
      </FieldSection>

      <FieldSection legend="Sex & protection">
        <Segmented legend="Had sex" options={YES_NO} value={form.sex} onChange={(v) => setForm((f) => ({ ...f, sex: v, protection: v === "yes" ? f.protection : null }))} />
        {form.sex === "yes" && <Segmented legend="Protection used" options={options(PROTECTIONS)} value={form.protection} onChange={(v) => set("protection", v)} />}
      </FieldSection>

      <FieldSection legend="Tests" hint="Log what the test showed. Bubbles does not interpret results.">
        <Segmented legend="Ovulation test" options={options(OVULATION_TESTS)} value={form.ovTest} onChange={(v) => set("ovTest", v)} />
        <Segmented legend="Pregnancy test" options={options(PREGNANCY_TESTS)} value={form.pregTest} onChange={(v) => set("pregTest", v)} />
      </FieldSection>

      <FieldSection legend="Temperature" hint="Basal body temperature, taken on waking before getting up.">
        <div className="flex flex-wrap items-end gap-3">
          <div className="min-w-[8rem] flex-1">
            <label htmlFor="cycle-bbt" className="block text-body-sm font-extrabold text-ink">Temperature (°{unit.toUpperCase()})</label>
            <input
              id="cycle-bbt"
              inputMode="decimal"
              value={form.bbt}
              placeholder={unit === "c" ? "36.50" : "97.70"}
              aria-invalid={errors.bbt ? true : undefined}
              aria-describedby={errors.bbt ? "cycle-bbt-err" : undefined}
              onChange={(e) => set("bbt", e.target.value)}
              className={`${INPUT} mt-2`}
            />
          </div>
          <Segmented
            legend="Unit"
            allowClear={false}
            options={[{ value: "c" as const, label: "°C" }, { value: "f" as const, label: "°F" }]}
            value={unit}
            onChange={(next) => {
              if (!next) return;
              setForm((f) => ({ ...f, bbt: convertBbtText(f.bbt, unit, next) }));
              setUnit(next);
            }}
          />
        </div>
        {errors.bbt && <p id="cycle-bbt-err" className="m-0 text-body-sm font-bold text-bubbles-pink-deep">{errors.bbt}</p>}
      </FieldSection>

      <FieldSection legend="Medications">
        <TagInput label="What you took" tags={form.meds} onChange={(list) => set("meds", list)} add={addMedication} maxLength={MED_LENGTH} placeholder="e.g. ibuprofen" />
        {errors.meds && <p className="m-0 text-body-sm font-bold text-bubbles-pink-deep">{errors.meds}</p>}
        <Segmented legend="Took birth control today" options={YES_NO} value={form.bcTaken} onChange={(v) => set("bcTaken", v)} />
      </FieldSection>

      <FieldSection legend="Notes">
        <div>
          <label htmlFor="cycle-notes" className="block text-body-sm font-extrabold text-ink">Anything else to remember</label>
          <textarea
            id="cycle-notes"
            rows={4}
            value={form.notes}
            maxLength={NOTES_MAX + 200}
            aria-describedby="cycle-notes-count"
            onChange={(e) => set("notes", e.target.value)}
            className={`${INPUT} mt-2 py-3`}
          />
          <p id="cycle-notes-count" className={`m-0 mt-1 text-body-sm ${form.notes.length > NOTES_MAX ? "font-bold text-bubbles-pink-deep" : "text-muted"}`}>
            {form.notes.length} / {NOTES_MAX}
          </p>
        </div>
      </FieldSection>

      <div className="sticky bottom-0 -mx-1 flex flex-wrap items-center gap-3 bg-surface/95 px-1 py-3">
        <button type="submit" disabled={saving} className={BTN_PRIMARY}>{saving ? "Saving…" : "Save this day"}</button>
        {onDone && <button type="button" onClick={onDone} className={BTN_SECONDARY}>Close</button>}
      </div>
    </form>
  );
}
