import { FILM_GLSL } from "./film";

/**
 * Soap bubble shader, shared by the small bubbles (one instanced mesh, per-bubble attributes) and the hero orb
 * (one mesh, the same values as uniforms).
 *
 * What a real bubble shows, and what this draws:
 *  - thin-film interference (film.ts): the film drains, so it is thinner at the top and thicker at the bottom,
 *    and slow swirls move the bands; the colour comes from the Airy reflectance summed over the spectrum.
 *  - two surfaces: the material is double sided and three.js draws the back (inner) face first, so the far
 *    side of the bubble reflects the room upside down, as a concave mirror, under the upright front reflection.
 *  - Fresnel: the film reflects far more at grazing angles, so the rim is bright and the face nearly clear.
 *  - the room it reflects: the page's own sky above, a lilac studio floor below (which gives the lower half its
 *    body on a pale page), and a warm window up and to the left (Pearl Lab's key light).
 * Colours are written in display (sRGB) space, like the sky; `uLinear` = 1 converts to linear light for the
 * post stack, which tone maps and encodes the scene itself (post/PostStack.ts).
 */

export const SOAP_VERT = /* glsl */ `
#ifdef USE_INSTANCING
attribute float aSeed;
attribute float aPop;
attribute float aAlpha;
attribute float aHover;
#else
uniform float uSeed;
uniform float uPop;
uniform float uAlpha;
uniform float uHover;
#endif
uniform float uTime;
uniform float uWobble;
varying vec3 vN;
varying vec3 vP;
varying vec3 vObj;
varying float vSeed;
varying float vPop;
varying float vAlpha;
varying float vHover;

void main() {
#ifdef USE_INSTANCING
  float seed = aSeed; float pop = aPop; vAlpha = aAlpha; vHover = aHover;
  mat4 inst = instanceMatrix;
#else
  float seed = uSeed; float pop = uPop; vAlpha = uAlpha; vHover = uHover;
  mat4 inst = mat4(1.0);
#endif
  vec3 n0 = normalize(position);
  float wob = (sin(uTime * 1.3 + seed * 40.0 + n0.y * 3.0) * 0.022
            + sin(uTime * 0.9 + seed * 23.0 + n0.x * 2.4 + n0.z * 1.7) * 0.02) * uWobble;
  vec3 p = position * (1.0 + wob) * (1.0 + pop * 0.38);
  vec4 mv = modelViewMatrix * inst * vec4(p, 1.0);
  vP = mv.xyz;
  vN = normalize(mat3(modelViewMatrix) * mat3(inst) * n0);
  vObj = n0;
  vSeed = seed;
  vPop = pop;
  gl_Position = projectionMatrix * mv;
}
`;

export const SOAP_FRAG = /* glsl */ `
precision highp float;
uniform float uTime;
uniform vec3 uTop;
uniform vec3 uMid;
uniform vec3 uHor;
uniform float uLinear;
varying vec3 vN;
varying vec3 vP;
varying vec3 vObj;
varying float vSeed;
varying float vPop;
varying float vAlpha;
varying float vHover;
${FILM_GLSL}

vec3 sky(float h) {
  return h < 0.5 ? mix(uHor, uMid, h * 2.0) : mix(uMid, uTop, (h - 0.5) * 2.0);
}

/** The room the bubble reflects, by view-space direction. */
vec3 room(vec3 d) {
  vec3 c = sky(clamp(d.y * 0.5 + 0.5, 0.0, 1.0));
  vec3 floorC = vec3(0.66, 0.6, 0.76);
  c = mix(c, floorC, smoothstep(0.02, -0.2, d.y) * 0.9);
  c *= 1.0 - 0.16 * exp(-abs(d.y + 0.03) * 34.0);
  // the window: a soft panel up and to the left, split by a mullion
  vec2 w = vec2(d.x + 0.42, d.y - 0.5);
  float win = (1.0 - smoothstep(0.15, 0.21, abs(w.x))) * (1.0 - smoothstep(0.12, 0.17, abs(w.y)));
  win *= smoothstep(0.006, 0.024, abs(w.x)) * smoothstep(0.006, 0.024, abs(w.y));
  // and a dimmer, narrow one to the right (the rim light)
  vec2 v = vec2(d.x - 0.62, d.y - 0.28);
  float rim = (1.0 - smoothstep(0.03, 0.07, abs(v.x))) * (1.0 - smoothstep(0.1, 0.16, abs(v.y)));
  return mix(c, vec3(1.0, 0.985, 0.95), clamp(win + rim * 0.6, 0.0, 1.0));
}

void main() {
  vec3 N = normalize(vN);
  bool back = !gl_FrontFacing;
  if (back) N = -N;
  vec3 V = normalize(-vP);
  float cosI = clamp(dot(N, V), 0.0, 1.0);
  float edge = 1.0 - cosI;
  float fres = 0.04 + 0.96 * pow(edge, 5.0);

  // Film thickness in nm: drainage (thin at the top, thick at the bottom) and slow swirls.
  float swirl = sin(vObj.y * 4.6 + vObj.x * 1.7 + uTime * 0.21 + vSeed * 31.0) * 0.5
              + sin(vObj.x * 5.9 - vObj.z * 2.6 - uTime * 0.16 + vSeed * 17.0) * 0.32
              + sin(length(vObj.xz) * 8.0 - uTime * 0.33 + vSeed * 7.0) * 0.18;
  float drain = pow(clamp(0.5 - 0.5 * vObj.y, 0.0, 1.0), 0.85);
  float d = 380.0 + 520.0 * drain + 105.0 * swirl;
  vec3 film = filmColor(d, max(cosI, 0.05));
  // Physical hue, softened for a pearl page: a little less saturated, brightness compressed, then display space.
  film = mix(film, vec3(dot(film, vec3(0.2126, 0.7152, 0.0722))), 0.3);
  film = pow(film / (1.0 + film * 0.35), vec3(1.0 / 2.2));

  vec3 R = reflect(-V, N);
  vec3 env = room(R);
  float lum = dot(env, vec3(0.299, 0.587, 0.114));
  float glint = smoothstep(0.93, 0.99, lum);

  vec3 col = env * mix(film, vec3(1.0), glint * 0.85);
  col += film * vPop * 0.6 + vec3(1.0, 0.94, 0.98) * vHover * 0.1;
  // Nearly clear face-on (what is inside stays readable), colour building toward the rim.
  float a = 0.05 + 0.5 * pow(edge, 2.2) + 0.5 * fres + 0.06 * (1.0 - lum);
  a = max(a, glint * 0.9);
  a *= back ? 0.62 : 1.0;
  a = clamp((a + vHover * 0.06) * vAlpha * (1.0 - vPop), 0.0, 1.0);

  // Dither, so the faint interior does not band.
  float n = fract(sin(dot(gl_FragCoord.xy, vec2(12.9898, 78.233))) * 43758.5453);
  col = clamp(col + (n - 0.5) / 255.0, 0.0, 1.0);
  col = mix(col, pow(col, vec3(2.2)), uLinear);
  gl_FragColor = vec4(col, a);
}
`;

export const SOAP_UNIFORMS = ["uTime", "uWobble", "uTop", "uMid", "uHor", "uLinear"] as const;
