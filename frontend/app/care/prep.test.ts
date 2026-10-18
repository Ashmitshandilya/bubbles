import { describe, expect, it } from "vitest";
import type { Entry } from "../../components/tracking/data";
import { addQuestion, afterDay, labRangeStatus, questionsText, recordRows, summaryText, typeCounts, visitLabel, visitSplit, whenText } from "./prep";

const entry = (id: string, date: string, extra: Record<string, string | number | null> = {}): Entry => ({ id, date, ...extra });
const NOW = new Date(2026, 9, 10, 12, 0, 0); // 10 Oct 2026, local

describe("visitSplit", () => {
  it("finds the newest past visit and the soonest upcoming one, ignoring undated rows", () => {
    const visits = [entry("a", "2026-08-01"), entry("b", "2026-09-20"), entry("c", "2026-11-02"), entry("d", "2026-12-01"), entry("e", "")];
    const { last, next } = visitSplit(visits, NOW);
    expect(last?.id).toBe("b");
    expect(next?.id).toBe("c");
  });

  it("is null on both sides when nothing is logged", () => {
    expect(visitSplit([], NOW)).toEqual({ last: null, next: null });
  });
});

describe("afterDay", () => {
  const items = [{ date: "2026-09-19" }, { date: "2026-09-20" }, { date: "2026-09-20T18:00:00" }, { date: "2026-09-21" }, { date: "" }, {}];
  it("keeps only items logged after the visit day, and drops undated ones", () => {
    expect(afterDay(items, "2026-09-20")).toEqual([{ date: "2026-09-21" }]);
  });
  it("is empty for an unreadable visit date", () => {
    expect(afterDay(items, "nonsense")).toEqual([]);
  });
});

describe("typeCounts", () => {
  it("counts by type, most frequent first, ties alphabetical", () => {
    expect(typeCounts([{ event_type: "sleep" }, { event_type: "symptom" }, { event_type: "symptom" }, { event_type: "mood" }, {}])).toEqual([
      ["symptom", 2],
      ["entry", 1],
      ["mood", 1],
      ["sleep", 1],
    ]);
  });
});

describe("labRangeStatus", () => {
  it("compares against the range entered and nothing else", () => {
    expect(labRangeStatus(entry("l", "", { value: 8, reference_range: "15-150" }))).toEqual({ status: "below", range: "15-150" });
    expect(labRangeStatus(entry("l", "", { value: 200, reference_range: "15-150" })).status).toBe("above");
    expect(labRangeStatus(entry("l", "", { value: 15, reference_range: "15-150" })).status).toBe("within");
  });
  it("shows a gap, not a verdict, when the range or the number is missing", () => {
    expect(labRangeStatus(entry("l", "", { value: 8 }))).toEqual({ status: "none", range: null });
    expect(labRangeStatus(entry("l", "", { reference_range: "15-150" }))).toEqual({ status: "none", range: "15-150" });
  });
});

describe("recordRows", () => {
  it("lists newest first and shows missing names as a gap", () => {
    const rows = recordRows("medications", [entry("old", "2026-01-01", { name: "A" }), entry("new", "2026-06-01", { dosage: "10 mg" }), entry("undated", "", { name: "C" })]);
    expect(rows.map((r) => r.id)).toEqual(["new", "old", "undated"]);
    expect(rows[0]).toMatchObject({ title: "Unnamed medicine", meta: "10 mg" });
  });

  it("attaches a range status to labs only", () => {
    const [lab] = recordRows("labs", [entry("l", "2026-09-01", { test_name: "Ferritin", value: 8, unit: "ng/mL", reference_range: "15-150" })]);
    expect(lab.title).toBe("Ferritin");
    expect(lab.meta).toContain("8 ng/mL");
    expect(lab.range?.status).toBe("below");
    expect(lab.date).toBe("2026-09-01");
    expect(recordRows("allergies", [entry("x", "", { allergen: "Penicillin" })])[0].range).toBeUndefined();
  });
});

describe("text helpers", () => {
  it("never produces an em dash for a missing date", () => {
    expect(whenText("")).toBe("No date");
    expect(whenText("garbage")).toBe("No date");
    expect(whenText("2026-09-20")).not.toContain("—");
  });
  it("labels a visit from whatever was filled in", () => {
    expect(visitLabel(entry("v", "", { doctor_name: "Dr Rao", reason: "Follow-up" }))).toBe("Dr Rao · Follow-up");
    expect(visitLabel(entry("v", ""))).toBe("");
  });
  it("numbers the questions, or sends nothing", () => {
    expect(questionsText(["A?", "B?"])).toBe("Questions for my visit:\n1. A?\n2. B?");
    expect(questionsText([])).toBe("");
  });
  it("adds a trimmed, capped, non-duplicate question", () => {
    expect(addQuestion(["Why?"], "  how long?  ")).toEqual(["Why?", "how long?"]);
    expect(addQuestion(["Why?"], "WHY?")).toEqual(["Why?"]);
    expect(addQuestion(["Why?"], "   ")).toEqual(["Why?"]);
    expect(addQuestion([], "x".repeat(500))[0]).toHaveLength(200);
  });
});

describe("summaryText", () => {
  const base = { generatedOn: "10 Oct 2026", concern: "", lastVisit: null, nextVisit: null, logLine: "Logs in the last 6 months: 0", sinceLine: null, questions: [], bring: [], flagged: [], lists: [], timeline: [] };
  it("says what it is and leaves out sections it has nothing for", () => {
    const out = summaryText(base);
    expect(out.split("\n")).toEqual(["Visit summary prepared with Bubbles, 10 Oct 2026", "Organized from my own logs. Not a diagnosis.", "Logs in the last 6 months: 0"]);
  });
  it("includes what is on file, numbered questions and non-empty lists only", () => {
    const out = summaryText({ ...base, concern: "headaches", lastVisit: "20 Sep 2026", questions: ["Why?"], lists: [{ heading: "Medications I log", rows: ["Iron"] }, { heading: "Allergies I log", rows: [] }] });
    expect(out).toContain("What I want to discuss: headaches");
    expect(out).toContain("Last visit on file: 20 Sep 2026");
    expect(out).toContain("1. Why?");
    expect(out).toContain("Medications I log:\n- Iron");
    expect(out).not.toContain("Allergies I log");
    expect(out).not.toContain("—");
  });
});
