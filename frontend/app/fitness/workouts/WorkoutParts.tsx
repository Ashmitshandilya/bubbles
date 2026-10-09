"use client";

import { useCallback, useEffect, useState } from "react";
import { BTN_PRIMARY, BTN_SECONDARY, CARD, ErrorCard, Skeleton, useBubblesQuery } from "../../../components/hub/HubKit";
import {
  BTN_GHOST, Chip, CheckRow, EstimateLabel, Field, INPUT, LiveMessage, Notice, Section, SelectField, Sheet, useSend,
} from "../../../components/fitness/ui";
import { fmt, formatRange } from "../../lib/fitness-calc";
import { formatWhen } from "../../lib/dates";
import type { Exercise, Move, Session, WorkoutLogDay, WorkoutPlan, WorkoutPlanDoc } from "../../lib/fitness-types";

/* The stop message is written here as well as by the server: if the network is slow, safety advice must not wait on it. */
const STOP_TEXT = "Please stop exercising. If you have chest pain, fainting, severe dizziness or severe pain, get medical help now. Call your local emergency number if it does not settle.";

interface AdaptResult { session: Session; stop: boolean; messages: string[]; next_step?: string | null }

function moveLine(m: Move): string {
  if (m.sets && m.reps) return `${m.sets} × ${m.reps}${m.rest_s ? `, rest ${m.rest_s}s` : ""}`;
  if (m.sets && m.seconds) return `${m.sets} × ${m.seconds}s`;
  if (m.seconds) return `${m.seconds}s`;
  if ((m as { minutes?: number }).minutes) return `${(m as { minutes?: number }).minutes} min`;
  return "";
}

function MoveList({ title, moves }: { title: string; moves: Move[] }) {
  if (!moves.length) return null;
  return (
    <div>
      <h4 className="m-0 mb-1 text-label font-extrabold uppercase tracking-wide text-subtle">{title}</h4>
      <ul className="m-0 flex list-none flex-col gap-2 p-0">
        {moves.map((m, i) => (
          <li key={`${m.id}-${i}`} className="rounded-2xl bg-blush px-3 py-2">
            <p className="m-0 flex flex-wrap items-baseline justify-between gap-2 text-body font-extrabold text-ink">
              <span>{m.name}</span>
              <span className="text-body-sm text-muted">{moveLine(m)}</span>
            </p>
            {m.cue && <p className="m-0 text-body-sm text-ink-soft">{m.cue}</p>}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function PlanView({ doc, plan, reload, onRemake }: { doc: WorkoutPlanDoc; plan: WorkoutPlan; reload: () => void; onRemake: () => void }) {
  const send = useSend();
  const [adapt, setAdapt] = useState<number | null>(null);
  const [adapted, setAdapted] = useState<Record<number, AdaptResult>>({});
  const [log, setLog] = useState<{ title: string; minutes: number } | null>(null);
  const [next, setNext] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [historyKey, setHistoryKey] = useState(0);

  async function nextWeek() {
    setNext(true);
    setError(null);
    const r = await send("/fitness/workouts/plan", "POST", { next_week: true, ...(doc.params ?? {}) });
    setNext(false);
    if (r.ok) {
      setAdapted({});
      setNote("Next week is ready. Bubbles nudged things up a little where it makes sense.");
      reload();
    } else setError(r.message);
  }

  return (
    <>
      <Section
        title={`Week ${plan.week_index}${plan.deload ? ", an easier week" : ""}`}
        aside={<EstimateLabel />}
      >
        <p className="m-0 text-body-sm text-muted">
          About {plan.summary.moderate_equivalent_minutes} minutes of moderate movement and {plan.summary.strength_days} strength {plan.summary.strength_days === 1 ? "day" : "days"} this week
          {plan.summary.meets_who ? ", which matches general WHO guidance." : ". General WHO guidance is 150 minutes, so this is a gentle build, not a shortfall."}
        </p>
        {plan.notes.map((n) => <p key={n} className="m-0 mt-2 text-body-sm text-ink-soft">{n}</p>)}
        {plan.mode === "clinician_first" && <p className="m-0 mt-2 text-body-sm font-bold text-ink">This week is limited to easy walking and mobility until a clinician has said more is fine.</p>}
        <div className="mt-4 flex flex-wrap gap-2">
          <button type="button" className={BTN_PRIMARY} onClick={() => void nextWeek()} disabled={next}>{next ? "Planning…" : "Next week"}</button>
          <button type="button" className={BTN_SECONDARY} onClick={onRemake}>Change my plan</button>
        </div>
        <div aria-live="polite" className="mt-3">
          {error && <p role="alert" className="m-0 rounded-2xl bg-tint-pink px-4 py-3 text-body-sm font-bold text-bubbles-pink-deep">{error}</p>}
          {note && !error && <LiveMessage message={note} />}
        </div>
      </Section>

      <ol className="m-0 flex list-none flex-col gap-4 p-0" aria-label="This week's sessions">
        {plan.sessions.map((s, i) => {
          const a = adapted[i];
          const shown = a ? a.session : s;
          return (
            <li key={`${s.day}-${i}`} className={`${CARD} flex flex-col gap-3 p-4 sm:p-5`}>
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <p className="m-0 text-label font-extrabold uppercase tracking-wide text-subtle">{s.day}</p>
                  <h3 className="m-0 font-display text-h3 text-ink">{s.label}</h3>
                </div>
                <p className="m-0 text-body-sm text-muted">{shown.minutes} min · about {fmt(s.kcal_estimate)} kcal burn <EstimateLabel /></p>
              </div>
              {a && !a.stop && <Notice tone="mint" title="Adapted for today">{a.messages.join(" ")}</Notice>}
              {a?.stop ? <StopCard /> : (
                <details open={i === 0}>
                  <summary className="inline-flex min-h-[44px] cursor-pointer items-center text-body-sm font-extrabold text-bubbles-grape-deep">Show the moves</summary>
                  <div className="mt-2 flex flex-col gap-4">
                    <MoveList title="Warm-up" moves={shown.warmup} />
                    <MoveList title="Main" moves={shown.main} />
                    <MoveList title="Cool-down" moves={shown.cooldown} />
                  </div>
                </details>
              )}
              <div className="flex flex-wrap gap-2">
                <button type="button" className={BTN_SECONDARY} onClick={() => setAdapt(i)} aria-label={`Adapt ${s.day} ${s.label}`}>Adapt</button>
                <button type="button" className={BTN_SECONDARY} onClick={() => setLog({ title: s.label, minutes: shown.minutes })} aria-label={`Log ${s.day} ${s.label}`}>Log this session</button>
              </div>
            </li>
          );
        })}
      </ol>

      <AdaptSheet
        open={adapt !== null}
        onClose={() => setAdapt(null)}
        index={adapt ?? 0}
        onResult={(r) => { if (adapt !== null) setAdapted((m) => ({ ...m, [adapt]: r })); setAdapt(null); }}
      />
      <LogSheet seed={log} onClose={() => setLog(null)} onLogged={() => { setNote("Logged. Any movement counts."); setHistoryKey((k) => k + 1); }} />
      <History key={historyKey} />
      <Library />
    </>
  );
}

export function StopCard() {
  return (
    <div role="alert" className="rounded-3xl border-2 border-bubbles-urgent bg-tint-urgent p-5">
      <p className="m-0 font-display text-h4 text-ink">Stop for now and get help</p>
      <p className="m-0 mt-1 text-body text-ink">{STOP_TEXT}</p>
      <p className="m-0 mt-2 text-body-sm text-ink-soft">Bubbles can&rsquo;t judge what is happening in your body. Please talk to a doctor before you do any more exercise.</p>
    </div>
  );
}

/* ── Adapt ──────────────────────────────────────────────────────────── */

const AREAS = ["knee", "lower back", "shoulder", "wrist", "neck", "ankle", "hip"];

function AdaptSheet({ open, onClose, index, onResult }: { open: boolean; onClose: () => void; index: number; onResult: (r: AdaptResult) => void }) {
  const send = useSend();
  const [pain, setPain] = useState(false);
  const [area, setArea] = useState("knee");
  const [severity, setSeverity] = useState(3);
  const [lowEnergy, setLowEnergy] = useState(false);
  const [poorSleep, setPoorSleep] = useState(false);
  const [heavyPeriod, setHeavyPeriod] = useState(false);
  const [minutes, setMinutes] = useState("");
  const [stop, setStop] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      setStop(false);
      setError(null);
    }
  }, [open]);

  async function apply() {
    setBusy(true);
    setError(null);
    const feedback: Record<string, unknown> = { low_energy: lowEnergy, poor_sleep: poorSleep, heavy_period: heavyPeriod };
    if (pain) Object.assign(feedback, { pain: true, pain_area: area, pain_severity: severity });
    const r = await send<AdaptResult>("/fitness/workouts/adapt", "POST", { session: index, feedback, ...(minutes ? { minutes: Number(minutes) } : {}) });
    setBusy(false);
    if (r.ok) onResult(r.data);
    else setError(r.message);
  }

  return (
    <Sheet open={open} onClose={onClose} title="How are you today?">
      {stop ? (
        <>
          <StopCard />
          <button type="button" onClick={onClose} className={BTN_SECONDARY}>Close</button>
        </>
      ) : (
        <>
          <p className="m-0 text-body-sm text-muted">Tell Bubbles and it will adjust this session. Lighter days still count.</p>
          <div className="flex flex-col">
            <CheckRow id="ad-low" checked={lowEnergy} onChange={setLowEnergy}>Low energy</CheckRow>
            <CheckRow id="ad-sleep" checked={poorSleep} onChange={setPoorSleep}>I slept badly</CheckRow>
            <CheckRow id="ad-period" checked={heavyPeriod} onChange={setHeavyPeriod}>Heavy period day</CheckRow>
            <CheckRow id="ad-pain" checked={pain} onChange={setPain}>Something hurts</CheckRow>
          </div>
          {pain && (
            <div className="flex flex-col gap-3 rounded-2xl bg-blush p-4">
              <SelectField id="ad-area" label="Where?" value={area} onChange={setArea} options={AREAS.map((a) => ({ value: a, label: a[0].toUpperCase() + a.slice(1) }))} />
              <Field id="ad-sev" label={`How strong? ${severity} out of 10`}>
                <input id="ad-sev" type="range" min={1} max={10} value={severity} onChange={(e) => setSeverity(Number(e.target.value))} className="h-11 w-full accent-[var(--bubbles-grape)]" />
              </Field>
              <p className="m-0 text-body-sm text-muted">Strong pain (7 or more) stops the session. If it lasts more than a few days, see a clinician.</p>
            </div>
          )}
          <SelectField id="ad-min" label="Time available" optional value={minutes} onChange={setMinutes} options={[{ value: "", label: "As planned" }, ...[10, 15, 20, 30, 45].map((n) => ({ value: String(n), label: `${n} minutes` }))]} />
          <div className="rounded-2xl border-2 border-line p-4">
            <p className="m-0 mb-2 text-body-sm font-extrabold text-ink">Is something scary happening?</p>
            <div className="flex flex-wrap gap-2">
              <button type="button" className={BTN_SECONDARY} onClick={() => setStop(true)}>Chest pain</button>
              <button type="button" className={BTN_SECONDARY} onClick={() => setStop(true)}>Dizzy</button>
              <button type="button" className={BTN_SECONDARY} onClick={() => setStop(true)}>I fainted</button>
            </div>
          </div>
          <div aria-live="polite">{error && <p role="alert" className="m-0 rounded-2xl bg-tint-pink px-4 py-3 text-body-sm font-bold text-bubbles-pink-deep">{error}</p>}</div>
          <button type="button" onClick={() => void apply()} disabled={busy} className={BTN_PRIMARY}>{busy ? "Adjusting…" : "Adapt this session"}</button>
        </>
      )}
    </Sheet>
  );
}

/* ── Log a session ──────────────────────────────────────────────────── */

const ACTIVITIES = [
  { value: "strength_light", label: "Strength" },
  { value: "walking_brisk", label: "Brisk walk" },
  { value: "walking_slow", label: "Easy walk" },
  { value: "jogging", label: "Jog" },
  { value: "cycling_easy", label: "Cycling" },
  { value: "yoga", label: "Yoga" },
  { value: "hiit", label: "Interval training" },
  { value: "dance", label: "Dance" },
  { value: "swimming_easy", label: "Swimming" },
];

interface LoggedSession { session: { title: string; minutes: number; burn: { kcal: number; kcal_low: number; kcal_high: number } } }

function LogSheet({ seed, onClose, onLogged }: { seed: { title: string; minutes: number } | null; onClose: () => void; onLogged: () => void }) {
  const send = useSend();
  const [title, setTitle] = useState("");
  const [minutes, setMinutes] = useState("");
  const [activity, setActivity] = useState("strength_light");
  const [rpe, setRpe] = useState(5);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<LoggedSession["session"] | null>(null);

  useEffect(() => {
    if (seed) {
      setTitle(seed.title);
      setMinutes(String(seed.minutes));
      setError(null);
      setDone(null);
    }
  }, [seed]);

  async function save() {
    setBusy(true);
    setError(null);
    const r = await send<LoggedSession>("/fitness/workouts/log", "POST", { title, activity, minutes: Number(minutes), rpe });
    setBusy(false);
    if (r.ok) {
      setDone(r.data.session);
      onLogged();
    } else setError(r.message);
  }

  return (
    <Sheet open={seed !== null} onClose={onClose} title="Log a session">
      {done ? (
        <>
          <p className="m-0 text-body text-ink" aria-live="polite">
            Logged <strong>{done.title}</strong> for {done.minutes} minutes. Estimated burn about {formatRange(done.burn.kcal_low, done.burn.kcal_high)} <EstimateLabel>Estimate</EstimateLabel>
          </p>
          <p className="m-0 text-body-sm text-muted">Burn estimates vary a lot between people. Bubbles only counts part of it towards your day, so you are never nudged to eat less.</p>
          <button type="button" onClick={onClose} className={BTN_PRIMARY}>Done</button>
        </>
      ) : (
        <form noValidate onSubmit={(e) => { e.preventDefault(); void save(); }} className="flex flex-col gap-4">
          <Field id="lg-title" label="What did you do?"><input id="lg-title" value={title} maxLength={100} onChange={(e) => setTitle(e.target.value)} className={INPUT} /></Field>
          <SelectField id="lg-act" label="Closest type" value={activity} onChange={setActivity} options={ACTIVITIES} hint="Used only for the burn estimate." />
          <Field id="lg-min" label="Minutes"><input id="lg-min" type="number" inputMode="numeric" min={1} max={600} value={minutes} onChange={(e) => setMinutes(e.target.value)} className={INPUT} /></Field>
          <Field id="lg-rpe" label={`How hard did it feel? ${rpe} out of 10`} hint="1 is very easy, 10 is as hard as it gets.">
            <input id="lg-rpe" type="range" min={0} max={10} value={rpe} onChange={(e) => setRpe(Number(e.target.value))} className="h-11 w-full accent-[var(--bubbles-grape)]" />
          </Field>
          <div aria-live="polite">{error && <p role="alert" className="m-0 rounded-2xl bg-tint-pink px-4 py-3 text-body-sm font-bold text-bubbles-pink-deep">{error}</p>}</div>
          <button type="submit" disabled={busy || !title.trim() || !minutes} className={BTN_PRIMARY}>{busy ? "Saving…" : "Save session"}</button>
        </form>
      )}
    </Sheet>
  );
}

/* ── History ────────────────────────────────────────────────────────── */

function History() {
  const [q, reload] = useBubblesQuery<{ days: WorkoutLogDay[] }>("/fitness/workouts/log?days=30");
  return (
    <Section title="Recent sessions">
      {q.status === "loading" ? <Skeleton className="h-20 w-full rounded-2xl" /> : q.status === "error" ? (
        <ErrorCard inset title="Couldn't load history" message={q.message} onRetry={reload} />
      ) : q.data.days.length === 0 ? (
        <p className="m-0 text-body-sm text-muted">No sessions logged yet. When you do one, it will show up here.</p>
      ) : (
        <ul className="m-0 flex list-none flex-col gap-2 p-0">
          {q.data.days.flatMap((d) => d.sessions.map((s) => (
            <li key={s.id} className="flex flex-wrap items-baseline justify-between gap-2 rounded-2xl bg-blush px-3 py-2 text-body-sm">
              <span><strong className="text-ink">{s.title}</strong> · {formatWhen(d.date)}</span>
              <span className="text-muted">{Math.round(s.minutes)} min{s.rpe != null ? ` · effort ${s.rpe}/10` : ""} · about {fmt(s.kcal_estimate)} kcal</span>
            </li>
          )))}
        </ul>
      )}
    </Section>
  );
}

/* ── Exercise library ───────────────────────────────────────────────── */

const CATEGORIES = ["strength", "cardio", "core", "mobility"];

function Library() {
  const send = useSend();
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [cat, setCat] = useState("");
  const [rows, setRows] = useState<Exercise[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    const r = await send<{ exercises: Exercise[] }>(`/fitness/exercises?q=${encodeURIComponent(text.trim())}&category=${encodeURIComponent(cat)}`, "GET");
    if (r.ok) setRows(r.data.exercises);
    else setError(r.message);
  }, [send, text, cat]);

  useEffect(() => {
    if (!open) return;
    const id = window.setTimeout(() => void load(), 250);
    return () => window.clearTimeout(id);
  }, [open, load]);

  return (
    <Section title="Exercise library" aside={<button type="button" className={BTN_SECONDARY} aria-expanded={open} onClick={() => setOpen((o) => !o)}>{open ? "Hide" : "Browse"}</button>}>
      {!open ? (
        <p className="m-0 text-body-sm text-muted">Look up any move and its form cue.</p>
      ) : (
        <div className="flex flex-col gap-4">
          <Field id="lib-q" label="Search"><input id="lib-q" type="search" value={text} onChange={(e) => setText(e.target.value)} placeholder="squat, plank, stretch…" className={INPUT} /></Field>
          <div role="group" aria-label="Category" className="flex flex-wrap gap-2">
            <Chip on={cat === ""} onClick={() => setCat("")}>All</Chip>
            {CATEGORIES.map((c) => <Chip key={c} on={cat === c} onClick={() => setCat(c)}>{c[0].toUpperCase() + c.slice(1)}</Chip>)}
          </div>
          <div aria-live="polite">
            {error && <ErrorCard inset title="Couldn't load moves" message={error} onRetry={() => void load()} />}
            {!rows && !error && <Skeleton className="h-24 w-full rounded-2xl" />}
            {rows && rows.length === 0 && <p className="m-0 text-body-sm text-muted">No moves match. Try a different word.</p>}
          </div>
          {rows && rows.length > 0 && (
            <ul className="m-0 flex list-none flex-col gap-2 p-0">
              {rows.map((m) => (
                <li key={m.id} className="rounded-2xl bg-blush px-3 py-2">
                  <p className="m-0 flex flex-wrap items-baseline justify-between gap-2 font-extrabold text-ink"><span>{m.name}</span><span className="text-body-sm font-bold text-muted">{m.category} · level {m.level}</span></p>
                  <p className="m-0 text-body-sm text-ink-soft">{m.cue}</p>
                </li>
              ))}
            </ul>
          )}
          <button type="button" className={BTN_GHOST} onClick={() => setOpen(false)}>Close the library</button>
        </div>
      )}
    </Section>
  );
}
