"use client";

// A simple timed breathing guide. With motion allowed it shows a circle that fills and empties; with "reduce motion" on
// it shows only the words and the countdown. A polite live region announces each change of phase (not every second).

import { useEffect, useRef, useState } from "react";
import { cycleSeconds, patternSentence, phaseAt, phasesOf } from "../../app/lib/wellness-breathing";
import type { Exercise } from "../../app/lib/wellness-types";
import { BTN_PRIMARY, BTN_SECONDARY } from "../hub/HubKit";
import { useReducedMotion } from "./useWellness";

function clock(totalSeconds: number): string {
  const s = Math.max(0, Math.floor(totalSeconds));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

export function BreathingGuide({ exercise }: { exercise: Exercise }) {
  const reduced = useReducedMotion();
  const phases = phasesOf(exercise.pattern);
  const total = Math.max(exercise.minutes, 1) * 60;
  const [running, setRunning] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [done, setDone] = useState(false);
  const last = useRef(0);
  const elapsedRef = useRef(0);

  useEffect(() => {
    if (!running) return;
    last.current = performance.now();
    const timer = window.setInterval(() => {
      const now = performance.now();
      elapsedRef.current += (now - last.current) / 1000;
      last.current = now;
      if (elapsedRef.current >= total) {
        elapsedRef.current = total;
        setRunning(false);
        setDone(true);
      }
      setElapsed(elapsedRef.current);
    }, 200);
    return () => window.clearInterval(timer);
  }, [running, total]);

  const state = phaseAt(phases, elapsed);
  const started = elapsed > 0 || running;
  const scale = state ? 0.55 + state.fill * 0.45 : 0.55;

  function start() {
    setDone(false);
    elapsedRef.current = 0;
    setElapsed(0);
    setRunning(true);
  }

  return (
    <div className="flex flex-col items-center gap-4 rounded-3xl bg-tint-grape p-5 text-center">
      <p className="m-0 text-body-sm font-semibold text-ink-soft">
        {phases.length ? `Pattern: ${patternSentence(phases)}. ${cycleSeconds(phases)} seconds a round, about ${exercise.minutes} minutes.` : ""}
      </p>

      {started && !done && state && (
        <>
          {!reduced && (
            <div className="flex h-40 w-40 items-center justify-center" aria-hidden="true">
              <div
                className="h-40 w-40 rounded-full border-4 border-bubbles-grape bg-white"
                style={{ transform: `scale(${scale})`, transition: "transform 220ms linear" }}
              />
            </div>
          )}
          <div aria-hidden="true">
            <p className="m-0 font-display text-h2 text-ink">{state.phase.label}</p>
            <p className="m-0 font-display text-metric-lg text-bubbles-grape-deep">{state.secondsLeft}</p>
          </div>
          <p className="m-0 text-body-sm font-bold text-ink-soft">
            Round {state.cycle + 1} · {clock(elapsed)} of {clock(total)}
          </p>
          <div role="status" aria-live="polite" className="sr-only">
            {running ? state.phase.label : "Paused"}
          </div>
        </>
      )}

      {done && (
        <p role="status" className="m-0 font-display text-h3 text-ink">
          Nicely done. Take a moment before you carry on.
        </p>
      )}

      <div className="flex flex-wrap justify-center gap-3">
        {!started || done ? (
          <button type="button" onClick={start} className={BTN_PRIMARY}>
            {done ? "Go again" : "Start"}
          </button>
        ) : (
          <>
            <button type="button" onClick={() => setRunning((r) => !r)} className={BTN_PRIMARY}>
              {running ? "Pause" : "Resume"}
            </button>
            <button
              type="button"
              onClick={() => {
                setRunning(false);
                elapsedRef.current = 0;
                setElapsed(0);
                setDone(false);
              }}
              className={BTN_SECONDARY}
            >
              Stop
            </button>
          </>
        )}
      </div>
    </div>
  );
}
