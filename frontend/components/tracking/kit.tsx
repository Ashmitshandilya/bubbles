"use client";

import { useEffect, useId, useRef, useState, type FormEvent, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { ApiAlert, Header, MobileNav, SectionTabs, Sidebar } from "../Navigation";
import { BubblesMascot } from "../BubblesMascot";
import { SoapPop } from "../SoapPop";
import { useApi, useAuth } from "../Providers";
import {
  byNewest, dayLabel, daysAgo, formatNumber, parseWhen, present, startOfDay, toNumber,
  type Entry, type EntryValue, type LoadStatus, type StatValue,
} from "./data";
import { buildPulse, lastLoggedText, weekText } from "../../app/lib/track-pulse";

/* ── Signal colours (literal class strings so Tailwind can see them) ─── */

export type Signal = "pink" | "grape" | "sun" | "mint" | "sky" | "peach";

const SIGNALS: Record<Signal, { tint: string; ink: string; button: string; solid: string; border: string; dashed: string; chipOn: string; bar: string; barSoft: string }> = {
  pink: {
    tint: "bg-tint-pink", ink: "text-bubbles-pink-deep",
    button: "bg-bubbles-pink-ink text-white bubbles-glow", solid: "bg-bubbles-pink-ink text-white",
    border: "border-line", dashed: "border-[#FFB3D3]", chipOn: "border-bubbles-pink-ink bg-tint-pink text-bubbles-pink-deep",
    bar: "bg-bubbles-pink", barSoft: "bg-[#FFC2DC]",
  },
  grape: {
    tint: "bg-tint-grape", ink: "text-bubbles-grape-deep",
    button: "bg-bubbles-grape text-white bubbles-glow bubbles-glow-grape", solid: "bg-bubbles-grape text-white",
    border: "border-[#E4DCFF]", dashed: "border-[#C9BCFF]", chipOn: "border-bubbles-grape bg-tint-grape text-bubbles-grape-deep",
    bar: "bg-bubbles-grape", barSoft: "bg-[#C9BCFF]",
  },
  sun: {
    tint: "bg-tint-sun", ink: "text-bubbles-sun-deep",
    button: "bg-bubbles-sun text-ink bubbles-glow bubbles-glow-sun", solid: "bg-bubbles-sun text-ink",
    border: "border-[#FCE8A9]", dashed: "border-[#F5CF5B]", chipOn: "border-bubbles-sun-deep bg-tint-sun text-bubbles-sun-deep",
    bar: "bg-bubbles-sun", barSoft: "bg-[#FCE8A9]",
  },
  mint: {
    tint: "bg-tint-mint", ink: "text-bubbles-mint-deep",
    button: "bg-bubbles-mint-deep text-white bubbles-glow bubbles-glow-mint", solid: "bg-bubbles-mint-deep text-white",
    border: "border-[#CFF1E4]", dashed: "border-[#8FDCC2]", chipOn: "border-bubbles-mint-deep bg-tint-mint text-bubbles-mint-deep",
    bar: "bg-bubbles-mint", barSoft: "bg-[#A9E8D2]",
  },
  sky: {
    tint: "bg-tint-sky", ink: "text-bubbles-sky-deep",
    button: "bg-bubbles-sky-deep text-white bubbles-glow bubbles-glow-sky", solid: "bg-bubbles-sky-deep text-white",
    border: "border-[#D3ECFF]", dashed: "border-[#9FD3FF]", chipOn: "border-bubbles-sky-deep bg-tint-sky text-bubbles-sky-deep",
    bar: "bg-bubbles-sky", barSoft: "bg-[#9FD3FF]",
  },
  peach: {
    tint: "bg-tint-peach", ink: "text-bubbles-peach-deep",
    button: "bg-bubbles-peach-deep text-white bubbles-glow bubbles-glow-peach", solid: "bg-bubbles-peach-deep text-white",
    border: "border-[#FFD9C8]", dashed: "border-[#FFB894]", chipOn: "border-bubbles-peach-deep bg-tint-peach text-bubbles-peach-deep",
    bar: "bg-bubbles-peach", barSoft: "bg-[#FFC9AE]",
  },
};

/* ── Icons ─────────────────────────────────────────────────────────────
   ponytail: same paths as Navigation's private ICON_PATHS; reuse them once Navigation exports its icon. */

const ICONS = {
  cycle: "M20 11a8 8 0 1 0-1.5 5.5M20 4v7h-7",
  symptoms: "M12 4 2.5 20h19L12 4zM12 10v4M12 17.3v.1",
  sleep: "M20 14.5A8.5 8.5 0 0 1 9.5 4a8.5 8.5 0 1 0 10.5 10.5z",
  hydration: "M12 3s6 6.5 6 10.5a6 6 0 0 1-12 0C6 9.5 12 3 12 3z",
  nutrition: "M12 8C12 5 14.5 3 17.5 3c0 3-2.5 5-5.5 5zM12 8C12 5 9.5 3 6.5 3c0 3 2.5 5 5.5 5zM12 8C8.5 8 6 10.5 6 14.5S9 21 12 21s6-2.5 6-6.5S15.5 8 12 8z",
  mood: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM8.5 14a4.5 4.5 0 0 0 7 0M9 9.5v.1M15 9.5v.1",
  activity: "M3 12h4l3-8 4 16 3-8h4",
  weight: "M4 8h16l-1.5 12h-13zM12 8V5.5M9.5 5.5h5",
  vitals: "M4 4h16v16H4zM7.5 12h2l1.5-3.5L13 15l1.5-3h2",
  medications: "M10.5 20.5a5 5 0 0 1-7-7l7-7a5 5 0 0 1 7 7zM8.5 8.5l7 7",
  conditions: "M9 4h6v3H9zM7 5H5v16h14V5h-2",
  allergies: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM5.6 5.6l12.8 12.8",
  labs: "M9 3v6l-4.5 8A2 2 0 0 0 6.2 20h11.6a2 2 0 0 0 1.7-3L15 9V3M8 3h8M7.5 14h9",
  reports: "M6 3h8l4 4v14H6zM14 3v4h4M9 12h6M9 16h6",
  visits: "M4 21V8l8-5 8 5v13M9 21v-6h6v6",
  plus: "M12 5v14M5 12h14",
  minus: "M5 12h14",
  close: "M6 6l12 12M18 6 6 18",
} as const;

export type IconName = keyof typeof ICONS;

export function Icon({ name, size = 22 }: { name: IconName; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
      <path d={ICONS[name]} />
    </svg>
  );
}

/* ── Page chrome ───────────────────────────────────────────────────── */

/** Auth gate + app navigation. Children mount only with a session, so data hooks can assume one. */
export function TrackerShell({ title, children }: { title: string; children: ReactNode }) {
  const router = useRouter();
  const { loading, session } = useAuth();
  const { apiStatus, connectionError, checkApiHealth } = useApi();

  useEffect(() => {
    if (!loading && !session) router.push("/login");
  }, [loading, session, router]);

  if (loading) {
    return (
      <main className="flex min-h-dvh items-center justify-center bg-blush px-4">
        <div className="flex flex-col items-center gap-4 text-center" role="status">
          <BubblesMascot size={88} mood="thinking" />
          <p className="text-body font-bold text-muted">Opening {title.toLowerCase()}…</p>
        </div>
      </main>
    );
  }
  if (!session) return null;

  return (
    <div className="flex min-h-dvh flex-col bg-blush">
      <Header apiStatus={apiStatus} currentPage={title} />
      <ApiAlert connectionError={connectionError} onRetry={checkApiHealth} />
      <div className="flex flex-1">
        <Sidebar apiStatus={apiStatus} />
        <main className="min-w-0 flex-1 px-4 pb-10 pt-5 sm:px-6 lg:px-10 lg:pt-8">
          <div className="mx-auto flex w-full max-w-[920px] flex-col gap-6">
            <SectionTabs />
            {children}
          </div>
        </main>
      </div>
      <MobileNav />
    </div>
  );
}

export function TrackerHero({ signal, icon, kicker, title, why, action }: {
  signal: Signal; icon: IconName; kicker: string; title: string; why: string; action: ReactNode;
}) {
  const s = SIGNALS[signal];
  return (
    <section aria-labelledby="tracker-title" className={`bubbles-rise relative overflow-hidden rounded-[32px] p-5 sm:p-7 ${s.tint}`}>
      <span aria-hidden="true" className="bubbles-drift-slow pointer-events-none absolute -right-12 -top-14 h-44 w-44 rounded-full bg-white/45" />
      <div className="relative flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex min-w-0 items-start gap-4">
          <span className={`flex h-14 w-14 shrink-0 items-center justify-center rounded-[20px] bg-surface ${s.ink}`}>
            <Icon name={icon} size={28} />
          </span>
          <div className="min-w-0">
            <p className={`text-label font-extrabold ${s.ink}`}>{kicker}</p>
            <h1 id="tracker-title" className="mt-1 break-words font-display text-h1 text-default">{title}</h1>
            <p className="mt-2 max-w-xl text-body text-muted">{why}</p>
          </div>
        </div>
        <div className="shrink-0">{action}</div>
      </div>
    </section>
  );
}

/** The Track hub links here with `?log=1`: open the log sheet once, then drop the flag so a refresh does not reopen it. */
function useOpenFromHub(open: () => void) {
  const openRef = useRef(open);
  useEffect(() => {
    openRef.current = open;
  });
  useEffect(() => {
    const url = new URL(window.location.href);
    if (url.searchParams.get("log") !== "1") return;
    url.searchParams.delete("log");
    window.history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
    openRef.current();
  }, []);
}

export function LogButton({ signal, onClick, children, wide = false }: { signal: Signal; onClick: () => void; children: ReactNode; wide?: boolean }) {
  useOpenFromHub(onClick);
  return (
    <button
      type="button"
      onClick={onClick}
      className={`bubbles-press inline-flex min-h-[52px] items-center justify-center gap-2 rounded-full px-6 text-body font-extrabold ${SIGNALS[signal].button} ${wide ? "w-full" : "w-full sm:w-auto"}`}
    >
      <Icon name="plus" size={20} />
      {children}
    </button>
  );
}

export function StatGrid({ stats, signal }: { stats: StatValue[]; signal: Signal }) {
  const s = SIGNALS[signal];
  const cols = stats.length >= 4 ? "lg:grid-cols-4" : stats.length === 3 ? "sm:grid-cols-3" : "";
  return (
    <dl aria-label="Summary" className={`bubbles-stagger m-0 grid grid-cols-2 gap-3 max-sm:[&>*:last-child:nth-child(odd)]:col-span-2 ${cols}`}>
      {stats.map((st) => (
        <div key={st.label} className={`flex min-w-0 flex-col gap-1 rounded-[24px] border-2 bg-surface p-4 ${st.value === null ? `border-dashed ${s.dashed}` : s.border}`}>
          <dt className={`text-body-sm font-extrabold ${s.ink}`}>{st.label}</dt>
          <dd className="m-0 break-words">
            {st.value === null ? (
              <span className="font-display text-h4 text-muted">{st.gap ?? "Not logged yet"}</span>
            ) : (
              <span data-private className="font-display text-metric text-default">{st.value}</span>
            )}
          </dd>
          {st.note && <dd className="m-0 text-body-sm font-semibold text-muted">{st.note}</dd>}
        </div>
      ))}
    </dl>
  );
}

/** "Logged today. Logged on 3 of the last 7 days." Nothing is shown until there is an entry to describe. */
export function LastLogged({ entries }: { entries: Entry[] }) {
  const pulse = buildPulse(entries);
  if (pulse.lastAgo === null) return null;
  return (
    <p className="m-0 text-body-sm font-bold text-muted">
      {lastLoggedText(pulse)}. {weekText(pulse)}.
    </p>
  );
}

export function StatSkeleton({ count }: { count: number }) {
  return (
    <div aria-hidden="true" className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {Array.from({ length: count }, (_, i) => (
        <div key={i} className="bubbles-skeleton h-[104px] rounded-[24px]" />
      ))}
    </div>
  );
}

export function Disclaimer() {
  return (
    <p className="text-body-sm font-semibold text-muted">
      Bubbles shares patterns and general guidance, not diagnoses. Missing data shows as a gap, never as &ldquo;all clear&rdquo;.
    </p>
  );
}

/* ── Log sheet (bottom sheet on phones, centred dialog from 640px) ──── */

function Spinner() {
  return (
    <svg className="h-5 w-5 animate-spin motion-reduce:animate-none" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeOpacity="0.3" strokeWidth="3" />
      <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}

function focusFirstInvalid(form: HTMLFormElement | null) {
  const bad = form?.querySelector<HTMLElement>('[aria-invalid="true"]');
  const target = bad?.matches("input, textarea, button") ? bad : bad?.querySelector<HTMLElement>("button, input, textarea");
  target?.focus();
}

/**
 * Native modal <dialog>: focus is trapped by the browser (the page behind is inert), Esc closes,
 * backdrop click closes, and focus returns to whatever opened it.
 * `onSubmit` resolves null when saved (sheet closes), false when inline validation failed
 * (first invalid field is focused), or an error message to show in role="alert".
 */
export function LogSheet({ open, onClose, signal, icon, title, subtitle, submitLabel, onSubmit, children }: {
  open: boolean; onClose: () => void; signal: Signal; icon: IconName; title: string; subtitle?: string;
  submitLabel: string; onSubmit: () => Promise<string | null | false>; children: ReactNode;
}) {
  const s = SIGNALS[signal];
  const dialogRef = useRef<HTMLDialogElement>(null);
  const formRef = useRef<HTMLFormElement>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);
  const titleId = useId();
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!open || !dialog) return;
    const trigger = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const root = document.documentElement;
    const overflow = root.style.overflow;
    setError(null);
    if (!dialog.open) dialog.showModal();
    root.style.overflow = "hidden";
    headingRef.current?.focus();
    return () => {
      if (dialog.open) dialog.close();
      root.style.overflow = overflow;
      trigger?.focus();
    };
  }, [open]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (saving) return;
    setError(null);
    setSaving(true);
    const result = await onSubmit();
    setSaving(false);
    if (result === null) onClose();
    else if (result === false) window.setTimeout(() => focusFirstInvalid(formRef.current), 0);
    else setError(result);
  }

  return (
    <dialog
      ref={dialogRef}
      aria-labelledby={titleId}
      onCancel={(e) => {
        if (saving) e.preventDefault();
      }}
      onClose={onClose}
      onClick={(e) => {
        if (e.target === e.currentTarget && !saving) onClose();
      }}
      className="m-0 mt-auto max-h-[94dvh] w-full max-w-none overflow-y-auto overscroll-contain bg-transparent p-0 text-default backdrop:bg-ink/55 sm:m-auto sm:w-[calc(100%-2rem)] sm:max-w-[560px]"
    >
      {open && (
        <div className="bubbles-sheet-up flex flex-col gap-5 rounded-t-[36px] bg-surface px-5 pb-[max(1.75rem,env(safe-area-inset-bottom))] pt-3 sm:rounded-[32px] sm:px-7 sm:pb-7 sm:pt-6">
          <span aria-hidden="true" className="mx-auto h-1.5 w-12 rounded-full bg-line sm:hidden" />
          <div className="flex items-center gap-3">
            <span className={`flex h-[52px] w-[52px] shrink-0 items-center justify-center rounded-[18px] ${s.tint} ${s.ink}`}>
              <Icon name={icon} size={26} />
            </span>
            <div className="min-w-0 flex-1">
              <h2 id={titleId} ref={headingRef} tabIndex={-1} className="font-display text-h2 text-default outline-none">
                {title}
              </h2>
              {subtitle && <p className="text-body-sm font-bold text-muted">{subtitle}</p>}
            </div>
            <button
              type="button"
              onClick={onClose}
              disabled={saving}
              aria-label="Close"
              className="bubbles-press flex h-11 w-11 shrink-0 items-center justify-center rounded-full border-2 border-line bg-surface text-muted hover:text-default disabled:opacity-50"
            >
              <Icon name="close" size={20} />
            </button>
          </div>
          <form ref={formRef} noValidate onSubmit={handleSubmit} className="flex flex-col gap-5">
            {children}
            {error && (
              <p role="alert" className="m-0 rounded-2xl bg-tint-pink px-4 py-3 text-body-sm font-bold text-bubbles-pink-deep">
                {error}
              </p>
            )}
            <button
              type="submit"
              aria-disabled={saving || undefined}
              className={`bubbles-press flex min-h-[56px] items-center justify-center gap-2 rounded-full px-6 text-[1.0625rem] font-extrabold aria-disabled:cursor-wait aria-disabled:opacity-75 ${s.button}`}
            >
              {saving ? (
                <>
                  <Spinner />
                  Saving…
                </>
              ) : error ? (
                // The sheet stays open with everything typed; saving again is the retry.
                "Try saving again"
              ) : (
                submitLabel
              )}
            </button>
          </form>
        </div>
      )}
    </dialog>
  );
}

/* ── Form controls ─────────────────────────────────────────────────── */

const BOX =
  "w-full min-w-0 rounded-[20px] border-2 border-line bg-surface px-4 py-3 text-body text-default placeholder:text-ink-faint hover:border-line-strong focus:border-bubbles-grape aria-[invalid=true]:border-bubbles-pink-ink";

function describedBy(id: string, hint?: string, error?: string) {
  return [hint && `${id}-hint`, error && `${id}-error`].filter(Boolean).join(" ") || undefined;
}

function FieldText({ id, hint, error }: { id: string; hint?: string; error?: string }) {
  return (
    <>
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
    </>
  );
}

function LabelText({ label, optional }: { label: string; optional?: boolean }) {
  return (
    <>
      {label}
      {optional && <span className="font-semibold text-muted"> (optional)</span>}
    </>
  );
}

interface BaseField {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  hint?: string;
  error?: string;
  optional?: boolean;
}

export function TextField({ id, label, value, onChange, hint, error, optional, placeholder, maxLength, suggestions, signal }: BaseField & {
  placeholder?: string; maxLength?: number; suggestions?: string[]; signal?: Signal;
}) {
  return (
    <div className="flex min-w-0 flex-col gap-2">
      <label htmlFor={id} className="text-body font-extrabold">
        <LabelText label={label} optional={optional} />
      </label>
      <input
        id={id}
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        maxLength={maxLength}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy(id, hint, error)}
        className={BOX}
      />
      {suggestions && signal && (
        <div role="group" aria-label={`Quick picks for ${label.toLowerCase()}`} className="flex flex-wrap gap-2">
          {suggestions.map((s) => (
            <Chip key={s} signal={signal} on={value.trim().toLowerCase() === s.toLowerCase()} onClick={() => onChange(s)}>
              {s}
            </Chip>
          ))}
        </div>
      )}
      <FieldText id={id} hint={hint} error={error} />
    </div>
  );
}

export function TextArea({ id, label, value, onChange, hint, error, optional, placeholder, maxLength }: BaseField & { placeholder?: string; maxLength?: number }) {
  return (
    <div className="flex min-w-0 flex-col gap-2">
      <label htmlFor={id} className="text-body font-extrabold">
        <LabelText label={label} optional={optional} />
      </label>
      <textarea
        id={id}
        rows={2}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        maxLength={maxLength}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy(id, hint, error)}
        className={`${BOX} resize-y`}
      />
      <FieldText id={id} hint={hint} error={error} />
    </div>
  );
}

export function DateField({ id, label, value, onChange, hint, error, optional, max }: BaseField & { max?: string }) {
  return (
    <div className="flex min-w-0 flex-col gap-2">
      <label htmlFor={id} className="text-body font-extrabold">
        <LabelText label={label} optional={optional} />
      </label>
      <input
        id={id}
        type="date"
        value={value}
        max={max}
        onChange={(e) => onChange(e.target.value)}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy(id, hint, error)}
        className={`${BOX} min-h-[52px]`}
      />
      <FieldText id={id} hint={hint} error={error} />
    </div>
  );
}

function Chip({ signal, on, onClick, children, tall = false }: { signal: Signal; on: boolean; onClick: () => void; children: ReactNode; tall?: boolean }) {
  return (
    <button
      type="button"
      aria-pressed={on}
      onClick={onClick}
      className={`bubbles-press min-h-[48px] border-2 font-extrabold leading-tight ${
        tall ? "min-h-[60px] rounded-[18px] px-1 text-[0.8125rem] break-words sm:text-[0.9375rem]" : "rounded-full px-4 text-body-sm"
      } ${on ? SIGNALS[signal].chipOn : "border-line bg-surface text-muted hover:border-line-strong hover:text-default"}`}
    >
      {children}
    </button>
  );
}

/** Single-choice chips in a fieldset/legend. `columns` lays them out as an equal grid (scales). */
export function Choices({ id, legend, options, value, onChange, signal, columns, hint, error, optional, allowDeselect = true }: {
  id: string; legend: string; options: { value: string; label: string }[]; value: string; onChange: (value: string) => void;
  signal: Signal; columns?: number; hint?: string; error?: string; optional?: boolean; allowDeselect?: boolean;
}) {
  return (
    <fieldset
      id={id}
      aria-invalid={error ? true : undefined}
      aria-describedby={describedBy(id, hint, error)}
      className="m-0 flex min-w-0 flex-col gap-2 border-0 p-0"
    >
      <legend className="mb-2 p-0 text-body font-extrabold">
        <LabelText label={legend} optional={optional} />
      </legend>
      <div
        className={columns ? "grid gap-1.5 sm:gap-2" : "flex flex-wrap gap-2"}
        style={columns ? { gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` } : undefined}
      >
        {options.map((o) => {
          const on = o.value === value;
          return (
            <Chip key={o.value} signal={signal} on={on} tall={Boolean(columns)} onClick={() => onChange(on && allowDeselect ? "" : o.value)}>
              {o.label}
            </Chip>
          );
        })}
      </div>
      <FieldText id={id} hint={hint} error={error} />
    </fieldset>
  );
}

/** Big friendly −/+ number control; the number itself stays typeable. */
export function Stepper({ id, label, value, onChange, hint, error, optional, min, max, step, unit, fallback, presets, signal }: BaseField & {
  min: number; max: number; step: number; unit?: string; fallback: number; presets?: number[]; signal: Signal;
}) {
  const s = SIGNALS[signal];
  const labelId = `${id}-label`;
  const decimals = (String(step).split(".")[1] ?? "").length;
  const current = value.trim() === "" ? null : Number(value);
  const bump = (dir: 1 | -1) => {
    const base = current === null || !Number.isFinite(current) ? fallback : current + dir * step;
    onChange(Math.min(max, Math.max(min, base)).toFixed(decimals));
  };
  const round = "flex h-[52px] w-[52px] shrink-0 items-center justify-center rounded-full disabled:opacity-40";
  return (
    <div className="flex min-w-0 flex-col gap-2">
      <label id={labelId} htmlFor={id} className="text-body font-extrabold">
        <LabelText label={label} optional={optional} />
      </label>
      <div role="group" aria-labelledby={labelId} className={`flex items-center gap-2 rounded-full p-2 ${s.tint}`}>
        <button type="button" onClick={() => bump(-1)} disabled={current !== null && current <= min} aria-label={`Less ${label.toLowerCase()}`} className={`bubbles-press bg-surface ${s.ink} ${round}`}>
          <Icon name="minus" size={22} />
        </button>
        <div className="flex min-w-0 flex-1 items-baseline justify-center gap-1">
          <input
            id={id}
            type="number"
            inputMode="decimal"
            step="any"
            min={min}
            max={max}
            value={value}
            placeholder="–"
            onChange={(e) => onChange(e.target.value)}
            aria-invalid={error ? true : undefined}
            aria-describedby={describedBy(id, hint, error)}
            style={{ width: `${Math.min(Math.max(value.length, 1), 7) + 1}ch` }}
            className="min-w-0 rounded-xl bg-transparent text-center font-display text-[2rem] leading-none text-default [appearance:textfield] placeholder:text-ink-faint [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
          />
          {unit && <span className="shrink-0 font-display text-h3 text-muted">{unit}</span>}
        </div>
        <button type="button" onClick={() => bump(1)} disabled={current !== null && current >= max} aria-label={`More ${label.toLowerCase()}`} className={`bubbles-press ${s.solid} ${round}`}>
          <Icon name="plus" size={22} />
        </button>
      </div>
      {presets && (
        <div role="group" aria-label={`Quick amounts for ${label.toLowerCase()}`} className="flex flex-wrap gap-2">
          {presets.map((p) => (
            <Chip key={p} signal={signal} on={current === p} onClick={() => onChange(String(p))}>
              {formatNumber(p, unit, decimals)}
            </Chip>
          ))}
        </div>
      )}
      <FieldText id={id} hint={hint} error={error} />
    </div>
  );
}

/* ── History, empty / error states, success toast ──────────────────── */

export function EmptyState({ title, text, action }: { title: string; text: string; action: ReactNode }) {
  return (
    <div className="bubbles-rise flex flex-col items-center gap-3 rounded-[28px] border-2 border-dashed border-line-strong bg-surface px-5 py-8 text-center">
      <BubblesMascot size={84} mood="resting" animated={false} />
      <p className="m-0 font-display text-h3 text-default">{title}</p>
      <p className="m-0 max-w-md text-body text-muted">{text}</p>
      <div className="mt-1 w-full max-w-xs">{action}</div>
    </div>
  );
}

export function History({ title = "History", status, error, onRetry, entries, freshId, signal, renderEntry, empty }: {
  title?: string; status: LoadStatus; error: string; onRetry: () => void; entries: Entry[]; freshId: string | null;
  signal: Signal; renderEntry: (entry: Entry) => ReactNode; empty: ReactNode;
}) {
  const headingId = useId();
  const s = SIGNALS[signal];
  const groups: { key: number; label: string; items: Entry[] }[] = [];
  for (const entry of [...entries].sort(byNewest)) {
    const key = startOfDay(parseWhen(entry.date)).getTime();
    const last = groups[groups.length - 1];
    if (last && last.key === key) last.items.push(entry);
    else groups.push({ key, label: dayLabel(entry.date), items: [entry] });
  }

  let body: ReactNode;
  if (status === "loading" && entries.length === 0) {
    body = (
      <div aria-busy="true" className="flex flex-col gap-2.5">
        <span className="sr-only" role="status">Loading entries…</span>
        {[0, 1, 2].map((i) => (
          <div key={i} className="bubbles-skeleton h-[84px] rounded-[24px]" />
        ))}
      </div>
    );
  } else if (status === "error") {
    body = (
      <div role="alert" className="flex flex-col items-center gap-3 rounded-[28px] border-2 border-line bg-surface px-5 py-8 text-center">
        <BubblesMascot size={72} mood="resting" animated={false} />
        <p className="m-0 font-display text-h3 text-default">Couldn&apos;t load your entries</p>
        <p className="m-0 max-w-md text-body text-muted">{error}</p>
        <button type="button" onClick={onRetry} className="bubbles-press min-h-[48px] rounded-full border-2 border-ink bg-surface px-6 text-body font-extrabold text-default">
          Try again
        </button>
      </div>
    );
  } else if (entries.length === 0) {
    body = empty;
  } else {
    body = groups.map((group) => (
      <div key={group.key} className="flex flex-col gap-2">
        <h3 className="m-0 text-body-sm font-extrabold text-muted">{group.label}</h3>
        <ul className="m-0 flex list-none flex-col gap-2.5 p-0">
          {group.items.map((entry) => (
            <li key={entry.id} className={`rounded-[24px] border-2 bg-surface p-4 ${s.border} ${entry.id === freshId ? "bubbles-rise" : ""}`}>
              {renderEntry(entry)}
            </li>
          ))}
        </ul>
      </div>
    ));
  }

  return (
    <section aria-labelledby={headingId} className="flex flex-col gap-3">
      <h2 id={headingId} className="m-0 font-display text-h2 text-default">
        {title}
      </h2>
      {body}
    </section>
  );
}

/** Entry row: tinted icon, title, time, then whatever details the page adds. */
export function EntryRow({ signal, icon, title, time, children }: { signal: Signal; icon: IconName; title: ReactNode; time?: string; children?: ReactNode }) {
  const s = SIGNALS[signal];
  return (
    <div className="flex items-start gap-3">
      <span className={`mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl ${s.tint} ${s.ink}`}>
        <Icon name={icon} size={20} />
      </span>
      <div data-private className="min-w-0 flex-1">
        <div className="flex items-baseline justify-between gap-3">
          <p className="m-0 min-w-0 break-words font-display text-h4 text-default">{title}</p>
          {time && <span className="shrink-0 text-body-sm font-bold text-muted">{time}</span>}
        </div>
        {children}
      </div>
    </div>
  );
}

export function EntryNote({ label, text }: { label?: string; text: EntryValue }) {
  if (!present(text)) return null;
  return (
    <p className="m-0 mt-2 whitespace-pre-line break-words text-body-sm text-muted">
      {label && <span className="font-extrabold text-default">{label}: </span>}
      {String(text)}
    </p>
  );
}

export function DetailChips({ items }: { items: { label: string; value: string }[] }) {
  if (items.length === 0) return null;
  return (
    <ul className="m-0 mt-2 flex list-none flex-wrap gap-1.5 p-0">
      {items.map((item) => (
        <li key={item.label} className="max-w-full break-words rounded-full bg-blush px-3 py-1 text-body-sm font-bold text-muted">
          <span className="text-default">{item.label}</span> {item.value}
        </li>
      ))}
    </ul>
  );
}

export function SavedToast({ trigger, message }: { trigger: string | null; message: string }) {
  const [shown, setShown] = useState<string | null>(null);
  useEffect(() => {
    if (!trigger) return;
    setShown(trigger);
    const timer = window.setTimeout(() => setShown(null), 3200);
    return () => window.clearTimeout(timer);
  }, [trigger]);
  return (
    <div role="status" aria-live="polite" className="pointer-events-none fixed inset-x-0 bottom-28 z-[70] flex justify-center px-4 lg:bottom-8">
      {shown && (
        <div key={shown} className="bubbles-pop-in flex max-w-full items-center gap-3 rounded-full border-2 border-line bg-surface py-2 pl-2 pr-5 shadow-lg">
          <span className="relative flex shrink-0">
            <SoapPop />
            <BubblesMascot size={40} mood="happy" />
          </span>
          <span className="text-body-sm font-extrabold text-default">{message}</span>
        </div>
      )}
    </div>
  );
}

/** Last-7-days bars (today on the right). Days without a log show as a dashed gap, not as zero. */
export function WeekBars({ title, entries, field, unit, signal, minScale, decimals = 1 }: {
  title: string; entries: Entry[]; field: string; unit: string; signal: Signal; minScale: number; decimals?: number;
}) {
  const s = SIGNALS[signal];
  const headingId = useId();
  const now = new Date();
  const totals = Array<number>(7).fill(0);
  const logged = Array<boolean>(7).fill(false);
  for (const e of entries) {
    const ago = daysAgo(e.date, now);
    const n = toNumber(e[field]);
    if (ago < 0 || ago > 6 || n === null) continue;
    totals[6 - ago] += n;
    logged[6 - ago] = true;
  }
  const max = Math.max(minScale, ...totals);
  return (
    <section aria-labelledby={headingId} className={`rounded-[28px] border-2 bg-surface p-5 ${s.border}`}>
      <h2 id={headingId} className="m-0 font-display text-h3 text-default">
        {title}
      </h2>
      <ul data-private className="m-0 mt-4 grid list-none grid-cols-7 gap-1.5 p-0 sm:gap-3">
        {totals.map((total, i) => {
          const day = new Date(now.getFullYear(), now.getMonth(), now.getDate() - (6 - i));
          const name = i === 6 ? "Today" : day.toLocaleDateString(undefined, { weekday: "short" });
          return (
            <li key={i} className="flex min-w-0 flex-col items-center gap-1.5">
              <span aria-hidden="true" className="text-[0.75rem] font-extrabold text-default">{logged[i] ? formatNumber(total, "", decimals) : ""}</span>
              <div className="flex h-24 w-full items-end justify-center">
                {logged[i] ? (
                  <span className={`bubbles-bar block w-full max-w-[36px] rounded-[10px] ${i === 6 ? s.bar : s.barSoft}`} style={{ height: `${Math.max(6, (total / max) * 100)}%`, animationDelay: `${i * 50}ms` }} />
                ) : (
                  <span className="block h-2 w-full max-w-[36px] rounded-full border-2 border-dashed border-line-strong" />
                )}
              </div>
              <span className={`text-[0.75rem] font-bold ${i === 6 ? "text-default" : "text-muted"}`}>{name}</span>
              <span className="sr-only">{logged[i] ? formatNumber(total, unit, decimals) : "not logged"}</span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
