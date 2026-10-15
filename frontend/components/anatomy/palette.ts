// Colours for the 3D body. Bubbles is light-first (no automatic dark mode), so there is one palette. Every pair that
// matters is checked in palette.test.ts: the silhouette outline against the canvas, and each status colour against the body.

export const CANVAS = "#FFF6FA";          // the blush the canvas sits on (--bubbles-blush)
export const BODY_FILL = "#F9D0E3";       // skin tone of the figure
export const BODY_OUTLINE = "#A8155A";    // silhouette line (--bubbles-pink-deep)
export const SELECT_GLOW = "#6A45F5";     // emissive + halo (--bubbles-grape)

/** One colour per assessment status. Darker than the list dots on purpose: they sit on the pink body and need 3:1 against it. */
export const STATUS_COLOR: Record<string, string> = {
  unknown: "#7F6BA8",
  no_major_risk_signal: "#0B7F5F",
  watch: "#9A6100",
  needs_attention: "#C2410C",
};

export function statusColor(status: string | undefined): string {
  return STATUS_COLOR[status ?? "unknown"] ?? STATUS_COLOR.unknown;
}

function channel(value: number): number {
  const c = value / 255;
  return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
}

function luminance(hex: string): number {
  const n = parseInt(hex.replace("#", ""), 16);
  return 0.2126 * channel((n >> 16) & 255) + 0.7152 * channel((n >> 8) & 255) + 0.0722 * channel(n & 255);
}

/** WCAG contrast ratio between two #RRGGBB colours (1 to 21). */
export function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}
