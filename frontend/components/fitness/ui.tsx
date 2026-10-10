"use client";

// Shared Fitness building blocks: page shell + sub-navigation, send helper, rings, bars, notices, sheet, form bits.
// Everything is keyboard operable, has 44px targets, respects reduced motion and never relies on colour alone.

import { useCallback, useEffect, useId, useRef, useState, type ReactNode } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useApi } from "../Providers";
import { CARD, HubPage, PILL, type Tone, TONE, useBubblesQuery } from "../hub/HubKit";
import { classifyFailure, failureFromError } from "../../app/lib/connection";
import { detailMessage, fmt, macroRows, reviewPending, type MacroRow } from "../../app/lib/fitness-calc";
import type { Review } from "../../app/lib/fitness-types";

/* ── Sending (never raw fetch; server `detail` shown on errors) ─────── */

export type SendResult<T> = { ok: true; data: T } | { ok: false; message: string; status: number };

export function useSend() {
  const { fetchBubbles } = useApi();
  return useCallback(
    async function send<T>(path: string, method: "GET" | "POST" | "PUT" | "DELETE", body?: unknown): Promise<SendResult<T>> {
      try {
        const response = await fetchBubbles(path, { method, ...(body !== undefined ? { body: JSON.stringify(body) } : {}) });
        const json: unknown = await response.json().catch(() => null);
        if (!response.ok) {
          const general = classifyFailure({ status: response.status, body: json });
          // A database-permission answer carries server internals; everything else may show the server's own kind sentence.
          const message = general.kind === "database_permission" ? general.message : detailMessage(response.status, json, general.message);
          return { ok: false, message, status: response.status };
        }
        return { ok: true, data: json as T };
      } catch (error) {
        return { ok: false, message: classifyFailure(failureFromError(error)).message, status: 0 };
      }
    },
    [fetchBubbles],
  );
}

/* ── Page shell ─────────────────────────────────────────────────────── */

const SECTIONS = [
  { href: "/fitness", label: "Overview" },
  { href: "/fitness/diet", label: "Diet" },
  { href: "/fitness/workouts", label: "Workouts" },
  { href: "/fitness/calories", label: "Calories" },
  { href: "/fitness/transform", label: "Transform" },
  { href: "/fitness/progress", label: "Progress" },
];

export function SubNav() {
  const pathname = usePathname() ?? "";
  return (
    <nav aria-label="Fitness sections" className="mb-6">
      <ul className="m-0 flex list-none flex-wrap gap-2 p-0">
        {SECTIONS.map((s) => {
          const active = s.href === "/fitness" ? pathname === "/fitness" : pathname === s.href || pathname.startsWith(`${s.href}/`);
          return (
            <li key={s.href}>
              <Link
                href={s.href}
                aria-current={active ? "page" : undefined}
                className={`bubbles-press inline-flex min-h-[44px] items-center rounded-full border-2 px-4 text-body-sm font-extrabold no-underline ${
                  active ? "border-bubbles-grape bg-tint-grape text-bubbles-grape-deep" : "border-line bg-surface text-muted hover:border-line-strong hover:text-ink"
                }`}
              >
                {s.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

export function FitnessPage({ title, children }: { title: string; children: ReactNode; subnav?: boolean }) {
  return (
    <HubPage title={title}>
      {/* Section tabs now come from the shared SectionTabs bar in HubPage; the old in-page bar was a duplicate. */}
      {children}
    </HubPage>
  );
}

export function PageHeading({ kicker, title, text }: { kicker?: string; title: string; text?: string }) {
  return (
    <header className="mb-5">
      {kicker && <p className="m-0 text-label font-extrabold uppercase tracking-wide text-subtle">{kicker}</p>}
      <h1 className="m-0 font-display text-h1 text-ink">{title}</h1>
      {text && <p className="m-0 mt-2 max-w-2xl text-body text-muted">{text}</p>}
    </header>
  );
}

export function Section({ title, children, aside, id }: { title?: string; children: ReactNode; aside?: ReactNode; id?: string }) {
  const hid = useId();
  return (
    <section aria-labelledby={title ? hid : undefined} id={id} className={`${CARD} p-5 sm:p-6`}>
      {(title || aside) && (
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          {title && (
            <h2 id={hid} className="m-0 font-display text-h3 text-ink">
              {title}
            </h2>
          )}
          {aside}
        </div>
      )}
      {children}
    </section>
  );
}

/* ── Estimates ──────────────────────────────────────────────────────── */

export function EstimateLabel({ children = "Estimate" }: { children?: ReactNode }) {
  return (
    <span title="Bubbles' numbers are estimates, not measurements" className={`${PILL} !px-2 !py-0.5 border border-line bg-blush !text-[0.75rem] text-ink-soft`}>
      {children}
    </span>
  );
}

/** "710 kcal" with the honest range next to it: "est. 524–896". */
export function RangeBadge({ value, low, high, unit = "kcal" }: { value: number; low: number; high: number; unit?: string }) {
  const showRange = Number.isFinite(low) && Number.isFinite(high) && Math.round(low) !== Math.round(high);
  return (
    <span className="inline-flex flex-wrap items-baseline gap-x-1.5">
      <span className="font-extrabold text-ink">
        {fmt(value)} {unit}
      </span>
      {showRange && (
        <span className="text-body-sm text-muted">
          <span className="sr-only">estimated range </span>
          <span aria-hidden="true">est. </span>
          {fmt(low)}–{fmt(high)}
        </span>
      )}
    </span>
  );
}

/* ── Notices ────────────────────────────────────────────────────────── */

const NOTICE_TONE: Record<"sky" | "mint" | "sun" | "pink" | "plain", string> = {
  sky: "bg-tint-sky text-ink",
  mint: "bg-tint-mint text-ink",
  sun: "bg-tint-sun text-ink",
  pink: "bg-tint-pink text-ink",
  plain: "bg-blush text-ink border border-line",
};

export function Notice({ tone = "sky", title, children, role }: { tone?: keyof typeof NOTICE_TONE; title?: string; children: ReactNode; role?: "status" | "alert" }) {
  return (
    <div role={role} className={`rounded-3xl px-5 py-4 ${NOTICE_TONE[tone]}`}>
      {title && <p className="m-0 font-display text-h4">{title}</p>}
      <div className="text-body-sm">{children}</div>
    </div>
  );
}

/**
 * The "pending clinician review" notice. Calm sky tone, never alarming. Shown whenever review.reviewed is false.
 */
export function ClinicalNote({ review }: { review: Review | null | undefined }) {
  if (!reviewPending(review)) return null;
  return (
    <aside aria-label="About these numbers" className="mb-5 rounded-3xl bg-tint-sky px-5 py-4 text-ink">
      <p className="m-0 text-body-sm font-extrabold text-bubbles-sky-deep">Waiting for a clinician&rsquo;s review</p>
      <p className="m-0 mt-1 text-body-sm">
        Bubbles&rsquo;s targets are general estimates and have not yet been checked by a clinician. Treat them as a starting point.
      </p>
      <details className="mt-2">
        <summary className="inline-flex min-h-[44px] cursor-pointer items-center text-body-sm font-extrabold text-bubbles-sky-deep">What does this mean?</summary>
        <div className="mt-1 text-body-sm text-ink-soft">
          <p className="m-0">{review?.notice}</p>
          <p className="m-0 mt-2">
            In plain words: the maths comes from public health guidance, but a doctor or dietitian has not signed it off yet. Estimates are never exact, and
            real life varies. Bubbles does not diagnose or prescribe. Please talk to a doctor or dietitian before big changes, especially if you have a health
            condition or take medicine.
          </p>
        </div>
      </details>
    </aside>
  );
}

/** Fetches the review state (the cheap /fitness/targets call) for pages whose own data does not carry it. */
export function ReviewNote() {
  const [q] = useBubblesQuery<{ review: Review }>("/fitness/targets");
  return q.status === "ready" ? <ClinicalNote review={q.data.review} /> : null;
}

/** One quiet line under numbers. */
export function Disclaimer() {
  return <p className="m-0 text-body-sm text-muted">Estimates, not medical advice. Talk to a doctor or dietitian before big changes.</p>;
}

/* ── Progress ring ──────────────────────────────────────────────────── */

export function ProgressRing({ fraction, size = 168, stroke = 14, tone = "mint", label, children }: {
  fraction: number; size?: number; stroke?: number; tone?: Tone; label: string; children?: ReactNode;
}) {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const f = Math.min(1, Math.max(0, Number.isFinite(fraction) ? fraction : 0));
  const ring = { mint: "var(--bubbles-mint)", pink: "var(--bubbles-pink)", grape: "var(--bubbles-grape)", sky: "var(--bubbles-sky)", peach: "var(--bubbles-peach)", sun: "var(--bubbles-sun)", plain: "var(--bubbles-ink-soft)" }[tone];
  return (
    <div className="relative inline-flex shrink-0 items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label={label} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--bubbles-line)" strokeWidth={stroke} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={ring}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={c * (1 - f)}
          className="transition-[stroke-dashoffset] duration-500 motion-reduce:transition-none"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center px-4 text-center">{children}</div>
    </div>
  );
}

/* ── Macro bars ─────────────────────────────────────────────────────── */

const BAR_TONE: Record<MacroRow["key"], string> = { protein: "bg-bubbles-grape", carbs: "bg-bubbles-sun", fat: "bg-bubbles-peach", fibre: "bg-bubbles-mint" };

export function MacroBars({ eaten, target }: {
  eaten: { protein_g: number; carbs_g: number; fat_g: number; fibre_g: number };
  target: { protein_g: number; carbs_g: number; fat_g: number; fibre_g: number } | null;
}) {
  const rows = macroRows(eaten, target);
  return (
    <ul className="m-0 flex list-none flex-col gap-3 p-0" aria-label="Macros today">
      {rows.map((r) => (
        <li key={r.key}>
          <div className="mb-1 flex items-baseline justify-between gap-2 text-body-sm">
            <span className="font-extrabold text-ink">{r.label}</span>
            <span className="text-muted">
              {fmt(r.eaten)}
              {r.target ? ` of about ${r.target}` : ""} g
            </span>
          </div>
          <div
            role="meter"
            aria-label={`${r.label} so far`}
            aria-valuemin={0}
            aria-valuemax={r.target || 100}
            aria-valuenow={Math.min(r.eaten, r.target || 100)}
            aria-valuetext={r.target ? `${fmt(r.eaten)} of about ${r.target} grams` : `${fmt(r.eaten)} grams`}
            className="h-3 overflow-hidden rounded-full bg-line"
          >
            <div className={`h-full rounded-full ${BAR_TONE[r.key]} transition-[width] duration-500 motion-reduce:transition-none`} style={{ width: `${r.pct}%` }} />
          </div>
        </li>
      ))}
    </ul>
  );
}

/* ── Consent ────────────────────────────────────────────────────────── */

export function ConsentCard({ id, checked, onChange, title, children, label }: {
  id: string; checked: boolean; onChange: (v: boolean) => void; title: string; children: ReactNode; label: string;
}) {
  return (
    <div className="rounded-3xl border-2 border-bubbles-grape bg-tint-grape p-5">
      <h3 className="m-0 font-display text-h4 text-ink">{title}</h3>
      <div className="mt-2 flex flex-col gap-2 text-body-sm text-ink">{children}</div>
      <label htmlFor={id} className="mt-4 flex min-h-[44px] cursor-pointer items-start gap-3 text-body font-extrabold text-ink">
        <input id={id} type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} className="mt-0.5 h-6 w-6 shrink-0 accent-[var(--bubbles-grape)]" />
        <span>{label}</span>
      </label>
    </div>
  );
}

/* ── Sheet (native modal dialog: focus trapped by the browser, Escape closes, focus returns) ─ */

export function Sheet({ open, onClose, title, children }: { open: boolean; onClose: () => void; title: string; children: ReactNode }) {
  const ref = useRef<HTMLDialogElement>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const titleId = useId();

  useEffect(() => {
    const dialog = ref.current;
    if (!open || !dialog) return;
    const trigger = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const root = document.documentElement;
    const overflow = root.style.overflow;
    if (!dialog.open) dialog.showModal();
    root.style.overflow = "hidden";
    heading.current?.focus({ preventScroll: true });
    dialog.scrollTop = 0;
    return () => {
      if (dialog.open) dialog.close();
      root.style.overflow = overflow;
      trigger?.focus();
    };
  }, [open]);

  return (
    <dialog
      ref={ref}
      aria-labelledby={titleId}
      onClose={onClose}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      className="m-0 mt-auto max-h-[94dvh] w-full max-w-none overflow-y-auto overscroll-contain bg-transparent p-0 text-ink backdrop:bg-ink/55 sm:m-auto sm:w-[calc(100%-2rem)] sm:max-w-[600px]"
    >
      {open && (
        <div className="bubbles-sheet-up flex flex-col gap-4 rounded-t-[36px] bg-surface px-5 pb-[max(1.75rem,env(safe-area-inset-bottom))] pt-4 sm:rounded-[32px] sm:px-7 sm:pb-7 sm:pt-6">
          <div className="flex items-start justify-between gap-3">
            <h2 id={titleId} ref={heading} tabIndex={-1} className="m-0 font-display text-h2 text-ink outline-none">
              {title}
            </h2>
            <button
              type="button"
              onClick={onClose}
              aria-label="Close"
              className="bubbles-press flex h-11 w-11 shrink-0 items-center justify-center rounded-full border-2 border-line bg-surface text-muted hover:text-ink"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" aria-hidden="true">
                <path d="M6 6l12 12M18 6 6 18" />
              </svg>
            </button>
          </div>
          {children}
        </div>
      )}
    </dialog>
  );
}

/* ── Form bits ──────────────────────────────────────────────────────── */

export const INPUT =
  "w-full min-w-0 min-h-[48px] rounded-[20px] border-2 border-line bg-surface px-4 py-3 text-body text-ink placeholder:text-ink-faint hover:border-line-strong focus:border-bubbles-grape aria-[invalid=true]:border-bubbles-pink-ink";

export function Field({ id, label, hint, error, optional, children }: { id: string; label: string; hint?: string; error?: string | null; optional?: boolean; children: ReactNode }) {
  return (
    <div className="flex min-w-0 flex-col gap-1.5">
      <label htmlFor={id} className="text-body font-extrabold text-ink">
        {label}
        {optional && <span className="font-semibold text-muted"> (optional)</span>}
      </label>
      {hint && (
        <p id={`${id}-hint`} className="m-0 text-body-sm text-muted">
          {hint}
        </p>
      )}
      {children}
      {error && (
        <p id={`${id}-error`} role="alert" className="m-0 text-body-sm font-bold text-bubbles-pink-deep">
          {error}
        </p>
      )}
    </div>
  );
}

export function NumField({ id, label, value, onChange, hint, error, optional, unit, min, max, step = "any" }: {
  id: string; label: string; value: string; onChange: (v: string) => void; hint?: string; error?: string | null; optional?: boolean; unit?: string; min?: number; max?: number; step?: number | "any";
}) {
  return (
    <Field id={id} label={label} hint={hint} error={error} optional={optional}>
      <div className="flex items-center gap-2">
        <input
          id={id}
          type="number"
          inputMode="decimal"
          min={min}
          max={max}
          step={step}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          aria-invalid={error ? true : undefined}
          aria-describedby={[hint && `${id}-hint`, error && `${id}-error`].filter(Boolean).join(" ") || undefined}
          className={INPUT}
        />
        {unit && <span className="shrink-0 text-body font-extrabold text-muted">{unit}</span>}
      </div>
    </Field>
  );
}

export function SelectField({ id, label, value, onChange, options, hint, error, optional }: {
  id: string; label: string; value: string; onChange: (v: string) => void; options: { value: string; label: string }[]; hint?: string; error?: string | null; optional?: boolean;
}) {
  return (
    <Field id={id} label={label} hint={hint} error={error} optional={optional}>
      <select
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        aria-invalid={error ? true : undefined}
        aria-describedby={[hint && `${id}-hint`, error && `${id}-error`].filter(Boolean).join(" ") || undefined}
        className={INPUT}
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </Field>
  );
}

export function Chip({ on, onClick, children, onRemove, removeLabel }: { on?: boolean; onClick?: () => void; children: ReactNode; onRemove?: () => void; removeLabel?: string }) {
  if (onRemove) {
    return (
      <span className="inline-flex min-h-[44px] items-center gap-1 rounded-full border-2 border-bubbles-grape bg-tint-grape pl-4 pr-1 text-body-sm font-extrabold text-bubbles-grape-deep">
        {children}
        <button type="button" onClick={onRemove} aria-label={removeLabel ?? "Remove"} className="bubbles-press flex h-11 w-11 items-center justify-center rounded-full hover:bg-surface">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" aria-hidden="true">
            <path d="M6 6l12 12M18 6 6 18" />
          </svg>
        </button>
      </span>
    );
  }
  return (
    <button
      type="button"
      aria-pressed={on}
      onClick={onClick}
      className={`bubbles-press inline-flex min-h-[44px] items-center gap-1.5 rounded-full border-2 px-4 text-body-sm font-extrabold ${
        on ? "border-bubbles-grape bg-tint-grape text-bubbles-grape-deep" : "border-line bg-surface text-muted hover:border-line-strong hover:text-ink"
      }`}
    >
      {on && <span aria-hidden="true">✓</span>}
      {children}
    </button>
  );
}

/** Single choice from a few options (radio semantics via aria-pressed chips in a labelled group). */
export function ChoiceGroup({ legend, value, onChange, options, hint }: { legend: string; value: string; onChange: (v: string) => void; options: { value: string; label: string }[]; hint?: string }) {
  return (
    <fieldset className="m-0 flex min-w-0 flex-col gap-2 border-0 p-0">
      <legend className="mb-1 p-0 text-body font-extrabold text-ink">{legend}</legend>
      {hint && <p className="m-0 text-body-sm text-muted">{hint}</p>}
      <div className="flex flex-wrap gap-2">
        {options.map((o) => (
          <Chip key={o.value} on={o.value === value} onClick={() => onChange(o.value)}>
            {o.label}
          </Chip>
        ))}
      </div>
    </fieldset>
  );
}

/** Multi-select from fixed options. */
export function MultiChoice({ legend, values, onChange, options, hint }: { legend: string; values: string[]; onChange: (v: string[]) => void; options: { value: string; label: string }[]; hint?: string }) {
  return (
    <fieldset className="m-0 flex min-w-0 flex-col gap-2 border-0 p-0">
      <legend className="mb-1 p-0 text-body font-extrabold text-ink">{legend}</legend>
      {hint && <p className="m-0 text-body-sm text-muted">{hint}</p>}
      <div className="flex flex-wrap gap-2">
        {options.map((o) => {
          const on = values.includes(o.value);
          return (
            <Chip key={o.value} on={on} onClick={() => onChange(on ? values.filter((v) => v !== o.value) : [...values, o.value])}>
              {o.label}
            </Chip>
          );
        })}
      </div>
    </fieldset>
  );
}

/** Free-text chips: type, press Enter or Add. Suggestions are optional quick picks. */
export function TagInput({ id, label, values, onChange, suggestions = [], hint, placeholder, max = 20, optional }: {
  id: string; label: string; optional?: boolean; values: string[]; onChange: (v: string[]) => void; suggestions?: string[]; hint?: string; placeholder?: string; max?: number;
}) {
  const [text, setText] = useState("");
  const add = (raw: string) => {
    const v = raw.trim().slice(0, 40);
    if (!v || values.some((x) => x.toLowerCase() === v.toLowerCase()) || values.length >= max) return;
    onChange([...values, v]);
    setText("");
  };
  return (
    <div className="flex min-w-0 flex-col gap-2">
      <label htmlFor={id} className="text-body font-extrabold text-ink">
        {label}
        {optional && <span className="font-semibold text-muted"> (optional)</span>}
      </label>
      {hint && (
        <p id={`${id}-hint`} className="m-0 text-body-sm text-muted">
          {hint}
        </p>
      )}
      {values.length > 0 && (
        <ul className="m-0 flex list-none flex-wrap gap-2 p-0" aria-label={`${label}, chosen`}>
          {values.map((v) => (
            <li key={v}>
              <Chip onRemove={() => onChange(values.filter((x) => x !== v))} removeLabel={`Remove ${v}`}>
                {v}
              </Chip>
            </li>
          ))}
        </ul>
      )}
      <div className="flex gap-2">
        <input
          id={id}
          type="text"
          value={text}
          maxLength={40}
          placeholder={placeholder}
          aria-describedby={hint ? `${id}-hint` : undefined}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              add(text);
            }
          }}
          className={INPUT}
        />
        <button type="button" onClick={() => add(text)} disabled={!text.trim()} className="bubbles-press min-h-[48px] shrink-0 rounded-full border-2 border-ink bg-surface px-5 text-body-sm font-extrabold text-ink disabled:opacity-50">
          Add
        </button>
      </div>
      {suggestions.filter((s) => !values.some((v) => v.toLowerCase() === s.toLowerCase())).length > 0 && (
        <div role="group" aria-label={`Quick picks for ${label.toLowerCase()}`} className="flex flex-wrap gap-2">
          {suggestions
            .filter((s) => !values.some((v) => v.toLowerCase() === s.toLowerCase()))
            .map((s) => (
              <Chip key={s} onClick={() => add(s)}>
                + {s}
              </Chip>
            ))}
        </div>
      )}
    </div>
  );
}

export function CheckRow({ id, checked, onChange, children }: { id: string; checked: boolean; onChange: (v: boolean) => void; children: ReactNode }) {
  return (
    <label htmlFor={id} className="flex min-h-[44px] cursor-pointer items-center gap-3 text-body font-bold text-ink">
      <input id={id} type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} className="h-6 w-6 shrink-0 accent-[var(--bubbles-grape)]" />
      <span>{children}</span>
    </label>
  );
}

/** Result text that screen readers hear when it changes. */
export function LiveMessage({ message, tone = "plain" }: { message: string | null; tone?: "plain" | "error" }) {
  return (
    <div aria-live="polite" role={tone === "error" ? "alert" : undefined}>
      {message && <p className={`m-0 rounded-2xl px-4 py-3 text-body-sm font-bold ${tone === "error" ? "bg-tint-pink text-bubbles-pink-deep" : "bg-tint-mint text-bubbles-mint-deep"}`}>{message}</p>}
    </div>
  );
}

export function Pill({ tone = "plain", children }: { tone?: Tone; children: ReactNode }) {
  return <span className={`${PILL} ${TONE[tone].chip}`}>{children}</span>;
}

export const BTN_GHOST = "bubbles-press inline-flex min-h-[44px] items-center justify-center rounded-full px-4 text-body-sm font-extrabold text-bubbles-grape-deep hover:bg-tint-grape disabled:opacity-60";
