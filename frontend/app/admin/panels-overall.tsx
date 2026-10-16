"use client";

// The Overall page: totals that survive restarts (daily counters, backend/ops_rollups.py), integer user counts, rates, latency per stage,
// tokens and cost at read time, funnel, retention, consent, safety, errors, push and community counts. Counts only: no user id anywhere.

import type { ReactNode } from "react";
import { BTN_SECONDARY, CARD } from "../../components/hub/HubKit";
import { NONE, humanize, ms, num, pct, words } from "./format";
import { Empty, LoadState, Panel, Pill, Refreshing, Stat, useAdminQuery } from "./kit";
import { toCsv } from "./live";

type Pair = { p50_ms: number | null; p95_ms: number | null };
type Provider = {
  provider: string; model: string; attempts: number; success: number; failed: number; success_rate: number | null; timeout_rate: number | null;
  answered_replies: number; tokens_in: number; tokens_out: number; p50_ms: number | null; p95_ms: number | null;
  cost: { usd: number | null; basis: string };
};
type Rate = { eligible: number; returned: number; rate: number | null };
type Overall = {
  generated_at: string; source: string; capped: boolean; range: string;
  totals: { requests: number; chats: number; server_errors: number; onboarding_completed: number };
  latency: { api: Pair; chat: Pair; reply: Pair };
  ai: {
    replies: number; answered: number; degraded: number; degraded_rate: number | null; fallback_used: number; fallback_rate: number | null;
    attempts: number; timeouts: number; timeout_rate: number | null; ai_share: number | null; deterministic_share: number | null;
    consent_needed: number; consent_needed_rate: number | null;
  };
  providers: Provider[];
  stages: { stage: string; n: number; p50_ms: number | null; p95_ms: number | null }[];
  route_mix: { route_kind: string; count: number; share: number | null }[];
  safety: { totals: Record<string, number>; per_day: { day: string; GREEN: number; AMBER: number; RED: number }[] };
  features: { feature: string; requests: number }[];
  routes: { route: string; requests: number; errors_5xx: number; feature: string }[];
  funnel: { step: string; count: number; of_first: number | null }[];
  errors: Record<string, number>;
  status_classes: Record<string, number>;
  client_crashes: Record<string, number>;
  users: {
    dau: number | null; wau: number | null; mau: number | null; capped: boolean; signups: Record<string, number> | null;
    signups_total: number | null; retention: Record<"d1" | "d7" | "d30", Rate> | null;
  };
  consent: { purpose: string; title: string; granted: number; declined: number; decided: number; rate: number | null }[] | null;
  community: { visible: number; held: number; removed: number } | null;
  push: { active_devices: number } | null;
  rollups: { mode: string; through: string | null; last_run?: string };
  persistence: { mode: string };
};
type Schema = { registered: boolean; applied: string[]; missing: { name: string; why: string }[] };

const TH = "whitespace-nowrap px-3 py-2 text-left text-label text-ink-soft";
const TD = "border-t border-line px-3 py-3 align-top text-body-sm";

function download(name: string, csv: string) {
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

/** A titled table with its own "Export CSV". `rows` hold the raw numbers; `show` turns a row into display cells. */
function Table({ title, id, range, headers, rows, show, empty, note }: {
  title: string; id: string; range: string; headers: string[]; rows: (string | number | null)[][];
  show?: (row: (string | number | null)[]) => ReactNode[]; empty: string; note?: ReactNode;
}) {
  return (
    <Panel title={title} id={id} action={rows.length ? (
      <button type="button" className={BTN_SECONDARY} onClick={() => download(`bubbles-${id}-${range}.csv`, toCsv(headers, rows))}>Export CSV</button>
    ) : null}>
      {note}
      {rows.length === 0 ? <Empty>{empty}</Empty> : (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse">
            <caption className="sr-only">{title}</caption>
            <thead><tr>{headers.map((h) => <th key={h} scope="col" className={TH}>{h}</th>)}</tr></thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i}>{(show ? show(r) : r.map((c) => (c === null ? NONE : typeof c === "number" ? num(c) : c))).map((c, j) => (
                  j === 0 ? <th key={j} scope="row" className={`${TD} text-left font-extrabold`}>{c}</th> : <td key={j} className={`${TD} tabular-nums`}>{c}</td>
                ))}</tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}

function money(c: Provider["cost"]): string {
  return c.usd === null ? "Unknown" : c.usd === 0 ? "$0, free tier" : `$${c.usd.toFixed(2)}`;
}

function Sources({ o }: { o: Overall }) {
  const r = o.rollups;
  const saved = r.mode === "ok";
  const msg = saved ? `Totals are saved daily${r.through ? ` (up to ${new Date(r.through).toLocaleString("en-GB", { hour12: false })})` : ""} and survive restarts.`
    : r.mode === "not_used" ? "Short range: counted from recent events."
    : r.mode === "not_set_up" ? "Daily totals are not saved yet. Apply 20261016_bubbles_ops_rollups.sql in Supabase. Until then this page counts events still held (memory only if the ops table is not set up)."
    : r.mode === "empty" ? "Daily totals have not been built yet; they appear after the first hourly run."
    : "Daily totals could not be read just now; showing recent events only.";
  return (
    <p role="note" className={`m-0 rounded-2xl px-5 py-3 text-body-sm ${saved || r.mode === "not_used" ? "bg-blush text-ink-soft" : "bg-tint-sky text-bubbles-sky-deep"}`}>
      {msg}{o.capped ? " Sampled: the newest events only." : ""}
    </p>
  );
}

function Schema() {
  const [state, reload] = useAdminQuery<Schema>("/admin/schema");
  return (
    <Panel title="Database setup" id="schema-title">
      <LoadState state={state} title="Couldn't read the database setup" retry={reload} rows={2}>
        {(s) => (
          <div className="space-y-3">
            {!s.registered && <p className="m-0 rounded-2xl bg-tint-sky px-4 py-3 text-body-sm text-bubbles-sky-deep">The migration register is not set up, so no migration can be confirmed. Apply 20261016_bubbles_schema_migrations.sql first.</p>}
            {s.registered && s.missing.length === 0 && <Pill tone="mint">Every known migration is applied</Pill>}
            {s.missing.length > 0 && (
              <ul className="m-0 list-none space-y-2 p-0">
                {s.missing.map((m) => (
                  <li key={m.name} className="rounded-2xl bg-blush px-4 py-3 text-body-sm">
                    <Pill tone="sun">{s.registered ? "Not applied" : "Unknown"}</Pill> <code className="font-mono text-chip">{m.name}</code>
                    <span className="mt-1 block text-muted">{m.why}</span>
                  </li>
                ))}
              </ul>
            )}
            {s.applied.length > 0 && <p className="m-0 text-body-sm text-muted">Applied: {s.applied.length}</p>}
          </div>
        )}
      </LoadState>
    </Panel>
  );
}

export function OverallPanel({ range }: { range: string }) {
  const [state, reload] = useAdminQuery<Overall>(`/admin/overall?range=${range}`, 20);
  return (
    <LoadState state={state} title="Couldn't load the overall numbers" retry={reload} rows={5}>
      {(o) => {
        const u = o.users;
        const days = o.safety.per_day;
        return (
          <>
            <Sources o={o} />
            <section aria-label="Totals" className={CARD}>
              <div className="flex items-center justify-end px-5 pt-3"><Refreshing on={state.status === "ready" && state.refreshing} /></div>
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4">
                <Stat label="Requests" value={num(o.totals.requests)} note={`${num(o.totals.server_errors)} server errors`} />
                <Stat label="Chat messages" value={num(o.totals.chats)} />
                <Stat label="Sign-ups" value={num(u.signups_total)} note={u.signups ? `${num(u.signups["24h"])} today, ${num(u.signups["7d"])} this week` : null} />
                <Stat label="Finished setup" value={num(o.totals.onboarding_completed)} />
                <Stat label="Active today" value={num(u.dau)} note="DAU, sent a chat message" />
                <Stat label="Active this week" value={num(u.wau)} note="WAU" />
                <Stat label="Active this month" value={num(u.mau)} note={u.capped ? "MAU, newest messages only" : "MAU"} />
                <Stat label="Chat reply time" value={ms(o.latency.chat.p50_ms)} note={`p95 ${ms(o.latency.chat.p95_ms)}`} />
              </div>
            </section>

            <Table title="How fast" id="latency" range={range} headers={["Stage", "Calls", "p50 ms", "p95 ms"]}
              rows={[["Whole request", null, o.latency.api.p50_ms, o.latency.api.p95_ms], ["Chat request", null, o.latency.chat.p50_ms, o.latency.chat.p95_ms],
                ["AI reply", null, o.latency.reply.p50_ms, o.latency.reply.p95_ms],
                ...o.stages.map((s): (string | number | null)[] => [`Chat: ${s.stage}`, s.n, s.p50_ms, s.p95_ms])]}
              show={(r) => [r[0], r[1] === null ? "" : num(r[1] as number), ms(r[2] as number | null), ms(r[3] as number | null)]}
              empty="No timings yet." />

            <Table title="AI providers and cost" id="providers" range={range}
              headers={["Provider", "Model", "Tries", "Failed", "Success rate", "Timeout rate", "Answers", "p50 ms", "p95 ms", "Tokens in", "Tokens out", "Cost"]}
              rows={o.providers.map((p) => [p.provider, p.model, p.attempts, p.failed, p.success_rate, p.timeout_rate, p.answered_replies, p.p50_ms, p.p95_ms, p.tokens_in, p.tokens_out, money(p.cost)])}
              show={(r) => [r[0], r[1], num(r[2] as number), num(r[3] as number), pct(r[4] as number | null), pct(r[5] as number | null), num(r[6] as number),
                ms(r[7] as number | null), ms(r[8] as number | null), num(r[9] as number), num(r[10] as number), r[11]]}
              empty="No AI tries in this range."
              note={<p className="m-0 mb-3 text-body-sm text-muted">
                Answered by AI {pct(o.ai.ai_share)}, by Bubbles itself {pct(o.ai.deterministic_share)}, asked for consent {pct(o.ai.consent_needed_rate)}.
                Fell back {pct(o.ai.fallback_rate)}, calm message {pct(o.ai.degraded_rate)}, timeouts {pct(o.ai.timeout_rate)}. Cost is worked out when you read this page.
              </p>} />

            <div className="grid gap-5 lg:grid-cols-2">
              <Table title="Features used" id="features" range={range} headers={["Feature", "Requests"]} rows={o.features.map((f) => [f.feature, f.requests])} empty="No requests yet." />
              <Table title="Setup funnel" id="funnel" range={range} headers={["Step", "People", "Of the first step"]}
                rows={o.funnel.map((f) => [humanize(f.step), f.count, f.of_first])}
                show={(r) => [r[0], num(r[1] as number), pct(r[2] as number | null)]} empty="No setup steps counted yet." />
            </div>

            <div className="grid gap-5 lg:grid-cols-2">
              <Table title="Coming back" id="retention" range={range} headers={["Day", "Signed up that long ago", "Came back", "Rate"]}
                rows={u.retention ? (["d1", "d7", "d30"] as const).map((k) => [`Day ${k.slice(1)}`, u.retention![k].eligible, u.retention![k].returned, u.retention![k].rate]) : []}
                show={(r) => [r[0], num(r[1] as number), num(r[2] as number), pct(r[3] as number | null)]}
                empty="Retention needs the profiles and chat tables." />
              <Table title="Consent choices" id="consent" range={range} headers={["Purpose", "On", "Off", "Rate on"]}
                rows={(o.consent ?? []).map((c) => [c.title, c.granted, c.declined, c.rate])}
                show={(r) => [r[0], num(r[1] as number), num(r[2] as number), pct(r[3] as number | null)]}
                empty="No consent choices recorded yet (or the consent table is not applied)." />
            </div>

            <Table title="Safety levels per day" id="safety" range={range} headers={["Day", "Green", "Amber", "Red"]}
              rows={days.map((d) => [d.day, d.GREEN, d.AMBER, d.RED])} empty="No chat messages in this range."
              show={(r) => [r[0], num(r[1] as number), num(r[2] as number), num(r[3] as number)]} />

            <div className="grid gap-5 lg:grid-cols-2">
              <Table title="Routes and errors" id="routes" range={range} headers={["Route", "Requests", "Server errors"]}
                rows={o.routes.map((r) => [r.route, r.requests, r.errors_5xx])} empty="No requests yet." />
              <Table title="Error kinds" id="errors" range={range} headers={["Kind", "Count"]}
                rows={[...Object.entries(o.errors).map(([k, v]): [string, number] => [words(k), v]),
                  ...Object.entries(o.client_crashes).map(([k, v]): [string, number] => [`App: ${words(k)}`, v])]}
                empty="No errors in this range." />
            </div>

            <Panel title="Push and community" id="extras">
              <div className="grid grid-cols-2 sm:grid-cols-4">
                <Stat label="Phones with reminders on" value={o.push ? num(o.push.active_devices) : NONE} note={o.push ? null : "Not set up yet"} />
                <Stat label="Posts visible" value={o.community ? num(o.community.visible) : NONE} note={o.community ? null : "Community not set up yet"} />
                <Stat label="Posts held" value={o.community ? num(o.community.held) : NONE} />
                <Stat label="Posts removed" value={o.community ? num(o.community.removed) : NONE} />
              </div>
            </Panel>
            <Schema />
          </>
        );
      }}
    </LoadState>
  );
}
