"use client";

import { useState } from "react";
import { DateField } from "../../../components/tracking/kit";
import { BTN_PRIMARY, BTN_SECONDARY, ErrorCard, Skeleton, useBubblesQuery } from "../../../components/hub/HubKit";
import { ChoiceGroup, ClinicalNote, Disclaimer, FitnessPage, CheckRow, Notice, PageHeading, Section, SelectField, useSend } from "../../../components/fitness/ui";
import { todayISO } from "../../lib/fitness-calc";
import type { BodyResponse, WorkoutPlanDoc } from "../../lib/fitness-types";
import { PlanView } from "./WorkoutParts";

export function WorkoutsClient() {
  return (
    <FitnessPage title="Workouts">
      <Workouts />
    </FitnessPage>
  );
}

function Workouts() {
  const [plan, reloadPlan] = useBubblesQuery<WorkoutPlanDoc>("/fitness/workouts/plan");
  const [body, reloadBody] = useBubblesQuery<BodyResponse>("/profile/body");
  const [redo, setRedo] = useState(false);

  if (plan.status === "loading" || body.status === "loading")
    return (
      <div className="flex flex-col gap-4" role="status" aria-label="Loading your workouts">
        <Skeleton className="h-12 w-2/3 rounded-2xl" />
        <Skeleton className="h-64 w-full rounded-3xl" />
      </div>
    );
  if (plan.status === "error") return <ErrorCard title="Couldn't load your workouts" message={plan.message} onRetry={reloadPlan} />;
  if (body.status === "error") return <ErrorCard title="Couldn't load your details" message={body.message} onRetry={reloadBody} />;

  const doc = plan.data;
  const screen = doc.screen;
  const answered = screen && screen.mode !== "incomplete";
  const refresh = () => {
    setRedo(false);
    reloadPlan();
  };

  return (
    <div className="flex flex-col gap-5">
      <PageHeading kicker="Workouts" title="Move in a way that suits you" text="A short safety check first, then a weekly plan you can bend to your day." />
      <ClinicalNote review={body.data.review} />
      {!answered || redo ? (
        <Screening questions={body.data.parq_questions} initial={screen?.answers} onDone={refresh} onCancel={redo ? () => setRedo(false) : undefined} />
      ) : (
        <>
          {screen.mode === "clinician_first" && <ClinicianFirst doc={doc} hasClearance={Boolean(body.data.profile.clinician_clearance)} onChanged={refresh} />}
          {screen.mode !== "clinician_first" && screen.message && <Notice tone="mint" title="Safety check done"><span>{screen.message}</span></Notice>}
          <PlanSection doc={doc} reload={reloadPlan} profile={body.data} />
          <p className="m-0">
            <button type="button" className={BTN_SECONDARY} onClick={() => setRedo(true)}>Redo the safety questions</button>
          </p>
        </>
      )}
      <Disclaimer />
    </div>
  );
}

/* ── Pre-participation screen ───────────────────────────────────────── */

export function Screening({ questions, initial, onDone, onCancel }: {
  questions: BodyResponse["parq_questions"]; initial?: Record<string, boolean>; onDone: () => void; onCancel?: () => void;
}) {
  const send = useSend();
  const [answers, setAnswers] = useState<Record<string, boolean | undefined>>(initial ?? {});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const missing = questions.filter((q) => answers[q.key] === undefined);

  async function submit() {
    if (missing.length) {
      setError(`Please answer every question so Bubbles can keep your plan safe (${missing.length} left).`);
      return;
    }
    setBusy(true);
    setError(null);
    const r = await send("/fitness/workouts/screen", "POST", { answers });
    setBusy(false);
    if (r.ok) onDone();
    else setError(r.message);
  }

  return (
    <Section title="A few quick questions">
      <p className="m-0 mb-4 text-body-sm text-muted">These help keep movement safe for you. They are not a diagnosis, and a &ldquo;yes&rdquo; is never a problem, it just changes the plan.</p>
      <form noValidate onSubmit={(e) => { e.preventDefault(); void submit(); }} className="flex flex-col gap-4">
        {questions.map((q, n) => (
          <fieldset key={q.key} className="m-0 min-w-0 rounded-2xl border-2 border-line p-4">
            <legend className="px-1 text-body font-bold text-ink">{n + 1}. {q.text}</legend>
            <div className="mt-1 flex gap-3">
              {([true, false] as const).map((v) => (
                <label key={String(v)} className={`flex min-h-[44px] flex-1 cursor-pointer items-center justify-center gap-2 rounded-full border-2 px-4 text-body-sm font-extrabold ${answers[q.key] === v ? "border-bubbles-grape bg-tint-grape text-bubbles-grape-deep" : "border-line text-muted"}`}>
                  <input type="radio" name={`q-${q.key}`} checked={answers[q.key] === v} onChange={() => setAnswers({ ...answers, [q.key]: v })} className="h-5 w-5 accent-[var(--bubbles-grape)]" />
                  {v ? "Yes" : "No"}
                </label>
              ))}
            </div>
          </fieldset>
        ))}
        <div aria-live="polite">{error && <p role="alert" className="m-0 rounded-2xl bg-tint-pink px-4 py-3 text-body-sm font-bold text-bubbles-pink-deep">{error}</p>}</div>
        <div className="flex flex-wrap gap-2">
          <button type="submit" disabled={busy} className={BTN_PRIMARY}>{busy ? "Saving…" : "Continue"}</button>
          {onCancel && <button type="button" onClick={onCancel} className={BTN_SECONDARY}>Cancel</button>}
        </div>
      </form>
    </Section>
  );
}

function ClinicianFirst({ doc, hasClearance, onChanged }: { doc: WorkoutPlanDoc; hasClearance: boolean; onChanged: () => void }) {
  const send = useSend();
  const [ok, setOk] = useState(false);
  const [date, setDate] = useState(todayISO());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function record() {
    setBusy(true);
    setError(null);
    // Dated record on the profile, limited to exercise so it can never stand in for a Strict mode sign-off.
    // An existing record (which may cover Strict mode) is never overwritten.
    const a = hasClearance ? { ok: true as const, data: null } : await send("/profile/body", "PUT", { clinician_clearance: { cleared: true, date, areas: ["exercise"] } });
    const b = a.ok ? await send("/fitness/workouts/screen", "POST", { answers: doc.screen?.answers ?? {}, clinician_cleared: true }) : a;
    setBusy(false);
    if (b.ok) onChanged();
    else setError(b.message);
  }

  return (
    <Section title="Please talk to a clinician first">
      <p className="m-0 text-body text-ink">{doc.screen?.message}</p>
      <p className="m-0 mt-2 text-body-sm text-muted">Until then Bubbles only suggests easy walking and gentle stretching, which are below. Nothing here is a reason to worry, it just means a doctor should look at the full picture before you ramp up.</p>
      <div className="mt-4 rounded-2xl bg-blush p-4">
        <p className="m-0 mb-2 text-body-sm font-extrabold text-ink">Already checked with a doctor?</p>
        <CheckRow id="cleared" checked={ok} onChange={setOk}>A doctor has said I can start exercising</CheckRow>
        {ok && (
          <div className="mt-2 flex flex-col gap-3">
            <DateField id="cleared-date" label="Date they said so" value={date} onChange={setDate} max={todayISO()} />
            <div><button type="button" onClick={() => void record()} disabled={busy || !date} className={BTN_PRIMARY}>{busy ? "Saving…" : "Record this"}</button></div>
          </div>
        )}
        <div aria-live="polite">{error && <p role="alert" className="m-0 mt-2 text-body-sm font-bold text-bubbles-pink-deep">{error}</p>}</div>
      </div>
    </Section>
  );
}

/* ── Make or view the plan ──────────────────────────────────────────── */

function PlanSection({ doc, reload, profile }: { doc: WorkoutPlanDoc; reload: () => void; profile: BodyResponse }) {
  const [making, setMaking] = useState(false);
  if (!doc.exists || !doc.plan || making)
    return <MakePlan doc={doc} profile={profile} onDone={() => { setMaking(false); reload(); }} onCancel={doc.exists ? () => setMaking(false) : undefined} />;
  return <PlanView doc={doc} plan={doc.plan} reload={reload} onRemake={() => setMaking(true)} />;
}

function MakePlan({ doc, profile, onDone, onCancel }: { doc: WorkoutPlanDoc; profile: BodyResponse; onDone: () => void; onCancel?: () => void }) {
  const send = useSend();
  const p = (doc.params ?? {}) as { days_per_week?: number; minutes?: number; equipment?: unknown; level?: number };
  const [days, setDays] = useState(String(p.days_per_week ?? profile.profile.days_per_week ?? 3));
  const [minutes, setMinutes] = useState(String(p.minutes ?? 40));
  const [equipment, setEquipment] = useState(typeof p.equipment === "string" ? p.equipment : "none");
  const [level, setLevel] = useState(String(p.level ?? profile.profile.level ?? 1));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function make() {
    setBusy(true);
    setError(null);
    const r = await send("/fitness/workouts/plan", "POST", { days_per_week: Number(days), minutes: Number(minutes), equipment, level: Number(level) });
    setBusy(false);
    if (r.ok) onDone();
    else setError(r.message);
  }

  return (
    <Section title={doc.exists ? "Make a new plan" : "Build your first week"}>
      <form noValidate onSubmit={(e) => { e.preventDefault(); void make(); }} className="flex flex-col gap-5">
        <ChoiceGroup legend="Days a week" value={days} onChange={setDays} options={[1, 2, 3, 4, 5, 6].map((n) => ({ value: String(n), label: String(n) }))} hint="Three is a great start. Rest days are part of the plan." />
        <SelectField id="mins" label="Time per session" value={minutes} onChange={setMinutes} options={[20, 30, 40, 45, 60, 75].map((n) => ({ value: String(n), label: `${n} minutes` }))} />
        <ChoiceGroup legend="What can you use?" value={equipment} onChange={setEquipment} options={[{ value: "none", label: "Nothing" }, { value: "home", label: "Home basics" }, { value: "gym", label: "Gym" }, { value: "pool", label: "Pool" }]} />
        <ChoiceGroup legend="Where are you now?" value={level} onChange={setLevel} options={[{ value: "1", label: "Just starting" }, { value: "2", label: "Some experience" }, { value: "3", label: "Quite experienced" }]} />
        <div aria-live="polite">
          {error && <p role="alert" className="m-0 rounded-2xl bg-tint-pink px-4 py-3 text-body-sm font-bold text-bubbles-pink-deep">{error}</p>}
        </div>
        <div className="flex flex-wrap gap-2">
          <button type="submit" disabled={busy} className={BTN_PRIMARY}>{busy ? "Planning…" : "Make my plan"}</button>
          {onCancel && <button type="button" onClick={onCancel} className={BTN_SECONDARY}>Keep my current plan</button>}
        </div>
      </form>
    </Section>
  );
}
