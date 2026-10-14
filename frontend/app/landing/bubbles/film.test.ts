import { describe, expect, it } from "vitest";
import { FILM_GLSL, FILM_LAMBDAS, airy, cmf, filmRgb } from "./film";

/** Hue in degrees of a linear colour, as it is seen (display-encoded). */
const hue = (lin: [number, number, number]) => {
  const [r, g, b] = lin.map((v) => Math.pow(Math.min(1, v), 1 / 2.2));
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  if (max - min < 1e-6) return -1;
  const h = max === r ? ((g - b) / (max - min)) % 6 : max === g ? (b - r) / (max - min) + 2 : (r - g) / (max - min) + 4;
  return (h * 60 + 360) % 360;
};

describe("thin-film interference", () => {
  it("reflects nothing from a film too thin to interfere (the black film of a bursting bubble)", () => {
    for (const l of FILM_LAMBDAS) expect(airy(0.5, 1, l).R).toBeLessThan(1e-4);
  });

  it("never reflects more than the two faces can (the Airy peak), at any angle", () => {
    for (let d = 100; d <= 1200; d += 37) {
      for (const c of [1, 0.7, 0.3, 0.05]) {
        for (const l of FILM_LAMBDAS) {
          const a = airy(d, c, l);
          expect(a.R).toBeLessThanOrEqual(a.peak + 1e-9);
          expect(a.R).toBeGreaterThanOrEqual(0);
        }
      }
    }
  });

  it("reflects about 2 percent per face face-on (water, n = 1.33), more at grazing angles", () => {
    expect(airy(300, 1, 550).peak).toBeCloseTo(0.077, 2);
    expect(airy(300, 0.1, 550).peak).toBeGreaterThan(airy(300, 1, 550).peak);
  });

  it("walks through the real interference colours as the film thickens: magenta, then gold, then cyan", () => {
    const magenta = filmRgb(400, 1);
    expect(magenta[0]).toBeGreaterThan(magenta[1]);
    expect(magenta[2]).toBeGreaterThan(magenta[1]);
    const gold = filmRgb(350, 1);
    expect(hue(gold)).toBeGreaterThan(25);
    expect(hue(gold)).toBeLessThan(60);
    const cyan = filmRgb(450, 1);
    expect(hue(cyan)).toBeGreaterThan(170);
    expect(hue(cyan)).toBeLessThan(215);
  });

  it("shifts the bands with the viewing angle (the colours slide toward the rim)", () => {
    expect(filmRgb(500, 1)).not.toEqual(filmRgb(500, 0.5));
  });

  it("uses colour matching functions that peak where the eye does", () => {
    expect(cmf(555)[1]).toBeGreaterThan(cmf(450)[1]);
    expect(cmf(600)[0]).toBeGreaterThan(cmf(450)[0]);
    expect(cmf(450)[2]).toBeGreaterThan(cmf(600)[2]);
  });

  it("writes the same tables into the shader", () => {
    expect(FILM_GLSL).toContain(`FILM_LAMBDA[${FILM_LAMBDAS.length}]`);
    expect(FILM_GLSL).toContain("vec3 filmColor(float d, float cosI)");
  });
});
