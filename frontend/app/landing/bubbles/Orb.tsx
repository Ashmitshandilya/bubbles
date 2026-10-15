"use client";

import { useEffect, useMemo, useRef } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import * as THREE from "three";
import { hexToUnit } from "../atmosphere/sky";
import { CHAPTERS, easeInOut, rectOf, story } from "../story/store";
import { LAYER_SCENE } from "../world/layers";
import { SOAP_FRAG, SOAP_VERT } from "./soap.glsl";

/**
 * The orb: the one giant soap bubble that carries the story. Each chapter that wants it marks a box in its
 * markup with `data-orb` (the CSS bubble that is the whole look in the static tier and the first paint); the
 * orb is drawn exactly over the box of the chapter on stage and glides to the next chapter's box through the
 * hand-over, or shrinks away where the next chapter has none. Same shader as the small bubbles (soap.glsl.ts),
 * finer sphere, slower wobble. It sits on the scene layer, so in the full tier it goes through the post stack
 * (a soft bloom on its window glints and the chapter grade).
 */

type Box = { x: number; y: number; r: number } | null;

const boxOf = (el: Element | null): Box => {
  if (!el) return null;
  const b = rectOf(el);
  return b.width > 1 ? { x: b.left + b.width / 2, y: b.top + b.height / 2, r: b.width / 2 } : null;
};

export function Orb() {
  const camera = useThree((s) => s.camera) as THREE.PerspectiveCamera;
  const scene = useThree((s) => s.scene);
  const live = useRef({ anchors: [] as (Element | null)[], skySeen: -1, shown: false, idle: 0, x: 0, y: 0, r: 0, a: 0, init: false });

  const rig = useMemo(() => {
    const geometry = new THREE.SphereGeometry(1, 96, 64);
    const uniforms = {
      uTime: { value: 0 },
      uWobble: { value: 0.35 },
      uTop: { value: new THREE.Vector3(0.96, 0.93, 0.98) },
      uMid: { value: new THREE.Vector3(0.98, 0.97, 0.96) },
      uHor: { value: new THREE.Vector3(0.99, 0.95, 0.92) },
      uLinear: { value: 0 },
      uSeed: { value: 0.37 },
      uPop: { value: 0 },
      uAlpha: { value: 0 },
      uHover: { value: 0 },
    };
    const material = new THREE.ShaderMaterial({
      vertexShader: SOAP_VERT,
      fragmentShader: SOAP_FRAG,
      uniforms,
      transparent: true,
      depthWrite: false,
      side: THREE.DoubleSide,
    });
    const mesh = new THREE.Mesh(geometry, material);
    mesh.frustumCulled = false;
    mesh.renderOrder = 3;
    mesh.layers.set(LAYER_SCENE);
    mesh.visible = false;
    return { geometry, material, mesh, uniforms };
  }, []);

  useEffect(() => {
    const { mesh, geometry, material } = rig;
    const addedCamera = camera.parent !== scene;
    if (addedCamera) scene.add(camera);
    camera.add(mesh);
    const root = document.querySelector<HTMLElement>(".cw");
    live.current.anchors = Array.from(root?.querySelectorAll("section[data-chapter]") ?? []).map((s) => s.querySelector("[data-orb]"));
    return () => {
      root?.removeAttribute("data-orb");
      camera.remove(mesh);
      if (addedCamera) scene.remove(camera);
      geometry.dispose();
      material.dispose();
    };
  }, [camera, scene, rig]);

  useFrame((state, rawDt) => {
    const { mesh, uniforms } = rig;
    const l = live.current;
    const dt = Math.min(rawDt, 1 / 20);
    if (!story.paused) l.idle += dt;

    // Where the orb should be: the box of the chapter on stage, gliding to the next one through the hand-over.
    const i = story.current;
    const j = Math.min(i + 1, CHAPTERS.length - 1);
    const t = easeInOut(story.blend);
    let A = boxOf(l.anchors[i] ?? null);
    let B = boxOf(l.anchors[j] ?? null);
    const alpha = (A ? 1 - t : 0) + (B ? t : 0);
    // A chapter without a box: the orb stays where it was and shrinks away (or grows in where the next box is).
    if (!A && B) A = { ...B, r: B.r * 0.55 };
    if (!B && A) B = { ...A, r: A.r * 0.55 };
    if (A && B) {
      const gx = A.x + (B.x - A.x) * t;
      const gy = A.y + (B.y - A.y) * t;
      const gr = A.r + (B.r - A.r) * t;
      // Follow the box closely (it is already smoothed by the director); ease only the very first frame in.
      const k = l.init ? 1 - Math.exp(-18 * dt) : 1;
      l.x += (gx - l.x) * k;
      l.y += (gy - l.y) * k;
      l.r += (gr - l.r) * k;
      l.init = true;
    }
    l.a += (alpha - l.a) * (1 - Math.exp(-10 * dt));

    const show = l.a > 0.004 && l.r > 1;
    if (show !== mesh.visible) mesh.visible = show;
    if (show && !l.shown) {
      l.shown = true;
      // The CSS orbs give way to this one once it has drawn a frame.
      document.querySelector<HTMLElement>(".cw")?.setAttribute("data-orb", "gl");
    }
    if (!show) return;

    uniforms.uTime.value = l.idle;
    uniforms.uAlpha.value = l.a;
    uniforms.uLinear.value = story.postLive ? 1 : 0;
    if (l.skySeen !== story.sky.v) {
      l.skySeen = story.sky.v;
      uniforms.uTop.value.set(...hexToUnit(story.sky.top));
      uniforms.uMid.value.set(...hexToUnit(story.sky.mid));
      uniforms.uHor.value.set(...hexToUnit(story.sky.horizon));
    }

    // px on screen to camera space at distance d (the mesh is a child of the camera), as in SoapBubbles.
    const vw = state.size.width;
    const vh = state.size.height;
    const d = 8;
    const hh = d * Math.tan((camera.fov * Math.PI) / 360);
    const s = (l.r * 2 * hh) / vh;
    mesh.scale.setScalar(s);
    mesh.position.set(((l.x / vw) * 2 - 1) * hh * (vw / Math.max(1, vh)), (1 - (l.y / vh) * 2) * hh, -d);
  });

  return null;
}
