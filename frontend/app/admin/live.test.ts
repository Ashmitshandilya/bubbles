import { describe, expect, it } from "vitest";
import { NO_FILTERS, chainOffsets, filterChoices, filterRows, groupLive, isError, stageWords, toCsv } from "./live";
import type { OpsEvent } from "./format";

const ev = (seq: number, kind: OpsEvent["kind"], data: Record<string, unknown>, extra: Partial<OpsEvent> = {}): OpsEvent =>
  ({ seq, at: `2026-10-16T09:00:0${seq}Z`, kind, request_id: "rq000001", data, ...extra });

const chat = [
  ev(1, "ai_attempt", { provider: "Groq", model: "m1", position: 1, outcome: "timeout", error_category: "timeout" }, { uid: "11111111-aaaa" }),
  ev(2, "ai_attempt", { provider: "Gemini", model: "g", position: 2, outcome: "success" }),
  ev(3, "ai_reply", { provider: "Gemini", model: "g", outcome: "answered", fallback_used: true }),
  ev(4, "api", { method: "POST", route: "/chat", status: 200, latency_ms: 900, stage_pre_ms: 12, stage_ai_ms: 700 }, { uid: "11111111-aaaa" }),
];

describe("live rows", () => {
  it("joins one request into one row with provider, uid, stages and fallback", () => {
    const [row] = groupLive(chat);
    expect(row).toMatchObject({ uid: "11111111-aaaa", route: "/chat", status: 200, provider: "Gemini", model: "g", tries: 2, fallback: true });
    expect(row.stages).toEqual({ pre: 12, ai: 700 });
    expect(isError(row)).toBe(true);
  });

  it("returns nothing for nothing, and newest request first", () => {
    expect(groupLive([])).toEqual([]);
    const rows = groupLive([ev(1, "api", { route: "/a", status: 200 }, { request_id: "a" }), ev(5, "api", { route: "/b", status: 200 }, { request_id: "b" })]);
    expect(rows.map((r) => r.route)).toEqual(["/b", "/a"]);
  });

  it("ignores stage values that are not finite numbers and survives rows with no data or no request id", () => {
    const bad = [
      ev(1, "api", { route: "/chat", status: 200, stage_pre_ms: "slow", stage_ai_ms: Number.NaN, stage_ctx_ms: null }, { request_id: "x" }),
      { seq: 2, at: "2026-10-16T09:00:02Z", kind: "api", request_id: null } as unknown as OpsEvent,
      ev(3, "error", { category: "database", route: "/health" }, { request_id: null }),
    ];
    const rows = groupLive(bad);
    expect(rows).toHaveLength(3);
    expect(rows.find((r) => r.route === "/chat")?.stages).toEqual({});
    expect(rows.find((r) => r.kind === "error")?.error).toBe("database");
  });

  it("does not invent a uid for events that have none", () => {
    const [row] = groupLive([ev(1, "ai_reply", { outcome: "answered" }), ev(2, "api", { route: "/chat", status: 200 })]);
    expect(row.uid).toBeNull();
  });
});

describe("live filters", () => {
  const rows = groupLive([
    ...chat,
    ev(5, "api", { method: "GET", route: "/health/{slug}", status: 500 }, { request_id: "r2" }),
    ev(6, "api", { method: "GET", route: "/insights", status: 200 }, { request_id: "r3" }),
  ]);
  it("filters by status, provider, route and errors only, and no filter keeps everything", () => {
    expect(filterRows(rows, NO_FILTERS)).toHaveLength(3);
    expect(filterRows(rows, { ...NO_FILTERS, status: "5xx" })).toHaveLength(1);
    expect(filterRows(rows, { ...NO_FILTERS, provider: "Gemini" })).toHaveLength(1);
    expect(filterRows(rows, { ...NO_FILTERS, provider: "Nobody" })).toEqual([]);
    expect(filterRows(rows, { ...NO_FILTERS, errorsOnly: true })).toHaveLength(2);
    expect(filterChoices(rows).providers).toEqual(["Gemini"]);
  });
});

describe("words and csv", () => {
  it("names measured stages only", () => {
    expect(stageWords({}, String)).toBeNull();
    expect(stageWords({ ai: 5, pre: 1 }, (n) => `${n}ms`)).toBe("pre 1ms, ai 5ms");
  });
  it("offsets a chain from its first event and never goes negative", () => {
    const [row] = groupLive(chat);
    expect(chainOffsets(row).every((o) => o.offsetMs >= 0)).toBe(true);
  });
  it("quotes cells and defuses spreadsheet formulas", () => {
    const csv = toCsv(["a", "b"], [["=HYPERLINK(\"x\")", "has,comma"], ["+1", "-2"], ["@cmd", 5], [null, undefined], ["line\nbreak", "say \"hi\""]]);
    expect(csv).toContain("'=HYPERLINK");
    expect(csv).toContain('"has,comma"');
    expect(csv).toContain("'+1,'-2");
    expect(csv).toContain("'@cmd,5");
    expect(csv).toContain('"line\nbreak","say ""hi"""');
    expect(toCsv(["h"], [])).toBe("h\r\n");
    expect(toCsv(["n"], [[-5]])).toContain("-5");   // a real negative number stays a number
  });
});
