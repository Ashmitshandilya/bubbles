"use client";

import { useEffect, useState } from "react";
import { useApi } from "./Providers";
import {
  Choices, DateField, DetailChips, Disclaimer, EmptyState, EntryNote, EntryRow, History, LastLogged, LogButton, LogSheet, SavedToast, SIGNALS,
  StatGrid, StatSkeleton, Stepper, TextArea, TextField, TrackerHero, TrackerShell, type IconName, type Signal,
} from "./tracking/kit";
import { choiceLabels } from "./tracking/choices";
import { readUnitPreference, saveUnitPreference, toShownUnit, toStoredUnit, type SwitchUnit } from "../app/lib/unit-switch";
import {
  byNewest, computeStat, dateLabel, formatNumber, parseRange, present, timeLabel, toNumber, useTracker,
  type Entry, type StatSpec,
} from "./tracking/data";

/** Serializable field config (tracker pages are server components). Ranges mirror backend/health_logs.py. */
export interface TrackerField {
  /** POST body key, also the key in GET entries. */
  id: string;
  label: string;
  type: "text" | "number" | "textarea" | "select" | "date";
  placeholder?: string;
  hint?: string;
  required?: boolean;
  /** number: inclusive range, stepper increment, unit shown after the value. */
  min?: number;
  max?: number;
  step?: number;
  unit?: string;
  /** number: offer a kg switch for this field. `unit` stays the stored unit (lbs); the API always receives lbs. */
  altUnit?: "kg";
  /** number: where the stepper starts when empty and nothing has been logged yet. */
  start?: number;
  /** number: one-tap amounts, e.g. [250, 500] ml. */
  presets?: number[];
  /** select: chips; `scale` lays them out as an equal row (e.g. Drained…Great mapped to 2…10). */
  options?: { value: string; label: string }[];
  scale?: boolean;
  /** select: pick any number of chips (the value is a comma-separated string). */
  multi?: boolean;
  /** Pre-selected value. */
  initial?: string;
  maxLength?: number;
  /** text: regex (whole value) checked before saving, with the message shown when it fails. */
  pattern?: string;
  patternHint?: string;
  /** History: append this entry field as the unit (labs: value + unit). */
  unitField?: string;
  /** History: flag the value when outside the "lo-hi" range held in this entry field. */
  rangeField?: string;
  hideInHistory?: boolean;
}

interface GenericTrackingClientProps {
  title: string;
  kicker: string;
  /** One line: why logging this helps Bubbles. */
  description: string;
  endpoint: string;
  signal: Signal;
  icon: IconName;
  fields: TrackerField[];
  stats: StatSpec[];
  /** Hero button / empty-state CTA, e.g. "Log water". */
  logLabel: string;
  /** Sheet heading, e.g. "Add a drink". */
  sheetTitle: string;
  submitLabel: string;
  emptyTitle: string;
  /** Title for an entry with no displayable fields, e.g. "Doctor visit". */
  entryLabel: string;
  /** Field shown as the entry title (default: first filled non-textarea field). */
  titleField?: string;
  /** At least one of these must be filled (vitals). */
  requireOneOf?: string[];
  historyTitle?: string;
  /** A note shown above the history that is not part of the form (for example when to seek urgent care). */
  callout?: { title: string; text: string };
}

export function GenericTrackingClient(props: GenericTrackingClientProps) {
  return (
    <TrackerShell title={props.title}>
      <GenericTracker {...props} />
    </TrackerShell>
  );
}

function blank(fields: TrackerField[]): Record<string, string> {
  return Object.fromEntries(fields.map((f) => [f.id, f.initial ?? ""]));
}

function rangeText(f: TrackerField): string {
  const unit = f.unit ? (/^[/°%]/.test(f.unit) ? f.unit : ` ${f.unit}`) : "";
  if (f.min !== undefined && f.max !== undefined) return `between ${f.min} and ${f.max}${unit}`;
  return f.min !== undefined ? `at least ${f.min}${unit}` : `at most ${f.max}${unit}`;
}

function displayValue(f: TrackerField, entry: Entry): string {
  const v = entry[f.id];
  if (f.multi && f.options) return choiceLabels(String(v), f.options);
  const option = f.options?.find((o) => o.value === String(v));
  if (option) return option.label;
  if (f.type === "date" && typeof v === "string") return dateLabel(v);
  const n = toNumber(v);
  if (n !== null && (f.type === "number" || f.unit)) return formatNumber(n, f.unit, 2);
  const unit = f.unitField ? entry[f.unitField] : undefined;
  if (!present(unit)) return String(v);
  return /^[/°%]/.test(String(unit)) ? `${v}${unit}` : `${v} ${unit}`;
}

function outsideRange(f: TrackerField, entry: Entry): boolean {
  if (!f.rangeField) return false;
  const n = toNumber(entry[f.id]);
  const range = parseRange(entry[f.rangeField]);
  return n !== null && range !== null && (n < range[0] || n > range[1]);
}

function humanize(key: string): string {
  const words = key.replace(/_/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

function GenericTracker({
  title, kicker, description, endpoint, signal, icon, fields, stats, logLabel, sheetTitle, submitLabel,
  emptyTitle, entryLabel, titleField, requireOneOf, historyTitle, callout,
}: GenericTrackingClientProps) {
  const { entries: storedEntries, status, error, retry, save, freshId } = useTracker(endpoint, 30);
  const { databaseStatus } = useApi();
  const [open, setOpen] = useState(false);
  const [values, setValues] = useState<Record<string, string>>(() => blank(fields));
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [unit, setUnit] = useState<SwitchUnit>("lbs");

  useEffect(() => {
    setUnit(readUnitPreference(endpoint));
  }, [endpoint]);

  const chooseUnit = (next: SwitchUnit) => {
    setUnit(next);
    saveUnitPreference(endpoint, next);
  };
  const hasSwitch = fields.some((f) => f.altUnit);
  const switched = (f: TrackerField) => Boolean(f.altUnit) && unit === "kg";

  // Everything on screen goes through these: the form, history and stats read the chosen unit, the API keeps lbs.
  const viewFields: TrackerField[] = fields.map((f) => {
    if (!switched(f)) return f;
    const shown = (n?: number) => (n === undefined ? undefined : toShownUnit(n, "kg"));
    return { ...f, unit: "kg", min: shown(f.min), max: shown(f.max), start: shown(f.start), step: 0.1 };
  });
  const entries = storedEntries.map((e) => {
    const next = { ...e };
    for (const f of fields) {
      const n = toNumber(e[f.id]);
      if (switched(f) && n !== null) next[f.id] = toShownUnit(n, "kg");
    }
    return next;
  });
  const shownStats = stats.map((spec) => {
    const f = fields.find((x) => x.id === spec.field);
    return f && switched(f) ? { ...spec, unit: "kg" } : spec;
  });

  const openSheet = () => {
    setErrors({});
    setOpen(true);
  };
  const set = (id: string, value: string) => {
    setValues((prev) => ({ ...prev, [id]: value }));
    setErrors((prev) => (prev[id] ? { ...prev, [id]: "" } : prev));
  };

  async function submit(): Promise<string | null | false> {
    const nextErrors: Record<string, string> = {};
    const body: Record<string, string | number> = {};
    for (const f of viewFields) {
      const raw = (values[f.id] ?? "").trim();
      if (!raw) {
        if (f.required) nextErrors[f.id] = `Please add ${f.label.toLowerCase()}.`;
        continue;
      }
      if (f.type === "number") {
        const n = Number(raw);
        if (!Number.isFinite(n)) nextErrors[f.id] = `${f.label} must be a number.`;
        else if ((f.min !== undefined && n < f.min) || (f.max !== undefined && n > f.max)) nextErrors[f.id] = `${f.label} must be ${rangeText(f)}.`;
        else body[f.id] = switched(f) ? toStoredUnit(n, "kg") : n;
        continue;
      }
      if (f.pattern && !new RegExp(`^(?:${f.pattern})$`).test(raw)) {
        nextErrors[f.id] = f.patternHint ?? `Please check ${f.label.toLowerCase()}.`;
        continue;
      }
      if (f.maxLength && raw.length > f.maxLength) {
        nextErrors[f.id] = `Please keep ${f.label.toLowerCase()} under ${f.maxLength} characters.`;
        continue;
      }
      body[f.id] = raw;
    }
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length) return false;
    if (requireOneOf && !requireOneOf.some((id) => id in body)) {
      const names = viewFields.filter((f) => requireOneOf.includes(f.id)).map((f) => f.label.toLowerCase());
      return `Add at least one: ${names.join(", ")}.`;
    }
    if (Object.keys(body).length === 0) return "Add at least one detail before saving.";
    const failure = await save(body);
    if (!failure) setValues(blank(fields));
    return failure;
  }

  const latestNumber = (id: string) => {
    for (const e of [...entries].sort(byNewest)) {
      const n = toNumber(e[id]);
      if (n !== null) return n;
    }
    return null;
  };

  function renderField(f: TrackerField) {
    const common = {
      id: `field-${f.id}`,
      label: f.label,
      value: values[f.id] ?? "",
      onChange: (v: string) => set(f.id, v),
      hint: f.hint,
      error: errors[f.id] || undefined,
      optional: !f.required && !requireOneOf?.includes(f.id),
    };
    switch (f.type) {
      case "number":
        return (
          <Stepper
            key={f.id}
            {...common}
            min={f.min ?? 0}
            max={f.max ?? 100000}
            step={f.step ?? 1}
            unit={f.unit}
            fallback={latestNumber(f.id) ?? f.start ?? f.min ?? 0}
            presets={f.presets}
            signal={signal}
          />
        );
      case "select":
        return (
          <Choices
            key={f.id}
            {...common}
            legend={f.label}
            options={f.options ?? []}
            columns={f.scale ? f.options?.length : undefined}
            multi={f.multi}
            signal={signal}
          />
        );
      case "textarea":
        return <TextArea key={f.id} {...common} placeholder={f.placeholder} maxLength={f.maxLength} />;
      case "date":
        return <DateField key={f.id} {...common} />;
      default:
        return <TextField key={f.id} {...common} placeholder={f.placeholder} maxLength={f.maxLength} />;
    }
  }

  function renderEntry(entry: Entry) {
    const shown = viewFields.filter((f) => !f.hideInHistory && present(entry[f.id]));
    const head = (titleField ? shown.find((f) => f.id === titleField) : undefined) ?? shown.find((f) => f.type !== "textarea");
    const chips = shown.filter((f) => f !== head && f.type !== "textarea");
    const notes = shown.filter((f) => f !== head && f.type === "textarea");
    const known = new Set(["id", "date", ...viewFields.map((f) => f.id)]);
    const extras = Object.entries(entry).filter(([k, v]) => !known.has(k) && present(v));
    const flagged = shown.some((f) => outsideRange(f, entry));
    return (
      <EntryRow signal={signal} icon={icon} title={head ? displayValue(head, entry) : entryLabel} time={timeLabel(entry.date)}>
        <DetailChips items={chips.map((f) => ({ label: f.label, value: displayValue(f, entry) }))} />
        {flagged && (
          <p className="m-0 mt-2 inline-block rounded-full bg-tint-sun px-3 py-1 text-body-sm font-extrabold text-bubbles-sun-deep">
            Outside the range you entered
          </p>
        )}
        {notes.map((f) => (
          <EntryNote key={f.id} label={f.id === "notes" ? undefined : f.label} text={entry[f.id]} />
        ))}
        {extras.map(([k, v]) => (
          <EntryNote key={k} label={k === "notes" ? undefined : humanize(k)} text={v} />
        ))}
      </EntryRow>
    );
  }

  const log = <LogButton signal={signal} onClick={openSheet}>{logLabel}</LogButton>;
  const today = new Date().toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "short" });

  return (
    <>
      <TrackerHero signal={signal} icon={icon} kicker={kicker} title={title} why={description} action={log} />
      {callout && (
        <aside role="note" className="rounded-3xl border-2 border-[#FFD3C2] bg-tint-urgent p-4 sm:p-5">
          <h2 className="m-0 text-body font-extrabold text-bubbles-urgent">{callout.title}</h2>
          <p className="m-0 mt-1 text-body-sm text-ink-soft">{callout.text}</p>
        </aside>
      )}
      {status === "ready" && <LastLogged entries={entries} />}
      {status === "loading" && entries.length === 0 && <StatSkeleton count={stats.length} />}
      {hasSwitch && entries.length > 0 && (
        <div className="mb-4 flex justify-end">
          <div role="group" aria-label="Units" className="inline-flex gap-1 rounded-full border border-line bg-surface p-1">
            {(["lbs", "kg"] as const).map((u) => (
              <button
                key={u}
                type="button"
                aria-pressed={unit === u}
                onClick={() => chooseUnit(u)}
                className={`min-h-[40px] rounded-full px-4 text-body-sm font-extrabold ${
                  unit === u ? SIGNALS[signal].chipOn : "text-muted hover:text-default"
                }`}
              >
                {u}
              </button>
            ))}
          </div>
        </div>
      )}
      {status === "ready" && entries.length > 0 && <StatGrid signal={signal} stats={shownStats.map((spec) => computeStat(spec, entries))} />}
      <History
        title={historyTitle}
        status={status}
        error={error}
        onRetry={retry}
        entries={entries}
        freshId={freshId}
        signal={signal}
        renderEntry={renderEntry}
        empty={<EmptyState title={emptyTitle} text={description} action={<LogButton signal={signal} onClick={openSheet} wide>{logLabel}</LogButton>} />}
      />
      <Disclaimer />
      <LogSheet open={open} onClose={() => setOpen(false)} signal={signal} icon={icon} title={sheetTitle} subtitle={today} submitLabel={submitLabel} onSubmit={submit}>
        {requireOneOf && <p className="m-0 text-body-sm font-semibold text-muted">Add at least one reading. The rest can stay empty.</p>}
        {viewFields.map(renderField)}
      </LogSheet>
      <SavedToast
        trigger={freshId}
        message={
          databaseStatus === "permission_denied"
            ? "Saved in compatibility mode. Bubbles will use this to learn your baseline."
            : "Saved! Bubbles will use this to learn your baseline."
        }
      />
    </>
  );
}
