"use client";

import { useEffect } from "react";
import { skyAt } from "../atmosphere/palette";
import { scrimCss } from "../atmosphere/sky";
import { restorePaused } from "./motion";
import { CHAPTERS, clamp01, measureRects, resetStory, smooth, story } from "./store";

/**
 * Drives the whole landing story from one requestAnimationFrame loop (no scroll
 * listeners, no React state). Each frame it eases the scroll position, works out
 * every chapter's progress and hand-over, and writes them as CSS custom properties
 * (`--p`, `--in`, `--out`) on the chapter sections. Chapter layers are fixed to the
 * viewport, so scrolling scrubs the story instead of moving the page.
 *
 * Reduced motion: the director stands down and the page renders as a calm,
 * normally scrolling document (see landing.css).
 */

const HANDOVER = 0.6; // fraction of a viewport used to cross-fade between chapters

const fmt = (v: number) => (Math.round(v * 10000) / 10000).toString();

export function ScrollDirector() {
  useEffect(() => {
    resetStory();
    const root = document.querySelector<HTMLElement>(".cw");
    if (!root) return;
    const motion = window.matchMedia("(prefers-reduced-motion: reduce)");
    story.reduced = motion.matches;
    story.active = !story.reduced;
    root.dataset.story = story.active ? "on" : "static";
    if (!story.active) {
      // Reduced motion is the static tier: no canvas, no loops, the calm page (landing.css).
      story.tier = "static";
      return;
    }
    // The visitor's remembered "Pause motion" choice, restored before the sky and the world decide their tier.
    restorePaused(root);

    const sections = Array.from(root.querySelectorAll<HTMLElement>("section[data-chapter]"));
    const n = sections.length;
    let tops: number[] = [];
    let heights: number[] = [];
    const measure = () => {
      story.vw = window.innerWidth;
      story.vh = window.innerHeight;
      story.mobile = story.vw < 820;
      const sy = window.scrollY;
      tops = sections.map((s) => s.getBoundingClientRect().top + sy);
      heights = sections.map((s) => s.offsetHeight);
    };
    measure();
    const resizeObserver = new ResizeObserver(measure);
    resizeObserver.observe(root);
    window.addEventListener("resize", measure);

    const onPointer = (event: PointerEvent) => {
      story.pointer.x = (event.clientX / story.vw) * 2 - 1;
      story.pointer.y = -(event.clientY / story.vh) * 2 + 1;
      story.pointer.has = event.pointerType === "mouse" || event.pointerType === "pen";
    };
    const onLeave = () => {
      story.pointer.has = false;
    };
    window.addEventListener("pointermove", onPointer, { passive: true });
    document.documentElement.addEventListener("pointerleave", onLeave);

    const written = sections.map(() => ({ p: "", in: "", out: "", on: false }));
    const rootVars: Record<string, string> = {};
    const setRoot = (name: string, value: string) => {
      if (rootVars[name] === value) return;
      rootVars[name] = value;
      root.style.setProperty(name, value);
    };

    let skyKey = "";
    let y = window.scrollY;
    let last = performance.now();
    let raf = 0;

    const frame = (now: number) => {
      measureRects(); // layout reads first, while the last paint left it clean (store.ts rectOf)
      const dt = Math.min(0.05, (now - last) / 1000);
      last = now;
      const raw = window.scrollY;
      y += (raw - y) * (1 - Math.exp(-dt * 9));
      if (Math.abs(raw - y) < 0.05) y = raw;
      story.y = y;

      const x = story.vh * HANDOVER;
      let current = 0;
      for (let i = 0; i < n; i += 1) {
        const top = tops[i];
        const h = heights[i];
        const state = story.chapters[i];
        state.p = clamp01((y - top) / Math.max(1, h - x));
        state.enter = i === 0 ? 1 : clamp01((y - (top - x)) / x);
        state.exit = i === n - 1 ? 0 : clamp01((y - (top + h - x)) / x);
        if (y >= top - 0.5) current = i;

        const w = written[i];
        const section = sections[i];
        const p = fmt(state.p);
        const enter = fmt(state.enter);
        const exit = fmt(state.exit);
        if (w.p !== p) section.style.setProperty("--p", (w.p = p));
        if (w.in !== enter) section.style.setProperty("--in", (w.in = enter));
        if (w.out !== exit) section.style.setProperty("--out", (w.out = exit));
        const on = state.enter > 0 && state.exit < 1;
        if (w.on !== on) {
          w.on = on;
          section.toggleAttribute("data-on", on);
        }
      }
      story.current = current;
      story.blend = story.chapters[current].exit;
      const next = Math.min(current + 1, n - 1);

      // The sky: the colour script, blended through the hand-over.
      const sk = story.sky;
      const t = smooth(story.blend);
      const key = `${current}|${t.toFixed(3)}`;
      if (key !== skyKey) {
        skyKey = key;
        const blended = skyAt(current, t);
        setRoot("--sky-top", blended.top);
        setRoot("--sky-mid", blended.mid);
        setRoot("--sky-hor", blended.horizon);
        setRoot("--bg", blended.mid);
        setRoot("--vig", fmt(blended.grade.vignette));
        setRoot("--scrim", scrimCss(blended.scrim));
        sk.top = blended.top;
        sk.mid = blended.mid;
        sk.horizon = blended.horizon;
        sk.sun = blended.sun;
        sk.key = blended.key;
        sk.rim = blended.rim;
        sk.accent = blended.accent;
        sk.bloom = blended.bloom;
        Object.assign(sk.grade, blended.grade);
        sk.tone = blended.tone;
        sk.v += 1;
      }
      const lead = story.blend < 0.5 ? current : next;
      if (root.dataset.active !== CHAPTERS[lead].key) root.dataset.active = CHAPTERS[lead].key;
      // Where the story is, fractionally (4.5 = halfway from chapter 4 to 5): the rail's ticks grow and fade from it.
      setRoot("--ch", fmt(current + story.blend));
      for (const listener of story.listeners) listener(dt);
      raf = requestAnimationFrame(frame);
    };
    raf = requestAnimationFrame(frame);

    return () => {
      cancelAnimationFrame(raf);
      resizeObserver.disconnect();
      window.removeEventListener("resize", measure);
      window.removeEventListener("pointermove", onPointer);
      document.documentElement.removeEventListener("pointerleave", onLeave);
      story.active = false;
      resetStory();
    };
  }, []);

  return null;
}
