// "Day N of about M" as an SVG arc. The words in the middle carry the meaning; the arc colour is only a hint.

import type { PhaseId } from "../../app/lib/cycle-types";

const STROKE: Record<PhaseId, string> = {
  menstrual: "var(--phase-period)",
  follicular: "var(--phase-follicular)",
  ovulatory: "var(--phase-ovulation)",
  luteal: "var(--phase-luteal)",
};

/** Phase dot colours for chips and legends (Tailwind needs the literal class names). */
export const PHASE_DOT: Record<PhaseId, string> = {
  menstrual: "bg-phase-period",
  follicular: "bg-phase-follicular",
  ovulatory: "bg-phase-ovulation",
  luteal: "bg-phase-luteal",
};

export function PhaseRing({ day, length, phase, phaseLabel, estimated }: { day: number; length: number; phase: PhaseId | null; phaseLabel: string | null; estimated: boolean }) {
  const size = 168;
  const r = 70;
  const c = 2 * Math.PI * r;
  const progress = Math.min(1, Math.max(0.02, day / Math.max(length, day)));
  const label = `Cycle day ${day}${phaseLabel ? `, ${phaseLabel}${estimated ? " (estimated)" : ""}` : ""}, of about ${length} days`;
  return (
    <svg role="img" aria-label={label} viewBox={`0 0 ${size} ${size}`} width={size} height={size} className="shrink-0">
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--tint-grape)" strokeWidth="12" />
      <circle
        cx={size / 2} cy={size / 2} r={r} fill="none" stroke={phase ? STROKE[phase] : "var(--bubbles-grape)"} strokeWidth="12"
        strokeLinecap="round" strokeDasharray={`${c * progress} ${c}`} transform={`rotate(-90 ${size / 2} ${size / 2})`}
      />
      <text x="50%" y="37%" textAnchor="middle" fontSize="11" fontWeight="500" fill="var(--bubbles-ink-soft)" style={{ fontFamily: "var(--font-mono)" }}>Cycle day</text>
      <text x="50%" y="60%" textAnchor="middle" fontSize="48" fontWeight="400" fill="var(--bubbles-ink)" style={{ fontFamily: "var(--font-display)" }}>{day}</text>
      {phaseLabel && <text x="50%" y="73%" textAnchor="middle" fontSize="12" fontWeight="600" fill="var(--bubbles-ink-soft)">{phaseLabel}</text>}
    </svg>
  );
}
