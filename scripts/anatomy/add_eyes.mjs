// Adds the eyes (eye_left, eye_right: globe, cornea, iris, pupil and optic nerve; eyes.mjs) to frontend/public/models/body.glb.
// Run after build_body_model.mjs (which does not build them: they carry vertex colours, the organs do not).
// Safe to run again: it replaces nodes of the same name. The other organs are not touched.
// Usage: cd scripts/anatomy && npm install && node add_eyes.mjs [model.glb]
import { NodeIO } from '@gltf-transform/core';
import { ALL_EXTENSIONS } from '@gltf-transform/extensions';
import { prune } from '@gltf-transform/functions';
import { statSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { eyes } from './eyes.mjs';

const file = process.argv[2] ?? fileURLToPath(new URL('../../frontend/public/models/body.glb', import.meta.url));
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS);
const doc = await io.read(file);
const root = doc.getRoot();
const scene = root.listScenes()[0];
const buffer = root.listBuffers()[0];

for (const name of ['eye_left', 'eye_right']) {
  const old = root.listNodes().find((n) => n.getName() === name);
  if (old) { old.getMesh()?.dispose(); old.dispose(); }
}

function normals(pos, idx) {
  const n = new Float32Array(pos.length);
  for (let i = 0; i < idx.length; i += 3) {
    const [a, b, c] = [idx[i] * 3, idx[i + 1] * 3, idx[i + 2] * 3];
    const ux = pos[b] - pos[a], uy = pos[b + 1] - pos[a + 1], uz = pos[b + 2] - pos[a + 2];
    const vx = pos[c] - pos[a], vy = pos[c + 1] - pos[a + 1], vz = pos[c + 2] - pos[a + 2];
    const nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx;
    for (const k of [a, b, c]) { n[k] += nx; n[k + 1] += ny; n[k + 2] += nz; }
  }
  // Vertices that share a position (the ring at the pole) must share a normal, or the pole shows a seam.
  const sum = new Map();
  for (let i = 0; i < pos.length; i += 3) {
    const key = `${pos[i].toFixed(7)},${pos[i + 1].toFixed(7)},${pos[i + 2].toFixed(7)}`;
    const s = sum.get(key) ?? [0, 0, 0];
    s[0] += n[i]; s[1] += n[i + 1]; s[2] += n[i + 2];
    sum.set(key, s);
  }
  for (let i = 0; i < pos.length; i += 3) {
    const s = sum.get(`${pos[i].toFixed(7)},${pos[i + 1].toFixed(7)},${pos[i + 2].toFixed(7)}`);
    const l = Math.hypot(...s) || 1;
    n[i] = s[0] / l; n[i + 1] = s[1] / l; n[i + 2] = s[2] / l;
  }
  return n;
}

const material = doc.createMaterial('eyes').setRoughnessFactor(0.3).setMetallicFactor(0);
const made = eyes();
for (const [name, side] of [['eye_left', made.left], ['eye_right', made.right]]) {
  const pos = new Float32Array(side.pos), idx = Uint32Array.from(side.idx);
  const prim = doc.createPrimitive()
    .setAttribute('POSITION', doc.createAccessor().setType('VEC3').setArray(pos).setBuffer(buffer))
    .setAttribute('NORMAL', doc.createAccessor().setType('VEC3').setArray(Int8Array.from(normals(pos, idx), (v) => Math.round(v * 127))).setNormalized(true).setBuffer(buffer))
    .setAttribute('COLOR_0', doc.createAccessor().setType('VEC3').setArray(Uint8Array.from(side.col, (v) => Math.round(v * 255))).setNormalized(true).setBuffer(buffer))
    .setIndices(doc.createAccessor().setType('SCALAR').setArray(pos.length / 3 <= 65535 ? Uint16Array.from(idx) : idx).setBuffer(buffer))
    .setMaterial(material);
  scene.addChild(doc.createNode(name).setMesh(doc.createMesh(name).addPrimitive(prim)).setExtras({
    name: 'Eye', source: 'procedural', license: 'CC BY-SA 4.0', credit: 'Modelled procedurally for Bubbles', illustrative: true, center: side.center,
  }));
}
await doc.transform(prune({ keepLeaves: true })); // the accessors of eyes replaced by a re-run
await io.write(file, doc);
console.log('wrote', file, (statSync(file).size / 1e6).toFixed(2), 'MB');
