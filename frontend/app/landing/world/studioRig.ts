/**
 * Pure rules for the studio (world/Studio.tsx): what the lights are, and when the reflections are rebuilt.
 * Plan 2.4: one key light for the whole page from the upper left (the painting's own light), a rim on the
 * opposite side that takes the horizon colour, and an environment built from the sky on screen, so beads,
 * pearls and bubbles reflect the world they are in. No DOM and no three.js: unit-tested in node.
 */
import { mixOklab, type Hex } from "../atmosphere/palette";
import type { SkyState } from "../story/store";

const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
const clamp01 = (v: number) => (v < 0 ? 0 : v > 1 ? 1 : v);

/** The reflections are rebuilt at most this often (4 Hz) and only while the sky colours really changed. */
export const ENV_MIN_MS = 250;
/** Cube face size of the environment. The sky is a smooth gradient, so a tiny cube is plenty (and about 1 ms). */
export const ENV_SIZE = 64;
/** How much the dome is brightened before it becomes reflections (the old studio panels were bright). */
export const ENV_GAIN = 1.25;
export const ENV_INTENSITY = 1;

/** Everything the environment is built from. A change in this string is a change worth rebuilding for. */
export const envKey = (s: Pick<SkyState, "top" | "mid" | "horizon" | "key">) => `${s.top}|${s.mid}|${s.horizon}|${s.key}`;

/** True when the environment should be rebuilt: the sky changed since the last build, and the throttle has passed. */
export const envDue = (lastBuiltAt: number, now: number, builtKey: string, key: string) =>
  key !== builtKey && now - lastBuiltAt >= ENV_MIN_MS;

export type LightRig = {
  hemiSky: Hex;
  hemiGround: Hex;
  hemi: number;
  key: Hex;
  keyI: number;
  fill: Hex;
  fillI: number;
  rim: Hex;
  rimI: number;
  rim2: Hex;
  rim2I: number;
};

/** Light directions: key from the upper left front, rim opposite and behind (shared by Studio and tests). */
export const LIGHT_POS = {
  key: [-3.5, 5, 4.5],
  fill: [4, 1.5, 3],
  rim: [3, 3.5, -4.5],
  rim2: [-3.5, 1, -4],
} as const;

/**
 * Light colours and strengths for the sky on screen. The palette's key and rim are blended with the old
 * fixed studio colours (70 and 65 percent), so a pearl is never lit by a colour so faint that it vanishes.
 * Rim strength grows with the dark: on night skies it is what keeps the white silhouette readable.
 */
export function lightRig(sky: Pick<SkyState, "top" | "mid" | "horizon" | "key" | "rim" | "dark">): LightRig {
  const dark = clamp01(sky.dark);
  const rimI = lerp(1.8, 2.6, dark);
  return {
    hemiSky: mixOklab(sky.mid, "#FFFFFF", 0.55),
    hemiGround: mixOklab(sky.horizon, "#2A1030", 0.6),
    hemi: lerp(0.85, 0.7, dark),
    key: mixOklab("#FFF6F2", sky.key, 0.7),
    keyI: 2.1,
    fill: mixOklab("#D8CCFF", sky.top, 0.35),
    fillI: 0.55,
    rim: mixOklab("#FF86BD", sky.rim, 0.65),
    rimI,
    rim2: mixOklab("#C9B4FF", sky.rim, 0.4),
    rim2I: rimI * 0.55,
  };
}

export const DOME_VERT = /* glsl */ `
varying vec3 vDir;
void main() {
  vDir = normalize(position);
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}
`;

/**
 * A sky dome for PMREM: the three sky stops by height (horizon at the bottom of the sphere, top at the top), a
 * soft patch of key light where the page's sun is (upper left, front), and a gain. Colours arrive in linear
 * light (THREE.Color), and the result goes to a linear target, so there is no colour-space conversion here.
 */
export const DOME_FRAG = /* glsl */ `
varying vec3 vDir;
uniform vec3 uTop;
uniform vec3 uMid;
uniform vec3 uHor;
uniform vec3 uKey;
uniform float uGain;
void main() {
  vec3 d = normalize(vDir);
  float h = d.y * 0.5 + 0.5;
  vec3 c = h < 0.5 ? mix(uHor, uMid, h * 2.0) : mix(uMid, uTop, (h - 0.5) * 2.0);
  float sun = pow(max(dot(d, normalize(vec3(-0.5, 0.6, 0.62))), 0.0), 18.0);
  c = c * uGain + uKey * sun * 1.6;
  gl_FragColor = vec4(c, 1.0);
}
`;
