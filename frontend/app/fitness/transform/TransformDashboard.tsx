"use client";

import Link from "next/link";
import { useState } from "react";
import { BTN_PRIMARY, BTN_SECONDARY, ErrorCard, Skeleton, useBubblesQuery } from "../../../components/hub/HubKit";
import { MealCard } from "../../../components/fitness/MealCard";
import {
  BTN_GHOST, CheckRow, EstimateLabel, Field, INPUT, LiveMessage, NumField, ProgressRing, Section, Sheet, useSend,
} from "../../../components/fitness/ui";
import { fmt, formatWeight, ringFraction, ringWord, weightFromKg, weightToKg, type Units } from "../../lib/fitness-calc";
import { formatWhen } from "../../lib/dates";
import type { Checkin, TodayView, TransformPlan } from "../../lib/fitness-types";

const EVENT_WORDS: Record<string, string> = {
  started: "Plan started", paused: "Plan paused", resumed: "Plan resumed", checkin_applied: "Weekly check-in, change accepted",
  checkin_skipped: "Weekly check-in, kept as is", goal_changed: "Goal updated", finished: "Plan finished",
};

export function Dashboard({ plan, units, reload }: { plan: TransformPlan; units: Units; reload: () => void }) {
  return (
    <>
      <Summary plan={plan} units={units} />
      {plan.status === "paused" ? <Paused plan={plan} reload={reload} /> : (
        <>
          <Today />
          <CheckinFlow reload={reload} />
        </>
      )}
      <Controls plan={plan} units={units} reload={reload} />
      <Report units={units} />
      <HistoryList plan={plan} />
    </>
  );
}

function Summary({ plan, units }: { plan: TransformPlan; units: Units }) {
  return (
    <Section title="At a glance" aside={<EstimateLabel />}>
      <dl className="m-0 flex flex-col">
        <Stat label="Started" value={formatWhen(plan.start_date, true)} />
        <Stat label="From" value={formatWeight(plan.start_weight_kg, units)} />
        <Stat label="Target" value={formatWeight(plan.target_weight_kg, units)} />
        <Stat label="Daily estimate" value={`${fmt(plan.targets.kcal)} kcal`} />
      </dl>
      <p className="m-0 mt-3 text-body-sm text-muted">Week {plan.weeks_on_plan + 1} of your plan. Close is good enough, and pausing is normal.</p>
    </Section>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-wrap items-baseline justify-between gap-x-4 border-b border-[color:var(--hairline)] py-3">
      <dt className="text-label font-extrabold uppercase tracking-wide text-subtle">{label}</dt>
      <dd className="m-0 font-display text-h4 text-ink">{value}</dd>
    </div>
  );
}

/* ── Paused: supportive, no mascot, no pressure ─────────────────────── */

function Paused({ plan, reload }: { plan: TransformPlan; reload: () => void }) {
  const send = useSend();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function resume() {
    setBusy(true);
    setError(null);
    const r = await send("/fitness/transform/resume", "POST", {});
    setBusy(false);
    if (r.ok) reload();
    else setError(r.message);
  }
  return (
    <Section title="Taking a break">
      <p className="m-0 text-body text-ink">Your plan is on pause. You haven&rsquo;t done anything wrong, and nothing is lost.{plan.paused?.safety ? " Bubbles paused it because something in your check-in suggested a rest would be wise." : ""}</p>
      {plan.paused?.safety && <p className="m-0 mt-2 text-body text-ink">Please consider talking to a doctor or dietitian before you restart. If you ever feel unwell, faint, or have chest pain, get medical help.</p>}
      <p className="m-0 mt-2 text-body-sm text-muted">When you are ready, Bubbles will ask a few quick safety questions again before the plan restarts. Some pauses have a short cooling-off period.</p>
      <div aria-live="polite" className="mt-3">{error && <p role="alert" className="m-0 rounded-2xl bg-tint-sky px-4 py-3 text-body-sm font-bold text-ink">{error}</p>}</div>
      <div className="mt-3"><button type="button" className={BTN_PRIMARY} onClick={() => void resume()} disabled={busy}>{busy ? "Checking…" : "Resume when I am ready"}</button></div>
    </Section>
  );
}

/* ── Today ──────────────────────────────────────────────────────────── */

function Today() {
  const [q, reload] = useBubblesQuery<TodayView>("/fitness/transform/today");
  if (q.status === "loading") return <Skeleton className="h-64 w-full rounded-3xl" />;
  if (q.status === "error") return <ErrorCard title="Couldn't load today" message={q.message} onRetry={reload} />;
  const { view, meals, good_day } = q.data;
  return (
    <>
      <Section title="Today" aside={<EstimateLabel />}>
        <div className="flex flex-col items-center gap-6 sm:flex-row sm:items-start">
          <ProgressRing fraction={ringFraction(view.budget.eaten_kcal, view.budget.budget_kcal)} label={`${fmt(view.budget.eaten_kcal)} of about ${fmt(view.budget.budget_kcal)} kilocalories today (estimate)`}>
            <span className="font-display text-metric text-ink">{fmt(view.budget.eaten_kcal)}</span>
            <span className="text-body-sm text-muted">of about {fmt(view.budget.budget_kcal)} kcal</span>
          </ProgressRing>
          <div className="w-full min-w-0 flex-1">
            <p className="m-0 font-extrabold text-ink" aria-live="polite">{ringWord(view.budget.eaten_kcal, view.budget.budget_kcal)}</p>
            <p className="m-0 mb-3 mt-1 text-body text-ink-soft">{view.message}</p>
            <Bars rows={[
              { label: "Protein", now: view.protein.eaten_g, goal: view.protein.target_g, unit: "g" },
              { label: "Water", now: view.water.drunk_ml / 1000, goal: (view.water.target_ml ?? 0) / 1000, unit: "L", digits: 1 },
              { label: "Steps", now: view.steps.done, goal: view.steps.target, unit: "" },
            ]} />
            <p className="m-0 mt-3 flex flex-wrap gap-2">
              <Link href="/fitness/calories" className={`${BTN_PRIMARY} no-underline`}>Log a meal</Link>
              <Link href="/hydration" className={`${BTN_SECONDARY} no-underline`}>Log water</Link>
            </p>
          </div>
        </div>
      </Section>
      {meals && (
        <Section title="Today's meals">
          <ul className="m-0 flex list-none flex-col gap-3 p-0">{meals.meals.map((m) => <li key={m.slot}><MealCard meal={m} compact /></li>)}</ul>
          <p className="m-0 mt-3 text-body-sm text-muted">Swap or shop for these on <Link href="/fitness/diet" className="font-extrabold text-bubbles-grape-deep">the Diet page</Link>.</p>
        </Section>
      )}
      <Section title="What a good day looks like">
        <ul className="m-0 list-disc pl-5 text-body-sm text-ink">{good_day.map((g) => <li key={g}>{g}</li>)}</ul>
      </Section>
    </>
  );
}

function Bars({ rows }: { rows: { label: string; now: number; goal: number; unit: string; digits?: number }[] }) {
  return (
    <ul className="m-0 flex list-none flex-col gap-3 p-0">
      {rows.map((r) => {
        const pct = r.goal > 0 ? Math.min(100, Math.round((r.now / r.goal) * 100)) : 0;
        const d = r.digits ?? 0;
        return (
          <li key={r.label}>
            <div className="mb-1 flex justify-between text-body-sm"><span className="font-extrabold text-ink">{r.label}</span><span className="text-muted">{r.now.toFixed(d)} of about {r.goal.toFixed(d)}{r.unit ? ` ${r.unit}` : ""}</span></div>
            <div role="meter" aria-label={r.label} aria-valuemin={0} aria-valuemax={r.goal || 100} aria-valuenow={Math.min(r.now, r.goal || 100)} className="h-3 overflow-hidden rounded-full bg-line">
              <div className="h-full rounded-full bg-bubbles-sky" style={{ width: `${pct}%` }} />
            </div>
          </li>
        );
      })}
    </ul>
  );
}

/* ── Weekly check-in ────────────────────────────────────────────────── */

function CheckinFlow({ reload }: { reload: () => void }) {
  const send = useSend();
  const [open, setOpen] = useState(false);
  const [symptoms, setSymptoms] = useState({ dizzy: false, fainting: false, palpitations: false, chest_pain: false });
  const [period, setPeriod] = useState(false);
  const [noteText, setNoteText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<Checkin | null>(null);
  const [done, setDone] = useState<string | null>(null);

  async function run() {
    setBusy(true);
    setError(null);
    const r = await send<Checkin>("/fitness/transform/checkin", "POST", { symptoms, in_luteal_or_period: period, note: noteText });
    setBusy(false);
    if (r.ok) setResult(r.data);
    else setError(r.message);
  }

  async function apply(accept: boolean) {
    setBusy(true);
    setError(null);
    const r = await send("/fitness/transform/checkin/apply", "POST", { accept });
    setBusy(false);
    if (r.ok) {
      setDone(accept ? "Done. Your new daily estimate is saved." : "Okay, Bubbles kept things as they are.");
      setResult(null);
      setOpen(false);
      reload();
    } else setError(r.message);
  }

  if (result) {
    if (result.decision === "pause") return <PauseResult result={result} reload={reload} />;
    return (
      <Section title="Your weekly check-in" aside={<EstimateLabel />}>
        <ul className="m-0 flex list-none flex-col gap-2 p-0">{result.messages.map((m) => <li key={m} className="text-body text-ink">{m}</li>)}</ul>
        {result.reasoning.length > 0 && <ul className="m-0 mt-3 list-disc pl-5 text-body-sm text-ink-soft">{result.reasoning.map((m) => <li key={m}>{m}</li>)}</ul>}
        {result.options.length > 0 && (
          <div className="mt-3 rounded-2xl bg-blush p-4">
            <p className="m-0 text-body-sm font-extrabold text-ink">Things you could try</p>
            <ul className="m-0 mt-1 list-disc pl-5 text-body-sm text-ink-soft">{result.options.map((m) => <li key={m}>{m}</li>)}</ul>
          </div>
        )}
        {result.decision === "adjust" && (
          <div className="mt-4 rounded-2xl bg-tint-sky p-4">
            <p className="m-0 text-body text-ink">Bubbles suggests changing your daily estimate by <strong>{result.change_kcal > 0 ? "+" : "−"}{Math.abs(result.change_kcal)} kcal</strong>, to about <strong>{fmt(result.new_kcal)} kcal</strong>. Nothing changes unless you say yes.</p>
            <div className="mt-3 flex flex-wrap gap-2">
              <button type="button" className={BTN_PRIMARY} disabled={busy} onClick={() => void apply(true)}>Accept the change</button>
              <button type="button" className={BTN_SECONDARY} disabled={busy} onClick={() => void apply(false)}>Keep my current numbers</button>
            </div>
          </div>
        )}
        {result.decision === "continue" && <div className="mt-4"><button type="button" className={BTN_PRIMARY} disabled={busy} onClick={() => void apply(false)}>Got it</button></div>}
        {result.decision === "insufficient_data" && <div className="mt-4"><button type="button" className={BTN_SECONDARY} onClick={() => setResult(null)}>Close</button></div>}
        <div aria-live="polite">{error && <p role="alert" className="m-0 mt-2 text-body-sm font-bold text-bubbles-pink-deep">{error}</p>}</div>
      </Section>
    );
  }

  return (
    <Section title="Weekly check-in">
      {done && <LiveMessage message={done} />}
      {!open ? (
        <>
          <p className="m-0 text-body-sm text-muted">Once a week Bubbles looks at your weight trend and logging, then suggests small changes only if they help. You decide.</p>
          <div className="mt-3"><button type="button" className={BTN_PRIMARY} onClick={() => { setOpen(true); setDone(null); }}>Start my check-in</button></div>
        </>
      ) : (
        <form noValidate onSubmit={(e) => { e.preventDefault(); void run(); }} className="flex flex-col gap-4">
          <fieldset className="m-0 min-w-0 border-0 p-0">
            <legend className="mb-1 p-0 text-body font-extrabold text-ink">Have you had any of these this week?</legend>
            <CheckRow id="s-dizzy" checked={symptoms.dizzy} onChange={(v) => setSymptoms({ ...symptoms, dizzy: v })}>Dizziness</CheckRow>
            <CheckRow id="s-faint" checked={symptoms.fainting} onChange={(v) => setSymptoms({ ...symptoms, fainting: v })}>Fainting</CheckRow>
            <CheckRow id="s-palp" checked={symptoms.palpitations} onChange={(v) => setSymptoms({ ...symptoms, palpitations: v })}>A racing heartbeat that does not settle</CheckRow>
            <CheckRow id="s-chest" checked={symptoms.chest_pain} onChange={(v) => setSymptoms({ ...symptoms, chest_pain: v })}>Chest pain</CheckRow>
          </fieldset>
          <CheckRow id="s-period" checked={period} onChange={setPeriod}>I am around my period (weight can hold extra water)</CheckRow>
          <Field id="s-note" label="Anything you want Bubbles to know?" optional hint="How food and moving have felt this week.">
            <textarea id="s-note" rows={3} maxLength={1000} value={noteText} onChange={(e) => setNoteText(e.target.value)} className={INPUT} />
          </Field>
          <div aria-live="polite">{error && <p role="alert" className="m-0 rounded-2xl bg-tint-pink px-4 py-3 text-body-sm font-bold text-bubbles-pink-deep">{error}</p>}</div>
          <div className="flex flex-wrap gap-2">
            <button type="submit" className={BTN_PRIMARY} disabled={busy}>{busy ? "Looking…" : "See my check-in"}</button>
            <button type="button" className={BTN_SECONDARY} onClick={() => setOpen(false)} disabled={busy}>Not now</button>
          </div>
        </form>
      )}
    </Section>
  );
}

function PauseResult({ result, reload }: { result: Checkin; reload: () => void }) {
  return (
    <section aria-labelledby="pause-title" className="rounded-3xl border border-bubbles-sky bg-tint-sky p-5 sm:p-6">
      <h2 id="pause-title" className="m-0 font-display text-h3 text-ink">Bubbles has paused your plan</h2>
      <ul className="m-0 mt-2 flex list-none flex-col gap-2 p-0">{result.messages.map((m) => <li key={m} className="text-body text-ink">{m}</li>)}</ul>
      <p className="m-0 mt-3 text-body text-ink">Taking a pause is a sensible thing to do. Please talk to a doctor or dietitian about how you have been feeling before you restart. If you feel unwell right now, get medical help.</p>
      <p className="m-0 mt-2 text-body-sm text-ink-soft">Nothing here is a failure, and nothing is lost.</p>
      <div className="mt-4 flex flex-wrap gap-2">
        <button type="button" className={BTN_PRIMARY} onClick={reload}>Okay</button>
        <Link href="/care" className={`${BTN_SECONDARY} no-underline`}>Prepare to talk to a doctor</Link>
      </div>
    </section>
  );
}

/* ── Pause / finish / goal ──────────────────────────────────────────── */

function Controls({ plan, units, reload }: { plan: TransformPlan; units: Units; reload: () => void }) {
  const send = useSend();
  const [sheet, setSheet] = useState<"goal" | "finish" | "pause" | null>(null);
  const [target, setTarget] = useState(weightFromKg(plan.target_weight_kg, units));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const close = () => { setSheet(null); setError(null); };

  async function act(path: string, method: "POST" | "PUT", body?: unknown) {
    setBusy(true);
    setError(null);
    const r = await send(path, method, body);
    setBusy(false);
    if (r.ok) {
      close();
      reload();
    } else setError(r.message);
  }

  return (
    <Section title="Your plan">
      <div className="flex flex-wrap gap-2">
        {plan.status === "active" && <button type="button" className={BTN_SECONDARY} onClick={() => setSheet("pause")}>Pause</button>}
        <button type="button" className={BTN_SECONDARY} onClick={() => setSheet("goal")}>Edit my goal</button>
        <button type="button" className={BTN_SECONDARY} onClick={() => setSheet("finish")}>Finish this plan</button>
      </div>
      <Sheet open={sheet === "pause"} onClose={close} title="Pause your plan?">
        <p className="m-0 text-body text-ink">A pause is fine at any time: a holiday, a busy week, or just needing a rest. Your numbers stay safe and Bubbles asks a few quick questions when you restart.</p>
        {error && <p role="alert" className="m-0 text-body-sm font-bold text-bubbles-pink-deep">{error}</p>}
        <div className="flex gap-2"><button type="button" className={BTN_PRIMARY} disabled={busy} onClick={() => void act("/fitness/transform/pause", "POST", { reason: "paused by me" })}>{busy ? "Pausing…" : "Pause"}</button><button type="button" className={BTN_SECONDARY} onClick={close}>Keep going</button></div>
      </Sheet>
      <Sheet open={sheet === "finish"} onClose={close} title="Finish this plan?">
        <p className="m-0 text-body text-ink">Bubbles will ease your calories back to maintenance a little each week, so your body settles gently.</p>
        {error && <p role="alert" className="m-0 text-body-sm font-bold text-bubbles-pink-deep">{error}</p>}
        <div className="flex gap-2"><button type="button" className={BTN_PRIMARY} disabled={busy} onClick={() => void act("/fitness/transform/finish", "POST", {})}>{busy ? "Finishing…" : "Finish"}</button><button type="button" className={BTN_SECONDARY} onClick={close}>Not yet</button></div>
      </Sheet>
      <Sheet open={sheet === "goal"} onClose={close} title="Edit my goal">
        <NumField id="goal-target" label="Target weight" unit={units === "imperial" ? "lb" : "kg"} value={target} onChange={setTarget} hint="Bubbles checks the new goal is within a healthy range before saving it." />
        {error && <p role="alert" className="m-0 text-body-sm font-bold text-bubbles-pink-deep">{error}</p>}
        <div className="flex gap-2"><button type="button" className={BTN_PRIMARY} disabled={busy || !Number.isFinite(weightToKg(target, units))} onClick={() => void act("/fitness/transform/goal", "PUT", { target_weight_kg: weightToKg(target, units) })}>{busy ? "Saving…" : "Save goal"}</button><button type="button" className={BTN_SECONDARY} onClick={close}>Cancel</button></div>
      </Sheet>
    </Section>
  );
}

/* ── Doctor report (print) ──────────────────────────────────────────── */

interface Report { plan_started: string; status: string; start_weight_kg: number; target_weight_kg: number; latest_weight_kg: number | null; trend_weight_kg: number | null; avg_logged_kcal: number | null; days_logged: number; daily_target_kcal: number; history: { ts: string; event: string }[]; note: string }

const PRINT_CSS = `@media print {
  body * { visibility: hidden !important; }
  .print-report, .print-report * { visibility: visible !important; }
  .print-report { position: absolute; left: 0; top: 0; width: 100%; padding: 24px; background: #fff; color: #000; }
  .print-hide { display: none !important; }
}`;

function Report({ units }: { units: Units }) {
  const send = useSend();
  const [report, setReport] = useState<Report | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setBusy(true);
    setError(null);
    const r = await send<{ report: Report }>("/fitness/transform/report", "GET");
    setBusy(false);
    if (r.ok) setReport(r.data.report);
    else setError(r.message);
  }

  return (
    <Section title="Report for your doctor">
      <style>{PRINT_CSS}</style>
      {!report ? (
        <>
          <p className="m-0 text-body-sm text-muted">A one-page summary you can print or save as a PDF to show a doctor or dietitian.</p>
          <div className="mt-3"><button type="button" className={BTN_SECONDARY} onClick={() => void load()} disabled={busy}>{busy ? "Preparing…" : "Prepare the report"}</button></div>
          <div aria-live="polite">{error && <p role="alert" className="m-0 mt-2 text-body-sm font-bold text-bubbles-pink-deep">{error}</p>}</div>
        </>
      ) : (
        <div className="flex flex-col gap-3">
          <article className="print-report rounded-2xl border border-line p-4" aria-label="Doctor report">
            <h3 className="m-0 font-display text-h3">Bubbles plan summary</h3>
            <table className="mt-2 w-full border-collapse text-left text-body-sm">
              <tbody>
                {([
                  ["Plan started", formatWhen(report.plan_started, true)],
                  ["Status", report.status],
                  ["Starting weight", formatWeight(report.start_weight_kg, units)],
                  ["Latest weigh-in", formatWeight(report.latest_weight_kg, units)],
                  ["Smoothed trend", formatWeight(report.trend_weight_kg, units)],
                  ["Target weight", formatWeight(report.target_weight_kg, units)],
                  ["Daily calorie estimate", `${fmt(report.daily_target_kcal)} kcal`],
                  ["Average logged intake", report.avg_logged_kcal ? `${fmt(report.avg_logged_kcal)} kcal over ${report.days_logged} logged days (estimates)` : "Not enough logged days"],
                ] as const).map(([k, v]) => (
                  <tr key={k} className="border-t border-line"><th scope="row" className="py-1 pr-3 font-bold">{k}</th><td className="py-1">{v}</td></tr>
                ))}
              </tbody>
            </table>
            <h4 className="m-0 mt-3 text-body-sm font-extrabold">Events</h4>
            <ul className="m-0 list-disc pl-5 text-body-sm">{report.history.map((h) => <li key={h.ts}>{formatWhen(h.ts, true)}: {EVENT_WORDS[h.event] ?? h.event}</li>)}</ul>
            <p className="m-0 mt-3 text-body-sm">{report.note} Targets are general estimates pending clinician review.</p>
          </article>
          <div className="print-hide flex gap-2">
            <button type="button" className={BTN_PRIMARY} onClick={() => window.print()}>Print or save as PDF</button>
            <button type="button" className={BTN_GHOST} onClick={() => setReport(null)}>Close</button>
          </div>
        </div>
      )}
    </Section>
  );
}

function HistoryList({ plan }: { plan: TransformPlan }) {
  const rows = [...plan.history].reverse().slice(0, 20);
  return (
    <Section title="History">
      {rows.length === 0 ? <p className="m-0 text-body-sm text-muted">Nothing yet.</p> : (
        <ol className="m-0 flex list-none flex-col gap-1 p-0 text-body-sm">
          {rows.map((h) => <li key={h.ts + h.event} className="flex justify-between gap-3 rounded-xl bg-blush px-3 py-2"><span className="font-bold text-ink">{EVENT_WORDS[h.event] ?? h.event.replaceAll("_", " ")}</span><span className="text-muted">{formatWhen(h.ts, true)}</span></li>)}
        </ol>
      )}
    </Section>
  );
}
