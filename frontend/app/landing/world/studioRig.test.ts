import { describe, expect, it } from "vitest";
import { COLOR_SCRIPT, contrastRatio, skyAt } from "../atmosphere/palette";
import { DOME_FRAG, ENV_MIN_MS, LIGHT_POS, envDue, envKey, lightRig } from "./studioRig";

const HEX = /^#[0-9A-F]{6}$/;
const sky = (index: number, blend = 0) => {
  const b = skyAt(index, blend);
  return { top: b.top, mid: b.mid, horizon: b.horizon, key: b.key, rim: b.rim, dark: b.tone === "dark" ? 1 : 0 };
};

describe("when the reflections are rebuilt", () => {
  const a = envKey({ top: "#111111", mid: "#222222", horizon: "#333333", key: "#444444" });
  const b = envKey({ top: "#111111", mid: "#222222", horizon: "#333333", key: "#555555" });

  it("is a different key whenever any of the four colours changes", () => {
    expect(a).not.toBe(b);
    expect(envKey({ top: "#111111", mid: "#222222", horizon: "#333333", key: "#444444" })).toBe(a);
  });

  it("never rebuilds for the same colours, however long it has been", () => {
    expect(envDue(0, 10_000, a, a)).toBe(false);
  });

  it("rebuilds at most four times a second while the colours keep changing", () => {
    expect(ENV_MIN_MS).toBe(250);
    expect(envDue(1000, 1100, a, b)).toBe(false);
    expect(envDue(1000, 1249, a, b)).toBe(false);
    expect(envDue(1000, 1250, a, b)).toBe(true);
  });

  it("builds straight away the first time (nothing has been built yet)", () => {
    expect(envDue(-Infinity, 0, "", a)).toBe(true);
  });

  it("always catches up: the last change is applied once the throttle has passed", () => {
    // a hand-over ends at t = 3000 ms with the final colours; the next frame after the throttle rebuilds with them
    expect(envDue(2900, 3000, a, b)).toBe(false);
    expect(envDue(2900, 3200, a, b)).toBe(true);
  });
});

describe("lights follow the sky on screen", () => {
  it("gives valid colours and positive strengths for every chapter", () => {
    COLOR_SCRIPT.forEach((_, i) => {
      const rig = lightRig(sky(i));
      for (const c of [rig.hemiSky, rig.hemiGround, rig.key, rig.fill, rig.rim, rig.rim2]) expect(c).toMatch(HEX);
      for (const n of [rig.hemi, rig.keyI, rig.fillI, rig.rimI, rig.rim2I]) expect(n).toBeGreaterThan(0);
    });
  });

  it("keys from the upper left and rims from the opposite side, behind", () => {
    expect(LIGHT_POS.key[0]).toBeLessThan(0);
    expect(LIGHT_POS.key[1]).toBeGreaterThan(0);
    expect(LIGHT_POS.rim[0]).toBeGreaterThan(0);
    expect(LIGHT_POS.rim[2]).toBeLessThan(0);
  });

  it("makes the rim stronger on night skies, where it keeps the white silhouette readable", () => {
    const day = lightRig(sky(0));
    const night = lightRig(sky(6));
    expect(night.rimI).toBeGreaterThan(day.rimI);
    expect(night.rim2I).toBeCloseTo(night.rimI * 0.55, 6);
  });

  it("takes its colours from the chapter: a cool key for the body, a warm one for the companion", () => {
    const body = lightRig(sky(1));
    const companion = lightRig(sky(7));
    const channel = (hex: string, at: number) => parseInt(hex.slice(1 + at * 2, 3 + at * 2), 16);
    expect(channel(body.key, 2)).toBeGreaterThan(channel(body.key, 0));
    expect(channel(companion.key, 0)).toBeGreaterThan(channel(companion.key, 2));
  });

  it("never lights a pearl with a colour so dark that it vanishes", () => {
    COLOR_SCRIPT.forEach((_, i) => {
      const rig = lightRig(sky(i));
      expect(contrastRatio(rig.key, "#000000")).toBeGreaterThan(8);
    });
  });

  it("hands over without a jump: the end of one chapter's hand-over is the start of the next, and the middle is neither", () => {
    expect(lightRig(sky(0, 1))).toEqual(lightRig(sky(1, 0)));
    const from = lightRig(sky(0, 0)).key;
    const to = lightRig(sky(1, 0)).key;
    const mid = lightRig(sky(0, 0.5)).key;
    expect(mid).not.toBe(from);
    expect(mid).not.toBe(to);
  });
});

describe("the sky dome shader", () => {
  it("mixes the three sky stops by height and adds a key patch to the upper left front", () => {
    for (const u of ["uTop", "uMid", "uHor", "uKey", "uGain"]) expect(DOME_FRAG).toContain(u);
    expect(DOME_FRAG).toContain("vec3(-0.5, 0.6, 0.62)");
  });
});
