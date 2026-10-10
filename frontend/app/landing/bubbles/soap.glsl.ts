/**
 * Thin-film soap bubble shader (plan 2.6): Fresnel alpha, a film whose thickness swirls slowly and drains
 * toward the bottom (where real films show their bands), a cosine interference palette that shifts with the
 * view angle, a window highlight, and a gentle vertex wobble. Colours are written straight in display
 * (sRGB) space, like the sky shader, because the bubbles blend over the sky as CSS would.
 *
 * What a bubble reflects and shows through itself is the page's own sky (top / mid / horizon, sampled by
 * direction). In the full tier the interior also shows the sky bent by a refraction; in lite it is the plain
 * reflection. There is no scene copy: true refraction of the 3D scene waits for the post stack (plan step 9).
 */

export const SOAP_VERT = /* glsl */ `
attribute float aSeed;
attribute float aPop;
attribute float aAlpha;
attribute float aHover;
uniform float uTime;
varying vec3 vN;
varying vec3 vP;
varying vec3 vObj;
varying float vSeed;
varying float vPop;
varying float vAlpha;
varying float vHover;

void main() {
  vec3 n0 = normalize(position);
  float wob = sin(uTime * 1.3 + aSeed * 40.0 + n0.y * 3.0) * 0.022
            + sin(uTime * 0.9 + aSeed * 23.0 + n0.x * 2.4 + n0.z * 1.7) * 0.02;
  vec3 p = position * (1.0 + wob) * (1.0 + aPop * 0.38);
  vec4 mv = modelViewMatrix * instanceMatrix * vec4(p, 1.0);
  vP = mv.xyz;
  vN = normalize(mat3(modelViewMatrix) * mat3(instanceMatrix) * n0);
  vObj = n0;
  vSeed = aSeed;
  vPop = aPop;
  vAlpha = aAlpha;
  vHover = aHover;
  gl_Position = projectionMatrix * mv;
}
`;

export const SOAP_FRAG = /* glsl */ `
precision highp float;
uniform float uTime;
uniform vec3 uTop;
uniform vec3 uMid;
uniform vec3 uHor;
uniform float uDark;
uniform float uFull;
varying vec3 vN;
varying vec3 vP;
varying vec3 vObj;
varying float vSeed;
varying float vPop;
varying float vAlpha;
varying float vHover;

vec3 sky(float h) {
  return h < 0.5 ? mix(uHor, uMid, h * 2.0) : mix(uMid, uTop, (h - 0.5) * 2.0);
}

void main() {
  vec3 N = normalize(vN);
  vec3 V = normalize(-vP);
  float edge = 1.0 - clamp(dot(N, V), 0.0, 1.0);
  float fres = pow(edge, 2.4);

  // Film thickness: slow swirl plus drainage (thicker toward the bottom).
  float swirl = sin(vObj.y * 3.2 + uTime * 0.22 + vSeed * 31.0) * 0.5
              + sin(vObj.x * 4.1 - uTime * 0.17 + vSeed * 17.0 + vObj.z * 2.0) * 0.35;
  float drain = 0.5 - vObj.y * 0.5;
  float thick = 0.35 + 0.25 * swirl + 0.55 * drain * drain;
  float phase = thick * 2.6 + edge * 1.9;
  vec3 film = 0.5 + 0.5 * cos(6.28318 * (phase + vec3(0.0, 0.33, 0.67)));
  film = mix(film, vec3(dot(film, vec3(0.3333))), 0.14);

  vec3 R = reflect(-V, N);
  vec3 env = sky(R.y * 0.5 + 0.5);
  vec3 T = refract(-V, N, 0.75);
  vec3 behind = mix(env, sky(T.y * 0.5 + 0.5), uFull);

  // A soft window highlight and a faint one opposite.
  float win = (1.0 - smoothstep(0.0, 0.1, abs(N.x + 0.42) - 0.11)) * (1.0 - smoothstep(0.0, 0.1, abs(N.y - 0.46) - 0.075));
  float win2 = (1.0 - smoothstep(0.0, 0.1, abs(N.x - 0.5) - 0.05)) * (1.0 - smoothstep(0.0, 0.1, abs(N.y + 0.5) - 0.035)) * 0.5;
  float glint = max(win, win2) * (1.0 - edge * 0.35);

  vec3 col = behind * 0.3 + film * (0.22 + 1.15 * fres) + env * fres * 0.45;
  col = mix(col, vec3(1.0), glint * 0.85);
  col += film * vPop * 0.7 + vec3(1.0, 0.92, 0.97) * vHover * 0.12;

  float a = 0.07 + 0.78 * fres + 0.2 * film.g * fres;
  a = max(a, glint * 0.92);
  a *= 1.0 + uDark * 0.3;
  a = clamp((a + vHover * 0.07) * vAlpha * (1.0 - vPop), 0.0, 1.0);

  // Dither, so the faint interior does not band.
  float n = fract(sin(dot(gl_FragCoord.xy, vec2(12.9898, 78.233))) * 43758.5453);
  col += (n - 0.5) / 255.0;
  gl_FragColor = vec4(clamp(col, 0.0, 1.0), a);
}
`;

export const SOAP_UNIFORMS = ["uTime", "uTop", "uMid", "uHor", "uDark", "uFull"] as const;
