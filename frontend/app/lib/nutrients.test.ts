// Run: npx vitest run app/lib/nutrients.test.ts
import { describe, expect, it } from "vitest";
import { LEVEL_TEXT, noteForLab, readLabNotes, readNudges } from "./nutrients";

const serverShape = {
  status: "success",
  nudges: [
    {
      id: "iron", name: "Iron", kind: "signs", level: "medium", headline: "Iron might be worth a blood test",
      reasons: ["You logged feeling tired on 3 of the last 30 days."], gaps: ["No recent ferritin or haemoglobin result is logged yet."],
      ask: "An iron blood test (ferritin and haemoglobin) could tell. It is worth asking a doctor about.", foods: ["ragi"],
    },
  ],
  lab_notes: [
    { entry: "iron", entry_name: "Iron", label: "Ferritin", status: "below", text: "Your Ferritin of 6 ng/mL is below the range you entered (15 to 150).", date: "2026-10-01", ask: "Worth going over it with a doctor." },
    { entry: "thyroid", label: "TSH", status: "within", text: "Your TSH of 2 mIU/L is inside the range you entered (0.4 to 4).", date: "2026-09-20", ask: null },
  ],
  unavailable: [],
};

describe("readNudges", () => {
  it("keeps the server's wording, level, reasons and gaps", () => {
    const [n] = readNudges(serverShape);
    expect(n).toEqual({
      id: "iron", headline: "Iron might be worth a blood test", level: "medium",
      reasons: ["You logged feeling tired on 3 of the last 30 days."], gaps: ["No recent ferritin or haemoglobin result is logged yet."],
      ask: "An iron blood test (ferritin and haemoglobin) could tell. It is worth asking a doctor about.",
    });
  });

  it("returns nothing, never a made-up row, for an empty or odd answer", () => {
    for (const raw of [null, undefined, 3, "x", [], {}, { nudges: null }, { nudges: [null, 4, {}, { headline: "" }] }]) expect(readNudges(raw)).toEqual([]);
  });

  it("treats an unknown level as the softer one and drops non-text lines", () => {
    const [n] = readNudges({ nudges: [{ headline: "Zinc might be worth a blood test", level: "high", reasons: ["a", 5, null, " "], gaps: "no" }] });
    expect(n.level).toBe("low");
    expect(n.reasons).toEqual(["a"]);
    expect(n.gaps).toEqual([]);
    expect(LEVEL_TEXT.low).not.toBe(LEVEL_TEXT.medium);
  });
});

describe("lab notes", () => {
  const notes = readLabNotes(serverShape);

  it("reads the notes the server wrote and nothing else", () => {
    expect(notes.map((n) => [n.label, n.status, n.date])).toEqual([["Ferritin", "below", "2026-10-01"], ["TSH", "within", "2026-09-20"]]);
    expect(readLabNotes({ lab_notes: [{ label: "X", status: "great", text: "hi" }, { status: "below" }, null] })).toEqual([]);
    expect(readLabNotes(undefined)).toEqual([]);
  });

  it("matches a lab row by test name and day, so an older result of the same test gets no note", () => {
    expect(noteForLab(notes, "ferritin", "2026-10-01T08:00:00+00:00")?.ask).toBe("Worth going over it with a doctor.");
    expect(noteForLab(notes, "Ferritin", "2026-06-01")).toBeNull();
    expect(noteForLab(notes, "Creatinine", "2026-10-01")).toBeNull();
    expect(noteForLab(notes, "Ferritin", undefined)).toBeNull();
  });
});
