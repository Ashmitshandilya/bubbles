"use client";

// Hand-rolled SVG visuals: sleep score ring, weekday sleep bars (with a table view), year-in-pixels table, hydration garden.
// Each has a text alternative, never relies on colour alone, and only moves when the device allows motion.

import { useId, useState } from "react";
import { barBoxes, gardenAlt, gardenStage, pixelSummary, pixelTable, ringDash, MOOD_WORDS, weekdayAverages, type GardenStage } from "../../app/lib/wellness-chart";
import { formatHours, scoreWords } from "../../app/lib/wellness-format";
import type { Pixels } from "../../app/lib/wellness-types";
import { BTN_TEXT } from "./ui";
import { useReducedMotion } from "./useWellness";

/* ── Score ring ─────────────────────────────────────────────────────── */

export function ScoreRing({ value, label, size = 148 }: { value: number; label?: string; size?: number }) {
  const r = 56;
  const { dash, gap } = ringDash(value, r);
  const words = label ?? scoreWords(value);
  return (
    <div className="flex flex-col items-center gap-1">
      <svg width={size} height={size} viewBox="0 0 140 140" role="img" aria-label={`Sleep score ${Math.round(value)} out of 100, ${words}`}>
        <circle cx="70" cy="70" r={r} fill="none" stroke="#F1ECFB" strokeWidth="14" />
        <circle
          cx="70" cy="70" r={r} fill="none" stroke="#D6246F" strokeWidth="14" strokeLinecap="round"
          strokeDasharray={`${dash} ${gap}`} transform="rotate(-90 70 70)"
        />
        <text x="70" y="76" textAnchor="middle" fontSize="38" fontWeight="800" fill="#2B1A3F" aria-hidden="true">
          {Math.round(value)}
        </text>
        <text x="70" y="98" textAnchor="middle" fontSize="12" fontWeight="700" fill="#5E5873" aria-hidden="true">
          out of 100
        </text>
      </svg>
      <p className="m-0 font-display text-h4 text-default">{words}</p>
    </div>
  );
}

/* ── Weekday sleep bars ─────────────────────────────────────────────── */

export function WeekdayChart({ series, goalHours }: { series: { date: string; hours: number }[] | undefined; goalHours: number }) {
  const [asTable, setAsTable] = useState(false);
  const titleId = useId();
  const bars = weekdayAverages(series);
  const haveData = bars.filter((b) => b.hours !== null);
  const W = 308;
  const H = 120;
  const ceiling = Math.max(10, Math.ceil(goalHours + 1), ...haveData.map((b) => b.hours ?? 0));
  const boxes = barBoxes(bars.map((b) => b.hours), W, H, ceiling);
  const summary = haveData.length
    ? `Average hours of sleep by weekday: ${haveData.map((b) => `${b.full} ${formatHours(b.hours)}`).join(", ")}. Weekdays with fewer than 2 logged nights are left out.`
    : "Not enough nights logged per weekday yet.";

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p id={titleId} className="m-0 text-body-sm font-bold text-muted">
          Average sleep by weekday
        </p>
        <button type="button" aria-pressed={asTable} onClick={() => setAsTable((v) => !v)} className={BTN_TEXT}>
          {asTable ? "Show as chart" : "Show as table"}
        </button>
      </div>

      {asTable ? (
        <table className="w-full border-collapse text-left text-body-sm">
          <caption className="sr-only">{summary}</caption>
          <thead>
            <tr className="border-b-2 border-line text-muted">
              <th scope="col" className="py-2 pr-3 font-extrabold">Weekday</th>
              <th scope="col" className="py-2 pr-3 font-extrabold">Average</th>
              <th scope="col" className="py-2 font-extrabold">Nights logged</th>
            </tr>
          </thead>
          <tbody>
            {bars.map((b) => (
              <tr key={b.index} className="border-b border-line">
                <th scope="row" className="py-2 pr-3 font-bold text-ink">{b.full}</th>
                <td className="py-2 pr-3 text-ink">{b.hours === null ? "Not enough nights yet" : formatHours(b.hours)}</td>
                <td className="py-2 text-muted">{b.nights}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <svg viewBox={`0 0 ${W + 20} ${H + 44}`} role="img" aria-labelledby={titleId} aria-describedby={`${titleId}-desc`} className="h-auto w-full max-w-[460px]">
          <desc id={`${titleId}-desc`}>{summary}</desc>
          <g transform="translate(10 18)">
            {/* goal line */}
            <line x1="0" x2={W} y1={H - (goalHours / ceiling) * H} y2={H - (goalHours / ceiling) * H} stroke="#D6246F" strokeWidth="1.5" strokeDasharray="5 4" />
            <text x={W} y={H - (goalHours / ceiling) * H - 4} textAnchor="end" fontSize="10" fontWeight="700" fill="#5835BF">
              your goal {formatHours(goalHours)}
            </text>
            {boxes.map((box, i) =>
              box ? (
                <g key={bars[i].index}>
                  <rect x={box.x} y={box.y} width={box.width} height={box.height} rx="6" fill="#D6246F" />
                  <text x={box.x + box.width / 2} y={box.y - 4} textAnchor="middle" fontSize="10" fontWeight="800" fill="#2B1A3F">
                    {bars[i].hours}
                  </text>
                </g>
              ) : (
                <rect
                  key={bars[i].index} x={(W / 7) * i + (W / 7) * 0.15} y={H - 8} width={(W / 7) * 0.7} height="8" rx="4"
                  fill="none" stroke="#C9B6F2" strokeWidth="2" strokeDasharray="3 3"
                />
              ),
            )}
            {bars.map((b, i) => (
              <text key={b.index} x={(W / 7) * i + W / 14} y={H + 16} textAnchor="middle" fontSize="11" fontWeight="700" fill="#5E5873">
                {b.short}
              </text>
            ))}
          </g>
        </svg>
      )}
      <p className="m-0 text-body-sm text-muted">{haveData.length ? "Dashed outlines mean fewer than 2 logged nights, so there is no average yet." : summary}</p>
    </div>
  );
}

/* ── Year in pixels ─────────────────────────────────────────────────── */

const LEVEL_FILL: Record<number, string> = {
  1: "bg-[#FBCFC6]",
  2: "bg-[#F1E2C2]",
  3: "bg-tint-mint",
  4: "bg-[#E3D8CA]",
  5: "bg-bubbles-mint",
};
const MONTH_INITIAL = ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"];

/**
 * A table: months across, days down. Every real cell holds its mood number (1 Rough to 5 Great) AND a screen-reader label
 * with the date and mood word, so the grid never relies on colour. Days that do not exist (30 February) are empty.
 */
export function PixelGrid({ pixels }: { pixels: Pixels }) {
  const table = pixelTable(pixels.days, pixels.year);
  const summary = pixelSummary(pixels.logged_days, pixels.level_counts, pixels.year);
  return (
    <div className="flex flex-col gap-3">
      <p className="m-0 text-body-sm font-bold text-ink">{summary}</p>
      <div className="overflow-x-auto">
        <table className="w-full max-w-[460px] table-fixed border-separate border-spacing-[3px]">
          <caption className="sr-only">
            Year in pixels for {pixels.year}. Each row is a day of the month and each column a month. {summary}
          </caption>
          <thead>
            <tr>
              <td className="w-6" />
              {table.months.map((m, i) => (
                <th key={m} scope="col" className="p-0 text-center text-[0.75rem] font-extrabold text-muted">
                  <span aria-hidden="true">{MONTH_INITIAL[i]}</span>
                  <span className="sr-only">{m}</span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {table.rows.map((row, d) => (
              <tr key={d}>
                <th scope="row" className="p-0 pr-1 text-right text-[0.75rem] font-bold text-ink-faint">
                  <span className="sr-only">Day </span>
                  {d + 1}
                </th>
                {row.map((cell, m) =>
                  cell ? (
                    <td
                      key={m}
                      className={`relative h-[22px] rounded-md p-0 text-center align-middle text-[0.75rem] font-extrabold leading-[22px] text-ink ${cell.level ? LEVEL_FILL[cell.level] : "border border-dashed border-line-strong bg-surface"}`}
                    >
                      <span aria-hidden="true">{cell.level ?? ""}</span>
                      <span className="sr-only">{cell.label}</span>
                    </td>
                  ) : (
                    <td key={m} aria-hidden="true" className="h-[22px] p-0" />
                  ),
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <ul className="m-0 flex list-none flex-wrap gap-x-4 gap-y-2 p-0" aria-label="Key">
        {[1, 2, 3, 4, 5].map((l) => (
          <li key={l} className="flex items-center gap-2 text-body-sm font-bold text-ink-soft">
            <span aria-hidden="true" className={`flex h-[22px] w-[22px] items-center justify-center rounded-md text-[0.75rem] font-extrabold text-ink ${LEVEL_FILL[l]}`}>
              {l}
            </span>
            {MOOD_WORDS[l]}
          </li>
        ))}
        <li className="flex items-center gap-2 text-body-sm font-bold text-ink-soft">
          <span aria-hidden="true" className="h-[22px] w-[22px] rounded-md border border-dashed border-line-strong bg-surface" />
          No check-in
        </li>
      </ul>
    </div>
  );
}

/* ── Hydration garden ───────────────────────────────────────────────── */

function Plant({ stage }: { stage: GardenStage }) {
  const leaf = (x: number, y: number, rot: number, s = 1) => (
    <path key={`${x}-${y}`} d="M0 0C10-14 26-14 32 0C20 10 8 10 0 0Z" fill="#D9CBB8" stroke="#5C4A33" strokeWidth="1.5" transform={`translate(${x} ${y}) rotate(${rot}) scale(${s})`} />
  );
  const flower = (cx: number, cy: number, s = 1) => (
    <g key={`f${cx}`} transform={`translate(${cx} ${cy}) scale(${s})`}>
      {[0, 72, 144, 216, 288].map((a) => (
        <ellipse key={a} cx="0" cy="-11" rx="7" ry="10" fill="#F7C8D6" stroke="#B03A66" strokeWidth="1.2" transform={`rotate(${a})`} />
      ))}
      <circle r="6" fill="#E9C98B" stroke="#7A5208" strokeWidth="1.2" />
    </g>
  );
  switch (stage) {
    case "seed":
      return (
        <g>
          <ellipse cx="160" cy="152" rx="26" ry="9" fill="#9A3A12" opacity="0.35" />
          <ellipse cx="160" cy="146" rx="9" ry="6" fill="#9A3A12" />
        </g>
      );
    case "sprout":
      return (
        <g>
          <path d="M160 156 V126" stroke="#5C4A33" strokeWidth="4" strokeLinecap="round" />
          {leaf(160, 130, -150, 0.8)}
          {leaf(160, 126, -30, 0.8)}
        </g>
      );
    case "leaves":
      return (
        <g>
          <path d="M160 156 V96" stroke="#5C4A33" strokeWidth="5" strokeLinecap="round" />
          {leaf(160, 138, -160)}
          {leaf(160, 124, -20)}
          {leaf(160, 108, -165, 1.1)}
          {leaf(160, 98, -15, 1.1)}
        </g>
      );
    case "blossom":
      return (
        <g>
          <path d="M160 156 V92" stroke="#5C4A33" strokeWidth="5" strokeLinecap="round" />
          {leaf(160, 138, -160)}
          {leaf(160, 124, -20)}
          {flower(160, 82, 1.3)}
        </g>
      );
    case "pond":
      return (
        <g>
          <path d="M120 156 V100" stroke="#5C4A33" strokeWidth="5" strokeLinecap="round" />
          {leaf(120, 140, -160)}
          {leaf(120, 126, -20)}
          {flower(120, 90, 1.3)}
          <path d="M92 150 V128" stroke="#5C4A33" strokeWidth="4" strokeLinecap="round" />
          {flower(92, 122, 0.8)}
          <ellipse cx="214" cy="158" rx="52" ry="14" fill="#CDB9DA" stroke="#8E6FA6" strokeWidth="2" />
          <path d="M190 156 q10 -4 20 0 M214 162 q10 -4 20 0" stroke="#8E6FA6" strokeWidth="1.5" fill="none" strokeLinecap="round" />
        </g>
      );
    case "oasis":
      return (
        <g>
          <path d="M120 158 C118 130 126 104 134 82" stroke="#9A3A12" strokeWidth="7" fill="none" strokeLinecap="round" />
          {[-60, -25, 10, 45, 80].map((a) => (
            <path key={a} d="M0 0 C16 -16 40 -14 54 4 C36 -2 16 0 0 0Z" fill="#D9CBB8" stroke="#5C4A33" strokeWidth="1.5" transform={`translate(134 82) rotate(${a - 20})`} />
          ))}
          <path d="M92 152 V132" stroke="#5C4A33" strokeWidth="4" strokeLinecap="round" />
          {flower(92, 126, 0.75)}
          <ellipse cx="220" cy="158" rx="60" ry="15" fill="#CDB9DA" stroke="#8E6FA6" strokeWidth="2" />
          <path d="M194 156 q10 -4 20 0 M222 163 q10 -4 20 0" stroke="#8E6FA6" strokeWidth="1.5" fill="none" strokeLinecap="round" />
          <path d="M262 150 V132" stroke="#5C4A33" strokeWidth="4" strokeLinecap="round" />
          {flower(262, 126, 0.75)}
        </g>
      );
  }
}

/**
 * Bubbles' garden: the plant grows with goal days (garden level from the API); the gauge on the left shows today's progress.
 * Only drawn when the API sent a goal (never for people with a fluid plan). Sways gently only when motion is allowed.
 */
export function GardenScene({ level, percent }: { level: number; percent: number }) {
  const reduced = useReducedMotion();
  const stage = gardenStage(level);
  const pct = Math.max(0, Math.min(100, percent));
  const gaugeTop = 36;
  const gaugeH = 116;
  const fillH = (gaugeH * pct) / 100;
  return (
    <svg viewBox="0 0 320 200" role="img" aria-label={gardenAlt(stage, pct)} className="h-auto w-full max-w-[460px] rounded-3xl">
      <rect width="320" height="200" fill="#F6F0F8" />
      <circle cx="268" cy="40" r="20" fill="#E9C98B" />
      <path d="M0 150 Q80 128 160 142 T320 140 V200 H0Z" fill="#E3D8CA" />
      <path d="M0 168 Q90 150 170 162 T320 160 V200 H0Z" fill="#CDBDA8" />
      <g className={reduced ? "" : "bubbles-breathe"} style={{ transformBox: "fill-box", transformOrigin: "50% 100%" }}>
        <Plant stage={stage} />
      </g>
      {/* today's water gauge */}
      <g>
        <rect x="22" y={gaugeTop} width="22" height={gaugeH} rx="11" fill="#FFFFFF" stroke="#8E6FA6" strokeWidth="2.5" />
        <clipPath id="gauge-clip">
          <rect x="22" y={gaugeTop} width="22" height={gaugeH} rx="11" />
        </clipPath>
        <rect
          x="22" y={gaugeTop + gaugeH - fillH} width="22" height={fillH} fill="#8E6FA6" clipPath="url(#gauge-clip)"
          style={{ transition: reduced ? "none" : "y .6s ease, height .6s ease" }}
        />
        <text x="33" y={gaugeTop + gaugeH + 18} textAnchor="middle" fontSize="12" fontWeight="800" fill="#5F4372">
          {Math.round(pct)}%
        </text>
      </g>
    </svg>
  );
}
