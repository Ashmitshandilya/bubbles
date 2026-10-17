/**
 * The save / skip decision on the health details Bubbles noticed in chat.
 *
 * Pure logic, no React: an optimistic reducer (the card flips the instant a button is pressed), the one batch
 * request (POST /health-events/confirmation) with an honest answer for every id, and the view the card renders.
 * What the server says always wins; a decision that never reached it is rolled back, never shown as saved.
 */
import { settledState, type ExtractedHealthEvent } from "../lib/bubbles-events";

export type DecisionStatus = "saved" | "dismissed" | "retracted";
/** optimistic: sent, no answer yet. settled: the server answered. checking: the answer was lost, re-reading the real status. */
export type DecisionPhase = "optimistic" | "settled" | "checking";
export type Projection = "done" | "queued" | "compat";

export interface Decision {
  status: DecisionStatus;
  phase: DecisionPhase;
  projection?: Projection;
}
export type Decisions = Record<string, Decision>;

/** The backend's batch limit (POST /health-events/confirmation accepts at most 30 decisions). */
export const BATCH_MAX = 30;

/** Server status words (extraction_status) to what the card shows. Anything else is not an answer. */
export function statusFromServer(status: unknown): DecisionStatus | null {
  if (status === "confirmed") return "saved";
  if (status === "rejected") return "dismissed";
  if (status === "retracted" || status === "superseded") return "retracted";
  return null;
}

/** Flip the cards at once. An id that already has a decision is left alone, so a second press is harmless. */
export function applyOptimistic(state: Decisions, ids: string[], confirmed: boolean): Decisions {
  const fresh = ids.filter((id) => !state[id]);
  if (fresh.length === 0) return state;
  const next = { ...state };
  for (const id of fresh) next[id] = { status: confirmed ? "saved" : "dismissed", phase: "optimistic" };
  return next;
}

/** Drop decisions the server never confirmed (a settled one is never undone here). */
export function rollback(state: Decisions, ids: string[]): Decisions {
  const next = { ...state };
  for (const id of ids) if (next[id] && next[id].phase !== "settled") delete next[id];
  return next;
}

/** The answer was lost (timeout, network, a waking host): keep the choice on screen but say it is being checked. */
export function markChecking(state: Decisions, ids: string[]): Decisions {
  const next = { ...state };
  for (const id of ids) if (next[id] && next[id].phase === "optimistic") next[id] = { ...next[id], phase: "checking" };
  return next;
}

/** A correction withdrew these events: settled, not retryable. */
export function markRetracted(state: Decisions, ids: string[]): Decisions {
  const next = { ...state };
  for (const id of ids) next[id] = { status: "retracted", phase: "settled" };
  return next;
}

export interface ServerResult {
  id: string;
  status: string;
  projection?: Projection;
}

/** Read a batch answer. Rows without a string id or status are dropped; a body that is not the contract gives []. */
export function parseBatch(payload: unknown): ServerResult[] {
  const list = (payload as { results?: unknown } | null)?.results;
  if (!Array.isArray(list)) return [];
  const out: ServerResult[] = [];
  for (const row of list) {
    const r = (row !== null && typeof row === "object" ? row : {}) as Record<string, unknown>;
    if (typeof r.id !== "string" || typeof r.status !== "string") continue;
    // The server answers a withdrawn event with an error row (409 or 410): that is settled, not a failure.
    const status = r.status === "error" && (r.code === 409 || r.code === 410) ? "retracted" : r.status;
    const projection = r.projection === "done" || r.projection === "queued" || r.projection === "compat" ? r.projection : undefined;
    out.push({ id: r.id, status, projection });
  }
  return out;
}

export interface Settled {
  state: Decisions;
  /** Sent ids the server did not answer for (or answered with a status that is not a decision). */
  missing: string[];
  /** Ids a correction had already withdrawn. */
  withdrawn: string[];
  /** Ids whose real status differs from what was asked (for example "skip" on an event that was already saved). */
  differed: string[];
}

/** Commit each id from what the server really says. `sent` is every id the request carried. */
export function settleFromServer(state: Decisions, results: ServerResult[], sent: string[], confirmed: boolean): Settled {
  const byId = new Map(results.map((r) => [r.id, r]));
  const next = { ...state };
  const missing: string[] = [];
  const withdrawn: string[] = [];
  const differed: string[] = [];
  const asked: DecisionStatus = confirmed ? "saved" : "dismissed";
  for (const id of sent) {
    const result = byId.get(id);
    const status = result ? statusFromServer(result.status) : null;
    if (!result || !status) {
      missing.push(id);
      continue;
    }
    next[id] = { status, phase: "settled", projection: result.projection };
    if (status === "retracted") withdrawn.push(id);
    else if (status !== asked) differed.push(id);
  }
  return { state: rollback(next, missing), missing, withdrawn, differed };
}

/** Event id -> server status, read from the rows of GET /chat/conversations/{id}/messages (the settled overlay). */
export function statusesFromRows(rows: unknown): Record<string, string> {
  const out: Record<string, string> = {};
  if (!Array.isArray(rows)) return out;
  for (const row of rows) {
    const events = (row as { health_events?: unknown } | null)?.health_events;
    if (!Array.isArray(events)) continue;
    for (const e of events) {
      const ev = (e !== null && typeof e === "object" ? e : {}) as Record<string, unknown>;
      if (typeof ev.id === "string" && typeof ev.status === "string") out[ev.id] = ev.status;
    }
  }
  return out;
}

/** After "checking": what the re-read says. Ids still pending (or unknown) are rolled back so the buttons return. */
export function settleFromRead(state: Decisions, ids: string[], statuses: Record<string, string>): Settled {
  const results: ServerResult[] = ids.flatMap((id) => (statusFromServer(statuses[id]) ? [{ id, status: statuses[id] }] : []));
  // The confirmed flag is only used to flag "differed"; a re-read has no expectation, so report none as different.
  const settled = settleFromServer(state, results, ids, true);
  return { ...settled, differed: [] };
}

// ---------------------------------------------------------------------------
// The one batch request
// ---------------------------------------------------------------------------

export type Fetcher = (path: string, init?: RequestInit, limits?: { timeoutMs?: number; retries?: number }) => Promise<Response>;

export interface Submitted {
  results: ServerResult[];
  /** Ids with no answer at all. */
  unanswered: string[];
  /** The HTTP status of the refusal that left ids unanswered; null when no response arrived (timeout, network). */
  status: number | null;
}

/** An answer was lost and the server may still have committed: the caller re-reads instead of assuming failure. */
export function isAmbiguous(status: number | null): boolean {
  return status === null || status >= 500;
}

const LIMITS = { timeoutMs: 30_000, retries: 1 };

async function postBatch(
  fetcher: Fetcher,
  decisions: Array<{ id: string; confirmed: boolean }>,
  token?: string
): Promise<{ response: Response } | { error: true }> {
  try {
    const response = await fetcher(
      "/health-events/confirmation",
      { method: "POST", body: JSON.stringify({ decisions }), ...(token ? { headers: { Authorization: `Bearer ${token}` } } : {}) },
      LIMITS
    );
    return { response };
  } catch {
    return { error: true };
  }
}

/**
 * Send decisions in batches of at most BATCH_MAX. A network error is retried once by the fetcher; a 401 refreshes
 * the session once and sends again. Never throws.
 */
export async function submitDecisions(
  fetcher: Fetcher,
  ids: string[],
  confirmed: boolean,
  refreshToken: () => Promise<string | null>
): Promise<Submitted> {
  const out: Submitted = { results: [], unanswered: [], status: null };
  const chunks: string[][] = [];
  for (let i = 0; i < ids.length; i += BATCH_MAX) chunks.push(ids.slice(i, i + BATCH_MAX));

  await Promise.all(
    chunks.map(async (chunk) => {
      const decisions = chunk.map((id) => ({ id, confirmed }));
      let attempt = await postBatch(fetcher, decisions);
      if ("response" in attempt && attempt.response.status === 401) {
        const token = await refreshToken().catch(() => null);
        if (token) attempt = await postBatch(fetcher, decisions, token);
      }
      if ("error" in attempt) {
        out.unanswered.push(...chunk);
        return;
      }
      const { response } = attempt;
      if (!response.ok) {
        out.unanswered.push(...chunk);
        out.status = response.status;
        return;
      }
      let rows: ServerResult[] = [];
      try {
        rows = parseBatch(await response.json());
      } catch {
        rows = [];
      }
      out.results.push(...rows);
      const answered = new Set(rows.map((r) => r.id));
      out.unanswered.push(...chunk.filter((id) => !answered.has(id)));
    })
  );
  return out;
}

// ---------------------------------------------------------------------------
// What the card shows
// ---------------------------------------------------------------------------

export type CardState = DecisionStatus | "checking" | null;

/** This session's decision wins; otherwise whatever the server already settled (a reloaded message). */
export function eventState(event: ExtractedHealthEvent, decisions: Decisions): CardState {
  const d = event.id ? decisions[event.id] : undefined;
  if (d) return d.phase === "checking" ? "checking" : d.status;
  return settledState(event);
}

export interface CardView {
  /** Events that take part in the decision: waiting for one, or already decided (here or on the server). */
  decidable: Array<ExtractedHealthEvent & { id: string }>;
  /** Ids still waiting for a press. */
  pendingIds: string[];
  saved: ExtractedHealthEvent[];
  skipped: ExtractedHealthEvent[];
  withdrawn: ExtractedHealthEvent[];
  /** Some choice is on screen but not confirmed yet ("Saving, checking..."). */
  checking: boolean;
  /** Every decidable event has a state. */
  resolved: boolean;
  /** True only when every saved event reached the health record in this session (projection "done"). */
  recordSaved: boolean;
}

export function cardView(events: ExtractedHealthEvent[], decisions: Decisions): CardView {
  const decidable = events.filter(
    (e): e is ExtractedHealthEvent & { id: string } => e.id !== null && (e.isConfirmable || settledState(e) !== null || decisions[e.id] !== undefined)
  );
  const states = decidable.map((e) => eventState(e, decisions));
  const pendingIds = decidable.filter((_, i) => states[i] === null).map((e) => e.id);
  const pick = (want: CardState) => decidable.filter((_, i) => states[i] === want);
  const saved = pick("saved");
  const checking = states.includes("checking");
  return {
    decidable,
    pendingIds,
    saved,
    skipped: pick("dismissed"),
    withdrawn: pick("retracted"),
    checking,
    resolved: decidable.length > 0 && pendingIds.length === 0 && !checking,
    recordSaved: saved.length > 0 && saved.every((e) => decisions[e.id]?.projection === "done"),
  };
}

/** The one line of copy for a failed or partial decision. Never claims a save that did not happen. */
export function decisionError(confirmed: boolean, failedCount: number, total: number, status: number | null): string | null {
  if (failedCount === 0) return null;
  if (status === 401) return "Your session has expired. Sign out and back in, then try again.";
  const which = failedCount < total ? `${failedCount} of these` : total === 1 ? "this" : "these";
  return `Bubbles couldn't ${confirmed ? "save" : "skip"} ${which} just now. Try again.`;
}
