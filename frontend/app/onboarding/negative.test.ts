import { describe, expect, it } from "vitest";
import fixture from "./bank.fixture.json";
import { AUTO_OPEN_MS, LINE_GAP_MS, MAX_LINES, MIN_WORKING_MS } from "./Creating";
import {
  advancesOnPick, buildScreens, isAnswered, missingRequired, pendingPatch, pick, progressLabel, resumeIndex, visibleQuestions, type Answers, type Question,
} from "./flow";
import { TOUR_STEPS, outcomeBody, placeCard, reduceTour, shouldStart, tourView, usableSteps } from "./tour";

const questions = fixture.questions as unknown as Question[];
const titles = fixture.screens as Record<string, string>;
const today = new Date(2026, 9, 15);
const byId = (id: string) => questions.find((q) => q.id === id)!;
const screensOf = (answers: Answers) => buildScreens(questions, titles, answers, today, false);

describe("nothing is sent before the date of birth is a real date", () => {
  const withBody = { body: "female", language: "english" };
  for (const bad of [undefined, null, "", "   ", [], {}]) {
    it(`sends nothing for a date of birth of ${JSON.stringify(bad)}`, () => {
      const answers = { ...withBody, birth_date: bad } as Answers;
      expect(pendingPatch(screensOf(answers), 3, questions, answers, {}, today)).toBeNull();
    });
  }

  it("sends the body only together with the date, never ahead of it", () => {
    const screens = screensOf(withBody);
    expect(pendingPatch(screens, 0, questions, withBody, {}, today)).toBeNull();
    const both = { ...withBody, birth_date: "1995-03-04" };
    expect(pendingPatch(screensOf(both), 1, questions, both, {}, today)).toMatchObject({ body: "female", birth_date: "1995-03-04" });
  });
});

describe("what the browser will and will not send", () => {
  const answers: Answers = { body: "male", language: "english", birth_date: "1990-01-01", preferred_name: "Sam", main_goal: "sleep", evil: "x", ai_consent: "yes", __proto__: { admin: true } };

  it("never sends a key the bank does not have, so consent and junk cannot ride along", () => {
    const patch = pendingPatch(screensOf(answers), 20, questions, answers, {}, today)!;
    expect(Object.keys(patch)).not.toContain("evil");
    expect(Object.keys(patch)).not.toContain("ai_consent");
    expect(Object.keys(patch)).not.toContain("admin");
  });

  it("a double tap or a re-save sends nothing the second time", () => {
    const clean: Answers = { body: "male", language: "english", birth_date: "1990-01-01", preferred_name: "Sam", main_goal: "sleep" };
    const screens = screensOf(clean);
    const first = pendingPatch(screens, 5, questions, clean, {}, today)!;
    expect(Object.keys(first).length).toBeGreaterThan(0);
    expect(pendingPatch(screens, 5, questions, clean, first, today)).toEqual({});
  });

  it("an unanswered required question is never sent as null", () => {
    const clean: Answers = { body: "male", language: "english", birth_date: "1990-01-01" };
    const saved: Answers = { ...clean, preferred_name: "Sam", sleep_pattern: "under_6", stress_level: "low" };
    const patch = pendingPatch(screensOf(clean), 20, questions, clean, saved, today)!;
    expect(Object.values(patch)).not.toContain(null);
    expect(patch).toEqual({});
  });
});

describe("skipping what is required", () => {
  const base: Answers = { body: "female", birth_date: "1990-01-01" };
  const required = (answers: Answers) => missingRequired(visibleQuestions(questions, answers, today), answers, today);

  it("lists every required question that is empty, whitespace or an empty list as missing", () => {
    expect(required({ ...base, preferred_name: "", main_goal: "", conditions_any: undefined, sleep_pattern: null as unknown as string })).toEqual(
      expect.arrayContaining(["preferred_name", "main_goal", "conditions_any", "sleep_pattern", "stress_level", "periods", "language"]));
    expect(isAnswered(byId("conditions"), [])).toBe(false);
    expect(isAnswered(byId("preferred_name"), null)).toBe(false);
  });

  it("asks the female body for periods and no other body", () => {
    expect(required(base)).toContain("periods");
    for (const body of ["male", "trans", "other", "prefer_not"]) expect(required({ ...base, body })).not.toContain("periods");
  });

  it("a hidden question is never reported as missing", () => {
    expect(required({ body: "male", birth_date: "1990-01-01" })).not.toContain("periods");
    expect(required({ body: "male" })).not.toContain("periods");
  });

  it("with no answers at all, only the first-screen and date questions can be reached, and all of them are needed", () => {
    expect(required({})).toEqual(expect.arrayContaining(["body", "language", "birth_date"]));
  });
});

describe("single taps", () => {
  it("never auto-advance on a multi choice, a text field, or an unanswered question", () => {
    const screens = screensOf({ body: "male", birth_date: "1990-01-01", conditions_any: "yes" });
    const follow = screens.find((s) => s.ids.includes("conditions"))!;
    expect(advancesOnPick(follow, questions, "conditions", { conditions: ["diabetes"] })).toBe(false);
    const about = screens.find((s) => s.id === "about")!;
    expect(advancesOnPick(about, questions, "preferred_name", { preferred_name: "R" })).toBe(false);
    const goal = screens.find((s) => s.id === "main_goal")!;
    expect(advancesOnPick(goal, questions, "main_goal", {})).toBe(false);
    expect(advancesOnPick(goal, questions, "does_not_exist", { main_goal: "sleep" })).toBe(false);
    const choices = screens.find((s) => s.kind === "choices")!;
    expect(advancesOnPick(choices, questions, "main_goal", { main_goal: "sleep" })).toBe(false);
  });

  it("a multi choice never exceeds its cap", () => {
    const capped = questions.find((q) => q.type === "multi" && q.max_picks !== undefined);
    if (!capped) return;
    const ids = (capped.options ?? []).map((o) => o.id).filter((id) => !(capped.exclusive ?? []).includes(id));
    let value: unknown;
    for (const id of ids) value = pick(capped, value, id);
    expect((value as string[]).length).toBeLessThanOrEqual(capped.max_picks!);
  });
});

describe("progress and resume edge cases", () => {
  it("a label for a screen that does not exist is empty, not a crash", () => {
    expect(progressLabel(screensOf({}), 99, {})).toBe("");
    expect(progressLabel([], 0, {})).toBe("");
  });

  it("resuming with nothing answered starts at the first screen, and with no screens at all at zero", () => {
    expect(resumeIndex(screensOf({}), questions, {}, false, today)).toBe(0);
    expect(resumeIndex([], questions, {}, true, today)).toBe(0);
  });

  it("a person who skipped everything optional still ends at the choices, not the extras", () => {
    const done: Answers = { body: "male", language: "english", birth_date: "1990-01-01", preferred_name: "Sam", main_goal: "sleep", conditions_any: "prefer_not", sleep_pattern: "six_seven", stress_level: "low" };
    const screens = screensOf(done);
    expect(screens[resumeIndex(screens, questions, done, false, today)].kind).toBe("choices");
  });
});

describe("the setup screen is quick and honest", () => {
  it("is within the owner's timings", () => {
    expect(MIN_WORKING_MS).toBeLessThanOrEqual(1200);
    expect(LINE_GAP_MS).toBeLessThanOrEqual(250);
    expect(AUTO_OPEN_MS).toBeLessThanOrEqual(2000);
    expect(MAX_LINES).toBeLessThanOrEqual(4);
    expect(MIN_WORKING_MS + MAX_LINES * LINE_GAP_MS).toBeLessThanOrEqual(AUTO_OPEN_MS + 200);
  });
});

describe("the tour, dismissed and replayed", () => {
  const open = { open: true, index: 2 };

  it("a closed tour ignores every action, so a stray key cannot reopen it", () => {
    const closed = { open: false, index: 4 };
    for (const type of ["next", "back", "close"] as const) expect(reduceTour(closed, { type }, 5)).toEqual(closed);
  });

  it("skip closes from any stop, and back never goes below the first", () => {
    for (let i = 0; i < 5; i++) expect(reduceTour({ open: true, index: i }, { type: "close" }, 5).open).toBe(false);
    expect(reduceTour({ open: true, index: 0 }, { type: "back" }, 5)).toEqual({ open: true, index: 0 });
  });

  it("next past the end closes instead of running off, even with a single stop or none", () => {
    expect(reduceTour({ open: true, index: 4 }, { type: "next" }, 5).open).toBe(false);
    expect(reduceTour({ open: true, index: 0 }, { type: "next" }, 1).open).toBe(false);
    expect(reduceTour(open, { type: "next" }, 0).open).toBe(false);
  });

  it("does not start when seen, when unknown, or when the check failed; replay always starts", () => {
    expect(shouldStart(true, false)).toBe(false);
    expect(shouldStart(null, false)).toBe(false);
    expect(shouldStart(false, false)).toBe(true);
    expect(shouldStart(true, true)).toBe(true);
    expect(shouldStart(null, true)).toBe(true);
  });

  it("with nothing on the page there are no stops, and the position text still reads sensibly", () => {
    expect(usableSteps(() => false)).toEqual([]);
    expect(tourView(0, 1)).toEqual({ position: "1 of 1", isFirst: true, isLast: true });
  });

  it("records only a boolean outcome and nothing else", () => {
    expect(JSON.parse(outcomeBody(true))).toEqual({ skipped: true });
    expect(JSON.parse(outcomeBody(false))).toEqual({ skipped: false });
  });

  it("every stop has a target selector and a title, so none is a blank card", () => {
    for (const s of TOUR_STEPS) {
      expect(s.selector.length).toBeGreaterThan(0);
      expect(s.title.length).toBeGreaterThan(0);
      expect(s.body.length).toBeGreaterThan(0);
    }
  });

  it("keeps the card on screen for a target off the edge or a tiny window", () => {
    const edge = placeCard({ top: -50, left: -300, width: 40, height: 40 }, { width: 320, height: 480 }, { width: 340, height: 200 });
    expect(edge.left).toBeGreaterThanOrEqual(16);
    expect(edge.top).toBeGreaterThanOrEqual(16);
    const tiny = placeCard({ top: 10, left: 10, width: 500, height: 500 }, { width: 200, height: 200 }, { width: 340, height: 400 });
    expect(Number.isFinite(tiny.top) && Number.isFinite(tiny.left)).toBe(true);
    expect(tiny.left).toBeGreaterThanOrEqual(16);
  });
});
