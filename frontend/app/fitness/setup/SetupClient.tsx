"use client";

import Link from "next/link";
import { useState } from "react";
import { DateField } from "../../../components/tracking/kit";
import { BTN_PRIMARY, CARD, ErrorCard, Skeleton, useBubblesQuery } from "../../../components/hub/HubKit";
import { ChoiceGroup, CheckRow, ClinicalNote, FitnessPage, LiveMessage, MultiChoice, NumField, PageHeading, SelectField, Section, TagInput, useSend } from "../../../components/fitness/ui";
import { cmToFtIn, ftInToCm, todayISO, weightFromKg, weightToKg, type Units } from "../../lib/fitness-calc";
import type { BodyProfile, BodyResponse } from "../../lib/fitness-types";

const ACTIVITY = [
  { value: "sedentary", label: "Mostly sitting" },
  { value: "light", label: "Light: some walking" },
  { value: "moderate", label: "Moderate: active most days" },
  { value: "very_active", label: "Very active" },
  { value: "extra_active", label: "Extra active: physical job and training" },
];
const DIET = [
  { value: "", label: "No particular style" },
  { value: "vegetarian", label: "Vegetarian" },
  { value: "vegan", label: "Vegan" },
  { value: "eggetarian", label: "Eggetarian" },
  { value: "jain", label: "Jain" },
  { value: "non-vegetarian", label: "Non-vegetarian" },
  { value: "halal", label: "Halal" },
];
const EQUIPMENT = [
  { value: "home", label: "Mat, chair, step" },
  { value: "dumbbell", label: "Dumbbells" },
  { value: "band", label: "Resistance bands" },
  { value: "bike", label: "Bike" },
  { value: "gym", label: "Gym" },
  { value: "pool", label: "Pool" },
];
const FIELD_KEYS = ["birth_date", "height_cm", "weight_kg", "target_weight_kg", "formula_basis", "activity_level", "diet_style"] as const;

export function SetupClient() {
  return (
    <FitnessPage title="Your details">
      <Setup />
    </FitnessPage>
  );
}

function Setup() {
  const [q, reload] = useBubblesQuery<BodyResponse>("/profile/body");
  if (q.status === "loading")
    return (
      <div className="flex flex-col gap-4" role="status" aria-label="Loading your details">
        <Skeleton className="h-24 w-full rounded-3xl" />
        <Skeleton className="h-72 w-full rounded-3xl" />
      </div>
    );
  if (q.status === "error") return <ErrorCard title="Couldn't load your details" message={q.message} onRetry={reload} />;
  return <SetupForm data={q.data} />;
}

/** The server names the field first ("height_cm must be between 120 and 230"); show it under that field. */
function errorKey(message: string): string | null {
  return FIELD_KEYS.find((k) => message.toLowerCase().startsWith(k)) ?? null;
}

function SetupForm({ data }: { data: BodyResponse }) {
  const send = useSend();
  const p = data.profile;
  const [units, setUnits] = useState<Units>(p.units === "imperial" ? "imperial" : "metric");
  const [birth, setBirth] = useState(p.birth_date ?? "");
  const [heightCm, setHeightCm] = useState(p.height_cm ? String(p.height_cm) : "");
  const [ft, setFt] = useState(p.height_cm ? String(cmToFtIn(p.height_cm).ft) : "");
  const [inch, setInch] = useState(p.height_cm ? String(cmToFtIn(p.height_cm).inch) : "");
  const [weight, setWeight] = useState(weightFromKg(p.weight_kg ?? data.known.latest_weight_kg, p.units === "imperial" ? "imperial" : "metric"));
  const [target, setTarget] = useState(weightFromKg(p.target_weight_kg, p.units === "imperial" ? "imperial" : "metric"));
  const [basis, setBasis] = useState<string>(p.formula_basis ?? "");
  const [activity, setActivity] = useState<string>(p.activity_level ?? "light");
  const [diet, setDiet] = useState(p.diet_style ?? "");
  const [cuisines, setCuisines] = useState<string[]>(p.cuisines ?? []);
  const [likes, setLikes] = useState<string[]>(p.likes ?? []);
  const [dislikes, setDislikes] = useState<string[]>(p.dislikes ?? []);
  const [equipment, setEquipment] = useState<string[]>(p.equipment ?? []);
  const [injuries, setInjuries] = useState<string[]>(p.injuries ?? []);
  const [flags, setFlags] = useState({
    pregnant: p.pregnant === true,
    breastfeeding: p.breastfeeding === true,
    trying_to_conceive: p.trying_to_conceive === true,
    menstruating: p.menstruating === true,
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [general, setGeneral] = useState<string | null>(null);
  const [saved, setSaved] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function switchUnits(next: Units) {
    if (next === units) return;
    const wKg = weightToKg(weight, units);
    const tKg = weightToKg(target, units);
    if (next === "imperial") {
      const cm = Number(heightCm);
      if (Number.isFinite(cm) && cm > 0) {
        const f = cmToFtIn(cm);
        setFt(String(f.ft));
        setInch(String(f.inch));
      }
    } else if (ft !== "" || inch !== "") {
      setHeightCm(String(ftInToCm(Number(ft) || 0, Number(inch) || 0)));
    }
    setWeight(Number.isFinite(wKg) ? weightFromKg(wKg, next) : "");
    setTarget(Number.isFinite(tKg) ? weightFromKg(tKg, next) : "");
    setUnits(next);
  }

  async function save() {
    setBusy(true);
    setSaved(null);
    setGeneral(null);
    const errs: Record<string, string> = {};
    const cm = units === "imperial" ? ftInToCm(Number(ft) || 0, Number(inch) || 0) : Number(heightCm);
    const wKg = weightToKg(weight, units);
    const tKg = weightToKg(target, units);
    if (!birth) errs.birth_date = "Add your birth date. Bubbles uses it for your age.";
    if (!(cm > 0)) errs.height_cm = "Add your height.";
    if (!Number.isFinite(wKg)) errs.weight_kg = "Add your weight.";
    if (!basis) errs.formula_basis = "Choose one. You can pick Average if you prefer.";
    if (Object.keys(errs).length) {
      setErrors(errs);
      setBusy(false);
      return;
    }
    const body: Record<string, unknown> = {
      units, birth_date: birth, height_cm: cm, weight_kg: wKg, target_weight_kg: Number.isFinite(tKg) ? tKg : "",
      formula_basis: basis, activity_level: activity, diet_style: diet, cuisines, likes, dislikes, equipment, injuries, ...flags,
    };
    const r = await send<{ profile: BodyProfile }>("/profile/body", "PUT", body);
    setBusy(false);
    if (!r.ok) {
      const key = errorKey(r.message);
      if (key) setErrors({ [key]: r.message });
      else setGeneral(r.message);
      return;
    }
    setErrors({});
    setSaved("Saved. Bubbles will use these details for your fitness numbers.");
  }

  const missingNote = data.missing.length > 0 ? `Still needed: ${data.missing.map((m) => m.replaceAll("_", " ")).join(", ")}.` : null;

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-5">
      <PageHeading kicker="Fitness setup" title="A few details about you" text="Bubbles only asks what it needs to work out your estimates. Everything marked optional can wait, and you can change any answer later." />
      <ClinicalNote review={data.review} />
      {missingNote && <p className="m-0 rounded-2xl bg-tint-sun px-4 py-3 text-body-sm font-bold text-ink">{missingNote}</p>}

      <Section title="What Bubbles already knows">
        <p className="m-0 mb-3 text-body-sm text-muted">From your Records pages. If something is out of date, fix it there and Bubbles will pick it up.</p>
        <dl className="m-0 grid gap-3 sm:grid-cols-3">
          <Known title="Conditions" items={data.known.conditions} href="/conditions" />
          <Known title="Medications" items={data.known.medications} href="/medications" />
          <Known title="Allergies" items={data.known.allergies} href="/allergies" />
        </dl>
      </Section>

      <form
        noValidate
        onSubmit={(e) => {
          e.preventDefault();
          void save();
        }}
        className="flex flex-col gap-5"
      >
        <Section title="Needed for your numbers">
          <div className="flex flex-col gap-5">
            <ChoiceGroup legend="Units" value={units} onChange={(v) => switchUnits(v as Units)} options={[{ value: "metric", label: "Metric (kg, cm)" }, { value: "imperial", label: "Imperial (lb, ft)" }]} hint="Bubbles shows and asks in your units. It always stores metric." />
            <DateField id="birth" label="Birth date" value={birth} onChange={setBirth} max={todayISO()} error={errors.birth_date} hint="Used for your age only." />
            {units === "metric" ? (
              <NumField id="height" label="Height" unit="cm" value={heightCm} onChange={setHeightCm} min={120} max={230} error={errors.height_cm} />
            ) : (
              <div className="grid grid-cols-2 gap-3">
                <NumField id="ft" label="Height" unit="ft" value={ft} onChange={setFt} min={3} max={7} step={1} error={errors.height_cm} />
                <NumField id="in" label="and" unit="in" value={inch} onChange={setInch} min={0} max={11} step={1} />
              </div>
            )}
            <NumField id="weight" label="Weight now" unit={units === "imperial" ? "lb" : "kg"} value={weight} onChange={setWeight} error={errors.weight_kg} hint={data.known.latest_weight_kg ? "Your newest weigh-in on the Weight page is used if it is more recent." : undefined} />
            <div>
              <ChoiceGroup
                legend="Which formula should Bubbles use?"
                value={basis}
                onChange={setBasis}
                options={[{ value: "female", label: "Female" }, { value: "male", label: "Male" }, { value: "average", label: "Average of both" }]}
                hint="Used only for the energy formula, which estimates how many calories a body uses. You choose, and it says nothing about who you are."
              />
              {errors.formula_basis && <p role="alert" className="m-0 mt-1 text-body-sm font-bold text-bubbles-pink-deep">{errors.formula_basis}</p>}
            </div>
            <SelectField id="activity" label="How active is a usual week?" value={activity} onChange={setActivity} options={ACTIVITY} />
          </div>
        </Section>

        <Section title="Optional: your goal and food">
          <p className="m-0 mb-4 text-body-sm text-muted">Skip anything you like. Plans still work without these.</p>
          <div className="flex flex-col gap-5">
            <NumField id="target" label="Target weight" unit={units === "imperial" ? "lb" : "kg"} optional value={target} onChange={setTarget} error={errors.target_weight_kg} hint="Only if you have one in mind. Bubbles will explain what is a healthy range." />
            <SelectField id="diet" label="Diet style" optional value={diet} onChange={setDiet} options={DIET} error={errors.diet_style} />
            <TagInput id="cuisines" label="Cuisines you enjoy" values={cuisines} onChange={setCuisines} suggestions={["North Indian", "South Indian", "Gujarati", "Bengali", "Continental"]} />
            <TagInput id="likes" label="Foods you like" values={likes} onChange={setLikes} suggestions={["rajma", "paneer", "dal", "poha", "curd"]} />
            <TagInput id="dislikes" label="Foods you would rather not have" values={dislikes} onChange={setDislikes} suggestions={["bitter gourd", "mushroom", "brinjal"]} />
          </div>
        </Section>

        <Section title="Optional: movement">
          <div className="flex flex-col gap-5">
            <MultiChoice legend="What can you use?" values={equipment} onChange={setEquipment} options={EQUIPMENT} hint="No equipment is fine. Pick nothing and Bubbles keeps to body-weight moves." />
            <TagInput id="injuries" label="Injuries or sore spots" values={injuries} onChange={setInjuries} suggestions={["knee", "lower back", "shoulder", "ankle"]} hint="Bubbles steers around these." />
          </div>
        </Section>

        <Section title="Optional: life stage">
          <p className="m-0 mb-2 text-body-sm text-muted">These change which plans are suitable. Bubbles keeps strict plans for adults who are none of these.</p>
          <div className="flex flex-col">
            <CheckRow id="f-mens" checked={flags.menstruating} onChange={(v) => setFlags({ ...flags, menstruating: v })}>I have periods</CheckRow>
            <CheckRow id="f-preg" checked={flags.pregnant} onChange={(v) => setFlags({ ...flags, pregnant: v })}>I am pregnant</CheckRow>
            <CheckRow id="f-bf" checked={flags.breastfeeding} onChange={(v) => setFlags({ ...flags, breastfeeding: v })}>I am breastfeeding</CheckRow>
            <CheckRow id="f-ttc" checked={flags.trying_to_conceive} onChange={(v) => setFlags({ ...flags, trying_to_conceive: v })}>I am trying to conceive</CheckRow>
          </div>
        </Section>

        <div className={`${CARD} flex flex-col gap-3 p-5`}>
          <LiveMessage message={general} tone="error" />
          <LiveMessage message={saved} />
          <div className="flex flex-wrap items-center gap-3">
            <button type="submit" disabled={busy} className={BTN_PRIMARY}>
              {busy ? "Saving…" : "Save my details"}
            </button>
            {saved && (
              <Link href="/fitness" className="inline-flex min-h-[44px] items-center text-body-sm font-extrabold text-bubbles-grape-deep">
                Back to Fitness
              </Link>
            )}
          </div>
        </div>
      </form>
    </div>
  );
}

function Known({ title, items, href }: { title: string; items: string[]; href: string }) {
  return (
    <div className="rounded-2xl bg-blush p-3">
      <dt className="text-body-sm font-extrabold text-ink">{title}</dt>
      <dd className="m-0 mt-1 text-body-sm text-muted">{items.length ? items.join(", ") : "Nothing recorded"}</dd>
      <dd className="m-0">
        <Link href={href} className="inline-flex min-h-[44px] items-center text-body-sm font-extrabold text-bubbles-grape-deep">
          {items.length ? "Fix or add" : "Add"}<span className="sr-only"> {title.toLowerCase()}</span>
        </Link>
      </dd>
    </div>
  );
}
