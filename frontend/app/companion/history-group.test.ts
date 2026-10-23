import { describe, expect, it } from "vitest";
import { groupByMode } from "./history";

const c = (id: string, mode?: "talk" | "orbit") => ({ id, title: id, when: "Today", mode });

describe("groupByMode", () => {
  it("keeps one plain list when there is no Heart-to-heart", () => {
    expect(groupByMode([c("a"), c("b", "talk")])).toEqual([{ label: null, items: [c("a"), c("b", "talk")] }]);
  });
  it("splits Talk from Heart-to-heart, keeping order", () => {
    const groups = groupByMode([c("a", "orbit"), c("b", "talk"), c("c", "orbit")]);
    expect(groups.map((g) => [g.label, g.items.map((i) => i.id)])).toEqual([["Talk", ["b"]], ["Heart-to-heart", ["a", "c"]]]);
  });
  it("shows only the Heart-to-heart heading when that is all there is", () => {
    expect(groupByMode([c("a", "orbit")]).map((g) => g.label)).toEqual(["Heart-to-heart"]);
  });
});
