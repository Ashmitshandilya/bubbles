// Timing for the breathing guide. Pure: the component only turns elapsed seconds into text and (when motion is allowed) a circle size.

export type PhaseName = "inhale" | "hold" | "exhale" | "hold_empty";

export interface Phase {
  name: PhaseName;
  /** What to tell the person to do. */
  label: string;
  seconds: number;
}

const ORDER: PhaseName[] = ["inhale", "hold", "exhale", "hold_empty"];
const LABEL: Record<PhaseName, string> = { inhale: "Breathe in", hold: "Hold gently", exhale: "Breathe out", hold_empty: "Rest" };

/** Phases in order from an exercise `pattern` ({inhale: 4, hold: 4, exhale: 4, hold_empty: 4}). Missing or invalid parts are skipped. */
export function phasesOf(pattern: Partial<Record<PhaseName, number>> | null | undefined): Phase[] {
  if (!pattern) return [];
  return ORDER.flatMap((name) => {
    const seconds = pattern[name];
    return typeof seconds === "number" && Number.isFinite(seconds) && seconds > 0 ? [{ name, label: LABEL[name], seconds }] : [];
  });
}

export function cycleSeconds(phases: Phase[]): number {
  return phases.reduce((sum, p) => sum + p.seconds, 0);
}

export interface PhaseState {
  phase: Phase;
  index: number;
  /** Whole seconds left in this phase, counting down to 1. */
  secondsLeft: number;
  /** 0 = lungs empty, 1 = full. Eases linearly through inhale and exhale. */
  fill: number;
  /** Completed full cycles so far. */
  cycle: number;
}

/** Where the guide is `elapsed` seconds in. Empty phases give null. */
export function phaseAt(phases: Phase[], elapsed: number): PhaseState | null {
  const total = cycleSeconds(phases);
  if (phases.length === 0 || total <= 0) return null;
  const t = Math.max(0, Number.isFinite(elapsed) ? elapsed : 0);
  const cycle = Math.floor(t / total);
  let within = t - cycle * total;
  for (let index = 0; index < phases.length; index += 1) {
    const phase = phases[index];
    if (within < phase.seconds || index === phases.length - 1) {
      const progress = Math.min(1, within / phase.seconds);
      const fill = phase.name === "inhale" ? progress : phase.name === "exhale" ? 1 - progress : phase.name === "hold" ? 1 : 0;
      return { phase, index, secondsLeft: Math.max(1, Math.ceil(phase.seconds - within)), fill, cycle };
    }
    within -= phase.seconds;
  }
  return null;
}

/** "Breathe in for 4, hold gently for 4, ..." for the text-only (reduced motion) description. */
export function patternSentence(phases: Phase[]): string {
  return phases.map((p) => `${p.label.toLowerCase()} for ${p.seconds}`).join(", then ");
}
