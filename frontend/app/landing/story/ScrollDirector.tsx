"use client";

import { useEffect } from "react";
import { CHAPTERS, CHAPTER_INDEX, clamp01, range, resetStory, rotateFocus, story } from "./store";

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

function hexToRgb(hex: string): [number, number, number] {
  const v = parseInt(hex.slice(1), 16);
  return [(v >> 16) & 255, (v >> 8) & 255, v & 255];
}
const RGB = CHAPTERS.map((c) => hexToRgb(c.bg));
function mixBg(a: number, b: number, t: number) {
  const ca = RGB[a];
  const cb = RGB[b];
  return `rgb(${Math.round(ca[0] + (cb[0] - ca[0]) * t)} ${Math.round(ca[1] + (cb[1] - ca[1]) * t)} ${Math.round(ca[2] + (cb[2] - ca[2]) * t)})`;
}

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
    if (!story.active) return;

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

    const companion = CHAPTER_INDEX.companion;
    let y = window.scrollY;
    let last = performance.now();
    let raf = 0;

    const frame = (now: number) => {
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

      setRoot("--bg", mixBg(current, next, story.blend));
      const lead = story.blend < 0.5 ? current : next;
      const portalDive = current === 0 ? range(story.chapters[0].p, 0.42, 1) : 0;
      const portalBloom = current === companion ? story.blend : 0;
      // The nav reads against whatever fills the screen, portals included.
      const tone = portalDive > 0.55 ? "dark" : portalBloom > 0.55 ? "light" : CHAPTERS[lead].tone;
      if (root.dataset.tone !== tone) root.dataset.tone = tone;
      if (root.dataset.active !== CHAPTERS[lead].key) root.dataset.active = CHAPTERS[lead].key;

      // Portal 1: the hero opens into the body.
      // (Only drawn while the hero is on stage; afterwards the base colour already matches.)
      setRoot("--dive", fmt(portalDive * portalDive));
      // Portal 2: light blooms out of Bubbles' horn as the companion hands over to care.
      setRoot("--bloom", fmt(portalBloom * portalBloom));
      if (current === companion && story.bubbles.visible) {
        setRoot("--bloom-x", `${Math.round(story.bubbles.horn.x)}px`);
        setRoot("--bloom-y", `${Math.round(story.bubbles.horn.y)}px`);
      }
      rotateFocus();
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
