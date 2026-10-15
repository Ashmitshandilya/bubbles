import { describe, expect, it } from "vitest";
import { ANATOMIES, REPRODUCTIVE_LABEL, figure, isAnatomy, organLabel, organsFor } from "./presets";

const ids = (anatomy: "female" | "male" | "neutral", list?: string[]) => organsFor(anatomy, list).map((o) => o.id);

describe("figure", () => {
  it("is a whole body: head, neck, torso, pelvis, two arms, two legs", () => {
    for (const anatomy of ANATOMIES) {
      const parts = figure(anatomy).map((p) => p.id);
      for (const id of ["head", "neck", "chest", "abdomen", "pelvis"]) expect(parts, `${anatomy} ${id}`).toContain(id);
      for (const side of ["l", "r"]) {
        for (const id of ["upper-arm", "forearm", "hand", "thigh", "shin", "foot"]) expect(parts, `${anatomy} ${id}-${side}`).toContain(`${id}-${side}`);
      }
    }
  });

  it("is symmetric left and right", () => {
    for (const anatomy of ANATOMIES) {
      const parts = figure(anatomy);
      for (const p of parts.filter((x) => x.id.endsWith("-l"))) {
        const twin = parts.find((x) => x.id === p.id.replace(/-l$/, "-r"));
        expect(twin?.position[0]).toBeCloseTo(-p.position[0], 10);
        expect(twin?.position[1]).toBe(p.position[1]);
      }
    }
  });

  it("has a female frame with wider hips and narrower shoulders than the male frame", () => {
    const scale = (a: "female" | "male", id: string) => figure(a).find((p) => p.id === id)?.scale?.[0] ?? 0;
    expect(scale("female", "pelvis")).toBeGreaterThan(scale("male", "pelvis"));
    expect(scale("female", "chest")).toBeLessThan(scale("male", "chest"));
    expect(scale("female", "pelvis") / scale("female", "chest")).toBeGreaterThan(scale("male", "pelvis") / scale("male", "chest"));
  });
});

describe("organsFor", () => {
  it("draws every body system by default, with eyes", () => {
    expect(ids("neutral")).toEqual(expect.arrayContaining(["brain", "eyes", "heart", "lungs", "liver", "kidneys", "pancreas", "digestive_system", "reproductive_system", "musculoskeletal_system"]));
  });

  it("only the female body has breasts", () => {
    expect(ids("female")).toContain("breasts");
    expect(ids("male")).not.toContain("breasts");
    expect(ids("neutral")).not.toContain("breasts");
  });

  it("draws the reproductive system differently for each anatomy", () => {
    const count = (a: "female" | "male" | "neutral") => organsFor(a).find((o) => o.id === "reproductive_system")!;
    expect(count("female").parts).toHaveLength(3);                      // uterus + ovary pair
    expect(count("male").parts).toHaveLength(3);                        // prostate + testes pair
    expect(count("male").focus[1]).toBeLessThan(count("female").focus[1]);
    expect(count("neutral").parts).toHaveLength(1);                     // one soft general marker
  });

  it("draws only the systems the backend reports, ignoring ones it does not know", () => {
    expect(ids("female", ["heart", "lungs", "not_a_system"])).toEqual(["lungs", "heart"]);
  });

  it("falls back to everything when none of the reported ids are known", () => {
    expect(ids("male", ["nothing_known"])).toEqual(ids("male"));
    expect(ids("male", [])).toEqual(ids("male"));
  });

  it("keeps eyes paired, centred and on the face", () => {
    const eyes = organsFor("neutral").find((o) => o.id === "eyes")!;
    expect(eyes.parts).toHaveLength(2);
    expect(eyes.parts[0].position[0]).toBeCloseTo(-eyes.parts[1].position[0], 10);
    expect(eyes.parts[0].position[1]).toBeGreaterThan(0.85);   // head height
    expect(eyes.parts[0].position[2]).toBeGreaterThan(0.1);    // front of the face
  });

  it("gives every organ a tap target big enough for a finger and a focus inside its own parts' reach", () => {
    for (const anatomy of ANATOMIES) {
      for (const o of organsFor(anatomy)) {
        expect(o.hit, `${anatomy} ${o.id}`).toBeGreaterThanOrEqual(0.09);
        const nearest = Math.min(...o.parts.map((p) => Math.hypot(p.position[0] - o.focus[0], p.position[1] - o.focus[1], p.position[2] - o.focus[2])));
        expect(nearest, `${anatomy} ${o.id}`).toBeLessThan(0.2);
      }
    }
  });

  it("keeps every organ inside the body's height", () => {
    for (const anatomy of ANATOMIES) for (const o of organsFor(anatomy)) for (const p of o.parts) {
      expect(p.position[1]).toBeGreaterThan(-1.4);
      expect(p.position[1]).toBeLessThan(1.15);
    }
  });
});

describe("labels", () => {
  it("names the reproductive system for the anatomy", () => {
    expect(organLabel("reproductive_system", "female")).toBe("Uterus and ovaries");
    expect(organLabel("reproductive_system", "male")).toBe("Prostate and testes");
    expect(organLabel("reproductive_system", "neutral")).toBe("Reproductive");
    expect(organLabel("reproductive_system")).toBe(REPRODUCTIVE_LABEL.neutral);
  });

  it("never shows a raw key for a system it does not know", () => {
    expect(organLabel("eyes")).toBe("Eyes");
    expect(organLabel("some_new_system")).toBe("Some new system");
  });

  it("recognises only the three anatomies", () => {
    expect(isAnatomy("female")).toBe(true);
    expect(isAnatomy("other")).toBe(false);
    expect(isAnatomy(undefined)).toBe(false);
  });
});
