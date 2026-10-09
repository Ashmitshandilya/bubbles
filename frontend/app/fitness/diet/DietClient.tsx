"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { BTN_PRIMARY, BTN_SECONDARY, CARD, ErrorCard, Skeleton, useBubblesQuery } from "../../../components/hub/HubKit";
import { MealCard } from "../../../components/fitness/MealCard";
import { SwapSheet } from "../../../components/fitness/SwapSheet";
import {
  BTN_GHOST, ChoiceGroup, ClinicalNote, Disclaimer, EstimateLabel, FitnessPage, LiveMessage, Notice, PageHeading, RangeBadge, Section, SelectField, Sheet, TagInput, useSend,
} from "../../../components/fitness/ui";
import { groceryKey, mealItemsText, parseTicks, proteinHint, slotToMeal } from "../../lib/fitness-calc";
import type { DietPlanDoc, GroceryItem, Parsed, PlanDay, PlanMeal } from "../../lib/fitness-types";

export function DietClient() {
  return (
    <FitnessPage title="Diet planner">
      <Diet />
    </FitnessPage>
  );
}

const STYLES = [
  { value: "", label: "No particular style" },
  { value: "vegetarian", label: "Vegetarian" },
  { value: "vegan", label: "Vegan" },
  { value: "eggetarian", label: "Eggetarian" },
  { value: "jain", label: "Jain" },
  { value: "non-vegetarian", label: "Non-vegetarian" },
  { value: "halal", label: "Halal" },
];

function Diet() {
  const [q, reload] = useBubblesQuery<DietPlanDoc>("/fitness/diet/plan");
  const [editing, setEditing] = useState(false);

  if (q.status === "loading")
    return (
      <div className="flex flex-col gap-4" role="status" aria-label="Loading your meal plan">
        <Skeleton className="h-12 w-2/3 rounded-2xl" />
        <Skeleton className="h-64 w-full rounded-3xl" />
      </div>
    );
  if (q.status === "error") return <ErrorCard title="Couldn't load your meal plan" message={q.message} onRetry={reload} />;

  const doc = q.data;
  const hasPlan = doc.exists && doc.plan?.days?.length;
  return (
    <div className="flex flex-col gap-5">
      <PageHeading kicker="Diet planner" title="Your week of meals" text="Meals picked to fit your food choices, allergies and daily estimate. Swap anything you don't fancy." />
      <ClinicalNote review={doc.review} />
      {!hasPlan || editing ? (
        <Preferences
          doc={doc}
          first={!hasPlan}
          onDone={() => {
            setEditing(false);
            reload();
          }}
          onCancel={hasPlan ? () => setEditing(false) : undefined}
        />
      ) : (
        <PlanView doc={doc} reload={reload} onChange={() => setEditing(true)} />
      )}
      <Disclaimer />
    </div>
  );
}

/* ── Preferences / generate ─────────────────────────────────────────── */

function Preferences({ doc, first, onDone, onCancel }: { doc: DietPlanDoc; first: boolean; onDone: () => void; onCancel?: () => void }) {
  const send = useSend();
  const [style, setStyle] = useState(doc.prefs?.diet_style ?? "");
  const [must, setMust] = useState<string[]>(doc.prefs?.must_include ?? []);
  const [meals, setMeals] = useState(String(doc.meals_per_day ?? 4));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [needsDetails, setNeedsDetails] = useState(false);

  async function generate(newSeed: boolean) {
    setBusy(true);
    setError(null);
    const r = await send("/fitness/diet/plan", "POST", {
      diet_style: style, must_include: must, meals_per_day: Number(meals), seed: newSeed ? 1 + Math.floor(Math.random() * 999) : (doc.prefs?.seed ?? 0),
    });
    setBusy(false);
    if (r.ok) onDone();
    else {
      setError(r.message);
      setNeedsDetails(/^add your/i.test(r.message));
    }
  }

  return (
    <Section title={first ? "Let's build your plan" : "Change your plan"}>
      <form noValidate onSubmit={(e) => { e.preventDefault(); void generate(!first); }} className="flex flex-col gap-5">
        <SelectField id="style" label="Diet style" value={style} onChange={setStyle} options={STYLES} hint="Allergies you have recorded are always respected." />
        <TagInput id="must" label="Foods to include" optional values={must} onChange={setMust} suggestions={["rajma", "paneer", "chana", "oats", "curd"]} hint="Bubbles will try to fit these in across the week." />
        <ChoiceGroup legend="Meals a day" value={meals} onChange={setMeals} options={[{ value: "3", label: "3" }, { value: "4", label: "4" }, { value: "5", label: "5" }]} />
        <div aria-live="polite">
          {error && (
            <p role="alert" className="m-0 rounded-2xl bg-tint-pink px-4 py-3 text-body-sm font-bold text-bubbles-pink-deep">
              {error}{" "}
              {needsDetails && <Link href="/fitness/setup" className="text-bubbles-grape-deep">Add my details</Link>}
            </p>
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          <button type="submit" disabled={busy} className={BTN_PRIMARY}>{busy ? "Planning…" : first ? "Make my plan" : "Make a fresh plan"}</button>
          {onCancel && <button type="button" onClick={onCancel} disabled={busy} className={BTN_SECONDARY}>Keep my current plan</button>}
        </div>
      </form>
    </Section>
  );
}

/* ── Plan view ──────────────────────────────────────────────────────── */

function PlanView({ doc, reload, onChange }: { doc: DietPlanDoc; reload: () => void; onChange: () => void }) {
  const days = doc.plan?.days ?? [];
  const [index, setIndex] = useState(0);
  const [swap, setSwap] = useState<PlanMeal | null>(null);
  const [logging, setLogging] = useState<PlanMeal | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const day: PlanDay = days[Math.min(index, days.length - 1)];
  const tabs = useRef<(HTMLButtonElement | null)[]>([]);

  function onKey(e: React.KeyboardEvent, i: number) {
    const next = e.key === "ArrowRight" ? (i + 1) % days.length : e.key === "ArrowLeft" ? (i - 1 + days.length) % days.length : e.key === "Home" ? 0 : e.key === "End" ? days.length - 1 : -1;
    if (next < 0) return;
    e.preventDefault();
    setIndex(next);
    tabs.current[next]?.focus();
  }

  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="m-0 text-body-sm text-muted">
          Average about <strong>{Math.round(doc.plan?.summary.avg_kcal ?? 0)} kcal</strong> and <strong>{Math.round(doc.plan?.summary.avg_protein_g ?? 0)} g protein</strong> a day <EstimateLabel />
        </p>
        <button type="button" onClick={onChange} className={BTN_SECONDARY}>Change or regenerate</button>
      </div>

      <div role="tablist" aria-label="Days of your plan" className="flex flex-wrap gap-2">
        {days.map((d, i) => (
          <button
            key={d.day}
            ref={(el) => { tabs.current[i] = el; }}
            role="tab"
            id={`day-tab-${i}`}
            aria-selected={i === index}
            aria-controls="day-panel"
            tabIndex={i === index ? 0 : -1}
            onClick={() => setIndex(i)}
            onKeyDown={(e) => onKey(e, i)}
            className={`bubbles-press min-h-[44px] min-w-[64px] rounded-full border-2 px-4 text-body-sm font-extrabold ${i === index ? "border-bubbles-grape bg-tint-grape text-bubbles-grape-deep" : "border-line bg-surface text-muted hover:border-line-strong"}`}
          >
            Day {d.day}
          </button>
        ))}
      </div>

      <div role="tabpanel" id="day-panel" aria-labelledby={`day-tab-${index}`} className="flex flex-col gap-4">
        <div className={`${CARD} flex flex-wrap items-center justify-between gap-3 p-4`}>
          <p className="m-0 text-body">
            Day {day.day} total <RangeBadge value={day.totals.kcal} low={day.totals.kcal_low} high={day.totals.kcal_high} /> · {Math.round(day.totals.protein_g)} g protein
          </p>
          <span className="text-body-sm text-muted">aiming for about {Math.round(day.target_kcal)} kcal</span>
        </div>
        {!day.protein_ok && (
          <Notice tone="sun" title="A little light on protein">
            This day is about {Math.round(day.totals.protein_g)} g against a goal near {Math.round(day.protein_target_g)} g. Foods that help: {proteinHint(doc.prefs?.diet_style)}. A small add-on to any meal is plenty.
          </Notice>
        )}
        <div aria-live="polite">{note && <LiveMessage message={note} />}</div>
        <ul className="m-0 flex list-none flex-col gap-4 p-0">
          {day.meals.map((m) => (
            <li key={m.slot}>
              <MealCard meal={m} onSwap={() => setSwap(m)} onLog={() => setLogging(m)} />
            </li>
          ))}
        </ul>
      </div>

      <Grocery created={doc.created} />

      <SwapSheet open={swap !== null} onClose={() => setSwap(null)} day={day.day} meal={swap} onSwapped={() => { setNote("Swapped. The rest of the day is rebalanced."); reload(); }} />
      <LogMealSheet meal={logging} onClose={() => setLogging(null)} onLogged={() => setNote("Logged to today. Thank you.")} />
    </>
  );
}

/* ── Log a planned meal (always confirmed first) ─────────────────────── */

function LogMealSheet({ meal, onClose, onLogged }: { meal: PlanMeal | null; onClose: () => void; onLogged: () => void }) {
  const send = useSend();
  const [parsed, setParsed] = useState<Parsed | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const text = meal ? mealItemsText(meal.items) : "";

  useEffect(() => {
    setParsed(null);
    setError(null);
    if (!meal) return;
    let live = true;
    void send<Parsed>("/fitness/meal/parse", "POST", { text }).then((r) => {
      if (!live) return;
      if (r.ok) setParsed(r.data);
      else setError(r.message);
    });
    return () => { live = false; };
  }, [meal, text, send]);

  async function confirm() {
    if (!meal || busy) return;
    setBusy(true);
    const r = await send("/fitness/food-log", "POST", { text, meal: slotToMeal(meal.label) });
    setBusy(false);
    if (r.ok) {
      onLogged();
      onClose();
    } else setError(r.message);
  }

  return (
    <Sheet open={meal !== null} onClose={onClose} title="Log this meal?">
      {meal && <p className="m-0 text-body text-ink"><strong>{meal.label}:</strong> {meal.name}</p>}
      <div aria-live="polite" className="flex flex-col gap-3">
        {error && <p role="alert" className="m-0 rounded-2xl bg-tint-pink px-4 py-3 text-body-sm font-bold text-bubbles-pink-deep">{error}</p>}
        {!parsed && !error && <Skeleton className="h-16 w-full rounded-2xl" />}
        {parsed && (
          <>
            <p className="m-0 text-body">Bubbles will add about <RangeBadge value={parsed.totals.kcal} low={parsed.totals.kcal_low} high={parsed.totals.kcal_high} /> to today, as you ate it.</p>
            {parsed.warnings.length > 0 && <Notice tone="sun" title="Worth a look">{parsed.warnings.join(" ")}</Notice>}
            {parsed.unrecognised.length > 0 && <p className="m-0 text-body-sm text-muted">Not counted: {parsed.unrecognised.join(", ")}</p>}
          </>
        )}
      </div>
      <div className="flex flex-wrap gap-2">
        <button type="button" onClick={() => void confirm()} disabled={!parsed || busy} className={BTN_PRIMARY}>{busy ? "Saving…" : "Yes, log it"}</button>
        <button type="button" onClick={onClose} className={BTN_SECONDARY}>Not now</button>
      </div>
      <p className="m-0 text-body-sm text-muted">If you ate it differently, use Calories and describe it your way.</p>
    </Sheet>
  );
}

/* ── Grocery list ───────────────────────────────────────────────────── */

function Grocery({ created }: { created?: string }) {
  const send = useSend();
  const [people, setPeople] = useState("1");
  const [aisles, setAisles] = useState<Record<string, GroceryItem[]> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [ticks, setTicks] = useState<Record<string, boolean>>({});
  const key = groceryKey(created);

  useEffect(() => {
    try {
      setTicks(parseTicks(window.localStorage.getItem(key)));
    } catch {
      // storage unavailable: ticks last for this visit only
    }
  }, [key]);

  const load = useCallback(async () => {
    setError(null);
    const r = await send<{ aisles: Record<string, GroceryItem[]> }>(`/fitness/diet/grocery?people=${people}`, "GET");
    if (r.ok) setAisles(r.data.aisles);
    else setError(r.message);
  }, [send, people]);

  useEffect(() => {
    if (open) void load();
  }, [open, load]);

  function toggle(id: string, on: boolean) {
    setTicks((t) => {
      const next = { ...t };
      if (on) next[id] = true;
      else delete next[id];
      try {
        window.localStorage.setItem(key, JSON.stringify(next));
      } catch {
        // not saved; still ticked on screen
      }
      return next;
    });
  }

  return (
    <Section title="Grocery list" aside={<button type="button" className={BTN_SECONDARY} aria-expanded={open} onClick={() => setOpen((o) => !o)}>{open ? "Hide list" : "Show list"}</button>}>
      {!open ? (
        <p className="m-0 text-body-sm text-muted">Everything in this week&rsquo;s plan, grouped by aisle, with approximate amounts.</p>
      ) : (
        <div className="flex flex-col gap-4">
          <SelectField id="people" label="Shopping for" value={people} onChange={setPeople} options={[1, 2, 3, 4, 5, 6].map((n) => ({ value: String(n), label: n === 1 ? "1 person" : `${n} people` }))} />
          {error && <ErrorCard inset title="Couldn't load the list" message={error} onRetry={() => void load()} />}
          {!aisles && !error && <Skeleton className="h-32 w-full rounded-2xl" />}
          {aisles && Object.entries(aisles).map(([aisle, items]) => (
            <fieldset key={aisle} className="m-0 min-w-0 border-0 p-0">
              <legend className="mb-1 p-0 font-display text-h4 text-ink">{aisle}</legend>
              <ul className="m-0 list-none p-0">
                {items.map((it) => {
                  const id = `${aisle}|${it.food}`;
                  const on = ticks[id] === true;
                  return (
                    <li key={id}>
                      <label className="flex min-h-[44px] cursor-pointer items-center gap-3 text-body">
                        <input type="checkbox" checked={on} onChange={(e) => toggle(id, e.target.checked)} className="h-6 w-6 shrink-0 accent-[var(--bubbles-grape)]" />
                        <span className={on ? "text-muted line-through" : "text-ink"}>
                          <span className="font-bold">{it.food}</span> · {it.quantity}
                          {it.note && <span className="text-body-sm text-muted"> ({it.note})</span>}
                        </span>
                      </label>
                    </li>
                  );
                })}
              </ul>
            </fieldset>
          ))}
          {aisles && <button type="button" className={BTN_GHOST} onClick={() => { setTicks({}); try { window.localStorage.removeItem(key); } catch { /* nothing saved to clear */ } }}>Clear ticks</button>}
          <p className="m-0 text-body-sm text-muted">Quantities are approximate. Raw weights of grains and pulses are estimated.</p>
        </div>
      )}
    </Section>
  );
}
