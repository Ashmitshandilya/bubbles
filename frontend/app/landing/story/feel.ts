/**
 * How each day of the example cycle felt (0 = heavier, 1 = bright), used by the
 * small "inner weather" sign in the cycle chapter. Example data only.
 */
export const FEEL = [
  0.48, 0.5, 0.54, 0.58, 0.63, 0.7, 0.76, 0.8, 0.84, 0.88, 0.9, 0.92, 0.9, 0.88,
  0.84, 0.8, 0.74, 0.7, 0.64, 0.58, 0.5, 0.44, 0.38, 0.32, 0.28, 0.3, 0.34, 0.4,
] as const;

export type FeelBand = "bright" | "steady" | "heavy";

/** Feel at a fractional day index (0..27.999), interpolated so the sign glides. */
export const feelAt = (d: number) => {
  const i = Math.max(0, Math.min(27, Math.floor(d)));
  const j = Math.min(27, i + 1);
  return FEEL[i] + (FEEL[j] - FEEL[i]) * (d - i);
};

export const feelBand = (m: number): FeelBand => (m > 0.72 ? "bright" : m < 0.45 ? "heavy" : "steady");
