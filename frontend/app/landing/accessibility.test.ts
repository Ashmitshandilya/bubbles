import * as React from "react";
import { createElement } from "react";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { renderToStaticMarkup } from "react-dom/server";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { CHAPTERS } from "./story/store";

// vitest compiles JSX with the classic runtime (tsconfig has jsx: "preserve"), so components expect `React` in scope.
(globalThis as { React?: typeof React }).React = React;

// The page imports Next-only modules (links, lazy client chunks) and the Supabase client. None of them
// changes the markup this test is about, so they are replaced by plain stand-ins.
vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children?: React.ReactNode } & Record<string, unknown>) =>
    createElement("a", { href, ...rest }, children),
}));
vi.mock("./atmosphere/SkyMount", () => ({ SkyMount: () => null }));
vi.mock("./world/WorldMount", () => ({ WorldMount: () => null }));
vi.mock("../../lib/supabase", () => ({ isSupabaseConfigured: false, supabase: {} }));
vi.mock("./landing.css", () => ({}));

let html = "";
let text = "";
beforeAll(async () => {
  const { Landing } = await import("./Landing");
  html = renderToStaticMarkup(createElement(Landing));
  text = html
    .replace(/<noscript>[\s\S]*?<\/noscript>/g, " ")
    .replace(/<style[\s\S]*?<\/style>/g, " ")
    .replace(/<[^>]+>/g, " ")
    .replace(/&nbsp;|&#x27;|&quot;|&amp;/g, " ")
    .replace(/\s+/g, " ");
});

describe("the calm page (what reduced motion and a screen reader get)", () => {
  it("has the landmarks: banner, chapter navigation, main, footer, and a skip link that comes first", () => {
    expect(html).toMatch(/<header[^>]*class="cw-nav"/);
    expect(html).toMatch(/<nav[^>]*aria-label="Story chapters"/);
    expect(html).toMatch(/<main[^>]*id="main"/);
    expect(html).toMatch(/<footer/);
    const firstLink = html.match(/<a [^>]*>/)?.[0] ?? "";
    expect(firstLink).toContain('href="#main"');
    expect(firstLink).toContain("cw-skip");
  });

  it("lets the skip link move focus: <main> is focusable by script, not by Tab", () => {
    expect(html).toMatch(/<main[^>]*id="main"[^>]*tabindex="-1"/);
  });

  it("has exactly one h1, then one h2 per remaining chapter, in story order", () => {
    expect(html.match(/<h1[ >]/g)).toHaveLength(1);
    const h2 = [...html.matchAll(/<h2[^>]*id="cw-h-([a-z]+)"/g)].map((m) => m[1]);
    expect(h2).toEqual(CHAPTERS.slice(1).map((c) => c.key));
  });

  it("names every chapter region by its heading, and the headings exist", () => {
    for (const c of CHAPTERS) {
      expect(html, c.key).toContain(`aria-labelledby="cw-h-${c.key}"`);
      expect(html, c.key).toContain(`id="cw-h-${c.key}"`);
      expect(html, c.key).toContain(`data-chapter="${c.key}"`);
    }
  });

  it("offers one call to action, Get started, in the hero and the close; the nav offers Sign in", () => {
    expect(html.match(/href="\/login\?mode=signup"/g)).toHaveLength(2);
    expect(text.match(/Get started/g)).toHaveLength(2);
    const nav = html.match(/<header[^>]*class="cw-nav"[\s\S]*?<\/header>/)?.[0] ?? "";
    expect(nav).toContain('href="/login"');
    expect(nav).toContain("Sign in");
    expect(nav).not.toContain("mode=signup");
  });

  it("keeps the whole story as text: every chapter's copy is there", () => {
    for (const phrase of [
      "Your body keeps a story.",
      "Bubbles remembers",
      "Just talk. Bubbles listens.",
      "2 rotis, dal and curd",
      "slept 7h 12m",
      "cramps since morning",
      "water 5 of 8",
      "Nothing becomes memory until you confirm",
      "Confirm",
      "Edit",
      "Patterns across weeks, not",
      "Walk into your appointment prepared.",
      "Bubbles does not diagnose.",
      "Start your story with Bubbles.",
    ]) {
      expect(text, phrase).toContain(phrase);
    }
  });

  it("repeats the safety note in the footer, with the Privacy and Terms links", () => {
    expect(text).toContain("not a medical device, and does not diagnose");
    expect(text).toContain("In an emergency, contact your local emergency number");
    const footer = html.match(/<footer[\s\S]*?<\/footer>/)?.[0] ?? "";
    expect(footer).toContain('href="/privacy"');
    expect(footer).toContain('href="/terms"');
  });

  it("labels example data as an example", () => {
    expect(text).toContain("Example message");
    expect(text).toContain("Example conversation");
    expect(text).toContain("Example pattern");
    expect(text).toMatch(/Example\s+Cycle summary for my clinician/);
    expect(text).toContain("An estimate, never birth control".replace("An estimate", "an estimate"));
  });

  it("makes only promises the privacy page keeps", () => {
    const promises = html.match(/<ol class="cw-promises">[\s\S]*?<\/ol>/)?.[0] ?? "";
    expect(promises.match(/<li/g)).toHaveLength(3);
    expect(promises).toContain("Nothing becomes memory until you confirm it.");
    expect(promises).toContain("You choose what a partner sees.");
    expect(promises).toContain("no analytics");
    const privacy = readFileSync(join(__dirname, "..", "privacy", "page.tsx"), "utf8");
    expect(privacy).toMatch(/no\s+analytics/);
    expect(privacy).toContain("Partner sharing is off by default");
    expect(privacy).toMatch(/designed not to contain your message text/);
  });

  it("gives Bubbles a text alternative, and hides the decoration", () => {
    expect(html).toMatch(/<img[^>]*alt="Bubbles, a baby unicorn doctor/);
    for (const hidden of ["cw-bg", "cw-grain"]) {
      expect(html, hidden).toContain(`class="${hidden}" aria-hidden="true"`);
    }
    expect(html).toMatch(/class="cw-orb cw-close-orb" data-orb="true" aria-hidden="true"/);
  });

  it("describes the example ring that is drawn as an image, and does not use colour alone for the phases", () => {
    expect(html).toMatch(/<svg[^>]*role="img"[^>]*aria-labelledby="cw-ring-cap"/);
    expect(html).toContain('id="cw-ring-cap"');
    for (const name of ["Period", "Follicular", "Ovulation (estimate)", "Luteal"]) expect(html).toContain(`>${name}</text>`);
  });
});

describe("Pause motion", () => {
  it("is a real button with a fixed name and its state in aria-pressed", () => {
    const button = html.match(/<button[^>]*class="cw-motion"[^>]*>[\s\S]*?<\/button>/)?.[0] ?? "";
    expect(button).toContain('type="button"');
    expect(button).toContain('aria-pressed="false"');
    expect(button).toContain("Pause motion");
  });
});

describe("copy rules", () => {
  it("has no em dashes or en dashes in visible text", () => {
    expect(text).not.toMatch(/[–—]/);
  });

  it("invents no testimonials, user counts or ratings", () => {
    expect(text).not.toMatch(/testimonial|\d\s*(\+\s*)?(users|people|customers|members)\b|★|\b5\/5\b/i);
  });
});

describe("landing.css", () => {
  const css = readFileSync(join(__dirname, "landing.css"), "utf8").replace(/\/\*[\s\S]*?\*\//g, "");

  /** Every declaration with the at-rules and selectors it sits inside, outermost first. */
  function declarations() {
    const out: Array<{ prop: string; value: string; context: string[] }> = [];
    const stack: string[] = [];
    let buffer = "";
    const flush = () => {
      const decl = buffer.trim();
      buffer = "";
      const at = decl.indexOf(":");
      if (at > 0) out.push({ prop: decl.slice(0, at).trim(), value: decl.slice(at + 1).trim(), context: [...stack] });
    };
    for (const ch of css) {
      if (ch === "{") {
        stack.push(buffer.trim());
        buffer = "";
      } else if (ch === "}") {
        flush();
        stack.pop();
      } else if (ch === ";") {
        flush();
      } else {
        buffer += ch;
      }
    }
    return out;
  }

  it("runs no animation unless motion is allowed: every animation sits inside prefers-reduced-motion: no-preference", () => {
    const animated = declarations().filter((d) => /^animation(-name)?$/.test(d.prop) && d.value !== "none" && !d.context.some((c) => c.startsWith("@keyframes")));
    expect(animated.length).toBeGreaterThan(15);
    for (const d of animated) {
      expect(d.context.some((c) => /prefers-reduced-motion:\s*no-preference/.test(c)), `${d.context.at(-1)} { animation: ${d.value} }`).toBe(true);
    }
  });

  it("settles every loop and entrance when motion is paused", () => {
    const paused = declarations().filter((d) => d.context.some((c) => c.startsWith(".cw[data-paused]")));
    const props = Object.fromEntries(paused.map((d) => [d.prop, d.value]));
    expect(props["animation-duration"]).toMatch(/^0\.001ms/);
    expect(props["animation-iteration-count"]).toMatch(/^1/);
    expect(props["animation-delay"]).toMatch(/^0s/);
  });

  it("handles reduced transparency, more contrast and forced colours", () => {
    expect(css).toContain("@media (prefers-reduced-transparency: reduce)");
    expect(css).toContain("@media (prefers-contrast: more)");
    expect(css).toContain("@media (forced-colors: active)");
  });

  it("keeps a visible focus ring on every control", () => {
    expect(css).toMatch(/\.cw :is\(a, button, \[tabindex\]\):focus-visible \{[^}]*outline: 2px solid/);
  });

  it("hides the pause button until the story is running, and gives it a 44px target", () => {
    expect(css).toMatch(/\.cw-motion \{ display: none; \}/);
    expect(css).toMatch(/\.cw\[data-story="on"\] \.cw-motion \{[^}]*min-height: 44px/);
  });
});
