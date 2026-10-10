"use client";

import { useEffect, useState } from "react";
import { applyPaused } from "./motion";
import { story } from "./store";

/**
 * The visible "Pause motion" control (WCAG 2.2.2). One button with a fixed name and `aria-pressed` for its
 * state; the glyph turns from "pause" to "play" while motion is paused. Keyboard operable like any button.
 * It stays hidden until the story is running (`.cw[data-story="on"]`, landing.css): with reduced motion or
 * without JavaScript there is nothing to pause. The choice is remembered (story/motion.ts).
 */
export function PauseMotion() {
  const [paused, setPaused] = useState(false);

  // The director has already restored the remembered choice by the time this effect runs (it is earlier in the page).
  useEffect(() => {
    setPaused(story.paused);
  }, []);

  const toggle = () => {
    const root = document.querySelector<HTMLElement>(".cw");
    setPaused(applyPaused(root, !paused, true));
  };

  return (
    <button type="button" className="cw-motion" aria-pressed={paused} onClick={toggle}>
      <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor" aria-hidden="true" focusable="false">
        {paused ? <path d="M8 5.5v13l11-6.5z" /> : <path d="M7 5h3.6v14H7zM13.4 5H17v14h-3.6z" />}
      </svg>
      <span className="cw-motion-label">Pause motion</span>
    </button>
  );
}
