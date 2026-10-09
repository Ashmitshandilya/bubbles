/*
 * FINAL, APPROVED BUBBLES DESIGN (approved 2026-10-07).
 * Reference sheet: docs/brand/bubbles-identity-final.png. Do not change the drawing
 * (shapes, proportions, colours) without design sign-off; poses and animation live
 * in landing.css and story/BubblesHost.tsx.
 */
import { useId, type CSSProperties } from "react";
import { BubblesDefs, BubblesHead } from "./BubblesHead";

/**
 * Bubbles' mark: the character's own head with soft volumetric shading, set in a
 * blush-pink circle. Fine details (lashes, strands, highlights) drop away at small
 * sizes so the silhouette (horn, ear, mane) stays clear down to favicon size.
 */
export function BubblesMark({
  size = 40,
  title,
  className,
  style,
}: {
  size?: number;
  title?: string;
  className?: string;
  style?: CSSProperties;
}) {
  // One id prefix per instance: ids shared by two marks of the same size resolve to the first one in the
  // document, and if that copy is display:none (e.g. a hidden sidebar) the visible mark paints nothing.
  const u = `cm${useId().replace(/[^a-zA-Z0-9_-]/g, "")}`;
  return (
    <svg
      viewBox="-200 -230 400 400"
      width={size}
      height={size}
      className={className}
      style={style}
      role={title ? "img" : undefined}
      aria-label={title}
      aria-hidden={title ? undefined : true}
      focusable="false"
    >
      <BubblesDefs u={u} />
      <clipPath id={`${u}-badgeClip`}>
        <circle cx="0" cy="-30" r="198" />
      </clipPath>
      <circle cx="0" cy="-30" r="198" fill={`url(#${u}-badge)`} />
      <g clipPath={`url(#${u}-badgeClip)`}>
        <g transform="translate(-4 -2) scale(0.94)">
          <BubblesHead u={u} detail={size >= 32} still />
        </g>
      </g>
    </svg>
  );
}

/** The mark with the "bubbles" wordmark. */
export function BubblesLogo({ size = 34, className }: { size?: number; className?: string }) {
  return (
    <span className={`cw-logo ${className ?? ""}`}>
      <BubblesMark size={size} />
      <span className="cw-logo-word">bubbles</span>
    </span>
  );
}
