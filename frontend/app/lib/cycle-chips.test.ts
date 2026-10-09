import { describe, expect, it } from "vitest";
import { addCustom, searchChips, selectedChips, selectedCounts, toggleId } from "./cycle-chips";
import type { ChipGroup } from "./cycle-types";

const chip = (id: string, label: string, group: string, keywords: string[] = []) => ({ id, label, group, keywords, signal: "symptom" });
const GROUPS: ChipGroup[] = [
  { id: "body", label: "Body", chips: [chip("cramps", "Cramps", "body", ["period pain", "abdominal"]), chip("headache", "Headache", "body", ["migraine"]), chip("lower_back_pain", "Lower back pain", "body")] },
  { id: "mood", label: "Mood", chips: [chip("anxious", "Anxious", "mood", ["worried", "nervous"]), chip("calm", "Calm", "mood")] },
];

describe("searchChips", () => {
  it("returns nothing for a blank query", () => {
    expect(searchChips(GROUPS, "")).toEqual([]);
    expect(searchChips(GROUPS, "   ")).toEqual([]);
  });

  it("matches labels, keywords and ids live", () => {
    expect(searchChips(GROUPS, "cra").map((c) => c.id)).toEqual(["cramps"]);
    expect(searchChips(GROUPS, "migraine").map((c) => c.id)).toEqual(["headache"]);
    expect(searchChips(GROUPS, "lower_back").map((c) => c.id)).toEqual(["lower_back_pain"]);
    expect(searchChips(GROUPS, "NERVOUS").map((c) => c.id)).toEqual(["anxious"]);
  });

  it("needs every word to match", () => {
    expect(searchChips(GROUPS, "back pain").map((c) => c.id)).toEqual(["lower_back_pain"]);
    expect(searchChips(GROUPS, "back anxious")).toEqual([]);
  });

  it("ranks label-prefix matches first and respects the limit", () => {
    const ranked = searchChips(GROUPS, "pain").map((c) => c.id);
    expect(ranked[0]).toBe("lower_back_pain");
    expect(ranked).toContain("cramps");
    expect(searchChips(GROUPS, "a", 2)).toHaveLength(2);
  });
});

describe("selection", () => {
  it("toggles without mutating", () => {
    const ids = ["cramps"];
    expect(toggleId(ids, "calm")).toEqual(["cramps", "calm"]);
    expect(toggleId(ids, "cramps")).toEqual([]);
    expect(ids).toEqual(["cramps"]);
  });

  it("resolves selected labels, keeping unknown ids readable", () => {
    expect(selectedChips(GROUPS, ["calm", "old_thing"])).toEqual([{ id: "calm", label: "Calm" }, { id: "old_thing", label: "old thing" }]);
  });

  it("counts selections per group", () => {
    expect(selectedCounts(GROUPS, ["cramps", "headache", "calm"])).toEqual({ body: 2, mood: 1 });
  });
});

describe("addCustom", () => {
  it("trims and adds", () => {
    expect(addCustom([], "  tired   legs ")).toEqual({ ok: true, list: ["tired legs"] });
  });

  it("rejects blank, duplicate, too long and too many", () => {
    expect(addCustom([], " ").ok).toBe(false);
    expect(addCustom(["Tired"], "tired")).toEqual({ ok: false, error: "You already added that." });
    expect(addCustom([], "x".repeat(41)).ok).toBe(false);
    expect(addCustom([], "x".repeat(40)).ok).toBe(true);
    const ten = Array.from({ length: 10 }, (_, i) => `item${i}`);
    expect(addCustom(ten, "one more").ok).toBe(false);
  });
});
