"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { DateField } from "../../../components/tracking/kit";
import { BTN_PRIMARY, BTN_SECONDARY, CARD, ErrorCard, Skeleton, useBubblesQuery } from "../../../components/hub/HubKit";
import { MealCard } from "../../../components/fitness/MealCard";
import { StepperShell } from "../../../components/fitness/StepperShell";
import {
  CheckRow, ChoiceGroup, ClinicalNote, ConsentCard, EstimateLabel, Field, MacroBars, NumField, Notice, SelectField, TagInput, useSend,
} from "../../../components/fitness/ui";
import {
  PACE_DEFAULT, PACE_MAX, PACE_MIN, clampPace, fmt, formatWeeks, formatWeight, paceKgPerWeek, paceWeeksRange, todayISO, weightFromKg, weightToKg, type Units,
} from "../../lib/fitness-calc";
import type { BodyResponse, PreviewResponse, ScreenResponse, Screening, WorkoutPlanDoc } from "../../lib/fitness-types";
import { Screening as ExerciseScreening } from "../workouts/WorkoutsClient";

const STEPS = ["Safety check", "Goal", "Foods", "Movement", "Review", "Commit"];
const DIET = [
  { value: "", label: "No particular style" }, { value: "vegetarian", label: "Vegetarian" }, { value: "vegan", label: "Vegan" },
  { value: "eggetarian", label: "Eggetarian" }, { value: "jain", label: "Jain" }, { value: "non-vegetarian", label: "Non-vegetarian" }, { value: "halal", label: "Halal" },
];

export function TransformStepper({ onStarted }: { onStarted: () => void }) {
  const [body, reloadBody] = useBubblesQuery<BodyResponse>("/profile/body");
  if (body.status === "loading") return <div role="status" aria-label="Loading"><Skeleton className="mx-auto h-72 w-full max-w-2xl rounded-3xl" /></div>;
  if (body.status === "error") return <ErrorCard title="Couldn't load your details" message={body.message} onRetry={reloadBody} />;
  return <Flow body={body.data} onStarted={onStarted} />;
}

function Flow({ body, onStarted }: { body: BodyResponse; onStarted: () => void }) {
  const send = useSend();
  const units: Units = body.profile.units === "imperial" ? "imperial" : "metric";
  const [step, setStep] = useState(0);
  const [booting, setBooting] = useState(true);
  const [screening, setScreening] = useState<Screening | null>(null);
  const [detailsNeeded, setDetailsNeeded] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Goal / foods / movement answers
  const currentKg = body.known.latest_weight_kg ?? body.profile.weight_kg ?? 0;
  const [target, setTarget] = useState(weightFromKg(body.profile.target_weight_kg, units));
  const [pace, setPace] = useState(PACE_DEFAULT);
  const [foods, setFoods] = useState<string[]>([]);
  const [likes, setLikes] = useState<string[]>(body.profile.likes ?? []);
  const [dislikes, setDislikes] = useState<string[]>(body.profile.dislikes ?? []);
  const [diet, setDiet] = useState(body.profile.diet_style ?? "");
  const [meals, setMeals] = useState("4");
  const [equipment, setEquipment] = useState("none");
  const [days, setDays] = useState("4");
  const [minutes, setMinutes] = useState("40");
  const [level, setLevel] = useState("1");
  const [preview, setPreview] = useState<PreviewResponse | null>(null);
  const [agree, setAgree] = useState(false);

  const targetKg = weightToKg(target, units);
  const selections = {
    foods, likes, dislikes, diet_style: diet || undefined, meals_per_day: Number(meals), equipment, days_per_week: Number(days), session_minutes: Number(minutes), level: Number(level), pace_pct_per_week: pace,
  };

  // Resume: the server remembers a finished safety check, so that step is skipped when it was answered and passed.
  useEffect(() => {
    let live = true;
    void send<ScreenResponse>("/fitness/transform/screen", "POST", {}).then((r) => {
      if (!live) return;
      if (r.ok) {
        setScreening(r.data);
        if (r.data.decision === "allowed" || r.data.decision === "allowed_with_cautions") setStep(1);
      } else if (/^add your/i.test(r.message)) setDetailsNeeded(r.message);
      else setError(r.message);
      setBooting(false);
    });
    return () => { live = false; };
  }, [send]);

  if (booting) return <div role="status" aria-label="Checking where you left off"><Skeleton className="mx-auto h-72 w-full max-w-2xl rounded-3xl" /></div>;

  if (detailsNeeded)
    return (
      <StepperShell steps={STEPS} index={0} title="First, a few details" lead="Strict mode needs your age, height and weight so the numbers can be safe." hideNext>
        <p className="m-0 text-body text-ink">{detailsNeeded}</p>
        <Link href="/fitness/setup" className={`${BTN_PRIMARY} self-start no-underline`}>Add my details</Link>
      </StepperShell>
    );

  const targetBlock = (() => {
    if (!Number.isFinite(targetKg)) return "Add the weight you are aiming for.";
    if (currentKg && targetKg >= currentKg) return "Strict mode is for gentle weight loss, so the target needs to be below your weight now. For anything else, the diet and workout planners are a better fit.";
    return null;
  })();

  /** Re-run the server-side check with the answers it already holds (after a clearance is recorded). */
  async function rescreen() {
    const r = await send<ScreenResponse>("/fitness/transform/screen", "POST", Number.isFinite(targetKg) ? { target_weight_kg: targetKg } : {});
    if (!r.ok) return setError(r.message);
    setScreening(r.data);
    if (r.data.decision === "allowed" || r.data.decision === "allowed_with_cautions") setStep((s) => Math.max(s, 1));
  }

  async function continueGoal() {
    setBusy(true);
    setError(null);
    const put = await send("/profile/body", "PUT", { target_weight_kg: targetKg });
    if (!put.ok) {
      setBusy(false);
      setError(put.message);
      return;
    }
    const r = await send<ScreenResponse>("/fitness/transform/screen", "POST", { target_weight_kg: targetKg });
    setBusy(false);
    if (!r.ok) {
      setError(r.message);
      return;
    }
    setScreening(r.data);
    if (r.data.decision === "allowed" || r.data.decision === "allowed_with_cautions") setStep(2);
  }

  async function loadPreview() {
    setBusy(true);
    setError(null);
    const r = await send<PreviewResponse>("/fitness/transform/preview", "POST", { target_weight_kg: targetKg, selections });
    setBusy(false);
    if (!r.ok) {
      setError(r.message);
      return;
    }
    setPreview(r.data);
    setScreening({ ...(screening ?? ({} as Screening)), ...r.data.screening });
    if (r.data.preview) setStep(4);
  }

  async function start() {
    setBusy(true);
    setError(null);
    const r = await send("/fitness/transform/start", "POST", { target_weight_kg: targetKg, acknowledged: true, selections });
    setBusy(false);
    if (r.ok) onStarted();
    else setError(r.message);
  }

  // Refusals are shown kindly, on whichever step found them.
  if (screening && screening.decision === "refused")
    return (
      <StepperShell steps={STEPS} index={step} title="Strict mode isn't the right fit right now" lead="This is about keeping you safe, not a judgement. Here is why, and what can help instead." hideNext>
        <Refusal
          screening={screening}
          onRecorded={() => void rescreen()}
          onRedo={() => { setScreening(null); setStep(0); }}
        />
      </StepperShell>
    );

  if (step === 0)
    return (
      <SafetyStep
        questions={body.scoff_questions}
        busy={busy}
        error={error}
        incomplete={screening?.decision === "incomplete" ? screening.message : null}
        onSubmit={async (scoff, surgery) => {
          setBusy(true);
          setError(null);
          const r = await send<ScreenResponse>("/fitness/transform/screen", "POST", { scoff, recent_surgery_or_injury: surgery, ...(Number.isFinite(targetKg) ? { target_weight_kg: targetKg } : {}) });
          setBusy(false);
          if (!r.ok) return setError(r.message);
          setScreening(r.data);
          if (r.data.decision === "allowed" || r.data.decision === "allowed_with_cautions") setStep(1);
        }}
        review={body.review}
      />
    );

  const cautions = screening?.cautions ?? [];

  if (step === 1) {
    const gap = Number.isFinite(targetKg) ? currentKg - targetKg : 0;
    const range = paceWeeksRange(gap, currentKg, pace);
    const perWeek = paceKgPerWeek(currentKg, pace);
    return (
      <StepperShell steps={STEPS} index={1} title="Your goal" lead="A gentle pace is the one that lasts." onBack={() => setStep(0)} onNext={() => void continueGoal()} nextDisabled={targetBlock !== null} busy={busy} error={error}>
        <ClinicalNote review={body.review} />
        {cautions.length > 0 && <Notice tone="sky" title="Bubbles will adapt for what you told it">Your record mentions: {cautions.join(", ")}. The plan adjusts, and your doctor or dietitian can tune it further.</Notice>}
        <NumField id="target" label="Target weight" unit={units === "imperial" ? "lb" : "kg"} value={target} onChange={setTarget} hint={`You are at ${formatWeight(currentKg, units)} now.`} error={target && targetBlock} />
        <Field id="pace" label={`Pace: ${pace.toFixed(2)}% of your weight a week`} hint="Slower is kinder and easier to keep. Bubbles will not plan faster than its safety limit, whatever you pick here.">
          <input id="pace" type="range" min={PACE_MIN} max={PACE_MAX} step={0.05} value={pace} onChange={(e) => setPace(clampPace(Number(e.target.value)))} className="h-11 w-full accent-[var(--bubbles-grape)]" aria-valuetext={`${pace.toFixed(2)} percent a week`} />
        </Field>
        <div aria-live="polite" className="rounded-2xl bg-blush p-4">
          <p className="m-0 text-body text-ink">That is about <strong>{units === "imperial" ? `${(perWeek * 2.2046).toFixed(2)} lb` : `${perWeek.toFixed(2)} kg`}</strong> a week on paper. <EstimateLabel /></p>
          <p className="m-0 mt-1 text-body-sm text-muted">{range ? `Reaching your target would typically take ${range[0]} to ${range[1]} weeks. Real progress is uneven and often slower.` : "Add a target below your current weight to see a time range."}</p>
        </div>
      </StepperShell>
    );
  }

  if (step === 2)
    return (
      <StepperShell steps={STEPS} index={2} title="Foods you enjoy" lead="Bubbles builds your week around these. Nothing is forbidden." onBack={() => setStep(1)} onNext={() => setStep(3)} error={error}>
        <ClinicalNote review={body.review} />
        <SelectField id="diet" label="Diet style" value={diet} onChange={setDiet} options={DIET} hint="Allergies in your records are always respected." />
        <TagInput id="foods" label="Foods you want in your week" optional values={foods} onChange={setFoods} suggestions={["rajma", "paneer", "chana", "oats", "curd", "eggs"]} />
        <TagInput id="likes" label="Foods you like" optional values={likes} onChange={setLikes} suggestions={["dal", "poha", "idli", "khichdi"]} />
        <TagInput id="dislikes" label="Foods to leave out" optional values={dislikes} onChange={setDislikes} suggestions={["bitter gourd", "mushroom", "brinjal"]} />
        <ChoiceGroup legend="Meals a day" value={meals} onChange={setMeals} options={[{ value: "3", label: "3" }, { value: "4", label: "4" }, { value: "5", label: "5" }]} />
      </StepperShell>
    );

  if (step === 3)
    return (
      <MovementStep
        onBack={() => setStep(2)}
        onNext={() => void loadPreview()}
        busy={busy}
        error={error}
        review={body.review}
        values={{ equipment, days, minutes, level }}
        set={{ setEquipment, setDays, setMinutes, setLevel }}
        questions={body.parq_questions}
      />
    );

  const pv = preview?.preview;
  if (step === 4 && pv)
    return (
      <StepperShell steps={STEPS} index={4} title="Your plan, before you decide" lead="Nothing starts until the next step. All numbers are estimates." onBack={() => setStep(3)} onNext={() => setStep(5)} nextLabel="Looks good">
        <ClinicalNote review={preview?.review} />
        <ReviewBody pv={pv} units={units} />
      </StepperShell>
    );

  return (
    <StepperShell steps={STEPS} index={5} title="Before you start" lead="Please read this once. You can pause or stop at any time." onBack={() => setStep(4)} onNext={() => void start()} nextLabel="Start my plan" nextDisabled={!agree || !pv} busy={busy} error={error}>
      <ClinicalNote review={preview?.review ?? body.review} />
      <ConsentCard id="ack" checked={agree} onChange={setAgree} title="What to know" label="I understand and want to start">
        <ul className="m-0 list-disc pl-5">{(pv?.commit_text ?? []).map((t) => <li key={t}>{t}</li>)}</ul>
      </ConsentCard>
      <div className="rounded-2xl bg-blush p-4">
        <p className="m-0 text-body-sm font-extrabold text-ink">Pause and talk to a doctor if you notice</p>
        <ul className="m-0 mt-1 list-disc pl-5 text-body-sm text-ink-soft">{(pv?.pause_symptoms ?? []).map((t) => <li key={t}>{t}</li>)}</ul>
      </div>
    </StepperShell>
  );
}

/* ── Step 0: the safety check ───────────────────────────────────────── */

function SafetyStep({ questions, busy, error, incomplete, onSubmit, review }: {
  questions: string[]; busy: boolean; error: string | null; incomplete: string | null; review: BodyResponse["review"];
  onSubmit: (scoff: boolean[], surgery: boolean) => void;
}) {
  const [answers, setAnswers] = useState<(boolean | undefined)[]>(questions.map(() => undefined));
  const [surgery, setSurgery] = useState(false);
  const [ok, setOk] = useState(false);
  const [local, setLocal] = useState<string | null>(null);

  function next() {
    if (answers.some((a) => a === undefined)) {
      setLocal("Please answer all five questions. Take your time.");
      return;
    }
    setLocal(null);
    onSubmit(answers as boolean[], surgery);
  }

  return (
    <StepperShell steps={STEPS} index={0} title="A kind, quick safety check" lead="Strict plans are only helpful when food and exercise feel okay. These questions are never judged." onNext={next} nextLabel="Continue" nextDisabled={!ok} busy={busy} error={local ?? error}>
      <ClinicalNote review={review} />
      {incomplete && <Notice tone="sky" role="status">{incomplete}</Notice>}
      <ConsentCard id="screen-ok" checked={ok} onChange={setOk} title="Why Bubbles asks" label="I'm happy to answer these">
        <p className="m-0">Plans that cut calories can be hard on some people, so Bubbles checks first. Your answers stay private and only decide what Bubbles offers you.</p>
      </ConsentCard>
      {questions.map((q, i) => (
        <fieldset key={q} className="m-0 min-w-0 rounded-2xl border border-line p-4">
          <legend className="px-1 text-body font-bold text-ink">{i + 1}. {q}</legend>
          <div className="mt-1 flex gap-3">
            {([true, false] as const).map((v) => (
              <label key={String(v)} className={`flex min-h-[44px] flex-1 cursor-pointer items-center justify-center gap-2 rounded-full border px-4 text-body-sm font-extrabold ${answers[i] === v ? "border-bubbles-grape bg-tint-grape text-bubbles-grape-deep" : "border-line text-muted"}`}>
                <input type="radio" name={`scoff-${i}`} checked={answers[i] === v} onChange={() => setAnswers(answers.map((a, n) => (n === i ? v : a)))} className="h-5 w-5 accent-[var(--bubbles-grape)]" />
                {v ? "Yes" : "No"}
              </label>
            ))}
          </div>
        </fieldset>
      ))}
      <CheckRow id="surgery" checked={surgery} onChange={setSurgery}>I have had surgery or an injury in the last few weeks</CheckRow>
    </StepperShell>
  );
}

/* ── Refusal, kindly ────────────────────────────────────────────────── */

function Refusal({ screening, onRecorded, onRedo }: { screening: Screening; onRecorded: () => void; onRedo: () => void }) {
  const send = useSend();
  const [ok, setOk] = useState(false);
  const [date, setDate] = useState(todayISO());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const alt = screening.alternative;
  const canClear = screening.exclusions.length > 0 && screening.exclusions.every((e) => e.clearable && e.area);

  async function record() {
    setBusy(true);
    setError(null);
    const areas = Array.from(new Set(screening.exclusions.map((e) => e.area).filter((a): a is string => Boolean(a))));
    const r = await send("/profile/body", "PUT", { clinician_clearance: { cleared: true, date, areas } });
    setBusy(false);
    if (r.ok) onRecorded();
    else setError(r.message);
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="m-0 text-body text-ink">{screening.message}</p>
      <ul className="m-0 flex list-none flex-col gap-3 p-0">
        {screening.exclusions.map((e) => (
          <li key={e.code} className="rounded-2xl bg-tint-sky p-4">
            <p className="m-0 font-display text-h4 text-ink">{e.label}</p>
            <p className="m-0 mt-1 text-body-sm text-ink">{e.message}</p>
          </li>
        ))}
      </ul>
      <div className={`${CARD} p-4`}>
        <p className="m-0 font-display text-h4 text-ink">What Bubbles can do instead</p>
        {alt === "support" ? (
          <p className="m-0 mt-1 text-body-sm text-ink-soft">Food can feel heavy sometimes, and you do not have to carry that alone. Talking to a doctor, a counsellor or someone you trust can really help. If you ever feel unsafe, please contact your local emergency number or a crisis line. Bubbles is here for gentle, no-pressure tracking whenever you want it.</p>
        ) : alt === "clinician" ? (
          <p className="m-0 mt-1 text-body-sm text-ink-soft">Please check with your doctor first. When they say a structured plan is fine, come back and Bubbles will be ready. Meanwhile a gentle plan is available.</p>
        ) : (
          <p className="m-0 mt-1 text-body-sm text-ink-soft">A gentle plan without strict targets fits you well right now: steady meals and easy movement.</p>
        )}
        <div className="mt-3 flex flex-wrap gap-2">
          {(screening.gentle_available || alt === "gentle" || alt === "clinician") && <Link href="/fitness/diet" className={`${BTN_PRIMARY} no-underline`}>Gentle diet plan</Link>}
          {(screening.gentle_available || alt === "gentle" || alt === "clinician") && <Link href="/fitness/workouts" className={`${BTN_SECONDARY} no-underline`}>Gentle workouts</Link>}
          {alt === "support" && <Link href="/care" className={`${BTN_SECONDARY} no-underline`}>Prepare to talk to a doctor</Link>}
          <Link href="/fitness" className={`${BTN_SECONDARY} no-underline`}>Back to Fitness</Link>
        </div>
      </div>
      {canClear && (
        <div className="rounded-2xl bg-blush p-4">
          <p className="m-0 mb-2 text-body-sm font-extrabold text-ink">Has your clinician already agreed to this plan?</p>
          <CheckRow id="clinician-ok" checked={ok} onChange={setOk}>My clinician has approved a structured weight-loss plan for me</CheckRow>
          {ok && (
            <div className="mt-2 flex flex-col gap-3">
              <DateField id="clinician-date" label="Date they agreed" value={date} onChange={setDate} max={todayISO()} />
              <div><button type="button" disabled={busy} onClick={() => void record()} className={BTN_PRIMARY}>{busy ? "Saving…" : "Record this and try again"}</button></div>
            </div>
          )}
          <div aria-live="polite">{error && <p role="alert" className="m-0 mt-2 text-body-sm font-bold text-bubbles-pink-deep">{error}</p>}</div>
        </div>
      )}
      <div><button type="button" className={BTN_SECONDARY} onClick={onRedo}>Review my answers</button></div>
    </div>
  );
}

/* ── Movement (needs the exercise screen) ───────────────────────────── */

function MovementStep({ onBack, onNext, busy, error, review, values, set, questions }: {
  onBack: () => void; onNext: () => void; busy: boolean; error: string | null; review: BodyResponse["review"]; questions: BodyResponse["parq_questions"];
  values: { equipment: string; days: string; minutes: string; level: string };
  set: { setEquipment: (v: string) => void; setDays: (v: string) => void; setMinutes: (v: string) => void; setLevel: (v: string) => void };
}) {
  const [plan, reload] = useBubblesQuery<WorkoutPlanDoc>("/fitness/workouts/plan");
  const screened = plan.status === "ready" && plan.data.screen && plan.data.screen.mode !== "incomplete";
  return (
    <StepperShell steps={STEPS} index={3} title="Movement" lead="Easy, regular movement beats hard and rare." onBack={onBack} onNext={onNext} nextLabel="See my plan" nextDisabled={!screened} busy={busy} error={error}>
      <ClinicalNote review={review} />
      {plan.status === "loading" && <Skeleton className="h-32 w-full rounded-2xl" />}
      {plan.status === "error" && <ErrorCard inset title="Couldn't check your exercise screen" message={plan.message} onRetry={reload} />}
      {plan.status === "ready" && !screened && (
        <>
          <p className="m-0 text-body-sm text-muted">Strict plans include exercise, so a short safety check comes first.</p>
          <ExerciseScreening questions={questions} onDone={reload} />
        </>
      )}
      {screened && plan.status === "ready" && (
        <>
          {plan.data.screen?.mode === "clinician_first" && <Notice tone="sky" title="Gentle movement only for now">{plan.data.screen.message}</Notice>}
          <ChoiceGroup legend="What can you use?" value={values.equipment} onChange={set.setEquipment} options={[{ value: "none", label: "Nothing" }, { value: "home", label: "Home basics" }, { value: "gym", label: "Gym" }, { value: "pool", label: "Pool" }]} />
          <ChoiceGroup legend="Days a week" value={values.days} onChange={set.setDays} options={[2, 3, 4, 5].map((n) => ({ value: String(n), label: String(n) }))} />
          <SelectField id="mv-min" label="Time per session" value={values.minutes} onChange={set.setMinutes} options={[20, 30, 40, 45, 60].map((n) => ({ value: String(n), label: `${n} minutes` }))} />
          <ChoiceGroup legend="Where are you now?" value={values.level} onChange={set.setLevel} options={[{ value: "1", label: "Just starting" }, { value: "2", label: "Some experience" }, { value: "3", label: "Quite experienced" }]} />
        </>
      )}
    </StepperShell>
  );
}

/* ── Review ─────────────────────────────────────────────────────────── */

function ReviewBody({ pv, units }: { pv: NonNullable<PreviewResponse["preview"]>; units: Units }) {
  const t = pv.targets;
  const day = pv.diet.days[0];
  return (
    <div className="flex flex-col gap-5">
      <section aria-label="Daily numbers" className="rounded-2xl bg-blush p-4">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="m-0 font-display text-h3 text-ink">Daily budget</h2>
          <EstimateLabel />
        </div>
        <p className="m-0 mt-1 font-display text-metric text-ink">about {fmt(t.kcal)} kcal</p>
        <p className="m-0 text-body-sm text-muted">Never below {fmt(t.floor_kcal)} kcal. About {t.pace_kg_per_week.toFixed(2)} {units === "imperial" ? "kg (" + (t.pace_kg_per_week * 2.2046).toFixed(2) + " lb)" : "kg"} a week on paper.</p>
        <div className="mt-3"><MacroBars eaten={{ protein_g: t.protein_g, carbs_g: t.carbs_g, fat_g: t.fat_g, fibre_g: t.fibre_g }} target={{ protein_g: t.protein_g, carbs_g: t.carbs_g, fat_g: t.fat_g, fibre_g: t.fibre_g }} /></div>
        <ul className="m-0 mt-3 grid list-none grid-cols-1 gap-1 p-0 text-body-sm text-ink sm:grid-cols-3">
          <li>Water: about {(t.water_ml / 1000).toFixed(1)} L</li>
          <li>Steps: about {fmt(t.steps)}</li>
          <li>Sleep: {t.sleep_hours[0]}–{t.sleep_hours[1]} hours</li>
        </ul>
      </section>

      {t.time_to_goal && t.time_to_goal.gap_kg > 0 && (
        <section aria-label="Time to goal" className="rounded-2xl bg-tint-sky p-4">
          <p className="m-0 text-body text-ink">Reaching {formatWeight(t.target_weight_kg ?? null, units)} would <strong>{formatWeeks(t.time_to_goal.weeks_low, t.time_to_goal.weeks_high)}</strong>. Real progress is uneven, and slower weeks are normal.</p>
          {t.limited_by.length > 0 && <p className="m-0 mt-1 text-body-sm text-ink-soft">Your pace was held back by Bubbles&rsquo;s safety limit: {t.limited_by.join("; ")}. That is on purpose.</p>}
        </section>
      )}
      {t.notes.length > 0 && <ul className="m-0 list-disc pl-5 text-body-sm text-ink-soft">{t.notes.map((n) => <li key={n}>{n}</li>)}</ul>}

      <section aria-label="Your first day of meals">
        <h2 className="m-0 mb-2 font-display text-h3 text-ink">A sample day of meals</h2>
        <p className="m-0 mb-3 text-body-sm text-muted">{pv.diet.days.length} days of meals are ready, averaging about {fmt(pv.diet.summary.avg_kcal)} kcal. You can swap any meal later.</p>
        <ul className="m-0 flex list-none flex-col gap-3 p-0">
          {day?.meals.map((m) => <li key={m.slot}><MealCard meal={m} compact /></li>)}
        </ul>
      </section>

      {pv.exercise?.ok && (
        <section aria-label="Your week of movement">
          <h2 className="m-0 mb-2 font-display text-h3 text-ink">Your week of movement</h2>
          <ul className="m-0 flex list-none flex-col gap-2 p-0">
            {pv.exercise.sessions.map((s, i) => (
              <li key={`${s.day}-${i}`} className="flex flex-wrap justify-between gap-2 rounded-2xl bg-blush px-3 py-2 text-body-sm">
                <span><strong className="text-ink">{s.day}</strong> · {s.label}</span>
                <span className="text-muted">{s.minutes} min</span>
              </li>
            ))}
          </ul>
          <p className="m-0 mt-2 text-body-sm text-muted">Rest days: {pv.exercise.summary.rest_days.join(", ")}. They count too.</p>
        </section>
      )}

      <section aria-label="What a good day looks like" className="rounded-2xl bg-tint-mint p-4">
        <h2 className="m-0 font-display text-h3 text-ink">What a good day looks like</h2>
        <ul className="m-0 mt-1 list-disc pl-5 text-body-sm text-ink">{pv.good_day.map((g) => <li key={g}>{g}</li>)}</ul>
      </section>
    </div>
  );
}
