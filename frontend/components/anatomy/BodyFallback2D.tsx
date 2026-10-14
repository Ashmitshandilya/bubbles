"use client";

import type { CSSProperties } from "react";
import { ORGAN_TINT, STATUS_META, partOwners, type Organ } from "../../app/lib/organ-map";

/** Shared by the 3D viewer and this flat body, so the page can swap one for the other without changing anything else. */
export interface BodyViewProps {
  organs: readonly Organ[];
  selected: string | null;
  hovered: string | null;
  onSelect: (id: string) => void;
  onHover: (id: string | null) => void;
}

// Front view, drawn on the same proportions as the 3D model (1 unit = 4 mm; head top at y=0, hips near y=215).
// The left half of the outline is listed once and mirrored, so the body is symmetric by construction.
const LEFT_OUTLINE: ReadonlyArray<readonly number[]> = [
  [88, 0, 79, 10, 79, 25], // crown to temple
  [79, 37, 84, 44, 90, 49], // jaw
  [91, 55, 90, 60, 84, 63], // neck
  [74, 67, 63, 67, 57, 72], // trapezius to shoulder
  [50, 78, 48, 90, 48, 100], // deltoid
  [47, 125, 43, 150, 41, 175], // upper arm to elbow
  [39, 198, 37, 220, 36, 238], // forearm
  [35, 252, 37, 264, 42, 266], // hand
  [47, 267, 49, 258, 48, 248],
  [48, 228, 51, 205, 53, 185], // inner forearm
  [55, 160, 57, 130, 61, 108], // inner arm to armpit
  [63, 130, 66, 150, 67, 168], // side to waist
  [67, 185, 63, 200, 63, 215], // hip
  [63, 240, 66, 262, 68, 284], // outer thigh
  [78, 284, 88, 284, 97, 284],
  [97, 262, 98, 240, 100, 228], // inner thigh to crotch
];

const OUTLINE = (() => {
  const ends = [[100, 0], ...LEFT_OUTLINE.map((s) => [s[4], s[5]])];
  let d = "M100 0";
  for (const s of LEFT_OUTLINE) d += `C${s[0]} ${s[1]} ${s[2]} ${s[3]} ${s[4]} ${s[5]}`;
  for (let i = LEFT_OUTLINE.length - 1; i >= 0; i--) {
    const s = LEFT_OUTLINE[i];
    d += `C${200 - s[2]} ${s[3]} ${200 - s[0]} ${s[1]} ${200 - ends[i][0]} ${ends[i][1]}`;
  }
  return `${d}Z`;
})();

/** Mirror an absolute M/C/L path across the body's midline (x = 100). */
const mirror = (d: string) => {
  let i = 0;
  return d.replace(/-?\d+(\.\d+)?/g, (n) => (i++ % 2 === 0 ? String(200 - Number(n)) : n));
};

const KIDNEY = "M80 142C86 140 90 146 89 152C88 156 86 157 86 160C87 163 86 166 82 166C77 165 75 158 75 152C75 146 76 143 80 142Z";
const OVARY = "M84 195C88 192 93 194 93 198C93 202 88 203 85 202C82 201 81 197 84 195Z";
const RIBS = [0, 1, 2, 3, 4, 5].map((i) => {
  const y = 80 + i * 10;
  return `M98 ${y}C86 ${y - 5} 72 ${y} 70 ${y + 11 + i}`;
});

interface Shape {
  paths: string[];
  /** Fine lines drawn on top for texture; never interactive. */
  detail?: string;
  /** Drawn only when the map includes it (not everyone has one, and the 3D model has no mesh for it). */
  optional?: boolean;
}

// Paint order = stacking order: kidneys sit behind the gut, the heart in front of the lungs, the bladder in front.
const SHAPES: ReadonlyArray<readonly [string, Shape]> = [
  ["kidneys", { paths: [KIDNEY, mirror(KIDNEY)] }],
  [
    "lungs",
    {
      paths: [
        "M96 76C88 72 76 80 73 98C70 116 70 140 72 154C80 158 92 154 97 148C98 130 99 100 96 76Z",
        "M104 76C112 72 124 80 127 98C130 116 131 140 129 154C121 158 110 154 105 150C108 140 112 128 108 118C104 110 103 96 104 76Z",
      ],
      detail: "M96 82C90 92 84 104 80 120M104 82C110 92 116 104 120 120",
    },
  ],
  ["heart", { paths: ["M98 94C104 88 116 90 119 98C122 107 114 116 104 119C96 116 90 108 92 100C93 97 95 95 98 94Z"] }],
  ["liver", { paths: ["M72 124C80 114 104 112 122 118C125 121 122 126 116 130C104 138 88 150 78 153C72 148 70 134 72 124Z"] }],
  [
    "stomach",
    { paths: ["M112 121C122 120 128 128 126 138C124 147 114 152 104 150C97 149 93 145 95 141C100 142 108 141 112 136C115 131 110 127 108 124C108 122 110 121 112 121Z"] },
  ],
  ["pancreas", { paths: ["M86 152C90 146 100 147 108 145C113 143 118 144 118 148C118 152 112 153 106 154C98 156 92 160 88 158C85 156 85 154 86 152Z"] }],
  [
    "intestines",
    {
      paths: ["M72 168C72 160 80 158 88 160L112 160C120 158 128 160 128 168L128 204C128 214 120 218 112 216C106 215 104 212 100 212C96 212 92 216 86 216C78 217 72 212 72 204Z"],
      detail: "M80 174C88 168 96 180 104 172C112 166 120 178 118 186M80 190C88 184 96 196 104 188C112 182 120 194 116 202",
    },
  ],
  ["uterus", { paths: ["M94 194C94 190 106 190 106 194C106 201 103 205 101 209L99 209C97 205 94 201 94 194Z"], optional: true }],
  ["ovaries", { paths: [OVARY, mirror(OVARY)], optional: true }],
  ["bladder", { paths: ["M92 214C92 209 108 209 108 214C108 219 104 222 100 222C96 222 92 219 92 214Z"] }],
  [
    "brain",
    {
      paths: ["M100 4C112 4 118 13 118 23C118 33 112 40 104 41C102 41 101 40 100 39C99 40 98 41 96 41C88 40 82 33 82 23C82 13 88 4 100 4Z"],
      detail: "M100 7L100 37M88 14C92 18 88 22 92 26M112 14C108 18 112 22 108 26M86 30C90 32 94 30 96 33M114 30C110 32 106 30 104 33",
    },
  ],
  [
    "thyroid",
    { paths: ["M93 56C95 54 98 56 100 58C102 56 105 54 107 56C109 59 107 63 104 63C102 63 101 62 100 61C99 62 98 63 96 63C93 63 91 59 93 56Z"], optional: true },
  ],
];

const SKELETON = [
  "M66 70C76 66 88 68 98 68M102 68C112 68 124 66 134 70", // clavicles
  ...RIBS,
  ...RIBS.map(mirror),
  "M72 196C70 184 84 180 92 190C96 196 104 196 108 190C116 180 130 184 128 196C126 208 112 214 100 214C88 214 74 208 72 196Z", // pelvis
];

/** Head to upper thighs, like the 3D opening shot; the legs fade out below. */
const VIEW = { x: 30, y: -4, w: 140, h: 258 };

const tintVar = (id: string) => ORGAN_TINT[id] ?? "--tint-pink";
const IVORY = "color-mix(in srgb, var(--bubbles-sun-deep) 28%, var(--tint-sun))";

function organStyle(organ: Organ | undefined, id: string, active: boolean, hovered: boolean): CSSProperties {
  const status = organ?.status ?? "no_data";
  const color = `var(${STATUS_META[status].color})`;
  return {
    // The organ keeps its own calm colour (as in 3D); the status is the outline, and a soft glow once chosen.
    fill:
      status === "no_data"
        ? `var(${tintVar(id)})`
        : `color-mix(in srgb, var(${tintVar(id).replace("--tint-", "--bubbles-")}) 30%, var(${tintVar(id)}))`,
    stroke: status === "no_data" ? "var(--bubbles-ink-faint)" : color,
    strokeOpacity: status === "no_data" ? 0.45 : 1,
    strokeWidth: active ? 2.4 : hovered ? 1.9 : 1.3,
    strokeDasharray: status === "no_data" ? "3 2" : undefined,
    filter: active ? `drop-shadow(0 0 5px ${status === "no_data" ? "var(--bubbles-line-strong)" : color})` : undefined,
    cursor: organ ? "pointer" : "default",
  };
}

/**
 * The flat body: used when WebGL is missing, the device is low-end or saving data, motion is reduced, or the 3D model
 * fails to load. Same organ ids and the same pointer interaction as the 3D viewer (hover highlights, click or tap
 * selects). Like the 3D canvas it is hidden from assistive tech: the organ list beside it is the accessible control.
 */
export function BodyFallback2D({ organs, selected, hovered, onSelect, onHover }: BodyViewProps) {
  const owners = partOwners(organs);
  const isSelected = (part: string) => owners.get(part)?.id === selected && selected !== null;
  const isHovered = (part: string) => owners.get(part)?.id === hovered && hovered !== null;

  const bind = (part: string) => {
    const organ = owners.get(part);
    if (!organ) return {};
    return {
      "data-organ": organ.id,
      "data-part": part,
      "data-selected": isSelected(part) || undefined,
      onPointerEnter: () => onHover(organ.id),
      onPointerLeave: () => onHover(null),
      onClick: (event: { stopPropagation: () => void }) => {
        event.stopPropagation();
        onSelect(organ.id);
      },
    };
  };

  const skin = owners.get("skin");
  const skeleton = owners.get("skeleton");
  const skeletonStyle = organStyle(skeleton, "skeleton", isSelected("skeleton"), isHovered("skeleton"));

  return (
    <svg
      viewBox={`${VIEW.x} ${VIEW.y} ${VIEW.w} ${VIEW.h}`}
      className="h-full w-full touch-manipulation select-none"
      preserveAspectRatio="xMidYMid meet"
      aria-hidden="true"
      focusable="false"
      data-testid="body-flat"
    >
      <defs>
        <radialGradient id="body-flat-skin" cx="50%" cy="38%" r="70%">
          <stop offset="0%" style={{ stopColor: "var(--bubbles-white)" }} />
          <stop offset="100%" style={{ stopColor: "var(--tint-pink)" }} />
        </radialGradient>
        <linearGradient id="body-flat-fade" x1="0" y1="0" x2="0" y2="1" gradientUnits="objectBoundingBox">
          <stop offset="0.8" stopColor="#fff" />
          <stop offset="1" stopColor="#000" />
        </linearGradient>
        <mask id="body-flat-mask" maskUnits="userSpaceOnUse" x={VIEW.x} y={VIEW.y} width={VIEW.w} height={VIEW.h}>
          <rect x={VIEW.x} y={VIEW.y} width={VIEW.w} height={VIEW.h} fill="url(#body-flat-fade)" />
        </mask>
      </defs>

      <g mask="url(#body-flat-mask)">
        <path
          d={OUTLINE}
          {...bind("skin")}
          style={{
            fill: "url(#body-flat-skin)",
            stroke: skin && skin.status !== "no_data" ? `var(${STATUS_META[skin.status].color})` : "var(--bubbles-line-strong)",
            strokeWidth: isSelected("skin") ? 2.4 : isHovered("skin") ? 1.8 : 1.2,
            cursor: skin ? "pointer" : "default",
          }}
        />

        <g
          {...bind("skeleton")}
          style={{
            fill: "none",
            stroke: isSelected("skeleton") || isHovered("skeleton") ? skeletonStyle.stroke : IVORY,
            strokeWidth: isSelected("skeleton") ? 2.6 : isHovered("skeleton") ? 2.2 : 1.6,
            strokeLinecap: "round",
            pointerEvents: "visibleStroke",
            cursor: skeleton ? "pointer" : "default",
          }}
        >
          <path d="M100 50L100 208" strokeWidth={4} strokeDasharray="4 1.6" />
          {SKELETON.map((d) => (
            <path key={d} d={d} />
          ))}
        </g>

        {SHAPES.map(([part, shape]) => {
          const organ = owners.get(part);
          if (shape.optional && !organ) return null;
          return (
            <g key={part} {...bind(part)} style={organStyle(organ, part, isSelected(part), isHovered(part))}>
              {shape.paths.map((d) => (
                <path key={d} d={d} />
              ))}
              {shape.detail && (
                <path d={shape.detail} style={{ fill: "none", strokeWidth: 0.8, strokeDasharray: "none", opacity: 0.45, pointerEvents: "none" }} />
              )}
            </g>
          );
        })}
      </g>
    </svg>
  );
}
