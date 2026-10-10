import type { CSSProperties } from "react";

/**
 * Soap bubbles in pure CSS: the whole look in the static tier (reduced motion, no WebGL2, weak devices) and the
 * first paint before the 3D ones arrive. They sit in a chapter's back layer, away from the copy, and hide as soon
 * as the WebGL bubbles are running (`.cw[data-soap="gl"]`). Decorative: aria-hidden, never interactive.
 */
type Bubble = { x: number; y: number; s: number; d: number; rot: number };

const FIELDS: Record<"hero" | "finale", Bubble[]> = {
  // Right half and the strip above the headline; the copy sits bottom left.
  hero: [
    { x: 84, y: 22, s: 150, d: 9, rot: 20 },
    { x: 66, y: 12, s: 64, d: 7, rot: 140 },
    { x: 94, y: 56, s: 84, d: 11, rot: 260 },
    { x: 72, y: 60, s: 46, d: 8, rot: 80 },
    { x: 48, y: 18, s: 38, d: 10, rot: 200 },
    { x: 14, y: 22, s: 54, d: 12, rot: 310 },
  ],
  // Along both edges; the finale copy is centred.
  finale: [
    { x: 9, y: 30, s: 120, d: 9, rot: 60 },
    { x: 92, y: 24, s: 96, d: 11, rot: 180 },
    { x: 18, y: 72, s: 54, d: 8, rot: 300 },
    { x: 86, y: 70, s: 140, d: 10, rot: 20 },
    { x: 4, y: 52, s: 38, d: 12, rot: 120 },
  ],
};

type Vars = CSSProperties & Record<`--${string}`, string | number>;

export function SoapCss({ variant }: { variant: "hero" | "finale" }) {
  return (
    <div className="cw-soapcss" aria-hidden="true">
      {FIELDS[variant].map((b, k) => (
        <span key={k} style={{ "--x": `${b.x}%`, "--y": `${b.y}%`, "--s": b.s, "--d": `${b.d}s`, "--rot": `${b.rot}deg` } as Vars} />
      ))}
    </div>
  );
}
