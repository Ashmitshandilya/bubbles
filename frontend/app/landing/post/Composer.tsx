"use client";

import { useEffect, useRef, useState, type MutableRefObject } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import { story } from "../story/store";
import { fadeAmount, postAllowed, postWanted } from "./grade";
import type { PostStack } from "./PostStack";

/**
 * The single mount point of the post stack (plan step 9), inside the 3D canvas. It exists only in the full tier:
 * when the frame monitor promotes the page to full, the stack fades in; when a demotion comes, it fades out and
 * unmounts, after which three.js renders the scene itself again, exactly as in the lite tier.
 *
 * While mounted it owns the render (a positive-priority frame callback turns off the automatic render), so
 * every frame must end in a draw: the stack's, or the plain one if the stack cannot run.
 */

/** Set when the stack failed once; it is then never mounted again this visit. */
let broken = false;

/** Can this browser render to half-float targets? (Every desktop that reaches the full tier can, but it is not guaranteed.) */
const hasFloatTargets = (extensions: { has: (name: string) => boolean }) =>
  extensions.has("EXT_color_buffer_float") || extensions.has("EXT_color_buffer_half_float");

export function Post() {
  const gl = useThree((s) => s.gl);
  const [mounted, setMounted] = useState(false);
  const wanted = useRef(false);
  // Decided once per visit: the page's address may switch the stack off (?post=0), and the browser may not support it.
  const [capable] = useState(() => postAllowed(window.location.search) && hasFloatTargets(gl.extensions));

  useFrame(() => {
    wanted.current = capable && !broken && postWanted(story.tier);
    if (wanted.current && !mounted) setMounted(true);
  });

  return mounted ? <Composer wanted={wanted} onGone={() => setMounted(false)} /> : null;
}

function Composer({ wanted, onGone }: { wanted: MutableRefObject<boolean>; onGone: () => void }) {
  const gl = useThree((s) => s.gl);
  const scene = useThree((s) => s.scene);
  const camera = useThree((s) => s.camera);
  const size = useThree((s) => s.size);
  const dpr = useThree((s) => s.viewport.dpr);
  const stack = useRef<PostStack | null>(null);
  const amount = useRef(0);
  /** the latest canvas size, for the effect that creates the stack (which must not re-run on every resize) */
  const latest = useRef({ w: size.width, h: size.height, dpr });

  useEffect(() => {
    latest.current = { w: size.width, h: size.height, dpr };
  });

  useEffect(() => {
    // The bloom code is only fetched when the full tier actually needs it (lite and static visitors never download it).
    let cancelled = false;
    import("./PostStack")
      .then(({ PostStack: Stack }) => {
        if (cancelled) return;
        stack.current = new Stack(gl, scene, camera, latest.current.w, latest.current.h, latest.current.dpr);
      })
      .catch(() => {
        broken = true;
        stack.current = null;
      });
    return () => {
      cancelled = true;
      stack.current?.dispose();
      stack.current = null;
    };
  }, [gl, scene, camera]);

  useEffect(() => {
    stack.current?.resize(size.width, size.height, dpr);
  }, [size.width, size.height, dpr]);

  useFrame((_, rawDt) => {
    const dt = Math.min(rawDt, 1 / 20);
    amount.current = fadeAmount(amount.current, wanted.current, dt);
    const gone = !wanted.current && amount.current <= 0;
    const s = stack.current;
    if (s && !broken && !gone) {
      try {
        s.render(dt, story.sky.bloom, story.sky.grade, amount.current);
        return;
      } catch {
        broken = true;
      }
    }
    // No stack to draw with (faded out, failed, or not built yet): the plain render, then let go of the render.
    gl.render(scene, camera);
    if (gone || broken) onGone();
  }, 1);

  return null;
}
