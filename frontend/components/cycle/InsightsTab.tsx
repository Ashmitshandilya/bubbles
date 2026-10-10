"use client";

import { BubblesMascot } from "../BubblesMascot";
import { PILL, useBubblesQuery } from "../hub/HubKit";
import { withToday } from "../../app/lib/cycle-api";
import { PHASE_LABEL } from "../../app/lib/cycle-format";
import { phaseSymptomHint } from "../../app/lib/cycle-today";
import type { InsightMetric, InsightsResponse, SymptomByPhase } from "../../app/lib/cycle-types";
import { useCycle, useReloadOnRev } from "./CycleStore";
import { Card, Notice, PanelError, PanelSkeleton, TabHeading } from "./shared";

const PATTERN_NOTE = "These are patterns in your logs, not causes. Many things affect how you feel, so talk to a clinician if something worries you.";

export function InsightsTab() {
  const { today, rev, overview } = useCycle();
  const [query, reload] = useBubblesQuery<InsightsResponse>(withToday("/cycle/insights", today));
  useReloadOnRev(reload, rev);

  if (query.status === "loading") return <PanelSkeleton rows={3} />;
  if (query.status === "error") return <PanelError title="Insights didn't load" message={query.message} onRetry={reload} />;
  const d = query.data;
  const hint = d.ready ? phaseSymptomHint(d.symptoms, overview?.phase?.id ?? null) : null;

  return (
    <div className="space-y-5">
      <TabHeading id="cycle-h-insights" title="Insights">How you tend to feel across the phases of your cycle.</TabHeading>

      {!d.ready ? (
        <Card className="text-center">
          <BubblesMascot size={96} mood="thinking" className="mx-auto" />
          <h3 className="m-0 mt-3 font-display text-h3 text-ink">Bubbles is still learning</h3>
          <p className="mx-auto mb-0 mt-2 max-w-md text-body text-muted">{d.message}</p>
          <div className="mx-auto mt-4 max-w-xs">
            <progress value={Math.min(d.cycles_used, d.min_cycles)} max={d.min_cycles} aria-label="Cycles logged toward your first insights" className="h-3 w-full accent-[var(--bubbles-grape)]" />
            <p className="m-0 mt-1 text-body-sm font-bold text-ink-soft">{Math.min(d.cycles_used, d.min_cycles)} of {d.min_cycles} cycles logged</p>
          </div>
        </Card>
      ) : (
        <>
          <div className="grid gap-5 md:grid-cols-2">
            {d.metrics.map((m) => <MetricCard key={m.id} m={m} />)}
          </div>
          {hint && <Notice tone="grape" title="Right now">{hint}{overview?.phase?.estimated ? " Your phase is an estimate." : ""}</Notice>}
          {d.symptoms.length > 0 && (
            <Card labelledBy="cycle-symptoms-title">
              <h3 id="cycle-symptoms-title" className="m-0 font-display text-h3 text-ink">Symptoms by phase</h3>
              <ul className="m-0 mt-3 list-none space-y-4 p-0">
                {d.symptoms.map((s) => <SymptomRow key={s.id} s={s} />)}
              </ul>
            </Card>
          )}
          {d.notes.length > 0 && (
            <ul className="m-0 list-none space-y-2 p-0">{d.notes.map((n) => <li key={n}><Notice tone="grape">{n}</Notice></li>)}</ul>
          )}
        </>
      )}

      <Notice tone="sky" title="Please remember">{PATTERN_NOTE} {d.disclaimer}</Notice>
    </div>
  );
}

function MetricCard({ m }: { m: InsightMetric }) {
  const means = m.per_phase.map((p) => p.mean).filter((v): v is number => v !== null);
  const top = Math.max(...means, 0.0001);
  return (
    <Card labelledBy={`metric-${m.id}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 id={`metric-${m.id}`} className="m-0 font-display text-h3 text-ink">{m.label}</h3>
        {m.confidence && <span className={`${PILL} bg-tint-grape text-bubbles-grape-deep`}>{m.confidence === "moderate" ? "Moderate confidence" : "Low confidence"}</span>}
      </div>
      <p className="m-0 mt-0.5 text-body-sm text-muted">From {m.source}</p>
      {!m.ready ? (
        <p className="m-0 mt-3 text-body text-muted">{m.needs ?? "Not enough data yet."}</p>
      ) : (
        <>
          {m.summary && <p className="m-0 mt-3 text-body font-bold text-ink">{m.summary}</p>}
          <ul className="m-0 mt-3 list-none space-y-2 p-0">
            {m.per_phase.map((p) => (
              <li key={p.phase} className="grid grid-cols-[6.5rem_1fr_auto] items-center gap-2 text-body-sm">
                <span className="font-extrabold text-ink">{PHASE_LABEL[p.phase]}</span>
                <span className="h-3 rounded-full bg-blush" aria-hidden="true">
                  {p.mean !== null && <span className="block h-3 rounded-full bg-bubbles-grape" style={{ width: `${Math.max(4, (p.mean / top) * 100)}%` }} />}
                </span>
                <span className="font-bold text-ink-soft">{p.mean === null ? "not enough data" : `${p.mean.toFixed(1)}${m.unit ? ` ${m.unit}` : ""}`}</span>
              </li>
            ))}
          </ul>
          <p className="m-0 mt-2 text-[0.8125rem] text-muted">Bars are drawn relative to the highest phase. Numbers are averages of your logged days.</p>
        </>
      )}
    </Card>
  );
}

function SymptomRow({ s }: { s: SymptomByPhase }) {
  return (
    <li>
      <p className="m-0 text-body font-extrabold text-ink">
        {s.label} <span className="font-semibold text-muted">· {s.total_days} {s.total_days === 1 ? "day" : "days"} logged</span>
      </p>
      {s.most_common_phase && <p className="m-0 text-body-sm text-muted">Logged most often in the {PHASE_LABEL[s.most_common_phase].toLowerCase()} phase.</p>}
      <ul className="m-0 mt-1 flex list-none flex-wrap gap-2 p-0">
        {s.per_phase.map((p) => (
          <li key={p.phase} className={`${PILL} bg-blush text-ink-soft border border-line`}>
            {PHASE_LABEL[p.phase]} {p.days} {p.days === 1 ? "day" : "days"} ({Math.round(p.share <= 1 ? p.share * 100 : p.share)}%)
          </li>
        ))}
      </ul>
    </li>
  );
}
