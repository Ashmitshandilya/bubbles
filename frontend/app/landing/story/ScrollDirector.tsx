"use client";

import { useEffect } from "react";
import { ENTER_VARIANTS, skyAt, timeOfDay, type BlendedSky } from "../atmosphere/palette";
import { mixSky, phaseMixAtDay, scrimCss } from "../atmosphere/sky";
import { restorePaused } from "./motion";
import { CHAPTERS, CHAPTER_INDEX, clamp01, measureRects, range, resetStory, rotateFocus, smooth, story } from "./store";

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
/** The opening sky eases from dawn to the visitor's time of day over this long after the page starts. */
const TOD_RAMP_S = 1.1;
/** The example cycle day (0..27.999) runs over this part of the cycle chapter's progress (shared with CycleDay). */
const CYCLE_DAYS = { from: 0.04, to: 0.62, span: 27.999 } as const;

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

    const companion = CHAPTER_INDEX.companion;
    const cycle = CHAPTER_INDEX.cycle;
    // "Her sky follows your clock": the opening chapter takes the visitor's time of day, eased in after load.
    const tod = timeOfDay(new Date().getHours());
    let todK = tod === "dawn" ? 1 : 0;
    let skyKey = "";
    let enterTone: string = CHAPTERS[0].tone;
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

      // The sky: the colour script, blended through the hand-over, the cycle tinted by the example day.
      const sk = story.sky;
      if (todK < 1) todK = Math.min(1, todK + dt / TOD_RAMP_S);
      const t = smooth(story.blend);
      const phase = phaseMixAtDay(range(story.chapters[cycle].p, CYCLE_DAYS.from, CYCLE_DAYS.to) * CYCLE_DAYS.span);
      const key = `${current}|${t.toFixed(3)}|${phase.toFixed(3)}|${todK.toFixed(3)}`;
      if (key !== skyKey) {
        skyKey = key;
        let blended: BlendedSky;
        if (current !== 0) blended = skyAt(current, t, phase);
        else if (todK < 1) blended = mixSky(skyAt(0, t, phase, "dawn"), skyAt(0, t, phase, tod), smooth(todK));
        else blended = skyAt(0, t, phase, tod);
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
        // The opening chapter's own text tone follows its time-of-day variant (night is a dark sky).
        const own = todK >= 0.5 ? ENTER_VARIANTS[tod].tone : CHAPTERS[0].tone;
        if (own !== enterTone) {
          enterTone = own;
          sections[0].dataset.tone = own;
        }
      }
      const darkGoal = sk.tone === "dark" ? 1 : 0;
      if (sk.dark !== darkGoal) {
        sk.dark += (darkGoal - sk.dark) * (1 - Math.exp(-dt * 5));
        if (Math.abs(darkGoal - sk.dark) < 0.002) sk.dark = darkGoal;
        sk.v += 1;
      }
      const lead = story.blend < 0.5 ? current : next;
      const portalDive = current === 0 ? range(story.chapters[0].p, 0.42, 1) : 0;
      const portalBloom = current === companion ? story.blend : 0;
      // The nav reads against whatever fills the screen, portals included.
      const tone = portalDive > 0.55 ? "dark" : portalBloom > 0.55 ? "light" : sk.tone;
      if (root.dataset.tone !== tone) root.dataset.tone = tone;
      if (root.dataset.active !== CHAPTERS[lead].key) root.dataset.active = CHAPTERS[lead].key;
      // Where the story is, fractionally (4.5 = halfway from chapter 4 to 5): the rail's ticks grow and fade from it.
      setRoot("--ch", fmt(current + story.blend));

      // Portal 1: the hero opens into the body.
      // (Only drawn while the hero is on stage; afterwards the base colour already matches.)
      setRoot("--dive", fmt(portalDive * portalDive));
      // ...and it opens from the bubble Bubbles stands in (her body centre), not a fixed spot on the screen.
      if (portalDive > 0 && story.bubbles.visible) {
        setRoot("--dive-x", `${Math.round(story.bubbles.feet.x)}px`);
        setRoot("--dive-y", `${Math.round((story.bubbles.y + story.bubbles.feet.y) / 2)}px`);
      }
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
