/*
 * FINAL, APPROVED BUBBLES DESIGN (approved 2026-10-07).
 * Reference sheet: docs/brand/bubbles-identity-final.png. Do not change the drawing
 * (shapes, proportions, colours) without design sign-off; poses and animation live
 * in landing.css and story/BubblesHost.tsx.
 */
import type { CSSProperties } from "react";
import { BubblesDefs, BubblesHead, BubblesNeck } from "./BubblesHead";

/**
 * Bubbles, the little doctor: a baby unicorn in a nurse cap and a tailored doctor's
 * coat (piped collar, pink scrubs, chest pocket with pens, ID badge, buttons,
 * patch pockets, trimmed cuffs) with a heart stethoscope. Vector art with soft
 * volumetric shading (no WebGL). Parts are grouped so CSS can pose and animate
 * them: arms, head, eyes, ears, mane, tail.
 *
 * Pose and expression come from data attributes on the root, e.g.
 *   data-pose="idle | wave | point | present | think | cheer | surprised | fly"
 *   data-mood="calm | happy | surprised"
 * and the look direction from --look-x / --look-y (-1..1).
 *
 * Geometry (viewBox 0 0 360 520): horn tip y≈63, hooves y≈506, pelvis line y≈426.
 */
export function BubblesFigure({
  uid,
  pose = "idle",
  mood = "calm",
  className,
  style,
  title,
}: {
  uid: string;
  pose?: string;
  mood?: string;
  className?: string;
  style?: CSSProperties;
  title?: string;
}) {
  const url = (name: string) => `url(#${uid}-${name})`;
  return (
    <svg
      viewBox="0 0 360 520"
      className={`cf ${className ?? ""}`}
      style={style}
      data-pose={pose}
      data-mood={mood}
      role={title ? "img" : undefined}
      aria-label={title}
      aria-hidden={title ? undefined : true}
      focusable="false"
    >
      <BubblesDefs u={uid} />
      <clipPath id={`${uid}-coatClip`}>
        <path d={COAT} />
      </clipPath>

      <ellipse className="cf-shadow" cx="175" cy="507" rx="108" ry="13" fill={url("ground")} />

      <g className="cf-bob">
        {/* tail */}
        <g className="cf-tail">
          <path d="M100 418c-48-6-84 18-88 54-4 32 20 50 46 42-16-6-20-26-8-38 12-10 30 0 26 16 16-8 26-38 24-74Z" fill={url("mane")} />
          <path d="M92 428c-30 2-52 18-58 42" fill="none" stroke="#FFD6EA" strokeWidth="4" strokeLinecap="round" opacity="0.8" />
        </g>

        {/* back arm (behind the coat) */}
        <g className="cf-arm cf-arm--back">
          <path d="M122 316c-16 6-26 22-28 40l-6 54c-1 11 7 19 18 19s18-7 19-18l7-62Z" fill={url("coatBack")} />
          <path d="M86 400c8 6 28 7 38 1l-1 11c-10 6-30 5-38-1Z" fill="#FFFFFF" />
          <ellipse cx="105" cy="432" rx="19" ry="16" fill={url("fur")} />
          <path d="M88 438c5 9 29 10 35 0" fill={url("hoof")} />
        </g>

        {/* legs */}
        <rect x="122" y="436" width="40" height="60" rx="18" fill={url("furSide")} />
        <rect x="184" y="436" width="42" height="60" rx="18" fill={url("furSide")} />
        <path d="M119 484h46v10c0 8-6 13-14 13h-18c-8 0-14-5-14-13Z" fill={url("hoof")} />
        <path d="M181 484h48v10c0 8-6 13-14 13h-20c-8 0-14-5-14-13Z" fill={url("hoof")} />
        <path d="M124 490h36M187 490h38" stroke="#FFE1EF" strokeWidth="2.4" strokeLinecap="round" opacity="0.9" />

        {/* neck, tucked into the coat collar */}
        <g transform={HEAD_TRANSFORM}>
          <BubblesNeck u={uid} />
        </g>

        {/* coat */}
        <g className="cf-body">
          <path d={COAT} fill={url("coat")} />
          <g clipPath={url("coatClip")}>
            {/* volume: turned-away side, hem and a soft fold */}
            <path d="M236 300c16 40 18 110 12 166h34V300Z" fill="#CFC2E2" opacity="0.55" filter={url("soft")} />
            <path d="M80 444h200v40H80Z" fill="#CDBFE0" opacity="0.4" filter={url("soft")} />
            <path d="M206 372c6 30 6 62 0 92" fill="none" stroke="#E6DDF1" strokeWidth="5" strokeLinecap="round" />
            {/* placket and back vent */}
            <path d="M176 352v114" stroke="#E2D9EE" strokeWidth="2.4" />
            {/* chest pocket with pens (near side) */}
            <path d="M104 368h40v26c0 5-3 8-8 8h-24c-5 0-8-3-8-8Z" fill="#F4F0FA" />
            <path d="M104 368h40" stroke="#FF9CC8" strokeWidth="3" strokeLinecap="round" />
            <rect x="113" y="352" width="6" height="22" rx="3" fill="#FF6FB2" />
            <rect x="123" y="356" width="5.5" height="18" rx="2.75" fill="#B49BFF" />
            <circle cx="116" cy="352" r="3.2" fill="#FFD3E8" />
            {/* patch pockets */}
            <path d="M98 420h44v24c0 5-3 8-8 8h-28c-5 0-8-3-8-8Z" fill="#F4F0FA" />
            <path d="M98 420h44" stroke="#FF9CC8" strokeWidth="3" strokeLinecap="round" />
            <path d="M208 420h40v24c0 5-3 8-8 8h-24c-5 0-8-3-8-8Z" fill="#ECE5F5" />
            <path d="M208 420h40" stroke="#FF9CC8" strokeWidth="3" strokeLinecap="round" />
          </g>
          {/* pink scrubs at the neck */}
          <path d="M146 300l30 56 30-56Z" fill={url("scrub")} />
          <path d="M162 300l14 26 14-26" fill="none" stroke="#FFC9E2" strokeWidth="2" />
          {/* collar with pink piping */}
          <path d="M140 296c-12 14-12 36-2 52l38 8-30-62Z" fill="#FFFFFF" />
          <path d="M212 296c12 14 12 36 2 52l-38 8 30-62Z" fill="#F3EEF9" />
          <path d="M140 296c-12 14-12 36-2 52l38 8M212 296c12 14 12 36 2 52l-38 8" fill="none" stroke="#FF8DC0" strokeWidth="2.6" strokeLinejoin="round" />
          {/* buttons */}
          <circle cx="176" cy="390" r="5.5" fill="#FF8DC0" />
          <circle cx="176" cy="416" r="5.5" fill="#FF8DC0" />
          <circle cx="176" cy="442" r="5.5" fill="#FF8DC0" />
          <circle cx="174.5" cy="388.5" r="1.8" fill="#FFFFFF" opacity="0.9" />
          <circle cx="174.5" cy="414.5" r="1.8" fill="#FFFFFF" opacity="0.9" />
          <circle cx="174.5" cy="440.5" r="1.8" fill="#FFFFFF" opacity="0.9" />
          {/* ID badge */}
          <g transform="rotate(4 226 378)">
            <rect x="222" y="352" width="8" height="10" rx="2" fill="#D7AFC4" />
            <rect x="206" y="360" width="40" height="46" rx="7" fill="#FFFFFF" stroke="#EADFF3" strokeWidth="1.5" />
            <rect x="206" y="360" width="40" height="11" rx="5" fill="#FF6FB2" />
            <path d="M226 384c-2-4-9-3-9 2 0 4 6 7 9 9 3-2 9-5 9-9 0-5-7-6-9-2Z" fill="#FF5FA8" />
            <rect x="214" y="397" width="24" height="3" rx="1.5" fill="#D9CDE8" />
          </g>
        </g>

        {/* stethoscope */}
        <g className="cf-steth">
          <path d="M146 300c-8 30 4 56 30 70M206 300c8 30-4 56-30 70" fill="none" stroke="#E2559A" strokeWidth="5.5" strokeLinecap="round" />
          <path d="M146 300c-8 30 4 56 30 70" fill="none" stroke="#FFA8D0" strokeWidth="1.6" strokeLinecap="round" opacity="0.85" />
          <path d="M176 370v8" stroke="#E2559A" strokeWidth="5.5" strokeLinecap="round" />
          <circle cx="176" cy="392" r="14" fill={url("metal")} />
          <path d="M176 389c-2-4-8-3-8 2 0 4 5 6 8 8 3-2 8-4 8-8 0-5-6-6-8-2Z" fill="#FF6FB2" />
        </g>

        {/* front arm: drawn behind the head, so a raised hoof peeks out beside the face */}
        <g className="cf-arm cf-arm--front">
          <g transform="translate(10 0)">
            <path d="M228 316c16-6 30 2 32 18l6 62c1 11-8 19-19 19s-19-6-20-17l-6-58c-1-12 2-20 7-24Z" fill={url("coat")} />
            <path d="M220 392c10 6 30 6 42-2l1 12c-12 8-32 8-42 2Z" fill="#FFFFFF" />
            <path d="M220 398c10 6 30 6 42-2" fill="none" stroke="#FF8DC0" strokeWidth="2.6" />
            <ellipse cx="244" cy="422" rx="19" ry="16" fill={url("fur")} />
            <path d="M227 428c5 9 29 10 35 0" fill={url("hoof")} />
          </g>
        </g>

        {/* head */}
        <g className="cf-head">
          <g transform={HEAD_TRANSFORM}>
            <BubblesHead u={uid} cap neck={false} />
          </g>
        </g>
      </g>
    </svg>
  );
}

/** Where the head (and neck) sit on the body. */
const HEAD_TRANSFORM = "translate(190 210) scale(0.8)";

const COAT = "M140 296c-26 6-38 24-42 48l-12 94c-2 14 8 24 22 24h136c14 0 24-10 22-24l-12-94c-4-24-16-42-42-48l-36 60Z";
