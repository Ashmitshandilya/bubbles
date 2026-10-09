"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { BTN_PRIMARY, BTN_SECONDARY, CARD, ErrorCard, Skeleton, useBubblesQuery, type Query } from "../../../components/hub/HubKit";
import {
  BTN_GHOST, Disclaimer, EstimateLabel, Field, FitnessPage, INPUT, LiveMessage, MacroBars, NumField, Notice, PageHeading, ProgressRing, RangeBadge, ReviewNote, Section, SelectField, Sheet, useSend,
} from "../../../components/fitness/ui";
import { formatWhen } from "../../lib/dates";
import { foodAddText, fmt, groupByMeal, microGaps, ringFraction, ringWord, shiftDay, sumMicros, todayISO } from "../../lib/fitness-calc";
import type { FoodCard, FoodLog, Parsed } from "../../lib/fitness-types";

export function CaloriesClient() {
  return (
    <FitnessPage title="Calories">
      <Calories />
    </FitnessPage>
  );
}

const MEALS = [
  { value: "", label: "Let Bubbles decide" },
  { value: "breakfast", label: "Breakfast" },
  { value: "lunch", label: "Lunch" },
  { value: "snack", label: "Snack" },
  { value: "dinner", label: "Dinner" },
];

/* Browser speech recognition is optional: feature-detected, never required. */
interface Recognition {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  onresult: ((e: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null;
  onerror: ((e: { error?: string }) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
}
type RecognitionCtor = new () => Recognition;
function recognitionCtor(): RecognitionCtor | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as { SpeechRecognition?: RecognitionCtor; webkitSpeechRecognition?: RecognitionCtor };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

function Calories() {
  const [day, setDay] = useState(todayISO());
  const [log, reload] = useBubblesQuery<FoodLog>(`/fitness/food-log?date=${day}`);
  const [text, setText] = useState("");
  const [meal, setMeal] = useState("");
  const [oil, setOil] = useState(0);
  const [parsed, setParsed] = useState<Parsed | null>(null);
  const [parseBusy, setParseBusy] = useState(false);
  const [saveBusy, setSaveBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [customOpen, setCustomOpen] = useState(false);
  const send = useSend();
  const resultRef = useRef<HTMLDivElement>(null);
  const today = todayISO();

  const estimate = useCallback(
    async (oilTsp: number) => {
      if (!text.trim()) {
        setError("Tell Bubbles what you ate first, for example: 2 rotis, dal and a katori of curd.");
        return;
      }
      setParseBusy(true);
      setError(null);
      setNote(null);
      const r = await send<Parsed>("/fitness/meal/parse", "POST", { text, oil_extra_tsp: oilTsp });
      setParseBusy(false);
      if (r.ok) setParsed(r.data);
      else setError(r.message);
    },
    [send, text],
  );

  // Moving the oil slider re-estimates the card that is already open (after a short pause).
  const firstOil = useRef(true);
  useEffect(() => {
    if (firstOil.current) {
      firstOil.current = false;
      return;
    }
    if (!parsed) return;
    const id = window.setTimeout(() => void estimate(oil), 450);
    return () => window.clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [oil]);

  useEffect(() => {
    if (parsed) resultRef.current?.focus();
  }, [parsed]);

  async function confirm() {
    if (!parsed || saveBusy) return;
    setSaveBusy(true);
    setError(null);
    const r = await send("/fitness/food-log", "POST", { text, meal: meal || undefined, date: day, oil_extra_tsp: oil });
    setSaveBusy(false);
    if (!r.ok) {
      setError(r.message);
      return;
    }
    setParsed(null);
    setText("");
    setOil(0);
    setNote("Saved to your day. Thank you for logging.");
    reload();
  }

  async function remove(id: string) {
    const r = await send(`/fitness/food-log/${encodeURIComponent(id)}?date=${day}`, "DELETE");
    if (r.ok) {
      setNote("Removed.");
      reload();
    } else setError(r.message);
  }

  function addFood(f: FoodCard) {
    setText((t) => (t.trim() ? `${t.trim()}, ${foodAddText(f)}` : foodAddText(f)));
    setParsed(null);
  }

  return (
    <div className="flex flex-col gap-5">
      <PageHeading kicker="Calories" title="What did you eat?" text="Say it the way you would say it to a friend. Bubbles makes an estimate, you check it, and only then is it saved." />
      <ReviewNote />

      <DayBar day={day} today={today} onChange={(d) => { setDay(d); setParsed(null); setNote(null); }} />

      <Section title="Log a meal">
        <form
          noValidate
          onSubmit={(e) => {
            e.preventDefault();
            void estimate(oil);
          }}
          className="flex flex-col gap-4"
        >
          <MealInput id="meal-text" value={text} onChange={(v) => { setText(v); setParsed(null); }} />
          <SelectField id="meal-kind" label="Which meal?" optional value={meal} onChange={setMeal} options={MEALS} />
          <div className="flex flex-wrap gap-2">
            <button type="submit" disabled={parseBusy} className={BTN_PRIMARY}>
              {parseBusy ? "Estimating…" : "Check Bubbles' estimate"}
            </button>
            <button type="button" onClick={() => setCustomOpen(true)} className={BTN_SECONDARY}>
              Add my own food
            </button>
          </div>
          <FoodSearch onAdd={addFood} />
        </form>
        <div aria-live="polite" className="mt-3">
          {error && <p role="alert" className="m-0 rounded-2xl bg-tint-pink px-4 py-3 text-body-sm font-bold text-bubbles-pink-deep">{error}</p>}
          {note && !error && <LiveMessage message={note} />}
        </div>
      </Section>

      {parsed && (
        <div ref={resultRef} tabIndex={-1} className="outline-none" aria-label="Estimate to confirm">
          <Confirmation parsed={parsed} oil={oil} onOil={setOil} onConfirm={() => void confirm()} onCancel={() => setParsed(null)} busy={saveBusy} refreshing={parseBusy} />
        </div>
      )}

      <DayView log={log} reload={reload} onDelete={remove} day={day} today={today} />
      <Disclaimer />
      <CustomFoodSheet open={customOpen} onClose={() => setCustomOpen(false)} onAdded={(f) => { addFood(f); setNote(`${f.name} added to your meal text. Check the estimate when you are ready.`); }} />
    </div>
  );
}

/* ── Day switcher ───────────────────────────────────────────────────── */

function DayBar({ day, today, onChange }: { day: string; today: string; onChange: (d: string) => void }) {
  return (
    <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Choose a day">
      <button type="button" className={BTN_SECONDARY} onClick={() => onChange(shiftDay(day, -1))} aria-label="Previous day">
        &larr;
      </button>
      <label className="flex min-h-[44px] items-center gap-2 rounded-full border-2 border-line bg-surface px-4 text-body-sm font-extrabold text-ink">
        <span className="sr-only">Date</span>
        <input type="date" value={day} max={today} onChange={(e) => e.target.value && onChange(e.target.value)} className="min-h-[40px] bg-transparent" />
      </label>
      <button type="button" className={BTN_SECONDARY} onClick={() => onChange(shiftDay(day, 1))} disabled={day >= today} aria-label="Next day">
        &rarr;
      </button>
      <span className="text-body-sm font-extrabold text-muted" aria-live="polite">
        {day === today ? "Today" : formatWhen(day, true)}
      </span>
      {day !== today && (
        <button type="button" className={BTN_GHOST} onClick={() => onChange(today)}>
          Back to today
        </button>
      )}
    </div>
  );
}

/* ── Meal text input with optional voice ────────────────────────────── */

function MealInput({ id, value, onChange }: { id: string; value: string; onChange: (v: string) => void }) {
  const [canSpeak, setCanSpeak] = useState(false);
  const [listening, setListening] = useState(false);
  const [voiceNote, setVoiceNote] = useState<string | null>(null);
  const rec = useRef<Recognition | null>(null);
  const valueRef = useRef(value);
  valueRef.current = value;

  useEffect(() => {
    setCanSpeak(recognitionCtor() !== null);
    return () => rec.current?.stop();
  }, []);

  function toggle() {
    if (listening) {
      rec.current?.stop();
      return;
    }
    const Ctor = recognitionCtor();
    if (!Ctor) return;
    const r = new Ctor();
    r.lang = "en-IN";
    r.interimResults = false;
    r.continuous = false;
    r.onresult = (e) => {
      const said = Array.from(e.results).map((x) => x[0]?.transcript ?? "").join(" ").trim();
      if (said) onChange(valueRef.current.trim() ? `${valueRef.current.trim()}, ${said}` : said);
    };
    r.onerror = (e) => setVoiceNote(e.error === "not-allowed" ? "Microphone access is off, so voice can't start. You can type instead." : "Voice didn't catch that. You can type instead.");
    r.onend = () => setListening(false);
    setVoiceNote(null);
    rec.current = r;
    try {
      r.start();
      setListening(true);
    } catch {
      setVoiceNote("Voice couldn't start. You can type instead.");
    }
  }

  return (
    <Field id={id} label="Your meal" hint="For example: 2 rotis, dal, sabzi and a katori of curd">
      <textarea id={id} rows={3} value={value} maxLength={2000} onChange={(e) => onChange(e.target.value)} className={`${INPUT} resize-y`} />
      {canSpeak && (
        <div className="flex flex-wrap items-center gap-3">
          <button type="button" onClick={toggle} aria-pressed={listening} className={listening ? BTN_PRIMARY : BTN_SECONDARY}>
            {listening ? "Listening… tap to stop" : "Speak instead"}
          </button>
          <span className="text-body-sm text-muted">Your browser turns speech into text; it may use an online service to do it.</span>
        </div>
      )}
      <div aria-live="polite">{voiceNote && <p className="m-0 text-body-sm font-bold text-bubbles-pink-deep">{voiceNote}</p>}</div>
    </Field>
  );
}

/* ── Food search ────────────────────────────────────────────────────── */

function FoodSearch({ onAdd }: { onAdd: (f: FoodCard) => void }) {
  const send = useSend();
  const [q, setQ] = useState("");
  const [results, setResults] = useState<FoodCard[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const latest = useRef(0);

  useEffect(() => {
    const term = q.trim();
    if (term.length < 2) {
      setResults(null);
      setError(null);
      return;
    }
    const id = window.setTimeout(async () => {
      const mine = ++latest.current;
      const r = await send<{ results: FoodCard[] }>(`/fitness/foods/search?q=${encodeURIComponent(term)}&limit=8`, "GET");
      if (mine !== latest.current) return;
      if (r.ok) {
        setResults(r.data.results);
        setError(null);
      } else setError(r.message);
    }, 300);
    return () => window.clearTimeout(id);
  }, [q, send]);

  return (
    <div className="rounded-3xl bg-blush p-4">
      <Field id="food-search" label="Or look up a food" optional hint="Add it to your meal, then check the estimate.">
        <input id="food-search" type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="paneer, poha, banana…" className={INPUT} />
      </Field>
      <div aria-live="polite" className="mt-2">
        {error && <p role="alert" className="m-0 text-body-sm font-bold text-bubbles-pink-deep">{error}</p>}
        {results && results.length === 0 && <p className="m-0 text-body-sm text-muted">No match. Try another word, or add your own food.</p>}
        {results && results.length > 0 && (
          <ul className="m-0 mt-1 flex list-none flex-col gap-2 p-0">
            {results.map((f) => (
              <li key={f.name} className="flex items-center justify-between gap-3 rounded-2xl bg-surface p-3">
                <span className="min-w-0 text-body-sm">
                  <span className="font-extrabold text-ink">{f.name}</span>
                  <span className="block text-muted">
                    {f.category === "custom" ? f.serving : `per ${Math.round(f.serving_g)} g`}: about {fmt(f.kcal)} kcal · {Math.round(f.protein_g)} g protein
                  </span>
                </span>
                <button type="button" onClick={() => onAdd(f)} className={BTN_SECONDARY} aria-label={`Add ${f.name} to my meal`}>
                  Add
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

/* ── Confirmation card ──────────────────────────────────────────────── */

function Confirmation({ parsed, oil, onOil, onConfirm, onCancel, busy, refreshing }: {
  parsed: Parsed; oil: number; onOil: (n: number) => void; onConfirm: () => void; onCancel: () => void; busy: boolean; refreshing: boolean;
}) {
  const t = parsed.totals;
  return (
    <section aria-labelledby="confirm-title" className={`${CARD} flex flex-col gap-4 border-bubbles-grape p-5 sm:p-6`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="confirm-title" className="m-0 font-display text-h3 text-ink">Is this right?</h2>
        <EstimateLabel />
      </div>
      {parsed.support && <Notice tone="sky" title="A gentle note" role="status">{parsed.support}</Notice>}
      {parsed.warnings.length > 0 && (
        <Notice tone="sun" title="Worth a look" role="status">
          <ul className="m-0 list-disc pl-5">
            {parsed.warnings.map((w) => <li key={w}>{w}</li>)}
          </ul>
        </Notice>
      )}
      {parsed.items.length === 0 ? (
        <p className="m-0 rounded-2xl bg-blush p-4 text-body-sm text-muted">Bubbles didn&rsquo;t recognise any food in that. Try naming the foods, or add your own food above.</p>
      ) : (
        <ul className="m-0 flex list-none flex-col divide-y divide-line p-0">
          {parsed.items.map((i, n) => (
            <li key={`${i.food}-${n}`} className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 py-2.5">
              <span className="text-body">
                <span className="font-extrabold text-ink">{i.food}</span>
                <span className="text-muted"> · {Number(i.quantity.toFixed(2))} {i.unit}{i.match && i.match !== "exact" ? " (closest match)" : ""}</span>
              </span>
              <RangeBadge value={i.kcal} low={i.kcal_low} high={i.kcal_high} />
            </li>
          ))}
        </ul>
      )}
      {parsed.unrecognised.length > 0 && (
        <p className="m-0 rounded-2xl bg-blush px-4 py-3 text-body-sm text-ink-soft">
          <strong>Bubbles didn&rsquo;t recognise:</strong> {parsed.unrecognised.join(", ")}. These are <em>not</em> counted. Reword them or add them as your own food.
        </p>
      )}
      <div className="rounded-2xl bg-blush p-4">
        <label htmlFor="oil" className="text-body-sm font-extrabold text-ink">Extra oil or ghee used in cooking: {oil === 0 ? "none extra" : `${oil} tsp`}</label>
        <input id="oil" type="range" min={0} max={5} step={0.5} value={oil} onChange={(e) => onOil(Number(e.target.value))} className="mt-2 h-11 w-full accent-[var(--bubbles-grape)]" aria-describedby="oil-hint" />
        <p id="oil-hint" className="m-0 text-body-sm text-muted">Home cooking often uses more oil than it looks. Slide to add it; the estimate updates.</p>
      </div>
      <p className="m-0 text-body" aria-live="polite">
        <span className="font-extrabold text-ink">Total:</span> <RangeBadge value={t.kcal} low={t.kcal_low} high={t.kcal_high} /> · {Math.round(t.protein_g)} g protein · {Math.round(t.carbs_g)} g carbs · {Math.round(t.fat_g)} g fat
        {refreshing && <span className="text-muted"> (updating…)</span>}
      </p>
      <div className="flex flex-wrap gap-2">
        <button type="button" onClick={onConfirm} disabled={busy || parsed.items.length === 0} className={BTN_PRIMARY}>
          {busy ? "Saving…" : "Yes, save this"}
        </button>
        <button type="button" onClick={onCancel} disabled={busy} className={BTN_SECONDARY}>
          Edit my words
        </button>
      </div>
      <p className="m-0 text-body-sm text-muted">Nothing is saved until you press save.</p>
    </section>
  );
}

/* ── The day ────────────────────────────────────────────────────────── */

function DayView({ log, reload, onDelete, day, today }: { log: Query<FoodLog>; reload: () => void; onDelete: (id: string) => Promise<void>; day: string; today: string }) {
  const [confirmId, setConfirmId] = useState<string | null>(null);
  if (log.status === "loading")
    return (
      <div className="flex flex-col gap-3" role="status" aria-label="Loading your day">
        <Skeleton className="h-48 w-full rounded-3xl" />
        <Skeleton className="h-24 w-full rounded-3xl" />
      </div>
    );
  if (log.status === "error") return <ErrorCard title="Couldn't load this day" message={log.message} onRetry={reload} />;

  const d = log.data;
  const groups = groupByMeal(d.entries);
  const gaps = d.entries.length >= 2 ? microGaps(sumMicros(d.entries)) : [];
  return (
    <>
      <Section title={day === today ? "Your day so far" : `Your day, ${formatWhen(day, true)}`} aside={<EstimateLabel />}>
        {d.budget && d.targets ? (
          <div className="flex flex-col items-center gap-6 sm:flex-row sm:items-start">
            <ProgressRing fraction={ringFraction(d.budget.eaten_kcal, d.budget.budget_kcal)} label={`${fmt(d.budget.eaten_kcal)} of about ${fmt(d.budget.budget_kcal)} kilocalories (estimate)`}>
              <span className="font-display text-metric text-ink">{fmt(d.budget.eaten_kcal)}</span>
              <span className="text-body-sm text-muted">of about {fmt(d.budget.budget_kcal)} kcal</span>
            </ProgressRing>
            <div className="w-full min-w-0 flex-1">
              <p className="m-0 mb-1 font-extrabold text-ink">{ringWord(d.budget.eaten_kcal, d.budget.budget_kcal)}</p>
              {d.totals.kcal > 0 && <p className="m-0 mb-3 text-body-sm text-muted">Estimated range <RangeBadge value={d.totals.kcal} low={d.totals.kcal_low} high={d.totals.kcal_high} /></p>}
              <MacroBars eaten={d.totals} target={d.targets} />
            </div>
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            <p className="m-0 text-body text-ink">
              Eaten so far: <RangeBadge value={d.totals.kcal} low={d.totals.kcal_low} high={d.totals.kcal_high} />
            </p>
            <Notice tone="sky" title="Want a daily budget too?">
              Add your height, weight and birth date and Bubbles will work out an estimate for you. <Link href="/fitness/setup" className="font-extrabold text-bubbles-grape-deep">Add my details</Link>
            </Notice>
          </div>
        )}
      </Section>

      {d.entries.length === 0 ? (
        <div className={`${CARD} p-6 text-center`}>
          <p className="m-0 font-display text-h4 text-ink">Nothing logged for this day</p>
          <p className="m-0 mt-1 text-body-sm text-muted">That&rsquo;s okay. Log what you remember, or skip the day. Missing days are just gaps, not mistakes.</p>
        </div>
      ) : (
        groups.map((g) => (
          <Section key={g.meal} title={g.meal[0].toUpperCase() + g.meal.slice(1)} aside={<span className="text-body-sm font-extrabold text-muted">about {fmt(g.kcal)} kcal</span>}>
            <ul className="m-0 flex list-none flex-col gap-3 p-0">
              {g.entries.map((e) => (
                <li key={e.id} className="rounded-2xl bg-blush p-3">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <p className="m-0 min-w-0 flex-1 text-body font-extrabold text-ink">{e.text}</p>
                    <RangeBadge value={e.totals.kcal} low={e.totals.kcal_low} high={e.totals.kcal_high} />
                  </div>
                  <details className="mt-1">
                    <summary className="inline-flex min-h-[44px] cursor-pointer items-center text-body-sm font-extrabold text-bubbles-grape-deep">What Bubbles counted</summary>
                    <ul className="m-0 list-disc pl-5 text-body-sm text-ink-soft">
                      {e.items.map((i, n) => <li key={`${i.food}-${n}`}>{Number(i.quantity.toFixed(2))} {i.unit} {i.food}: about {fmt(i.kcal)} kcal</li>)}
                    </ul>
                    {e.unrecognised.length > 0 && <p className="m-0 mt-1 text-body-sm text-muted">Not counted: {e.unrecognised.join(", ")}</p>}
                  </details>
                  {confirmId === e.id ? (
                    <div className="flex flex-wrap items-center gap-2" role="group" aria-label={`Delete ${e.text}?`}>
                      <span className="text-body-sm font-bold">Remove this entry?</span>
                      <button type="button" className={BTN_SECONDARY} onClick={() => { setConfirmId(null); void onDelete(e.id); }}>Yes, remove</button>
                      <button type="button" className={BTN_GHOST} onClick={() => setConfirmId(null)}>Keep it</button>
                    </div>
                  ) : (
                    <button type="button" className={BTN_GHOST} onClick={() => setConfirmId(e.id)} aria-label={`Delete ${e.text}`}>Delete</button>
                  )}
                </li>
              ))}
            </ul>
          </Section>
        ))
      )}

      {gaps.length > 0 && (
        <Notice tone="mint" title="A gentle food idea">
          <p className="m-0">From what you have logged so far, these look a little lower. Not every food has this data, so treat it as a hint, not a verdict.</p>
          <ul className="m-0 mt-2 list-disc pl-5">
            {gaps.map((g) => <li key={g.label}><strong>{g.label}</strong>: foods that can help include {g.foods}.</li>)}
          </ul>
        </Notice>
      )}
    </>
  );
}

/* ── Custom food ────────────────────────────────────────────────────── */

function CustomFoodSheet({ open, onClose, onAdded }: { open: boolean; onClose: () => void; onAdded: (f: FoodCard) => void }) {
  const send = useSend();
  const [v, setV] = useState({ name: "", serving: "1 serving", serving_g: "100", kcal: "", protein_g: "", carbs_g: "", fat_g: "", fibre_g: "", diet: "v" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const set = (k: keyof typeof v) => (x: string) => setV((p) => ({ ...p, [k]: x }));

  async function save() {
    setBusy(true);
    setError(null);
    const r = await send<{ food: FoodCard }>("/fitness/foods/custom", "POST", { ...v, serving_g: Number(v.serving_g), kcal: Number(v.kcal), protein_g: Number(v.protein_g || 0), carbs_g: Number(v.carbs_g || 0), fat_g: Number(v.fat_g || 0), fibre_g: Number(v.fibre_g || 0) });
    setBusy(false);
    if (!r.ok) {
      setError(r.message);
      return;
    }
    onAdded({ ...r.data.food, category: "custom" });
    setV({ ...v, name: "", kcal: "", protein_g: "", carbs_g: "", fat_g: "", fibre_g: "" });
    onClose();
  }

  return (
    <Sheet open={open} onClose={onClose} title="Add your own food">
      <p className="m-0 text-body-sm text-muted">Only you can see this. Use the label on the pack or your best guess; everything stays an estimate.</p>
      <form noValidate onSubmit={(e) => { e.preventDefault(); void save(); }} className="flex flex-col gap-4">
        <Field id="cf-name" label="Name"><input id="cf-name" value={v.name} maxLength={80} onChange={(e) => set("name")(e.target.value)} className={INPUT} /></Field>
        <Field id="cf-serving" label="One serving is" hint="For example: 1 ladoo, 1 bowl"><input id="cf-serving" value={v.serving} maxLength={80} onChange={(e) => set("serving")(e.target.value)} className={INPUT} /></Field>
        <div className="grid grid-cols-2 gap-3">
          <NumField id="cf-g" label="Serving weight" unit="g" value={v.serving_g} onChange={set("serving_g")} min={1} max={2000} />
          <NumField id="cf-kcal" label="Calories" unit="kcal" value={v.kcal} onChange={set("kcal")} min={0} max={5000} />
          <NumField id="cf-p" label="Protein" unit="g" optional value={v.protein_g} onChange={set("protein_g")} min={0} max={500} />
          <NumField id="cf-c" label="Carbs" unit="g" optional value={v.carbs_g} onChange={set("carbs_g")} min={0} max={500} />
          <NumField id="cf-f" label="Fat" unit="g" optional value={v.fat_g} onChange={set("fat_g")} min={0} max={500} />
          <NumField id="cf-fi" label="Fibre" unit="g" optional value={v.fibre_g} onChange={set("fibre_g")} min={0} max={500} />
        </div>
        <SelectField id="cf-diet" label="Diet" value={v.diet} onChange={set("diet")} options={[{ value: "V", label: "Vegan" }, { value: "v", label: "Vegetarian" }, { value: "e", label: "Eggetarian" }, { value: "n", label: "Non-vegetarian" }]} />
        <div aria-live="polite">{error && <p role="alert" className="m-0 rounded-2xl bg-tint-pink px-4 py-3 text-body-sm font-bold text-bubbles-pink-deep">{error}</p>}</div>
        <button type="submit" disabled={busy || !v.name.trim() || !v.kcal} className={BTN_PRIMARY}>{busy ? "Saving…" : "Save food"}</button>
      </form>
    </Sheet>
  );
}
