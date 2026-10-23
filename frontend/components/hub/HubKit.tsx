"use client";

// Shared pieces for the hub pages (/health, /insights, /care, /profile, /settings):
// auth-gated page shell, one data-loading hook, tones, icons and small formatters.
// Shared by the hub routes only; tracker pages use components/tracking/kit.tsx.

import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { Header, Sidebar, MobileNav, ApiAlert, SectionTabs } from "../Navigation";
import { useAuth, useApi } from "../Providers";
import { classifyFailure, failureFromError } from "../../app/lib/connection";
import { responseFailure } from "../../lib/api";

/* ── Page shell ─────────────────────────────────────────── */

export function HubPage({ title, children }: { title: string; children: ReactNode }) {
  const router = useRouter();
  const { loading, session } = useAuth();
  const { apiStatus, connectionError, checkApiHealth } = useApi();

  useEffect(() => {
    if (!loading && !session) router.replace("/login");
  }, [loading, session, router]);

  if (loading || !session) {
    return (
      <main className="flex min-h-dvh items-center justify-center bg-blush">
        <LoadingBubbles label={loading ? "Opening Bubbles…" : "Taking you to sign in…"} />
      </main>
    );
  }

  return (
    <div className="flex min-h-dvh bg-blush text-ink">
      <Sidebar apiStatus={apiStatus} />
      <div className="flex min-w-0 flex-1 flex-col">
        <Header apiStatus={apiStatus} currentPage={title} />
        <ApiAlert connectionError={connectionError} onRetry={checkApiHealth} />
        <main id="main" className="mx-auto w-full max-w-content flex-1 px-4 pb-12 pt-6 sm:px-8 sm:pt-7">
          <SectionTabs />
          {children}
        </main>
        <MobileNav />
      </div>
    </div>
  );
}

/* ── Data ───────────────────────────────────────────────── */

export type Query<T> =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; data: T };

/**
 * GET `path`, or POST it with `body`. Keeps showing old data while refreshing. A failed query says why (server
 * stopped, slow, database needs its permission update, signed out) and reloads by itself once Bubbles reconnects.
 */
export function useBubblesQuery<T>(path: string, body?: object): [Query<T>, () => void] {
  const { fetchBubbles, reconnects, dataVersion } = useApi();
  const [state, setState] = useState<Query<T>>({ status: "loading" });
  const payload = body ? JSON.stringify(body) : undefined;
  const latest = useRef(0);
  const current = useRef(state);

  const load = useCallback(async () => {
    const id = ++latest.current; // only the newest request may write state
    setState((s) => (s.status === "ready" ? s : { status: "loading" }));
    try {
      const response = await fetchBubbles(path, payload ? { method: "POST", body: payload } : {});
      if (id !== latest.current) return;
      if (!response.ok) {
        const failure = await responseFailure(response);
        if (id === latest.current) setState({ status: "error", message: failure.message });
        return;
      }
      const data = (await response.json()) as T;
      if (id === latest.current) setState({ status: "ready", data });
    } catch (error) {
      if (id === latest.current) setState({ status: "error", message: classifyFailure(failureFromError(error)).message });
    }
  }, [fetchBubbles, path, payload]);

  useEffect(() => {
    void load();
  }, [load, dataVersion]);

  useEffect(() => {
    current.current = state;
  }, [state]);

  const seenReconnects = useRef(reconnects);
  useEffect(() => {
    if (seenReconnects.current === reconnects) return;
    seenReconnects.current = reconnects;
    if (current.current.status === "error") void load();
  }, [reconnects, load]);

  return [state, load];
}

/* ── Tones (signal colours from the brief) ──────────────── */

export type Tone = "pink" | "grape" | "sun" | "mint" | "sky" | "peach" | "plain";

export const TONE: Record<Tone, { chip: string; bubble: string; dot: string; ink: string }> = {
  pink: { chip: "bg-tint-pink text-bubbles-pink-deep", bubble: "bg-tint-pink text-bubbles-pink-deep", dot: "bg-bubbles-pink", ink: "text-bubbles-pink-deep" },
  grape: { chip: "bg-tint-grape text-bubbles-grape-deep", bubble: "bg-tint-grape text-bubbles-grape", dot: "bg-bubbles-grape", ink: "text-bubbles-grape-deep" },
  sun: { chip: "bg-tint-sun text-bubbles-sun-deep", bubble: "bg-tint-sun text-bubbles-sun-deep", dot: "bg-bubbles-sun", ink: "text-bubbles-sun-deep" },
  mint: { chip: "bg-tint-mint text-bubbles-mint-deep", bubble: "bg-tint-mint text-bubbles-mint-deep", dot: "bg-bubbles-mint", ink: "text-bubbles-mint-deep" },
  sky: { chip: "bg-tint-sky text-bubbles-sky-deep", bubble: "bg-tint-sky text-bubbles-sky-deep", dot: "bg-bubbles-sky", ink: "text-bubbles-sky-deep" },
  peach: { chip: "bg-tint-peach text-bubbles-peach-deep", bubble: "bg-tint-peach text-bubbles-peach-deep", dot: "bg-bubbles-peach", ink: "text-bubbles-peach-deep" },
  plain: { chip: "bg-blush text-ink-soft border border-line", bubble: "bg-blush text-ink-soft", dot: "bg-line-strong", ink: "text-ink-soft" },
};

const TONE_WORDS: Array<[Tone, string[]]> = [
  ["pink", ["cycle", "period", "menstrua", "symptom", "pain", "headache", "cramp"]],
  ["grape", ["sleep", "rest", "vital"]],
  ["sun", ["mood", "stress", "anx", "wellness", "wellbeing"]],
  ["sky", ["water", "hydrat", "medic", "lab", "report", "visit", "doctor", "condition", "allerg"]],
  ["peach", ["activity", "exercise", "workout", "walk", "steps", "weight"]],
  ["mint", ["food", "nutrition", "meal", "diet", "supplement"]],
];

/** Signal colour for an event type / domain / subject. */
export function toneFor(signal: string): Tone {
  const s = signal.toLowerCase();
  return TONE_WORDS.find(([, words]) => words.some((w) => s.includes(w)))?.[0] ?? "plain";
}

/* ── Small UI ───────────────────────────────────────────── */

// Pearl surface: hairline edge on raised paper, no shadow. A box is for something truly separate; new screens use components/pearl instead.
export const CARD = "rounded-[20px] border border-[color:var(--hairline)] bg-[color:var(--paper-raised)]";
// An unboxed group: a hairline above and room around it. Use for sections of a page; keep CARD for forms and truly separate things.
export const SECTION = "border-t border-[color:var(--hairline)] py-6";
export const BTN_PRIMARY =
  "bubbles-press inline-flex min-h-[44px] items-center justify-center gap-2 rounded-full bg-bubbles-pink-ink px-6 text-[0.9375rem] font-semibold text-white bubbles-glow disabled:opacity-40";
export const BTN_SECONDARY =
  "bubbles-press inline-flex min-h-[44px] items-center justify-center gap-2 rounded-full border border-line-strong bg-surface px-6 text-[0.9375rem] font-semibold text-ink hover:border-bubbles-grape disabled:opacity-40";
export const PILL = "inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-[0.8125rem] font-extrabold";

export function SignOutButton() {
  const { signOut } = useAuth();
  const [busy, setBusy] = useState(false);
  return (
    <button
      type="button"
      disabled={busy}
      onClick={async () => {
        setBusy(true);
        try {
          await signOut();
        } catch {
          setBusy(false);
        }
      }}
      className="bubbles-press inline-flex min-h-[44px] items-center rounded-full px-5 text-body-sm font-extrabold text-bubbles-pink-ink hover:bg-tint-pink hover:text-bubbles-pink-deep disabled:opacity-60"
    >
      {busy ? "Signing out…" : "Sign out"}
    </button>
  );
}

/** Page-level loading: three soft dots and one plain line. Loading never shows the mascot (DESIGN.md: empty and onboarding only). */
export function LoadingBubbles({ label }: { label: string }) {
  return (
    <div role="status" className="flex flex-col items-center gap-4 px-4 text-center">
      <span className="inline-flex gap-1.5" aria-hidden="true">
        <span className="bubbles-thinking-dot" />
        <span className="bubbles-thinking-dot" />
        <span className="bubbles-thinking-dot" />
      </span>
      <p className="m-0 text-body font-semibold text-muted">{label}</p>
    </div>
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`bubbles-skeleton ${className}`} aria-hidden="true" />;
}

/** `inset` = sitting inside another card: blush fill instead of a second border. */
export function ErrorCard({ title, message, onRetry, inset = false }: { title: string; message: string; onRetry: () => void; inset?: boolean }) {
  return (
    <div role="alert" className={`${inset ? "rounded-3xl bg-blush" : CARD} flex flex-wrap items-center gap-4 p-5`}>
      <div className="min-w-[10rem] flex-1">
        <p className="font-display text-h4 text-ink">{title}</p>
        <p className="text-body-sm text-muted">{message}</p>
      </div>
      <button type="button" onClick={onRetry} className={BTN_SECONDARY}>
        Try again
      </button>
    </div>
  );
}

/* ── Icons ──────────────────────────────────────────────── */

const ICONS: Record<string, ReactNode> = {
  cycle: (
    <>
      <path d="M21 12a9 9 0 1 1-3-6.7" />
      <polyline points="21 3 21 9 15 9" />
    </>
  ),
  sleep: <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />,
  symptoms: <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />,
  hydration: <path d="M12 2.7 6.7 9a7.5 7.5 0 1 0 10.6 0z" />,
  nutrition: (
    <>
      <path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.5 19 2c1 2 2 4.2 2 8a7 7 0 0 1-10 10z" />
      <path d="M2 21c0-3 1.9-5.6 4.5-7" />
    </>
  ),
  activity: <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />,
  mood: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M8.5 14.5a4.5 4.5 0 0 0 7 0M9 10h.01M15 10h.01" />
    </>
  ),
  weight: (
    <>
      <rect x="3" y="4" width="18" height="17" rx="4" />
      <path d="M8 10a4 4 0 0 1 8 0M12 10l2-2" />
    </>
  ),
  vitals: <path d="M20.8 5.6a5 5 0 0 0-7.1 0L12 7.3l-1.7-1.7a5 5 0 1 0-7.1 7.1l8.8 8.8 8.8-8.8a5 5 0 0 0 0-7.1z" />,
  medications: (
    <>
      <rect x="1.5" y="8" width="21" height="8" rx="4" />
      <path d="M12 8v8" />
    </>
  ),
  conditions: (
    <>
      <rect x="4" y="4" width="16" height="17" rx="2.5" />
      <path d="M9 4h6v3H9zM8.5 12h7M8.5 16h4.5" />
    </>
  ),
  allergies: (
    <>
      <path d="M10.3 3.9 1.9 18a2 2 0 0 0 1.7 3h16.8a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" />
      <path d="M12 9v4.5M12 17h.01" />
    </>
  ),
  labs: <path d="M9 3h6M10 3v6.5L4.8 18a2 2 0 0 0 1.7 3h11a2 2 0 0 0 1.7-3L14 9.5V3M7.5 15h9" />,
  reports: (
    <>
      <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
      <path d="M14 3v5h5M9 13h6M9 17h4" />
    </>
  ),
  visits: (
    <>
      <path d="M5 3v6a5 5 0 0 0 10 0V3M4 3h2M14 3h2M10 14v2a5 5 0 0 0 10 0v-2" />
      <circle cx="20" cy="12" r="1.6" />
    </>
  ),
  shield: <path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6zM9 12l2 2 4-4" />,
  sparkle: <path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z" />,
  arrow: <path d="M5 12h14M13 6l6 6-6 6" />,
};

export function Icon({ id, size = 22 }: { id: string; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {ICONS[id]}
    </svg>
  );
}

/* ── Formatters ─────────────────────────────────────────── */

/** "menstrual_symptom" → "Menstrual symptom" */
export function humanize(value: string): string {
  const s = value.replaceAll("_", " ").trim();
  return s ? s[0].toUpperCase() + s.slice(1) : s;
}
