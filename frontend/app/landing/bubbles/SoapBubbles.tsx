"use client";

import { useEffect, useMemo, useRef } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import * as THREE from "three";
import { hexToUnit } from "../atmosphere/sky";
import { measureKeepOut, type Rect } from "../story/keepOut";
import { CHAPTERS, story } from "../story/store";
import { LAYER_OVERLAY } from "../world/layers";
import { Droplets, MAX_DROPS } from "./pop";
import { SOAP_FRAG, SOAP_VERT } from "./soap.glsl";
import { MAX_BUBBLES, SoapField, bubbleCount, levelAt } from "./soap";

/**
 * The iridescent soap bubbles. One instanced sphere mesh (bubbles first, then the droplets of popped ones),
 * parented to the camera so every bubble keeps its place on screen however the chapter rigs move the camera.
 * Bubble motion is the pure SoapField (viewport px); this only maps px to camera space and uploads.
 * Tiers: full draws 12, lite 6, static none (CSS bubbles show instead).
 */

const CAP = MAX_BUBBLES + MAX_DROPS;
const DROP_DEPTH = 6.5;
/** Anything a click should leave alone: bubbles never steal a tap from a control. */
const INTERACTIVE = "a, button, input, textarea, select, summary, label, [role='button'], [tabindex]";

export function SoapBubbles() {
  const camera = useThree((s) => s.camera) as THREE.PerspectiveCamera;
  const scene = useThree((s) => s.scene);
  /** frame-to-frame bookkeeping that must not trigger renders */
  const live = useRef({ root: null as HTMLElement | null, lead: -1, stale: true, skySeen: -1, warm: 0 });

  const rig = useMemo(() => {
    const geometry = new THREE.SphereGeometry(1, 28, 20);
    const attr = (name: string) => {
      const a = new THREE.InstancedBufferAttribute(new Float32Array(CAP), 1);
      a.setUsage(THREE.DynamicDrawUsage);
      geometry.setAttribute(name, a);
      return a;
    };
    const seed = attr("aSeed");
    const pop = attr("aPop");
    const alpha = attr("aAlpha");
    const hover = attr("aHover");
    const uniforms = {
      uTime: { value: 0 },
      uWobble: { value: 1 },
      uTop: { value: new THREE.Vector3(0.96, 0.93, 0.98) },
      uMid: { value: new THREE.Vector3(0.98, 0.97, 0.96) },
      uHor: { value: new THREE.Vector3(0.99, 0.95, 0.92) },
      // display colours straight to the canvas: the bubbles sit on the overlay layer, outside the post stack
      uLinear: { value: 0 },
    };
    const material = new THREE.ShaderMaterial({
      vertexShader: SOAP_VERT,
      fragmentShader: SOAP_FRAG,
      uniforms,
      transparent: true,
      depthWrite: false,
      // both faces: three.js draws the inner (back) face first, so each bubble shows the far side's reflection too
      side: THREE.DoubleSide,
    });
    const mesh = new THREE.InstancedMesh(geometry, material, CAP);
    mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    mesh.frustumCulled = false;
    mesh.renderOrder = 4;
    mesh.layers.set(LAYER_OVERLAY);
    mesh.visible = false;
    const field = new SoapField();
    for (let i = 0; i < CAP; i += 1) seed.array[i] = i < MAX_BUBBLES ? field.seed[i] : (i * 0.37) % 1;
    seed.needsUpdate = true;
    return { geometry, material, mesh, seed, pop, alpha, hover, uniforms, field, drops: new Droplets(), rects: [] as Rect[] };
  }, []);

  useEffect(() => {
    const { mesh, geometry, material, field, drops } = rig;
    const addedCamera = camera.parent !== scene;
    if (addedCamera) scene.add(camera);
    camera.add(mesh);
    // The bubbles live on their own layer (see world/layers.ts); the camera sees it, so every tier draws them.
    camera.layers.enable(LAYER_OVERLAY);

    const root = document.querySelector<HTMLElement>(".cw");
    const state = live.current;
    state.root = root;
    const stale = () => {
      state.stale = true;
    };
    const resize = new ResizeObserver(stale);
    if (root) resize.observe(root);
    void document.fonts?.ready.then(stale);

    const onClick = (event: MouseEvent) => {
      if ((event.target as Element | null)?.closest?.(INTERACTIVE)) return;
      const i = field.hit(event.clientX, event.clientY);
      if (i >= 0 && field.popAt(i)) drops.burst(field.x[i], field.y[i], field.r[i]);
    };
    let hovering = false;
    const onMove = (event: PointerEvent) => {
      if (event.pointerType !== "mouse") return;
      const on = field.hoverAt(event.clientX, event.clientY);
      if (on !== hovering) {
        hovering = on;
        root?.toggleAttribute("data-bubble-hover", on);
      }
    };
    window.addEventListener("click", onClick);
    window.addEventListener("pointermove", onMove, { passive: true });

    return () => {
      window.removeEventListener("click", onClick);
      window.removeEventListener("pointermove", onMove);
      resize.disconnect();
      root?.removeAttribute("data-soap");
      root?.removeAttribute("data-bubble-hover");
      state.root = null;
      camera.layers.disable(LAYER_OVERLAY);
      camera.remove(mesh);
      if (addedCamera) scene.remove(camera);
      geometry.dispose();
      material.dispose();
    };
  }, [camera, scene, rig]);

  useFrame((state, rawDt) => {
    const { mesh, field, drops, rects, uniforms, pop, alpha, hover } = rig;
    const l = live.current;
    const active = bubbleCount(story.tier);
    if (active === 0) {
      if (mesh.visible) {
        mesh.visible = false;
        l.root?.removeAttribute("data-soap");
      }
      return;
    }
    if (!mesh.visible) {
      mesh.visible = true;
      l.root?.setAttribute("data-soap", "gl");
    }
    // Pause freezes the field, but a visitor who arrived with Pause remembered still gets a first settled frame (about half a second).
    if (!story.paused) l.warm = 30;
    if (story.paused) {
      if (l.warm >= 30) return;
      l.warm += 1;
    }

    // Copy blocks of the chapter on stage: measured when it changes, and after a resize or font load.
    const lead = story.blend < 0.5 ? story.current : Math.min(story.current + 1, CHAPTERS.length - 1);
    if (l.root && (lead !== l.lead || l.stale)) {
      l.lead = lead;
      l.stale = false;
      measureKeepOut(l.root, CHAPTERS[lead].key, rects);
    }

    const dt = Math.min(rawDt, 1 / 20);
    const vw = state.size.width;
    const vh = state.size.height;
    const time = state.clock.elapsedTime;
    field.step(dt, {
      vw,
      vh,
      mobile: story.mobile,
      time,
      level: levelAt(story.current, story.blend),
      active,
      excite: story.excite,
      pointer: story.pointer.has && !story.mobile ? story.pointer : null,
      rects,
    });
    drops.step(dt);

    uniforms.uTime.value = time;
    if (l.skySeen !== story.sky.v) {
      l.skySeen = story.sky.v;
      uniforms.uTop.value.set(...hexToUnit(story.sky.top));
      uniforms.uMid.value.set(...hexToUnit(story.sky.mid));
      uniforms.uHor.value.set(...hexToUnit(story.sky.horizon));
    }

    // px on screen to camera space at distance d (the mesh is a child of the camera); radius 0 hides an instance.
    const tanH = Math.tan((camera.fov * Math.PI) / 360);
    const aspect = vw / Math.max(1, vh);
    const m = mesh.instanceMatrix.array as Float32Array;
    const put = (k: number, px: number, py: number, radius: number, d: number) => {
      const hh = d * tanH;
      const s = (radius * 2 * hh) / vh;
      const o = k * 16;
      m.fill(0, o, o + 16);
      m[o] = s;
      m[o + 5] = s;
      m[o + 10] = s;
      m[o + 12] = ((px / vw) * 2 - 1) * hh * aspect;
      m[o + 13] = (1 - (py / vh) * 2) * hh;
      m[o + 14] = -d;
      m[o + 15] = 1;
    };
    for (let i = 0; i < MAX_BUBBLES; i += 1) {
      const shown = field.alpha[i] > 0.002 && field.pop[i] < 1;
      put(i, field.x[i], field.y[i], shown ? field.r[i] : 0, field.depth[i]);
      pop.array[i] = field.pop[i];
      alpha.array[i] = field.alpha[i];
      hover.array[i] = field.hover[i];
    }
    for (let k = 0; k < MAX_DROPS; k += 1) {
      const life = drops.life[k];
      put(MAX_BUBBLES + k, drops.x[k], drops.y[k], life > 0 ? drops.r[k] * (0.55 + 0.45 * life) : 0, DROP_DEPTH);
      pop.array[MAX_BUBBLES + k] = 0;
      alpha.array[MAX_BUBBLES + k] = life > 0 ? 0.9 * life : 0;
      hover.array[MAX_BUBBLES + k] = 0;
    }
    mesh.instanceMatrix.needsUpdate = true;
    pop.needsUpdate = true;
    alpha.needsUpdate = true;
    hover.needsUpdate = true;
  });

  return null;
}
