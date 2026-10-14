import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

// Every text/fill pair the Pearl Lab app theme relies on, read from the real tokens.css so a palette edit that breaks
// contrast fails here. AA: 4.5:1 for text, 3:1 for large text and UI marks.
const css = readFileSync(join(__dirname, "..", "tokens.css"), "utf8");
const token = (name: string): string => {
  const hit = css.match(new RegExp(`--${name}:\\s*(#[0-9A-Fa-f]{6})`));
  if (!hit) throw new Error(`token --${name} is not a hex colour in tokens.css`);
  return hit[1];
};

const channel = (v: number) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4);
const luminance = (hex: string) => {
  const [r, g, b] = [1, 3, 5].map((i) => channel(parseInt(hex.slice(i, i + 2), 16) / 255));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
};
export const ratio = (a: string, b: string) => {
  const [x, y] = [luminance(a), luminance(b)].sort((m, n) => n - m);
  return (x + 0.05) / (y + 0.05);
};

const TEXT_PAIRS: Array<[text: string, fill: string]> = [
  // body text on the page, cards and washes
  ...["bubbles-ink", "bubbles-ink-soft", "bubbles-ink-faint"].flatMap((t) =>
    ["bubbles-blush", "bubbles-white", "tint-pink", "tint-grape", "tint-sun", "tint-mint", "tint-sky", "tint-peach"].map((f) => [t, f] as [string, string]),
  ),
  // plum on the decorative fills (your chat messages are plum on lilac)
  ["bubbles-ink", "bubbles-lilac"], ["bubbles-ink", "bubbles-sun"], ["bubbles-ink", "bubbles-mint"], ["bubbles-ink", "bubbles-peach"], ["bubbles-ink", "bubbles-sky"],
  // white on the primary, the deep inks and the two signals
  ...["bubbles-pink-ink", "bubbles-pink-deep", "bubbles-grape", "bubbles-grape-deep", "bubbles-sun-deep", "bubbles-mint-deep", "bubbles-sky-deep", "bubbles-peach-deep", "bubbles-urgent", "bubbles-caution"].map(
    (f) => ["bubbles-white", f] as [string, string],
  ),
  // each family's ink on its own wash, on cards and on the page
  ...(["pink", "grape", "sun", "mint", "sky", "peach"] as const).flatMap((family) => {
    const ink = family === "pink" ? "bubbles-pink-deep" : `bubbles-${family}-deep`;
    return [[ink, `tint-${family}`], [ink, "bubbles-white"], [ink, "bubbles-blush"]] as Array<[string, string]>;
  }),
  ["bubbles-pink-ink", "bubbles-white"], ["bubbles-pink-ink", "bubbles-blush"], ["bubbles-pink-ink", "tint-grape"],
  ["bubbles-urgent", "tint-urgent"], ["bubbles-urgent", "bubbles-white"],
];

describe("Pearl Lab colour tokens", () => {
  it.each(TEXT_PAIRS)("%s on %s meets AA for text", (text, fill) => {
    expect(ratio(token(text), token(fill))).toBeGreaterThanOrEqual(4.5);
  });

  it("the focus ring and the period dot stay visible on pearl and porcelain (3:1)", () => {
    for (const fill of ["bubbles-blush", "bubbles-white"]) {
      expect(ratio(token("bubbles-grape"), token(fill))).toBeGreaterThanOrEqual(3);
      expect(ratio(token("bubbles-pink"), token(fill))).toBeGreaterThanOrEqual(3);
    }
  });

  it("keeps the palette warm: no blue-dominant colour anywhere in the app tokens", () => {
    const hexes = [...css.matchAll(/#([0-9A-Fa-f]{6})\b/g)].map((m) => m[1]);
    for (const hex of hexes) {
      const [r, g, b] = [0, 2, 4].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
      const max = Math.max(r, g, b);
      const delta = max - Math.min(r, g, b);
      if (delta < 0.04) continue; // near-neutral: no hue to speak of
      const hue = max === r ? (60 * ((g - b) / delta) + 360) % 360 : max === g ? 60 * ((b - r) / delta + 2) : 60 * ((r - g) / delta + 4);
      // Cyan to blue is cold. Iris violet sits at about 255 degrees and lilac at about 260, so the line is drawn at 248.
      expect(hue >= 170 && hue < 248, `#${hex} reads blue (hue ${Math.round(hue)})`).toBe(false);
    }
  });

  it("uses no pure black", () => {
    expect(css).not.toMatch(/#000000\b/i);
  });
});
