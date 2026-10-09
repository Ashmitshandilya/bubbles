"use client";

import { useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { CHAPTER_INDEX, focusOn, isLead, onStoryFrame, story } from "./store";

/**
 * Everyday health as one connected system. Twelve signals sit around Bubbles; as
 * you scroll, example links light up one by one (Bubbles points at each). Hover,
 * focus or tap any signal to see everything it connects to.
 */

type Vars = CSSProperties & Record<`--${string}`, string | number>;

const NODES = [
  "Cycle", "Sleep", "Mood", "Energy", "Activity", "Food", "Water", "Symptoms", "Medications", "Visits", "Weight", "Vitals",
].map((name, k) => {
  const a = (k / 12) * Math.PI * 2;
  return { id: name.toLowerCase(), name, x: 50 + 41 * Math.sin(a), y: 50 - 40 * Math.cos(a) };
});

const STORY_LINKS: Array<{ a: string; b: string; label: string }> = [
  { a: "sleep", b: "mood", label: "Short nights, lower mood the next day" },
  { a: "water", b: "symptoms", label: "Less water, more headaches" },
  { a: "cycle", b: "sleep", label: "Lighter sleep before a period" },
  { a: "activity", b: "energy", label: "Walks on busy days, steadier energy" },
  { a: "medications", b: "symptoms", label: "A new medication, a change in symptoms" },
  { a: "food", b: "energy", label: "Late dinners, slow mornings" },
];

const WEB_LINKS: Array<[string, string]> = [
  ["cycle", "mood"], ["cycle", "symptoms"], ["cycle", "energy"], ["sleep", "energy"], ["mood", "energy"],
  ["food", "weight"], ["vitals", "medications"], ["visits", "symptoms"], ["visits", "medications"], ["weight", "activity"],
  ["vitals", "weight"], ["water", "energy"], ["activity", "sleep"], ["food", "symptoms"], ["vitals", "activity"],
];

const SEQ_START = 0.08;
const SEQ_STEP = 0.14;

const byId = Object.fromEntries(NODES.map((n) => [n.id, n]));

/** A link bowed toward the centre (where Bubbles is), in pixels of a w×h box; label point in %. */
function curve(a: string, b: string, w: number, h: number) {
  const p = byId[a];
  const q = byId[b];
  const mx = (p.x + q.x) / 2;
  const my = (p.y + q.y) / 2;
  const cx = mx + (50 - mx) * 0.42;
  const cy = my + (50 - my) * 0.42;
  const X = (v: number) => ((v / 100) * w).toFixed(1);
  const Y = (v: number) => ((v / 100) * h).toFixed(1);
  return {
    d: `M${X(p.x)} ${Y(p.y)} Q${X(cx)} ${Y(cy)} ${X(q.x)} ${Y(q.y)}`,
    // point on the quadratic at t = 0.5
    lx: 0.25 * p.x + 0.5 * cx + 0.25 * q.x,
    ly: 0.25 * p.y + 0.5 * cy + 0.25 * q.y,
  };
}

export function ConnectWeb() {
  const [hovered, setHovered] = useState<string | null>(null);
  const hoveredRef = useRef<string | null>(null);
  const nodeRefs = useRef<Record<string, HTMLButtonElement | null>>({});
  const labelRefs = useRef<Array<HTMLSpanElement | null>>([]);

  const box = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 1000, h: 600 });
  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const observer = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      if (width > 0 && height > 0) setSize({ w: Math.round(width), h: Math.round(height) });
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const links = useMemo(
    () => [
      ...STORY_LINKS.map((l, k) => ({ ...l, ...curve(l.a, l.b, size.w, size.h), story: k })),
      ...WEB_LINKS.map(([a, b]) => ({ a, b, label: "", ...curve(a, b, size.w, size.h), story: -1 })),
    ],
    [size],
  );

  const neighbours = useMemo(() => {
    const map: Record<string, Set<string>> = {};
    for (const l of links) {
      (map[l.a] ??= new Set()).add(l.b);
      (map[l.b] ??= new Set()).add(l.a);
    }
    return map;
  }, [links]);

  useEffect(() => {
    hoveredRef.current = hovered;
  }, [hovered]);

  // Bubbles looks at whatever the visitor points at, or at the link being revealed.
  useEffect(() => {
    const index = CHAPTER_INDEX.connect;
    return onStoryFrame(() => {
      if (!isLead(index)) return;
      const h = hoveredRef.current;
      if (h) {
        story.focus = focusOn(nodeRefs.current[h]);
        return;
      }
      const p = story.chapters[index].p;
      const k = Math.floor((p - SEQ_START) / SEQ_STEP);
      story.focus = k >= 0 && k < STORY_LINKS.length ? focusOn(labelRefs.current[k]) : null;
    });
  }, []);

  const lit = (a: string, b: string) => hovered !== null && (a === hovered || b === hovered);

  return (
    <div ref={box} className="cw-web" data-hovering={hovered ? "" : undefined}>
      <svg className="cw-web-lines" viewBox={`0 0 ${size.w} ${size.h}`} aria-hidden="true">
        {links.map((l, i) => (
          <path
            key={i}
            d={l.d}
            pathLength={1}
            className={l.story >= 0 ? "cw-link cw-link--story" : "cw-link"}
            style={l.story >= 0 ? ({ "--a": SEQ_START + l.story * SEQ_STEP, "--b": SEQ_START + (l.story + 1) * SEQ_STEP } as Vars) : ({ "--i": i } as Vars)}
            data-lit={lit(l.a, l.b) ? "" : undefined}
          />
        ))}
      </svg>

      {links
        .filter((l) => l.story >= 0)
        .map((l) => (
          <span
            key={l.label}
            ref={(el) => {
              labelRefs.current[l.story] = el;
            }}
            className="cw-link-label"
            style={{ "--x": `${l.lx}%`, "--y": `${l.ly}%`, "--a": SEQ_START + l.story * SEQ_STEP, "--b": SEQ_START + (l.story + 1) * SEQ_STEP } as Vars}
          >
            <span className="cw-mono">Example</span>
            {l.label}
          </span>
        ))}

      <ul className="cw-nodes" aria-label="Signals Bubbles connects">
        {NODES.map((node) => {
          const near = neighbours[node.id] ? Array.from(neighbours[node.id]).map((id) => byId[id].name) : [];
          const active = hovered === node.id || (hovered !== null && neighbours[hovered]?.has(node.id));
          return (
            <li key={node.id} style={{ "--x": `${node.x}%`, "--y": `${node.y}%` } as Vars}>
              <button
                type="button"
                ref={(el) => {
                  nodeRefs.current[node.id] = el;
                }}
                className="cw-node"
                data-active={active ? "" : undefined}
                aria-describedby={`cw-near-${node.id}`}
                onPointerEnter={(e) => {
                  if (e.pointerType === "mouse") setHovered(node.id);
                }}
                onPointerLeave={(e) => {
                  if (e.pointerType === "mouse") setHovered((h) => (h === node.id ? null : h));
                }}
                onFocus={() => setHovered(node.id)}
                onBlur={() => setHovered((h) => (h === node.id ? null : h))}
                onClick={() => setHovered((h) => (h === node.id ? null : node.id))}
              >
                {node.name}
              </button>
              <span id={`cw-near-${node.id}`} className="cw-near" data-show={hovered === node.id ? "" : undefined}>
                Connects with {near.slice(0, 4).join(", ")}
                {near.length > 4 ? " and more" : ""}
              </span>
            </li>
          );
        })}
      </ul>
      <p className="cw-web-hint">Hover or tap a signal to see what it touches.</p>
    </div>
  );
}
