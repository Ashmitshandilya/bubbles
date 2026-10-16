import { describe, expect, it } from "vitest";
import fixture from "./bank.fixture.json";
import { activeSteps, ageOn, isAnswered, matches, missingRequired, pick, stepPatch, titleFor, visibleOptions, visibleQuestions, type Answers, type Question, type Step } from "./flow";

const questions = fixture.questions as unknown as Question[];
const steps = fixture.steps as unknown as Step[];
const today = new Date(2026, 9, 15);
const byId = (id: string) => questions.find((q) => q.id === id)!;

describe("the browser applies the same rules as the server", () => {
  it("shows exactly the questions the server shows, for every body and age case", () => {
    expect(fixture.cases.length).toBeGreaterThan(200);
    for (const c of fixture.cases) {
      expect(visibleQuestions(questions, c.answers as Answers, today).map((q) => q.id), JSON.stringify(c.answers)).toEqual(c.visible);
    }
  });

  it("shows exactly the options the server shows", () => {
    for (const c of fixture.cases) {
      for (const [qid, ids] of Object.entries(c.options as Record<string, string[]>)) {
        expect(visibleOptions(byId(qid), c.answers as Answers, today).map((o) => o.id), `${qid} ${JSON.stringify(c.answers)}`).toEqual(ids);
      }
    }
  });
});

describe("what a male body is never shown", () => {
  const male = { birth_date: "1990-01-01", body: "male" };
  it("has no period, pregnancy or cervical questions, options or goals", () => {
    const ids = visibleQuestions(questions, male, today).map((q) => q.id);
    for (const gone of ["periods", "periods_reason", "last_period", "pregnancy_plans", "cervical_screen", "midlife_changes"]) expect(ids).not.toContain(gone);
    expect(visibleOptions(byId("goals"), male, today).map((o) => o.id)).not.toEqual(expect.arrayContaining(["cycle"]));
    expect(visibleOptions(byId("avoid_topics"), male, today).map((o) => o.id)).not.toContain("periods");
  });

  it("a female body gets them", () => {
    const ids = visibleQuestions(questions, { birth_date: "1990-01-01", body: "female" }, today).map((q) => q.id);
    expect(ids).toEqual(expect.arrayContaining(["periods", "pregnancy_plans", "cervical_screen"]));
  });
});

describe("ages", () => {
  it("counts whole years and rejects impossible or future days", () => {
    expect(ageOn("2008-10-15", today)).toBe(18);
    expect(ageOn("2008-10-16", today)).toBe(17);
    expect(ageOn("2026-10-16", today)).toBeNull();
    expect(ageOn("2026-02-30", today)).toBeNull();
    expect(ageOn("not a date", today)).toBeNull();
    expect(ageOn(undefined, today)).toBeNull();
  });

  it("a question that needs an age is hidden until there is one", () => {
    expect(matches({ age_gte: 30 }, {}, today)).toBe(false);
    expect(matches({ age_gte: 30 }, { birth_date: "1990-01-01" }, today)).toBe(true);
    expect(matches({ not_answers: { a: ["x"] } }, {}, today)).toBe(true);
  });
});

describe("steps", () => {
  it("drops a step that has no question for this person", () => {
    const male = { birth_date: "1990-01-01", body: "male" };
    expect(activeSteps(steps, questions, male, today).map((s) => s.id)).toContain("life");   // bp and sugar checks still apply at 30+
    const youngMale = { birth_date: "2004-01-01", body: "male" };
    expect(activeSteps(steps, questions, youngMale, today).map((s) => s.id)).not.toContain("life");
  });
});

describe("answering", () => {
  it("single choice replaces and clears", () => {
    const q = byId("body");
    expect(pick(q, undefined, "male")).toBe("male");
    expect(pick(q, "male", "female")).toBe("female");
    expect(pick(q, "male", "male")).toBeUndefined();
  });

  it("multi choice adds, removes, and lets 'none of these' stand alone", () => {
    const q = byId("conditions");
    expect(pick(q, undefined, "diabetes")).toEqual(["diabetes"]);
    expect(pick(q, ["diabetes"], "high_bp")).toEqual(["diabetes", "high_bp"]);
    expect(pick(q, ["diabetes", "high_bp"], "diabetes")).toEqual(["high_bp"]);
    expect(pick(q, ["diabetes"], "none")).toEqual(["none"]);
    expect(pick(q, ["none"], "diabetes")).toEqual(["diabetes"]);
    expect(pick(q, ["diabetes"], "diabetes")).toBeUndefined();
  });

  it("stops at the most picks allowed", () => {
    const q = byId("goals");
    const six = ["understand_symptoms", "sleep", "stress_mood", "fitness_weight", "food", "manage_condition"];
    expect(pick(q, six, "doctor_visits")).toEqual(six);
  });

  it("only required questions block, and an empty optional one is sent as a skip", () => {
    const about = questions.filter((q) => q.step === "about" && ["preferred_name", "body", "birth_date", "language"].includes(q.id));
    expect(missingRequired(about, { preferred_name: "Riya" })).toEqual(["body", "birth_date"]);
    const daily = [byId("sleep_hours"), byId("screen_hours")];
    expect(stepPatch(daily, { sleep_hours: 7 })).toEqual({ sleep_hours: 7, screen_hours: null });
    expect(stepPatch([byId("tone")], {})).toEqual({ tone: null });
  });

  it("knows what counts as answered", () => {
    expect(isAnswered(byId("sleep_hours"), 0)).toBe(true);
    expect(isAnswered(byId("goals"), [])).toBe(false);
    expect(isAnswered(byId("height_weight"), {})).toBe(false);
    expect(isAnswered(byId("height_weight"), { height_cm: 160 })).toBe(true);
    expect(isAnswered(byId("preferred_name"), "")).toBe(false);
  });
});

describe("language", () => {
  it("uses the Hinglish title when there is one and English otherwise", () => {
    const hi = fixture.titles_hi as Record<string, string>;
    expect(titleFor(byId("tone"), "hinglish", hi)).toBe(hi.tone);
    expect(titleFor(byId("tone"), "english", hi)).toBe(byId("tone").title);
    expect(titleFor(byId("helps"), "hinglish", hi)).toBe(hi.helps);
    expect(titleFor(byId("last_period"), "hinglish", hi)).toBe(byId("last_period").title);
  });
});
