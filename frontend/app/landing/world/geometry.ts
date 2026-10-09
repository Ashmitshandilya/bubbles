import * as THREE from "three";
import { mergeGeometries } from "three/examples/jsm/utils/BufferGeometryUtils.js";

/**
 * Procedural geometry for Bubbles' world. Everything is generated in code (no model
 * files to download), so the anatomy stays crisp at any size and the landing page
 * ships no binary assets.
 */

const V = (x: number, y: number, z: number) => new THREE.Vector3(x, y, z);

/** A tube whose radius changes along its length: used for the spinal cord and nerves. */
export function taperedTube(
  curve: THREE.Curve<THREE.Vector3>,
  segments: number,
  radial: number,
  radiusAt: (u: number) => number,
) {
  const frames = curve.computeFrenetFrames(segments, false);
  const positions: number[] = [];
  const normals: number[] = [];
  const uvs: number[] = [];
  const indices: number[] = [];
  const point = new THREE.Vector3();
  const normal = new THREE.Vector3();

  for (let i = 0; i <= segments; i += 1) {
    const u = i / segments;
    curve.getPointAt(u, point);
    const r = radiusAt(u);
    for (let j = 0; j <= radial; j += 1) {
      const v = (j / radial) * Math.PI * 2;
      normal
        .set(0, 0, 0)
        .addScaledVector(frames.normals[i], -Math.cos(v))
        .addScaledVector(frames.binormals[i], Math.sin(v))
        .normalize();
      positions.push(point.x + r * normal.x, point.y + r * normal.y, point.z + r * normal.z);
      normals.push(normal.x, normal.y, normal.z);
      uvs.push(u, j / radial);
    }
  }
  for (let i = 0; i < segments; i += 1) {
    for (let j = 0; j < radial; j += 1) {
      const a = i * (radial + 1) + j;
      const b = (i + 1) * (radial + 1) + j;
      indices.push(a, b, a + 1, b, b + 1, a + 1);
    }
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setIndex(indices);
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  geometry.setAttribute("normal", new THREE.Float32BufferAttribute(normals, 3));
  geometry.setAttribute("uv", new THREE.Float32BufferAttribute(uvs, 2));
  return geometry;
}

/** Rounded cylinder (vertebral body, intervertebral disc). */
export function roundedCylinder(radius: number, height: number, bevel = 0.3, segments = 40) {
  const h = height / 2;
  const b = Math.min(radius, h) * bevel;
  const pts: THREE.Vector2[] = [new THREE.Vector2(0, -h)];
  const steps = 6;
  for (let k = 0; k <= steps; k += 1) {
    const a = (k / steps) * (Math.PI / 2);
    pts.push(new THREE.Vector2(radius - b + Math.sin(a) * b, -h + b - Math.cos(a) * b));
  }
  for (let k = 0; k <= steps; k += 1) {
    const a = (k / steps) * (Math.PI / 2);
    pts.push(new THREE.Vector2(radius - b + Math.cos(a) * b, h - b + Math.sin(a) * b));
  }
  pts.push(new THREE.Vector2(0, h));
  return new THREE.LatheGeometry(pts, segments);
}

function prepare(geometry: THREE.BufferGeometry) {
  // mergeGeometries needs identical attribute sets on every part.
  for (const name of Object.keys(geometry.attributes)) {
    if (name !== "position" && name !== "normal" && name !== "uv") geometry.deleteAttribute(name);
  }
  return geometry;
}

/**
 * A stylised vertebra: rounded body, neural arch, spinous and transverse
 * processes. Merged into one geometry so 28 of them render as one instanced draw.
 */
export function vertebraGeometry() {
  const parts: THREE.BufferGeometry[] = [];

  const body = roundedCylinder(0.2, 0.15, 0.45, 36);
  parts.push(body);

  const arch = new THREE.TorusGeometry(0.105, 0.036, 10, 28);
  arch.rotateX(Math.PI / 2);
  arch.translate(0, 0.005, -0.2);
  parts.push(arch);

  const spinous = new THREE.ConeGeometry(0.055, 0.32, 14, 1);
  spinous.rotateX(-Math.PI / 2 - 0.42);
  spinous.translate(0, -0.06, -0.38);
  parts.push(spinous);

  for (const side of [-1, 1]) {
    const transverse = new THREE.CapsuleGeometry(0.04, 0.2, 6, 12);
    transverse.rotateZ(Math.PI / 2);
    transverse.rotateY(side * 0.42);
    transverse.translate(side * 0.2, 0.01, -0.14);
    parts.push(transverse);
  }

  // Every part is indexed and keeps its own smooth normals.
  const merged = mergeGeometries(parts.map(prepare), false);
  if (!merged) throw new Error("vertebra geometry merge failed");
  return merged;
}

/** S-shaped column used for the spine layout (bottom → top). */
export function spinePoint(i: number, count: number, out = new THREE.Vector3()) {
  const t = i / (count - 1);
  const y = -2.55 + t * 5.1;
  // lumbar lordosis → thoracic kyphosis → cervical lordosis
  const z = 0.28 * Math.sin(t * Math.PI * 2 + 0.6) - 0.06;
  return out.set(0, y, z);
}

const ringScratch = {
  m: new THREE.Matrix4(),
  q: new THREE.Quaternion(),
  e: new THREE.Euler(),
  v: new THREE.Vector3(),
  s: new THREE.Vector3(),
};

/** Top of the cycle ring (where Bubbles sits) for a spine group transform, in world space. */
export function ringTopFor(
  spine: { pos: readonly [number, number, number]; rot: readonly [number, number, number]; scale: number },
  out: THREE.Vector3,
) {
  const r = ringScratch;
  r.m.compose(r.v.set(...spine.pos), r.q.setFromEuler(r.e.set(...spine.rot)), r.s.setScalar(spine.scale));
  return out.set(0, 2.77, 0).applyMatrix4(r.m);
}

export { V };
