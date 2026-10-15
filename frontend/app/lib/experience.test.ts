import { describe, expect, it } from "vitest";
import { SECTIONS } from "../../components/Navigation";
import { filterSections, gateApplies, gateDecision, readExperience, readSetupState } from "./experience";

const male = readExperience({ body_map: { visible: true, anatomy: "male", reproductive: "none" }, sections: { hidden: ["cycle"] }, cycle: { visible: false }, companion: { name: "Arjun", tone: "calm_direct" } });
const female = readExperience({ body_map: { visible: true, anatomy: "female", reproductive: "uterus_ovaries" }, sections: { hidden: [] }, cycle: { visible: true } });
const trans = readExperience({ body_map: { visible: false, anatomy: "neutral", reproductive: "by_use" }, sections: { hidden: [] }, cycle: { visible: true } });

describe("reading the server's profile", () => {
  it("keeps what it is told", () => {
    expect(male).toMatchObject({ bodyMap: { visible: true, anatomy: "male", reproductive: "none" }, hiddenSections: ["cycle"], cycleVisible: false });
    expect(male?.companion).toMatchObject({ name: "Arjun", tone: "calm_direct", replyLength: "short" });
    expect(female?.bodyMap).toEqual({ visible: true, anatomy: "female", reproductive: "uterus_ovaries" });
    expect(trans?.bodyMap.visible).toBe(false);
  });

  it("falls back to the general experience for anything missing or odd, hiding nothing", () => {
    const empty = readExperience({});
    expect(empty).toMatchObject({ bodyMap: { visible: true, anatomy: "neutral", reproductive: "by_use" }, hiddenSections: [], cycleVisible: true, hideNumbers: false });
    expect(readExperience({ body_map: { anatomy: "alien", reproductive: 5 }, sections: { hidden: "cycle" } })).toMatchObject({ bodyMap: { anatomy: "neutral", reproductive: "by_use" }, hiddenSections: [] });
    expect(readExperience(null)).toBeNull();
    expect(readExperience("x")).toBeNull();
    expect(readExperience([])).toBeNull();
  });

  it("drops malformed care and tracker rows", () => {
    const e = readExperience({ care_checklist: [{ id: "a", title: "T", why: "W", source: "S" }, { id: 1 }, null, "x"], trackers_suggested: [{ tracker: "sleep", why: "y" }, {}, 3] });
    expect(e?.care).toEqual([{ id: "a", title: "T", why: "W", source: "S" }]);
    expect(e?.trackers).toEqual([{ tracker: "sleep", why: "y" }]);
  });
});

describe("the menu follows the person's body", () => {
  const ids = (list: readonly { id: string }[]) => list.map((s) => s.id);

  it("a male body does not get Cycle", () => {
    expect(ids(filterSections(SECTIONS, male))).not.toContain("cycle");
    expect(ids(filterSections(SECTIONS, male))).toEqual(expect.arrayContaining(["today", "talk", "patterns", "track", "fitness", "care"]));
  });

  it("a female body gets everything", () => {
    expect(ids(filterSections(SECTIONS, female))).toEqual(ids(SECTIONS));
  });

  it("a switched-off body map removes only the Body map tab", () => {
    const patterns = (list: ReturnType<typeof filterSections<(typeof SECTIONS)[number]>>) => list.find((s) => s.id === "patterns")!;
    expect(patterns(filterSections(SECTIONS, trans)).tabs?.map((t) => t.href)).not.toContain("/body");
    expect(patterns(filterSections(SECTIONS, trans)).tabs?.map((t) => t.href)).toContain("/insights");
    expect(ids(filterSections(SECTIONS, trans))).toEqual(ids(SECTIONS));
    expect(patterns(filterSections(SECTIONS, female)).tabs?.map((t) => t.href)).toContain("/body");
  });

  it("with no profile yet nothing is hidden", () => {
    expect(filterSections(SECTIONS, null)).toEqual([...SECTIONS]);
  });
});

describe("the setup gate", () => {
  it("only applies to the signed-in app", () => {
    for (const path of ["/dashboard", "/companion", "/body", "/eyes", "/cycle", "/settings"]) expect(gateApplies(path), path).toBe(true);
    for (const path of ["/", "/onboarding", "/onboarding/x", "/login", "/callback", "/password", "/terms", "/privacy", "/partner/abc", "/cycle/partner/tok", "/android"]) expect(gateApplies(path), path).toBe(false);
  });

  it("sends an unfinished person to setup, waits while it checks, and never locks anyone out", () => {
    expect(gateDecision("/dashboard", { complete: false, under18: false })).toBe("setup");
    expect(gateDecision("/dashboard", { complete: true, under18: false })).toBe("pass");
    expect(gateDecision("/dashboard", "loading")).toBe("wait");
    expect(gateDecision("/dashboard", "error")).toBe("pass");
    expect(gateDecision("/onboarding", { complete: false, under18: false })).toBe("pass");
    expect(gateDecision("/login", "loading")).toBe("pass");
  });

  it("reads the state tolerantly", () => {
    expect(readSetupState({ complete: false, under_18: true })).toEqual({ complete: false, under18: true });
    expect(readSetupState({ complete: true })).toEqual({ complete: true, under18: false });
    expect(readSetupState({})).toBeNull();
    expect(readSetupState(null)).toBeNull();
  });
});
