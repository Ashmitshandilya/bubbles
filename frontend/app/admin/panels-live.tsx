"use client";

// The Live page: one row per request, newest first, polled every few seconds with a cursor. The UID column is the one owner-approved
// exception to "observe the system, not the user": the API sends it only on this endpoint, from memory (docs/admin/README.md).

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { BTN_SECONDARY } from "../../components/hub/HubKit";
import { responseFailure } from "../../lib/api";
import { clock, humanize, ms, num, words, type OpsEvent, kindLabel, eventSentence, mergeLive } from "./format";
import { Empty, Panel, Pill, useAdmin } from "./kit";
import { NO_FILTERS, chainOffsets, filterChoices, filterRows, groupLive, isError, stageWords, type LiveFilters, type LiveRow } from "./live";

type LiveView = {
  events: OpsEvent[]; next_cursor: number; process_started_at: string; restarted: boolean; gap: boolean; refresh_seconds: number;
  health: { events_last_minute: number; persistence: string };
};

const KEEP_EVENTS = 600;
const TH = "whitespace-nowrap px-3 py-2 text-left text-label text-ink-soft";
const TD = "whitespace-nowrap border-t border-line px-3 py-3 align-top text-body-sm";

export function CopyUid({ uid }: { uid: string | null }) {
  const [done, setDone] = useState(false);
  if (!uid) return <span className="text-muted">No one</span>;
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(uid);
      setDone(true);
      window.setTimeout(() => setDone(false), 1500);
    } catch {
      setDone(false);
    }
  };
  return (
    <span className="inline-flex items-center gap-2">
      <code className="select-all font-mono text-chip">{uid}</code>
      <button type="button" onClick={copy} aria-label={`Copy user id ${uid}`}
        className="min-h-[44px] min-w-[44px] rounded-full border border-line px-3 text-chip font-extrabold text-ink-soft hover:border-line-strong">
        {done ? "Copied" : "Copy"}
      </button>
    </span>
  );
}

function statusTone(row: LiveRow) {
  if (row.error || (row.status ?? 0) >= 500) return "urgent" as const;
  if ((row.status ?? 0) >= 400) return "sun" as const;
  return "mint" as const;
}

function routeLabel(row: LiveRow) {
  return row.route ? `${row.method ?? ""} ${row.route}`.trim() : humanize(row.kind);
}

function Detail({ row, onClose }: { row: LiveRow; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  const { openRequest } = useAdmin();
  useEffect(() => {
    const d = ref.current;
    if (d && !d.open) d.showModal();
  }, []);
  return (
    <dialog ref={ref} aria-labelledby="live-detail-title" onClose={onClose} onClick={(e) => { if (e.target === e.currentTarget) ref.current?.close(); }}
      className="m-auto max-h-[90dvh] w-[min(44rem,calc(100vw-2rem))] overflow-y-auto rounded-[24px] bg-surface p-0 text-ink backdrop:bg-ink/55">
      <div className="p-6">
        <div className="mb-4 flex items-center justify-between gap-3">
          <h2 id="live-detail-title" className="m-0 font-display text-h3">{routeLabel(row)}</h2>
          <button type="button" className={BTN_SECONDARY} onClick={() => ref.current?.close()}>Close</button>
        </div>
        <dl className="m-0 mb-4 grid grid-cols-[7rem_1fr] gap-x-3 gap-y-2 text-body-sm">
          <dt className="text-muted">Time</dt><dd className="m-0">{clock(row.at)}</dd>
          <dt className="text-muted">User id</dt><dd className="m-0"><CopyUid uid={row.uid} /></dd>
          <dt className="text-muted">Request id</dt>
          <dd className="m-0">
            {row.requestId ? (
              <span className="inline-flex flex-wrap items-center gap-2">
                <code className="font-mono text-chip">{row.requestId}</code>
                <button type="button" className="min-h-[44px] text-chip font-extrabold text-bubbles-pink-ink" onClick={() => { ref.current?.close(); openRequest(row.requestId as string); }}>
                  Open the full request in Logs
                </button>
              </span>
            ) : "None"}
          </dd>
          <dt className="text-muted">Answered by</dt><dd className="m-0">{row.provider ? `${row.provider} ${row.model ?? ""}` : "No AI used"}</dd>
          <dt className="text-muted">Stages</dt><dd className="m-0">{stageWords(row.stages, ms) ?? "Not measured for this request"}</dd>
        </dl>
        <h3 className="m-0 mb-2 text-body font-extrabold">Steps in this request</h3>
        <ol className="m-0 list-none space-y-2 p-0">
          {chainOffsets(row).map(({ event, offsetMs }) => (
            <li key={`${event.seq}-${event.at}`} className="rounded-2xl bg-blush px-4 py-3 text-body-sm">
              <div className="flex flex-wrap items-center gap-2">
                <span className="tabular-nums text-muted">+{num(offsetMs)} ms</span>
                <Pill tone={kindLabel(event.kind).tone}>{kindLabel(event.kind).word}</Pill>
                <span>{eventSentence(event)}</span>
              </div>
              <details className="mt-2">
                <summary className="min-h-[44px] cursor-pointer py-2 text-chip font-extrabold text-ink-soft">All fields</summary>
                <dl className="m-0 grid grid-cols-[9rem_1fr] gap-x-3 gap-y-1 text-chip">
                  {Object.entries(event.data).map(([k, v]) => (
                    <div key={k} className="contents"><dt className="text-muted">{k}</dt><dd className="m-0 break-all">{String(v)}</dd></div>
                  ))}
                </dl>
              </details>
            </li>
          ))}
        </ol>
      </div>
    </dialog>
  );
}

function Select({ label, value, onChange, options }: { label: string; value: string; onChange: (v: string) => void; options: [string, string][] }) {
  return (
    <label className="flex flex-col gap-1 text-label text-ink-soft">
      {label}
      <select value={value} onChange={(e) => onChange(e.target.value)} className="min-h-[44px] rounded-xl border border-line bg-surface px-3 text-body-sm text-ink">
        {options.map(([v, t]) => <option key={v} value={v}>{t}</option>)}
      </select>
    </label>
  );
}

function Card({ row, onOpen }: { row: LiveRow; onOpen: () => void }) {
  return (
    <li className="rounded-2xl border border-line p-4 text-body-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="tabular-nums text-muted">{clock(row.at)}</span>
        <Pill tone={statusTone(row)}>{row.status ?? words(row.kind)}</Pill>
      </div>
      <p className="m-0 mt-1 break-all font-extrabold">{routeLabel(row)}</p>
      <p className="m-0 mt-1 text-muted">
        {[row.latencyMs !== null ? ms(row.latencyMs) : null, row.provider ? `${row.provider} ${row.model ?? ""}` : null, row.fallback ? `try ${row.tries}` : null,
          row.safety, row.error ? humanize(row.error) : null].filter(Boolean).join(", ")}
      </p>
      <div className="mt-2"><CopyUid uid={row.uid} /></div>
      <button type="button" onClick={onOpen} aria-label={`Details for ${routeLabel(row)} at ${clock(row.at)}`}
        className="mt-1 min-h-[44px] text-chip font-extrabold text-bubbles-pink-ink">Details</button>
    </li>
  );
}

export function LivePanel() {
  const { adminFetch, me } = useAdmin();
  const [events, setEvents] = useState<OpsEvent[]>([]);
  const [paused, setPaused] = useState(false);
  const [hidden, setHidden] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [updated, setUpdated] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [health, setHealth] = useState<LiveView["health"] | null>(null);
  const [filters, setFilters] = useState<LiveFilters>(NO_FILTERS);
  const [open, setOpen] = useState<string | null>(null);
  const cursor = useRef({ since: 0, started: null as string | null });
  const every = me.live_refresh_seconds;

  const poll = useCallback(async () => {
    const { since, started } = cursor.current;
    try {
      const res = await adminFetch(`/admin/live?since=${since}${started ? `&process_started_at=${encodeURIComponent(started)}` : ""}`);
      if (!res.ok) {
        setError((await responseFailure(res)).message);
        return;
      }
      const data = (await res.json()) as LiveView;
      if (data.restarted) setNote(`Server restarted at ${clock(data.process_started_at)}. Earlier events are in Logs.`);
      else if (data.gap) setNote("Some events went by faster than this page could show. All of them are in Logs.");
      cursor.current = { since: data.next_cursor, started: data.process_started_at };
      setEvents((current) => mergeLive(data.restarted ? [] : current, data.events, KEEP_EVENTS));
      setHealth(data.health);
      setUpdated(Date.now());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Bubbles did not answer.");
    }
  }, [adminFetch]);

  useEffect(() => {
    const onVis = () => setHidden(document.hidden);
    document.addEventListener("visibilitychange", onVis);
    return () => document.removeEventListener("visibilitychange", onVis);
  }, []);

  useEffect(() => {
    if (paused || hidden) return;
    void poll();
    const timer = window.setInterval(() => void poll(), every * 1000);
    return () => window.clearInterval(timer);
  }, [paused, hidden, poll, every]);

  const [, tick] = useState(0);
  useEffect(() => {
    const t = window.setInterval(() => tick((n) => n + 1), 1000);
    return () => window.clearInterval(t);
  }, []);

  const all = useMemo(() => groupLive(events), [events]);
  const choices = useMemo(() => filterChoices(all), [all]);
  const rows = useMemo(() => filterRows(all, filters), [all, filters]);
  const age = updated ? Math.round((Date.now() - updated) / 1000) : null;
  const live = !paused && !hidden && !error && age !== null && age <= every * 3;
  const opened = open ? all.find((r) => r.key === open) ?? null : null;
  const filtered = filters.feature || filters.provider || filters.status || filters.errorsOnly;

  return (
    <Panel
      title="Live"
      id="live-title"
      action={
        <div className="flex flex-wrap items-center gap-3">
          <Pill tone={error ? "urgent" : live ? "mint" : "plain"}>{error ? "Stalled" : paused ? "Paused" : hidden ? "Tab in background" : live ? "Live" : "Connecting"}</Pill>
          <span className="text-body-sm text-muted" aria-live="off">
            {age !== null ? `Updated ${age} s ago` : "Connecting…"}
            {health ? `, ${num(health.events_last_minute)} events in the last minute` : ""}
          </span>
          <button type="button" className={BTN_SECONDARY} onClick={() => setPaused((p) => !p)}>{paused ? "Resume" : "Pause"}</button>
        </div>
      }
    >
      {health && health.persistence !== "stored" && (
        <p role="note" className="mb-3 rounded-2xl bg-tint-sky px-4 py-3 text-body-sm text-bubbles-sky-deep">
          Memory only: these rows disappear when the server restarts. Apply 20261013_bubbles_ops.sql in Supabase to keep history. User ids are never saved.
        </p>
      )}
      {note && <p className="mb-3 rounded-2xl bg-tint-sky px-4 py-3 text-body-sm text-bubbles-sky-deep">{note}</p>}
      {error && <p role="alert" className="mb-3 rounded-2xl bg-tint-urgent px-4 py-3 text-body-sm text-bubbles-urgent">{error}</p>}

      <div role="group" aria-label="Filters" className="mb-4 grid grid-cols-2 items-end gap-3 sm:grid-cols-4 lg:grid-cols-[repeat(4,minmax(0,12rem))_auto]">
        <Select label="Feature or route" value={filters.feature} onChange={(feature) => setFilters({ ...filters, feature })}
          options={[["", "All"], ...choices.features.map((f): [string, string] => [f, f])]} />
        <Select label="Provider" value={filters.provider} onChange={(provider) => setFilters({ ...filters, provider })}
          options={[["", "All"], ...choices.providers.map((p): [string, string] => [p, p])]} />
        <Select label="Status" value={filters.status} onChange={(status) => setFilters({ ...filters, status: status as LiveFilters["status"] })}
          options={[["", "All"], ["2xx", "OK (2xx)"], ["4xx", "Refused (4xx)"], ["5xx", "Server error (5xx)"]]} />
        <label className="flex min-h-[44px] items-center gap-2 text-body-sm font-extrabold">
          <input type="checkbox" checked={filters.errorsOnly} onChange={(e) => setFilters({ ...filters, errorsOnly: e.target.checked })} className="h-5 w-5" />
          Errors only
        </label>
        {filtered ? <button type="button" className={BTN_SECONDARY} onClick={() => setFilters(NO_FILTERS)}>Clear filters</button> : null}
      </div>

      {rows.length === 0 ? (
        <Empty>{filtered && all.length ? "No rows match these filters." : `Waiting for the next request. New events appear within ${every} seconds.`}</Empty>
      ) : (
        <>
          <div className="relative hidden overflow-x-auto lg:block">
            <table className="w-full border-collapse">
              <caption className="sr-only">Newest requests first</caption>
              <thead>
                <tr>
                  {["Time", "User id", "Route", "Kind", "Provider", "Model", "Try", "Safety", "Status", "Latency", "Stages", "Error", ""].map((h) => (
                    <th key={h || "open"} scope="col" className={TH}>{h || <span className="sr-only">Details</span>}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.key} className={isError(r) ? "bg-tint-urgent/30" : undefined}>
                    <td className={`${TD} tabular-nums`}>{clock(r.at)}</td>
                    <td className={TD}><CopyUid uid={r.uid} /></td>
                    <td className={TD}>{routeLabel(r)}{r.feature ? <span className="ml-2 text-muted">{r.feature}</span> : null}</td>
                    <td className={TD}>{r.routeKind ? words(r.routeKind) : words(r.kind)}</td>
                    <td className={TD}>{r.provider ?? "None"}</td>
                    <td className={TD}>{r.model ?? "None"}</td>
                    <td className={TD}>{r.tries ? (r.fallback ? `${r.tries}, fallback` : r.tries) : "None"}</td>
                    <td className={TD}>{r.safety ?? "None"}</td>
                    <td className={TD}>{r.status !== null ? <Pill tone={statusTone(r)}>{r.status}</Pill> : "None"}</td>
                    <td className={`${TD} tabular-nums`}>{ms(r.latencyMs)}</td>
                    <td className={TD}>{stageWords(r.stages, ms) ?? "None"}</td>
                    <td className={TD}>{r.error ? humanize(r.error) : "None"}</td>
                    <td className={TD}>
                      <button type="button" onClick={() => setOpen(r.key)} aria-label={`Details for ${routeLabel(r)} at ${clock(r.at)}`}
                        className="min-h-[44px] min-w-[44px] text-chip font-extrabold text-bubbles-pink-ink">Details</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <ol className="m-0 list-none space-y-3 p-0 lg:hidden" aria-label="Newest requests first">
            {rows.map((r) => <Card key={r.key} row={r} onOpen={() => setOpen(r.key)} />)}
          </ol>
        </>
      )}
      {opened && <Detail row={opened} onClose={() => setOpen(null)} />}
    </Panel>
  );
}
