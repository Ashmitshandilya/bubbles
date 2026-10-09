import * as React from "react";
import { Fragment, createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { BubblesMark } from "./BubblesMark";

// vitest compiles JSX with the classic runtime (tsconfig has jsx: "preserve"), so components expect `React` in scope.
(globalThis as { React?: typeof React }).React = React;

const ids = (html: string) => [...html.matchAll(/\bid="([^"]+)"/g)].map((m) => m[1]);

describe("BubblesMark", () => {
  it("gives every instance its own SVG ids, even at the same size (a hidden copy must not capture a visible one's gradients)", () => {
    const html = renderToStaticMarkup(createElement(Fragment, null, createElement(BubblesMark, { size: 40 }), createElement(BubblesMark, { size: 40 })));
    const all = ids(html);
    expect(all.length).toBeGreaterThan(20);
    expect(new Set(all).size).toBe(all.length);
  });

  it("only references ids that its own svg defines", () => {
    const html = renderToStaticMarkup(createElement(BubblesMark, { size: 36 }));
    const defined = new Set(ids(html));
    const refs = [...html.matchAll(/url\(#([^)]+)\)/g)].map((m) => m[1]);
    expect(refs.length).toBeGreaterThan(10);
    for (const ref of refs) expect(defined.has(ref)).toBe(true);
    for (const id of defined) expect(id).toMatch(/^[a-zA-Z][a-zA-Z0-9_-]*$/);
  });

  it("stays decorative unless it has a title", () => {
    expect(renderToStaticMarkup(createElement(BubblesMark, { size: 32 }))).toContain('aria-hidden="true"');
    expect(renderToStaticMarkup(createElement(BubblesMark, { size: 32, title: "Bubbles" }))).toContain('role="img"');
  });
});
