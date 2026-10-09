"use client";

import Link from "next/link";
import { useEffect, useRef, type ReactNode } from "react";
import { BTN_PRIMARY, BTN_SECONDARY, CARD } from "../hub/HubKit";

/**
 * Calm, one-thing-at-a-time layout for the Strict mode flow. The step heading takes focus on every change
 * so screen-reader users hear where they are; leaving is always one tap away and never loses saved answers.
 */
export function StepperShell({ steps, index, title, lead, children, onBack, onNext, nextLabel = "Continue", nextDisabled = false, busy = false, error, hideNext = false, exitHref = "/fitness" }: {
  steps: string[]; index: number; title: string; lead?: string; children: ReactNode; onBack?: () => void; onNext?: () => void; nextLabel?: string;
  nextDisabled?: boolean; busy?: boolean; error?: string | null; hideNext?: boolean; exitHref?: string;
}) {
  const heading = useRef<HTMLHeadingElement>(null);
  const first = useRef(true);
  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    heading.current?.focus();
  }, [index]);

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-5">
      <div className="flex items-center justify-between gap-3">
        <p className="m-0 text-body-sm font-extrabold text-muted" aria-live="polite">
          Step {index + 1} of {steps.length}: {steps[index]}
        </p>
        <Link href={exitHref} className="inline-flex min-h-[44px] items-center rounded-full px-4 text-body-sm font-extrabold text-muted no-underline hover:text-ink">
          Leave for now
        </Link>
      </div>
      <ol className="m-0 flex list-none gap-1.5 p-0" aria-label="Steps">
        {steps.map((s, i) => (
          <li key={s} aria-current={i === index ? "step" : undefined} className="min-w-0 flex-1">
            <span className={`block h-2 rounded-full ${i < index ? "bg-bubbles-mint" : i === index ? "bg-bubbles-grape" : "bg-line"}`} />
            <span className="sr-only">
              {s}
              {i < index ? " (done)" : i === index ? " (current)" : ""}
            </span>
          </li>
        ))}
      </ol>
      <section aria-labelledby="step-title" className={`${CARD} flex flex-col gap-5 p-5 sm:p-7`}>
        <div>
          <h1 id="step-title" ref={heading} tabIndex={-1} className="m-0 font-display text-h1 text-ink outline-none">
            {title}
          </h1>
          {lead && <p className="m-0 mt-2 text-body text-muted">{lead}</p>}
        </div>
        {children}
        <div aria-live="polite">
          {error && <p role="alert" className="m-0 rounded-2xl bg-tint-pink px-4 py-3 text-body-sm font-bold text-bubbles-pink-deep">{error}</p>}
        </div>
        <div className="flex flex-wrap items-center justify-between gap-3">
          {onBack && index > 0 ? (
            <button type="button" onClick={onBack} disabled={busy} className={BTN_SECONDARY}>
              Back
            </button>
          ) : (
            <span />
          )}
          {!hideNext && onNext && (
            <button type="button" onClick={onNext} disabled={nextDisabled || busy} className={BTN_PRIMARY}>
              {busy ? "One moment…" : nextLabel}
            </button>
          )}
        </div>
      </section>
    </div>
  );
}
