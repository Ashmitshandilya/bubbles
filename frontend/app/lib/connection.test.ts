import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  COMPAT_FIX_FILE,
  MESSAGES,
  RECONNECT_MAX_MS,
  classifyFailure,
  corsBlockedMessage,
  connectionBanner,
  createReconnectLoop,
  databaseStatusOf,
  databaseSummary,
  failureFromError,
  mayReplayAfterTimeout,
  parseHealth,
  probeRetryDelay,
  reconnectDelay,
  reconnectStatus,
  saveFailureMessage,
  shareInFlight,
  type FailureKind,
  type HealthPayload,
} from "./connection";

const KINDS: FailureKind[] = [
  "backend_offline", "timeout", "database_permission", "auth_expired", "validation", "server_error", "not_found", "ok",
];

describe("classifyFailure: every kind", () => {
  it("backend_offline: a network error with no response", () => {
    expect(classifyFailure({ networkError: true })).toEqual({
      kind: "backend_offline",
      message: "Bubbles can't reach its server right now. It may be waking up, which can take up to a minute. This page will reconnect by itself.",
      retryable: true,
      blocking: true,
    });
  });

  it("timeout: timedOut, and HTTP 408", () => {
    for (const input of [{ timedOut: true }, { status: 408 }]) {
      const f = classifyFailure(input);
      expect(f).toMatchObject({ kind: "timeout", retryable: true, blocking: false });
      expect(f.message).toBe(MESSAGES.timeout);
    }
  });

  it("database_permission: HTTP 503 with the contract code", () => {
    const f = classifyFailure({ status: 503, body: { detail: "permission denied", code: "database_permission_denied", table: "sleep_logs" } });
    expect(f).toEqual({
      kind: "database_permission",
      message: "Bubbles is running, but the database needs a one-time permission update. Your entries are still being saved in compatibility mode.",
      retryable: false,
      blocking: false,
    });
  });

  it("auth_expired: 401 and 403", () => {
    for (const status of [401, 403]) {
      expect(classifyFailure({ status })).toEqual({ kind: "auth_expired", message: "Your session expired. Please sign in again.", retryable: false, blocking: true });
    }
  });

  it("validation: 4xx with a string detail, a FastAPI list, and no body", () => {
    expect(classifyFailure({ status: 422, body: { detail: "Sleep hours must be between 0 and 24" } })).toMatchObject({
      kind: "validation", message: "Sleep hours must be between 0 and 24", retryable: false, blocking: false,
    });
    const list = { detail: [{ loc: ["body", "weight_kg"], msg: "ensure this value is less than 500", type: "x" }, { loc: ["body"], msg: "field required" }] };
    expect(classifyFailure({ status: 422, body: list }).message).toBe("weight_kg: ensure this value is less than 500; field required");
    expect(classifyFailure({ status: 400 }).message).toBe(MESSAGES.validation);
    expect(classifyFailure({ status: 409, body: { detail: "Chat idempotency key was already used" } }).kind).toBe("validation");
  });

  it("server_error: 5xx, rate limiting, and unknown failures", () => {
    for (const status of [500, 502, 503, 504]) {
      expect(classifyFailure({ status })).toMatchObject({ kind: "server_error", retryable: true, blocking: false, message: MESSAGES.server });
    }
    expect(classifyFailure({ status: 429 })).toMatchObject({ kind: "server_error", retryable: true, message: MESSAGES.rateLimited });
    expect(classifyFailure({})).toMatchObject({ kind: "server_error", message: MESSAGES.unknown });
  });

  it("not_found: 404 and 410", () => {
    for (const status of [404, 410]) {
      expect(classifyFailure({ status })).toMatchObject({ kind: "not_found", retryable: false, blocking: false, message: MESSAGES.notFound });
    }
  });

  it("ok: any 2xx", () => {
    for (const status of [200, 201, 204, 299]) {
      expect(classifyFailure({ status })).toEqual({ kind: "ok", message: "", retryable: false, blocking: false });
    }
  });

  it("every kind is reachable and always carries a boolean pair", () => {
    const seen = new Set(
      [
        { networkError: true }, { timedOut: true }, { status: 503, body: { code: "database_permission_denied" } }, { status: 401 },
        { status: 422 }, { status: 500 }, { status: 404 }, { status: 200 },
      ].map((input) => classifyFailure(input).kind),
    );
    expect([...seen].sort()).toEqual([...KINDS].sort());
  });
});

describe("classifyFailure: precedence and edge cases", () => {
  it("a real HTTP status beats the network flags (a response means the server is up)", () => {
    expect(classifyFailure({ status: 500, networkError: true }).kind).toBe("server_error");
    expect(classifyFailure({ status: 404, timedOut: true }).kind).toBe("not_found");
  });

  it("timedOut beats networkError, so a hung server is not reported as stopped", () => {
    expect(classifyFailure({ timedOut: true, networkError: true }).kind).toBe("timeout");
  });

  it("the database-permission code wins on any failing status, including 500, 403 and 400", () => {
    for (const status of [400, 403, 500, 503]) {
      expect(classifyFailure({ status, body: { code: "database_permission_denied" } }).kind).toBe("database_permission");
    }
  });

  it("recognises a leaked Postgres 42501 and a nested code", () => {
    expect(classifyFailure({ status: 500, body: { code: "42501" } }).kind).toBe("database_permission");
    expect(classifyFailure({ status: 500, body: { detail: "permission denied for table profiles (42501)" } }).kind).toBe("database_permission");
    expect(classifyFailure({ status: 503, body: { detail: { code: "database_permission_denied" } } }).kind).toBe("database_permission");
  });

  it("a plain 503 without the code is a server error, never a database-permission claim", () => {
    expect(classifyFailure({ status: 503, body: { detail: "Service Unavailable" } }).kind).toBe("server_error");
  });

  it("a successful status is ok even if the body mentions the code", () => {
    expect(classifyFailure({ status: 200, body: { code: "database_permission_denied" } }).kind).toBe("ok");
  });

  it("status 0 (failed network call in some stacks) is offline", () => {
    expect(classifyFailure({ status: 0 }).kind).toBe("backend_offline");
    expect(classifyFailure({ status: 0, timedOut: true }).kind).toBe("timeout");
  });

  it("never echoes server text on 5xx (it can carry internals)", () => {
    const f = classifyFailure({ status: 500, body: { detail: "psycopg2 OperationalError at 10.0.0.5 password=hunter2" } });
    expect(f.message).toBe(MESSAGES.server);
    expect(f.message).not.toMatch(/hunter2|psycopg2|10\.0\.0\.5/);
  });

  it("caps and flattens a very long or multi-line 4xx detail", () => {
    const f = classifyFailure({ status: 422, body: { detail: `line one\n\n   line two ${"x".repeat(500)}` } });
    expect(f.message.length).toBeLessThanOrEqual(200);
    expect(f.message.startsWith("line one line two")).toBe(true);
    expect(f.message.endsWith("…")).toBe(true);
  });

  it("uses a nested detail message and skips malformed list items", () => {
    expect(classifyFailure({ status: 400, body: { detail: { message: "Pick a date in the past" } } }).message).toBe("Pick a date in the past");
    const messy = { detail: [null, 7, { msg: 5 }, "plain text", { loc: [], msg: "no location" }] };
    expect(classifyFailure({ status: 422, body: messy }).message).toBe("plain text; no location");
  });

  it("malformed inputs never throw and never return ok", () => {
    const inputs: unknown[] = [
      undefined, null, 0, 1, "503", true, [], [503], {}, { status: "503" }, { status: Number.NaN }, { status: Infinity }, { status: -1 },
      { status: 503.9, body: "text" }, { status: 500, body: null }, { status: 422, body: [1, 2] }, { status: 422, body: 12 },
      { networkError: "yes" }, { timedOut: 1 }, { status: 99 }, { status: 302 },
    ];
    for (const input of inputs) {
      const f = classifyFailure(input as never);
      expect(KINDS).toContain(f.kind);
      expect(typeof f.message).toBe("string");
      expect(typeof f.retryable).toBe("boolean");
      expect(typeof f.blocking).toBe("boolean");
      if (f.kind !== "ok") expect(f.message.length).toBeGreaterThan(0);
    }
    expect(classifyFailure(undefined).kind).toBe("server_error");
    expect(classifyFailure({ status: "503" } as never).kind).toBe("server_error");
    expect(classifyFailure({ status: 503.9 }).kind).toBe("server_error");
  });

  it("non-boolean flags do not count as true", () => {
    expect(classifyFailure({ networkError: "yes" as never }).kind).toBe("server_error");
    expect(classifyFailure({ timedOut: 1 as never }).kind).toBe("server_error");
  });
});

describe("failureFromError", () => {
  it("reads the flags fetchBubbles attaches", () => {
    expect(failureFromError(Object.assign(new Error("x"), { timedOut: true }))).toEqual({ timedOut: true });
    expect(failureFromError(Object.assign(new Error("x"), { timedOut: false, networkError: true }))).toEqual({ networkError: true });
  });

  it("treats an AbortError as a timeout", () => {
    const abort = Object.assign(new Error("aborted"), { name: "AbortError" });
    expect(failureFromError(abort)).toEqual({ timedOut: true });
  });

  it("leaves unknown errors unknown (a parse or render bug is not an outage)", () => {
    expect(failureFromError(new SyntaxError("Unexpected token <"))).toEqual({});
    expect(classifyFailure(failureFromError(new SyntaxError("x"))).kind).toBe("server_error");
    for (const e of [undefined, null, "boom", 42, []]) expect(failureFromError(e)).toEqual({});
  });
});

describe("saveFailureMessage", () => {
  it("tells the user the entry is still there and never claims it was saved", () => {
    for (const input of [{ networkError: true }, { timedOut: true }, { status: 500 }, { status: 422, body: { detail: "Too heavy" } }]) {
      const text = saveFailureMessage(classifyFailure(input));
      expect(text).toContain(MESSAGES.kept);
      expect(text.toLowerCase()).not.toMatch(/\bwas saved\b|saved successfully/);
    }
  });

  it("database permission on a save says it could not be saved yet (not 'still being saved')", () => {
    const text = saveFailureMessage(classifyFailure({ status: 503, body: { code: "database_permission_denied" } }));
    expect(text).toContain("couldn't be saved yet");
    expect(text).toContain("one-time permission update");
    expect(text).not.toContain("still being saved");
    expect(text).toContain(MESSAGES.kept);
  });

  it("an expired session is not told 'your entry is still here' (signing in leaves the page)", () => {
    expect(saveFailureMessage(classifyFailure({ status: 401 }))).toBe(MESSAGES.auth);
  });

  it("is empty for ok", () => {
    expect(saveFailureMessage(classifyFailure({ status: 201 }))).toBe("");
  });
});

describe("parseHealth", () => {
  const full = {
    status: "healthy",
    version: "0.1.0",
    timestamp: "2026-10-07T10:00:00+00:00",
    services: { api: "healthy", database: "permission_denied" },
    compat_mode: true,
    denied_tables: ["profiles", "sleep_logs", "profiles"],
  };

  it("parses the new payload and de-duplicates denied tables", () => {
    expect(parseHealth(full)).toEqual({ ...full, denied_tables: ["profiles", "sleep_logs"] });
  });

  it("parses a healthy payload", () => {
    const h = parseHealth({ ...full, services: { api: "healthy", database: "ok" }, compat_mode: false, denied_tables: [] }) as HealthPayload;
    expect(h.compat_mode).toBe(false);
    expect(databaseStatusOf(h)).toBe("ok");
  });

  it("accepts the older backend shape (no compat fields, database unknown)", () => {
    const h = parseHealth({ status: "healthy", version: "0.1.0", timestamp: "t", services: { api: "healthy", database: "unknown" } }) as HealthPayload;
    expect(h.compat_mode).toBe(false);
    expect(h.denied_tables).toEqual([]);
    expect(databaseStatusOf(h)).toBe("unknown");
  });

  it("derives compatibility mode from the database state or the denied list even if the flag is missing", () => {
    expect(parseHealth({ status: "healthy", services: { database: "permission_denied" } })?.compat_mode).toBe(true);
    expect(parseHealth({ status: "healthy", denied_tables: ["profiles"] })?.compat_mode).toBe(true);
    expect(databaseStatusOf(parseHealth({ status: "healthy", denied_tables: ["profiles"] }))).toBe("permission_denied");
  });

  it("normalises junk: unknown database value, non-string tables, wrong types", () => {
    const h = parseHealth({ status: "healthy", version: 7, timestamp: {}, services: { api: 1, database: "exploded" }, denied_tables: ["a", 3, "", null, "b"] }) as HealthPayload;
    expect(h.version).toBeNull();
    expect(h.timestamp).toBeNull();
    expect(h.services).toEqual({ api: "unknown", database: "unknown" });
    expect(h.denied_tables).toEqual(["a", "b"]);
    expect(parseHealth({ status: "healthy", denied_tables: "profiles" })?.denied_tables).toEqual([]);
  });

  it("caps the denied list", () => {
    const many = Array.from({ length: 200 }, (_, i) => `t${i}`);
    expect(parseHealth({ status: "healthy", denied_tables: many })?.denied_tables).toHaveLength(50);
  });

  it("returns null for anything that is not a Bubbles health payload", () => {
    for (const raw of [undefined, null, "ok", 200, [], {}, { status: 1 }, { services: {} }, [{ status: "healthy" }]]) {
      expect(parseHealth(raw)).toBeNull();
    }
  });

  it("database status is unknown without a payload", () => {
    expect(databaseStatusOf(null)).toBe("unknown");
  });
});

describe("probeRetryDelay: a waking host is not an outage", () => {
  const base = { elapsedMs: 0, canRetry: true };
  const refused = { networkError: true };

  it("retries a fast refusal for the whole wake window, then gives up", () => {
    expect(probeRetryDelay(refused, { ...base, elapsedMs: 5000 })).toBe(1500);
    expect(probeRetryDelay(refused, { ...base, elapsedMs: 64999 })).toBe(1500);
    expect(probeRetryDelay(refused, { ...base, elapsedMs: 65000 })).toBeNull();
  });

  it("never retries a timeout (the caller handles slow hosts) or a failure with no network cause", () => {
    expect(probeRetryDelay({ timedOut: true }, base)).toBeNull();
    expect(probeRetryDelay({}, base)).toBeNull();
  });

  it("does not retry when the browser is offline or no usable address exists", () => {
    expect(probeRetryDelay(refused, { ...base, canRetry: false })).toBeNull();
  });
});

describe("reconnect timing", () => {
  it("starts at 4s and backs off to a 15s ceiling", () => {
    expect([0, 1, 2, 3, 4, 5, 6].map(reconnectDelay)).toEqual([4000, 6000, 9000, 13500, 15000, 15000, 15000]);
  });

  it("is monotonic and never exceeds the ceiling, even for absurd or malformed attempts", () => {
    let last = 0;
    for (let i = 0; i < 40; i += 1) {
      const d = reconnectDelay(i);
      expect(d).toBeGreaterThanOrEqual(last);
      expect(d).toBeLessThanOrEqual(RECONNECT_MAX_MS);
      last = d;
    }
    for (const bad of [-5, Number.NaN, Infinity, -Infinity, 1e9, 2.9]) {
      const d = reconnectDelay(bad);
      expect(d).toBeGreaterThanOrEqual(4000);
      expect(d).toBeLessThanOrEqual(RECONNECT_MAX_MS);
    }
    expect(reconnectDelay(2.9)).toBe(9000);
  });

  it("only reads may be replayed after a timeout, so a save is never duplicated", () => {
    expect(mayReplayAfterTimeout()).toBe(true);
    expect(mayReplayAfterTimeout("get")).toBe(true);
    expect(mayReplayAfterTimeout("HEAD")).toBe(true);
    for (const method of ["POST", "post", "PATCH", "PUT", "DELETE"]) expect(mayReplayAfterTimeout(method)).toBe(false);
  });

  it("describes the countdown", () => {
    expect(reconnectStatus(10_000, 4_000, false)).toBe("Trying again in 6s");
    expect(reconnectStatus(10_001, 4_000, false)).toBe("Trying again in 7s");
    expect(reconnectStatus(10_000, 10_000, false)).toBe("Trying again in 1s");
    expect(reconnectStatus(10_000, 99_000, false)).toBe("Trying again in 1s");
    expect(reconnectStatus(10_000, 4_000, true)).toBe("Checking now…");
    expect(reconnectStatus(null, 0, false)).toBe("Reconnecting…");
    expect(reconnectStatus(null, 0, true)).toBe("Checking now…");
  });
});

describe("connectionBanner", () => {
  const healthy = parseHealth({ status: "healthy", services: { api: "healthy", database: "ok" }, compat_mode: false, denied_tables: [] });
  const compat = parseHealth({ status: "healthy", services: { api: "healthy", database: "permission_denied" }, compat_mode: true, denied_tables: ["profiles"] });
  const dbDown = parseHealth({ status: "healthy", services: { api: "healthy", database: "unreachable" }, compat_mode: false, denied_tables: [] });

  it("offline is a blocking banner using the classifier text, and outranks compat mode", () => {
    const b = connectionBanner({ apiStatus: "offline", connectionError: MESSAGES.offline, health: compat });
    expect(b).toMatchObject({ kind: "offline", dismissible: false, message: MESSAGES.offline });
    expect(connectionBanner({ apiStatus: "offline", connectionError: null, health: null })?.message).toBe(MESSAGES.offline);
  });

  it("compat mode is a dismissible info banner that points to Settings", () => {
    const b = connectionBanner({ apiStatus: "online", connectionError: null, health: compat });
    expect(b).toMatchObject({ kind: "compat", dismissible: true });
    expect(b?.message).toMatch(/Settings/);
  });

  it("an unreachable database is a dismissible notice", () => {
    expect(connectionBanner({ apiStatus: "online", connectionError: null, health: dbDown })).toMatchObject({ kind: "database_down", dismissible: true });
  });

  it("shows nothing when healthy, unknown, or still checking", () => {
    expect(connectionBanner({ apiStatus: "online", connectionError: null, health: healthy })).toBeNull();
    expect(connectionBanner({ apiStatus: "online", connectionError: null, health: null })).toBeNull();
    expect(connectionBanner({ apiStatus: "checking", connectionError: null, health: compat })).toBeNull();
  });

  it("a slow first answer shows a friendly waking-up notice, not the offline banner", () => {
    expect(connectionBanner({ apiStatus: "checking", connectionError: null, health: null, waking: true })).toMatchObject({ kind: "waking", dismissible: false });
    expect(connectionBanner({ apiStatus: "checking", connectionError: null, health: null, waking: false })).toBeNull();
    expect(connectionBanner({ apiStatus: "offline", connectionError: null, health: null, waking: true })?.kind).toBe("offline");
  });

  it("a stale connection error never shows a banner while online and healthy", () => {
    expect(connectionBanner({ apiStatus: "online", connectionError: "old failure", health: healthy })).toBeNull();
  });
});

describe("databaseSummary and the fix file", () => {
  it("labels every status", () => {
    expect(databaseSummary("ok")).toEqual({ label: "Working", tone: "good" });
    expect(databaseSummary("permission_denied")).toEqual({ label: "Compatibility mode", tone: "warn" });
    expect(databaseSummary("unreachable")).toEqual({ label: "Not answering", tone: "bad" });
    expect(databaseSummary("unknown")).toEqual({ label: "Not checked yet", tone: "idle" });
  });

  it("names the migration the owner applies", () => {
    expect(COMPAT_FIX_FILE).toBe("supabase/migrations/20261006_coco_service_role_grants.sql");
  });
});

describe("createReconnectLoop", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(1_000_000);
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  function setup(answers: boolean[], hidden = { value: false }) {
    const probe = vi.fn(async () => (answers.length > 1 ? (answers.shift() as boolean) : answers[0]));
    const next: Array<number | null> = [];
    const probing: boolean[] = [];
    const loop = createReconnectLoop({
      probe,
      isHidden: () => hidden.value,
      onNextAttempt: (at) => next.push(at),
      onProbing: (p) => probing.push(p),
    });
    return { loop, probe, next, probing, hidden };
  }

  it("waits 4s, then retries on a 4s, 6s, 9s, 13.5s, 15s cadence while the server stays down", async () => {
    const { loop, probe, next } = setup([false]);
    loop.start();
    expect(next).toEqual([1_004_000]);
    expect(probe).not.toHaveBeenCalled();

    const waits = [4000, 6000, 9000, 13500, 15000, 15000];
    for (const [i, wait] of waits.entries()) {
      await vi.advanceTimersByTimeAsync(wait - 1);
      expect(probe).toHaveBeenCalledTimes(i);
      await vi.advanceTimersByTimeAsync(1);
      expect(probe).toHaveBeenCalledTimes(i + 1);
    }
    // each probe scheduled the next attempt at now + the next delay
    expect(next.slice(1).map((at, i) => (at as number) - (1_000_000 + waits.slice(0, i + 1).reduce((a, b) => a + b, 0)))).toEqual([6000, 9000, 13500, 15000, 15000, 15000]);
    loop.stop();
  });

  it("ends the loop when the server answers, and schedules nothing more", async () => {
    const { loop, probe, probing } = setup([false, true]);
    loop.start();
    await vi.advanceTimersByTimeAsync(4000); // probe 1: down
    await vi.advanceTimersByTimeAsync(6000); // probe 2: up
    expect(probe).toHaveBeenCalledTimes(2);
    expect(probing).toEqual([true, false, true, false]);
    await vi.advanceTimersByTimeAsync(60_000);
    expect(probe).toHaveBeenCalledTimes(2);
    expect(vi.getTimerCount()).toBe(0);
  });

  it("a probe that throws counts as down and keeps retrying", async () => {
    const hidden = { value: false };
    const probe = vi.fn().mockRejectedValueOnce(new Error("boom")).mockResolvedValue(true);
    const loop = createReconnectLoop({ probe, isHidden: () => hidden.value, onNextAttempt: () => {}, onProbing: () => {} });
    loop.start();
    await vi.advanceTimersByTimeAsync(4000);
    await vi.advanceTimersByTimeAsync(6000);
    expect(probe).toHaveBeenCalledTimes(2);
  });

  it("does not schedule while the tab is hidden, and probes at once (resetting the backoff) when it returns", async () => {
    const hidden = { value: true };
    const { loop, probe, next } = setup([false], hidden);
    loop.start();
    expect(next).toEqual([null]);
    await vi.advanceTimersByTimeAsync(60_000);
    expect(probe).not.toHaveBeenCalled();

    hidden.value = false;
    loop.visibilityChanged();
    await vi.advanceTimersByTimeAsync(0);
    expect(probe).toHaveBeenCalledTimes(1);
    expect(next.at(-1)).toBe(1_060_000 + 4000); // back to the first delay
    loop.stop();
  });

  it("returning to the tab after backing off starts the cadence over at 4s", async () => {
    const { loop, probe, next, hidden } = setup([false]);
    loop.start();
    await vi.advanceTimersByTimeAsync(4000); // probe 1 -> next in 6s
    await vi.advanceTimersByTimeAsync(6000); // probe 2 -> next in 9s
    expect(probe).toHaveBeenCalledTimes(2);
    expect((next.at(-1) as number) - Date.now()).toBe(9000);
    hidden.value = true;
    loop.visibilityChanged();
    hidden.value = false;
    loop.visibilityChanged();
    await vi.advanceTimersByTimeAsync(0);
    expect(probe).toHaveBeenCalledTimes(3);
    expect((next.at(-1) as number) - Date.now()).toBe(4000);
    loop.stop();
  });

  it("hiding the tab cancels the pending attempt", async () => {
    const { loop, probe, next, hidden } = setup([false]);
    loop.start();
    await vi.advanceTimersByTimeAsync(2000);
    hidden.value = true;
    loop.visibilityChanged();
    expect(next.at(-1)).toBeNull();
    await vi.advanceTimersByTimeAsync(60_000);
    expect(probe).not.toHaveBeenCalled();
    expect(vi.getTimerCount()).toBe(0);
  });

  it("hiding the tab during a probe stops the chain after that probe", async () => {
    const hidden = { value: false };
    let release: (v: boolean) => void = () => {};
    const probe = vi.fn(() => new Promise<boolean>((resolve) => { release = resolve; }));
    const next: Array<number | null> = [];
    const loop = createReconnectLoop({ probe, isHidden: () => hidden.value, onNextAttempt: (at) => next.push(at), onProbing: () => {} });
    loop.start();
    await vi.advanceTimersByTimeAsync(4000);
    expect(probe).toHaveBeenCalledTimes(1);
    hidden.value = true;
    loop.visibilityChanged();
    release(false);
    await vi.advanceTimersByTimeAsync(0);
    expect(next.at(-1)).toBeNull();
    await vi.advanceTimersByTimeAsync(60_000);
    expect(probe).toHaveBeenCalledTimes(1);
  });

  it("never runs two probes at once, even if the tab flickers visible while one is in flight", async () => {
    let release: (v: boolean) => void = () => {};
    const probe = vi.fn(() => new Promise<boolean>((resolve) => { release = resolve; }));
    const loop = createReconnectLoop({ probe, isHidden: () => false, onNextAttempt: () => {}, onProbing: () => {} });
    loop.start();
    await vi.advanceTimersByTimeAsync(4000);
    loop.visibilityChanged();
    loop.visibilityChanged();
    await vi.advanceTimersByTimeAsync(0);
    expect(probe).toHaveBeenCalledTimes(1);
    release(false);
    await vi.advanceTimersByTimeAsync(0);
    loop.stop();
  });

  it("stop() (unmount) cancels the timer and ignores a probe still in flight", async () => {
    let release: (v: boolean) => void = () => {};
    const probe = vi.fn(() => new Promise<boolean>((resolve) => { release = resolve; }));
    const next: Array<number | null> = [];
    const probing: boolean[] = [];
    const loop = createReconnectLoop({ probe, isHidden: () => false, onNextAttempt: (at) => next.push(at), onProbing: (p) => probing.push(p) });
    loop.start();
    loop.stop();
    expect(vi.getTimerCount()).toBe(0);
    await vi.advanceTimersByTimeAsync(60_000);
    expect(probe).not.toHaveBeenCalled();

    const again = createReconnectLoop({ probe, isHidden: () => false, onNextAttempt: (at) => next.push(at), onProbing: (p) => probing.push(p) });
    again.start();
    await vi.advanceTimersByTimeAsync(4000);
    again.stop();
    next.length = 0;
    probing.length = 0;
    release(false);
    await vi.advanceTimersByTimeAsync(0);
    expect(next).toEqual([]); // nothing re-armed after unmount
    expect(probing).toEqual([]); // and no state update after unmount
    expect(vi.getTimerCount()).toBe(0);
    again.visibilityChanged();
    expect(vi.getTimerCount()).toBe(0);
  });
});

describe("a refused origin (CORS) is told apart from a stopped server", () => {
  it("classifyFailure uses the refusal message but keeps the connectivity kind", () => {
    const f = classifyFailure({ networkError: true, corsOrigin: "http://localhost:3001" });
    expect(f).toMatchObject({ kind: "backend_offline", retryable: true, blocking: true });
    expect(f.message).toBe(corsBlockedMessage("http://localhost:3001"));
    expect(f.message).toContain("server is running");
  });

  it("without the flag, or with an empty one, it stays the plain offline message", () => {
    expect(classifyFailure({ networkError: true }).message).toBe(MESSAGES.offline);
    expect(classifyFailure({ networkError: true, corsOrigin: "" }).message).toBe(MESSAGES.offline);
    expect(classifyFailure({ networkError: true, corsOrigin: 5 as never }).message).toBe(MESSAGES.offline);
  });

  it("a timeout or a real HTTP status ignores it", () => {
    expect(classifyFailure({ timedOut: true, corsOrigin: "http://x" }).kind).toBe("timeout");
    expect(classifyFailure({ status: 500, networkError: true, corsOrigin: "http://x" }).message).toBe(MESSAGES.server);
    expect(classifyFailure({ status: 0, corsOrigin: "http://x" }).message).toBe(MESSAGES.offline);
  });

  it("failureFromError carries the origin through fetchBubbles' error", () => {
    const err = Object.assign(new Error("x"), { timedOut: false, networkError: true, corsOrigin: "http://localhost:3001" });
    expect(failureFromError(err)).toEqual({ networkError: true, corsOrigin: "http://localhost:3001" });
    expect(classifyFailure(failureFromError(err)).message).toBe(corsBlockedMessage("http://localhost:3001"));
    expect(failureFromError(Object.assign(new Error("x"), { networkError: true, corsOrigin: undefined }))).toEqual({ networkError: true });
  });
});

describe("corsBlockedMessage", () => {
  it("names the page address, the setting, and the safe address to use", () => {
    const text = corsBlockedMessage("http://localhost:3100");
    expect(text).toContain("http://localhost:3100");
    expect(text).toContain("BUBBLES_FRONTEND_ORIGINS");
    expect(text).toContain("http://localhost:3000");
    expect(text).toContain("server is running");
    expect(text).not.toContain("isn't running");
  });

  it("copes with an empty or enormous origin", () => {
    expect(corsBlockedMessage("")).toContain("this address");
    expect(corsBlockedMessage("x".repeat(1000)).length).toBeLessThan(400);
  });
});


describe("corsBlockedMessage wording", () => {
  it("points a local developer at the backend setting and everyone else at the real site", () => {
    expect(corsBlockedMessage("http://localhost:3001")).toContain("BUBBLES_FRONTEND_ORIGINS");
    const live = corsBlockedMessage("https://bubbles-7x74-hey-bubbles.vercel.app");
    expect(live).toContain("https://heybubbles.in");
    expect(live).not.toContain("BUBBLES_FRONTEND_ORIGINS");
  });

  it("never tells a signed-in person to run a batch file", () => {
    expect(MESSAGES.offline).not.toMatch(/start_bubbles|backend folder/);
  });
});

describe("shareInFlight: many failed calls start one /health probe", () => {
  it("callers that arrive while it runs share one run, and the next call after it settles starts a new one", async () => {
    const slot = { current: null as Promise<boolean> | null };
    let release!: (v: boolean) => void;
    const task = vi.fn(() => new Promise<boolean>((r) => (release = r)));
    const a = shareInFlight(slot, task);
    const b = shareInFlight(slot, task);
    const c = shareInFlight(slot, task);
    expect(task).toHaveBeenCalledTimes(1);
    release(true);
    expect(await Promise.all([a, b, c])).toEqual([true, true, true]);
    expect(slot.current).toBeNull();
    task.mockImplementation(() => Promise.resolve(false));
    expect(await shareInFlight(slot, task)).toBe(false);
    expect(task).toHaveBeenCalledTimes(2);
  });

  it("a failed run is shared too and does not block the next one", async () => {
    const slot = { current: null as Promise<boolean> | null };
    const task = vi.fn((): Promise<boolean> => Promise.reject(new Error("down")));
    const runs = [shareInFlight(slot, task), shareInFlight(slot, task)];
    for (const run of runs) await expect(run).rejects.toThrow("down");
    expect(task).toHaveBeenCalledTimes(1);
    expect(slot.current).toBeNull();
    task.mockImplementation(() => Promise.resolve(true));
    expect(await shareInFlight(slot, task)).toBe(true);
  });
});
