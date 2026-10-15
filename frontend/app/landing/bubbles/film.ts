/**
 * Thin-film interference for the soap bubbles, the physics half (pure, no WebGL, unit-tested in node).
 *
 * A soap film (refractive index 1.33, a few hundred nanometres thick) reflects light from its front and back
 * faces; the two reflections interfere, so each wavelength is reflected more or less depending on the film's
 * thickness and the viewing angle (Airy reflectance). Summing the reflected spectrum against the CIE 1931
 * colour matching functions gives the colour a real film shows: the magenta, gold and cyan bands that slide
 * down a bubble as it drains. The shader (soap.glsl.ts) runs the same sum with the tables built here.
 */

export const FILM_N = 1.33;
/** Wavelength samples in nm (400 to 700): enough for smooth bands, cheap enough per pixel. */
export const FILM_LAMBDAS = Array.from({ length: 10 }, (_, i) => 400 + (300 * i) / 9);

/** CIE 1931 2-degree colour matching functions, multi-lobe Gaussian fit (Wyman, Sloan and Shirley, 2013). */
export function cmf(l: number): [number, number, number] {
  const g = (x: number, mu: number, s1: number, s2: number) => {
    const t = (x - mu) * (x < mu ? s1 : s2);
    return Math.exp(-0.5 * t * t);
  };
  const x = 1.056 * g(l, 599.8, 0.0264, 0.0323) + 0.362 * g(l, 442.0, 0.0624, 0.0374) - 0.065 * g(l, 501.1, 0.049, 0.0382);
  const y = 0.821 * g(l, 568.8, 0.0213, 0.0247) + 0.286 * g(l, 530.9, 0.0613, 0.0322);
  const z = 1.217 * g(l, 437.0, 0.0845, 0.0278) + 0.681 * g(l, 459.0, 0.0385, 0.0725);
  return [x, y, z];
}

/** Airy reflectance of a free-standing film for one wavelength: both faces reflect `r2` (= r squared), with a half-wave flip. */
export function airy(dNm: number, cosI: number, lambda: number, n = FILM_N) {
  const sinT = Math.sqrt(Math.max(0, 1 - cosI * cosI)) / n;
  const cosT = Math.sqrt(Math.max(0, 1 - sinT * sinT));
  const r = (cosI - n * cosT) / (cosI + n * cosT);
  const r2 = r * r;
  const cd = Math.cos((4 * Math.PI * n * dNm * cosT) / lambda);
  return { R: (2 * r2 * (1 - cd)) / (1 + r2 * r2 - 2 * r2 * cd), peak: (4 * r2) / ((1 + r2) * (1 + r2)) };
}

const XYZ_TO_RGB = [
  [3.2406, -1.5372, -0.4986],
  [-0.9689, 1.8758, 0.0415],
  [0.0557, -0.204, 1.057],
] as const;

/**
 * Linear sRGB colour of a film `dNm` thick seen at `cosI`, normalised so the strongest possible reflection is
 * white (1, 1, 1): the hue is physical, the brightness is scaled up so the bands read on a pearl page.
 */
export function filmRgb(dNm: number, cosI: number): [number, number, number] {
  let X = 0;
  let Y = 0;
  let Z = 0;
  let white = 0;
  let peak = 1;
  for (const l of FILM_LAMBDAS) {
    const a = airy(dNm, cosI, l);
    const c = cmf(l);
    peak = a.peak;
    X += a.R * c[0];
    Y += a.R * c[1];
    Z += a.R * c[2];
    white += c[1];
  }
  const k = 1 / (white * Math.max(peak, 1e-4));
  const xyz = [X * k, Y * k, Z * k];
  return XYZ_TO_RGB.map((row) => Math.max(0, row[0] * xyz[0] + row[1] * xyz[1] + row[2] * xyz[2])) as [number, number, number];
}

const num = (v: number) => (Number.isInteger(v) ? v.toFixed(1) : v.toPrecision(6));

/** The GLSL half: constant tables (built from the functions above) and `filmColor`, which matches `filmRgb`. */
export const FILM_GLSL = /* glsl */ `
const float FILM_N = ${num(FILM_N)};
const float FILM_LAMBDA[${FILM_LAMBDAS.length}] = float[](${FILM_LAMBDAS.map(num).join(", ")});
const vec3 FILM_CMF[${FILM_LAMBDAS.length}] = vec3[](${FILM_LAMBDAS.map((l) => `vec3(${cmf(l).map(num).join(", ")})`).join(", ")});
const float FILM_WHITE = ${num(FILM_LAMBDAS.reduce((s, l) => s + cmf(l)[1], 0))};

vec3 filmColor(float d, float cosI) {
  float sinT = sqrt(max(0.0, 1.0 - cosI * cosI)) / FILM_N;
  float cosT = sqrt(max(0.0, 1.0 - sinT * sinT));
  float r = (cosI - FILM_N * cosT) / (cosI + FILM_N * cosT);
  float r2 = r * r;
  vec3 xyz = vec3(0.0);
  for (int i = 0; i < ${FILM_LAMBDAS.length}; i++) {
    float cd = cos(12.5663706 * FILM_N * d * cosT / FILM_LAMBDA[i]);
    xyz += FILM_CMF[i] * (2.0 * r2 * (1.0 - cd) / (1.0 + r2 * r2 - 2.0 * r2 * cd));
  }
  float peak = 4.0 * r2 / ((1.0 + r2) * (1.0 + r2));
  xyz /= FILM_WHITE * max(peak, 1e-4);
  vec3 rgb = mat3(3.2406, -0.9689, 0.0557, -1.5372, 1.8758, -0.2040, -0.4986, 0.0415, 1.0570) * xyz;
  return max(rgb, 0.0);
}
`;
