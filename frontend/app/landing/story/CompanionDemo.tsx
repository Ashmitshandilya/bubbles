"use client";

import { useEffect, useRef, useState, type CSSProperties } from "react";
import { CHAPTER_INDEX, focusOn, isLead, onStoryFrame, range, rectOf, story } from "./store";

/**
 * Bubbles' intelligence layer, shown as it really works: deterministic safety
 * rules run first, then memory, logs and trusted sources flow into Bubbles (the
 * streams end at Bubbles' horn), and only then does an answer form. Visitors can
 * switch between three example questions.
 */

type Vars = CSSProperties & Record<`--${string}`, string | number>;

const STEP_NAMES = ["Safety check", "Your memory", "Your logs", "Trusted sources"];

const QUESTIONS = [
  {
    q: "Why have I been so tired this week?",
    steps: ["No urgent signs in this message", "Cycle history, 6 cycles", "Sleep, last 7 nights", "Sleep and the menstrual cycle"],
    a: "You've slept under 6 hours on 4 of the last 7 nights, and you're a few days from your period, when your sleep has been lighter in past cycles. Both may be playing a part. Want to keep an eye on caffeine this week? If the tiredness is new, severe or doesn't lift, it's worth talking to a doctor.",
  },
  {
    q: "Is my period late?",
    steps: ["No urgent signs in this message", "Cycle history, 8 cycles", "Your notes this month", "Cycle length and what shifts it"],
    a: "Your cycles have run 27 to 31 days, so day 33 is later than usual for you. Stress, travel and illness can all shift a cycle. If there's a chance you could be pregnant, a test is the quickest way to know, and a doctor can help if this keeps happening.",
  },
  {
    q: "What should I tell my doctor?",
    steps: ["No urgent signs in this message", "Symptoms, last 6 months", "Medications and notes", "Preparing for an appointment"],
    a: "Here's a summary for your visit: headaches two days before your period in 4 of your last 6 cycles, mostly in the afternoon. Sleep under 6 hours on most of those days. Ibuprofen helped twice. Want me to add your own questions to the list?",
  },
];

export function CompanionDemo() {
  const [active, setActive] = useState(0);
  const activeRef = useRef(0);
  const replayAt = useRef(0);
  const answer = useRef<HTMLSpanElement>(null);
  const bubble = useRef<HTMLParagraphElement>(null);
  const answerBox = useRef<HTMLDivElement>(null);
  const steps = useRef<Array<HTMLLIElement | null>>([]);
  const lines = useRef<Array<SVGPathElement | null>>([]);
  const svg = useRef<SVGSVGElement>(null);

  useEffect(() => {
    activeRef.current = active;
  }, [active]);

  useEffect(() => {
    const index = CHAPTER_INDEX.companion;
    let shown = -1;
    let shownFor = -1;
    const drawn = ["", "", "", ""];
    return onStoryFrame(() => {
      const state = story.chapters[index];
      const visible = state.enter > 0 && state.exit < 1;
      if (!visible) return;
      const p = state.p;
      const q = QUESTIONS[activeRef.current];

      // Layout reads first, writes after: alternating them forces a layout per stream per frame.
      const box = svg.current ? rectOf(svg.current) : undefined;
      const ready = Boolean(box) && story.worldReady && story.bubbles.visible;
      const rects = ready ? steps.current.map((step) => (step ? rectOf(step) : undefined)) : [];
      const lead = isLead(index);
      const focus = lead
        ? focusOn(p < 0.18 ? bubble.current : p < 0.6 ? steps.current[Math.min(3, Math.floor(range(p, 0.18, 0.58) * 4))] : answerBox.current)
        : null;

      // The answer composes with the scroll, or replays after switching questions.
      let count = Math.round(range(p, 0.6, 0.86) * q.a.length);
      if (replayAt.current) {
        const typed = Math.floor((performance.now() - replayAt.current) / 14);
        if (typed >= q.a.length) replayAt.current = 0;
        else count = Math.min(count, typed);
      }
      if ((count !== shown || shownFor !== activeRef.current) && answer.current) {
        shown = count;
        shownFor = activeRef.current;
        answer.current.textContent = q.a.slice(0, count);
      }

      // Streams from each source into Bubbles' horn (only touched when the route changes).
      if (box) {
        lines.current.forEach((path, k) => {
          const r = rects[k];
          let d = "";
          if (r) {
            const sx = r.right - box.left + 6;
            const sy = r.top + r.height / 2 - box.top;
            const ex = story.bubbles.horn.x - box.left;
            const ey = story.bubbles.horn.y - box.top;
            const dx = Math.max(80, (ex - sx) * 0.5);
            d = `M${sx.toFixed(1)} ${sy.toFixed(1)} C${(sx + dx).toFixed(1)} ${sy.toFixed(1)} ${(ex - dx).toFixed(1)} ${ey.toFixed(1)} ${ex.toFixed(1)} ${ey.toFixed(1)}`;
          }
          if (path && d !== drawn[k]) {
            path.setAttribute("d", d);
            drawn[k] = d;
          }
        });
      }

      if (lead) story.focus = focus;
    });
  }, []);

  const q = QUESTIONS[active];

  return (
    <div className="cw-companion">
      <div className="cw-asks" role="group" aria-label="Example questions">
        {QUESTIONS.map((item, k) => (
          <button
            key={item.q}
            type="button"
            className="cw-ask"
            aria-pressed={k === active}
            onClick={() => {
              if (k === active) return;
              setActive(k);
              replayAt.current = performance.now();
            }}
          >
            {item.q}
          </button>
        ))}
      </div>

      <p ref={bubble} className="cw-question">
        <span className="cw-mono">Example conversation</span>
        {q.q}
      </p>

      <ol className="cw-steps" aria-label="What Bubbles checks before answering">
        {STEP_NAMES.map((name, k) => (
          <li
            key={name}
            ref={(el) => {
              steps.current[k] = el;
            }}
            className="cw-step"
            style={{ "--k": k } as Vars}
            data-safety={k === 0 ? "" : undefined}
          >
            <strong>{name}</strong>
            <span>{q.steps[k]}</span>
          </li>
        ))}
      </ol>

      <div ref={answerBox} className="cw-answer" aria-live="off">
        <span className="cw-sr">{q.a}</span>
        <span className="cw-answer-text" aria-hidden="true">
          <span className="cw-answer-full">{q.a}</span>
          <span ref={answer} className="cw-answer-live" />
          <span className="cw-caret" />
        </span>
        <span className="cw-answer-meta cw-mono">Based on {q.steps.slice(1).join(", ")}</span>
      </div>

      <svg ref={svg} className="cw-streams" aria-hidden="true">
        {STEP_NAMES.map((name, k) => (
          <path
            key={name}
            ref={(el) => {
              lines.current[k] = el;
            }}
            className="cw-stream"
            style={{ "--k": k } as Vars}
          />
        ))}
      </svg>

      <p className="cw-fineprint">Bubbles does not diagnose. If something sounds urgent, it skips the chat and tells you to get help.</p>
    </div>
  );
}
