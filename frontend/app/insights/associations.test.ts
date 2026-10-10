// Run: npx vitest run app/insights/associations.test.ts
import { describe, expect, it } from "vitest";
import { caveats, closestGap, directionInfo, emptyProgressLine, loggedDaysLine, sentence, strengthSteps, whatToTry } from "./associations";

describe("association card pieces", () => {
  it("maps strength to bar steps and never promotes an unknown word", () => {
    expect([strengthSteps("weak"), strengthSteps("moderate"), strengthSteps("strong"), strengthSteps("huge")]).toEqual([1, 2, 3, 1]);
  });

  it("describes direction without implying a cause", () => {
    expect(directionInfo("up")?.arrow).toBe("up");
    expect(directionInfo("down")?.text).toMatch(/higher when the other is lower/);
    expect(directionInfo(undefined)).toBeNull();
    for (const d of ["up", "down"]) expect(directionInfo(d)?.text).not.toMatch(/cause|because|leads? to|improv/i);
  });

  it("offers a neutral next step that names both things and gives no advice", () => {
    const line = whatToTry({ domains: ["sleep_hours", "mood"] });
    expect(line).toContain("sleep and mood");
    expect(line).not.toMatch(/should|take|dose|mg|cause|because/i);
    expect(whatToTry({})).toMatch(/Keep logging/);
  });

  it("splits the server text into sentence and caveats", () => {
    const text = "On days after you slept less, your logged mood tended to be higher (31 days logged). Mood is self-rated. It is an association.";
    expect(sentence(text)).toBe("On days after you slept less, your logged mood tended to be higher");
    expect(caveats(text)).toBe("Mood is self-rated. It is an association.");
    expect(caveats("Just one sentence")).toBe("");
  });
});

describe("honest empty state", () => {
  const gaps = [
    { id: "a", text: "", domains: ["activity_minutes", "mood"], n_days: 3, need: 10 },
    { id: "b", text: "", domains: ["sleep_hours", "mood"], n_days: 7, need: 10 },
    { id: "c", text: "no counts" },
  ];

  it("picks the pair closest to checkable and counts the days still needed from the response", () => {
    const p = closestGap(gaps)!;
    expect(p.pair).toBe("sleep and mood");
    expect(p.remaining).toBe(3);
    expect(p.fraction).toBeCloseTo(0.7);
    expect(emptyProgressLine(p)).toBe("sleep and mood: 7 of 10 days logged together. About 3 more days of both, then Bubbles can check this link.");
  });

  it("invents no number when the response has none", () => {
    expect(closestGap([])).toBeNull();
    expect(closestGap([{ id: "x", text: "", domains: ["mood"], n_days: 2, need: 10 }])).toBeNull();
    expect(emptyProgressLine(null)).not.toMatch(/\d/);
  });

  it("never reports a negative remainder or a bar over 100%", () => {
    const p = closestGap([{ id: "x", text: "", domains: ["mood", "sleep_hours"], n_days: 14, need: 10 }])!;
    expect(p.remaining).toBe(0);
    expect(p.fraction).toBe(1);
  });

  it("summarises what is logged, busiest first, and says nothing when nothing is", () => {
    expect(loggedDaysLine({ mood: 3, sleep_hours: 12, hydration_ml: 5, calories: 1 })).toBe("In this window you logged sleep on 12 days, drinks on 5 days and mood on 3 days.");
    expect(loggedDaysLine({ mood: 1 })).toBe("In this window you logged mood on 1 day.");
    expect(loggedDaysLine({})).toBeNull();
    expect(loggedDaysLine(undefined)).toBeNull();
  });
});
