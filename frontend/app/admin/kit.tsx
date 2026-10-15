"use client";

// Shared pieces of the admin console: the admin context, the data hook and the small building blocks.

import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { CARD, ErrorCard, Skeleton } from "../../components/hub/HubKit";
import { responseFailure } from "../../lib/api";
import { DOT_TONE, PILL_TONE, type PillTone } from "./format";

export type ChainStep = { provider: string; position: number; paused: boolean; key_configured: boolean };
export type Persistence = { mode: string; written: number; dropped: number; write_errors: number; last_write_at: string | null; retention_days: number };
export type Me = {
  you: string; environment: string; commit: string | null; started_at: string; persistence: Persistence; chain: ChainStep[];
  live_refresh_seconds: number;
};

export type AdminCtx = {
  me: Me;
  adminFetch: (path: string, init?: RequestInit) => Promise<Response>;
  openRequest: (id: string) => void;
};
export const AdminContext = createContext<AdminCtx | null>(null);
export function useAdmin(): AdminCtx {
  const ctx = useContext(AdminContext);
  if (!ctx) throw new Error("useAdmin outside the admin console");
  return ctx;
}

export type Loaded<T> = { status: "loading" } | { status: "error"; message: string } | { status: "ready"; data: T; refreshing: boolean };

/** GET an admin path. Keeps the last data while refreshing; `every` (seconds) re-asks while the tab is visible. */
export function useAdminQuery<T>(path: string | null, every?: number): [Loaded<T>, () => void] {
  const { adminFetch } = useAdmin();
  const [state, setState] = useState<Loaded<T>>({ status: "loading" });
  const latest = useRef(0);
  const load = useCallback(async () => {
    if (!path) return;
    const id = ++latest.current;
    setState((s) => (s.status === "ready" ? { ...s, refreshing: true } : { status: "loading" }));
    try {
      const res = await adminFetch(path);
      if (id !== latest.current) return;
      if (!res.ok) {
        const failure = await responseFailure(res);
        setState({ status: "error", message: failure.message });
        return;
      }
      const data = (await res.json()) as T;
      if (id === latest.current) setState({ status: "ready", data, refreshing: false });
    } catch (error) {
      if (id === latest.current) setState({ status: "error", message: error instanceof Error ? error.message : "Bubbles did not answer." });
    }
  }, [adminFetch, path]);
  useEffect(() => {
    void load();
  }, [load]);
  useEffect(() => {
    if (!every) return;
    const timer = window.setInterval(() => {
      if (!document.hidden) void load();
    }, every * 1000);
    return () => window.clearInterval(timer);
  }, [every, load]);
  return [state, load];
}

/* ── Shared pieces ───────────────────────────────────────── */

export function Pill({ tone, children }: { tone: PillTone; children: ReactNode }) {
  return (
    <span className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-3 py-1 text-chip font-extrabold ${PILL_TONE[tone]}`}>
      <span aria-hidden className={`h-2 w-2 rounded-full ${DOT_TONE[tone]}`} />
      {children}
    </span>
  );
}

export function Panel({ title, action, children, id }: { title: string; action?: ReactNode; children: ReactNode; id?: string }) {
  return (
    <section aria-labelledby={id} className={`${CARD} min-w-0 p-5 sm:p-6`}>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h2 id={id} className="m-0 font-display text-h3">{title}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="m-0 rounded-2xl bg-blush px-4 py-5 text-body-sm text-muted">{children}</p>;
}

export function LoadState<T>({ state, title, retry, children, rows = 3 }: {
  state: Loaded<T>; title: string; retry: () => void; children: (data: T) => ReactNode; rows?: number;
}) {
  if (state.status === "loading") {
    return (
      <div className="space-y-3" role="status" aria-label="Loading">
        {Array.from({ length: rows }, (_, i) => <Skeleton key={i} className="h-12 rounded-2xl" />)}
      </div>
    );
  }
  if (state.status === "error") return <ErrorCard inset title={title} message={state.message} onRetry={retry} />;
  return <>{children(state.data)}</>;
}

export function Refreshing({ on }: { on: boolean }) {
  return <span aria-live="polite" className="text-body-sm text-muted">{on ? "Refreshing…" : ""}</span>;
}
