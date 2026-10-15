// Colours for the 3D body. Bubbles is light-first (no automatic dark mode), so there is one palette. The organ status colours are
// checked against the body in palette.test.ts (the canvas is decorative: the list beside it is the accessible source of truth).

export const CANVAS = "#FFF6FA";          // the blush the canvas sits on (--bubbles-blush)
export const BODY_FILL = "#FFC9E0";       // soft pink of the figure (translucent, like the first body)
export const BODY_EDGE = "#EE86B2";       // a soft rim, not a line: it only lifts the edge off the canvas
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
