import * as React from "react";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import type { Nudge } from "../../lib/nutrients";

// vitest compiles JSX with the classic runtime, so components expect `React` in scope.
(globalThis as { React?: typeof React }).React = React;
vi.mock("next/link", () => ({
  default: (props: { href: string; children: unknown; className?: string }) =>
    createElement("a", { href: props.href, className: props.className }, props.children as never),
}));

import { NutrientNudges } from "./NutrientNudges";

const iron: Nudge = {
  id: "iron", headline: "Iron might be worth a blood test", level: "low",
  reasons: ["You logged feeling tired on 3 of the last 30 days."],
  gaps: ["No recent ferritin or haemoglobin result is logged yet."],
  ask: "An iron blood test (ferritin and haemoglobin) could tell. It is worth asking a doctor about.",
};

describe("NutrientNudges", () => {
  const html = renderToStaticMarkup(createElement(NutrientNudges, { items: [iron] }));

  it("shows the server's sentences, the missing result as a gap, and a way to add the result", () => {
    expect(html).toContain("Iron might be worth a blood test");
    expect(html).toContain("You logged feeling tired on 3 of the last 30 days.");
    expect(html).toContain("Gap: No recent ferritin or haemoglobin result is logged yet.");
    expect(html).toContain("worth asking a doctor about");
    expect(html).toContain('href="/labs"');
    expect(html).toContain("data-private");
  });

  it("never says fine, healthy or diagnosed, and has no em-dash", () => {
    expect(html).not.toMatch(/\b(fine|healthy|diagnos\w*|deficien\w*|you have)\b/i);
    expect(html).not.toMatch(/[–—]/);
  });
});
