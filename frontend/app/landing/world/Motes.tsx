"use client";

import { useEffect, useImperativeHandle, useMemo, useRef, type Ref } from "react";
import * as THREE from "three";
import { fireflyFade, fireflyGlow, fireflyThreshold } from "./fireflies";

/**
 * Drifting "cells": soft points that give the inner world depth and life. On the night chapters
 * (`night` > 0, from the rig) most of them fade out and the rest become warm fireflies: bigger, golden, and
 * each twinkling on its own beat while it wanders (plan 2.6, far bokeh at night).
 */
export type MotesHandle = {
  /**
   * `dt` is the frame time, `drift` the time that moves them (0 while motion is paused, so they hold still but
   * still fade with the chapters), `night` 0..1 and `time` the idle clock for the twinkle.
   */
  update: (opacity: number, light: boolean, dt: number, night: number, time: number, drift: number) => void;
};

function dotTexture() {
  const size = 64;
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = size;
  const ctx = canvas.getContext("2d");
  if (ctx) {
    const g = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
    g.addColorStop(0, "rgba(255,255,255,1)");
    g.addColorStop(0.35, "rgba(255,255,255,0.85)");
    g.addColorStop(0.7, "rgba(255,255,255,0.18)");
    g.addColorStop(1, "rgba(255,255,255,0)");
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, size, size);
  }
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

const DOT_SIZE = 0.075;
const FIREFLY_SIZE = 1.9; // times DOT_SIZE at full night
const FIREFLY_GOLD = ["#FFD98A", "#FFE9B0", "#FFC46B", "#FFF1DE"].map((c) => new THREE.Color(c));

export function Motes({ ref, count }: { ref: Ref<MotesHandle>; count: number }) {
  const points = useRef<THREE.Points>(null);
  const { geometry, material, speeds, base, gold, keep, beat, phase } = useMemo(() => {
    const positions = new Float32Array(count * 3);
    const colors = new Float32Array(count * 3);
    const gold = new Float32Array(count * 3);
    const speeds = new Float32Array(count);
    const keep = new Float32Array(count);
    const beat = new Float32Array(count);
    const phase = new Float32Array(count);
    const palette = ["#FFD3E6", "#FF8CC2", "#C9B4FF", "#FFE9C7", "#FFFFFF"].map((c) => new THREE.Color(c));
    for (let i = 0; i < count; i += 1) {
      positions[i * 3] = (Math.random() - 0.5) * 30;
      positions[i * 3 + 1] = (Math.random() - 0.5) * 20;
      positions[i * 3 + 2] = -14 + Math.random() * 18;
      const c = palette[i % palette.length];
      colors[i * 3] = c.r;
      colors[i * 3 + 1] = c.g;
      colors[i * 3 + 2] = c.b;
      const f = FIREFLY_GOLD[i % FIREFLY_GOLD.length];
      gold[i * 3] = f.r;
      gold[i * 3 + 1] = f.g;
      gold[i * 3 + 2] = f.b;
      speeds[i] = 0.08 + Math.random() * 0.22;
      keep[i] = Math.random();
      beat[i] = 0.5 + Math.random() * 1.1;
      phase[i] = Math.random() * Math.PI * 2;
    }
    const base = colors.slice();
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute("color", new THREE.BufferAttribute(colors, 3));
    const material = new THREE.PointsMaterial({
      size: DOT_SIZE,
      map: dotTexture(),
      vertexColors: true,
      transparent: true,
      depthWrite: false,
      opacity: 0,
      sizeAttenuation: true,
    });
    return { geometry, material, speeds, base, gold, keep, beat, phase };
  }, [count]);

  useEffect(
    () => () => {
      geometry.dispose();
      material.map?.dispose();
      material.dispose();
    },
    [geometry, material],
  );

  const state = useRef({ opacity: 0, light: 0, night: 0, recolor: false });

  useImperativeHandle(
    ref,
    () => ({
      update(opacity, light, dt, night, time, drift) {
        const s = state.current;
        const k = 1 - Math.exp(-3 * dt);
        s.opacity += (opacity - s.opacity) * k;
        s.light += ((light ? 1 : 0) - s.light) * k;
        s.night += (night - s.night) * k;
        const glow = s.night > 0.004 ? s.night : 0;
        material.opacity = s.opacity * (0.85 - s.light * 0.45);
        material.blending = s.light > 0.5 ? THREE.NormalBlending : THREE.AdditiveBlending;
        material.color.setRGB(1, 1 - s.light * 0.35, 1 - s.light * 0.2);
        material.size = DOT_SIZE * (1 + (FIREFLY_SIZE - 1) * glow);
        if (points.current) points.current.visible = material.opacity > 0.01;

        const pos = geometry.attributes.position as THREE.BufferAttribute;
        const arr = pos.array as Float32Array;
        const rise = 1 - 0.6 * glow; // fireflies wander more than they rise
        for (let i = 0; i < count; i += 1) {
          arr[i * 3 + 1] += speeds[i] * drift * rise;
          if (glow > 0) arr[i * 3] += Math.sin(time * 0.4 + phase[i]) * 0.14 * drift * glow;
          if (arr[i * 3 + 1] > 10) arr[i * 3 + 1] = -10;
        }
        pos.needsUpdate = true;

        // Colours change only while the night is coming or going (and once more to settle back to the day palette).
        if (glow > 0 || s.recolor) {
          const col = geometry.attributes.color as THREE.BufferAttribute;
          const out = col.array as Float32Array;
          const thr = fireflyThreshold(glow);
          for (let i = 0; i < count; i += 1) {
            const w = fireflyFade(keep[i], thr, glow) * fireflyGlow(glow, time, beat[i], phase[i]);
            for (let c = 0; c < 3; c += 1) {
              const j = i * 3 + c;
              out[j] = (base[j] + (gold[j] - base[j]) * glow) * w;
            }
          }
          col.needsUpdate = true;
          s.recolor = glow > 0;
        }
      },
    }),
    [count, geometry, material, speeds, base, gold, keep, beat, phase],
  );

  return <points ref={points} geometry={geometry} material={material} frustumCulled={false} />;
}
