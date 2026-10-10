/**
 * The sky shader (WebGL2, GLSL ES 3.00). One full-screen triangle, no attributes, no textures.
 *
 * Layers: a three-stop gradient mixed in OKLab (the stops arrive already in OKLab, so there is no
 * per-pixel colour conversion except the one way back), a sun or moon with a soft glow, analytic
 * god rays (angular noise that turns about 0.3 degrees a second) and drifting haze. The glow,
 * rays and haze share one budget, `uCap`, so copy contrast is bounded (see OVERLAY_CAP in sky.ts).
 * The result is dithered to kill banding.
 */

export const SKY_VERT = `#version 300 es
out vec2 vUv;
void main() {
  vec2 p = vec2(float((gl_VertexID << 1) & 2), float(gl_VertexID & 2));
  vUv = p;
  gl_Position = vec4(p * 2.0 - 1.0, 0.0, 1.0);
}
`;

export const SKY_FRAG = `#version 300 es
precision highp float;

in vec2 vUv;
out vec4 outColor;

uniform vec2 uRes;
uniform float uTime;
uniform vec3 uLabTop;
uniform vec3 uLabMid;
uniform vec3 uLabHor;
uniform vec3 uSun;
uniform vec2 uSunPos;
uniform float uSunSize;
uniform float uDisc;
uniform float uRays;
uniform float uHaze;
uniform float uCap;
uniform float uFull;

const float MID = 0.5;
const float TAU = 6.28318530718;
const float RAY_COUNT = 24.0;

vec3 labToSrgb(vec3 c) {
  float l_ = c.x + 0.3963377774 * c.y + 0.2158037573 * c.z;
  float m_ = c.x - 0.1055613458 * c.y - 0.0638541728 * c.z;
  float s_ = c.x - 0.0894841775 * c.y - 1.2914855480 * c.z;
  float l = l_ * l_ * l_;
  float m = m_ * m_ * m_;
  float s = s_ * s_ * s_;
  vec3 lin = vec3(
    4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
    -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
    -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s
  );
  lin = clamp(lin, 0.0, 1.0);
  return mix(lin * 12.92, 1.055 * pow(lin, vec3(1.0 / 2.4)) - 0.055, step(0.0031308, lin));
}

float hash(float n) { return fract(sin(n * 127.1) * 43758.5453); }
float hash2(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }

float vnoise(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  f = f * f * (3.0 - 2.0 * f);
  return mix(mix(hash2(i), hash2(i + vec2(1.0, 0.0)), f.x), mix(hash2(i + vec2(0.0, 1.0)), hash2(i + vec2(1.0, 1.0)), f.x), f.y);
}

// Noise around a circle: the period is n whole steps, so there is no seam where the angle wraps.
float ring(float x, float n) {
  float i = floor(x);
  float f = fract(x);
  f = f * f * (3.0 - 2.0 * f);
  return mix(hash(mod(i, n)), hash(mod(i + 1.0, n)), f);
}

void main() {
  float aspect = uRes.x / uRes.y;
  float h = 1.0 - vUv.y; // 0 at the top of the screen, 1 at the horizon
  vec3 lab = h <= MID ? mix(uLabTop, uLabMid, h / MID) : mix(uLabMid, uLabHor, (h - MID) / (1.0 - MID));
  vec3 col = labToSrgb(lab);

  // sun or moon
  vec2 p = (vUv - uSunPos) * vec2(aspect, 1.0);
  float d = length(p);
  float glow = exp(-d * 3.2) * 0.32 + exp(-d * 11.0) * 0.4;

  // god rays: angular noise from the sun, falling off with distance, turning very slowly
  float rot = uTime * 0.0052 / TAU * RAY_COUNT;
  float a = (atan(p.y, p.x) / TAU + 0.5) * RAY_COUNT;
  float r1 = ring(a + rot, RAY_COUNT);
  float r2 = ring(a * 2.0 - rot * 0.7 + 3.0, RAY_COUNT * 2.0);
  float rays = pow(clamp(r1 * 0.65 + r2 * 0.35, 0.0, 1.0), 2.4) * uRays / (1.0 + d * 3.4);

  // haze: low, slow fbm, domain-warped on the full tier
  vec2 q = vUv * vec2(aspect, 1.0) * 1.7 + vec2(uTime * 0.012, uTime * 0.004);
  if (uFull > 0.5) q += 0.55 * vec2(vnoise(q * 0.8 + vec2(0.0, uTime * 0.006)), vnoise(q * 0.8 + 7.0));
  float f = vnoise(q) * 0.55 + vnoise(q * 2.1) * 0.3;
  if (uFull > 0.5) f += vnoise(q * 4.3) * 0.15; else f += 0.075;
  float haze = smoothstep(0.38, 0.9, f) * uHaze * (0.35 + 0.65 * h);

  float a1 = min(glow + rays + haze * 0.35, uCap);
  col = mix(col, uSun, a1);
  col = mix(col, uSun, smoothstep(uSunSize, uSunSize * 0.55, d) * uDisc);

  // triangular-ish dither, one 8-bit step wide
  float n = fract(52.9829189 * fract(dot(gl_FragCoord.xy, vec2(0.06711056, 0.00583715))));
  col += (n - 0.5) / 255.0;
  outColor = vec4(col, 1.0);
}
`;

/** Every uniform the fragment shader declares (sky.test.ts keeps this list and the source in step). */
export const SKY_UNIFORMS = [
  "uRes", "uTime", "uLabTop", "uLabMid", "uLabHor", "uSun", "uSunPos", "uSunSize", "uDisc", "uRays", "uHaze", "uCap", "uFull",
] as const;
