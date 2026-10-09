import { describe, expect, it } from "vitest";
import { appetiteWords, blankForm, byDoseUrgency, formFromSchedule, scheduleToBody, weekdaysText } from "./wellness-meds";
import type { Schedule } from "./wellness-types";

const form = (over = {}) => ({ ...blankForm("2026-10-08"), name: "Metformin", ...over });

describe("scheduleToBody", () => {
  it("builds a regular schedule", () => {
    const r = scheduleToBody(form({ dose_label: "500 mg", times: ["08:00", "20:00"], weekdays: [4, 0], pill_count: "30", refill_alert_days: "5" }));
    if (!("body" in r)) throw new Error("expected body");
    expect(r.body).toMatchObject({ name: "Metformin", kind: "regular", times: ["08:00", "20:00"], weekdays: [0, 4], pill_count: 30, refill_alert_days: 5, dose_label: "500 mg" });
  });
  it("sends blank optional fields as empty so an edit can clear them", () => {
    const r = scheduleToBody(form());
    if (!("body" in r)) throw new Error("expected body");
    expect(r.body).toMatchObject({ pill_count: null, refill_alert_days: null, units_per_dose: null, end_date: "", dose_label: "" });
  });
  it("needs a name and a time (except as-needed)", () => {
    expect(scheduleToBody(form({ name: " " }))).toEqual({ errors: { name: "Add the medicine's name." } });
    const noTime = scheduleToBody(form({ times: [] }));
    expect("errors" in noTime && noTime.errors.times).toMatch(/at least one time/);
    const prn = scheduleToBody(form({ kind: "as_needed", times: [] }));
    if (!("body" in prn)) throw new Error("expected body");
    expect(prn.body.times).toEqual([]);
  });
  it("rejects bad times, dates and numbers", () => {
    const bad = scheduleToBody(form({ times: ["8am"], end_date: "2026-01-01", pill_count: "-3", refill_alert_days: "99", units_per_dose: "50" }));
    expect("errors" in bad && Object.keys(bad.errors).sort()).toEqual(["end_date", "pill_count", "refill_alert_days", "times", "units_per_dose"]);
  });
  it("keeps a weekly injection to one day and one time", () => {
    const r = scheduleToBody(form({ kind: "glp1", weekdays: [1, 3], times: ["09:00", "10:00"] }));
    expect("errors" in r && r.errors.weekdays).toBeTruthy();
    expect("errors" in r && r.errors.times).toBeTruthy();
    expect(scheduleToBody(form({ kind: "glp1", weekdays: [1], times: ["09:00"] }))).toHaveProperty("body");
  });
  it("needs prescriber steps for a stepped plan and dates for a pill pack", () => {
    const taper = scheduleToBody(form({ kind: "taper", taper_steps: [{ from_date: "2026-10-08", dose_label: "" }] }));
    expect("errors" in taper && taper.errors.taper).toMatch(/dose written on your plan/);
    const ok = scheduleToBody(form({ kind: "taper", taper_steps: [{ from_date: "2026-10-08", dose_label: " 10 mg " }] }));
    if (!("body" in ok)) throw new Error("expected body");
    expect(ok.body.taper_steps).toEqual([{ from_date: "2026-10-08", dose_label: "10 mg" }]);
    const pack = scheduleToBody(form({ kind: "cycle_pill", cycle_pack_start: "" }));
    expect("errors" in pack && pack.errors.cycle).toBeTruthy();
  });
});

describe("formFromSchedule", () => {
  const s: Schedule = { id: "a".repeat(12), name: "Iron", kind: "regular", active: true, times: ["09:00"], weekdays: [1], pill_count: 12, units_per_dose: 2, refill_alert_days: 7 };
  it("round-trips", () => {
    const f = formFromSchedule(s, "2026-10-08");
    expect(f).toMatchObject({ name: "Iron", times: ["09:00"], weekdays: [1], pill_count: "12", units_per_dose: "2", refill_alert_days: "7", start_date: "2026-10-08" });
    const r = scheduleToBody(f);
    expect("body" in r && r.body).toMatchObject({ name: "Iron", pill_count: 12, units_per_dose: 2 });
  });
  it("shows default units as blank", () => {
    expect(formFromSchedule({ ...s, units_per_dose: 1 }, "2026-10-08").units_per_dose).toBe("");
  });
});

describe("dose list order and words", () => {
  it("puts things that need attention first", () => {
    const items = [
      { status: "taken" as const, time: "08:00" },
      { status: "upcoming" as const, time: "21:00" },
      { status: "due" as const, time: "12:00" },
      { status: "late" as const, time: "09:00" },
    ];
    expect([...items].sort(byDoseUrgency).map((i) => i.status)).toEqual(["late", "due", "upcoming", "taken"]);
  });
  it("describes weekdays", () => {
    expect(weekdaysText([])).toBe("Every day");
    expect(weekdaysText([0, 1, 2, 3, 4, 5, 6])).toBe("Every day");
    expect(weekdaysText([0, 2])).toBe("Mon, Wed");
  });
  it("describes appetite", () => {
    expect(appetiteWords(1)).toBe("Very low");
    expect(appetiteWords(5)).toBe("Strong");
  });
});
