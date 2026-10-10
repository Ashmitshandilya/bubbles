"use client";

import { useEffect, useMemo, useRef } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import * as THREE from "three";
import { SoapBubbles } from "../bubbles/SoapBubbles";
import { Motes, type MotesHandle } from "./Motes";
import { HOP_LIFT, RIGS, type Env, type Rig } from "./rig";
import { ringTopFor } from "./geometry";
import { Spine, type SpineHandle } from "./Spine";
import { Studio } from "./Studio";
import { CHAPTER_INDEX, easeInOut, story } from "../story/store";

/**
 * The director of the 3D scene. Every frame it evaluates the current and next
 * chapter rigs at their scroll progress, blends them, and eases the camera, the
 * spine and an invisible "Bubbles anchor" toward the result. The illustrated Bubbles
 * (an HTML/SVG layer) is drawn exactly on that anchor, so the beads can orbit
 * and halo around it.
 */

const elastic = (t: number) => (t >= 1 ? 1 : 1 - Math.pow(2, -9 * t) * Math.cos(t * Math.PI * 2.6));

export function World() {
  const camera = useThree((s) => s.camera) as THREE.PerspectiveCamera;
  const size = useThree((s) => s.size);
  const spine = useRef<SpineHandle>(null);
  const motes = useRef<MotesHandle>(null);

  const sim = useMemo(
    () => ({
      init: false,
      introAt: -1,
      camPos: new THREE.Vector3(),
      camTarget: new THREE.Vector3(),
      camGoal: new THREE.Vector3(),
      targetGoal: new THREE.Vector3(),
      fov: 35,
      pos: new THREE.Vector3(),
      goalA: new THREE.Vector3(),
      goalB: new THREE.Vector3(),
      goal: new THREE.Vector3(),
      scale: 0.001,
      look: new THREE.Vector3(),
      ray: new THREE.Vector3(),
      head: new THREE.Vector3(),
      lift: new THREE.Vector3(),
      sample: new THREE.Vector3(),
      hopIndex: 0,
      cam: new THREE.PerspectiveCamera(35, 1, 0.1, 80),
    }),
    [],
  );

  useEffect(
    () => () => {
      story.worldReady = false;
      story.bubbles.anchor.unit = 0;
      const root = document.querySelector<HTMLElement>(".cw");
      if (root) root.dataset.world = "off";
    },
    [],
  );

  /** Bubbles' anchor for a rig, in world space. */
  const resolve = (r: Rig, out: THREE.Vector3, aspect: number) => {
    if (r.bubbles.mode === "ring" && spine.current) return out.copy(spine.current.ringTop);
    const cam = sim.cam;
    cam.fov = r.fov;
    cam.aspect = aspect;
    cam.position.set(...r.cam);
    cam.lookAt(r.target[0], r.target[1], r.target[2]);
    cam.updateProjectionMatrix();
    cam.updateMatrixWorld();
    sim.ray.set(r.bubbles.x, r.bubbles.y, 0.5).unproject(cam).sub(cam.position).normalize();
    return out.copy(cam.position).addScaledVector(sim.ray, r.bubbles.z);
  };

  useFrame((state, rawDt) => {
    const dt = Math.min(rawDt, 1 / 20);
    const time = state.clock.elapsedTime;
    if (sim.introAt < 0) {
      sim.introAt = time;
      story.worldReady = true;
      const root = document.querySelector<HTMLElement>(".cw");
      if (root) root.dataset.world = "ready";
    }
    const aspect = size.width / Math.max(1, size.height);
    const env: Env = { mobile: story.mobile, aspect, time, intro: time - sim.introAt };
    const i = story.current;
    const j = Math.min(i + 1, RIGS.length - 1);
    const t = easeInOut(story.blend);
    const A = RIGS[i](story.chapters[i].p, env);
    const B = RIGS[j](story.chapters[j].p, env);
    const L = (a: number, b: number) => a + (b - a) * t;

    // Camera, with a little parallax from the pointer on desktop.
    const px = story.pointer.has && !story.mobile ? story.pointer.x : 0;
    const py = story.pointer.has && !story.mobile ? story.pointer.y : 0;
    sim.camGoal.set(L(A.cam[0], B.cam[0]) + px * 0.32, L(A.cam[1], B.cam[1]) + py * 0.18, L(A.cam[2], B.cam[2]));
    sim.targetGoal.set(L(A.target[0], B.target[0]), L(A.target[1], B.target[1]), L(A.target[2], B.target[2]));
    const kc = sim.init ? 1 - Math.exp(-3.2 * dt) : 1;
    sim.camPos.lerp(sim.camGoal, kc);
    sim.camTarget.lerp(sim.targetGoal, kc);
    camera.position.copy(sim.camPos);
    camera.lookAt(sim.camTarget);
    const fov = L(A.fov, B.fov);
    sim.fov += (fov - sim.fov) * kc;
    if (Math.abs(camera.fov - sim.fov) > 0.01) {
      camera.fov = sim.fov;
      camera.updateProjectionMatrix();
    }
    camera.updateMatrixWorld();

    // Living spine.
    spine.current?.update({ a: A.spine, b: B.spine, t, nerves: L(A.nerves, B.nerves), dt, time, camera, bubbles: sim.pos });

    // Bubbles' anchor glides between chapter positions.
    resolve(A, sim.goalA, aspect);
    resolve(B, sim.goalB, aspect);
    const hopChapter = i === CHAPTER_INDEX.track;
    if (hopChapter) {
      // Carry hop: Bubbles leaps along an arc to where it will sit on the finished ring.
      ringTopFor(B.spine, sim.goalB);
      const lift = story.mobile ? HOP_LIFT.mobile : HOP_LIFT.desktop;
      sim.lift.set(lift[0], lift[1], lift[2]);
      sim.goal.lerpVectors(sim.goalA, sim.goalB, t).addScaledVector(sim.lift, 4 * t * (1 - t));
    } else {
      sim.goal.lerpVectors(sim.goalA, sim.goalB, t);
    }
    const hopping = hopChapter && story.blend > 0 && story.blend < 1;
    const stiff = L(A.bubbles.stiff ?? 0, B.bubbles.stiff ?? 0);
    const kp = sim.init ? 1 - Math.exp(-(hopping ? 12 : 3.1 + 9 * stiff) * dt) : 1;
    sim.pos.lerp(sim.goal, kp);

    const intro = elastic(Math.min(1, (time - sim.introAt) / 1.25));
    const scaleGoal = L(A.bubbles.scale, B.bubbles.scale) * L(A.bubbles.show, B.bubbles.show) * intro;
    sim.scale += (scaleGoal - sim.scale) * (sim.init ? 1 - Math.exp(-6 * dt) : 1);

    // Publish the anchor on screen: pelvis position and pixels per (scaled) unit.
    sim.head.copy(sim.pos).project(camera);
    const ax = ((sim.head.x + 1) / 2) * size.width;
    const ay = ((1 - sim.head.y) / 2) * size.height;
    sim.look.copy(sim.pos).addScaledVector(camera.up, Math.max(0.0001, sim.scale)).project(camera);
    const bx = ((sim.look.x + 1) / 2) * size.width;
    const by = ((1 - sim.look.y) / 2) * size.height;
    story.bubbles.anchor.x = ax;
    story.bubbles.anchor.y = ay;
    story.bubbles.anchor.unit = Math.hypot(bx - ax, by - ay);

    // Publish the carry-hop route in screen px while it is on stage.
    const hop = story.hop;
    if (hopChapter && (story.chapters[i].p > 0.86 || story.blend > 0)) {
      const n = hop.n - 1;
      let best = sim.hopIndex;
      let bestD = Infinity;
      for (let k = 0; k <= n; k += 1) {
        const u = k / n;
        sim.sample.lerpVectors(sim.goalA, sim.goalB, u).addScaledVector(sim.lift, 4 * u * (1 - u)).project(camera);
        const x = ((sim.sample.x + 1) / 2) * size.width;
        const y = ((1 - sim.sample.y) / 2) * size.height;
        hop.pts[k * 2] = x;
        hop.pts[k * 2 + 1] = y;
        if (Math.abs(k - sim.hopIndex) <= 4 || !hop.live) {
          const d = (x - ax) * (x - ax) + (y - ay) * (y - ay);
          if (d < bestD) {
            bestD = d;
            best = k;
          }
        }
      }
      sim.hopIndex = best;
      // Refine to a fractional position on the neighbouring segment, so the trail ends exactly at Bubbles.
      let head = best;
      const nb = best < n ? best + 1 : best - 1;
      const sx = hop.pts[nb * 2] - hop.pts[best * 2];
      const sy = hop.pts[nb * 2 + 1] - hop.pts[best * 2 + 1];
      const len2 = sx * sx + sy * sy;
      if (len2 > 1e-3) {
        const f = ((ax - hop.pts[best * 2]) * sx + (ay - hop.pts[best * 2 + 1]) * sy) / len2;
        if (f > 0) head = best + (nb > best ? 1 : -1) * Math.min(1, f);
      }
      hop.head = story.blend > 0 ? Math.min(1, Math.max(0, head / n)) : 0;
      hop.dest.x = hop.pts[n * 2];
      hop.dest.y = hop.pts[n * 2 + 1];
      hop.live = true;
    } else if (story.worldReady) {
      hop.live = false;
    }

    const lightTone = story.sky.tone === "light"; // the lead sky (includes the opening chapter's time of day)
    motes.current?.update(L(A.motes, B.motes), lightTone, dt);
    sim.init = true;
  });

  return (
    <>
      <Studio />
      <Spine ref={spine} />
      <Motes ref={motes} count={story.mobile ? 380 : 820} />
      <SoapBubbles />
    </>
  );
}
