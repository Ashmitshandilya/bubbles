"use client";

import { useEffect, useImperativeHandle, useMemo, useRef, type Ref } from "react";
import * as THREE from "three";
import { roundedCylinder, spinePoint, taperedTube, vertebraGeometry, V } from "./geometry";
import type { LayoutName, Rig } from "./rig";
import { story } from "../story/store";

/**
 * The living spine: 28 vertebrae that are the recurring object of the story.
 * They stand as a spine, burst into data, gather around Bubbles, become the 28 days
 * of a cycle, a lattice of signals, a timeline of memory, and finally a halo.
 */

export const COUNT = 28;

export const PHASE_COLORS = {
  period: "#E8336F",
  follicular: "#FF8A7A",
  ovulation: "#FFC37A",
  luteal: "#B49BFF",
} as const;

export function phaseOfDay(day: number) {
  if (day <= 5) return "period" as const;
  if (day <= 13) return "follicular" as const;
  if (day <= 16) return "ovulation" as const;
  return "luteal" as const;
}

/** Nerve branches: from a vertebra out to a body system, each carrying an HTML label. */
const NERVES = [
  { key: "brain", from: 27, mid: V(0.4, 3.0, 0.35), end: V(0.1, 3.4, 0.7) },
  { key: "hormones", from: 23, mid: V(1.05, 2.15, 0.45), end: V(2.05, 2.0, 0.85) },
  { key: "heart", from: 19, mid: V(1.0, 1.25, 0.55), end: V(2.15, 0.85, 1.0) },
  { key: "sleep", from: 15, mid: V(-1.0, 0.45, 0.4), end: V(-1.95, 0.05, 0.65) },
  { key: "gut", from: 10, mid: V(1.1, -0.45, 0.55), end: V(2.05, -0.85, 0.95) },
  { key: "cycle", from: 5, mid: V(-0.95, -1.4, 0.55), end: V(-1.8, -1.9, 0.95) },
] as const;

export type SpineHandle = {
  group: THREE.Group | null;
  update: (args: {
    a: Rig["spine"];
    b: Rig["spine"];
    t: number;
    nerves: number;
    dt: number;
    time: number;
    camera: THREE.Camera;
    bubbles: THREE.Vector3;
  }) => void;
  /** world-space end of the nerve currently growing (Bubbles looks at it) */
  nervePoint: THREE.Vector3;
  ringTop: THREE.Vector3;
};

// Deterministic pseudo-random per instance (stable between renders).
const rand = (i: number, salt = 1) => {
  const x = Math.sin(i * 127.1 * salt + salt * 311.7) * 43758.5453;
  return x - Math.floor(x);
};

const UP = new THREE.Vector3(0, 1, 0);
const PEARL = new THREE.Color("#F8EAF1");

type Target = { p: THREE.Vector3; q: THREE.Quaternion; s: number; c: THREE.Color; form: number };
const makeTarget = (): Target => ({ p: new THREE.Vector3(), q: new THREE.Quaternion(), s: 1, c: new THREE.Color(), form: 1 });

/** 1 = a vertebra, 0 = a glossy data bead. Bones become data once they leave the body. */
const FORM: Record<LayoutName, number> = {
  column: 1, scatter: 0, orbit: 0, cycle: 0, lattice: 0, timeline: 0, halo: 0, wave: 0,
};
const BEAD_SCALE = 1.9;

const scratch = {
  m: new THREE.Matrix4(),
  v1: new THREE.Vector3(),
  v2: new THREE.Vector3(),
  v3: new THREE.Vector3(),
  e: new THREE.Euler(),
  q: new THREE.Quaternion(),
};

function basisQuat(out: THREE.Quaternion, yAxis: THREE.Vector3, zAxis: THREE.Vector3) {
  const x = scratch.v3.crossVectors(yAxis, zAxis).normalize();
  scratch.m.makeBasis(x, yAxis, zAxis);
  return out.setFromRotationMatrix(scratch.m);
}

const phaseColor: Record<string, THREE.Color> = Object.fromEntries(
  Object.entries(PHASE_COLORS).map(([k, v]) => [k, new THREE.Color(v)]),
);
const ORBIT_COLORS = [phaseColor.period, phaseColor.follicular, phaseColor.ovulation, phaseColor.luteal];

function layoutTarget(name: LayoutName, i: number, param: number, time: number, out: Target) {
  const n = COUNT;
  out.form = FORM[name];
  const r1 = rand(i, 1);
  const r2 = rand(i, 2);
  const r3 = rand(i, 3);
  switch (name) {
    case "column": {
      spinePoint(i, n, out.p);
      const a = spinePoint(Math.max(0, i - 0.5), n, scratch.v1);
      const b = spinePoint(Math.min(n - 1, i + 0.5), n, scratch.v2);
      const tangent = b.sub(a).normalize();
      out.q.setFromUnitVectors(UP, tangent);
      out.s = 1.12 - 0.46 * (i / (n - 1));
      out.c.copy(PEARL);
      return;
    }
    case "scatter": {
      const theta = r1 * Math.PI * 2 + time * 0.05 + param * 0.9;
      const phi = Math.acos(2 * r2 - 1);
      const radius = 3.6 + r3 * 4.6 + param * 1.4;
      out.p.set(Math.sin(phi) * Math.cos(theta) * radius * 1.35, Math.cos(phi) * radius * 0.7 - 0.4, Math.sin(phi) * Math.sin(theta) * radius - 2.5);
      scratch.e.set(r1 * 6 + time * 0.3 * (r2 - 0.5), r2 * 6 + time * 0.25, r3 * 6);
      out.q.setFromEuler(scratch.e);
      out.s = 0.32 + r3 * 0.38;
      out.c.copy(PEARL).lerp(i % 3 === 0 ? phaseColor.luteal : phaseColor.period, 0.25 + r1 * 0.4);
      return;
    }
    case "orbit": {
      const a = (i / n) * Math.PI * 2 + time * 0.55;
      const radius = 1.25 + 0.12 * Math.sin(i * 2.7);
      out.p.set(Math.cos(a) * radius, 0.85 + 0.16 * Math.sin(a * 2 + time), Math.sin(a) * radius);
      const tangent = scratch.v1.set(-Math.sin(a), 0, Math.cos(a));
      basisQuat(out.q, tangent, scratch.v2.set(Math.cos(a), 0, Math.sin(a)));
      out.s = 0.2;
      out.c.copy(ORBIT_COLORS[i % 4]);
      return;
    }
    case "cycle": {
      const radius = 2.35;
      const today = param; // 0..28
      const theta = Math.PI / 2 - ((i - today) / n) * Math.PI * 2;
      out.p.set(Math.cos(theta) * radius, Math.sin(theta) * radius, 0);
      const tangent = scratch.v1.set(-Math.sin(theta), Math.cos(theta), 0);
      const inward = scratch.v2.set(-Math.cos(theta), -Math.sin(theta), 0);
      basisQuat(out.q, tangent, inward);
      let dist = Math.abs(i - Math.floor(today));
      dist = Math.min(dist, n - dist);
      const focus = Math.max(0, 1 - dist / 1.5);
      out.s = 0.44 + focus * 0.38;
      out.c.copy(phaseColor[phaseOfDay(i + 1)]).lerp(PEARL, focus * 0.25);
      return;
    }
    case "lattice": {
      const k = i + 0.5;
      const phi = Math.acos(1 - (2 * k) / n);
      const theta = Math.PI * (1 + Math.sqrt(5)) * k + time * 0.04;
      const radius = 5.2;
      out.p.set(Math.cos(theta) * Math.sin(phi) * radius * 1.4, Math.cos(phi) * radius * 0.8, Math.sin(theta) * Math.sin(phi) * radius);
      scratch.e.set(r1 * 6, r2 * 6 + time * 0.1, r3 * 6);
      out.q.setFromEuler(scratch.e);
      out.s = 0.24;
      out.c.copy(PEARL).lerp(phaseColor.luteal, 0.35);
      return;
    }
    case "timeline": {
      const x = -9 + i * 0.68 - param * 2.4;
      out.p.set(x, 0.18 * Math.sin(i * 0.55 + time * 0.6), 0);
      scratch.e.set(0, 0, -Math.PI / 2);
      out.q.setFromEuler(scratch.e);
      out.s = 0.18 + 0.15 * (0.5 + 0.5 * Math.sin(i * 0.83));
      out.c.copy(phaseColor[phaseOfDay((i % 28) + 1)]).lerp(PEARL, 0.25);
      return;
    }
    case "halo": {
      const a = (i / n) * Math.PI * 2 + halo.phase;
      const swell = 1 + 0.06 * story.excite;
      out.p.set(Math.cos(a) * swell, 0.05 * Math.sin(a * 3 + time * 1.4), Math.sin(a) * swell);
      const tangent = scratch.v1.set(-Math.sin(a), 0, Math.cos(a));
      basisQuat(out.q, tangent, scratch.v2.set(-Math.cos(a), 0, -Math.sin(a)));
      out.s = 0.24;
      out.c.copy(i % 2 ? phaseColor.luteal : phaseColor.period).lerp(PEARL, 0.35);
      return;
    }
    case "wave": {
      const x = -7.2 + i * 0.53;
      out.p.set(x, 0.32 * Math.sin(i * 0.48 + time * 0.8 + param * 4), 0);
      scratch.e.set(0.3 * Math.cos(i * 0.48 + time * 0.8), 0, -Math.PI / 2);
      out.q.setFromEuler(scratch.e);
      out.s = 0.3;
      out.c.copy(PEARL).lerp(phaseColor.period, 0.2 + 0.2 * Math.sin(i * 0.7));
      return;
    }
  }
}

/** Continuous halo spin; speeds up and swells while the visitor is about to start (story.excite). */
const halo = { phase: 0 };

const lerpAngle = (a: number, b: number, t: number) => {
  let d = (b - a) % (Math.PI * 2);
  if (d > Math.PI) d -= Math.PI * 2;
  if (d < -Math.PI) d += Math.PI * 2;
  return a + d * t;
};

export function Spine({ ref }: { ref: Ref<SpineHandle> }) {
  const group = useRef<THREE.Group>(null);
  const bones = useRef<THREE.InstancedMesh>(null);
  const beads = useRef<THREE.InstancedMesh>(null);
  const discs = useRef<THREE.InstancedMesh>(null);
  const cord = useRef<THREE.Mesh>(null);
  const nerveMeshes = useRef<Array<THREE.Mesh | null>>([]);
  const nodeMeshes = useRef<Array<THREE.Mesh | null>>([]);

  const geo = useMemo(() => {
    const columnPts = Array.from({ length: COUNT }, (_, i) => spinePoint(i, COUNT, new THREE.Vector3()).add(V(0, 0, -0.2)));
    const cordCurve = new THREE.CatmullRomCurve3(columnPts);
    const nerves = NERVES.map((nerve, k) => {
      const start = spinePoint(nerve.from, COUNT, new THREE.Vector3());
      const side = Math.sign(nerve.end.x) || 1;
      const curve = new THREE.CatmullRomCurve3([start.clone().add(V(0.12 * side, 0, -0.1)), start.clone().add(V(0.45 * side, 0.08, 0.15)), nerve.mid, nerve.end]);
      const main = taperedTube(curve, 90, 8, (u) => 0.032 * (1 - u * 0.55));
      const twigA = new THREE.CatmullRomCurve3([nerve.mid.clone(), nerve.mid.clone().add(V(0.18 * side, 0.22, 0.08)), nerve.mid.clone().add(V(0.36 * side, 0.3 + 0.04 * k, 0.14))]);
      const twigB = new THREE.CatmullRomCurve3([nerve.end.clone().add(V(-0.3 * side, 0.03, -0.05)), nerve.end.clone().add(V(-0.16 * side, -0.2, 0.08)), nerve.end.clone().add(V(0.04 * side, -0.3, 0.1))]);
      return {
        main,
        twigs: [taperedTube(twigA, 40, 6, (u) => 0.016 * (1 - u * 0.7)), taperedTube(twigB, 40, 6, (u) => 0.014 * (1 - u * 0.7))],
        end: nerve.end.clone(),
        key: nerve.key,
        side: side > 0 ? "right" : "left",
      };
    });
    return {
      vertebra: vertebraGeometry(),
      disc: roundedCylinder(0.165, 0.055, 0.5, 28),
      cord: taperedTube(cordCurve, 160, 10, () => 0.05),
      node: new THREE.SphereGeometry(0.075, 24, 16),
      bead: new THREE.SphereGeometry(0.17, 36, 24),
      nerves,
    };
  }, []);

  const mats = useMemo(
    () => ({
      bone: new THREE.MeshPhysicalMaterial({
        color: "#FFFFFF", roughness: 0.42, sheen: 0.8, sheenColor: new THREE.Color("#FFB9D6"), sheenRoughness: 0.5,
        clearcoat: 0.35, clearcoatRoughness: 0.3, emissive: new THREE.Color("#FF5FA2"), emissiveIntensity: 0.05,
      }),
      disc: new THREE.MeshPhysicalMaterial({ color: "#C9B4FF", roughness: 0.25, transmission: 0, transparent: true, opacity: 0.85, emissive: new THREE.Color("#9C7BFF"), emissiveIntensity: 0.25 }),
      cord: new THREE.MeshBasicMaterial({ color: "#FF6FAE", transparent: true, opacity: 1 }),
      nerve: new THREE.MeshBasicMaterial({ color: "#FF8CC2", transparent: true, opacity: 0.95 }),
      twig: new THREE.MeshBasicMaterial({ color: "#C9B4FF", transparent: true, opacity: 0.8 }),
      node: new THREE.MeshBasicMaterial({ color: "#FFF1F7" }),
      bead: new THREE.MeshPhysicalMaterial({
        color: "#FFFFFF", roughness: 0.5, clearcoat: 0.35, clearcoatRoughness: 0.4, sheen: 1,
        sheenColor: new THREE.Color("#FFE6F2"), sheenRoughness: 0.6, emissive: new THREE.Color("#FF5FA2"), emissiveIntensity: 0.05,
      }),
    }),
    [],
  );

  useEffect(
    () => () => {
      geo.vertebra.dispose();
      geo.disc.dispose();
      geo.cord.dispose();
      geo.node.dispose();
      geo.bead.dispose();
      geo.nerves.forEach((n) => {
        n.main.dispose();
        n.twigs.forEach((t) => t.dispose());
      });
      Object.values(mats).forEach((m) => m.dispose());
    },
    [geo, mats],
  );

  const sim = useMemo(
    () => ({
      cur: Array.from({ length: COUNT }, makeTarget),
      ta: makeTarget(),
      tb: makeTarget(),
      tmp: makeTarget(),
      init: false,
      pos: new THREE.Vector3(),
      rot: new THREE.Vector3(),
      scale: 1,
      groupInit: false,
      nervePoint: new THREE.Vector3(),
      ringTop: new THREE.Vector3(),
      swirl: Array.from({ length: COUNT }, (_, i) => new THREE.Vector3(rand(i, 4) - 0.5, rand(i, 5) - 0.5, rand(i, 6) - 0.5).normalize()),
      project: new THREE.Vector3(),
      discQ: new THREE.Quaternion(),
      discM: new THREE.Matrix4(),
      one: new THREE.Vector3(1, 1, 1),
    }),
    [],
  );

  useImperativeHandle(
    ref,
    () => ({
      get group() {
        return group.current;
      },
      nervePoint: sim.nervePoint,
      ringTop: sim.ringTop,
      update({ a, b, t, nerves, dt, time, camera, bubbles }) {
        halo.phase += dt * 0.45 * (1 + 1.6 * story.excite);
        const g = group.current;
        const bm = bones.current;
        const dm = discs.current;
        const bd = beads.current;
        if (!g || !bm || !dm || !bd) return;

        // Group transform (eased, shortest-path rotations, optional follow of Bubbles).
        const follow = a.follow + (b.follow - a.follow) * t;
        const gx = a.pos[0] + (b.pos[0] - a.pos[0]) * t + bubbles.x * follow;
        const gy = a.pos[1] + (b.pos[1] - a.pos[1]) * t + bubbles.y * follow;
        const gz = a.pos[2] + (b.pos[2] - a.pos[2]) * t + bubbles.z * follow;
        const sc = a.scale + (b.scale - a.scale) * t;
        const rx = lerpAngle(a.rot[0], b.rot[0], t);
        const ry = lerpAngle(a.rot[1], b.rot[1], t);
        const rz = lerpAngle(a.rot[2], b.rot[2], t);
        const kg = sim.groupInit ? 1 - Math.exp(-4.5 * dt) : 1;
        sim.groupInit = true;
        sim.pos.x += (gx - sim.pos.x) * kg;
        sim.pos.y += (gy - sim.pos.y) * kg;
        sim.pos.z += (gz - sim.pos.z) * kg;
        sim.rot.x = lerpAngle(sim.rot.x, rx, kg);
        sim.rot.y = lerpAngle(sim.rot.y, ry, kg);
        sim.rot.z = lerpAngle(sim.rot.z, rz, kg);
        sim.scale += (sc - sim.scale) * kg;
        g.position.copy(sim.pos);
        g.rotation.set(sim.rot.x, sim.rot.y, sim.rot.z);
        g.scale.setScalar(sim.scale);
        g.updateMatrixWorld();

        const dim = a.dim + (b.dim - a.dim) * t;
        mats.bone.color.setScalar(dim);
        mats.bead.color.setScalar(dim);

        // Per-vertebra morph between the two layouts, staggered along the column.
        const morphing = a.layout !== b.layout;
        for (let i = 0; i < COUNT; i += 1) {
          layoutTarget(a.layout, i, a.param, time, sim.ta);
          layoutTarget(b.layout, i, b.param, time, sim.tb);
          let w = Math.min(1, Math.max(0, t * 1.6 - (i / (COUNT - 1)) * 0.6));
          w = w * w * (3 - 2 * w);
          const target = sim.tmp;
          target.p.lerpVectors(sim.ta.p, sim.tb.p, w);
          if (morphing) target.p.addScaledVector(sim.swirl[i], Math.sin(Math.PI * w) * 1.1);
          target.q.slerpQuaternions(sim.ta.q, sim.tb.q, w);
          target.s = sim.ta.s + (sim.tb.s - sim.ta.s) * w;
          target.c.lerpColors(sim.ta.c, sim.tb.c, w);
          target.form = sim.ta.form + (sim.tb.form - sim.ta.form) * w;

          const cur = sim.cur[i];
          const k = sim.init ? 1 - Math.exp(-(4.5 + rand(i, 7) * 3) * dt) : 1;
          cur.p.lerp(target.p, k);
          cur.q.slerp(target.q, k);
          cur.s += (target.s - cur.s) * k;
          cur.c.lerp(target.c, k);
          cur.form += (target.form - cur.form) * k;
          const vs = cur.s * Math.min(1, cur.form * 1.4);
          scratch.m.compose(cur.p, cur.q, scratch.v1.setScalar(Math.max(0.0001, vs)));
          bm.setMatrixAt(i, scratch.m);
          bm.setColorAt(i, cur.c);
          const bs = cur.s * BEAD_SCALE * Math.min(1, (1 - cur.form) * 1.4);
          scratch.m.compose(cur.p, cur.q, scratch.v1.setScalar(Math.max(0.0001, bs)));
          bd.setMatrixAt(i, scratch.m);
          bd.setColorAt(i, cur.c);
        }
        sim.init = true;
        bm.instanceMatrix.needsUpdate = true;
        if (bm.instanceColor) bm.instanceColor.needsUpdate = true;
        bd.instanceMatrix.needsUpdate = true;
        if (bd.instanceColor) bd.instanceColor.needsUpdate = true;

        // Discs and the glowing cord belong to the standing column only.
        const columnWeight = (a.layout === "column" ? 1 - t : 0) + (b.layout === "column" ? t : 0);
        const discScale = Math.pow(columnWeight, 3);
        for (let i = 0; i < COUNT - 1; i += 1) {
          const c0 = sim.cur[i];
          const c1 = sim.cur[i + 1];
          scratch.v2.lerpVectors(c0.p, c1.p, 0.5);
          sim.discQ.slerpQuaternions(c0.q, c1.q, 0.5);
          const s = ((c0.s + c1.s) / 2) * discScale;
          sim.discM.compose(scratch.v2, sim.discQ, scratch.v1.setScalar(Math.max(0.0001, s)));
          dm.setMatrixAt(i, sim.discM);
        }
        dm.instanceMatrix.needsUpdate = true;
        dm.visible = discScale > 0.01;
        if (cord.current) {
          const cw = Math.pow(columnWeight, 4);
          cord.current.visible = cw > 0.02;
          mats.cord.opacity = cw * (0.75 + 0.25 * Math.sin(time * 2.4));
        }

        // Nerve branches grow one after another; their labels follow on screen.
        const vw = story.vw;
        const vh = story.vh;
        let latest = -1;
        geo.nerves.forEach((nerve, k) => {
          const grow = Math.min(1, Math.max(0, nerves * 1.45 - k * 0.09));
          const mesh = nerveMeshes.current[k];
          if (mesh) {
            mesh.visible = grow > 0.001;
            const count = nerve.main.index ? nerve.main.index.count : 0;
            nerve.main.setDrawRange(0, Math.floor((count * grow) / 6) * 6);
            mesh.children.forEach((child) => {
              const twig = (child as THREE.Mesh).geometry;
              const tc = twig.index ? twig.index.count : 0;
              const tg = Math.min(1, Math.max(0, (grow - 0.55) / 0.45));
              twig.setDrawRange(0, Math.floor((tc * tg) / 6) * 6);
            });
          }
          const node = nodeMeshes.current[k];
          if (node) {
            const pop = Math.min(1, Math.max(0, (grow - 0.9) / 0.1));
            node.scale.setScalar(Math.max(0.0001, pop * (1 + 0.12 * Math.sin(time * 3 + k))));
            node.visible = pop > 0;
          }
          if (grow > 0.05) latest = k;

          const label = story.labels.get(nerve.key);
          if (label) {
            sim.project.copy(nerve.end).applyMatrix4(g.matrixWorld).project(camera);
            const x = ((sim.project.x + 1) / 2) * vw;
            const y = ((1 - sim.project.y) / 2) * vh;
            const shown = Math.min(1, Math.max(0, (grow - 0.85) / 0.15));
            label.style.transform = `translate3d(${x.toFixed(1)}px, ${y.toFixed(1)}px, 0)`;
            label.style.opacity = shown.toFixed(3);
            if (label.dataset.side !== nerve.side) label.dataset.side = nerve.side;
          }
        });
        if (latest >= 0) sim.nervePoint.copy(geo.nerves[latest].end).applyMatrix4(g.matrixWorld);
        else sim.nervePoint.copy(sim.pos);

        // Where Bubbles sits on the cycle ring (top of the ring, in world space).
        sim.ringTop.set(0, 2.35 + 0.42, 0).applyMatrix4(g.matrixWorld);
      },
    }),
    [geo, mats, sim],
  );

  return (
    <group ref={group}>
      <instancedMesh ref={bones} args={[geo.vertebra, mats.bone, COUNT]} frustumCulled={false} />
      <instancedMesh ref={beads} args={[geo.bead, mats.bead, COUNT]} frustumCulled={false} />
      <instancedMesh ref={discs} args={[geo.disc, mats.disc, COUNT - 1]} frustumCulled={false} />
      <mesh ref={cord} geometry={geo.cord} material={mats.cord} visible={false} />
      {geo.nerves.map((nerve, k) => (
        <group key={nerve.key}>
          <mesh
            ref={(el) => {
              nerveMeshes.current[k] = el;
            }}
            geometry={nerve.main}
            material={mats.nerve}
            visible={false}
            frustumCulled={false}
          >
            {nerve.twigs.map((twig, j) => (
              <mesh key={j} geometry={twig} material={mats.twig} frustumCulled={false} />
            ))}
          </mesh>
          <mesh
            ref={(el) => {
              nodeMeshes.current[k] = el;
            }}
            geometry={geo.node}
            material={mats.node}
            position={nerve.end}
            visible={false}
          />
        </group>
      ))}
    </group>
  );
}
