"use client";

// Small accessible form controls for the cycle log: radio segments, toggle chips, a tag input and a section wrapper.
// Selected state is never colour-only: a check mark and heavier text come with it.

import { useId, useState, type ReactNode } from "react";
import type { TagResult } from "../../app/lib/cycle-chips";

const CHOICE =
  "relative inline-flex min-h-[44px] min-w-[44px] cursor-pointer select-none items-center justify-center gap-1.5 rounded-full border px-4 text-body-sm";
const OFF = "border-line bg-surface font-bold text-ink-soft hover:border-line-strong";
const ON = "border-bubbles-pink-ink bg-tint-pink font-extrabold text-bubbles-pink-deep";
const FOCUS = "has-[:focus-visible]:outline has-[:focus-visible]:outline-[3px] has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-bubbles-grape";

export const INPUT =
  "min-h-[48px] w-full rounded-2xl border border-line bg-surface px-4 text-body text-ink focus:border-bubbles-grape focus:outline-none";

export function FieldSection({ legend, hint, children }: { legend: string; hint?: ReactNode; children: ReactNode }) {
  return (
    <fieldset className="m-0 min-w-0 rounded-3xl border border-line p-4 sm:p-5">
      <legend className="px-2 font-display text-h4 text-ink">{legend}</legend>
      {hint && <p className="mb-3 mt-0 text-body-sm text-muted">{hint}</p>}
      <div className="space-y-4">{children}</div>
    </fieldset>
  );
}

/** A labelled group of radios that behaves like one native control (arrow keys move and select). */
export function Segmented<T extends string | number>({
  legend, options, value, onChange, allowClear = true, describedBy,
}: {
  legend: string;
  options: ReadonlyArray<{ value: T; label: string }>;
  value: T | null;
  onChange: (value: T | null) => void;
  allowClear?: boolean;
  describedBy?: string;
}) {
  const name = useId();
  return (
    <fieldset className="m-0 min-w-0 border-0 p-0" aria-describedby={describedBy}>
      <legend className="mb-2 p-0 text-body-sm font-extrabold text-ink">{legend}</legend>
      <div className="flex flex-wrap items-center gap-2">
        {options.map((o) => (
          <label key={String(o.value)} className={`${CHOICE} ${FOCUS} ${value === o.value ? ON : OFF}`}>
            <input
              type="radio"
              name={name}
              className="sr-only"
              checked={value === o.value}
              onChange={() => onChange(o.value)}
            />
            {value === o.value && <span aria-hidden="true">✓</span>}
            {o.label}
          </label>
        ))}
        {allowClear && value !== null && (
          <button type="button" onClick={() => onChange(null)} className="min-h-[44px] rounded-full px-3 text-body-sm font-bold text-bubbles-pink-ink underline">
            Clear<span className="sr-only"> {legend}</span>
          </button>
        )}
      </div>
    </fieldset>
  );
}

export function ToggleChip({ pressed, onClick, children, disabled }: { pressed: boolean; onClick: () => void; children: ReactNode; disabled?: boolean }) {
  return (
    <button
      type="button"
      aria-pressed={pressed}
      disabled={disabled}
      onClick={onClick}
      className={`${CHOICE} ${pressed ? ON : OFF} focus-visible:outline-[3px] focus-visible:outline-offset-2 disabled:opacity-50`}
    >
      {pressed && <span aria-hidden="true">✓</span>}
      {children}
    </button>
  );
}

export function CheckRow({ checked, onChange, children, describedBy }: { checked: boolean; onChange: (v: boolean) => void; children: ReactNode; describedBy?: string }) {
  return (
    <label className="flex min-h-[44px] cursor-pointer items-start gap-3 rounded-2xl py-1.5 text-body text-ink">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        aria-describedby={describedBy}
        className="mt-0.5 h-6 w-6 shrink-0 accent-[var(--bubbles-pink-ink)]"
      />
      <span>{children}</span>
    </label>
  );
}

/** Free-text tags (medications, own symptoms): type, press Enter or "Add", remove with the x. */
export function TagInput({
  label, tags, onChange, add, placeholder, maxLength,
}: {
  label: string;
  tags: string[];
  onChange: (next: string[]) => void;
  add: (list: readonly string[], text: string) => TagResult;
  placeholder?: string;
  maxLength: number;
}) {
  const id = useId();
  const [text, setText] = useState("");
  const [error, setError] = useState("");

  function commit() {
    if (!text.trim()) return;
    const result = add(tags, text);
    if (result.ok) {
      onChange(result.list);
      setText("");
      setError("");
    } else setError(result.error);
  }

  return (
    <div>
      <label htmlFor={id} className="block text-body-sm font-extrabold text-ink">{label}</label>
      <div className="mt-2 flex gap-2">
        <input
          id={id}
          value={text}
          maxLength={maxLength + 20}
          placeholder={placeholder}
          aria-describedby={error ? `${id}-err` : undefined}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              commit();
            }
          }}
          className={INPUT}
        />
        <button type="button" onClick={commit} className="bubbles-press min-h-[48px] shrink-0 rounded-full border border-line-strong bg-surface px-5 text-body-sm font-extrabold text-ink">
          Add
        </button>
      </div>
      {error && <p id={`${id}-err`} role="alert" className="mt-1 text-body-sm font-bold text-bubbles-pink-deep">{error}</p>}
      {tags.length > 0 && (
        <ul className="m-0 mt-3 flex list-none flex-wrap gap-2 p-0">
          {tags.map((tag) => (
            <li key={tag}>
              <RemovablePill label={tag} onRemove={() => onChange(tags.filter((t) => t !== tag))} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function RemovablePill({ label, onRemove }: { label: string; onRemove: () => void }) {
  return (
    <span className="inline-flex min-h-[44px] items-center gap-1 rounded-full bg-tint-grape py-1 pl-4 pr-1 text-body-sm font-extrabold text-bubbles-grape-deep">
      {label}
      <button
        type="button"
        onClick={onRemove}
        aria-label={`Remove ${label}`}
        className="inline-flex h-11 w-11 items-center justify-center rounded-full text-lg leading-none hover:bg-white/60"
      >
        <span aria-hidden="true">×</span>
      </button>
    </span>
  );
}
