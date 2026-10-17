import { describe, expect, it } from "vitest";
import { fromAssociation, fromPattern, fromToday, itemFromSearch, sureness } from "./detail";

describe("insight detail", () => {
  it("uses one scale for every surface and reads an unknown level as the weakest", () => {
    expect(sureness("High")).toBe("Steadier");
    expect(sureness("strong")).toBe("Steadier");
    expect(sureness("Medium")).toBe("Fairly steady");
    expect(sureness("moderate")).toBe("Fairly steady");
    expect(sureness("Low")).toBe("Early");
    expect(sureness("???")).toBe("Early");
  });

  it("turns a pattern card into the same sections", () => {
    const d = fromPattern({ key: "r-x-sleep", headline: "Sleep came up 6 times", confidence: "Medium", signals: [], window: "1 Oct – 9 Oct", evidence: ["Logged 6 times."], note: "Repeating is not a sign of anything wrong." });
    expect(d.id).toBe("r-x-sleep");
    expect(d.how.word).toBe("Fairly steady");
    expect(d.table?.rows).toEqual([["Logged 6 times."]]);
    expect(d.not.length).toBeGreaterThan(1);
  });

  it("builds an association table from its own numbers and never claims a cause", () => {
    const d = fromAssociation({ id: "sleep_hours->mood", status: "ok", strength: "weak", direction: "up", domains: ["sleep_hours", "mood"], lag_days: 1, n_days: 12, text: "Sleep and mood may be linked (12 days logged). Not a cause." });
    expect(d.title).toBe("Sleep and mood may be linked");
    expect(d.table?.rows).toContainEqual(["Days with both logged", "12"]);
    expect(d.table?.rows).toContainEqual(["Gap between them", "1 day"]);
    expect(d.how.word).toBe("Early");
    expect(d.not.join(" ")).toMatch(/does not mean one thing causes/);
  });

  it("states a gap, not made-up numbers, for a Today item", () => {
    const d = fromToday({ id: "insight-0", title: "You slept less this week." });
    expect(d.table).toBeNull();
    expect(d.gap).toMatch(/Patterns page/);
  });

  it("accepts only short URL-safe ids from the address", () => {
    expect(itemFromSearch("?item=sleep_hours->mood")).toBe("sleep_hours->mood");
    expect(itemFromSearch("?item=r-symptom-headache")).toBe("r-symptom-headache");
    expect(itemFromSearch("?item=<script>")).toBeNull();
    expect(itemFromSearch("")).toBeNull();
  });
});
