"use client";

// Small building blocks shared by the sleep, hydration, medications, mind, notifications and settings pages.
// Bright design system only. 44px targets. State is always said in words, never by colour alone.

import { useEffect, useId, useRef, type ReactNode } from "react";
import { BTN_SECONDARY, CARD, ErrorCard, Skeleton, type Query } from "../hub/HubKit";
import type { SafetyResponse } from "../../app/lib/wellness-types";

export type Signal = "pink" | "grape" | "sun" | "mint" | "sky" | "peach";

/** Literal class strings so Tailwind can see them. */
export const SIGNAL: Record<Signal, { tint: string; ink: string; on: string; solid: string; bar: string }> = {
  pink: { tint: "bg-tint-pink", ink: "text-bubbles-pink-deep", on: "border-bubbles-pink-ink bg-tint-pink text-bubbles-pink-deep", solid: "bg-bubbles-pink-ink text-white", bar: "bg-bubbles-pink" },
  grape: { tint: "bg-tint-grape", ink: "text-bubbles-grape-deep", on: "border-bubbles-grape bg-tint-grape text-bubbles-grape-deep", solid: "bg-bubbles-grape text-white", bar: "bg-bubbles-grape" },
  sun: { tint: "bg-tint-sun", ink: "text-bubbles-sun-deep", on: "border-bubbles-sun-deep bg-tint-sun text-bubbles-sun-deep", solid: "bg-bubbles-sun text-ink", bar: "bg-bubbles-sun" },
  mint: { tint: "bg-tint-mint", ink: "text-bubbles-mint-deep", on: "border-bubbles-mint-deep bg-tint-mint text-bubbles-mint-deep", solid: "bg-bubbles-mint-deep text-white", bar: "bg-bubbles-mint" },
  sky: { tint: "bg-tint-sky", ink: "text-bubbles-sky-deep", on: "border-bubbles-sky-deep bg-tint-sky text-bubbles-sky-deep", solid: "bg-bubbles-sky-deep text-white", bar: "bg-bubbles-sky" },
  peach: { tint: "bg-tint-peach", ink: "text-bubbles-peach-deep", on: "border-bubbles-peach-deep bg-tint-peach text-bubbles-peach-deep", solid: "bg-bubbles-peach-deep text-white", bar: "bg-bubbles-peach" },
};

export const BTN_TEXT =
  "bubbles-press inline-flex min-h-[44px] items-center justify-center gap-2 rounded-full px-4 text-body-sm font-extrabold text-bubbles-grape-deep hover:bg-tint-grape disabled:opacity-60";
export const INPUT =
  "min-h-[48px] w-full min-w-0 rounded-[20px] border-2 border-line bg-surface px-4 py-2.5 text-body text-default placeholder:text-ink-faint hover:border-line-strong focus:border-bubbles-grape aria-[invalid=true]:border-bubbles-pink-ink";

/* ── Layout ─────────────────────────────────────────────────────────── */

export function Panel({ title, kicker, action, children, className = "", id }: {
  title: string; kicker?: string; action?: ReactNode; children: ReactNode; className?: string; id?: string;
}) {
  const headingId = useId();
  return (
    <section id={id} aria-labelledby={headingId} className={`${CARD} scroll-mt-24 p-5 sm:p-6 ${className}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          {kicker && <p className="m-0 text-label font-extrabold text-muted">{kicker}</p>}
          <h2 id={headingId} className="m-0 font-display text-h3 text-default">
            {title}
          </h2>
        </div>
        {action}
      </div>
      <div className="mt-4 flex flex-col gap-4">{children}</div>
    </section>
  );
}

const NOTICE_TONE = {
  info: "bg-tint-sky text-ink",
  calm: "bg-blush text-ink-soft",
  warm: "bg-tint-sun text-ink",
  soft: "bg-tint-pink text-ink",
} as const;

/** Inline message. `role="alert"` only for failures; plain text otherwise so screen readers are not interrupted. */
export function Notice({ tone = "calm", title, children, role }: { tone?: keyof typeof NOTICE_TONE; title?: string; children: ReactNode; role?: "alert" | "status" | "note" }) {
  return (
    <div role={role} className={`rounded-2xl px-4 py-3 text-body-sm ${NOTICE_TONE[tone]}`}>
      {title && <p className="m-0 font-extrabold text-ink">{title}</p>}
      <div className={title ? "mt-1" : ""}>{children}</div>
    </div>
  );
}

export function ErrorNotice({ message }: { message: string }) {
  return (
    <p role="alert" className="m-0 rounded-2xl bg-tint-pink px-4 py-3 text-body-sm font-bold text-bubbles-pink-deep">
      {message}
    </p>
  );
}

/**
 * The deterministic safety engine's answer to urgent or crisis wording. Shown prominently, with no mascot and no cheer,
 * and focused so it is read first. Nothing was saved.
 */
export function SafetyCard({ response, onClose }: { response: SafetyResponse; onClose?: () => void }) {
  const ref = useRef<HTMLElement>(null);
  useEffect(() => {
    ref.current?.focus();
    ref.current?.scrollIntoView({ block: "center" });
  }, [response]);
  return (
    <section ref={ref} role="alert" tabIndex={-1} aria-label="Important safety message" className="rounded-3xl border-4 border-bubbles-urgent bg-tint-urgent p-5 outline-none sm:p-6">
      <h2 className="m-0 font-display text-h3 text-ink">Please read this first</h2>
      <p className="m-0 mt-3 whitespace-pre-line text-body font-bold text-ink">{response.message}</p>
      <p className="m-0 mt-3 text-body-sm font-semibold text-ink-soft">{response.note || "Nothing was saved from this message."}</p>
      {onClose && (
        <button type="button" onClick={onClose} className={`${BTN_SECONDARY} mt-4`}>
          I&apos;ve read this
        </button>
      )}
    </section>
  );
}

/** Polite live region for results of async actions ("Added 250 ml"). Keep the node mounted; change only the text. */
export function LiveRegion({ message }: { message: string }) {
  return (
    <div role="status" aria-live="polite" className="sr-only">
      {message}
    </div>
  );
}

/* ── Controls ───────────────────────────────────────────────────────── */

/** An on/off switch with a visible "On"/"Off" word, so the state never relies on colour or position alone. */
export function Switch({ label, hint, checked, onChange, disabled = false, offWord = "Off", onWord = "On" }: {
  label: string; hint?: string; checked: boolean; onChange: (next: boolean) => void; disabled?: boolean; offWord?: string; onWord?: string;
}) {
  const hintId = useId();
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl bg-blush px-4 py-2">
      <div className="min-w-0 flex-1 py-1">
        <p className="m-0 text-body font-extrabold text-ink">{label}</p>
        {hint && (
          <p id={hintId} className="m-0 text-body-sm text-muted">
            {hint}
          </p>
        )}
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-label={label}
        aria-describedby={hint ? hintId : undefined}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className="bubbles-press inline-flex min-h-[44px] items-center gap-2 rounded-full pl-1 pr-3 disabled:opacity-60"
      >
        <span aria-hidden="true" className={`relative h-7 w-12 shrink-0 rounded-full border-2 ${checked ? "border-bubbles-mint-deep bg-bubbles-mint-deep" : "border-line-strong bg-surface"}`}>
          <span className={`absolute top-0.5 h-5 w-5 rounded-full ${checked ? "left-[1.375rem] bg-white" : "left-0.5 bg-line-strong"}`} />
        </span>
        <span aria-hidden="true" className="w-8 text-body-sm font-extrabold text-ink">
          {checked ? onWord : offWord}
        </span>
      </button>
    </div>
  );
}

/** Multi-select chips (tags, weekdays, activities). Each is a toggle button with aria-pressed. */
export function ToggleChips<T extends string | number>({ legend, options, selected, onToggle, signal, hint, error, optional = false }: {
  legend: string; options: { value: T; label: string }[]; selected: T[]; onToggle: (value: T) => void; signal: Signal;
  hint?: string; error?: string; optional?: boolean;
}) {
  const id = useId();
  return (
    <fieldset className="m-0 flex min-w-0 flex-col gap-2 border-0 p-0" aria-describedby={hint ? `${id}-hint` : undefined}>
      <legend className="mb-2 p-0 text-body font-extrabold">
        {legend}
        {optional && <span className="font-semibold text-muted"> (optional)</span>}
      </legend>
      <div className="flex flex-wrap gap-2">
        {options.map((o) => {
          const on = selected.includes(o.value);
          return (
            <button
              key={String(o.value)}
              type="button"
              aria-pressed={on}
              onClick={() => onToggle(o.value)}
              className={`bubbles-press min-h-[44px] rounded-full border-2 px-4 text-body-sm font-extrabold ${on ? SIGNAL[signal].on : "border-line bg-surface text-muted hover:border-line-strong hover:text-default"}`}
            >
              {on && <span aria-hidden="true">✓ </span>}
              {o.label}
            </button>
          );
        })}
      </div>
      {hint && (
        <p id={`${id}-hint`} className="m-0 text-body-sm font-semibold text-muted">
          {hint}
        </p>
      )}
      {error && <p className="m-0 text-body-sm font-bold text-bubbles-pink-deep">{error}</p>}
    </fieldset>
  );
}

export function TimeField({ id, label, value, onChange, hint, error, optional = false }: {
  id: string; label: string; value: string; onChange: (v: string) => void; hint?: string; error?: string; optional?: boolean;
}) {
  const describedBy = [hint && `${id}-hint`, error && `${id}-error`].filter(Boolean).join(" ") || undefined;
  return (
    <div className="flex min-w-0 flex-col gap-2">
      <label htmlFor={id} className="text-body font-extrabold">
        {label}
        {optional && <span className="font-semibold text-muted"> (optional)</span>}
      </label>
      <input id={id} type="time" value={value} onChange={(e) => onChange(e.target.value)} aria-invalid={error ? true : undefined} aria-describedby={describedBy} className={INPUT} />
      {hint && (
        <p id={`${id}-hint`} className="m-0 text-body-sm font-semibold text-muted">
          {hint}
        </p>
      )}
      {error && (
        <p id={`${id}-error`} className="m-0 text-body-sm font-bold text-bubbles-pink-deep">
          {error}
        </p>
      )}
    </div>
  );
}

export function SelectField({ id, label, value, onChange, options, hint }: {
  id: string; label: string; value: string; onChange: (v: string) => void; options: { value: string; label: string }[]; hint?: string;
}) {
  return (
    <div className="flex min-w-0 flex-col gap-2">
      <label htmlFor={id} className="text-body font-extrabold">
        {label}
      </label>
      <select id={id} value={value} onChange={(e) => onChange(e.target.value)} aria-describedby={hint ? `${id}-hint` : undefined} className={INPUT}>
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
      {hint && (
        <p id={`${id}-hint`} className="m-0 text-body-sm font-semibold text-muted">
          {hint}
        </p>
      )}
    </div>
  );
}

/* ── Query states ───────────────────────────────────────────────────── */

/** Loading skeleton / friendly error with retry / the ready view. Queries time out on their own, so this never spins forever. */
export function QueryView<T>({ query, onRetry, what, skeleton, children }: {
  query: Query<T>; onRetry: () => void; what: string; skeleton?: ReactNode; children: (data: T) => ReactNode;
}) {
  if (query.status === "loading") {
    return (
      <div aria-busy="true">
        <span className="sr-only" role="status">
          Loading {what}…
        </span>
        {skeleton ?? <Skeleton className="h-40 rounded-3xl" />}
      </div>
    );
  }
  if (query.status === "error") return <ErrorCard title={`Couldn't load ${what}`} message={query.message} onRetry={onRetry} />;
  return <>{children(query.data)}</>;
}

/** Empty state without the mascot-heavy chrome: a dashed card with words and (optionally) one action. */
export function EmptyNote({ title, children, action }: { title: string; children: ReactNode; action?: ReactNode }) {
  return (
    <div className="rounded-2xl border-2 border-dashed border-line-strong bg-blush px-4 py-4">
      <p className="m-0 font-display text-h4 text-default">{title}</p>
      <div className="mt-1 text-body-sm text-muted">{children}</div>
      {action && <div className="mt-3">{action}</div>}
    </div>
  );
}

/** A thin labelled bar (e.g. sleep score parts). The number is always printed, so the bar is decoration. */
export function MeterRow({ label, value, signal, caption }: { label: string; value: number; signal: Signal; caption?: string }) {
  const pct = Math.max(0, Math.min(100, value));
  return (
    <li className="flex flex-col gap-1">
      <div className="flex items-baseline justify-between gap-3 text-body-sm">
        <span className="font-extrabold text-ink">{label}</span>
        <span className="font-bold text-muted">{caption ?? `${Math.round(pct)} / 100`}</span>
      </div>
      <div aria-hidden="true" className="h-2.5 overflow-hidden rounded-full bg-blush">
        <div className={`h-full rounded-full ${SIGNAL[signal].bar}`} style={{ width: `${pct}%` }} />
      </div>
    </li>
  );
}
