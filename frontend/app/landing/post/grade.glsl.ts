/**
 * The last pass of the post stack: grade, tone map, encode and hand the result to the canvas.
 *
 * The scene arrives in linear light, premultiplied by alpha (the canvas is transparent over the page's sky), and
 * with the bloom already added. So: un-premultiply, grade in linear light, let three apply the renderer's tone
 * mapping and output colour space with the standard chunks (this pass is drawn straight to the canvas, so they
 * are the renderer's own), dither one 8-bit step, premultiply again. Doing it by hand keeps translucent edges
 * (soft cords, pearls' rims) exactly as they looked when drawn without post.
 */

export const GRADE_VERT = /* glsl */ `
varying vec2 vUv;
void main() {
  vUv = uv;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}
`;

export const GRADE_FRAG = /* glsl */ `
uniform sampler2D tDiffuse;
uniform vec3 uWarm;
uniform float uSat;
uniform float uCon;
uniform float uLift;
uniform float uVig;
varying vec2 vUv;

float hash12(vec2 p) {
  return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453);
}

void main() {
  vec4 c = texture2D(tDiffuse, vUv);
  float a = c.a;
  vec3 rgb = a > 0.0001 ? c.rgb / a : vec3(0.0);

  // Grade, in linear light.
  rgb *= uWarm;
  float l = dot(rgb, vec3(0.2126, 0.7152, 0.0722));
  rgb = mix(vec3(l), rgb, uSat);
  rgb = 0.18 * pow(max(rgb / 0.18, vec3(0.0)), vec3(uCon));
  rgb += uLift;

  // The page's own vignette (an ellipse in the CSS of .cw-bg::after), so objects near the edge darken with the sky behind them.
  vec2 d = vec2((vUv.x - 0.5) / 1.2, ((1.0 - vUv.y) - 0.45) / 0.9);
  float edge = clamp((length(d) - 0.55) / 0.45, 0.0, 1.0);
  rgb *= 1.0 - clamp(uVig * 3.0, 0.0, 1.0) * edge;

  float outA = min(a, 1.0);
  gl_FragColor = vec4(rgb, 1.0);
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
  gl_FragColor.rgb += (hash12(gl_FragCoord.xy) - 0.5) / 255.0;
  gl_FragColor = vec4(gl_FragColor.rgb * outA, outA);
}
`;

export const GRADE_UNIFORMS = ["tDiffuse", "uWarm", "uSat", "uCon", "uLift", "uVig"] as const;
