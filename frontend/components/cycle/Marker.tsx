// Calendar marker shapes. Shape (not colour) tells them apart: filled drop = logged period, dashed ring = predicted,
// dotted ring = possible, diamond = fertile window, star = ovulation, small dot = has a log. Decorative: the day's
// aria-label carries the meaning.

import type { MarkerKind } from "../../app/lib/cycle-markers";

const PINK = "var(--phase-period)";
const MINT = "var(--bubbles-sun-deep)";
const SUN = "#A8700F"; // gold, 4.2:1 on porcelain
const INK = "var(--bubbles-ink-soft)";

const STAR = "M6 1.2l1.4 3 3.2.4-2.4 2.2.7 3.2L6 8.4 3.1 10l.7-3.2L1.4 4.6l3.2-.4z";

/** The shapes only, for drawing inside an existing 12x12 SVG box. */
export function MarkerShapes({ kind }: { kind: MarkerKind }) {
  return (
    <>
      {kind === "period-logged" && <path d="M6 1C6 1 2 5.6 2 8a4 4 0 0 0 8 0C10 5.6 6 1 6 1z" fill={PINK} />}
      {kind === "period-predicted" && <circle cx="6" cy="6" r="4.2" fill="none" stroke={PINK} strokeWidth="1.5" strokeDasharray="2.4 1.6" />}
      {kind === "period-possible" && <circle cx="6" cy="6" r="4.2" fill="none" stroke={PINK} strokeWidth="1.8" strokeDasharray="0.1 2.6" strokeLinecap="round" />}
      {kind === "fertile-predicted" && <path d="M6 1l4.5 5L6 11 1.5 6z" fill={MINT} />}
      {kind === "fertile-possible" && <path d="M6 1.8l3.8 4.2L6 10.2 2.2 6z" fill="none" stroke={MINT} strokeWidth="1.4" />}
      {kind === "ovulation-predicted" && <path d={STAR} fill="none" stroke={SUN} strokeWidth="1.2" strokeLinejoin="round" />}
      {kind === "ovulation-confirmed" && <path d={STAR} fill={SUN} stroke={SUN} strokeWidth="0.6" strokeLinejoin="round" />}
      {kind === "log" && <circle cx="6" cy="6" r="2.2" fill={INK} />}
    </>
  );
}

export function Marker({ kind, size = 12 }: { kind: MarkerKind; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 12 12" aria-hidden="true" focusable="false" className="shrink-0">
      <MarkerShapes kind={kind} />
    </svg>
  );
}
