import { describe, expect, it } from "vitest";
import { countLabel, memoryItems } from "./memory";

describe("countLabel", () => {
  it("shows a gap as null, never as zero", () => {
    expect(countLabel(undefined)).toBeNull();
    expect(countLabel(null)).toBeNull();
    expect(countLabel(Number.NaN)).toBeNull();
    expect(countLabel(0)).toBe("0");
    expect(countLabel(12)).toBe("12");
    expect(countLabel(200)).toBe("200+");
  });
});

describe("memoryItems", () => {
  it("titles an item from its own name and lists a few simple fields, hiding metadata", () => {
    const [item] = memoryItems([
      { id: "e1", event_type: "symptom", extracted_data: { name: "headache", severity: 6, _prov: "x", source_id: "y", note: "", side: "left" }, created_at: "2026-10-01T10:00:00Z", extraction_status: "pending" },
    ]);
    expect(item).toMatchObject({ id: "e1", kind: "Symptom", title: "Headache", detail: "Severity: 6 · Side: left", confirmed: false });
  });

  it("counts either confirmation flag as confirmed", () => {
    const items = memoryItems([
      { id: "a", event_type: "sleep", user_confirmed: true },
      { id: "b", event_type: "sleep", extraction_status: "confirmed" },
      { id: "c", event_type: "sleep", extraction_status: "pending" },
    ]);
    expect(items.map((i) => i.confirmed)).toEqual([true, true, false]);
  });

  it("falls back to the event type, keeps id-less rows read-only, and survives nothing at all", () => {
    expect(memoryItems([{ event_type: "mood_log", extracted_data: null }])[0]).toMatchObject({ id: null, title: "Mood log", detail: "" });
    expect(memoryItems(undefined)).toEqual([]);
  });
});
