// Geometry for the cycle-length bar chart (inline SVG, no chart library). Pure numbers in, rectangles out.

export const NORMAL_MIN = 21;
export const NORMAL_MAX = 35;

export interface ChartBar { index: number; value: number; x: number; y: number; width: number; height: number; outside: boolean }
export interface ChartGeometry {
  width: number; height: number; baseline: number; left: number; right: number;
  yMin: number; yMax: number;
  bars: ChartBar[];
  band: { y: number; height: number };
  ticks: Array<{ value: number; y: number }>;
}

/** Bars are drawn oldest to newest. The y-axis always spans the 21-35 band with some air around it. */
export function lengthChart(lengths: number[], width = 360, height = 190): ChartGeometry {
  const pad = { left: 34, right: 8, top: 18, bottom: 26 };
  const values = lengths.slice(-12);
  const yMin = Math.max(0, Math.min(NORMAL_MIN - 6, ...values.map((v) => v - 3)));
  const yMax = Math.max(NORMAL_MAX + 5, ...values.map((v) => v + 3));
  const plotH = height - pad.top - pad.bottom;
  const plotW = width - pad.left - pad.right;
  const y = (v: number) => pad.top + ((yMax - v) / (yMax - yMin)) * plotH;
  const slot = values.length ? plotW / values.length : plotW;
  const barW = Math.min(34, slot * 0.62);
  const baseline = pad.top + plotH;

  const bars = values.map((value, index) => ({
    index, value,
    x: pad.left + slot * index + (slot - barW) / 2,
    y: y(value),
    width: barW,
    height: Math.max(0, baseline - y(value)),
    outside: value < NORMAL_MIN || value > NORMAL_MAX,
  }));

  const step = yMax - yMin > 30 ? 10 : 5;
  const ticks: ChartGeometry["ticks"] = [];
  for (let v = Math.ceil(yMin / step) * step; v <= yMax; v += step) ticks.push({ value: v, y: y(v) });

  return {
    width, height, baseline, left: pad.left, right: width - pad.right, yMin, yMax, bars,
    band: { y: y(NORMAL_MAX), height: y(NORMAL_MIN) - y(NORMAL_MAX) },
    ticks,
  };
}
