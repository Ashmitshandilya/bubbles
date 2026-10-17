"use client";

// Bubbles admin console (/admin). Visual direction: docs/admin/DESIGN.md (Lixie). The lock is on the API: this page only asks
// GET /admin/me and shows the ordinary "page not found" view for anything but a 200, including later 404s mid-session.

import { useCallback, useEffect, useRef, useState, type KeyboardEvent } from "react";
import Link from "next/link";
import NotFound from "../not-found";
import { useApi, useAuth } from "../../components/Providers";
import { ApiAlert } from "../../components/Navigation";
import { BubblesMascot } from "../../components/BubblesMascot";
import { OVERALL_RANGES, RANGES, TABS, parseView, rangeFor, viewSearch, type TabId, type ViewRange } from "./format";
import { AdminContext, Pill, type AdminCtx, type Me, type Persistence } from "./kit";
import { RequestDialog } from "./panels";
import { PANELS } from "./registry";

function MemoryBanner({ persistence }: { persistence: Persistence }) {
  if (persistence.mode === "stored") return null;
  const failing = persistence.mode === "write_failing";
  return (
    <div role="note" className="mb-5 rounded-2xl bg-tint-sky px-5 py-4 text-bubbles-sky-deep">
      <p className="m-0 font-extrabold">{failing ? "Saving logs is failing" : "History is kept in memory only"}</p>
      <p className="m-0 mt-1 text-body-sm">
        {failing
          ? "The server could not write its technical logs to the database just now. Recent events still show here; older ones may be missing."
          : "The ops table isn't set up yet, so logs are lost when the server restarts. Apply 20261013_bubbles_ops.sql in Supabase to keep them."}
      </p>
    </div>
  );
}

function Tabs({ tab, onTab }: { tab: TabId; onTab: (t: TabId, push?: boolean) => void }) {
  const refs = useRef<Record<string, HTMLButtonElement | null>>({});
  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    const i = TABS.findIndex((t) => t.id === tab);
    const next = e.key === "ArrowRight" ? (i + 1) % TABS.length : e.key === "ArrowLeft" ? (i - 1 + TABS.length) % TABS.length
      : e.key === "Home" ? 0 : e.key === "End" ? TABS.length - 1 : -1;
    if (next < 0) return;
    e.preventDefault();
    onTab(TABS[next].id, false);
    refs.current[TABS[next].id]?.focus();
  };
  return (
    <div role="tablist" aria-label="Admin sections" onKeyDown={onKey}
      className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-2 pt-1 sm:mx-0 sm:px-0 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
      {TABS.map((t) => {
        const active = t.id === tab;
        return (
          <button key={t.id} ref={(el) => { refs.current[t.id] = el; }} type="button" role="tab" id={`tab-${t.id}`} aria-selected={active}
            aria-controls="admin-panel" tabIndex={active ? 0 : -1} onClick={() => onTab(t.id)}
            className={`bubbles-press inline-flex min-h-[44px] shrink-0 items-center rounded-full border px-4 text-body-sm font-extrabold transition-colors ${
              active ? "border-bubbles-pink-ink bg-bubbles-pink-ink text-white" : "border-line bg-surface text-ink-soft hover:border-line-strong hover:text-ink"}`}>
            {t.label}
          </button>
        );
      })}
    </div>
  );
}

function RangePicker({ range, ranges, onRange }: { range: ViewRange; ranges: readonly { id: ViewRange; label: string }[]; onRange: (r: ViewRange) => void }) {
  return (
    <div role="group" aria-label="Time range"
      className="-mx-4 flex gap-1.5 overflow-x-auto px-4 pb-1 sm:mx-0 sm:flex-wrap sm:px-0 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
      {ranges.map((r) => (
        <button key={r.id} type="button" aria-pressed={r.id === range} onClick={() => onRange(r.id)}
          className={`min-h-[44px] shrink-0 rounded-full border px-3 text-body-sm font-extrabold ${
            r.id === range ? "border-bubbles-grape bg-tint-grape text-bubbles-grape-deep" : "border-line bg-surface text-ink-soft hover:border-line-strong"}`}>
          {r.label}
        </button>
      ))}
    </div>
  );
}

function Opening() {
  return (
    <main className="flex min-h-dvh items-center justify-center bg-blush">
      <div role="status" className="text-center">
        <BubblesMascot size={88} mood="thinking" className="mx-auto" />
        <p className="mt-4 text-body font-bold text-muted">Opening Bubbles…</p>
      </div>
    </main>
  );
}

/* ── The console ─────────────────────────────────────────── */

export function AdminClient() {
  const { loading, session } = useAuth();
  const { fetchBubbles, checkApiHealth } = useApi();
  const [me, setMe] = useState<Me | null | "denied">(null);
  const [view, setView] = useState<ReturnType<typeof parseView>>({ tab: "overview", range: "1h", request: null });

  useEffect(() => {
    setView(parseView(window.location.search));
    const onPop = () => setView(parseView(window.location.search));
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  const viewRef = useRef(view);
  useEffect(() => {
    viewRef.current = view;
  }, [view]);
  // The address is updated outside any state updater: Next.js listens to history changes and updates its own router state,
  // which must not happen while React is rendering this component.
  const go = useCallback((next: Partial<ReturnType<typeof parseView>>, push = true) => {
    const base = { ...viewRef.current, ...next };
    const merged = { ...base, range: rangeFor(base.tab, base.range) };
    const url = `${window.location.pathname}${viewSearch(merged)}`;
    if (push) window.history.pushState(null, "", url);
    else window.history.replaceState(null, "", url);
    viewRef.current = merged;
    setView(merged);
  }, []);

  const adminFetch = useCallback(async (path: string, init?: RequestInit) => {
    const res = await fetchBubbles(path, init, { timeoutMs: 20000, retries: 0 });
    if (res.status === 404) setMe("denied");   // the API closed the door (signed out, removed from the list): look like any missing page
    return res;
  }, [fetchBubbles]);

  useEffect(() => {
    if (loading) return;
    if (!session) {
      setMe("denied");
      return;
    }
    let live = true;
    (async () => {
      try {
        const res = await fetchBubbles("/admin/me", {}, { timeoutMs: 65000, retries: 0 });
        if (!live) return;
        setMe(res.ok ? ((await res.json()) as Me) : "denied");
      } catch {
        if (live) setMe("denied");
      }
    })();
    return () => {
      live = false;
    };
  }, [loading, session, fetchBubbles]);

  if (me === "denied") return <NotFound />;
  if (loading || me === null) return <Opening />;

  const spec = PANELS[view.tab];
  const ctx: AdminCtx = { me, adminFetch, openRequest: (id) => go({ request: id }) };
  return (
    <AdminContext.Provider value={ctx}>
      <div className="min-h-dvh bg-blush text-ink">
        <header className="sticky top-0 z-20 border-b border-soft bg-blush/90 backdrop-blur">
          <div className="mx-auto flex max-w-content items-center gap-3 px-4 py-3 sm:px-8">
            <BubblesMascot size={36} mood="calm" animated={false} />
            <p className="m-0 whitespace-nowrap font-display text-h4 sm:text-h3">Bubbles admin</p>
            <span className="hidden sm:inline-flex"><Pill tone="plain">{me.environment === "production" ? "Live site" : "Local"}</Pill></span>
            <Link href="/dashboard" className="ml-auto inline-flex min-h-[44px] items-center whitespace-nowrap text-body-sm font-extrabold text-bubbles-pink-ink">
              <span className="hidden sm:inline">Back to </span>Today
            </Link>
          </div>
        </header>
        <ApiAlert onRetry={checkApiHealth} />
        <main id="main" className="mx-auto w-full max-w-content px-4 pb-16 pt-5 sm:px-8">
          <MemoryBanner persistence={me.persistence} />
          <div className="mb-5 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <Tabs tab={view.tab} onTab={(tab, push = true) => go({ tab }, push)} />
            {spec.ranges !== "none" && (
              <RangePicker range={view.range} ranges={spec.ranges === "overall" ? OVERALL_RANGES : RANGES} onRange={(range) => go({ range }, false)} />
            )}
          </div>
          <div id="admin-panel" role="tabpanel" aria-labelledby={`tab-${view.tab}`} className="space-y-5">
            {spec.render(view.range)}
          </div>
        </main>
        {view.request && <RequestDialog id={view.request} onClose={() => go({ request: null })} />}
      </div>
    </AdminContext.Provider>
  );
}
