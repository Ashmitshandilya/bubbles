import { describe, expect, it } from "vitest";
import {
  NONE, ago, duration, eventSentence, humanize, words, mergeLive, ms, num, parseView, pct, providerTone, sampleNote, viewSearch, type OpsEvent,
} from "./format";

const ev = (kind: OpsEvent["kind"], data: Record<string, unknown>, seq = 1): OpsEvent => ({ seq, at: "2026-10-13T08:00:00Z", kind, request_id: "abcd1234", data });

describe("admin console wording", () => {
  it("shows units and never an em-dash", () => {
    expect(ms(840)).toBe("840 ms");
    expect(ms(2400)).toBe("2.4 s");
    expect(ms(65_000)).toBe("1 min 5 s");
    expect(ms(null)).toBe(NONE);
    expect(pct(0.004)).toBe("0.4%");
    expect(pct(0.94)).toBe("94%");
    expect(pct(0)).toBe("0%");
    expect(pct(null)).toBe(NONE);
    expect(num(12345)).toBe("12,345");
    expect(duration(5400)).toBe("1 h 30 min");
    expect(duration(3600)).toBe("1 h");
    expect(humanize("ai_provider")).toBe("AI provider");
    expect(humanize("ok")).toBe("OK");
    expect(words("AI_PROVIDER")).toBe("AI provider");
    for (const text of [ms(null), pct(undefined), num(null), NONE]) expect(text).not.toContain("—");
  });

  it("says when a sample is too small", () => {
    expect(sampleNote(3, 10)).toBe("Not enough data yet (3 of 10 calls)");
    expect(sampleNote(10, 10)).toBeNull();
  });

  it("reads relative time", () => {
    const now = Date.parse("2026-10-13T08:10:00Z");
    expect(ago("2026-10-13T08:09:50Z", now)).toBe("just now");
    expect(ago("2026-10-13T08:08:00Z", now)).toBe("2 min ago");
    expect(ago(null, now)).toBe(NONE);
  });

  it("keeps the view in the address bar and ignores anything unexpected", () => {
    expect(parseView("?tab=ai&range=24h&request=abcd1234")).toEqual({ tab: "ai", range: "24h", request: "abcd1234" });
    expect(parseView("?tab=drop&range=99y&request=<script>")).toEqual({ tab: "overview", range: "1h", request: null });
    expect(viewSearch({ tab: "overview", range: "1h", request: null })).toBe("");
    expect(viewSearch({ tab: "logs", range: "7d", request: "abcd1234" })).toBe("?tab=logs&range=7d&request=abcd1234");
  });

  it("judges a provider only with enough calls and shows a pause first", () => {
    expect(providerTone({ requests: 3, success_rate: 0 }, false).word).toBe("Too few calls");
    expect(providerTone({ requests: 50, success_rate: 0.95 }, false).tone).toBe("mint");
    expect(providerTone({ requests: 50, success_rate: 0.7 }, false).tone).toBe("sun");
    expect(providerTone({ requests: 50, success_rate: 0.2 }, false).tone).toBe("urgent");
    expect(providerTone({ requests: 50, success_rate: 0.99 }, true).word).toBe("Paused");
  });

  it("turns events into one plain sentence each", () => {
    expect(eventSentence(ev("api", { method: "POST", route: "/chat", status: 200, latency_ms: 1800, route_kind: "emergency", ai_called: false })))
      .toBe("POST /chat 200 in 1.8 s, emergency, no AI used");
    expect(eventSentence(ev("ai_attempt", { provider: "Gemini", outcome: "timeout", latency_ms: 25000, position: 1, error_category: "timeout" })))
      .toBe("Gemini ran out of time in 25.0 s, try 1 (timeout)");
    expect(eventSentence(ev("ai_reply", { outcome: "answered", provider: "Groq", attempts: 2, total_ms: 3400 }))).toBe("Groq answered after 2 tries, 3.4 s");
    expect(eventSentence(ev("api", { method: "POST", route: "/chat", status: 200, latency_ms: 14, route_kind: "ai", ai_called: true })))
      .toBe("POST /chat 200 in 14 ms, AI");
    expect(eventSentence(ev("error", { category: "ai_provider", component: "AI_PROVIDER", error_class: "ProviderError" }))).toBe("AI provider error");
    expect(eventSentence(ev("error", { category: "timeout", component: "RAG", route: "/chat", error_class: "ReadTimeout" })))
      .toBe("Timeout error in RAG on /chat");
    expect(eventSentence(ev("ai_reply", { outcome: "degraded", total_ms: 900 }))).toBe("No AI answer, calm message sent after 900 ms");
    expect(eventSentence(ev("audit", { action: "setting_changed", target: "provider_paused.Groq", old: false, new: true })))
      .toBe("Groq paused");
    expect(eventSentence(ev("audit", { action: "setting_changed", target: "cache_enabled.sign_in", old: true, new: false }))).toBe("Sign in cache turned off");
    expect(eventSentence(ev("audit", { action: "setting_changed", target: "telemetry_retention_days", old: 14, new: 30 })))
      .toBe("Log retention changed from 14 to 30 days");
    for (const kind of ["api", "ai_attempt", "ai_reply", "error", "audit"] as const) expect(eventSentence(ev(kind, {}))).not.toContain("—");
  });

  it("keeps the live feed newest first and bounded", () => {
    const old = [ev("api", {}, 2), ev("api", {}, 1)];
    const merged = mergeLive(old, [ev("api", {}, 3), ev("api", {}, 4)], 3);
    expect(merged.map((e) => e.seq)).toEqual([4, 3, 2]);
  });
});
