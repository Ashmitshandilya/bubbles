import { describe, expect, it } from "vitest";
import { continuingLabel, mapMessageRows, olderCursor, parseEntry, pickLatest, prependOlder, scrollPlan } from "./resume";

const q = (s: string) => new URLSearchParams(s);

describe("parseEntry", () => {
  it("reads ?new=1 as a blank start and nothing else as one", () => {
    expect(parseEntry(q("new=1"))).toEqual({ fresh: true, ask: null });
    expect(parseEntry(q("new=0")).fresh).toBe(false);
    expect(parseEntry(q("")).fresh).toBe(false);
  });

  it("reports a waiting question from ?ask= or ?askref=", () => {
    expect(parseEntry(q("ask=hello")).ask).toBe("hello");
    expect(parseEntry(q("askref=abc")).ask).toBe("abc");
    expect(parseEntry(q("new=1&ask=hi"))).toEqual({ fresh: true, ask: "hi" });
  });
});

describe("mapMessageRows", () => {
  it("keeps createdAt and runs assistant rows through the safety adapters", () => {
    const rows = [
      { id: "u1", role: "user", content: "my head hurts", created_at: "2026-10-10T08:00:00Z" },
      {
        id: "a1",
        role: "assistant",
        content: "Sorry to hear.",
        created_at: "2026-10-10T08:00:05Z",
        safety: { level: "AMBER", state: "POTENTIAL_REDFLAG_NEEDS_CLARIFICATION", reasons: ["a headache"] },
        health_events: [{ id: "e1", event_type: "symptom", status: "confirmed", extracted_data: {} }],
      },
    ];
    const [user, reply] = mapMessageRows(rows, "c1");
    expect(user).toMatchObject({ id: "u1", role: "user", createdAt: "2026-10-10T08:00:00Z" });
    expect(reply.role).toBe("assistant");
    expect(reply.safetyLevel).toBe("AMBER");
    expect(reply.healthEvents?.[0]).toMatchObject({ id: "e1", status: "confirmed" });
  });

  it("brings a stored Safe Harbor reply back with its resources and choices", () => {
    const harbor = {
      tier: 2,
      mode: "disclosure",
      step: "options",
      resources: [{ name: "Emergency services", number: "112", note: "Free." }],
      actions: [{ id: "talk_more", label: "I want to talk more" }],
    };
    const [plain, shown] = mapMessageRows(
      [
        { id: "a0", role: "assistant", content: "Hello." },
        { id: "a1", role: "assistant", content: "I'm so sorry.", kind: "safe_harbor", harbor },
      ],
      "c1"
    );
    expect(plain.harbor).toBeUndefined();
    expect(shown.harbor?.resources[0].number).toBe("112");
    expect(shown.harbor?.actions[0].label).toBe("I want to talk more");
  });

  it("survives junk rows and a non-array", () => {
    expect(mapMessageRows(null, "c1")).toEqual([]);
    const [m] = mapMessageRows([42], "c1");
    expect(m.id).toBe("c1-0");
  });
});

describe("pickLatest", () => {
  const ok = { status: "success", conversation: { id: "c1", title: "Sleep", created_at: "x", updated_at: "y" }, has_more: true };

  it("returns the chat with its messages and paging flag", () => {
    const r = pickLatest({ ...ok, messages: [{ id: "u1", role: "user", content: "hi" }] });
    expect(r).toMatchObject({ kind: "chat", conversationId: "c1", title: "Sleep", hasMore: true });
  });

  it("is empty when there is no conversation or it has no messages", () => {
    expect(pickLatest({ status: "success", conversation: null, messages: [], has_more: false })).toEqual({ kind: "empty" });
    expect(pickLatest({ ...ok, messages: [] })).toEqual({ kind: "empty" });
  });

  it("treats degraded and unreadable answers as an error, never as no chats", () => {
    expect(pickLatest({ ...ok, messages: [], degraded: true })).toEqual({ kind: "error" });
    expect(pickLatest(null)).toEqual({ kind: "error" });
    expect(pickLatest({ status: "error" })).toEqual({ kind: "error" });
    expect(pickLatest({ status: "success" })).toEqual({ kind: "error" });
    expect(pickLatest({ status: "success", conversation: { title: "no id" }, messages: [] })).toEqual({ kind: "error" });
  });
});

describe("paging older messages", () => {
  const m = (id: string, createdAt?: string) => ({ id, role: "user" as const, content: id, createdAt });

  it("uses the oldest loaded time as the cursor", () => {
    expect(olderCursor([m("a", "2026-10-01T00:00:00Z"), m("b", "2026-10-02T00:00:00Z")])).toBe("2026-10-01T00:00:00Z");
    expect(olderCursor([m("a")])).toBeNull();
  });

  it("puts older rows first and never doubles one", () => {
    const merged = prependOlder([m("c"), m("d")], [m("a"), m("b"), m("c")]);
    expect(merged.map((x) => x.id)).toEqual(["a", "b", "c", "d"]);
  });
});

describe("scrollPlan", () => {
  const base = { opened: false, prepended: false, lastIdChanged: false, sendingStarted: false };
  it("jumps instantly on open and anchors on prepend", () => {
    expect(scrollPlan({ ...base, opened: true, lastIdChanged: true })).toBe("jump");
    expect(scrollPlan({ ...base, prepended: true })).toBe("anchor");
  });
  it("glides only for a new last message or a reply starting", () => {
    expect(scrollPlan({ ...base, lastIdChanged: true })).toBe("smooth");
    expect(scrollPlan({ ...base, sendingStarted: true })).toBe("smooth");
    expect(scrollPlan(base)).toBe("none");
  });
});

describe("continuingLabel", () => {
  const now = new Date(2026, 9, 16, 12, 0, 0);
  it("is silent for today and names yesterday, a weekday or a date", () => {
    expect(continuingLabel(new Date(2026, 9, 16, 8).toISOString(), now)).toBeNull();
    expect(continuingLabel(new Date(2026, 9, 15, 20).toISOString(), now)).toBe("Continuing your chat from yesterday");
    expect(continuingLabel(new Date(2026, 9, 13, 9).toISOString(), now)).toMatch(/^Continuing your chat from [A-Z][a-z]+day$/);
    expect(continuingLabel(new Date(2026, 8, 1, 9).toISOString(), now)).toMatch(/from 1 Sep/);
    expect(continuingLabel(undefined, now)).toBeNull();
  });
});
