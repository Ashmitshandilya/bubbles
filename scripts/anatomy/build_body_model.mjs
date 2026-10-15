// Builds frontend/public/models/body.glb: BodyParts3D (CC BY-SA 2.1 JP) for most organs,
// Z-Anatomy (CC BY-SA 4.0) for thyroid, lungs, stomach and bladder, procedural (illustrative)
// uterus and ovaries from female_pelvis.mjs. Sources and credits: organs.json, CREDITS.md.
// Usage: cd scripts/anatomy && npm install && node build_body_model.mjs && node add_eyes.mjs   (the eyes carry vertex colours, so they are added after)
// Downloads into <repo>/.anatomy-work (git-ignored by its own .gitignore). No Blender needed.
import { execFileSync } from 'node:child_process';
import { existsSync, mkdirSync, readFileSync, writeFileSync, statSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { Document, NodeIO } from '@gltf-transform/core';
import { ALL_EXTENSIONS, KHRMeshQuantization } from '@gltf-transform/extensions';
import { weld, dedup, simplifyPrimitive, prune, quantize } from '@gltf-transform/functions';
import { MeshoptSimplifier, MeshoptDecoder } from 'meshoptimizer';
import { uterus, ovaries } from './female_pelvis.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const repo = join(here, '..', '..');
const work = join(repo, '.anatomy-work');
const BASE = 'https://dbarchive.biosciencedbc.jp/data/bodyparts3d/LATEST';
const ZIP = 'partof_BP3D_4.0_obj_99';
const out = join(repo, 'frontend', 'public', 'models', 'body.glb');
const cfg = JSON.parse(readFileSync(join(here, 'organs.json'), 'utf8'));

mkdirSync(work, { recursive: true });
writeFileSync(join(work, '.gitignore'), '*\n'); // downloads and extracted sources never get committed
const fetchTo = async (name, file, url = `${BASE}/${name}`) => {
  if (existsSync(file)) return;
  console.log('download', url);
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${url}: HTTP ${res.status}`);
  writeFileSync(file, Buffer.from(await res.arrayBuffer()));
};
await fetchTo('partof_element_parts.txt', join(work, 'partof_element_parts.txt'));
await fetchTo(`${ZIP}.zip`, join(work, 'partof.zip'));
const ZA = join(work, 'zanat', 'ic-organlar.glb');
mkdirSync(dirname(ZA), { recursive: true });
await fetchTo(null, ZA, cfg.sources.zanatomy.url);
if (!existsSync(join(work, ZIP))) execFileSync(process.platform === 'win32' ? 'C:/Windows/System32/tar.exe' : 'bsdtar', ['-xf', 'partof.zip'], { cwd: work, stdio: 'inherit' }); // bsdtar reads zip on Win10+/macOS/Linux

// concept FMA id -> element files (FJxxxx.obj)
const elements = new Map();
for (const line of readFileSync(join(work, 'partof_element_parts.txt'), 'utf8').split(/\r?\n/).slice(1)) {
  const [fma, , fj] = line.split('\t');
  if (!fj) continue;
  if (!elements.has(fma)) elements.set(fma, new Set());
  elements.get(fma).add(fj);
}

// Minimal OBJ reader: v + f only (BP3D files are plain triangle meshes). mm, Z up -> m, Y up, anterior +Z.
function readObj(file, pos, idx) {
  const base = pos.length / 3;
  for (const l of readFileSync(file, 'utf8').split('\n')) {
    if (l.startsWith('v ')) {
      const [, x, y, z] = l.trim().split(/\s+/).map(Number);
      pos.push(x / 1000, z / 1000, -y / 1000);
    } else if (l.startsWith('f ')) {
      const v = l.trim().split(/\s+/).slice(1).map((t) => parseInt(t, 10) - 1 + base);
      for (let i = 1; i + 1 < v.length; i++) idx.push(v[0], v[i], v[i + 1]);
    }
  }
}

// Z-Anatomy organs, moved into the BodyParts3D frame (same scale; offset measured on the kidneys).
await MeshoptDecoder.ready;
const zaDoc = await new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({ 'meshopt.decoder': MeshoptDecoder }).read(ZA);
const zaNodes = new Map(zaDoc.getRoot().listNodes().map((n) => [n.getName(), n]));
const [ox, oy, oz] = cfg.sources.zanatomy.offset_m;
function readZa(name, pos, idx) {
  const node = zaNodes.get(name);
  if (!node?.getMesh()) throw new Error(`Z-Anatomy node missing: ${name}`);
  const W = node.getWorldMatrix(), v = [0, 0, 0];
  for (const prim of node.getMesh().listPrimitives()) {
    const a = prim.getAttribute('POSITION'), base = pos.length / 3;
    for (let i = 0; i < a.getCount(); i++) {
      a.getElement(i, v); const [x, y, z] = v;
      pos.push(W[0] * x + W[4] * y + W[8] * z + W[12] - ox, W[1] * x + W[5] * y + W[9] * z + W[13] - oy, W[2] * x + W[6] * y + W[10] * z + W[14] - oz);
    }
    const ix = prim.getIndices().getArray();
    for (const i of ix) idx.push(base + i);
  }
}
const procedural = { uterus, ovaries };

const geo = [];
for (const organ of cfg.organs) {
  let pos = [], idx = [];
  if (organ.source === 'bp3d') {
    const fjs = new Set(organ.fma.flatMap((f) => [...(elements.get(f) ?? [])]));
    if (!fjs.size) throw new Error(`no BodyParts3D elements for ${organ.id}`);
    for (const fj of fjs) readObj(join(work, ZIP, `${fj}.obj`), pos, idx);
  } else if (organ.source === 'zanatomy') {
    for (const n of organ.nodes) readZa(n, pos, idx);
  } else {
    ({ pos, idx } = procedural[organ.id]());
  }
  const srcTris = idx.length / 3;
  if (organ.fill_holes || organ.refine) ({ pos, idx } = refine(pos, idx, organ.fill_holes, organ.refine ?? 0));
  geo.push([organ, pos, idx]);
  console.log(organ.id.padEnd(11), organ.source.padEnd(10), srcTris, 'source tris ->', idx.length / 3);
}

// Weld, optionally close open boundaries (fan to the loop centroid), split every triangle into
// four `levels` times and Taubin-smooth (shrink-free) so coarse source meshes read as soft tissue.
function refine(pos, idx, fill, levels) {
  const ids = new Map(), P = [], remap = [];
  for (let i = 0; i < pos.length; i += 3) {
    const k = `${pos[i].toFixed(6)},${pos[i + 1].toFixed(6)},${pos[i + 2].toFixed(6)}`;
    if (!ids.has(k)) { ids.set(k, P.length); P.push([pos[i], pos[i + 1], pos[i + 2]]); }
    remap.push(ids.get(k));
  }
  let T = idx.map((i) => remap[i]);
  const nOrig = T.length; // triangles past this index are hole fills (and, after splitting, their children)
  if (fill) {
    const half = new Map();
    for (let i = 0; i < T.length; i += 3) for (let k = 0; k < 3; k++) half.set(`${T[i + k]},${T[i + (k + 1) % 3]}`, 1);
    const next = new Map(); // boundary half-edges walked in reverse give the hole's own winding
    for (let i = 0; i < T.length; i += 3) for (let k = 0; k < 3; k++) {
      const a = T[i + k], b = T[i + (k + 1) % 3];
      if (!half.has(`${b},${a}`)) next.set(b, a);
    }
    const seen = new Set();
    for (const start of next.keys()) {
      if (seen.has(start)) continue;
      const loop = [];
      for (let v = start; v !== undefined && !seen.has(v); v = next.get(v)) { seen.add(v); loop.push(v); }
      if (loop.length < 3) continue;
      // Concentric rings shrinking toward the centroid, vertex count falling with the radius,
      // so the patch is made of near-even triangles (a bare fan leaves shading streaks).
      const c = loop.reduce((s, v) => s.map((x, i) => x + P[v][i] / loop.length), [0, 0, 0]);
      const seg = loop.map((v, i) => Math.hypot(...P[v].map((x, k) => x - P[loop[(i + 1) % loop.length]][k])));
      const per = seg.reduce((a, b) => a + b, 0), R = loop.reduce((s, v) => s + Math.hypot(...P[v].map((x, k) => x - c[k])), 0) / loop.length;
      const K = Math.max(1, Math.round(R / (per / loop.length)));
      const along = (f) => { // point at arc-length fraction f of the hole rim
        let d = f * per, i = 0;
        while (i < loop.length - 1 && d > seg[i]) d -= seg[i++];
        const a = P[loop[i]], b = P[loop[(i + 1) % loop.length]], t = seg[i] ? d / seg[i] : 0;
        return a.map((x, k) => x + (b[k] - x) * t);
      };
      let outer = loop;
      for (let r = 1; r < K; r++) {
        const n = Math.max(6, Math.round(loop.length * (1 - r / K)));
        const inner = Array.from({ length: n }, (_, j) => P.push(along(j / n).map((x, k) => x + (c[k] - x) * (r / K))) - 1);
        for (let i = 0, j = 0; i < outer.length || j < n;) {
          if (j >= n || (i < outer.length && (i + 1) / outer.length < (j + 1) / n)) { T.push(outer[i], outer[(i + 1) % outer.length], inner[j % n]); i++; }
          else { T.push(outer[i % outer.length], inner[(j + 1) % n], inner[j]); j++; }
        }
        outer = inner;
      }
      const ci = P.push(c) - 1;
      for (let i = 0; i < outer.length; i++) T.push(outer[i], outer[(i + 1) % outer.length], ci);
    }
  }
  for (let l = 0; l < levels; l++) {
    const mid = new Map(), out = [];
    const m = (a, b) => { const k = a < b ? `${a},${b}` : `${b},${a}`; if (!mid.has(k)) mid.set(k, P.push(P[a].map((x, i) => (x + P[b][i]) / 2)) - 1); return mid.get(k); };
    for (let i = 0; i < T.length; i += 3) {
      const [a, b, c] = [T[i], T[i + 1], T[i + 2]], ab = m(a, b), bc = m(b, c), ca = m(c, a);
      out.push(a, ab, ca, ab, b, bc, ca, bc, c, ab, bc, ca);
    }
    T = out;
  }
  const fillStart = nOrig * 4 ** levels;
  const nb = P.map(() => new Set());
  for (let i = 0; i < T.length; i += 3) for (let k = 0; k < 3; k++) { nb[T[i + k]].add(T[i + (k + 1) % 3]); nb[T[i + (k + 1) % 3]].add(T[i + k]); }
  // Fair the fill patches (vertices touched only by fill triangles) with bi-Laplacian steps so they
  // continue the surrounding curvature instead of reading as flat fans.
  const inFill = new Uint8Array(P.length).fill(1);
  for (let i = 0; i < fillStart; i++) inFill[T[i]] = 0;
  for (let ring = 0; ring < 3 * (levels + 1); ring++) { // widen to the rim band, whose source lip is often rolled in
    const grow = []; for (let v = 0; v < P.length; v++) if (inFill[v]) for (const u of nb[v]) if (!inFill[u]) grow.push(u);
    for (const u of grow) inFill[u] = 1;
  }
  const free = [...inFill.keys()].filter((v) => inFill[v] && nb[v].size);
  if (free.length) {
    const lap = (v) => { const a = [0, 0, 0]; for (const u of nb[v]) for (let i = 0; i < 3; i++) a[i] += P[u][i] / nb[v].size; return a.map((x, i) => x - P[v][i]); };
    for (let it = 0; it < 400; it++) {
      const L = new Map(); for (const v of free) { L.set(v, lap(v)); for (const u of nb[v]) if (!L.has(u)) L.set(u, lap(u)); }
      for (const v of free) { const l2 = [0, 0, 0]; for (const u of nb[v]) for (let i = 0; i < 3; i++) l2[i] += L.get(u)[i] / nb[v].size; for (let i = 0; i < 3; i++) P[v][i] -= 0.25 * (l2[i] - L.get(v)[i]); }
    }
  }
  for (let it = 0; it < 2 * (6 + 4 * levels); it++) {
    const f = it % 2 ? -0.53 : 0.5;
    const avg = nb.map((s, v) => { const a = [0, 0, 0]; for (const u of s) for (let i = 0; i < 3; i++) a[i] += P[u][i] / s.size; return s.size ? a : P[v]; });
    for (let v = 0; v < P.length; v++) for (let i = 0; i < 3; i++) P[v][i] += f * (avg[v][i] - P[v][i]);
  }
  return { pos: P.flat(), idx: T };
}

// Centre x and z on the bounding box and stand the feet on y=0 (the viewer frames the chest at
// y=1.22), baked into vertices so every organ node sits at the scene root with an identity transform.
const min = [Infinity, Infinity, Infinity], max = [-Infinity, -Infinity, -Infinity];
for (const [, pos] of geo) for (let i = 0; i < pos.length; i++) { const k = i % 3; if (pos[i] < min[k]) min[k] = pos[i]; if (pos[i] > max[k]) max[k] = pos[i]; }
const mid = min.map((v, i) => (i === 1 ? v : (v + max[i]) / 2));

const doc = new Document();
const buffer = doc.createBuffer();
const scene = doc.createScene('body');
const meshes = [];
for (const [organ, pos, idx] of geo) {
  const p = new Float32Array(pos.length);
  for (let i = 0; i < pos.length; i++) p[i] = pos[i] - mid[i % 3];
  const prim = doc.createPrimitive()
    .setAttribute('POSITION', doc.createAccessor().setType('VEC3').setArray(p).setBuffer(buffer))
    .setIndices(doc.createAccessor().setType('SCALAR').setArray(new Uint32Array(idx)).setBuffer(buffer))
    .setMaterial(doc.createMaterial(organ.id).setRoughnessFactor(0.6).setMetallicFactor(0));
  const src = cfg.sources[organ.source];
  scene.addChild(doc.createNode(organ.id).setMesh(doc.createMesh(organ.id).addPrimitive(prim)).setExtras({
    name: organ.name, fma: organ.fma, source: organ.source, license: src.license, credit: src.credit, illustrative: !!organ.illustrative,
  }));
  meshes.push([organ, prim]);
}
scene.setExtras({ credit: cfg.credit, license: cfg.license, height_m: +(max[1] - min[1]).toFixed(4), units: 'metres', origin: 'feet at y=0, centred in x and z', up: '+Y', anterior: '+Z', left: '+X' });
doc.getRoot().getAsset().copyright = cfg.credit;

await MeshoptSimplifier.ready;
await doc.transform(weld());
for (const [organ, prim] of meshes) {
  if (organ.simplify) simplifyPrimitive(prim, { simplifier: MeshoptSimplifier, ratio: organ.simplify, error: organ.simplify_error ?? 0.001 }); // per-organ ratio; unset = keep all
}
for (const [, prim] of meshes) smoothNormals(prim);
await doc.transform(dedup(), prune({ keepLeaves: true }));
// Quantized only (KHR_mesh_quantization), no EXT_meshopt_compression: meshopt's decoder needs WebAssembly, which the
// site's CSP (script-src without 'wasm-unsafe-eval') refuses. Quantized attributes load with no decoder at all, and the
// host's gzip/brotli does the rest of the shrinking.
await doc.transform(quantize());
for (const [, prim] of meshes) { // 16-bit indices wherever they fit: indices are most of the file
  const ix = prim.getIndices(), count = prim.getAttribute('POSITION').getCount();
  if (count <= 65535) ix.setArray(Uint16Array.from(ix.getArray()));
}
mkdirSync(dirname(out), { recursive: true });
await new NodeIO().registerExtensions([KHRMeshQuantization]).write(out, doc);
console.log('wrote', out, (statSync(out).size / 1e6).toFixed(2), 'MB');

// Area-weighted smooth vertex normals (gltf-transform's normals() unwelds into flat normals).
function smoothNormals(prim) {
  const p = prim.getAttribute('POSITION').getArray(), ix = prim.getIndices().getArray(), n = new Float32Array(p.length);
  for (let i = 0; i < ix.length; i += 3) {
    const [a, b, c] = [ix[i] * 3, ix[i + 1] * 3, ix[i + 2] * 3];
    const ux = p[b] - p[a], uy = p[b + 1] - p[a + 1], uz = p[b + 2] - p[a + 2];
    const vx = p[c] - p[a], vy = p[c + 1] - p[a + 1], vz = p[c + 2] - p[a + 2];
    const nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx;
    for (const k of [a, b, c]) { n[k] += nx; n[k + 1] += ny; n[k + 2] += nz; }
  }
  for (let i = 0; i < n.length; i += 3) { const l = Math.hypot(n[i], n[i + 1], n[i + 2]) || 1; n[i] /= l; n[i + 1] /= l; n[i + 2] /= l; }
  prim.setAttribute('NORMAL', doc.createAccessor().setType('VEC3').setArray(n).setBuffer(buffer));
}
