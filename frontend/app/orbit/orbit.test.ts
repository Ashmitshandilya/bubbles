import { describe, expect, it } from "vitest";
import {
  clearPlan, dial, ledeFor, loadPlan, readCheckin, readConsentNeeded, readCooldown, readDraft, readHarbor, readHome, readLoveMap, readQuestion, readReplies, readSafety, savePlan,
  SAFETY_PLAN_ITEMS, STATUS_OPTIONS,
} from "./orbit";

const home = (over: Record<string, unknown> = {}) => ({
  status: "success", profile: { status: "dating", partner_word: "my girlfriend", cared_for_by: ["words"], conflict_style: null }, paired: false, partner_name: null,
  question: { id: "q01", text: "What made you smile today?", answered: false, state: "solo" }, checkin: { week: "2026-W43", answered: false, state: "solo" }, weather: null, weather_paused: false,
  sharing: { rituals: false, weather: false }, ...over,
});

describe("readHome", () => {
  it("reads the home answer", () => {
    const h = readHome(home())!;
    expect(h.profile).toEqual({ status: "dating", partnerWord: "my girlfriend", caredForBy: ["words"], conflictStyle: null });
    expect(h.question.text).toBe("What made you smile today?");
    expect(h.paired).toBe(false);
  });
  it("is tolerant of missing pieces and refuses a failure", () => {
    expect(readHome({ status: "success" })!.profile.status).toBeNull();
    expect(readHome({ status: "error" })).toBeNull();
    expect(readHome(null)).toBeNull();
  });
});

describe("ledeFor", () => {
  it("prefers the partner's weather line", () => {
    expect(ledeFor(readHome(home({ weather: "Ask how their day really was." })))).toBe("Ask how their day really was.");
  });
  it("asks about the relationship first when nothing is known", () => {
    expect(ledeFor(readHome(home({ profile: { status: null } })))).toContain("where you are");
  });
  it("speaks to a person who is single without assuming a partner", () => {
    expect(ledeFor(readHome(home({ profile: { status: "single" } })))).toContain("everyone you hold close");
  });
  it("notices a waiting question and a revealed one", () => {
    expect(ledeFor(readHome(home({ paired: true, partner_name: "Ashmit" })))).toContain("waiting for you both");
    expect(ledeFor(readHome(home({ paired: true, question: { text: "q", answered: true, state: "revealed" } })))).toContain("both answered");
  });
  it("has a line even before it loads", () => {
    expect(ledeFor(null)).toBeTruthy();
  });
});

describe("safety answers", () => {
  it("reads a fixed safety answer with its numbers", () => {
    const s = readSafety({ status: "safety", kind: "safe_harbor", message: "I'm here.", harbor: { resources: [{ name: "Emergency services", number: "112", note: "Free" }, { nope: 1 }] } })!;
    expect(s.kind).toBe("safe_harbor");
    expect(s.resources).toEqual([{ name: "Emergency services", number: "112", note: "Free" }]);
  });
  it("is null for an ordinary answer", () => {
    expect(readSafety({ status: "success" })).toBeNull();
    expect(readSafety(undefined)).toBeNull();
  });
  it("reads the ask for the AI yes only from a 403 with the right code", () => {
    expect(readConsentNeeded(403, { detail: { code: "consent_required", message: "Turn it on?" } })).toEqual({ message: "Turn it on?" });
    expect(readConsentNeeded(403, { detail: "nope" })).toBeNull();
    expect(readConsentNeeded(200, { detail: { code: "consent_required" } })).toBeNull();
  });
});

describe("tools", () => {
  it("reads replies, a decline, and nothing else", () => {
    const r = readReplies({ status: "success", feelings: ["tired"], replies: [{ tone: "gentle", text: "Hi", why: "Warm" }, { tone: 3 }], source: "ai" })!;
    expect(r.replies).toEqual([{ tone: "gentle", text: "Hi", why: "Warm" }]);
    expect(readReplies({ status: "declined", message: "Say it directly." })!.declined).toBe("Say it directly.");
    expect(readReplies({ status: "success" })).toBeNull();
  });
  it("reads the question and the check-in with the partner's side only when sent", () => {
    expect(readQuestion({ status: "success", text: "Q?", answered: true, my_answer: "a", partner_answer: null, state: "waiting", paired: true })).toMatchObject({ answered: true, partnerAnswer: null, state: "waiting" });
    const c = readCheckin({ status: "success", prompts: { wish: "A wish" }, answered: true, my_answers: { wish: "rest" }, partner_answers: { appreciate: "tea" }, state: "revealed", paired: true })!;
    expect(c.partner).toEqual({ appreciate: "tea" });
    expect(readCheckin({ status: "success", prompts: {}, answered: false, my_answers: {}, state: "solo" })!.partner).toBeNull();
  });
  it("reads the love map, the cool-down, the draft and the harbor page", () => {
    expect(readLoveMap({ status: "success", known: [{ id: "name", text: "Their name: A" }, { id: 1 }], ask: [{ id: "m01", text: "What?" }] })).toEqual({ known: [{ id: "name", text: "Their name: A" }], ask: [{ id: "m01", text: "What?" }] });
    expect(readCooldown({ status: "success", heated: true, rewrite: "Softer", pause_minutes: 20 })).toEqual({ heated: true, rewrite: "Softer", pauseMinutes: 20 });
    expect(readDraft({ status: "success", draft: "Hello" })).toBe("Hello");
    expect(readHarbor({ status: "success", title: "Feeling unsafe at home?", resources: [{ name: "Emergency services", number: "112" }] })!.resources[0].number).toBe("112");
  });
});

describe("dial", () => {
  it("lets only a plain number into a phone link", () => {
    expect(dial("112")).toBe("112");
    expect(dial("1-800-891-4416")).toBe("");        // too long for the short-code rule; the page shows it as text
    expect(dial("14416")).toBe("14416");
    expect(dial("+91 98765")).toBe("");            // seven digits: not a short help line, shown as text
    expect(dial("javascript:alert(1)")).toBe("");
    expect(dial("")).toBe("");
  });
});

describe("the safety plan stays in this browser", () => {
  const store = () => {
    const data = new Map<string, string>();
    return { getItem: (k: string) => data.get(k) ?? null, setItem: (k: string, v: string) => void data.set(k, v), removeItem: (k: string) => void data.delete(k), data };
  };
  it("saves, loads and clears only known items", () => {
    const s = store();
    savePlan(s, ["numbers", "bag", "made-up"]);
    expect(loadPlan(s)).toEqual(["numbers", "bag"]);
    clearPlan(s);
    expect(loadPlan(s)).toEqual([]);
  });
  it("survives broken or missing storage", () => {
    expect(loadPlan(undefined)).toEqual([]);
    expect(loadPlan({ getItem: () => "{not json" })).toEqual([]);
    expect(() => savePlan({ setItem: () => { throw new Error("blocked"); } }, ["numbers"])).not.toThrow();
  });
  it("has the checklist the plan describes", () => {
    expect(SAFETY_PLAN_ITEMS.length).toBeGreaterThanOrEqual(6);
    expect(new Set(SAFETY_PLAN_ITEMS.map((i) => i.id)).size).toBe(SAFETY_PLAN_ITEMS.length);
    expect(STATUS_OPTIONS.some((o) => o.id === "prefer_not")).toBe(true);
  });
});
