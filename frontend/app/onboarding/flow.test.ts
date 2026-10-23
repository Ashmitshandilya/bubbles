import { describe, expect, it } from "vitest";
import fixture from "./bank.fixture.json";
import {
  advancesOnPick, ageOn, buildScreens, countryFromTimeZone, isAnswered, isRequired, matches, missingRequired, pendingPatch, pick, progressLabel, resumeIndex,
  screenQuestions, titleFor, visibleOptions, visibleQuestions, type Answers, type Question,
} from "./flow";

const questions = fixture.questions as unknown as Question[];
const titles = fixture.screens as Record<string, string>;
const today = new Date(2026, 9, 15);
const byId = (id: string) => questions.find((q) => q.id === id)!;
const screensOf = (answers: Answers, editing = false) => buildScreens(questions, titles, answers, today, editing);

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
    expect(visibleOptions(byId("main_goal"), male, today).map((o) => o.id)).not.toContain("cycle");
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

describe("screens", () => {
  it("opens on the gender question with the language row beside it, then the date of birth with the name", () => {
    const screens = screensOf({});
    expect(screens[0]).toMatchObject({ id: "first", ids: ["body", "language", "country"] });
    expect(screens[1]).toMatchObject({ id: "about", ids: ["birth_date", "preferred_name"] });
  });

  it("puts 'Your choices' after the required core and the optional extras after a stage intro", () => {
    const screens = screensOf({ body: "male", birth_date: "1990-01-01" });
    const choices = screens.findIndex((s) => s.kind === "choices");
    expect(screens.slice(0, choices).every((s) => s.kind === "questions" && s.stage === "core")).toBe(true);
    expect(screens[choices + 1].kind).toBe("extras-intro");
    expect(new Set(screens.slice(choices + 2).map((s) => s.stage))).toEqual(new Set(["extras"]));
  });

  it("never shows the screening questions on a first run, only when editing", () => {
    const answers = { body: "female", birth_date: "1990-01-01" };
    const ids = (editing: boolean) => screensOf(answers, editing).flatMap((s) => s.ids);
    expect(ids(false)).not.toContain("cervical_screen");
    expect(ids(true)).toContain("cervical_screen");
    expect(screensOf(answers, true).some((s) => s.kind !== "questions")).toBe(false);
  });

  it("asks the list of conditions only after a yes, as a follow-up", () => {
    const no = screensOf({ body: "male", birth_date: "1990-01-01", conditions_any: "no" });
    expect(no.flatMap((s) => s.ids)).not.toContain("conditions");
    const yes = screensOf({ body: "male", birth_date: "1990-01-01", conditions_any: "yes" });
    const follow = yes.find((s) => s.ids.includes("conditions"))!;
    expect(follow.followUp).toBe(true);
    expect(yes.indexOf(follow)).toBe(yes.findIndex((s) => s.ids.includes("conditions_any")) + 1);
  });

  it("groups the optional extras into a few screens", () => {
    const extras = screensOf({ body: "female", birth_date: "1990-01-01" }).filter((s) => s.stage === "extras" && s.kind === "questions");
    expect(extras.map((s) => s.id)).toEqual(["identity", "body_basics", "food", "health_basics", "cycle", "talk", "support"]);
    expect(extras.find((s) => s.id === "food")!.ids).toEqual(["diet_style", "recent_blood_test"]);
    expect(extras.every((s) => screenQuestions(s, questions).every((q) => !q.required))).toBe(true);
  });
});

describe("what is required", () => {
  it("is the same list for every body except periods, which only a female body must answer", () => {
    const female = { body: "female", birth_date: "1990-01-01" };
    const other = { body: "other", birth_date: "1990-01-01" };
    expect(isRequired(byId("periods"), female, today)).toBe(true);
    expect(isRequired(byId("periods"), other, today)).toBe(false);
    expect(missingRequired(visibleQuestions(questions, female, today), female, today)).toEqual(["language", "preferred_name", "main_goal", "conditions_any", "sleep_pattern", "stress_level", "periods"]);
    expect(missingRequired(visibleQuestions(questions, other, today), other, today)).not.toContain("periods");
  });

  it("knows what counts as answered", () => {
    expect(isAnswered(byId("sleep_pattern"), "under_6")).toBe(true);
    expect(isAnswered(byId("conditions"), [])).toBe(false);
    expect(isAnswered(byId("height_weight"), {})).toBe(false);
    expect(isAnswered(byId("height_weight"), { height_cm: 160 })).toBe(true);
    expect(isAnswered(byId("preferred_name"), "")).toBe(false);
  });
});

/** Answers every required question the way a person who only does what is needed would: one tap (or one field) per screen. */
function scriptedRun(body: string, age = 32): { taps: number; visited: string[]; answers: Answers } {
  const answers: Answers = { language: "english" };
  const visited: string[] = [];
  for (let guard = 0; guard < 40; guard++) {
    const screens = screensOf(answers);
    const screen = visited.length === 0
      ? screens[0]
      : screens.find((s) => s.kind === "questions" && s.stage === "core" && missingRequired(screenQuestions(s, questions), answers, today).length > 0);
    if (!screen) break;
    visited.push(screen.id);
    for (const q of screenQuestions(screen, questions)) {
      if (q.id === "body") answers.body = body;
      else if (q.id === "birth_date") answers.birth_date = `${2026 - age}-01-01`;
      else if (q.id === "preferred_name") answers.preferred_name = "Riya";
      else if (q.type === "single" && isRequired(q, answers, today)) answers[q.id] = visibleOptions(q, answers, today)[0].id;
    }
  }
  return { taps: visited.length + 1, visited, answers };       // +1 for "Your choices", which is one tap (Not now or Continue)
}

describe("a scripted run that answers only what is needed", () => {
  it("finishes in at most 8 taps for every body", () => {
    for (const body of ["female", "male", "trans", "other", "prefer_not"]) {
      const run = scriptedRun(body);
      expect(run.taps, `${body}: ${run.visited.join(" > ")}`).toBeLessThanOrEqual(8);
      expect(missingRequired(visibleQuestions(questions, run.answers, today), run.answers, today), body).toEqual([]);
    }
    expect(scriptedRun("female").visited).toEqual(["first", "about", "main_goal", "conditions_any", "sleep_pattern", "stress_level", "periods"]);
    expect(scriptedRun("male").taps).toBe(7);
  });
});

describe("answering", () => {
  it("single choice replaces", () => {
    const q = byId("body");
    expect(pick(q, undefined, "male")).toBe("male");
    expect(pick(q, "male", "female")).toBe("female");
    expect(pick(q, "male", "male")).toBe("male");
  });

  it("multi choice adds, removes, and lets 'none of these' stand alone", () => {
    const q = byId("avoid_topics");
    expect(pick(q, undefined, "weight")).toEqual(["weight"]);
    expect(pick(q, ["weight"], "family")).toEqual(["weight", "family"]);
    expect(pick(q, ["weight", "family"], "weight")).toEqual(["family"]);
    expect(pick(q, ["weight"], "none")).toEqual(["none"]);
    expect(pick(q, ["none"], "weight")).toEqual(["weight"]);
    expect(pick(q, ["weight"], "weight")).toBeUndefined();
  });

  it("a single tap moves on only when nothing else on the screen is waiting", () => {
    const first = screensOf({})[0];
    expect(advancesOnPick(first, questions, "body", { body: "male", language: "english", country: "in" })).toBe(true);
    expect(advancesOnPick(first, questions, "body", { body: "male", language: "english" })).toBe(false);
    const screens = screensOf({ body: "male", birth_date: "1990-01-01" });
    const goal = screens.find((s) => s.id === "main_goal")!;
    expect(advancesOnPick(goal, questions, "main_goal", { main_goal: "sleep" })).toBe(true);
    const food = screens.find((s) => s.id === "food")!;
    expect(advancesOnPick(food, questions, "diet_style", { diet_style: "vegan" })).toBe(false);
    expect(advancesOnPick(food, questions, "recent_blood_test", { diet_style: "vegan", recent_blood_test: "yes" })).toBe(true);
    expect(advancesOnPick(screens.find((s) => s.id === "about")!, questions, "preferred_name", { preferred_name: "R" })).toBe(false);
  });
});

describe("saving", () => {
  const male = { body: "male", language: "english", birth_date: "1990-01-01", preferred_name: "Sam" };

  it("saves nothing before the date of birth is known, then sends body, language and date together", () => {
    const screens = screensOf({});
    expect(pendingPatch(screens, 0, questions, { body: "male", language: "english" }, {}, today)).toBeNull();
    expect(pendingPatch(screens, 1, questions, male, {}, today)).toEqual({ body: "male", language: "english", birth_date: "1990-01-01", preferred_name: "Sam" });
  });

  it("sends only what changed, and null for an optional answer that was cleared", () => {
    const screens = screensOf(male);
    const index = screens.findIndex((s) => s.id === "main_goal");
    expect(pendingPatch(screens, index, questions, { ...male, main_goal: "food" }, male, today)).toEqual({ main_goal: "food" });
    const extra = screens.findIndex((s) => s.id === "talk");
    expect(pendingPatch(screens, extra, questions, { ...male, tone: "calm_direct" }, { ...male, tone: "calm_direct", reply_length: "short" }, today)).toEqual({ reply_length: null });
    expect(pendingPatch(screens, index, questions, male, { ...male, main_goal: "food" }, today)).toEqual({});
  });

  it("never clears a required answer", () => {
    const screens = screensOf(male);
    const index = screens.findIndex((s) => s.id === "stress_level");
    expect(pendingPatch(screens, index, questions, male, { ...male, stress_level: "low" }, today)).toEqual({});
  });
});

describe("progress and resuming", () => {
  it("counts the required core only, and says so for follow-ups, choices and extras", () => {
    const answers = { body: "female", birth_date: "1990-01-01", conditions_any: "yes" };
    const screens = screensOf(answers);
    const at = (id: string) => screens.findIndex((s) => s.id === id);
    expect(screens.filter((s) => s.kind === "questions" && s.stage === "core" && !s.followUp).length).toBe(7);
    expect(progressLabel(screens, at("first"), answers)).toBe("Question 1 of 7");
    expect(progressLabel(screens, at("first"), {})).toBe("Question 1");
    expect(progressLabel(screens, at("sleep_pattern"), answers)).toBe("Question 5 of 7");
    expect(progressLabel(screens, at("conditions"), answers)).toBe("A quick follow-up");
    expect(progressLabel(screens, at("choices"), answers)).toBe("Your choices");
    expect(progressLabel(screens, at("food"), answers)).toBe("A few extras (skip any)");
  });

  it("resumes at the first required question still open, else at the choices or the extras", () => {
    const answers = { body: "male", language: "english", birth_date: "1990-01-01", preferred_name: "Sam", main_goal: "sleep" };
    const screens = screensOf(answers);
    expect(screens[resumeIndex(screens, questions, answers, false, today)].id).toBe("conditions_any");
    const done = { ...answers, conditions_any: "no", sleep_pattern: "six_seven", stress_level: "low" };
    const all = screensOf(done);
    expect(all[resumeIndex(all, questions, done, false, today)].kind).toBe("choices");
    expect(all[resumeIndex(all, questions, done, true, today)].kind).toBe("extras-intro");
  });
});

describe("language", () => {
  it("uses the Hinglish title when there is one and English otherwise", () => {
    const hi = fixture.titles_hi as Record<string, string>;
    expect(titleFor(byId("tone"), "hinglish", hi)).toBe(hi.tone);
    expect(titleFor(byId("tone"), "english", hi)).toBe(byId("tone").title);
    expect(titleFor(byId("last_period"), "hinglish", hi)).toBe(byId("last_period").title);
  });
});

describe("country", () => {
  it("starts from India only for an Indian time zone, and never asks a server", () => {
    expect(countryFromTimeZone("Asia/Kolkata")).toBe("in");
    expect(countryFromTimeZone("Asia/Calcutta")).toBe("in");
    expect(countryFromTimeZone("America/New_York")).toBeUndefined();
    expect(countryFromTimeZone(undefined)).toBeUndefined();
  });

  it("is an optional question beside language, and the state is asked only in India", () => {
    expect(byId("country").required).toBe(false);
    expect(visibleQuestions(questions, { country: "in" }, today).map((q) => q.id)).toContain("region");
    expect(visibleQuestions(questions, { country: "us" }, today).map((q) => q.id)).not.toContain("region");
    expect(missingRequired(visibleQuestions(questions, {}, today), {}, today)).not.toContain("country");
  });

  it("the self-description appears only when chosen", () => {
    expect(visibleQuestions(questions, { gender: "woman" }, today).map((q) => q.id)).not.toContain("gender_other");
    expect(visibleQuestions(questions, { gender: "self_describe" }, today).map((q) => q.id)).toContain("gender_other");
  });
});
