/**
 * Live page logic, kept pure so it is tested (live.test.ts): one row per request (the request event plus its AI tries and reply),
 * the filters, and the CSV export used by the Overall page. Nothing here knows about the network.
 */
import type { OpsEvent } from "./format";

export const STAGES = ["pre", "ctx", "rag", "ai", "post"] as const;
export type Stage = (typeof STAGES)[number];

/** Plain names for the five parts of a chat reply (backend/ops_telemetry.py STAGES). */
export const STAGE_LABELS: Record<Stage, string> = {
  pre: "Understanding the message", ctx: "Reading the person's own data", rag: "Looking up reading sources",
  ai: "Waiting for the model", post: "Checking and saving the reply",
};

export type LiveRow = {
  key: string;
  at: string;
  seq: number;
  uid: string | null;
  requestId: string | null;
  method: string | null;
  route: string | null;
  feature: string | null;
  routeKind: string | null;
  safety: string | null;
  status: number | null;
  latencyMs: number | null;
  provider: string | null;
  model: string | null;
  position: number | null;   // where in the provider order the attempt that answered sat (1 = first choice); null when no model answered
  fallback: boolean;
  stages: Partial<Record<Stage, number>>;
  error: string | null;
  kind: OpsEvent["kind"];
  events: OpsEvent[];
};

const text = (v: unknown): string | null => (typeof v === "string" && v ? v : null);
const num = (v: unknown): number | null => (typeof v === "number" && Number.isFinite(v) ? v : null);

/** Newest event first in, newest request first out. Events without a request id (errors, funnel steps) get a row each. */
export function groupLive(events: OpsEvent[]): LiveRow[] {
  const groups = new Map<string, OpsEvent[]>();
  for (const raw of events) {
    const e: OpsEvent = { ...raw, data: raw.data && typeof raw.data === "object" ? raw.data : {} };   // a malformed row never breaks the page
    const key = e.request_id ?? `seq-${e.seq ?? e.id ?? e.at}`;
    const list = groups.get(key);
    if (list) list.push(e);
    else groups.set(key, [e]);
  }
  const rows: LiveRow[] = [];
  for (const [key, list] of groups) {
    const chain = [...list].sort((a, b) => (a.seq ?? 0) - (b.seq ?? 0));
    const api = chain.find((e) => e.kind === "api");
    const reply = chain.find((e) => e.kind === "ai_reply");
    const attempts = chain.filter((e) => e.kind === "ai_attempt");
    const answering = attempts.find((e) => e.data.outcome === "success");
    const winner = answering ?? attempts[attempts.length - 1];
    const position = num(answering?.data.position);
    const failure = chain.find((e) => e.kind === "error") ?? attempts.slice().reverse().find((e) => e.data.outcome !== "success" && e.data.error_category);
    const lead = api ?? chain[chain.length - 1];
    const stages: LiveRow["stages"] = {};
    for (const s of STAGES) {
      const value = num(api?.data[`stage_${s}_ms`]);
      if (value !== null) stages[s] = value;
    }
    const uid = chain.map((e) => e.uid).find((u): u is string => !!u) ?? null;
    const error = text(failure?.data.error_category) ?? text(failure?.data.category) ??
      (reply?.data.outcome === "degraded" ? "degraded" : null) ?? ((num(api?.data.status) ?? 0) >= 500 ? "server_error" : null);
    rows.push({
      key,
      at: lead.at,
      seq: Math.max(...chain.map((e) => e.seq ?? 0)),
      uid,
      requestId: lead.request_id,
      method: text(api?.data.method),
      route: text(api?.data.route) ?? text(chain.find((e) => e.kind === "error")?.data.route),
      feature: text(api?.feature),
      routeKind: text(api?.data.route_kind),
      safety: text(api?.data.safety_level),
      status: num(api?.data.status),
      latencyMs: num(api?.data.latency_ms),
      provider: text(reply?.data.provider) ?? text(winner?.data.provider),
      model: text(reply?.data.model) ?? text(winner?.data.model),
      position,
      fallback: reply?.data.fallback_used === true || (position !== null && position > 1),
      stages,
      error,
      kind: lead.kind,
      events: chain,
    });
  }
  return rows.sort((a, b) => b.seq - a.seq);
}

export type LiveFilters = { feature: string; provider: string; status: "" | "2xx" | "4xx" | "5xx"; errorsOnly: boolean };
export const NO_FILTERS: LiveFilters = { feature: "", provider: "", status: "", errorsOnly: false };

export function isError(row: LiveRow): boolean {
  return row.error !== null || (row.status !== null && row.status >= 400) || row.kind === "error" || row.kind === "client";
}

export function filterRows(rows: LiveRow[], f: LiveFilters): LiveRow[] {
  return rows.filter((r) =>
    (!f.feature || (r.feature ?? r.route) === f.feature) &&
    (!f.provider || r.provider === f.provider) &&
    (!f.status || (r.status !== null && `${Math.floor(r.status / 100)}xx` === f.status)) &&
    (!f.errorsOnly || isError(r)));
}

/** The choices for the filter menus, from what is on screen. */
export function filterChoices(rows: LiveRow[]): { features: string[]; providers: string[] } {
  const uniq = (xs: (string | null)[]) => [...new Set(xs.filter((x): x is string => !!x))].sort();
  return { features: uniq(rows.map((r) => r.feature ?? r.route)), providers: uniq(rows.map((r) => r.provider)) };
}

/** "1", or "2, fallback" when a later provider had to answer; null when no model answered. */
export function positionWords(row: Pick<LiveRow, "position" | "fallback">): string | null {
  if (row.position === null) return null;
  return row.fallback ? `${row.position}, fallback` : String(row.position);
}

/** "pre 40 ms, ctx 120 ms ..." for the stages that were measured; null when none were. */
export function stageWords(stages: LiveRow["stages"], fmt: (ms: number) => string): string | null {
  const parts = STAGES.filter((s) => stages[s] !== undefined).map((s) => `${s} ${fmt(stages[s] as number)}`);
  return parts.length ? parts.join(", ") : null;
}

/** One CSV document. A leading = + - @ in a cell is defused so a spreadsheet never runs it as a formula. */
export function toCsv(headers: string[], rows: (string | number | null | undefined)[][]): string {
  const cell = (v: string | number | null | undefined) => {
    let s = v === null || v === undefined ? "" : String(v);
    if (typeof v === "string" && /^[=+\-@\t\r]/.test(s)) s = `'${s}`;
    return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  return [headers, ...rows].map((r) => r.map(cell).join(",")).join("\r\n") + "\r\n";
}

/** Time-ordered list of the events behind a row, as "+N ms" offsets from the first. */
export function chainOffsets(row: LiveRow): { event: OpsEvent; offsetMs: number }[] {
  const start = row.events.length ? new Date(row.events[0].at).getTime() : 0;
  return row.events.map((event) => ({ event, offsetMs: Math.max(0, new Date(event.at).getTime() - start) }));
}
