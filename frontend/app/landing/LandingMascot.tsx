/**
 * Bubbles on the landing page. For now a cut-out of the front view from the turnaround sheet
 * (public/brand/bubbles-front.webp, 220 x 587). When components/mascot/BubblesMascot3D lands, this
 * file is the one place to swap: render <BubblesMascot3D pose={pose} size={size} /> instead.
 * The size is the rendered height in px; the width follows the picture's aspect, so nothing jumps.
 */
export function LandingMascot({ size, className = "", title }: { pose?: "idle" | "wave"; size: number; className?: string; title?: string }) {
  return (
    // eslint-disable-next-line @next/next/no-img-element -- a small static cut-out with fixed dimensions; next/image adds nothing here
    <img
      src="/brand/bubbles-front.webp"
      width={Math.round((size * 220) / 587)}
      height={size}
      alt={title ?? ""}
      aria-hidden={title ? undefined : true}
      decoding="async"
      draggable={false}
      className={`cw-mascot ${className}`}
    />
  );
}
