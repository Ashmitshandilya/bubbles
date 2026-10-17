import { describe, expect, it } from "vitest";
import { buildEditBody, editableFields, isChanged } from "./entry-edit";

const weight = { id: "w1", date: "2026-10-05T10:00:00Z", weight: 154.3, notes: "after run", time_of_day: "morning", flag: true, gone: null };

describe("editableFields", () => {
  it("offers numbers and text, never ids, dates, booleans or nulls, with notes last", () => {
    const fields = editableFields(weight);
    expect(fields.map((f) => f.key)).toEqual(["weight", "time_of_day", "notes"]);
    expect(fields[0]).toMatchObject({ kind: "number", value: "154.3", label: "Weight" });
    expect(fields[1].label).toBe("Time of day");
  });
});

describe("buildEditBody", () => {
  const fields = editableFields(weight);
  it("keeps the date and turns numbers back into numbers", () => {
    expect(buildEditBody(fields, { weight: "150" }, weight.date)).toEqual({ date: weight.date, weight: 150, time_of_day: "morning", notes: "after run" });
  });
  it("leaves out a cleared note", () => {
    expect(buildEditBody(fields, { notes: "  " }, weight.date)).toEqual({ date: weight.date, weight: 154.3, time_of_day: "morning" });
  });
  it("refuses a number that is not a number", () => {
    expect(buildEditBody(fields, { weight: "abc" }, weight.date)).toBeNull();
  });
});

describe("isChanged", () => {
  const fields = editableFields(weight);
  it("is false until something differs", () => {
    expect(isChanged(fields, {})).toBe(false);
    expect(isChanged(fields, { weight: "154.3 " })).toBe(false);
    expect(isChanged(fields, { weight: "150" })).toBe(true);
  });
});
