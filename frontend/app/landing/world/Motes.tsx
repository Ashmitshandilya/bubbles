"use client";

import { useEffect, useImperativeHandle, useMemo, useRef, type Ref } from "react";
import * as THREE from "three";

/** Drifting "cells": soft points that give the inner world depth and life. */
export type MotesHandle = { update: (opacity: number, light: boolean, dt: number) => void };

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

export function Motes({ ref, count }: { ref: Ref<MotesHandle>; count: number }) {
  const points = useRef<THREE.Points>(null);
  const { geometry, material, speeds } = useMemo(() => {
    const positions = new Float32Array(count * 3);
    const colors = new Float32Array(count * 3);
    const speeds = new Float32Array(count);
    const palette = ["#FFD3E6", "#FF8CC2", "#C9B4FF", "#FFE9C7", "#FFFFFF"].map((c) => new THREE.Color(c));
    for (let i = 0; i < count; i += 1) {
      positions[i * 3] = (Math.random() - 0.5) * 30;
      positions[i * 3 + 1] = (Math.random() - 0.5) * 20;
      positions[i * 3 + 2] = -14 + Math.random() * 18;
      const c = palette[i % palette.length];
      colors[i * 3] = c.r;
      colors[i * 3 + 1] = c.g;
      colors[i * 3 + 2] = c.b;
      speeds[i] = 0.08 + Math.random() * 0.22;
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute("color", new THREE.BufferAttribute(colors, 3));
    const material = new THREE.PointsMaterial({
      size: 0.075,
      map: dotTexture(),
      vertexColors: true,
      transparent: true,
      depthWrite: false,
      opacity: 0,
      sizeAttenuation: true,
    });
    return { geometry, material, speeds };
  }, [count]);

  useEffect(
    () => () => {
      geometry.dispose();
      material.map?.dispose();
      material.dispose();
    },
    [geometry, material],
  );

  const state = useRef({ opacity: 0, light: 0 });

  useImperativeHandle(
    ref,
    () => ({
      update(opacity, light, dt) {
        const s = state.current;
        const k = 1 - Math.exp(-3 * dt);
        s.opacity += (opacity - s.opacity) * k;
        s.light += ((light ? 1 : 0) - s.light) * k;
        material.opacity = s.opacity * (0.85 - s.light * 0.45);
        material.blending = s.light > 0.5 ? THREE.NormalBlending : THREE.AdditiveBlending;
        material.color.setRGB(1, 1 - s.light * 0.35, 1 - s.light * 0.2);
        if (points.current) points.current.visible = material.opacity > 0.01;
        const pos = geometry.attributes.position as THREE.BufferAttribute;
        const arr = pos.array as Float32Array;
        for (let i = 0; i < count; i += 1) {
          arr[i * 3 + 1] += speeds[i] * dt;
          if (arr[i * 3 + 1] > 10) arr[i * 3 + 1] = -10;
        }
        pos.needsUpdate = true;
      },
    }),
    [count, geometry, material, speeds],
  );

  return <points ref={points} geometry={geometry} material={material} frustumCulled={false} />;
}
