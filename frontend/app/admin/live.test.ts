import { describe, expect, it } from "vitest";
import type { OpsEvent } from "./format";
import { NO_FILTERS, chainOffsets, filterChoices, filterRows, groupLive, isError, stageWords, toCsv } from "./live";

const ev = (seq: number, kind: OpsEvent["kind"], data: Record<string, unknown>, extra: Partial<OpsEvent> = {}): OpsEvent => ({
  seq, at: `2026-10-16T08:00:0${seq}Z`, kind, request_id: "req00001", data, ...extra,
});

const chat = [
  ev(1, "ai_attempt", { provider: "groq", model: "m1", outcome: "rate_limited", error_category: "rate_limit" }, { uid: "u-1" }),
  ev(2, "ai_attempt", { provider: "gemini", model: "m2", outcome: "success" }),
  ev(3, "ai_reply", { provider: "gemini", model: "m2", outcome: "ok", fallback_used: true }),
  ev(4, "api", { method: "POST", route: "/chat", status: 200, latency_ms: 900, stage_pre_ms: 5, stage_ai_ms: 700, safety_level: "GREEN" },
    { feature: "chat" }),
];

describe("live rows", () => {
  it("joins one request into one row with the winning provider, tries and stages", () => {
    const [row] = groupLive(chat);
    expect(row.requestId).toBe("req00001");
    expect(row.uid).toBe("u-1");
    expect([row.provider, row.model, row.tries, row.fallback]).toEqual(["gemini", "m2", 2, true]);
    expect(row.stages).toEqual({ pre: 5, ai: 700 });
    expect([row.status, row.latencyMs, row.feature, row.safety]).toEqual([200, 900, "chat", "GREEN"]);
    expect(row.error).toBe("rate_limit");
  });

  it("gives events without a request id a row each and puts the newest first", () => {
    const loose = [ev(7, "error", { category: "rag", route: "/rag/search" }, { request_id: null }),
      ev(9, "funnel", { step: "signed_up" }, { request_id: null })];
    const rows = groupLive([...chat, ...loose]);
    expect(rows.map((r) => r.seq)).toEqual([9, 7, 4]);
    expect(rows[1].route).toBe("/rag/search");
    expect(isError(rows[1])).toBe(true);
    expect(isError(rows[0])).toBe(false);
  });

  it("marks a degraded reply and a 5xx as errors", () => {
    expect(groupLive([ev(1, "ai_reply", { outcome: "degraded" })])[0].error).toBe("degraded");
    expect(groupLive([ev(1, "api", { status: 503 })])[0].error).toBe("server_error");
  });
});

describe("filters", () => {
  const rows = groupLive([...chat, ev(5, "api", { route: "/profile", status: 404 }, { request_id: "req00002", feature: "profile" })]);

  it("filters by feature, provider, status class and errors", () => {
    expect(filterRows(rows, NO_FILTERS)).toHaveLength(2);
    expect(filterRows(rows, { ...NO_FILTERS, feature: "profile" }).map((r) => r.requestId)).toEqual(["req00002"]);
    expect(filterRows(rows, { ...NO_FILTERS, provider: "gemini" }).map((r) => r.requestId)).toEqual(["req00001"]);
    expect(filterRows(rows, { ...NO_FILTERS, status: "4xx" }).map((r) => r.requestId)).toEqual(["req00002"]);
    expect(filterRows(rows, { ...NO_FILTERS, errorsOnly: true })).toHaveLength(2);
  });

  it("offers only the choices that are on screen", () => {
    expect(filterChoices(rows)).toEqual({ features: ["chat", "profile"], providers: ["gemini"] });
  });
});

describe("wording and export", () => {
  it("lists only measured stages", () => {
    expect(stageWords({ pre: 5, ai: 700 }, (ms) => `${ms} ms`)).toBe("pre 5 ms, ai 700 ms");
    expect(stageWords({}, (ms) => `${ms} ms`)).toBeNull();
  });

  it("quotes cells and defuses spreadsheet formulas", () => {
    expect(toCsv(["a", "b"], [["=SUM(A1)", 'say "hi", ok'], [null, 3]])).toBe('a,b\r\n\'=SUM(A1),"say ""hi"", ok"\r\n,3\r\n');
  });

  it("measures each event from the first one", () => {
    const [row] = groupLive(chat);
    expect(chainOffsets(row).map((o) => o.offsetMs)).toEqual([0, 1000, 2000, 3000]);
  });
});
