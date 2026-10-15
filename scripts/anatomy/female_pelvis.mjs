// Procedural uterus (with uterine tubes and ovarian ligaments) and ovaries.
// ILLUSTRATIVE: BodyParts3D and Z-Anatomy are built from a male donor, so there is no
// measured female pelvis to take. Proportions follow standard adult nulliparous
// textbook values (uterus ~7.5 x 5 x 3 cm, anteverted and anteflexed; tube ~10 cm;
// ovary ~3 x 2 x 1.5 cm in the ovarian fossa), placed in the BodyParts3D pelvis.
// Coordinates: metres, BodyParts3D frame after the build's axis swap
// (Y up, +Z anterior, +X the body's left). Output: { pos: number[], idx: number[] }.

const add = (a, b) => a.map((v, i) => v + b[i]);
const sub = (a, b) => a.map((v, i) => v - b[i]);
const mul = (a, k) => a.map((v) => v * k);
const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
const norm = (a) => mul(a, 1 / (Math.hypot(...a) || 1));
const smooth = (e0, e1, x) => { const t = Math.min(1, Math.max(0, (x - e0) / (e1 - e0))); return t * t * (3 - 2 * t); };
const lerp = (a, b, t) => a + (b - a) * t;

// Closed surface swept along a spine: rings of V vertices for u in (0,1), one pole vertex at
// each end, shared seam (indices wrap), so the mesh is watertight and welds cleanly.
// ring(u, v) returns a world-space point for 0<u<1, v in [0, 2pi).
function sweep(out, U, V, ring, pole0, pole1) {
  const base = out.pos.length / 3, start = out.idx.length;
  out.pos.push(...pole0);
  for (let i = 1; i < U; i++) for (let j = 0; j < V; j++) out.pos.push(...ring(i / U, (j / V) * Math.PI * 2));
  out.pos.push(...pole1);
  const r = (i, j) => base + 1 + (i - 1) * V + (j % V);
  const last = base + 1 + (U - 1) * V;
  for (let j = 0; j < V; j++) out.idx.push(base, r(1, j + 1), r(1, j));
  for (let i = 1; i < U - 1; i++) for (let j = 0; j < V; j++) {
    out.idx.push(r(i, j), r(i, j + 1), r(i + 1, j + 1), r(i, j), r(i + 1, j + 1), r(i + 1, j));
  }
  for (let j = 0; j < V; j++) out.idx.push(r(U - 1, j), r(U - 1, j + 1), last);
  // Signed volume of this closed piece must be positive, or faces point inward and get culled.
  let vol = 0;
  for (let i = start; i < out.idx.length; i += 3) {
    const [a, b, c] = [0, 1, 2].map((k) => out.pos.slice(out.idx[i + k] * 3, out.idx[i + k] * 3 + 3));
    vol += dot(a, cross(b, c)) / 6;
  }
  if (!(vol > 0)) throw new Error('sweep winding points inward');
}

// Centripetal-ish Catmull-Rom through points, sampled at t in [0,1].
function spline(pts) {
  const n = pts.length - 1;
  const at = (t) => {
    const f = Math.min(n - 1e-9, Math.max(0, t * n)), k = Math.floor(f), s = f - k;
    const p0 = pts[Math.max(0, k - 1)], p1 = pts[k], p2 = pts[k + 1], p3 = pts[Math.min(n, k + 2)];
    return [0, 1, 2].map((i) => 0.5 * (2 * p1[i] + (-p0[i] + p2[i]) * s + (2 * p0[i] - 5 * p1[i] + 4 * p2[i] - p3[i]) * s * s + (-p0[i] + 3 * p1[i] - 3 * p2[i] + p3[i]) * s * s * s));
  };
  return at;
}

// Round tube along a spline with radius(t); rotation-minimising frame so it never twists.
function tube(out, pts, radius, U = 90, V = 18, capEnd = 0.6) {
  const at = spline(pts);
  const frames = [];
  let n = null;
  for (let i = 0; i <= U; i++) {
    const t = i / U, c = at(t), T = norm(sub(at(Math.min(1, t + 1e-3)), at(Math.max(0, t - 1e-3))));
    if (!n) n = norm(cross(T, Math.abs(T[1]) < 0.9 ? [0, 1, 0] : [1, 0, 0]));
    n = norm(sub(n, mul(T, dot(n, T))));
    frames.push({ c, T, n, b: cross(T, n) });
  }
  const ringPt = (u, v) => {
    const f = frames[Math.round(u * U)], r = radius(u);
    return add(f.c, add(mul(f.n, Math.cos(v) * r), mul(f.b, Math.sin(v) * r)));
  };
  // Rounded caps: poles pulled out by part of the end radius; a negative capEnd dishes the end in.
  sweep(out, U, V, ringPt, sub(frames[0].c, mul(frames[0].T, radius(0) * 0.6)), add(frames[U].c, mul(frames[U].T, radius(1) * capEnd)));
  return at;
}

// ---- Uterus body: anteflexed spine from the external os (u=0) to the fundus (u=1). ----
const OS = [0, 0.797, 0.064], BEND = [0, 0.836, 0.066], FUNDUS = [0, 0.872, 0.109];
const spineAt = (u) => add(add(mul(OS, (1 - u) ** 2), mul(BEND, 2 * u * (1 - u))), mul(FUNDUS, u * u));
const tangentAt = (u) => norm(sub(spineAt(Math.min(1, u + 1e-3)), spineAt(Math.max(0, u - 1e-3))));
const LAT = [1, 0, 0];
const halfWidth = (u) => lerp(lerp(0.0125, 0.0112, smooth(0.25, 0.38, u)), 0.0255, smooth(0.38, 0.86, u));
const halfDepth = (u) => lerp(lerp(0.0112, 0.0098, smooth(0.25, 0.38, u)), 0.0165, smooth(0.38, 0.72, u));
const ends = (u) => (u < 0.07 ? Math.sqrt(Math.max(0, 1 - ((0.07 - u) / 0.07) ** 2)) : 1) * (u > 0.8 ? Math.sqrt(Math.max(0, 1 - ((u - 0.8) / 0.2) ** 2)) : 1);
const uterusPoint = (u, v) => {
  const T = tangentAt(u), N = norm(cross(LAT, T)); // N points anterior along the sagittal plane
  const e = ends(u), c = Math.cos(v), s = -Math.sin(v); // minus: keeps the winding outward
  const p = 2 / lerp(2, 2.6, smooth(0.35, 0.7, u)); // squarer cross-section in the body
  const sx = Math.sign(c) * Math.abs(c) ** p, sy = Math.sign(s) * Math.abs(s) ** p;
  const depth = halfDepth(u) * (sy > 0 ? 0.86 : 1); // anterior (vesical) surface flatter
  return add(spineAt(u), add(mul(LAT, sx * halfWidth(u) * e), mul(N, sy * depth * e)));
};

function ovaryCenter(s) { return [s * 0.047, 0.846, 0.071]; }
const OVARY_AXIS = (s) => norm([s * 0.22, 1, -0.3]);

export function uterus() {
  const out = { pos: [], idx: [] };
  sweep(out, 80, 72, uterusPoint, spineAt(0), spineAt(1));
  for (const s of [1, -1]) {
    // Uterine tube: isthmus running laterally from the cornu in the broad ligament, ampulla
    // arching up and over the lateral side of the ovary, infundibulum opening down onto it.
    const cornu = add(spineAt(0.85), mul(LAT, s * halfWidth(0.85) * 0.45)); // starts inside, exits laterally
    const path = [cornu, [s * 0.031, 0.864, 0.094], [s * 0.045, 0.866, 0.088], [s * 0.057, 0.865, 0.078], [s * 0.064, 0.857, 0.067], [s * 0.064, 0.848, 0.059]];
    const radius = (t) => lerp(lerp(0.0019, 0.0033, smooth(0.2, 0.8, t)), 0.0058, smooth(0.88, 1, t));
    const at = tube(out, path, radius, 140, 20, -0.5);
    // Fimbriae: fine, tapering fronds fanning from the infundibulum rim, the longest one
    // (fimbria ovarica) reaching the ovary's tubal pole.
    const end = at(1), dir = norm(sub(at(1), at(0.97)));
    const side = norm(cross(dir, [0, 1, 0])), up = cross(side, dir);
    const tubalPole = add(ovaryCenter(s), mul(OVARY_AXIS(s), 0.012));
    const N = 13;
    for (let k = 0; k < N; k++) {
      const a = (k / N) * Math.PI * 2, rad = add(mul(side, Math.cos(a)), mul(up, Math.sin(a)));
      const rim = add(end, mul(rad, 0.0052));
      const len = 0.003 + 0.0035 * (0.5 + 0.5 * Math.sin(k * 2.7 + s * 1.3));
      const curl = mul(cross(dir, rad), 0.0016 * Math.sin(k * 1.9));
      const p1 = add(rim, mul(add(mul(dir, 0.9), mul(rad, 0.45)), len * 0.5));
      const p2 = add(add(rim, mul(add(mul(dir, 0.55), mul(rad, 0.9)), len)), curl);
      tube(out, [add(end, add(mul(rad, 0.0036), mul(dir, -0.0012))), p1, p2], (t) => lerp(0.00095, 0.00035, t), 18, 10); // root buried in the funnel wall
    }
    const nearest = add(end, mul(norm(sub(tubalPole, end)), 0.0045));
    const ovaryCore = add(ovaryCenter(s), mul(OVARY_AXIS(s), 0.006)); // ends buried in the ovary
    tube(out, [sub(nearest, mul(dir, 0.0015)), add(mul(add(nearest, tubalPole), 0.5), [0, 0.001, 0]), tubalPole, ovaryCore], (t) => lerp(0.0009, 0.0006, t), 30, 10);
    // Ligament of the ovary: from the uterus below and behind the tube to the ovary's uterine pole.
    const lo = add(spineAt(0.74), add(mul(LAT, s * halfWidth(0.74) * 0.5), mul(norm(cross(LAT, tangentAt(0.74))), -0.005)));
    const pole = sub(ovaryCenter(s), mul(OVARY_AXIS(s), 0.0105));
    tube(out, [lo, add(mul(add(lo, pole), 0.5), [0, -0.003, -0.002]), pole, ovaryCenter(s)], () => 0.0016, 56, 14);
  }
  return out;
}

export function ovaries() {
  const out = { pos: [], idx: [] };
  for (const s of [1, -1]) {
    const c = ovaryCenter(s), A = OVARY_AXIS(s);
    const W = norm(cross(A, [0, 0, 1])), D = cross(A, W); // W medial-lateral (thickness), D anterior-posterior (width)
    const L = 0.0155, Wr = 0.0075, Dr = 0.0102;
    const pt = (u, v) => {
      const th = u * Math.PI, y = -Math.cos(th), r = Math.sin(th);
      const egg = 1 + 0.08 * y; // tubal pole slightly fuller
      // Gentle surface relief so it reads as an ovary, not a pebble.
      const bump = 1 + r * r * (0.025 * Math.sin(5 * th + 1.3 * s) * Math.sin(4 * v) + 0.018 * Math.sin(9 * th) * Math.cos(7 * v + s)); // fades to zero at the poles
      return add(c, add(mul(A, y * L * bump), add(mul(W, Math.cos(v) * r * Wr * egg * bump), mul(D, Math.sin(v) * r * Dr * egg * bump))));
    };
    sweep(out, 56, 64, pt, sub(c, mul(A, L)), add(c, mul(A, L)));
  }
  return out;
}

// Self-check: closed meshes, valid indices, everything inside the true pelvis box.
if (process.argv[1]?.endsWith('female_pelvis.mjs')) {
  for (const [name, m] of [['uterus', uterus()], ['ovaries', ovaries()]]) {
    const nv = m.pos.length / 3;
    if (m.idx.some((i) => i < 0 || i >= nv)) throw new Error(name + ': bad index');
    const edges = new Map();
    for (let i = 0; i < m.idx.length; i += 3) for (let k = 0; k < 3; k++) { const a = m.idx[i + k], b = m.idx[i + (k + 1) % 3]; const key = a < b ? a + ',' + b : b + ',' + a; edges.set(key, (edges.get(key) ?? 0) + 1); }
    const open = [...edges.values()].filter((n) => n !== 2).length;
    const ys = m.pos.filter((_, i) => i % 3 === 1), xs = m.pos.filter((_, i) => i % 3 === 0);
    console.log(name, m.idx.length / 3, 'tris; open edges', open, '; x', Math.min(...xs).toFixed(3), Math.max(...xs).toFixed(3), '; y', Math.min(...ys).toFixed(3), Math.max(...ys).toFixed(3));
    if (open) throw new Error(name + ': not watertight');
    if (Math.max(...xs.map(Math.abs)) > 0.075 || Math.min(...ys) < 0.75 || Math.max(...ys) > 0.9) throw new Error(name + ': outside pelvis');
  }
}
