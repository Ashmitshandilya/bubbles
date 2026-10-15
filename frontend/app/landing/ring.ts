/**
 * Geometry of the example cycle ring in the "Patterns" chapter (pure, computed once at import, unit-tested).
 * A 28-day cycle runs clockwise from the top. Phase arcs sit on the glass band; sleep, mood and energy are
 * three threads inside it, one point per day. A day that was not logged is a gap in its thread, never a
 * guess: the path simply stops and starts again.
 */
import type { PHASE_ORDER } from "./atmosphere/palette";

const C = 280;
const R = 206;
const W = 34;
const DAYS = 28;

/** Angle (radians, 0 = top, clockwise) of the start of day `d` (1-based; fractions allowed). */
const angle = (d: number) => ((d - 1) / DAYS) * Math.PI * 2;
const at = (d: number, r: number): [number, number] => {
  const a = angle(d);
  return [C + r * Math.sin(a), C - r * Math.cos(a)];
};
const f = (v: number) => Math.round(v * 10) / 10;

function arc(from: number, to: number, r: number) {
  const [x0, y0] = at(from, r);
  const [x1, y1] = at(to, r);
  const large = angle(to) - angle(from) > Math.PI ? 1 : 0;
  return `M${f(x0)} ${f(y0)} A${r} ${r} 0 ${large} 1 ${f(x1)} ${f(y1)}`;
}

type PhaseKey = (typeof PHASE_ORDER)[number];
const PHASES: Array<{ key: PhaseKey; name: string; from: number; to: number }> = [
  { key: "period", name: "Period", from: 1, to: 6 },
  { key: "follicular", name: "Follicular", from: 6, to: 14 },
  { key: "ovulation", name: "Ovulation (estimate)", from: 14, to: 17 },
  { key: "luteal", name: "Luteal", from: 17, to: 29 },
];

const GAP = 0.18; // days of air between neighbouring phase arcs

export const RING = {
  c: C,
  r: R,
  w: W,
  phases: PHASES.map((p) => {
    const mid = (p.from + p.to) / 2;
    const [lx, ly] = at(mid, R + W / 2 + 30);
    const side = Math.sin(angle(mid));
    return {
      key: p.key,
      name: p.name,
      arc: arc(p.from + GAP, p.to - GAP, R),
      dot: at(p.from + GAP, R),
      label: [f(lx), f(ly)] as const,
      anchor: (Math.abs(side) < 0.25 ? "middle" : side > 0 ? "start" : "end") as "middle" | "start" | "end",
    };
  }),
  /** the three days before the next period (days 26 to 28): a soft wedge behind the threads */
  dip: (() => {
    const [a0, b0] = at(26, R - W / 2 - 4);
    const [a1, b1] = at(29, R - W / 2 - 4);
    const [c1, d1] = at(29, 70);
    const [c0, d0] = at(26, 70);
    const r0 = R - W / 2 - 4;
    return `M${f(a0)} ${f(b0)} A${r0} ${r0} 0 0 1 ${f(a1)} ${f(b1)} L${f(c1)} ${f(d1)} A70 70 0 0 0 ${f(c0)} ${f(d0)} Z`;
  })(),
};

/** Example values, one per day (null = not logged). Higher means more sleep, better mood, more energy. */
const SERIES = {
  sleep: [7.2, 6.8, 7.0, 7.4, 7.5, 7.3, 7.6, 7.4, 7.7, 7.5, 7.6, 7.4, 7.3, 7.5, 7.2, 7.0, 7.1, 6.9, 7.0, 6.8, 6.9, 6.7, 6.8, 6.7, 6.6, 6.3, 6.2, 6.4],
  mood: [3, 3, 3.5, 4, 4, 4, 4.5, 4, null, null, 4, 4.5, 4.5, 4, 4, 3.5, 4, 3.5, 3.5, 3.5, 3, 3.5, 3, 3, 3, 2.5, 2.5, 3],
  energy: [2.5, 2.5, 3, 3.5, 4, 4, 4.5, 4.5, 4.5, 4, 4.5, 4.5, 4, 4, 4, 3.5, 3.5, 3.5, 3.5, 3, 3.5, 3, 3, 3, 3, 2, 2, 2],
} as const;

/** Inner radius of each thread's band and how far a value swings it. */
const BANDS = { sleep: { base: 160, swing: 22, lo: 6, hi: 8 }, mood: { base: 128, swing: 20, lo: 1, hi: 5 }, energy: { base: 96, swing: 20, lo: 1, hi: 5 } } as const;

/** Smooth path through points (Catmull-Rom as cubic Beziers); `closed` joins the last point to the first. */
export function smoothPath(pts: Array<[number, number]>, closed: boolean): string {
  const n = pts.length;
  if (n < 2) return "";
  const p = (i: number) => (closed ? pts[(i + n) % n] : pts[Math.max(0, Math.min(n - 1, i))]);
  let d = `M${f(pts[0][0])} ${f(pts[0][1])}`;
  const last = closed ? n : n - 1;
  for (let i = 0; i < last; i += 1) {
    const [x0, y0] = p(i - 1);
    const [x1, y1] = p(i);
    const [x2, y2] = p(i + 1);
    const [x3, y3] = p(i + 2);
    d += ` C${f(x1 + (x2 - x0) / 6)} ${f(y1 + (y2 - y0) / 6)} ${f(x2 - (x3 - x1) / 6)} ${f(y2 - (y3 - y1) / 6)} ${f(x2)} ${f(y2)}`;
  }
  return closed ? `${d} Z` : d;
}

/** A thread's paths: one closed loop when every day is logged, otherwise one open run per logged stretch. */
export function threadPaths(values: ReadonlyArray<number | null>, band: { base: number; swing: number; lo: number; hi: number }): string[] {
  const pt = (v: number, day: number) => at(day + 0.5, band.base + ((v - band.lo) / (band.hi - band.lo) - 0.5) * 2 * band.swing);
  if (values.every((v) => v !== null)) return [smoothPath(values.map((v, i) => pt(v as number, i + 1)), true)];
  // Rotate so the list starts right after a gap, then split at every gap.
  const n = values.length;
  const start = (values.findIndex((v) => v === null) + 1) % n;
  const runs: Array<Array<[number, number]>> = [];
  let run: Array<[number, number]> = [];
  for (let k = 0; k < n; k += 1) {
    const i = (start + k) % n;
    const v = values[i];
    if (v === null) {
      if (run.length) runs.push(run);
      run = [];
    } else run.push(pt(v, i + 1));
  }
  if (run.length) runs.push(run);
  return runs.filter((r) => r.length > 1).map((r) => smoothPath(r, false));
}

export const THREADS = (["sleep", "mood", "energy"] as const).map((key) => ({
  key,
  label: key === "sleep" ? "Sleep" : key === "mood" ? "Mood" : "Energy",
  paths: threadPaths(SERIES[key], BANDS[key]),
}));
