"use client";

import { useEffect, useRef, useState } from "react";
import { BubblesMascot } from "../../components/BubblesMascot";

const MIN_WORKING_MS = 2000;
const LINE_GAP_MS = 380;
const AUTO_OPEN_MS = 4500;

export interface CreatingResult {
  lines: string[];
}

/**
 * "Creating your personal companion". It runs the real setup call and only shows lines the server confirmed after it answered:
 * nothing is announced before it is true. A short minimum keeps the screen from flashing; a failure keeps the answers and offers a retry.
 */
export function Creating({ run, name, onOpen, onBack }: { run: () => Promise<CreatingResult>; name: string; onOpen: () => void; onBack: () => void }) {
  const [phase, setPhase] = useState<"working" | "revealing" | "done" | "failed">("working");
  const [lines, setLines] = useState<string[]>([]);
  const [shown, setShown] = useState(0);
  const [message, setMessage] = useState("");
  const [attempt, setAttempt] = useState(0);
  const started = useRef(-1);

  useEffect(() => {
    if (started.current === attempt) return;           // React runs effects twice in development: set up once per attempt
    started.current = attempt;
    let live = true;
    const began = Date.now();
    setPhase("working");
    setShown(0);
    run().then(
      async (result) => {
        const wait = Math.max(0, MIN_WORKING_MS - (Date.now() - began));
        await new Promise((resolve) => window.setTimeout(resolve, wait));
        if (!live) return;
        setLines(result.lines);
        setPhase("revealing");
      },
      (error: unknown) => {
        if (!live) return;
        setMessage(error instanceof Error ? error.message : "Bubbles couldn't finish setting up just now.");
        setPhase("failed");
      },
    );
    return () => {
      live = false;
      started.current = -1;
    };
  }, [run, attempt]);

  useEffect(() => {
    if (phase !== "revealing") return;
    if (shown >= lines.length) {
      setPhase("done");
      return;
    }
    const timer = window.setTimeout(() => setShown((n) => n + 1), LINE_GAP_MS);
    return () => window.clearTimeout(timer);
  }, [phase, shown, lines.length]);

  useEffect(() => {
    if (phase !== "done") return;
    const timer = window.setTimeout(onOpen, AUTO_OPEN_MS);
    return () => window.clearTimeout(timer);
  }, [phase, onOpen]);

  const title = phase === "done" ? (name ? `All set, ${name}` : "All set") : phase === "failed" ? "Your answers are saved" : "Creating your personal companion";

  return (
    <main className="flex min-h-dvh items-center justify-center bg-blush px-5 py-10">
      <div className="bubbles-rise w-full max-w-[520px] text-center">
        <BubblesMascot size={112} mood={phase === "done" ? "happy" : phase === "failed" ? "calm" : "thinking"} className="mx-auto" />
        <h1 aria-live="polite" className="mt-5 font-display text-h1 text-ink">{title}</h1>

        {phase === "working" && (
          <div role="status" className="mt-3">
            <p className="m-0 text-body font-bold text-muted">Setting things up for you</p>
            <span className="mt-4 inline-flex gap-1.5" aria-hidden="true">
              <span className="bubbles-thinking-dot" />
              <span className="bubbles-thinking-dot" />
              <span className="bubbles-thinking-dot" />
            </span>
          </div>
        )}

        {(phase === "revealing" || phase === "done") && (
          <ul aria-label="What Bubbles set up" className="mx-auto mt-5 flex max-w-[440px] list-none flex-col gap-2 p-0 text-left">
            {lines.slice(0, shown).map((line) => (
              <li key={line} className="bubbles-rise flex items-start gap-3 rounded-2xl border border-line bg-surface px-4 py-3 text-body-sm font-bold text-ink">
                <svg className="mt-0.5 shrink-0 text-bubbles-mint-deep" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M5 12.5l4.5 4.5L19 7.5" />
                </svg>
                {line}
              </li>
            ))}
          </ul>
        )}

        {phase === "done" && (
          <button type="button" onClick={onOpen} className="bubbles-press bubbles-glow mt-6 inline-flex min-h-[56px] items-center justify-center rounded-full bg-bubbles-pink-ink px-8 text-[1.0625rem] font-extrabold text-white">
            Open Bubbles
          </button>
        )}

        {phase === "failed" && (
          <div role="alert" className="mt-4">
            <p className="m-0 text-body text-muted">{message || "Bubbles couldn't finish setting up just now."} Nothing you typed is lost.</p>
            <div className="mt-5 flex flex-wrap justify-center gap-3">
              <button type="button" onClick={() => setAttempt((n) => n + 1)} className="bubbles-press bubbles-glow inline-flex min-h-[52px] items-center rounded-full bg-bubbles-pink-ink px-6 font-extrabold text-white">Try again</button>
              <button type="button" onClick={onBack} className="bubbles-press inline-flex min-h-[52px] items-center rounded-full border border-line bg-surface px-6 font-extrabold text-ink-soft">Go back to my answers</button>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
