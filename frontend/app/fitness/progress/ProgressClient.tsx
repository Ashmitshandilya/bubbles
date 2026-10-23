"use client";

import Link from "next/link";
import { useState } from "react";
import { BTN_PRIMARY, ErrorCard, Skeleton, useBubblesQuery } from "../../../components/hub/HubKit";
import { WeightTrendChart } from "../../../components/fitness/WeightTrendChart";
import { Disclaimer, EstimateLabel, FitnessPage, LiveMessage, NumField, Notice, PageHeading, ReviewNote, Section, Sheet, useSend } from "../../../components/fitness/ui";
import { useUnits } from "../../../components/fitness/useUnits";
import { formatRate, formatWeight } from "../../lib/fitness-calc";
import { formatWhen } from "../../lib/dates";
import type { Progress } from "../../lib/fitness-types";

export function ProgressClient() {
  return (
    <FitnessPage title="Progress">
      <ProgressView />
    </FitnessPage>
  );
}

const FIELDS = [
  { key: "waist_cm", label: "Waist" },
  { key: "hip_cm", label: "Hips" },
  { key: "chest_cm", label: "Chest" },
  { key: "arm_cm", label: "Arm" },
  { key: "thigh_cm", label: "Thigh" },
] as const;

function ProgressView() {
  const [q, reload] = useBubblesQuery<Progress>("/fitness/progress");
  const units = useUnits();
  const [open, setOpen] = useState(false);
  const [saved, setSaved] = useState<string | null>(null);

  if (q.status === "loading")
    return (
      <div className="flex flex-col gap-4" role="status" aria-label="Loading your progress">
        <Skeleton className="h-10 w-1/2 rounded-2xl" />
        <Skeleton className="h-72 w-full rounded-3xl" />
      </div>
    );
  if (q.status === "error") return <ErrorCard title="Couldn't load your progress" message={q.message} onRetry={reload} />;

  const p = q.data;
  const latest = p.weights.length ? p.weights[p.weights.length - 1].weight_kg : null;
  const trendNow = p.trend.length ? p.trend[p.trend.length - 1].trend_kg : null;
  return (
    <div className="flex flex-col gap-5">
      <PageHeading kicker="Progress" title="The bigger picture" text="One weigh-in is a snapshot. The trend line smooths out water, salt and timing, so it tells the truer story." />
      <ReviewNote />
      <ul className="m-0 flex list-none flex-col p-0" aria-label="Summary">
        <Tile label="Latest weigh-in" value={formatWeight(latest, units)} />
        <Tile label="Trend now" value={formatWeight(trendNow, units)} />
        <Tile label="Rate" value={formatRate(p.rate_kg_per_week, units)} note="over about two weeks" />
        <Tile label="Target" value={p.plan ? formatWeight(p.plan.target_weight_kg, units) : "Not set"} />
      </ul>

      <Section title="Weight trend" aside={<EstimateLabel>Trend</EstimateLabel>}>
        <WeightTrendChart weights={p.weights} trend={p.trend} units={units} />
        <p className="m-0 mt-3 text-body-sm text-muted">Add a weigh-in on the <Link href="/weight" className="font-extrabold text-bubbles-grape-deep">Weight page</Link>. Weighing weekly is plenty.</p>
        <Notice tone="sky"><span>{p.luteal_note}</span></Notice>
      </Section>

      <Section title="Consistency, not perfection">
        <p className="m-0 text-body text-ink">
          You logged food on <strong>{p.adherence.days_logged_28} of the last 28 days</strong>.
        </p>
        <div role="meter" aria-label="Days logged in the last 28" aria-valuemin={0} aria-valuemax={28} aria-valuenow={p.adherence.days_logged_28} className="mt-3 h-3 overflow-hidden rounded-full bg-line">
          <div className="h-full rounded-full bg-bubbles-mint" style={{ width: `${Math.round((p.adherence.days_logged_28 / 28) * 100)}%` }} />
        </div>
        <p className="m-0 mt-3 text-body-sm text-muted">Gaps are just gaps. Any logging helps Bubbles see the pattern, and a day you skipped is not a mistake.</p>
      </Section>

      <Section title="Measurements" aside={<button type="button" onClick={() => { setOpen(true); setSaved(null); }} className={BTN_PRIMARY}>Add measurements</button>}>
        <LiveMessage message={saved} />
        {p.measurements.length === 0 ? (
          <p className="m-0 text-body-sm text-muted">Tape measurements can show change when the scale doesn&rsquo;t move. Totally optional.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[28rem] border-collapse text-left text-body-sm">
              <caption className="sr-only">Body measurements by date, in centimetres</caption>
              <thead>
                <tr className="text-muted">
                  <th scope="col" className="py-2 pr-3">Date</th>
                  {FIELDS.map((f) => <th key={f.key} scope="col" className="py-2 pr-3">{f.label} (cm)</th>)}
                </tr>
              </thead>
              <tbody>
                {p.measurements.map((m) => (
                  <tr key={m.date} className="border-t border-line">
                    <th scope="row" className="py-2 pr-3 font-bold">{formatWhen(m.date, true)}</th>
                    {FIELDS.map((f) => <td key={f.key} className="py-2 pr-3">{m[f.key] ?? "—"}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>
      <MeasureSheet open={open} onClose={() => setOpen(false)} onSaved={() => { setSaved("Saved."); reload(); }} />
      <Disclaimer />
    </div>
  );
}

function Tile({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <li className="flex flex-wrap items-baseline justify-between gap-x-4 border-b border-[color:var(--hairline)] py-3">
      <p className="m-0 text-label font-extrabold uppercase tracking-wide text-subtle">{label}</p>
      <p className="m-0 font-display text-h3 text-ink">{value}</p>
      {note && <p className="m-0 w-full text-body-sm text-muted">{note}</p>}
    </li>
  );
}

function MeasureSheet({ open, onClose, onSaved }: { open: boolean; onClose: () => void; onSaved: () => void }) {
  const send = useSend();
  const [v, setV] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save() {
    const body: Record<string, number> = {};
    for (const f of FIELDS) if (v[f.key]?.trim()) body[f.key] = Number(v[f.key]);
    if (Object.keys(body).length === 0) {
      setError("Enter at least one measurement.");
      return;
    }
    setBusy(true);
    setError(null);
    const r = await send("/fitness/measurements", "POST", body);
    setBusy(false);
    if (r.ok) {
      setV({});
      onSaved();
      onClose();
    } else setError(r.message);
  }

  return (
    <Sheet open={open} onClose={onClose} title="Add measurements">
      <p className="m-0 text-body-sm text-muted">In centimetres, as many or as few as you like. Measure at the same spots each time.</p>
      <form noValidate onSubmit={(e) => { e.preventDefault(); void save(); }} className="flex flex-col gap-4">
        <div className="grid grid-cols-2 gap-3">
          {FIELDS.map((f) => <NumField key={f.key} id={`m-${f.key}`} label={f.label} unit="cm" optional min={10} max={300} value={v[f.key] ?? ""} onChange={(x) => setV({ ...v, [f.key]: x })} />)}
        </div>
        <div aria-live="polite">{error && <p role="alert" className="m-0 rounded-2xl bg-tint-pink px-4 py-3 text-body-sm font-bold text-bubbles-pink-deep">{error}</p>}</div>
        <button type="submit" disabled={busy} className={BTN_PRIMARY}>{busy ? "Saving…" : "Save"}</button>
      </form>
    </Sheet>
  );
}
