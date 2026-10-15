"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { BTN_PRIMARY, BTN_SECONDARY, CARD, ErrorCard } from "../../components/hub/HubKit";
import { responseFailure } from "../../lib/api";
import {
  DOT_TONE, NONE, ago, clock, duration, eventSentence, healthTone, healthWords, humanize, kindLabel, mergeLive, ms, num, pct, providerTone,
  sampleNote, shortId, type Health, type OpsEvent, type RangeId,
} from "./format";
import { Empty, LoadState, Panel, Pill, Refreshing, useAdmin, useAdminQuery, type ChainStep, type Persistence } from "./kit";

/* ── Response shapes (backend/admin_api.py) ──────────────── */

type Lat = { avg: number | null; p50: number | null; p95: number | null; p99: number | null };
type AiSummary = {
  chat_turns: number; ai_called: number; answered_without_ai: number; safety_gated: number; replies: number; answered: number; degraded: number;
  fallback_used: number; attempts: number; failed_attempts: number; timeouts: number; success_rate: number | null; reply_ms: Lat;
};
type ApiSummary = { requests: number; per_minute: number; client_errors: number; server_errors: number; error_rate: number | null; latency_ms: Lat };
type Answering = { provider: string; model: string; share: number | null; n: number; last_reply_at: string } | null;
type CacheStat = { name: string; enabled: boolean; ttl_s: number; entries: number; hits: number; misses: number; shared: number; errors: number; hit_rate: number | null; avg_miss_ms: number };
type Meta = { generated_at: string; source: "stored" | "memory"; capped: boolean; cap: number };
type Overview = Meta & {
  headline: { status: Health; reasons: string[] };
  now: { ai: AiSummary; api: ApiSummary; answering: Answering };
  system: { components: { database: string; ai_keys: Record<string, boolean> }; version: string; environment: string; commit: string | null; started_at: string; uptime_s: number; persistence: Persistence };
  ai: AiSummary & { answering: Answering };
  api: ApiSummary;
  errors: Record<string, number>;
  cache: CacheStat[];
  chain: ChainStep[];
};
type ProviderRow = {
  provider: string; model: string; requests: number; successful: number; failed: number; success_rate: number | null; timeout_rate: number | null;
  first_choice_rate: number | null; avg_position: number; final_answers: number; final_share: number | null; latency_ms: Lat;
  error_categories: Record<string, number>; last_success_at: string | null; last_failure_at: string | null;
};
type Highlight = { provider: string; model: string; [k: string]: unknown } | null;
type Flow = { steps: { provider: string; reached: number; answered: number; moved_on: number }[]; transitions: { from: string; to: string; count: number }[]; ran_out: number; requests: number };
type AiView = Meta & {
  summary: AiSummary; providers: ProviderRow[]; chain: ChainStep[]; flow: Flow;
  highlights: { most_answers: Highlight; most_failing: Highlight; slowest: Highlight; most_reliable: Highlight; min_sample: number };
};
type RouteRow = {
  method: string; route: string; requests: number; success_rate: number | null; client_errors: number; server_errors: number; latency_ms: Lat;
  slowest_ms: number | null; last_server_error_at: string | null; trend: number[];
};
type ApiView = Meta & { summary: ApiSummary; routes: RouteRow[] };
type EventsView = Meta & { events: OpsEvent[]; next_before: string | null };
type LiveView = { events: OpsEvent[]; next_cursor: number; process_started_at: string; restarted: boolean; gap: boolean; refresh_seconds: number };
type Setting = { key: string; type: "bool" | "int"; label: string; min?: number; max?: number; default: boolean | number; value: boolean | number; updated_at: string | null; updated_by: string | null };
type SettingsView = { settings: Setting[]; persisted: boolean | null; chain: ChainStep[] };

const TH = "px-3 py-2 text-left text-label text-ink-soft";
const TD = "border-t border-line px-3 py-3 align-top";

function Sampled({ meta }: { meta: Meta }) {
  return meta.capped ? <Pill tone="sun">Sampled, first {num(meta.cap)} events</Pill> : null;
}

function Stat({ label, value, note }: { label: string; value: string; note?: string | null }) {
  return (
    <div className="px-5 py-4">
      <p className="m-0 text-label text-ink-soft">{label}</p>
      <p className="m-0 mt-1 font-display text-metric tabular-nums">{value}</p>
      {note && <p className="m-0 mt-1 text-body-sm text-muted">{note}</p>}
    </div>
  );
}

function Few({ n, min }: { n: number; min: number }) {
  return <span className="whitespace-nowrap text-muted">{num(n)} of {min} calls</span>;
}

function RequestLink({ id }: { id: string | null }) {
  const { openRequest } = useAdmin();
  if (!id) return <span className="text-muted">{NONE}</span>;
  return (
    <button type="button" onClick={() => openRequest(id)} className="inline-flex min-h-[44px] items-center font-mono text-body-sm font-bold text-bubbles-grape-deep underline underline-offset-2">
      {shortId(id)}
    </button>
  );
}

/* ── Fallback chain ──────────────────────────────────────── */

function ChainView({ chain, flow }: { chain: ChainStep[]; flow?: Flow }) {
  const step = (name: string) => flow?.steps.find((s) => s.provider === name);
  const passed = (from: string) => flow?.transitions.filter((t) => t.from === from).reduce((a, t) => a + t.count, 0) ?? 0;
  const allPaused = chain.length > 0 && chain.every((c) => c.paused);
  return (
    <div>
      {allPaused && (
        <p role="alert" className="mb-3 rounded-2xl bg-tint-urgent px-4 py-3 text-body-sm font-bold text-bubbles-urgent">
          Every provider is paused. Everyone gets the calm message.
        </p>
      )}
      <ol className="m-0 flex list-none flex-col gap-2 p-0 md:flex-row md:flex-wrap md:items-center" aria-label="Order Bubbles asks AI providers in">
        {chain.map((c, i) => {
          const s = step(c.provider);
          const moved = passed(c.provider);
          const next = chain[i + 1]?.provider ?? "the calm message";
          return (
            <li key={c.provider} className="flex flex-col items-start gap-2 md:flex-row md:items-center">
              <Pill tone={c.paused ? "plain" : !c.key_configured ? "sun" : "mint"}>
                {c.position} {c.provider}
                {c.paused ? " · Paused" : !c.key_configured ? " · No key" : s ? ` · answered ${num(s.answered)}` : ""}
              </Pill>
              <span className="sr-only">{`${c.provider} passed ${moved} on to ${next}.`}</span>
              <span aria-hidden className="flex items-center gap-2 text-body-sm text-muted md:flex-row">
                <span className="ml-4 h-6 w-0.5 bg-line-strong md:ml-0 md:h-0.5 md:w-6" />
                {flow ? `${num(moved)} passed on` : ""}
              </span>
            </li>
          );
        })}
        <li>
          <Pill tone={flow && flow.ran_out ? "urgent" : "plain"}>No AI answer, calm message sent{flow ? ` · ${num(flow.ran_out)}` : ""}</Pill>
        </li>
      </ol>
    </div>
  );
}

function Highlights({ h }: { h: AiView["highlights"] }) {
  const cell = (label: string, item: Highlight, detail: (x: NonNullable<Highlight>) => string) => (
    <div className="rounded-2xl bg-blush px-4 py-3">
      <p className="m-0 text-label text-ink-soft">{label}</p>
      {item ? (
        <>
          <p className="m-0 mt-1 font-extrabold">{item.provider}</p>
          <p className="m-0 text-body-sm text-muted">{item.model}, {detail(item)}</p>
        </>
      ) : (
        <p className="m-0 mt-1 text-body-sm text-muted">Not enough data yet (needs {h.min_sample} calls)</p>
      )}
    </div>
  );
  if (!h.most_answers && !h.most_reliable && !h.slowest && !h.most_failing) {
    return <Empty>Not enough data yet to compare providers (needs {h.min_sample} calls each).</Empty>;
  }
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      {cell("Gives most answers", h.most_answers, (x) => `${num(x.final_answers as number)} answers (${pct(x.final_share as number)})`)}
      {cell("Most reliable", h.most_reliable, (x) => `${pct(x.success_rate as number)} answered, typical ${ms(x.p50_ms as number)}`)}
      {cell("Slowest", h.slowest, (x) => `p95 ${ms(x.p95_ms as number)}`)}
      {cell("Fails most", h.most_failing, (x) => `${pct(x.failure_rate as number)} failed`)}
    </div>
  );
}

/* ── Overview ────────────────────────────────────────────── */

export function OverviewPanel({ range }: { range: RangeId }) {
  const [overview, reloadOverview] = useAdminQuery<Overview>(`/admin/overview?range=${range}`, 15);
  const [ai, reloadAi] = useAdminQuery<AiView>(`/admin/ai?range=${range}`, 30);
  return (
    <>
      <LoadState state={overview} title="Couldn't load the overview" retry={reloadOverview} rows={4}>
        {(o) => (
          <>
            <section aria-label="Status right now" className={`${CARD} p-5 sm:p-6`}>
              <div className="flex flex-wrap items-center gap-3">
                <Pill tone={healthTone(o.headline.status)}>{healthWords(o.headline.status)}</Pill>
                <Refreshing on={overview.status === "ready" && overview.refreshing} />
                <span className="ml-auto text-body-sm text-muted">Updated {clock(o.generated_at)}</span>
              </div>
              <p className="m-0 mt-3 font-display text-h3">
                {o.now.answering
                  ? `${o.now.answering.provider} answered ${pct(o.now.answering.share)} of AI replies in the last 5 min.`
                  : o.now.ai.replies > 0
                    ? `No provider answered in the last 5 min. ${num(o.now.ai.degraded)} of ${num(o.now.ai.replies)} replies got the calm message.`
                    : "No AI replies in the last 5 min."}
              </p>
              {o.headline.reasons.length > 0 && (
                <ul className="m-0 mt-2 list-disc pl-5 text-body-sm text-ink-soft">
                  {o.headline.reasons.map((r) => <li key={r}>{r}</li>)}
                </ul>
              )}
            </section>
            <section aria-label="Key numbers" className={CARD}>
              <div className="grid grid-cols-2 divide-line sm:grid-cols-3 lg:grid-cols-6">
                <Stat label="Requests a minute" value={o.api.per_minute.toLocaleString("en-IN", { maximumFractionDigits: 1 })} note={`${num(o.api.requests)} in range`} />
                <Stat label="Server errors" value={pct(o.api.error_rate)} note={`${num(o.api.server_errors)} of ${num(o.api.requests)}`} />
                <Stat label="AI replies" value={num(o.ai.replies)} note={`${num(o.ai.degraded)} got the calm message`} />
                <Stat label="Fell back" value={num(o.ai.fallback_used)} note="answered by a later provider" />
                <Stat label="Reply time p95" value={o.ai.replies >= 20 ? ms(o.ai.reply_ms.p95) : o.ai.replies ? "Too few calls" : NONE} note={sampleNote(o.ai.replies, 20) ?? `typical ${ms(o.ai.reply_ms.p50)}`} />
                <Stat label="Up for" value={duration(o.system.uptime_s)} note={`since ${clock(o.system.started_at)}`} />
              </div>
            </section>
          </>
        )}
      </LoadState>
      <Panel title="Who answers, in order" id="chain-title" action={ai.status === "ready" ? <Sampled meta={ai.data} /> : null}>
        <LoadState state={ai} title="Couldn't load the AI chain" retry={reloadAi}>
          {(a) => (
            <div className="space-y-4">
              <ChainView chain={a.chain} flow={a.flow} />
              <p className="m-0 text-body-sm text-muted">
                {num(a.summary.chat_turns)} chat messages: {num(a.summary.ai_called)} went to AI, {num(a.summary.answered_without_ai)} answered by Bubbles itself
                {a.summary.safety_gated ? `, ${num(a.summary.safety_gated)} handled by safety rules, no AI used` : ""}.
              </p>
              <Highlights h={a.highlights} />
            </div>
          )}
        </LoadState>
      </Panel>
      <LoadState state={overview} title="Couldn't load system facts" retry={reloadOverview} rows={1}>
        {(o) => (
          <div className="grid gap-5 lg:grid-cols-2 [&>*]:min-w-0">
            <Panel title="System" id="system-title">
              <dl className="m-0 grid grid-cols-[auto_1fr] gap-x-6 gap-y-2 text-body-sm">
                <dt className="text-ink-soft">Database</dt><dd className="m-0 font-bold">{humanize(o.system.components.database)}</dd>
                <dt className="text-ink-soft">AI keys set</dt>
                <dd className="m-0">{Object.entries(o.system.components.ai_keys).map(([p, ok]) => `${p} ${ok ? "yes" : "no"}`).join(", ")}</dd>
                <dt className="text-ink-soft">Version</dt><dd className="m-0">{o.system.version}{o.system.commit ? <span className="ml-2 font-mono">{o.system.commit}</span> : null}</dd>
                <dt className="text-ink-soft">Where</dt><dd className="m-0">{o.system.environment === "production" ? "Live site" : "Local"}</dd>
                <dt className="text-ink-soft">Started</dt><dd className="m-0">{clock(o.system.started_at)} ({ago(o.system.started_at)})</dd>
                <dt className="text-ink-soft">Logs</dt>
                <dd className="m-0">
                  {o.system.persistence.mode === "stored" ? `Saved, kept ${o.system.persistence.retention_days} days` : humanize(o.system.persistence.mode)}
                  {o.system.persistence.dropped ? `, ${num(o.system.persistence.dropped)} dropped` : ""}
                </dd>
                <dt className="text-ink-soft">Read from</dt><dd className="m-0">{o.source === "stored" ? "Saved logs" : "Memory since the last restart"}</dd>
              </dl>
            </Panel>
            <Panel title="Errors and caches" id="errors-title">
              {Object.keys(o.errors).length === 0 ? (
                <Empty>No errors in this range.</Empty>
              ) : (
                <ul className="m-0 flex list-none flex-wrap gap-2 p-0">
                  {Object.entries(o.errors).sort((a, b) => b[1] - a[1]).map(([cat, n]) => (
                    <li key={cat}><Pill tone="urgent">{humanize(cat)} · {num(n)}</Pill></li>
                  ))}
                </ul>
              )}
              <div className="mt-4 overflow-x-auto">
                <table className="w-full min-w-[26rem] border-collapse text-body-sm">
                  <caption className="sr-only">Server caches since the last restart</caption>
                  <thead><tr><th className={TH}>Cache</th><th className={TH}>Hit rate</th><th className={TH}>Kept</th><th className={TH}>Saved a lookup</th></tr></thead>
                  <tbody>
                    {o.cache.map((c) => (
                      <tr key={c.name}>
                        <td className={TD}>{humanize(c.name)}{c.enabled ? "" : " (off)"}</td>
                        <td className={TD}>{pct(c.hit_rate)}</td>
                        <td className={TD}>{num(c.entries)} for {duration(c.ttl_s)}</td>
                        <td className={TD}>{num(c.hits + c.shared)} times, a miss takes {ms(c.avg_miss_ms)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Panel>
          </div>
        )}
      </LoadState>
    </>
  );
}

/* ── AI providers ────────────────────────────────────────── */

export function AiPanel({ range }: { range: RangeId }) {
  const [ai, reload] = useAdminQuery<AiView>(`/admin/ai?range=${range}`, 30);
  return (
    <LoadState state={ai} title="Couldn't load providers" retry={reload} rows={5}>
      {(a) => (
        <>
          <Panel title="Providers and models" id="providers-title" action={<span className="flex items-center gap-2"><Sampled meta={a} /><Refreshing on={ai.status === "ready" && ai.refreshing} /></span>}>
            {a.providers.length === 0 ? (
              <Empty>No AI calls in this range.</Empty>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[44rem] border-collapse text-body-sm">
                  <caption className="sr-only">Each AI provider and model: how often it answered, how reliably and how fast</caption>
                  <thead>
                    <tr>
                      <th className={`${TH} sticky left-0 bg-surface`}>Provider</th><th className={TH}>Status</th><th className={TH}>Answered</th>
                      <th className={TH}>Success</th><th className={TH}>p95</th>
                      <th className={`${TH} hidden lg:table-cell`}>Usual try</th><th className={`${TH} hidden lg:table-cell`}>Ran out of time</th>
                      <th className={`${TH} hidden lg:table-cell`}>p50</th><th className={`${TH} hidden lg:table-cell`}>p99</th>
                      <th className={`${TH} hidden lg:table-cell`}>Top failure</th><th className={`${TH} hidden lg:table-cell`}>Last failure</th>
                    </tr>
                  </thead>
                  <tbody>
                    {a.providers.map((p) => {
                      const paused = a.chain.find((c) => c.provider === p.provider)?.paused ?? false;
                      const status = providerTone(p, paused);
                      const top = Object.entries(p.error_categories).sort((x, y) => y[1] - x[1])[0];
                      return (
                        <tr key={`${p.provider}-${p.model}`}>
                          <td className={`${TD} sticky left-0 bg-surface`}><span className="font-extrabold">{p.provider}</span><br /><span className="text-muted">{p.model === "unknown" ? "Model not set" : p.model}</span></td>
                          <td className={TD}><Pill tone={status.tone}>{status.word}</Pill></td>
                          <td className={TD}>
                            {p.final_answers ? <>{pct(p.final_share)} <span className="text-muted">({num(p.final_answers)})</span></> : "0"}
                            <span aria-hidden className="mt-1 block h-1.5 w-24 rounded-full bg-tint-pink"><span className="block h-1.5 rounded-full bg-bubbles-pink" style={{ width: `${Math.round((p.final_share ?? 0) * 100)}%` }} /></span>
                          </td>
                          <td className={TD}>{pct(p.success_rate)} <span className="text-muted">of {num(p.requests)}</span></td>
                          <td className={TD}>{p.requests >= 20 ? ms(p.latency_ms.p95) : <Few n={p.requests} min={20} />}</td>
                          <td className={`${TD} hidden lg:table-cell`}>{p.avg_position.toFixed(1)}</td>
                          <td className={`${TD} hidden lg:table-cell`}>{pct(p.timeout_rate)}</td>
                          <td className={`${TD} hidden lg:table-cell`}>{p.requests >= 5 ? ms(p.latency_ms.p50) : <Few n={p.requests} min={5} />}</td>
                          <td className={`${TD} hidden lg:table-cell`}>{p.requests >= 20 ? ms(p.latency_ms.p99) : <Few n={p.requests} min={20} />}</td>
                          <td className={`${TD} hidden lg:table-cell`}>{top ? `${humanize(top[0])} (${num(top[1])})` : NONE}</td>
                          <td className={`${TD} hidden lg:table-cell`}>{p.last_failure_at ? ago(p.last_failure_at) : NONE}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>
          <Panel title="Who answers, in order" id="ai-chain-title"><ChainView chain={a.chain} flow={a.flow} /></Panel>
          <Panel title="Comparisons" id="ai-highlights-title"><Highlights h={a.highlights} /></Panel>
        </>
      )}
    </LoadState>
  );
}

/* ── Live ────────────────────────────────────────────────── */

function EventRow({ e }: { e: OpsEvent }) {
  const k = kindLabel(e.kind);
  return (
    <li className="grid grid-cols-[4.5rem_1fr] items-start gap-x-3 gap-y-1 py-3 sm:grid-cols-[5rem_7rem_1fr_auto]">
      <span className="flex items-center gap-2 tabular-nums text-body-sm text-muted">
        <span aria-hidden className={`h-2 w-2 shrink-0 rounded-full sm:hidden ${DOT_TONE[k.tone]}`} />{clock(e.at)}
      </span>
      <span className="hidden sm:block"><Pill tone={k.tone}>{k.word}</Pill></span>
      <span className="text-body-sm">{eventSentence(e)}</span>
      <span className="col-start-2 sm:col-start-auto"><RequestLink id={e.request_id} /></span>
    </li>
  );
}

export function LivePanel() {
  const { adminFetch, me } = useAdmin();
  const [rows, setRows] = useState<OpsEvent[]>([]);
  const [paused, setPaused] = useState(false);
  const [hidden, setHidden] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [updated, setUpdated] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const cursor = useRef({ after: 0, started: null as string | null });
  const every = me.live_refresh_seconds;

  const poll = useCallback(async () => {
    const { after, started } = cursor.current;
    const q = `/admin/events/live?after=${after}${started ? `&process_started_at=${encodeURIComponent(started)}` : ""}`;
    try {
      const res = await adminFetch(q);
      if (!res.ok) {
        setError((await responseFailure(res)).message);
        return;
      }
      const data = (await res.json()) as LiveView;
      if (data.restarted) setNote(`Server restarted at ${clock(data.process_started_at)}. Earlier events are in Logs.`);
      else if (data.gap) setNote("Some events went by faster than this page could show. All of them are in Logs.");
      cursor.current = { after: data.next_cursor, started: data.process_started_at };
      setRows((current) => mergeLive(data.restarted ? [] : current, data.events));
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

  return (
    <Panel
      title="Live"
      id="live-title"
      action={
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-body-sm text-muted" aria-live="off">
            {hidden ? "Paused while this tab is in the background" : paused ? "Paused" :
              updated ? `Updated ${Math.round((Date.now() - updated) / 1000)} s ago, refreshing every ${every} s` : "Connecting…"}
          </span>
          <button type="button" className={BTN_SECONDARY} onClick={() => setPaused((p) => !p)}>{paused ? "Resume" : "Pause"}</button>
        </div>
      }
    >
      {note && <p className="mb-3 rounded-2xl bg-tint-sky px-4 py-3 text-body-sm text-bubbles-sky-deep">{note}</p>}
      {error && <p role="alert" className="mb-3 rounded-2xl bg-tint-urgent px-4 py-3 text-body-sm text-bubbles-urgent">{error}</p>}
      {rows.length === 0 ? (
        <Empty>Waiting for the next request. New events appear within {every} seconds.</Empty>
      ) : (
        <ol className="m-0 list-none divide-y-2 divide-line p-0" aria-label="Newest events first">
          {rows.map((e) => <EventRow key={`${e.seq ?? e.id}-${e.at}`} e={e} />)}
        </ol>
      )}
    </Panel>
  );
}

/* ── API routes ──────────────────────────────────────────── */

function Trend({ values }: { values: number[] }) {
  const max = Math.max(1, ...values);
  return (
    <span aria-hidden className="flex h-6 items-end gap-0.5">
      {values.map((v, i) => <span key={i} className="w-1.5 rounded-sm bg-bubbles-grape/60" style={{ height: `${Math.max(2, (v / max) * 24)}px` }} />)}
    </span>
  );
}

export function ApiPanel({ range }: { range: RangeId }) {
  const [api, reload] = useAdminQuery<ApiView>(`/admin/api?range=${range}`, 30);
  return (
    <LoadState state={api} title="Couldn't load API routes" retry={reload} rows={5}>
      {(a) => (
        <Panel title="API routes" id="api-title" action={<span className="flex items-center gap-2"><Sampled meta={a} /><Refreshing on={api.status === "ready" && api.refreshing} /></span>}>
          <p className="m-0 mb-4 text-body-sm text-muted">
            {num(a.summary.requests)} requests, {a.summary.per_minute.toLocaleString("en-IN")} a minute, {pct(a.summary.error_rate)} server errors, typical {ms(a.summary.latency_ms.p50)}. The portal&apos;s own requests are not counted.
          </p>
          {a.routes.length === 0 ? (
            <Empty>No requests in this range.</Empty>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[44rem] border-collapse text-body-sm">
                <caption className="sr-only">Each API route: traffic, errors and speed</caption>
                <thead>
                  <tr>
                    <th className={`${TH} sticky left-0 bg-surface`}>Route</th><th className={TH}>Requests</th><th className={TH}>OK</th>
                    <th className={TH}>4xx</th><th className={TH}>5xx</th><th className={TH}>p50</th><th className={TH}>p95</th>
                    <th className={`${TH} hidden lg:table-cell`}>Slowest</th><th className={`${TH} hidden lg:table-cell`}>Last 5xx</th><th className={TH}>Trend</th>
                  </tr>
                </thead>
                <tbody>
                  {a.routes.map((r) => (
                    <tr key={`${r.method}-${r.route}`}>
                      <td className={`${TD} sticky left-0 bg-surface font-mono`}>{r.method} {r.route}</td>
                      <td className={TD}>{num(r.requests)}</td>
                      <td className={TD}>{pct(r.success_rate)}</td>
                      <td className={TD}>{num(r.client_errors)}</td>
                      <td className={TD}>{r.server_errors ? <Pill tone="urgent">{num(r.server_errors)}</Pill> : "0"}</td>
                      <td className={TD}>{r.requests >= 5 ? ms(r.latency_ms.p50) : <Few n={r.requests} min={5} />}</td>
                      <td className={TD}>{r.requests >= 20 ? ms(r.latency_ms.p95) : <Few n={r.requests} min={20} />}</td>
                      <td className={`${TD} hidden lg:table-cell`}>{ms(r.slowest_ms)}</td>
                      <td className={`${TD} hidden lg:table-cell`}>{r.last_server_error_at ? ago(r.last_server_error_at) : NONE}</td>
                      <td className={TD}><Trend values={r.trend} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Panel>
      )}
    </LoadState>
  );
}

/* ── Logs ────────────────────────────────────────────────── */

function Select({ label, value, onChange, options }: { label: string; value: string; onChange: (v: string) => void; options: [string, string][] }) {
  return (
    <label className="flex flex-col gap-1 text-body-sm font-bold text-ink-soft">
      {label}
      <select value={value} onChange={(e) => onChange(e.target.value)} className="min-h-[44px] rounded-2xl border border-line bg-surface px-3 text-ink">
        {options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
      </select>
    </label>
  );
}

export function LogsPanel({ range }: { range: RangeId }) {
  const { adminFetch, me } = useAdmin();
  const [kind, setKind] = useState("");
  const [provider, setProvider] = useState("");
  const [outcome, setOutcome] = useState("");
  const [status, setStatus] = useState("");
  const [requestId, setRequestId] = useState("");
  const validId = /^[0-9a-f]{8,12}$/.test(requestId.trim()) ? requestId.trim() : "";   // half-typed ids do not refetch
  const [rows, setRows] = useState<OpsEvent[]>([]);
  const [next, setNext] = useState<string | null>(null);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [message, setMessage] = useState("");

  const query = useCallback((before: string | null) => {
    const q = new URLSearchParams({ range, limit: "50" });
    if (kind) q.set("kind", kind);
    if (provider) q.set("provider", provider);
    if (outcome) q.set("outcome", outcome);
    if (status) q.set("status", status);
    if (validId) q.set("request_id", validId);
    if (before) q.set("before", before);
    return `/admin/events?${q.toString()}`;
  }, [range, kind, provider, outcome, status, validId]);

  const load = useCallback(async (before: string | null) => {
    if (!before) setState("loading");
    try {
      const res = await adminFetch(query(before));
      if (!res.ok) {
        setMessage((await responseFailure(res)).message);
        setState("error");
        return;
      }
      const data = (await res.json()) as EventsView;
      setRows((current) => (before ? [...current, ...data.events] : data.events));
      setNext(data.next_before);
      setMeta(data);
      setState("ready");
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Bubbles did not answer.");
      setState("error");
    }
  }, [adminFetch, query]);

  useEffect(() => {
    void load(null);
  }, [load]);

  const providers: [string, string][] = [["", "Any provider"], ...me.chain.map((c): [string, string] => [c.provider, c.provider])];
  return (
    <Panel title="Logs" id="logs-title" action={meta ? <Sampled meta={meta} /> : null}>
      <form className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-5" onSubmit={(e) => { e.preventDefault(); void load(null); }}>
        <Select label="Kind" value={kind} onChange={setKind} options={[["", "Everything"], ["api", "Requests"], ["ai_attempt", "AI tries"], ["ai_reply", "AI replies"], ["error", "Errors"], ["audit", "Admin actions"]]} />
        <Select label="Provider" value={provider} onChange={setProvider} options={providers} />
        <Select label="Outcome" value={outcome} onChange={setOutcome} options={[["", "Any outcome"], ["success", "Answered (try)"], ["answered", "Answered (reply)"], ["error", "Failed"], ["timeout", "Ran out of time"], ["budget_spent", "No time left"], ["invalid_json", "Unusable answer"], ["degraded", "Calm message sent"]]} />
        <Select label="Status" value={status} onChange={setStatus} options={[["", "Any status"], ["2xx", "2xx OK"], ["4xx", "4xx"], ["5xx", "5xx"]]} />
        <label className="flex flex-col gap-1 text-body-sm font-bold text-ink-soft">
          Request id
          <input value={requestId} onChange={(e) => setRequestId(e.target.value.toLowerCase())} inputMode="text" maxLength={12} placeholder="8 characters"
            className="min-h-[44px] rounded-2xl border border-line bg-surface px-3 font-mono text-ink" />
        </label>
      </form>
      {state === "loading" && <p className="m-0 text-body-sm text-muted">Loading…</p>}
      {state === "error" && <ErrorCard inset title="Couldn't load logs" message={message} onRetry={() => void load(null)} />}
      {state === "ready" && rows.length === 0 && <Empty>No events match these filters. Try a longer range or clear a filter.</Empty>}
      {rows.length > 0 && (
        <ol className="m-0 list-none divide-y-2 divide-line p-0">
          {rows.map((e) => <EventRow key={`${e.seq ?? e.id}-${e.at}`} e={e} />)}
        </ol>
      )}
      {next && <button type="button" className={`${BTN_SECONDARY} mt-4`} onClick={() => void load(next)}>Load older</button>}
    </Panel>
  );
}

/* ── Request detail ──────────────────────────────────────── */

export function RequestDialog({ id, onClose }: { id: string; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  const [events] = useAdminQuery<EventsView>(`/admin/events?request_id=${id}&range=30d&limit=200`);
  useEffect(() => {
    const d = ref.current;
    if (d && !d.open) d.showModal();
  }, []);
  const rows = events.status === "ready" ? [...events.data.events].sort((a, b) => a.at.localeCompare(b.at)) : [];
  const start = rows.length ? new Date(rows[0].at).getTime() : 0;
  return (
    <dialog ref={ref} aria-labelledby="request-title" onClose={onClose} onClick={(e) => { if (e.target === e.currentTarget) ref.current?.close(); }}
      className="m-auto w-[min(40rem,calc(100vw-2rem))] rounded-[24px] bg-surface p-0 text-ink backdrop:bg-ink/55">
      <div className="p-6">
        <div className="mb-4 flex items-center justify-between gap-3">
          <h2 id="request-title" className="m-0 font-display text-h3">Request <span className="font-mono">{shortId(id)}</span></h2>
          <button type="button" className={BTN_SECONDARY} onClick={() => ref.current?.close()}>Close</button>
        </div>
        <p className="m-0 mb-3 text-body-sm text-muted">Technical steps only. What the person wrote is never recorded.</p>
        {events.status === "loading" && <p className="m-0 text-body-sm text-muted">Loading…</p>}
        {events.status === "error" && <p role="alert" className="m-0 text-body-sm text-bubbles-urgent">{events.message}</p>}
        {events.status === "ready" && rows.length === 0 && <Empty>Nothing was recorded for this request in the last 30 days.</Empty>}
        {rows.length > 0 && (
          <ol className="m-0 list-none space-y-2 p-0">
            {rows.map((e) => (
              <li key={`${e.seq ?? e.id}-${e.at}`} className="grid grid-cols-[5.5rem_1fr] gap-3 rounded-2xl bg-blush px-4 py-3 text-body-sm">
                <span className="tabular-nums text-muted">+{num(new Date(e.at).getTime() - start)} ms</span>
                <span><Pill tone={kindLabel(e.kind).tone}>{kindLabel(e.kind).word}</Pill> <span className="ml-1">{eventSentence(e)}</span></span>
              </li>
            ))}
          </ol>
        )}
      </div>
    </dialog>
  );
}

/* ── Settings and audit ──────────────────────────────────── */

function Confirm({ question, yes, onYes, onNo }: { question: string; yes: string; onYes: () => void; onNo: () => void }) {
  return (
    <div className="mt-2 flex flex-wrap items-center gap-2 rounded-2xl bg-tint-sun px-4 py-3 text-body-sm text-bubbles-sun-deep">
      <span className="font-bold">{question}</span>
      <button type="button" className={BTN_PRIMARY} onClick={onYes}>{yes}</button>
      <button type="button" className={BTN_SECONDARY} onClick={onNo}>Cancel</button>
    </div>
  );
}

function SettingRow({ s, onSave }: { s: Setting; onSave: (key: string, value: boolean | number) => Promise<string | null> }) {
  const [asking, setAsking] = useState(false);
  const [draft, setDraft] = useState(String(s.value));
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const save = async (value: boolean | number) => {
    setBusy(true);
    setErr(await onSave(s.key, value));
    setBusy(false);
    setAsking(false);
  };
  const provider = s.key.startsWith("provider_paused.") ? s.key.split(".")[1] : null;
  return (
    <li className="border-t border-line py-4 first:border-t-0">
      <div className="flex flex-wrap items-center gap-3">
        <div className="min-w-[12rem] flex-1">
          <p id={`label-${s.key}`} className="m-0 font-extrabold">{s.label}</p>
          <p className="m-0 text-body-sm text-muted">{s.updated_at ? `Changed ${ago(s.updated_at)}` : "Default"}</p>
        </div>
        {s.type === "bool" ? (
          <button type="button" role="switch" aria-labelledby={`label-${s.key}`} aria-checked={provider ? s.value !== true : s.value === true} disabled={busy}
            onClick={() => (provider && s.value !== true ? setAsking(true) : void save(!(s.value as boolean)))}
            className={`min-h-[44px] rounded-full border px-4 text-body-sm font-extrabold ${(provider ? s.value !== true : s.value === true) ? "border-bubbles-grape bg-tint-grape text-bubbles-grape-deep" : "border-line bg-surface text-ink-soft"}`}>
            {provider ? (s.value ? "Paused" : "Running") : s.value ? "On" : "Off"}
          </button>
        ) : (
          <form className="flex items-center gap-2" onSubmit={(e) => { e.preventDefault(); void save(Number(draft)); }}>
            <input type="number" min={s.min} max={s.max} value={draft} onChange={(e) => setDraft(e.target.value)} aria-label={s.label}
              className="min-h-[44px] w-24 rounded-2xl border border-line bg-surface px-3" />
            <button type="submit" className={BTN_SECONDARY} disabled={busy}>Save</button>
          </form>
        )}
      </div>
      {asking && provider && (
        <Confirm question={`Pause ${provider}? Bubbles will skip it and ask the next one.`} yes="Yes, pause" onYes={() => void save(true)} onNo={() => setAsking(false)} />
      )}
      {err && <p role="alert" className="m-0 mt-2 text-body-sm text-bubbles-urgent">{err}</p>}
    </li>
  );
}

export function SettingsPanel() {
  const { adminFetch } = useAdmin();
  const [settings, reload] = useAdminQuery<SettingsView>("/admin/settings");
  const [audit, reloadAudit] = useAdminQuery<EventsView>("/admin/audit?range=30d&limit=100");
  const [clearing, setClearing] = useState<"idle" | "asking" | "done">("idle");
  const [clearFailure, setClearFailure] = useState<string | null>(null);

  const save = useCallback(async (key: string, value: boolean | number): Promise<string | null> => {
    const res = await adminFetch("/admin/settings", { method: "PUT", body: JSON.stringify({ key, value }) });
    if (!res.ok) return (await responseFailure(res)).message;
    reload();
    reloadAudit();
    return null;
  }, [adminFetch, reload, reloadAudit]);

  const groups: [string, (s: Setting) => boolean][] = [
    ["AI providers", (s) => s.key.startsWith("provider_paused.")],
    ["Caches", (s) => s.key.startsWith("cache_enabled.")],
    ["Logs", (s) => s.key === "telemetry_retention_days"],
  ];
  return (
    <>
      <Panel title="Settings" id="settings-title">
        <LoadState state={settings} title="Couldn't load settings" retry={reload}>
          {(d) => (
            <div className="space-y-6">
              {d.persisted === false && <p className="m-0 rounded-2xl bg-tint-sky px-4 py-3 text-body-sm text-bubbles-sky-deep">Changes apply now but are not saved, so a restart resets them. Apply 20261013_bubbles_ops.sql to keep them.</p>}
              {d.chain.every((c) => c.paused) && <p role="alert" className="m-0 rounded-2xl bg-tint-urgent px-4 py-3 text-body-sm font-bold text-bubbles-urgent">Every provider is paused. Everyone gets the calm message.</p>}
              {groups.map(([title, match]) => (
                <section key={title} aria-label={title}>
                  <h3 className="m-0 mb-1 text-label text-ink-soft">{title}</h3>
                  <ul className="m-0 list-none p-0">{d.settings.filter(match).map((s) => <SettingRow key={`${s.key}-${String(s.value)}`} s={s} onSave={save} />)}</ul>
                </section>
              ))}
              <section aria-label="Server caches">
                <h3 className="m-0 mb-2 text-label text-ink-soft">Server caches</h3>
                {clearing === "asking" ? (
                  <Confirm question="Clear every server cache? The next requests will be a little slower." yes="Yes, clear"
                    onYes={async () => {
                      try {
                        const r = await adminFetch("/admin/cache/clear", { method: "POST" });
                        if (r.ok) setClearing("done");
                        else { setClearFailure((await responseFailure(r)).message); setClearing("idle"); }
                      } catch (e) {
                        setClearFailure(e instanceof Error ? e.message : "Bubbles did not answer.");
                        setClearing("idle");
                      }
                      reloadAudit();
                    }}
                    onNo={() => setClearing("idle")} />
                ) : (
                  <div className="flex items-center gap-3">
                    <button type="button" className={BTN_SECONDARY} onClick={() => setClearing("asking")}>Clear caches</button>
                    {clearing === "done" && <span className="text-body-sm text-muted">Cleared.</span>}
                    {clearFailure && clearing === "idle" && <span role="alert" className="text-body-sm text-bubbles-urgent">{clearFailure}</span>}
                  </div>
                )}
              </section>
              <p className="m-0 text-body-sm text-muted">Secrets, safety rules, clinical numbers, sign-in, the database rules and the paid or keyless AI switches cannot be changed here.</p>
            </div>
          )}
        </LoadState>
      </Panel>
      <Panel title="Admin activity" id="audit-title">
        <LoadState state={audit} title="Couldn't load admin activity" retry={reloadAudit}>
          {(a) => a.events.length === 0 ? <Empty>No admin activity in the last 30 days.</Empty> : (
            <ol className="m-0 list-none divide-y-2 divide-line p-0">
              {a.events.map((e) => (
                <li key={`${e.seq ?? e.id}-${e.at}`} className="flex flex-wrap items-baseline gap-x-3 py-3 text-body-sm">
                  <span className="tabular-nums text-muted">{new Date(e.at).toLocaleString("en-GB", { hour12: false })}</span>
                  <span>{eventSentence(e)}</span>
                  {typeof e.data.actor === "string" && <span className="text-muted">by {shortId(e.data.actor)}</span>}
                </li>
              ))}
            </ol>
          )}
        </LoadState>
      </Panel>
    </>
  );
}

