import * as React from "react";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { ChapterRail, leadChapter, railTarget } from "./ChapterRail";
import { CHAPTERS } from "./store";

// vitest compiles JSX with the classic runtime (tsconfig has jsx: "preserve"), so components expect `React` in scope.
(globalThis as { React?: typeof React }).React = React;

describe("keys in the chapter list", () => {
  const n = CHAPTERS.length;

  it("steps with the arrow keys and does not wrap", () => {
    expect(railTarget("ArrowDown", 0, n)).toBe(1);
    expect(railTarget("ArrowRight", 3, n)).toBe(4);
    expect(railTarget("ArrowUp", 4, n)).toBe(3);
    expect(railTarget("ArrowLeft", 1, n)).toBe(0);
    expect(railTarget("ArrowUp", 0, n)).toBe(0);
    expect(railTarget("ArrowDown", n - 1, n)).toBe(n - 1);
  });

  it("jumps to the ends with Home and End", () => {
    expect(railTarget("Home", 6, n)).toBe(0);
    expect(railTarget("End", 2, n)).toBe(n - 1);
  });

  it("starts from the right end when focus is not on a link", () => {
    expect(railTarget("ArrowDown", -1, n)).toBe(0);
    expect(railTarget("ArrowUp", -1, n)).toBe(n - 1);
  });

  it("leaves every other key (Tab, Enter, letters) alone, and an empty list", () => {
    for (const key of ["Tab", "Enter", " ", "a", "PageDown", "Escape"]) expect(railTarget(key, 2, n)).toBeNull();
    expect(railTarget("ArrowDown", 0, 0)).toBeNull();
  });
});

describe("the chapter on stage", () => {
  it("leads until the hand-over is half done, then the next chapter does", () => {
    expect(leadChapter(2, 0, 10)).toBe(2);
    expect(leadChapter(2, 0.49, 10)).toBe(2);
    expect(leadChapter(2, 0.5, 10)).toBe(3);
    expect(leadChapter(9, 0.9, 10)).toBe(9);
  });
});

describe("the chapter list markup", () => {
  const html = renderToStaticMarkup(createElement(ChapterRail));

  it("is a labelled navigation landmark with one link per chapter, in order", () => {
    expect(html).toMatch(/<nav[^>]*aria-label="Story chapters"/);
    const hrefs = [...html.matchAll(/href="#([^"]+)"/g)].map((m) => m[1]);
    expect(hrefs).toEqual(CHAPTERS.map((c) => c.id));
    const labels = [...html.matchAll(/cw-rail-label">([^<]+)</g)].map((m) => m[1]);
    expect(labels).toEqual(CHAPTERS.map((c) => c.label));
  });

  it("hides the decorative ticks from assistive technology", () => {
    expect(html.match(/cw-rail-tick" aria-hidden="true"/g)).toHaveLength(CHAPTERS.length);
  });
});
