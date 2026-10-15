"use client";

import { useEffect, useRef, type CSSProperties } from "react";
import { phaseInk } from "../atmosphere/palette";
import { feelAt, feelBand, type FeelBand } from "./feel";
import { CHAPTER_INDEX, focusOn, isLead, onStoryFrame, range, say, story } from "./store";

// Text ink, not the raw phase colour: the day number is large type on a sky tinted by that same colour (see phaseInk).
const INK = (["#E8336F", "#FF8A7A", "#FFC37A", "#B49BFF"] as const).map(phaseInk);
const PHASE_COLOR = (day: number) => (day <= 5 ? INK[0] : day <= 13 ? INK[1] : day <= 16 ? INK[2] : INK[3]);

type Vars = CSSProperties & Record<`--${string}`, string | number>;

/**
 * The ticking day counter of the example cycle (follows the scroll), with a
 * small "inner weather" sign beside it: how each example day felt, from bright
 * to heavier. Bubbles, sitting on today's bead, quietly mirrors it.
 */
export function CycleDay() {
  const day = useRef<HTMLSpanElement>(null);
  const box = useRef<HTMLParagraphElement>(null);
  const feel = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    let lastM = -1;
    let lastBand: FeelBand | "" = "";
    let lastDf = -1;
    let owned = false;
    let checkedIn = false;
    return onStoryFrame(() => {
      const p = story.chapters[CHAPTER_INDEX.cycle].p;
      const df = range(p, 0.04, 0.62) * 27.999;
      const d = Math.min(28, Math.floor(df) + 1);
      if (day.current && day.current.textContent !== String(d)) day.current.textContent = String(d);
      box.current?.style.setProperty("--day-c", PHASE_COLOR(d));

      const m = feelAt(df);
      const band = feelBand(m);
      const el = feel.current;
      if (el) {
        if (Math.abs(m - lastM) > 0.005) {
          el.style.setProperty("--m", m.toFixed(3));
          lastM = m;
        }
        if (band !== lastBand) {
          el.dataset.feel = band;
          lastBand = band;
        }
      }

      // Bubbles keeps an eye on the sign while the cycle plays.
      if (isLead(CHAPTER_INDEX.cycle) && p < 0.62) {
        story.focus = focusOn(el);
        owned = true;
      } else if (owned) {
        story.focus = null;
        owned = false;
      }

      // The first heavier day (day 22): one warm check-in, forward only, once per visit.
      if (!checkedIn && !story.mobile && lastDf >= 0 && lastDf < 21 && df >= 21) {
        checkedIn = true;
        say("Go easy today. I'm right here.", 3000);
        window.dispatchEvent(new CustomEvent("bubbles:spark", { detail: "heart" }));
      }
      lastDf = df;
    });
  }, []);

  return (
    <p ref={box} className="cw-day-counter">
      <span className="cw-mono">Day</span>
      <span ref={day} className="cw-day-num">
        14
      </span>
      <span className="cw-mono">of about 28</span>
      <span ref={feel} className="cw-feel" data-feel="bright" style={{ "--m": 0.88 } as Vars} aria-hidden="true">
        <svg viewBox="0 0 32 24" className="cw-feel-glyph" focusable="false">
          <g className="cw-feel-rays">
            {Array.from({ length: 8 }, (_, k) => {
              const a = (k / 8) * Math.PI * 2;
              return (
                <line
                  key={k}
                  x1={12 + Math.cos(a) * 7.5}
                  y1={11 + Math.sin(a) * 7.5}
                  x2={12 + Math.cos(a) * 10}
                  y2={11 + Math.sin(a) * 10}
                />
              );
            })}
          </g>
          <circle className="cw-feel-sun" cx="12" cy="11" r="5.5" />
          <path className="cw-feel-cloud" d="M13 20h13a4 4 0 0 0 .4-8 5.5 5.5 0 0 0-10.4-1.4A4.2 4.2 0 0 0 13 20Z" />
          <g className="cw-feel-rain">
            <line x1="16" y1="21.5" x2="15" y2="24" />
            <line x1="20.5" y1="21.5" x2="19.5" y2="24" />
            <line x1="25" y1="21.5" x2="24" y2="24" />
          </g>
        </svg>
        <span className="cw-feel-label">
          <span data-band="bright">Bright day</span>
          <span data-band="steady">Steady day</span>
          <span data-band="heavy">Heavier day</span>
        </span>
      </span>
      <span className="cw-sr">Example: each day of this cycle is marked as a bright, steady or heavier day.</span>
    </p>
  );
}
