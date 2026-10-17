"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useApi, useAuth } from "../../components/Providers";
import { TOUR_STEPS, outcomeBody, placeCard, reduceTour, shouldStart, tourView, usableSteps, type Box, type TourAction, type TourState, type TourStep } from "./tour";

const CARD_WIDTH = 340;
const BTN = "bubbles-press inline-flex min-h-[44px] items-center justify-center rounded-full px-5 font-extrabold";

function targetOf(step: TourStep): HTMLElement | null {
  const found = document.querySelector<HTMLElement>(step.selector);
  const el = (step.closest ? found?.closest<HTMLElement>(step.closest) : null) ?? found;
  return el && el.getClientRects().length > 0 ? el : null;
}

const sleep = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms));

/**
 * The first-run tour: a few coach marks over Today. It starts once (never seen) or when Today is opened with ?tour=1 (Settings > Replay tour),
 * can be skipped at any point (button or Esc), keeps keyboard focus inside the card and does not animate for people who asked for less motion.
 */
export function FirstRunTour() {
  const { fetchBubbles } = useApi();
  const { session } = useAuth();
  const token = session?.access_token;
  const fetchRef = useRef(fetchBubbles);
  fetchRef.current = fetchBubbles;
  const [steps, setSteps] = useState<TourStep[]>([]);
  const [state, setState] = useState<TourState>({ open: false, index: 0 });
  const [box, setBox] = useState<Box | null>(null);
  const [cardHeight, setCardHeight] = useState(210);
  const started = useRef(false);
  const opener = useRef<HTMLElement | null>(null);
  const card = useRef<HTMLDivElement>(null);
  const heading = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    if (!token || started.current) return;
    started.current = true;
    let alive = true;
    (async () => {
      const replay = new URLSearchParams(window.location.search).get("tour") === "1";
      let seen: boolean | null = null;
      try {
        const response = await fetchRef.current("/onboarding/tour");
        if (response.ok) seen = (await response.json()).seen === true;
      } catch {
        /* unknown: do not start */
      }
      if (!alive || !shouldStart(seen, replay)) return;
      for (let tries = 0; tries < 20 && alive && !targetOf(TOUR_STEPS[0]); tries++) await sleep(300);   // Today may still be loading
      const found = usableSteps((s) => targetOf(s) !== null);
      if (!alive || found.length < 2) return;
      if (replay) window.history.replaceState(null, "", window.location.pathname);
      opener.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
      setSteps(found);
      setState({ open: true, index: 0 });
    })();
    return () => { alive = false; };
  }, [token]);

  const step = state.open ? steps[state.index] : undefined;

  // keep the highlight on the target, through smooth scrolling and resizing
  useEffect(() => {
    if (!step) return;
    const el = targetOf(step);
    if (!el) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    el.scrollIntoView({ block: "center", behavior: reduce ? "auto" : "smooth" });
    let frame = 0;
    const measure = () => {
      const r = el.getBoundingClientRect();
      const next = { top: Math.round(r.top) - 6, left: Math.round(r.left) - 6, width: Math.round(r.width) + 12, height: Math.round(r.height) + 12 };
      setBox((prev) => (prev && prev.top === next.top && prev.left === next.left && prev.width === next.width && prev.height === next.height ? prev : next));
      if (card.current) setCardHeight((prev) => (prev === card.current!.offsetHeight ? prev : card.current!.offsetHeight));
      frame = window.requestAnimationFrame(measure);
    };
    frame = window.requestAnimationFrame(measure);
    heading.current?.focus();
    return () => window.cancelAnimationFrame(frame);
  }, [step]);

  const finish = useCallback((skipped: boolean) => {
    void fetchRef.current("/onboarding/tour", { method: "PUT", body: outcomeBody(skipped) }).catch(() => undefined);
    if (opener.current?.isConnected) opener.current.focus();
  }, []);

  function go(action: TourAction) {
    const next = reduceTour(state, action, steps.length);
    setState(next);
    if (!next.open) finish(action.type === "close");
  }

  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Escape") {
      e.stopPropagation();
      go({ type: "close" });
      return;
    }
    if (e.key !== "Tab" || !card.current) return;
    const items = Array.from(card.current.querySelectorAll<HTMLElement>("button:not([disabled])"));
    if (!items.length) return;
    const first = items[0];
    const last = items[items.length - 1];
    if (e.shiftKey && (document.activeElement === first || document.activeElement === heading.current)) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  }

  if (!state.open || !step || !box) return null;
  const view = tourView(state.index, steps.length);
  const at = placeCard(box, { width: window.innerWidth, height: window.innerHeight }, { width: CARD_WIDTH, height: cardHeight });

  return (
    <div className="fixed inset-0 z-[200]" onKeyDown={onKeyDown}>
      <div aria-hidden="true" className="absolute inset-0" />
      <div aria-hidden="true" style={{ top: box.top, left: box.left, width: box.width, height: box.height }}
        className="pointer-events-none fixed rounded-[22px] ring-2 ring-white shadow-[0_0_0_9999px_rgba(34,24,52,0.58)] transition-[top,left,width,height] duration-300 motion-reduce:transition-none" />
      <div ref={card} role="dialog" aria-modal="true" aria-labelledby="tour-title" style={{ top: at.top, left: at.left }}
        className="fixed w-[340px] max-w-[calc(100vw-32px)] rounded-3xl border border-line bg-surface p-5 shadow-[var(--shadow-sm)]">
        <p className="m-0 text-chip font-extrabold uppercase tracking-wide text-muted">{view.position}</p>
        <h2 id="tour-title" ref={heading} tabIndex={-1} className="m-0 mt-1 font-display text-h2 text-ink outline-none">{step.title}</h2>
        <p className="m-0 mt-2 text-body text-muted">{step.body}</p>
        <div className="mt-5 flex flex-wrap items-center justify-between gap-2">
          <button type="button" onClick={() => go({ type: "close" })} className={`${BTN} px-3 text-body-sm text-ink-soft underline underline-offset-4`}>Skip tour</button>
          <div className="flex items-center gap-2">
            {!view.isFirst && <button type="button" onClick={() => go({ type: "back" })} className={`${BTN} border border-line bg-surface text-ink-soft`}>Back</button>}
            <button type="button" onClick={() => go({ type: "next" })} className={`${BTN} bubbles-glow bg-bubbles-pink-ink text-white`}>{view.isLast ? "Done" : "Next"}</button>
          </div>
        </div>
      </div>
    </div>
  );
}
