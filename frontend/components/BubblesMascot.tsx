import type { CSSProperties } from "react";
import { BubblesMark } from "../app/landing/BubblesMark";

export type BubblesMood = "calm" | "happy" | "thinking" | "caring" | "resting";

export interface BubblesMascotProps {
  size?: number;
  mood?: BubblesMood;
  /** Ambient motion (breathing/hopping/tilting). Always off under prefers-reduced-motion. */
  animated?: boolean;
  /** Accessible name. Without it the mascot is decorative (aria-hidden). */
  title?: string;
  className?: string;
  style?: CSSProperties;
}

/**
 * Bubbles, the brand character, as drawn in the approved final design (docs/brand/bubbles-identity-final.png).
 * The drawing itself lives in app/landing/BubblesMark.tsx and must not be redrawn here; moods are expressed with
 * motion and a small sign beside her, so every screen shows the same Bubbles.
 *
 * Moods map to product states: calm (default), happy (saved/streaks), thinking (AI working),
 * caring (AMBER / hard moments), resting (offline/empty). In RED safety states the UI should not show the mascot at all.
 */
export function BubblesMascot({ size = 64, mood = "calm", animated = true, title, className = "", style }: BubblesMascotProps) {
  const motion = !animated ? "" : mood === "thinking" ? "bubbles-tilt" : mood === "happy" ? "bubbles-hop" : mood === "resting" ? "" : "bubbles-breathe";

  return (
    <span
      className={`relative inline-flex shrink-0 ${motion} ${className}`}
      style={{ width: size, height: size, ...style }}
      role={title ? "img" : undefined}
      aria-label={title}
      aria-hidden={title ? undefined : true}
    >
      <BubblesMark size={size} />
      {size >= 40 && mood !== "calm" && <MoodSign mood={mood} size={size} />}
    </span>
  );
}

/** A small sign in the corner: sparkle (happy), dots (thinking), heart (caring), z (resting). Decorative only. */
function MoodSign({ mood, size }: { mood: Exclude<BubblesMood, "calm">; size: number }) {
  const box = Math.max(14, Math.round(size * 0.3));
  return (
    <svg
      viewBox="0 0 24 24"
      width={box}
      height={box}
      aria-hidden="true"
      focusable="false"
      style={{ position: "absolute", right: -Math.round(box * 0.15), top: -Math.round(box * 0.1) }}
    >
      {mood === "happy" && <path d="M12 2l2.2 6.3L21 10l-6.8 1.7L12 18l-2.2-6.3L3 10l6.8-1.7z" fill="#FFC83D" stroke="#2B1A3F" strokeWidth="1.4" strokeLinejoin="round" />}
      {mood === "thinking" && (
        <>
          <circle cx="5" cy="19" r="2.4" fill="#6A45F5" />
          <circle cx="12" cy="13" r="3.2" fill="#6A45F5" />
          <circle cx="18" cy="6" r="4" fill="#6A45F5" />
        </>
      )}
      {mood === "caring" && <path d="M12 21s-8-5.2-8-11a4.6 4.6 0 0 1 8-3 4.6 4.6 0 0 1 8 3c0 5.800-8 11-8 11z" fill="#FF5FA2" stroke="#2B1A3F" strokeWidth="1.4" strokeLinejoin="round" />}
      {mood === "resting" && <path d="M5 6h8L5 14h8M14 12h6l-6 7h6" fill="none" stroke="#6A45F5" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />}
    </svg>
  );
}
