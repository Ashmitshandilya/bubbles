// "Day N of about M" as an SVG arc. The words in the middle carry the meaning; the arc colour is only a hint.

import type { PhaseId } from "../../app/lib/cycle-types";

const STROKE: Record<PhaseId, string> = {
  menstrual: "var(--bubbles-pink-ink)",
  follicular: "var(--bubbles-mint-deep)",
  ovulatory: "var(--bubbles-sun-deep)",
  luteal: "var(--bubbles-grape)",
};

export function PhaseRing({ day, length, phase, phaseLabel, estimated }: { day: number; length: number; phase: PhaseId | null; phaseLabel: string | null; estimated: boolean }) {
  const size = 168;
  const r = 70;
  const c = 2 * Math.PI * r;
  const progress = Math.min(1, Math.max(0.02, day / Math.max(length, day)));
  const label = `Cycle day ${day}${phaseLabel ? `, ${phaseLabel} phase${estimated ? " (estimated)" : ""}` : ""}, of about ${length} days`;
  return (
    <svg role="img" aria-label={label} viewBox={`0 0 ${size} ${size}`} width={size} height={size} className="shrink-0">
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--tint-pink)" strokeWidth="14" />
      <circle
        cx={size / 2} cy={size / 2} r={r} fill="none" stroke={phase ? STROKE[phase] : "var(--bubbles-pink-ink)"} strokeWidth="14"
        strokeLinecap="round" strokeDasharray={`${c * progress} ${c}`} transform={`rotate(-90 ${size / 2} ${size / 2})`}
      />
      <text x="50%" y="38%" textAnchor="middle" fontSize="12" fontWeight="800" fill="var(--bubbles-ink-soft)">Cycle day</text>
      <text x="50%" y="58%" textAnchor="middle" fontSize="38" fontWeight="700" fill="var(--bubbles-ink)" style={{ fontFamily: "var(--font-display)" }}>{day}</text>
      {phaseLabel && <text x="50%" y="71%" textAnchor="middle" fontSize="12" fontWeight="800" fill="var(--bubbles-ink-soft)">{phaseLabel}</text>}
    </svg>
  );
}
