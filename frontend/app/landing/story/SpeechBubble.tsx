"use client";

import { useEffect, useRef, useState } from "react";
import { onStoryFrame, story, type ChapterKey } from "./store";

/**
 * Bubbles' speech bubble. It follows Bubbles' head on screen, greets the visitor
 * (by time of day), answers boops with a line that fits the current chapter, and
 * speaks for other moments through the "bubbles:say" event (see `say()` in store).
 */
const LINES: Record<ChapterKey, string[]> = {
  enter: ["Hi! I'm Bubbles.", "Hehe. That tickles."],
  body: ["Everything in there is talking."],
  noise: ["Numbers are moments. I keep the story."],
  track: ["Tell me like you'd tell a friend."],
  cycle: ["I'll keep count. You live your life."],
  connect: ["Tap a signal. I'll show you its friends."],
  remember: ["I only keep what you confirm."],
  companion: ["Safety check first. Always."],
  care: ["I never diagnose. Hoof promise."],
  bubbles: ["One message is all it takes."],
};
const TICKLISH = "Okay, okay. You found my ticklish spot.";

const greeting = (h: number) =>
  h >= 5 && h < 12
    ? "Good morning! I'm Bubbles. Tap me any time."
    : h >= 12 && h < 18
      ? "Hi! I'm Bubbles. Tap me any time."
      : h >= 18 && h < 23
        ? "Good evening! I'm Bubbles. Tap me any time."
        : "Up late? Hi, I'm Bubbles. Tap me any time.";

/**
 * Which side of Bubbles the bubble opens to, and how wide it may be. It sits 40px beside
 * Bubbles and keeps 12px from the screen edge; on a phone it takes the roomier side
 * and wraps instead of running off the screen.
 */
export function bubbleFit(x: number, vw: number, mobile: boolean) {
  const left = mobile ? x > vw / 2 : x > vw * 0.7;
  const room = left ? x - 52 : vw - x - 52;
  return { left, room: Math.max(96, Math.floor(room)) };
}

export function SpeechBubble() {
  const ref = useRef<HTMLDivElement>(null);
  const [line, setLine] = useState<string | null>(null);
  const hideAt = useRef(0);

  useEffect(() => {
    let greeted = false;
    let greetTimer = 0;
    const turns: Partial<Record<ChapterKey, number>> = {};
    const show = (text: string, ms: number) => {
      setLine(text);
      hideAt.current = performance.now() + ms;
    };
    const onBoop = (event: Event) => {
      const n = (event as CustomEvent<number>).detail ?? 1;
      if (n % 5 === 0) {
        show(TICKLISH, 2600);
        return;
      }
      const key = (document.querySelector<HTMLElement>(".cw")?.dataset.active ?? "enter") as ChapterKey;
      const lines = LINES[key] ?? LINES.enter;
      const k = turns[key] ?? 0;
      turns[key] = k + 1;
      show(lines[k % lines.length], 2600);
    };
    const onSay = (event: Event) => {
      const detail = (event as CustomEvent<{ text: string; ms?: number }>).detail;
      if (detail?.text) show(detail.text, detail.ms ?? 2600);
    };
    window.addEventListener("bubbles:boop", onBoop);
    window.addEventListener("bubbles:say", onSay);

    let lastRoom = -1;
    const stop = onStoryFrame(() => {
      const el = ref.current;
      if (!el) return;
      if (!greeted && story.bubbles.visible) {
        greeted = true;
        greetTimer = window.setTimeout(() => show(greeting(new Date().getHours()), 3800), 900);
      }
      if (hideAt.current && performance.now() > hideAt.current) {
        hideAt.current = 0;
        setLine(null);
      }
      const x = Math.min(story.vw - 24, Math.max(24, story.bubbles.x));
      // On a phone keep the bubble (which opens upward, up to ~3 lines) clear of the nav bar.
      const y = Math.max(story.mobile ? 200 : 80, story.bubbles.y);
      el.style.transform = `translate3d(${x.toFixed(1)}px, ${y.toFixed(1)}px, 0)`;
      const fit = bubbleFit(x, story.vw, story.mobile);
      const flip = fit.left ? "left" : "right";
      if (el.dataset.flip !== flip) el.dataset.flip = flip;
      if (fit.room !== lastRoom) {
        el.style.setProperty("--room", `${fit.room}px`);
        lastRoom = fit.room;
      }
    });
    return () => {
      stop();
      window.clearTimeout(greetTimer);
      window.removeEventListener("bubbles:boop", onBoop);
      window.removeEventListener("bubbles:say", onSay);
    };
  }, []);

  return (
    <div ref={ref} className="cw-bubble" data-show={line ? "" : undefined} aria-live="polite">
      <span>{line ?? ""}</span>
    </div>
  );
}
