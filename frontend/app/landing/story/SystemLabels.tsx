"use client";

import { useEffect, useRef } from "react";
import { story } from "./store";

/**
 * Labels for the body systems. With the 3D world running they ride on the tips of
 * the spine's nerve branches; without it they render as a simple list.
 */
const SYSTEMS = [
  { key: "brain", name: "Brain and mood", signals: "Mood, stress, focus" },
  { key: "hormones", name: "Hormones", signals: "Cycle, energy" },
  { key: "heart", name: "Heart and circulation", signals: "Heart rate, blood pressure" },
  { key: "sleep", name: "Sleep and recovery", signals: "Sleep, activity" },
  { key: "gut", name: "Gut and digestion", signals: "Food, water, symptoms" },
  { key: "cycle", name: "Reproductive health", signals: "Periods, symptoms" },
];

export function SystemLabels() {
  const refs = useRef<Record<string, HTMLLIElement | null>>({});

  useEffect(() => {
    const entries = Object.entries(refs.current);
    for (const [key, el] of entries) if (el) story.labels.set(key, el);
    return () => {
      for (const [key] of entries) story.labels.delete(key);
    };
  }, []);

  return (
    <ul className="cw-systems" aria-label="Body systems Bubbles pays attention to">
      {SYSTEMS.map((s) => (
        <li
          key={s.key}
          ref={(el) => {
            refs.current[s.key] = el;
          }}
          className="cw-sys"
        >
          <strong>{s.name}</strong>
          <span className="cw-mono">{s.signals}</span>
        </li>
      ))}
    </ul>
  );
}
