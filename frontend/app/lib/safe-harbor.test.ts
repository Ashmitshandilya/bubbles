import { describe, expect, it } from "vitest";
import { adaptHarbor, dialNumber, telHref } from "./safe-harbor";

const served = {
  tier: 3,
  mode: "disclosure",
  step: "options",
  resources: [
    { name: "Emergency services", number: "112", note: "Police, fire and ambulance." },
    { name: "Women Helpline", number: "181", note: "Free." },
    { name: "NCW women helpline", number: "14490", note: "Free." },
  ],
  actions: [
    { id: "talk_more", label: "I want to talk more" },
    { id: "safety_plan", label: "Help me make a safety plan" },
    { id: "show_help", label: "Show me who can help" },
    { id: "okay_for_now", label: "I'm okay for now" },
  ],
};

describe("adaptHarbor", () => {
  it("reads the payload the server sends", () => {
    const h = adaptHarbor(served)!;
    expect(h.tier).toBe(3);
    expect(h.resources.map((r) => r.number)).toEqual(["112", "181", "14490"]);
    expect(h.actions.map((a) => a.id)).toEqual(["talk_more", "safety_plan", "show_help", "okay_for_now"]);
  });

  it("is null for an ordinary reply", () => {
    expect(adaptHarbor(undefined)).toBeNull();
    expect(adaptHarbor(null)).toBeNull();
    expect(adaptHarbor("harbor")).toBeNull();
    expect(adaptHarbor([])).toBeNull();
  });

  it("shows only 112 when the server sent no resources", () => {
    for (const resources of [[], undefined, "x", [{ name: "" }, null, 4]]) {
      const h = adaptHarbor({ ...served, resources })!;
      expect(h.resources).toHaveLength(1);
      expect(h.resources[0].number).toBe("112");
    }
  });

  it("treats an unknown tier as tier 2 and does not crash", () => {
    for (const tier of [0, 1, 4, "3", "high", null, undefined, {}]) {
      expect(adaptHarbor({ ...served, tier })!.tier).toBe(2);
    }
  });

  it("keeps a resource with no number as words only", () => {
    const h = adaptHarbor({ ...served, resources: [{ name: "your local emergency number", number: "", note: "Not shown as a number yet." }] })!;
    expect(h.resources).toEqual([{ name: "your local emergency number", number: "", note: "Not shown as a number yet." }]);
  });

  it("drops actions that cannot be sent and caps the list", () => {
    const h = adaptHarbor({ ...served, actions: [{ id: "a" }, { label: "b" }, null, ...Array.from({ length: 9 }, (_, i) => ({ id: `x${i}`, label: `Label ${i}` }))] })!;
    expect(h.actions).toHaveLength(5);
    expect(h.actions[0].id).toBe("x0");
  });

  it("closed step has no chips", () => {
    expect(adaptHarbor({ ...served, step: "closed", actions: [] })!.actions).toEqual([]);
  });
});

describe("telHref", () => {
  it("builds a tel link for real helpline numbers", () => {
    expect(telHref("112")).toBe("tel:112");
    expect(telHref(" 14490 ")).toBe("tel:14490");
    expect(telHref("1098")).toBe("tel:1098");
  });

  it("builds nothing for words or unsafe text", () => {
    for (const bad of ["", "  ", "call me", "112; rm", "javascript:alert(1)", "tel:112", "1", "1234567", null, undefined, 112]) {
      expect(telHref(bad)).toBeNull();
    }
  });

  it("strips spacing but keeps a plus", () => {
    expect(dialNumber("+91 112")).toBe("+91112");
    expect(dialNumber("1-1-2")).toBe("112");
  });
});
