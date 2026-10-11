"use client";

import { useEffect } from "react";
import { useThree } from "@react-three/fiber";
import { shouldDrawWorld, worldDprCap } from "../perf/tier";
import { onStoryFrame, story } from "../story/store";

const INPUTS = ["pointermove", "pointerdown", "wheel", "touchstart", "keydown", "resize"] as const;

/**
 * Paces the 3D world from the scroll director's frame loop (the canvas uses frameloop="demand", so the page runs one
 * requestAnimationFrame). It asks for a frame when perf/tier.ts says so (every frame while the visitor scrolls or
 * points, about 30 fps in lite once they are idle, none while "Pause motion" holds an idle page still) and caps the
 * pixel ratio for the current tier. A hidden tab stops the director, so the world stops with it.
 */
export function Governor() {
  const invalidate = useThree((s) => s.invalidate);
  const setDpr = useThree((s) => s.setDpr);

  useEffect(() => {
    let inputAt = performance.now();
    let lastY = story.y;
    let frame = 0;
    let tierSeen = "";
    const touch = () => {
      inputAt = performance.now();
    };
    for (const name of INPUTS) window.addEventListener(name, touch, { passive: true });

    const off = onStoryFrame(() => {
      // The intro (Bubbles growing in) must finish however long the first frame takes, so the idle clock starts once the world is ready.
      if (!story.worldReady) inputAt = performance.now();
      // The damped scroll position keeps moving until it settles, so a glide after the last wheel tick still counts as input.
      if (story.y !== lastY) {
        lastY = story.y;
        inputAt = performance.now();
      }
      if (story.tier !== tierSeen) {
        tierSeen = story.tier;
        if (!story.mobile) setDpr(Math.min(window.devicePixelRatio || 1, worldDprCap(story.tier)));
      }
      frame += 1;
      if (shouldDrawWorld({ tier: story.tier, idleMs: performance.now() - inputAt, paused: story.paused, frame })) invalidate();
    });

    return () => {
      off();
      for (const name of INPUTS) window.removeEventListener(name, touch);
    };
  }, [invalidate, setDpr]);

  return null;
}
