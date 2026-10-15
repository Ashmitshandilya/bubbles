import * as React from "react";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { readOrganMap } from "../../app/lib/organ-map";

// vitest compiles JSX with the classic runtime (tsconfig has jsx: "preserve"), so components expect `React` in scope.
(globalThis as { React?: typeof React }).React = React;

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: () => {} }) }));
vi.mock("../BubblesMascot", () => ({ BubblesMascot: () => createElement("i", { "data-testid": "mascot" }) }));

import { BodyFallback2D } from "./BodyFallback2D";
import { OrganList } from "./OrganList";
import { OrganPanel } from "./OrganPanel";

const ORGANS = readOrganMap({
  organs: [
    {
      organ_id: "heart",
      name: "Heart",
      status: "talk_to_doctor",
      safety: { message: "On 12 Oct you logged chest pain. If it is happening now, call 112." },
      summary: "You logged chest pain on 12 Oct.",
      evidence: [{ date: "2026-10-12", label: "Chest pain", value: "7/10", source: "chat" }],
      confidence: { level: "high", reason: "A recent entry needs attention." },
      chat_prompt: { text: "Explain my heart" },
    },
    {
      organ_id: "kidneys_bladder",
      name: "Kidneys and bladder",
      status: "worth_watching",
      summary: "Burning when you pee came up twice.",
      evidence: [{ date: "2026-10-09", label: "Burning urination", source: "tracker" }],
      confidence: { level: "medium", reason: "Two entries." },
      missing: ["How much water you drink"],
      next_step: "Note when it happens and drink water steadily.",
    },
    { organ_id: "thyroid", name: "Thyroid", status: "no_data", missing: ["A TSH result"] },
    { organ_id: "skin", name: "Skin", status: "no_data" },
  ],
});
const [heart, kidneys, thyroid] = ORGANS;
const noop = () => {};

describe("BodyFallback2D", () => {
  const html = (selected: string | null) =>
    renderToStaticMarkup(createElement(BodyFallback2D, { organs: ORGANS, selected, hovered: null, onSelect: noop, onHover: noop }));

  it("draws every part of a grouped organ and ties it to the organ id", () => {
    const out = html("kidneys_bladder");
    expect(out).toContain('data-part="kidneys"');
    expect(out).toContain('data-part="bladder"');
    expect(out.match(/data-organ="kidneys_bladder"/g)).toHaveLength(2);
    expect(out.match(/data-selected="true"/g)).toHaveLength(2); // both parts light up together
    expect(out).toContain('data-part="thyroid"'); // optional part, present in the map
    expect(out).not.toContain('data-part="uterus"'); // optional part, absent from the map
    expect(out).not.toContain('data-organ="liver'); // drawn for the body's sake, but not interactive
  });

  it("is hidden from assistive tech (the organ list is the accessible control)", () => {
    expect(html(null)).toMatch(/<svg[^>]*aria-hidden="true"/);
  });

  it("marks missing data with a dashed outline, never a status colour", () => {
    const out = html(null);
    const start = out.indexOf('data-organ="thyroid"');
    const thyroidGroup = out.slice(start, out.indexOf(">", start));
    expect(thyroidGroup).toContain("stroke-dasharray:3 2");
    expect(thyroidGroup).not.toContain("--bubbles-mint");
  });
});

describe("OrganPanel", () => {
  const html = (organ: (typeof ORGANS)[number] | null) => renderToStaticMarkup(createElement(OrganPanel, { organ }));

  it("puts the safety message first and drops the mascot when a doctor is needed", () => {
    const out = html(heart);
    expect(out).toContain("If it is happening now, call 112.");
    expect(out.indexOf("organ-safety")).toBeLessThan(out.indexOf(">Heart<"));
    expect(out).not.toContain('data-testid="mascot"');
    expect(out).toContain("This is not a diagnosis.");
    expect(out).toContain("Ask Bubbles about this");
  });

  it("shows evidence, confidence, what is missing and one next step", () => {
    const out = html(kidneys);
    expect(out).not.toContain("organ-safety");
    expect(out).toContain('data-testid="mascot"');
    expect(out).toContain("Burning when you pee came up twice.");
    expect(out).toContain("Burning urination");
    expect(out).toContain("9 Oct · Tracker");
    expect(out).toContain("Medium confidence");
    expect(out).toContain("Two entries.");
    expect(out).toContain("How much water you drink");
    expect(out).toContain("Note when it happens and drink water steadily.");
    expect(out).toContain("This is not a diagnosis.");
  });

  it("treats no data as a gap", () => {
    const out = html(thyroid);
    expect(out).toContain("No data yet");
    expect(out).toContain("Not enough to judge");
    expect(out).toContain("Nothing logged yet relates to this part of the body.");
    expect(out).toContain("A TSH result");
    expect(out).toContain("This is not a diagnosis.");
  });

  it("invites a choice when nothing is selected, still with the disclaimer", () => {
    const out = html(null);
    expect(out).toContain("Choose a part of the body");
    expect(out).toContain("This is not a diagnosis.");
  });
});

describe("OrganList", () => {
  it("lists every organ as a button with its status in text, and the legend", () => {
    const out = renderToStaticMarkup(
      createElement(OrganList, { organs: ORGANS, selected: "heart", hovered: null, onSelect: noop, onHover: noop }),
    );
    expect(out.match(/<button/g)).toHaveLength(ORGANS.length);
    expect(out).toMatch(/aria-pressed="true"[^>]*>.*?Heart.*?Talk to a doctor/);
    expect(out).toContain("Kidneys and bladder");
    expect(out).toContain("2 of 4 with recent entries");
    for (const label of ["Talk to a doctor", "Worth watching", "Steady", "No data yet"]) expect(out).toContain(label);
  });
});
