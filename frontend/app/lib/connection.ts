// Pure connection and error classification for the Bubbles client. No React, no fetch, so every rule here is
// unit-tested (connection.test.ts). The UI never guesses why a request failed: it asks classifyFailure.

export type FailureKind =
  | "backend_offline"
  | "timeout"
  | "database_permission"
  | "auth_expired"
  | "validation"
  | "server_error"
  | "not_found"
  | "ok";

export type Failure = {
  kind: FailureKind;
  /** Plain, kind, actionable. Safe to show as-is. */
  message: string;
  /** Trying the same thing again may work without the user changing anything. */
  retryable: boolean;
  /** The app cannot be used until this is resolved (offline, signed out). */
  blocking: boolean;
};

/** What the caller knows. A real HTTP status always wins over the flags: a response means the server is up. */
export type FailureInput = {
  status?: number;
  body?: unknown;
  networkError?: boolean;
  timedOut?: boolean;
  /** Set with `networkError` when the server did answer a no-cors probe: this page's address is what it refuses. */
  corsOrigin?: string;
};

export const MESSAGES = {
  offline:
    "Bubbles can't reach its server right now. It may be waking up, which can take up to a minute. This page will reconnect by itself.",
  timeout: "Bubbles is taking longer than usual to answer. Please try again in a moment.",
  database:
    "Bubbles is running, but the database needs a one-time permission update. Your entries are still being saved in compatibility mode.",
  databaseSave:
    "Bubbles is running, but the database needs a one-time permission update, so this entry couldn't be saved yet. Settings has the details.",
  databaseDown: "Bubbles is running, but its database isn't answering right now. Some pages may not load until it is back.",
  auth: "Your session expired. Please sign in again.",
  notFound: "Bubbles couldn't find that. It may have been removed, or the running backend may be out of date.",
  validation: "Bubbles couldn't accept that. Please check the details and try again.",
  server: "Bubbles' server ran into a problem. Please try again in a moment.",
  rateLimited: "Bubbles is getting a lot of requests right now. Please wait a moment and try again.",
  unknown: "Something went wrong. Please try again.",
  kept: "Your entry is still here, so you can try again.",
} as const;

/**
 * A browser reports "blocked by CORS" and "server is down" the same way (a rejected fetch). When the server does
 * answer a no-cors probe, the real problem is that the page's address is not on the backend's allow-list.
 */
export function corsBlockedMessage(origin: string): string {
  const address = tidy(origin, 80) || "this address";
  const local = /^https?:\/\/(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$/i.test(origin);
  const fix = local
    ? "Open the app at http://localhost:3000, or add this address to BUBBLES_FRONTEND_ORIGINS in backend/.env and restart the backend."
    : "Please open Bubbles at https://heybubbles.in instead.";
  return `Bubbles' server is running, but it is refusing requests from this page (${address}). ${fix}`;
}

/** The migration that permanently fixes compatibility mode (applied once, by the database owner). */
export const COMPAT_FIX_FILE = "supabase/migrations/20261006_coco_service_role_grants.sql";

function record(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : null;
}

function tidy(text: string, max = 200): string {
  const flat = text.replace(/\s+/g, " ").trim();
  return flat.length > max ? `${flat.slice(0, max - 1).trimEnd()}…` : flat;
}

/** FastAPI `detail`: a string, a list of {loc, msg}, or an object with a message. Empty string when absent. */
function detailText(body: unknown): string {
  const detail = record(body)?.detail;
  if (typeof detail === "string") return tidy(detail);
  if (Array.isArray(detail)) {
    const parts = detail.flatMap((item) => {
      if (typeof item === "string") return [item];
      const entry = record(item);
      if (!entry || typeof entry.msg !== "string") return [];
      const where = Array.isArray(entry.loc) ? entry.loc[entry.loc.length - 1] : undefined;
      return [typeof where === "string" && where !== "body" ? `${where}: ${entry.msg}` : entry.msg];
    });
    return tidy(parts.join("; "));
  }
  const nested = record(detail);
  const text = nested?.message ?? nested?.msg;
  return typeof text === "string" ? tidy(text) : "";
}

const DB_DENIED_CODES = new Set(["database_permission_denied", "42501"]);

function isDatabasePermission(body: unknown): boolean {
  const rec = record(body);
  if (!rec) return false;
  const nested = record(rec.detail);
  if ([rec.code, nested?.code].some((c) => typeof c === "string" && DB_DENIED_CODES.has(c))) return true;
  return /\b42501\b|permission denied for (?:table|schema)/i.test(typeof rec.detail === "string" ? rec.detail : "");
}

function failure(kind: FailureKind, message: string, retryable: boolean, blocking = false): Failure {
  return { kind, message, retryable, blocking };
}

export function classifyFailure(input?: FailureInput | null): Failure {
  const i = record(input) ?? {};
  const status = typeof i.status === "number" && Number.isFinite(i.status) ? Math.trunc(i.status) : undefined;

  if (status !== undefined && status > 0) {
    if (status >= 200 && status < 300) return failure("ok", "", false);
    if (isDatabasePermission(i.body)) return failure("database_permission", MESSAGES.database, false);
    if (status === 401 || status === 403) return failure("auth_expired", MESSAGES.auth, false, true);
    if (status === 404 || status === 410) return failure("not_found", MESSAGES.notFound, false);
    if (status === 408) return failure("timeout", MESSAGES.timeout, true);
    if (status === 429) return failure("server_error", MESSAGES.rateLimited, true);
    if (status >= 400 && status < 500) return failure("validation", detailText(i.body) || MESSAGES.validation, false);
    // 5xx and anything unexpected: never echo the server's own text, it can carry internals.
    return failure("server_error", MESSAGES.server, true);
  }

  // No usable HTTP status: status 0 is how some stacks report a failed network call.
  if (i.timedOut === true) return failure("timeout", MESSAGES.timeout, true);
  if (i.networkError === true || status === 0) {
    const refused = typeof i.corsOrigin === "string" && i.corsOrigin !== "" && status !== 0;
    return failure("backend_offline", refused ? corsBlockedMessage(i.corsOrigin as string) : MESSAGES.offline, true, true);
  }
  return failure("server_error", MESSAGES.unknown, true);
}

/** Read what fetchBubbles attached to the error it threw (`timedOut` / `networkError`). Unknown errors stay unknown. */
export function failureFromError(error: unknown): FailureInput {
  const e = record(error);
  if (!e) return {};
  if (e.timedOut === true || e.name === "AbortError" || e.name === "TimeoutError") return { timedOut: true };
  if (e.networkError === true) {
    return typeof e.corsOrigin === "string" && e.corsOrigin ? { networkError: true, corsOrigin: e.corsOrigin } : { networkError: true };
  }
  return {};
}

/** Message for a failed save. Never claims the entry was saved, and says the typed entry is still on screen. */
export function saveFailureMessage(f: Failure): string {
  if (f.kind === "ok") return "";
  if (f.kind === "auth_expired") return f.message;
  if (f.kind === "database_permission") return `${MESSAGES.databaseSave} ${MESSAGES.kept}`;
  return `${f.message} ${MESSAGES.kept}`;
}

/* ── /health ─────────────────────────────────────────────────────────── */

export type DatabaseStatus = "ok" | "permission_denied" | "unreachable" | "unknown";

export type HealthPayload = {
  status: string;
  version: string | null;
  timestamp: string | null;
  services: { api: string; database: DatabaseStatus };
  compat_mode: boolean;
  denied_tables: string[];
};

const DB_STATUSES = new Set<string>(["ok", "permission_denied", "unreachable", "unknown"]);

/** Tolerant parse of GET /health. Older backends omit the new fields; anything that is not a Bubbles payload is null. */
export function parseHealth(raw: unknown): HealthPayload | null {
  const r = record(raw);
  if (!r || typeof r.status !== "string") return null;
  const services = record(r.services);
  const db = services?.database;
  const database: DatabaseStatus = typeof db === "string" && DB_STATUSES.has(db) ? (db as DatabaseStatus) : "unknown";
  const denied = Array.isArray(r.denied_tables)
    ? Array.from(new Set(r.denied_tables.filter((t): t is string => typeof t === "string" && t.length > 0))).slice(0, 50)
    : [];
  return {
    status: r.status,
    version: typeof r.version === "string" ? r.version : null,
    timestamp: typeof r.timestamp === "string" ? r.timestamp : null,
    services: { api: typeof services?.api === "string" ? services.api : "unknown", database },
    compat_mode: r.compat_mode === true || database === "permission_denied" || denied.length > 0,
    denied_tables: denied,
  };
}

export function databaseStatusOf(health: HealthPayload | null): DatabaseStatus {
  if (!health) return "unknown";
  return health.compat_mode ? "permission_denied" : health.services.database;
}

/* ── Reconnect ───────────────────────────────────────────────────────── */

export const RECONNECT_FIRST_MS = 4000;
export const RECONNECT_MAX_MS = 15000;

/** Wait before reconnect attempt `attempt` (0-based): 4s, 6s, 9s, 13.5s, then 15s. */
export function reconnectDelay(attempt: number): number {
  const n = Number.isFinite(attempt) ? Math.max(0, Math.floor(attempt)) : 0;
  return Math.min(RECONNECT_MAX_MS, Math.round(RECONNECT_FIRST_MS * 1.5 ** n));
}

export type ReconnectLoop = { start: () => void; visibilityChanged: () => void; stop: () => void };

/**
 * The offline reconnect poller, free of React so its timing is tested. `start` waits the first delay, then probes;
 * a failed probe schedules the next (backing off); a successful one ends the loop (the caller sees the app go
 * online and calls `stop`). While the tab is hidden nothing is scheduled; coming back probes at once.
 */
export function createReconnectLoop(deps: {
  /** Resolves true when the server answered (any HTTP status), false when it did not. */
  probe: () => Promise<boolean>;
  isHidden: () => boolean;
  /** Epoch ms of the scheduled attempt, or null when none is scheduled. */
  onNextAttempt: (at: number | null) => void;
  onProbing: (probing: boolean) => void;
  now?: () => number;
}): ReconnectLoop {
  const now = deps.now ?? Date.now;
  let timer: ReturnType<typeof setTimeout> | undefined;
  let attempt = 0;
  let busy = false;
  let stopped = false;

  const clear = () => {
    clearTimeout(timer);
    timer = undefined;
  };
  const schedule = () => {
    if (stopped) return;
    if (deps.isHidden()) {
      deps.onNextAttempt(null);
      return;
    }
    const delay = reconnectDelay(attempt);
    attempt += 1;
    deps.onNextAttempt(now() + delay);
    timer = setTimeout(() => void poll(), delay);
  };
  const poll = async () => {
    clear();
    if (busy || stopped) return;
    busy = true;
    deps.onProbing(true);
    let online = false;
    try {
      online = await deps.probe();
    } catch {
      online = false;
    }
    busy = false;
    if (stopped) return;
    deps.onProbing(false);
    if (!online) schedule();
  };

  return {
    start: schedule,
    visibilityChanged() {
      if (stopped) return;
      clear();
      if (deps.isHidden()) {
        deps.onNextAttempt(null);
      } else {
        attempt = 0;
        void poll();
      }
    },
    stop() {
      stopped = true;
      clear();
    },
  };
}

/** After a timeout the server may still be working on the request, so only reads may be sent again. */
export function mayReplayAfterTimeout(method?: string): boolean {
  return ["GET", "HEAD", "OPTIONS"].includes((method ?? "GET").toUpperCase());
}

export function reconnectStatus(nextRetryAt: number | null, now: number, retrying: boolean): string {
  if (retrying) return "Checking now…";
  if (nextRetryAt === null) return "Reconnecting…";
  return `Trying again in ${Math.max(1, Math.ceil((nextRetryAt - now) / 1000))}s`;
}

/* ── Banner ──────────────────────────────────────────────────────────── */

export type Banner =
  | { kind: "offline"; title: string; message: string; dismissible: false }
  | { kind: "waking"; title: string; message: string; dismissible: false }
  | { kind: "compat" | "database_down"; title: string; message: string; dismissible: true }
  | null;

/** What the global alert shows. Offline outranks everything; healthy shows nothing. */
export function connectionBanner(state: {
  apiStatus: "checking" | "online" | "offline";
  connectionError: string | null;
  health: HealthPayload | null;
  /** The first /health is taking long: a free host is starting up. Not a failure. */
  waking?: boolean;
}): Banner {
  if (state.apiStatus === "checking" && state.waking) {
    return { kind: "waking", title: "Bubbles is waking up", message: "This can take up to a minute the first time. Hang tight, it will load by itself.", dismissible: false };
  }
  if (state.apiStatus === "offline") {
    return { kind: "offline", title: "Can't connect to Bubbles", message: state.connectionError || MESSAGES.offline, dismissible: false };
  }
  if (state.apiStatus !== "online") return null;
  const db = databaseStatusOf(state.health);
  if (db === "permission_denied") {
    return {
      kind: "compat",
      title: "Bubbles is in compatibility mode",
      message: "The database needs a one-time permission update. Your entries are still being saved. Settings has the one-step fix.",
      dismissible: true,
    };
  }
  if (db === "unreachable") {
    return { kind: "database_down", title: "Bubbles' database isn't answering", message: MESSAGES.databaseDown, dismissible: true };
  }
  return null;
}

/** Pill text for Settings. */
export function databaseSummary(status: DatabaseStatus): { label: string; tone: "good" | "warn" | "bad" | "idle" } {
  switch (status) {
    case "ok":
      return { label: "Working", tone: "good" };
    case "permission_denied":
      return { label: "Compatibility mode", tone: "warn" };
    case "unreachable":
      return { label: "Not answering", tone: "bad" };
    default:
      return { label: "Not checked yet", tone: "idle" };
  }
}
