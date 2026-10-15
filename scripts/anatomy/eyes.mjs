// Procedural eyes: two eyeballs with a cornea bulge, a painted iris and pupil, and the optic nerves running back to the
// optic chiasm. ILLUSTRATIVE: BodyParts3D has no eyes, so the size follows textbook adult values (globe ~24 mm across, cornea
// ~11.7 mm across standing ~2.4 mm proud of the globe, iris ~12 mm, pupil ~3-4 mm, optic nerve ~4 mm thick and ~5 cm long to
// the chiasm). They are placed in the BodyParts3D head: skin front at the eye line measured at z ~ 0.065 m.
// Coordinates: metres, same frame as body.glb (feet at y=0, +Y up, +Z anterior, +X the body's left).
// Output per eye: { pos, idx, col } with one RGB colour per vertex (sclera, iris, pupil, nerve), so one material draws all of it.

const lerp = (a, b, t) => a + (b - a) * t;
const smooth = (e0, e1, x) => { const t = Math.min(1, Math.max(0, (x - e0) / (e1 - e0))); return t * t * (3 - 2 * t); };
const mix = (a, b, t) => a.map((v, i) => lerp(v, b[i], t));
const sub = (a, b) => a.map((v, i) => v - b[i]);
const add = (a, b) => a.map((v, i) => v + b[i]);
const mul = (a, k) => a.map((v) => v * k);
const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
const norm = (a) => mul(a, 1 / (Math.hypot(...a) || 1));
const deg = Math.PI / 180;

export const EYE = {
  y: 1.605,        // eye line
  x: 0.031,        // half the pupil distance (~62 mm)
  z: 0.046,        // globe centre, ~19 mm behind the skin of the face
  radius: 0.012,   // globe radius (24 mm)
  cornea: 0.0024,  // how far the cornea stands proud of the globe
  chiasm: [0.0012, 1.5985, -0.001], // where the two nerves meet, per side (x is mirrored)
};

const SCLERA = [0.95, 0.93, 0.9], SCLERA_BACK = [0.92, 0.84, 0.82];
const LIMBUS = [0.17, 0.12, 0.12], IRIS_OUT = [0.31, 0.2, 0.11], IRIS_IN = [0.58, 0.4, 0.21], PUPIL = [0.015, 0.015, 0.02];
const NERVE = [0.93, 0.87, 0.74];

function globe(side) {
  const { x, y, z, radius: R, cornea } = EYE;
  const C = [side * x, y, z];
  const pos = [], col = [], idx = [];
  // Rings of constant angle from the gaze axis (+Z); fine near the cornea, where the colour changes.
  const thetas = [];
  for (let i = 0; i <= 26; i++) thetas.push((i / 26) * 44 * deg);
  for (let i = 1; i <= 34; i++) thetas.push((44 + (i / 34) * 136) * deg);
  const V = 40;
  for (const t of thetas) {
    for (let j = 0; j < V; j++) {
      const p = (j / V) * Math.PI * 2;
      const d = [Math.sin(t) * Math.cos(p), Math.sin(t) * Math.sin(p), Math.cos(t)];
      const r = R + cornea * (1 - smooth(10 * deg, 33 * deg, t)) ** 1.4; // a smooth bulge over the front
      pos.push(...add(C, mul(d, r)));
      const a = t / deg;
      let c = mix(SCLERA, SCLERA_BACK, smooth(70, 160, a));
      c = mix(c, LIMBUS, 1 - smooth(29, 32, a)); // the dark ring around the cornea
      c = mix(c, mix(IRIS_IN, IRIS_OUT, smooth(10, 25, a)), 1 - smooth(25, 27.5, a));
      c = mix(c, PUPIL, 1 - smooth(8.5, 10.5, a));
      col.push(...c);
    }
  }
  // Single pole vertex at theta=0 is repeated V times in the first ring; collapse is harmless (zero-area triangles are skipped).
  const at = (i, j) => i * V + (j % V);
  for (let i = 0; i < thetas.length - 1; i++) {
    for (let j = 0; j < V; j++) {
      const a = at(i, j), b = at(i, j + 1), c = at(i + 1, j + 1), d = at(i + 1, j);
      if (i > 0) idx.push(a, d, b), idx.push(b, d, c);
      else idx.push(a, d, c);
    }
  }
  return { pos, col, idx };
}

// Round tube along a spline, rotation-minimising frame, closed with rounded caps.
function nerve(side) {
  const { x, y, z, radius: R, chiasm } = EYE;
  const start = [side * (x - 0.0028), y - 0.0004, z - R + 0.0009]; // leaves the globe just inside the back pole
  const end = [side * chiasm[0], chiasm[1], chiasm[2]];
  const mid1 = [side * (x - 0.0105), y - 0.0016, z - 0.0225];
  const mid2 = [side * (x - 0.0215), y - 0.0033, z - 0.0345];
  const pts = [start, mid1, mid2, end];
  const n = pts.length - 1;
  const at = (t) => {
    const f = Math.min(n - 1e-9, Math.max(0, t * n)), k = Math.floor(f), s = f - k;
    const p0 = pts[Math.max(0, k - 1)], p1 = pts[k], p2 = pts[k + 1], p3 = pts[Math.min(n, k + 2)];
    return [0, 1, 2].map((i) => 0.5 * (2 * p1[i] + (-p0[i] + p2[i]) * s + (2 * p0[i] - 5 * p1[i] + 4 * p2[i] - p3[i]) * s * s + (-p0[i] + 3 * p1[i] - 3 * p2[i] + p3[i]) * s * s * s));
  };
  const U = 40, V = 14;
  const frames = [];
  let nrm = null;
  for (let i = 0; i <= U; i++) {
    const t = i / U, c = at(t), T = norm(sub(at(Math.min(1, t + 1e-3)), at(Math.max(0, t - 1e-3))));
    if (!nrm) nrm = norm(cross(T, [0, 1, 0]));
    nrm = norm(sub(nrm, mul(T, dot(nrm, T))));
    frames.push({ c, T, n: nrm, b: cross(T, nrm) });
  }
  const radius = (u) => lerp(0.0021, 0.0017, smooth(0, 0.5, u)) * (u > 0.9 ? lerp(1, 1.25, smooth(0.9, 1, u)) : 1); // a touch thicker where the nerves meet
  const pos = [], col = [], idx = [];
  pos.push(...sub(frames[0].c, mul(frames[0].T, 0.0008)));
  col.push(...NERVE);
  for (let i = 1; i < U; i++) for (let j = 0; j < V; j++) {
    const f = frames[i], r = radius(i / U), v = (j / V) * Math.PI * 2;
    pos.push(...add(f.c, add(mul(f.n, Math.cos(v) * r), mul(f.b, Math.sin(v) * r))));
    col.push(...NERVE);
  }
  pos.push(...add(frames[U].c, mul(frames[U].T, 0.0014)));
  col.push(...NERVE);
  const r = (i, j) => 1 + (i - 1) * V + (j % V), last = 1 + (U - 1) * V;
  for (let j = 0; j < V; j++) idx.push(0, r(1, j + 1), r(1, j));
  for (let i = 1; i < U - 1; i++) for (let j = 0; j < V; j++) idx.push(r(i, j), r(i, j + 1), r(i + 1, j + 1), r(i, j), r(i + 1, j + 1), r(i + 1, j));
  for (let j = 0; j < V; j++) idx.push(r(U - 1, j), r(U - 1, j + 1), last);
  return { pos, col, idx };
}

function join(parts) {
  const out = { pos: [], col: [], idx: [] };
  for (const p of parts) {
    const base = out.pos.length / 3;
    out.pos.push(...p.pos); out.col.push(...p.col);
    for (const i of p.idx) out.idx.push(base + i);
  }
  return out;
}

/** Drops zero-area triangles (the pole ring). */
function tidy({ pos, col, idx }) {
  const keep = [];
  for (let i = 0; i < idx.length; i += 3) {
    const [a, b, c] = [idx[i], idx[i + 1], idx[i + 2]];
    const pa = pos.slice(a * 3, a * 3 + 3), pb = pos.slice(b * 3, b * 3 + 3), pc = pos.slice(c * 3, c * 3 + 3);
    const n = cross(sub(pb, pa), sub(pc, pa));
    if (Math.hypot(...n) < 1e-14) continue;
    keep.push(a, b, c);
  }
  return { pos, col, idx: keep };
}

/** Both eyes, left (+X) and right (-X), each with its own optic nerve. The pivot is the globe centre. */
export function eyes() {
  const make = (side) => ({ ...tidy(join([globe(side), nerve(side)])), center: [side * EYE.x, EYE.y, EYE.z] });
  return { left: make(1), right: make(-1) };
}
