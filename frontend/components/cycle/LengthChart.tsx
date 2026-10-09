// Cycle-length history as inline SVG bars with the typical 21-35 day band shaded. The figure has a text alternative:
// a caption sentence plus a visually hidden table.

import { lengthChart, NORMAL_MAX, NORMAL_MIN } from "../../app/lib/cycle-chart";
import { lengthsSentence } from "../../app/lib/cycle-format";

export function LengthChart({ lengths, average }: { lengths: number[]; average: number | null }) {
  const g = lengthChart(lengths);
  const shown = lengths.slice(-12);
  return (
    <figure className="m-0">
      <svg viewBox={`0 0 ${g.width} ${g.height}`} className="block w-full max-w-xl" role="img" aria-labelledby="cycle-length-cap" focusable="false">
        <rect x={g.left} y={g.band.y} width={g.right - g.left} height={g.band.height} fill="var(--tint-mint)" />
        <text x={g.right - 2} y={g.band.y + 11} textAnchor="end" fontSize="10" fontWeight="800" fill="var(--bubbles-mint-deep)">typical {NORMAL_MIN} to {NORMAL_MAX} days</text>
        {g.ticks.map((t) => (
          <g key={t.value}>
            <line x1={g.left} x2={g.right} y1={t.y} y2={t.y} stroke="var(--bubbles-line)" strokeWidth="1" />
            <text x={g.left - 6} y={t.y + 3.5} textAnchor="end" fontSize="10" fontWeight="700" fill="var(--bubbles-ink-soft)">{t.value}</text>
          </g>
        ))}
        {g.bars.map((b) => (
          <g key={b.index}>
            <rect
              x={b.x} y={b.y} width={b.width} height={b.height} rx="4"
              fill={b.outside ? "var(--tint-sun)" : "var(--bubbles-grape)"}
              stroke={b.outside ? "var(--bubbles-sun-deep)" : "none"} strokeWidth="2" strokeDasharray={b.outside ? "4 2" : undefined}
            />
            <text x={b.x + b.width / 2} y={b.y - 4} textAnchor="middle" fontSize="11" fontWeight="800" fill="var(--bubbles-ink)">{b.value}</text>
            <text x={b.x + b.width / 2} y={g.baseline + 14} textAnchor="middle" fontSize="10" fontWeight="700" fill="var(--bubbles-ink-soft)">{shown.length - b.index === 1 ? "latest" : `#${b.index + 1}`}</text>
          </g>
        ))}
        {average !== null && <text x={g.left} y={10} fontSize="10" fontWeight="700" fill="var(--bubbles-ink-soft)">average {average} days</text>}
      </svg>
      <figcaption id="cycle-length-cap" className="mt-2 text-body-sm text-muted">
        Cycle length in days, oldest to newest. Bars with a dashed outline fall outside the typical band; cycles vary, and one outlier is common.
        <span className="sr-only"> {lengthsSentence(lengths)}</span>
      </figcaption>
      <table className="sr-only">
        <caption>Cycle lengths in days, oldest first</caption>
        <thead><tr><th scope="col">Cycle</th><th scope="col">Length in days</th><th scope="col">Within 21 to 35</th></tr></thead>
        <tbody>
          {shown.map((v, i) => (
            <tr key={i}><td>{i + 1}</td><td>{v}</td><td>{v >= NORMAL_MIN && v <= NORMAL_MAX ? "yes" : "no"}</td></tr>
          ))}
        </tbody>
      </table>
    </figure>
  );
}
