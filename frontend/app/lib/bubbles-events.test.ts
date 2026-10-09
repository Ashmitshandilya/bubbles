/**
 * Checks for the chat-contract adapter. Run: npx vitest run app/lib/bubbles-events.test.ts
 * The smallest thing that fails if the contract pairing, safety mapping, correction handling,
 * description rendering, link safety or reply parsing breaks.
 */
import { describe, expect, it } from "vitest";
import {
  adaptCorrection,
  adaptEvidence,
  adaptHealthEvents,
  adaptKind,
  adaptReplySafety,
  adaptSafety,
  applyCorrection,
  confidenceLabel,
  eventNote,
  isUrgentMessage,
  parseChatMarkdown,
  reasonSentence,
  replaceId,
  retractionNote,
  settledState,
  splitBold,
  upsertById,
  type SafetyLevel,
} from "./bubbles-events";

describe("adaptHealthEvents", () => {
  it("pairs ids by index and renders extracted_data as prose", () => {
    const events = adaptHealthEvents(
      [
        { event_type: "sleep", extracted_data: { hours: 6.5 }, confidence: 0.82 },
        { event_type: "symptom", extracted_data: { name: "headache", severity: 3 }, confidence: 0.44 },
      ],
      ["evt-1", "evt-2"]
    );
    expect(events.map((e) => e.id)).toEqual(["evt-1", "evt-2"]);
    expect(events[0].eventType).toBe("sleep");
    expect(events[0].isConfirmable).toBe(true);
    expect(events[0].description).toBe("hours: 6.5");
  });

  it("never offers a dead confirm button for an event without an id", () => {
    const orphan = adaptHealthEvents([{ event_type: "mood", extracted_data: {} }], []);
    expect(orphan[0].id).toBeNull();
    expect(orphan[0].isConfirmable).toBe(false);
    expect(orphan[0].description).toContain("No additional detail");
  });

  // Updated: this used to expect ["only-one", null]. The contract now says health_event_ids is index-aligned with
  // health_events, so a shorter list means a skipped event shifted every later id. Guessing would confirm the wrong row.
  it("refuses to guess when the parallel id array does not line up", () => {
    const short = adaptHealthEvents([{ event_type: "a" }, { event_type: "b" }], ["only-one"]);
    expect([short[0].id, short[1].id]).toEqual([null, null]);
    expect(short.every((e) => !e.isConfirmable)).toBe(true);
  });

  it("prefers the inline id over the parallel array", () => {
    const events = adaptHealthEvents(
      [
        { id: "inline-1", event_type: "a" },
        { id: "inline-2", event_type: "b" },
      ],
      ["wrong-1", "wrong-2"]
    );
    expect(events.map((e) => e.id)).toEqual(["inline-1", "inline-2"]);
  });

  it("does not pair e1 with id2 when the backend sends inline ids and a stale parallel array", () => {
    const events = adaptHealthEvents(
      [
        { id: null, event_type: "unsaved" },
        { id: "id2", event_type: "saved" },
      ],
      ["id2"]
    );
    expect(events.map((e) => e.id)).toEqual([null, "id2"]);
    expect(events.map((e) => e.isConfirmable)).toEqual([false, true]);
  });

  it("falls back to the parallel array only when the lengths match and the event has no id key", () => {
    const matched = adaptHealthEvents([{ event_type: "a" }, { event_type: "b" }], [null, "id-b"]);
    expect(matched.map((e) => e.id)).toEqual([null, "id-b"]);
  });

  it("tolerates non-array input", () => {
    expect(adaptHealthEvents(undefined, undefined)).toEqual([]);
    expect(adaptHealthEvents({ bad: true }, null)).toEqual([]);
  });

  it("survives malformed entries and non-string ids", () => {
    const events = adaptHealthEvents([null, "text", 7, { id: 5, event_type: 3, extracted_data: "x" }], undefined);
    expect(events).toHaveLength(4);
    expect(events.every((e) => e.id === null && !e.isConfirmable)).toBe(true);
    expect(events[3].eventType).toBe("health event");
  });
});

describe("health event confirmability", () => {
  const base = { id: "e1", event_type: "symptom", extracted_data: { symptom: "headache" } };

  it("treats a missing assertion and status as a legacy, confirmable event", () => {
    expect(adaptHealthEvents([base], undefined)[0].isConfirmable).toBe(true);
  });

  it("confirms a present, pending event", () => {
    const [event] = adaptHealthEvents([{ ...base, assertion: "present", status: "pending", temporal: "current" }], undefined);
    expect(event.isConfirmable).toBe(true);
    expect(event.assertion).toBe("present");
    expect(event.temporal).toBe("current");
    expect(event.status).toBe("pending");
  });

  it.each(["negated", "possible", "hypothetical", "question", "other_person", "quoted"])("does not offer to save a %s event", (assertion) => {
    const [event] = adaptHealthEvents([{ ...base, assertion, status: "pending" }], undefined);
    expect(event.isConfirmable).toBe(false);
    expect(eventNote(event)).toEqual(expect.any(String));
  });

  it.each(["confirmed", "rejected", "superseded", "retracted"])("does not offer to save a %s event", (status) => {
    const [event] = adaptHealthEvents([{ ...base, assertion: "present", status }], undefined);
    expect(event.isConfirmable).toBe(false);
  });

  it("reads the assertion from _prov and treats present:false as a denial", () => {
    const [viaProv] = adaptHealthEvents([{ id: "e1", extracted_data: { symptom: "x", _prov: { assertion: "negated" } } }], undefined);
    expect(viaProv.assertion).toBe("negated");
    expect(viaProv.isConfirmable).toBe(false);
    const [denied] = adaptHealthEvents([{ id: "e2", extracted_data: { symptom: "x", present: false } }], undefined);
    expect(denied.assertion).toBe("negated");
    expect(denied.isConfirmable).toBe(false);
  });

  it("reports what the server already settled, so reloaded messages do not re-offer it", () => {
    const events = adaptHealthEvents(
      ["confirmed", "rejected", "retracted", "superseded", "pending"].map((status, i) => ({ id: `e${i}`, status })),
      undefined
    );
    expect(events.map(settledState)).toEqual(["saved", "dismissed", "retracted", "retracted", null]);
  });

  it("explains why an event has no save button", () => {
    const [unsaved] = adaptHealthEvents([{ id: null }], undefined);
    expect(eventNote(unsaved)).toContain("couldn't be staged");
    const [pending] = adaptHealthEvents([{ id: "e1" }], undefined);
    expect(eventNote(pending)).toBeNull();
    const [odd] = adaptHealthEvents([{ id: "e1", assertion: "something_new" }], undefined);
    expect(eventNote(odd)).toContain("isn't sure");
  });
});

describe("health event descriptions", () => {
  it("never prints metadata keys", () => {
    const [event] = adaptHealthEvents(
      [
        {
          id: "e1",
          event_type: "symptom",
          extracted_data: {
            symptom: "headache",
            severity: 3,
            assertion: "present",
            temporal: "current",
            status: "pending",
            provenance: { source: "chat" },
            _prov: { source: "chat", assertion: "present" },
            _internal: "x",
          },
        },
      ],
      undefined
    );
    expect(event.description).toBe("symptom: headache · severity: 3");
    for (const word of ["assertion", "temporal", "status", "provenance", "_prov", "_internal", "pending"]) {
      expect(event.description).not.toContain(word);
    }
  });

  it("falls back to a plain sentence when only metadata is present", () => {
    const [event] = adaptHealthEvents([{ id: "e1", extracted_data: { _prov: { a: 1 }, assertion: "present" } }], undefined);
    expect(event.description).toContain("No additional detail");
  });

  it("renders a symptom screen as read-only denials", () => {
    const [event] = adaptHealthEvents(
      [
        {
          id: "e1",
          event_type: "wellness_checkin",
          assertion: "negated",
          extracted_data: { pertinent_negatives: ["headache", " chest pain "], screen: "symptom_screen", date: "2026-10-07", _prov: {} },
        },
      ],
      undefined
    );
    expect(event.notPresent).toEqual(["headache", "chest pain"]);
    expect(event.description).toBe("Not present: headache, chest pain");
    expect(event.isConfirmable).toBe(false);
  });

  it("joins array values readably", () => {
    const [event] = adaptHealthEvents([{ id: "e1", extracted_data: { foods: ["rice", "dal"], notes: [] } }], undefined);
    expect(event.description).toBe("foods: rice, dal");
  });
});

describe("adaptSafety", () => {
  it.each<[string, SafetyLevel]>([
    ["EMERGENCY", "RED"],
    ["URGENT", "RED"],
    ["POTENTIAL_REDFLAG_NEEDS_CLARIFICATION", "AMBER"],
    ["NO_REDFLAG", "GREEN"],
  ])("maps state %s to %s", (state, level) => {
    const view = adaptSafety({ state });
    expect(view.level).toBe(level);
    expect(view.state).toBe(state);
  });

  it("maps URGENT to RED even though the backend sends the legacy level AMBER", () => {
    expect(adaptSafety({ state: "URGENT", level: "AMBER" }).level).toBe("RED");
  });

  it("keeps the legacy RED/AMBER/GREEN levels working without a state", () => {
    expect(adaptSafety({ level: "RED" }).level).toBe("RED");
    expect(adaptSafety({ level: "AMBER" }).level).toBe("AMBER");
    expect(adaptSafety({ level: "GREEN" }).level).toBe("GREEN");
    expect(adaptSafety({ level: "red" }).level).toBe("RED");
  });

  it("fails toward caution: an unknown non-empty level or state is AMBER", () => {
    expect(adaptSafety({ level: "SEVERE" }).level).toBe("AMBER");
    expect(adaptSafety({ level: 3 }).level).toBe("AMBER");
    expect(adaptSafety({ state: "SOMETHING_NEW" }).level).toBe("AMBER");
    expect(adaptSafety({ state: "SOMETHING_NEW" }).state).toBeNull();
    expect(adaptSafety(undefined, "ORANGE").level).toBe("AMBER");
  });

  it("takes the more cautious of state and level when they disagree", () => {
    expect(adaptSafety({ state: "NO_REDFLAG", level: "RED" }).level).toBe("RED");
    expect(adaptSafety({ state: "NO_REDFLAG", level: "AMBER" }).level).toBe("AMBER");
  });

  it("treats only a wholly missing safety object as GREEN", () => {
    for (const missing of [undefined, null, {}, "", "text", 5, [], { level: "" }, { level: null }]) {
      expect(adaptSafety(missing).level).toBe("GREEN");
    }
    expect(adaptSafety(undefined, undefined).state).toBeNull();
  });

  it("uses the legacy safety_level of a history row when there is no safety object", () => {
    expect(adaptSafety(undefined, "RED").level).toBe("RED");
    expect(adaptSafety(null, "AMBER").level).toBe("AMBER");
    expect(adaptSafety({ reasons: ["x"] }, "RED").level).toBe("RED");
  });

  it("honours retracted only when it is the boolean true", () => {
    for (const notTrue of ["true", 1, "yes", {}, [], null, undefined, false]) {
      const view = adaptSafety({ level: "RED", state: "EMERGENCY", retracted: notTrue });
      expect(view.retracted).toBe(false);
      expect(view.level).toBe("RED");
    }
    const withdrawn = adaptSafety({
      level: "RED",
      state: "EMERGENCY",
      retracted: true,
      retracted_at: "2026-10-07T10:00:00Z",
      retracted_by_message_id: "m2",
    });
    expect(withdrawn.retracted).toBe(true);
    expect(withdrawn.level).toBe("GREEN");
    expect(withdrawn.originalLevel).toBe("RED");
    expect(withdrawn.retractedAt).toBe("2026-10-07T10:00:00Z");
    expect(withdrawn.retractedBy).toBe("m2");
  });

  it("keeps only non-empty string reasons", () => {
    expect(adaptSafety({ level: "AMBER", reasons: ["you mentioned chest pain", "", 4, null, " dizziness "] }).reasons).toEqual([
      "you mentioned chest pain",
      "dizziness",
    ]);
    expect(adaptSafety({ level: "AMBER", reasons: "chest pain" }).reasons).toEqual([]);
  });
});

describe("adaptReplySafety", () => {
  it("returns the fields a message needs", () => {
    expect(adaptReplySafety({ level: "AMBER", state: "POTENTIAL_REDFLAG_NEEDS_CLARIFICATION", reasons: ["r"] }, undefined, "clarification")).toEqual({
      safetyLevel: "AMBER",
      safetyState: "POTENTIAL_REDFLAG_NEEDS_CLARIFICATION",
      safetyReasons: ["r"],
      retracted: false,
      kind: "clarification",
    });
  });

  it("never shows an emergency reply as calm", () => {
    const view = adaptReplySafety(undefined, undefined, "emergency");
    expect(view.safetyLevel).toBe("RED");
    expect(view.safetyState).toBe("EMERGENCY");
  });

  it("does not escalate a retracted emergency", () => {
    const view = adaptReplySafety({ level: "RED", retracted: true }, undefined, "emergency");
    expect(view.retracted).toBe(true);
    expect(view.safetyLevel).toBe("GREEN");
  });

  it("drops unknown kinds", () => {
    expect(adaptKind("daily_log_summary")).toBe("daily_log_summary");
    expect(adaptKind("correction_ack")).toBe("correction_ack");
    expect(adaptKind("surprise")).toBeUndefined();
    expect(adaptKind(undefined)).toBeUndefined();
  });
});

describe("isUrgentMessage", () => {
  it("is true for a live RED message only", () => {
    expect(isUrgentMessage({ safetyLevel: "RED" })).toBe(true);
    expect(isUrgentMessage({ safetyLevel: "RED", retracted: true })).toBe(false);
    expect(isUrgentMessage({ safetyLevel: "AMBER" })).toBe(false);
    expect(isUrgentMessage({})).toBe(false);
  });
});

describe("adaptCorrection", () => {
  it("reads the contract", () => {
    expect(
      adaptCorrection({ retracted_message_id: "m1", concepts: ["chest pain"], retracted_event_ids: ["e1"], kept_event_ids: ["e2"] })
    ).toEqual({ retractedMessageId: "m1", concepts: ["chest pain"], retractedEventIds: ["e1"], keptEventIds: ["e2"] });
  });

  it("defaults missing lists to empty", () => {
    expect(adaptCorrection({ retracted_message_id: "m1" })).toEqual({
      retractedMessageId: "m1",
      concepts: [],
      retractedEventIds: [],
      keptEventIds: [],
    });
  });

  it("returns null for absent or malformed input", () => {
    for (const bad of [undefined, null, "m1", 5, [], {}, { retracted_message_id: "" }, { retracted_message_id: 7 }]) {
      expect(adaptCorrection(bad)).toBeNull();
    }
  });

  it("drops non-string list members", () => {
    expect(adaptCorrection({ retracted_message_id: "m1", concepts: ["a", 1, null], retracted_event_ids: "e1" })).toMatchObject({
      concepts: ["a"],
      retractedEventIds: [],
    });
  });
});

describe("applyCorrection", () => {
  const messages = [
    { id: "u1", content: "chest pain" },
    { id: "a1", content: "Bubbles detected chest pain", retracted: undefined as boolean | undefined },
    { id: "u2", content: "I said no chest pain" },
  ];
  const correction = { retractedMessageId: "a1", concepts: ["chest pain"], retractedEventIds: [], keptEventIds: [] };

  it("marks only the target retracted and keeps its original content", () => {
    const next = applyCorrection(messages, correction);
    expect(next[1]).toMatchObject({ id: "a1", content: "Bubbles detected chest pain", retracted: true, retractionConcepts: ["chest pain"] });
    expect(next[0]).toBe(messages[0]);
    expect(next[2]).toBe(messages[2]);
    expect(messages[1].retracted).toBeUndefined(); // input is not mutated
  });

  it("is idempotent", () => {
    const once = applyCorrection(messages, correction);
    const twice = applyCorrection(once, correction);
    expect(twice).toBe(once);
    expect(twice).toEqual(once);
  });

  it("ignores unknown ids and a null correction", () => {
    expect(applyCorrection(messages, { ...correction, retractedMessageId: "nope" })).toBe(messages);
    expect(applyCorrection(messages, null)).toBe(messages);
    expect(applyCorrection([], correction)).toEqual([]);
  });
});

describe("upsertById", () => {
  it("appends a new message and replaces an existing one", () => {
    const list = [{ id: "a", v: 1 }];
    expect(upsertById(list, { id: "b", v: 2 })).toEqual([
      { id: "a", v: 1 },
      { id: "b", v: 2 },
    ]);
    expect(upsertById(list, { id: "a", v: 9 })).toEqual([{ id: "a", v: 9 }]);
    expect(list).toEqual([{ id: "a", v: 1 }]);
  });

  it("never renders a replayed reply twice", () => {
    const once = upsertById([{ id: "u" }], { id: "reply" });
    expect(upsertById(once, { id: "reply" }).map((m) => m.id)).toEqual(["u", "reply"]);
  });
});

describe("replaceId", () => {
  it("gives the optimistic bubble its server id and keeps the old id as the key", () => {
    const next = replaceId([{ id: "chat-1" }, { id: "a1" }], "chat-1", "srv-1");
    expect(next).toEqual([{ id: "srv-1", clientId: "chat-1" }, { id: "a1" }]);
  });

  it("is a no-op for an unknown id, the same id, or a server id already present", () => {
    const list = [{ id: "chat-1" }, { id: "srv-1" }];
    expect(replaceId(list, "missing", "x")).toBe(list);
    expect(replaceId(list, "chat-1", "chat-1")).toBe(list);
    expect(replaceId(list, "chat-1", "srv-1")).toBe(list);
  });

  it("keeps the first client id across repeated replacement", () => {
    const first = replaceId([{ id: "chat-1" }], "chat-1", "srv-1");
    expect(replaceId(first, "srv-1", "srv-2")[0]).toEqual({ id: "srv-2", clientId: "chat-1" });
  });
});

describe("retractionNote", () => {
  it("names what the user denied, in plain words", () => {
    expect(retractionNote(["chest pain"])).toContain("did not have chest pain,");
    expect(retractionNote(["chest pain", "headache"])).toContain("did not have chest pain or headache");
    expect(retractionNote(["chest pain", "headache", "nausea"])).toContain("did not have chest pain, headache or nausea");
  });

  it("stays honest and calm when the concepts are unknown", () => {
    for (const none of [undefined, []]) {
      const note = retractionNote(none);
      expect(note).toContain("misread");
      expect(note).not.toContain("did not have");
    }
  });
});

describe("reasonSentence", () => {
  it("keeps the current 'Bubbles noticed' copy for emergencies, urgent care and the legacy RED/AMBER", () => {
    expect(reasonSentence(["chest pain"], null)).toBe("Bubbles noticed chest pain. ");
    expect(reasonSentence(["chest pain", "dizziness"], "EMERGENCY")).toBe("Bubbles noticed chest pain, dizziness. ");
    expect(reasonSentence(["a seizure"], "URGENT")).toBe("Bubbles noticed a seizure. ");
    expect(reasonSentence(["chest pain"])).toBe("Bubbles noticed chest pain. ");
  });

  it("never claims a symptom when Bubbles is only unsure", () => {
    const text = reasonSentence(["chest pain"], "POTENTIAL_REDFLAG_NEEDS_CLARIFICATION");
    expect(text).toBe("You mentioned chest pain. ");
    expect(text).not.toContain("noticed");
  });

  it("prints a reason the backend already phrased, without wrapping it again", () => {
    expect(reasonSentence(["you mentioned chest pain yesterday"], "POTENTIAL_REDFLAG_NEEDS_CLARIFICATION")).toBe(
      "You mentioned chest pain yesterday. "
    );
    expect(reasonSentence(["You said it stopped."], "URGENT")).toBe("You said it stopped. ");
    expect(reasonSentence(["youth sports injury"], null)).toBe("Bubbles noticed youth sports injury. ");
  });

  it("is empty when there is nothing to say", () => {
    expect(reasonSentence([], "EMERGENCY")).toBe("");
    expect(reasonSentence(undefined, null)).toBe("");
  });
});

describe("adaptEvidence", () => {
  it("reads the real contract with honest fallbacks", () => {
    const ev = adaptEvidence([
      { chunk_id: "c1", title: "Sleep and recovery", source_name: "Bubbles corpus", evidence_level: "moderate", source_url: "https://example.org/a" },
      { chunk_id: "c2" },
    ]);
    expect(ev[0].title).toBe("Sleep and recovery");
    expect(ev[0].sourceName).toBe("Bubbles corpus");
    expect(ev[0].sourceUrl).toBe("https://example.org/a");
    expect(ev[1].title).toBe("Source");
    expect(ev[1].sourceName).toBe("Unknown source");
    expect(ev[0].fusedScore).toBeNull();
  });

  it("drops non-http links so they can never become clickable script URLs", () => {
    const ev = adaptEvidence([{ source_url: "javascript:alert(1)" }, { source_url: "data:text/html,x" }]);
    expect(ev.map((e) => e.sourceUrl)).toEqual([null, null]);
  });
});

describe("confidenceLabel", () => {
  it("preserves uncertainty", () => {
    expect(confidenceLabel(0.9)).toContain("high");
    expect(confidenceLabel(0.7)).toContain("moderate");
    expect(confidenceLabel(0.3)).toContain("worth checking");
    expect(confidenceLabel(null)).toBeNull();
  });
});

describe("parseChatMarkdown", () => {
  it("parses the deterministic RED reply shape into headings, paragraphs and lists", () => {
    const blocks = parseChatMarkdown(
      "### Please get urgent medical help\n\nBubbles detected chest pain.\nCall now.\n\n### While getting help\n- Do not drive.\n- Tell someone nearby.\n\n1. First\n2. Second"
    );
    expect(blocks).toEqual([
      { kind: "heading", text: "Please get urgent medical help" },
      { kind: "paragraph", text: "Bubbles detected chest pain.\nCall now." },
      { kind: "heading", text: "While getting help" },
      { kind: "list", ordered: false, items: ["Do not drive.", "Tell someone nearby."] },
      { kind: "list", ordered: true, items: ["First", "Second"] },
    ]);
  });

  it("keeps bold lines as paragraphs and treats normalize_response bullets as a list", () => {
    expect(parseChatMarkdown("**What I'm noticing**\n• One\n• Two")).toEqual([
      { kind: "paragraph", text: "**What I'm noticing**" },
      { kind: "list", ordered: false, items: ["One", "Two"] },
    ]);
  });

  it("returns plain text for HTML-looking input instead of markup", () => {
    expect(parseChatMarkdown("<img src=x onerror=alert(1)>")).toEqual([
      { kind: "paragraph", text: "<img src=x onerror=alert(1)>" },
    ]);
  });
});

describe("splitBold", () => {
  it("splits bold runs", () => {
    expect(splitBold("Short **sleep** came **before** it")).toEqual([
      { text: "Short ", bold: false },
      { text: "sleep", bold: true },
      { text: " came ", bold: false },
      { text: "before", bold: true },
      { text: " it", bold: false },
    ]);
    expect(splitBold("no bold")).toEqual([{ text: "no bold", bold: false }]);
  });
});
