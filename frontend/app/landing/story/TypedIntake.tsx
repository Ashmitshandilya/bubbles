"use client";

import { useEffect, useRef, type CSSProperties } from "react";
import { CHAPTER_INDEX, focusOn, isLead, onStoryFrame, range, story } from "./store";

/**
 * "Say it like you'd tell a friend": an example message types itself as you
 * scroll, its key phrases light up, lift off and become structured records that
 * wait for the visitor's confirmation (the real product's flow).
 */
const SEGMENTS: Array<{ text: string; mark?: number }> = [
  { text: "cramps since this morning", mark: 0 },
  { text: ", " },
  { text: "slept badly", mark: 1 },
  { text: ", " },
  { text: "only one glass of water", mark: 2 },
  { text: " so far" },
];
const FULL = SEGMENTS.map((s) => s.text).join("");

const RECORDS = [
  { kind: "Symptom", value: "Cramps", detail: "Since this morning" },
  { kind: "Sleep", value: "Poor night", detail: "Last night" },
  { kind: "Water", value: "1 glass", detail: "So far today" },
];

type Vars = CSSProperties & Record<`--${string}`, string | number>;

export function TypedIntake() {
  const spans = useRef<Array<HTMLSpanElement | null>>([]);
  const field = useRef<HTMLDivElement>(null);
  const list = useRef<HTMLOListElement>(null);

  useEffect(() => {
    let shown = -1;
    // In calm mode (no story engine) the full sentence simply stays as rendered.
    return onStoryFrame(() => {
      const p = story.chapters[CHAPTER_INDEX.track].p;
      // Bubbles watches the message being typed, then the records it becomes.
      // (From p 0.9 the travel route takes over Bubbles' gaze, toward the cycle ring.)
      if (isLead(CHAPTER_INDEX.track) && p < 0.9) story.focus = focusOn(p < 0.45 ? field.current : list.current);
      const count = Math.round(range(p, 0.05, 0.38) * FULL.length);
      if (count === shown) return;
      shown = count;
      let left = count;
      SEGMENTS.forEach((segment, i) => {
        const el = spans.current[i];
        if (!el) return;
        const take = Math.max(0, Math.min(segment.text.length, left));
        left -= take;
        const text = segment.text.slice(0, take);
        if (el.textContent !== text) el.textContent = text;
      });
    });
  }, []);

  return (
    <div className="cw-intake">
      <p className="cw-sr">Example message: “{FULL}”. Bubbles turns it into three records you confirm.</p>
      <div ref={field} className="cw-field" aria-hidden="true">
        <span className="cw-field-text">
          {SEGMENTS.map((segment, i) => (
            <span
              key={i}
              ref={(el) => {
                spans.current[i] = el;
              }}
              className={segment.mark !== undefined ? "cw-mark" : undefined}
              style={segment.mark !== undefined ? ({ "--k": segment.mark } as Vars) : undefined}
            >
              {segment.text}
            </span>
          ))}
          <span className="cw-caret" />
        </span>
        <span className="cw-send" />
      </div>
      <ol ref={list} className="cw-records" aria-hidden="true">
        {RECORDS.map((record, k) => (
          <li key={record.kind} style={{ "--k": k } as Vars}>
            <span className="cw-mono">{record.kind}</span>
            <strong>{record.value}</strong>
            <span className="cw-record-detail">{record.detail}</span>
            <span className="cw-confirm">
              <span className="cw-confirm-ask">Confirm?</span>
              <span className="cw-confirm-done">Saved</span>
            </span>
          </li>
        ))}
      </ol>
      <p className="cw-note">Nothing becomes part of your record until you confirm it.</p>
    </div>
  );
}
