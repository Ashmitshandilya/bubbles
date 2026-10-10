"use client";

import { useEffect, useRef, type CSSProperties, type KeyboardEvent } from "react";
import { CHAPTERS, onStoryFrame, story } from "./store";

type Vars = CSSProperties & Record<`--${string}`, string | number>;

/**
 * Which chapter link a key moves to, from the link at `index` of `count` (-1 when focus is not on one).
 * Arrow keys step, Home and End jump to the ends; the list does not wrap. Null means the key is not ours.
 */
export function railTarget(key: string, index: number, count: number): number | null {
  if (count <= 0) return null;
  const last = count - 1;
  switch (key) {
    case "ArrowDown":
    case "ArrowRight":
      return index < 0 ? 0 : Math.min(last, index + 1);
    case "ArrowUp":
    case "ArrowLeft":
      return index < 0 ? last : Math.max(0, index - 1);
    case "Home":
      return 0;
    case "End":
      return last;
    default:
      return null;
  }
}

/** The chapter that is on stage (it leads the hand-over past its midpoint). */
export const leadChapter = (current: number, blend: number, count: number) => (blend < 0.5 ? current : Math.min(current + 1, count - 1));

/**
 * The story's chapter list: a column of ticks on wide screens, and on any screen a list that keyboard users can
 * reach (Tab), walk with the arrow keys, Home and End, and open with Enter. The chapter on stage carries
 * `aria-current`. On narrow screens it is invisible until it has focus (landing.css), then shows every label.
 */
export function ChapterRail() {
  const nav = useRef<HTMLElement>(null);

  useEffect(() => {
    let shown = -1;
    return onStoryFrame(() => {
      const lead = leadChapter(story.current, story.blend, CHAPTERS.length);
      if (lead === shown) return;
      shown = lead;
      nav.current?.querySelectorAll("a").forEach((link, i) => {
        if (i === lead) link.setAttribute("aria-current", "location");
        else link.removeAttribute("aria-current");
      });
    });
  }, []);

  const onKeyDown = (event: KeyboardEvent<HTMLElement>) => {
    if (event.altKey || event.ctrlKey || event.metaKey) return;
    const links = Array.from(nav.current?.querySelectorAll<HTMLAnchorElement>("a") ?? []);
    const next = railTarget(event.key, links.indexOf(document.activeElement as HTMLAnchorElement), links.length);
    if (next === null) return;
    event.preventDefault();
    links[next]?.focus();
  };

  return (
    <nav ref={nav} className="cw-rail" aria-label="Story chapters" onKeyDown={onKeyDown}>
      <ol>
        {CHAPTERS.map((c, k) => (
          <li key={c.key} style={{ "--i": k } as Vars}>
            <a href={`#${c.id}`} data-key={c.key}>
              <span className="cw-rail-tick" aria-hidden="true" />
              <span className="cw-rail-label">{c.label}</span>
            </a>
          </li>
        ))}
      </ol>
    </nav>
  );
}
