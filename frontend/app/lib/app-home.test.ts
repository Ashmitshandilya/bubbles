import { describe, expect, it } from "vitest";
import { appTiles, bodyMapShown, dockTabs } from "./app-home";
import type { Experience } from "./experience";

const exp = (over: Partial<Experience>): Experience =>
  ({ bodyMap: { visible: true, anatomy: "neutral", reproductive: "by_use" }, hiddenSections: [], cycleVisible: true, ...over }) as Experience;

describe("app home", () => {
  it("shows everything before the profile is known", () => {
    expect(appTiles(null).map((t) => t.id)).toContain("cycle");
    expect(bodyMapShown(null)).toBe(true);
    expect(dockTabs(null)[1].href).toBe("/body");
  });

  it("follows the profile: no cycle, no hidden sections, no body map", () => {
    const e = exp({ cycleVisible: false, hiddenSections: ["fitness"], bodyMap: { visible: false, anatomy: "neutral", reproductive: "none" } });
    const ids = appTiles(e).map((t) => t.id);
    expect(ids).not.toContain("cycle");
    expect(ids).not.toContain("fitness");
    expect(bodyMapShown(e)).toBe(false);
    expect(dockTabs(e)[1].id).toBe("mind");
  });

  it("puts Cycle in the dock when there is no body map but cycle is on", () => {
    expect(dockTabs(exp({ bodyMap: { visible: false, anatomy: "neutral", reproductive: "none" } }))[1].href).toBe("/cycle");
  });

  it("keeps Talk in the centre", () => {
    expect(dockTabs(null)[2].id).toBe("talk");
  });
});
