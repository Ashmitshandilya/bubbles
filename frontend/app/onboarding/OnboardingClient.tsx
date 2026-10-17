"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { BubblesMascot } from "../../components/BubblesMascot";
import { resetExperience, useApi, useAuth } from "../../components/Providers";
import { DateField, Stepper, TextArea, TextField } from "../../components/tracking/kit";
import { changeBody, readOverview, type ConsentPurpose } from "../lib/consents";
import { ChoicesStep, OFFERED_PURPOSES } from "./ChoicesStep";
import { Creating } from "./Creating";
import {
  advancesOnPick, ageOn, buildScreens, isAnswered, isRequired, missingRequired, pendingPatch, pick, picked, progressLabel, resumeIndex, screenQuestions,
  titleFor, visibleOptions, type Answers, type Question, type Screen,
} from "./flow";

interface Bank {
  questions: Question[];
  screens: Record<string, string>;
  titlesHi: Record<string, string>;
}

type Phase = "loading" | "error" | "form" | "creating" | "under18";
type Failure = { field?: string; message: string };
type Sync = { ok: boolean; safety?: boolean };

const BUTTON = "bubbles-press bubbles-glow inline-flex min-h-[56px] items-center justify-center rounded-full bg-bubbles-pink-ink px-8 text-[1.0625rem] font-extrabold text-white disabled:cursor-wait disabled:opacity-70";
const GHOST = "bubbles-press inline-flex min-h-[52px] items-center justify-center rounded-full border border-line bg-surface px-6 font-extrabold text-ink-soft";
const LINK = "bubbles-press inline-flex min-h-[44px] items-center justify-center rounded-full bg-transparent px-4 text-body-sm font-extrabold text-ink-soft underline underline-offset-4";
const CHIP_ON = "border-bubbles-pink-ink bg-tint-pink text-bubbles-pink-deep";
const CHIP_OFF = "border-line bg-surface text-muted hover:border-line-strong hover:text-default";

/** The server's urgent text is a few headings and bullets: show it as plain paragraphs and a list. */
function SafetyText({ message }: { message: string }) {
  const rows = message.split("\n").map((row) => row.trim()).filter(Boolean);
  return (
    <div className="mt-2 flex flex-col gap-2">
      {rows.map((row, i) =>
        row.startsWith("#") ? <h3 key={i} className="m-0 text-body font-extrabold text-ink">{row.replace(/^#+\s*/, "")}</h3>
          : row.startsWith("- ") ? <p key={i} className="m-0 pl-3 text-body-sm text-ink-soft">• {row.slice(2)}</p>
          : <p key={i} className="m-0 text-body-sm text-ink-soft">{row}</p>,
      )}
    </div>
  );
}

/** Marks a question that has to be answered, instead of labelling every other one "(optional)". */
function Needed() {
  return (
    <span className="mb-2 inline-flex items-center gap-1 rounded-full bg-blush px-2.5 py-0.5 text-chip font-extrabold text-ink-soft">
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <rect x="5" y="11" width="14" height="9" rx="2" /><path d="M8 11V8a4 4 0 0 1 8 0v3" />
      </svg>
      Needed
    </span>
  );
}

function ChipGroup({ q, title, hint, value, options, error, onPick }: {
  q: Question; title: string; hint: string; value: unknown; options: { id: string; label: string }[]; error?: string; onPick: (optionId: string) => void;
}) {
  const chosen = picked(value);
  return (
    <fieldset id={`q-${q.id}`} aria-invalid={error ? true : undefined} className="m-0 flex min-w-0 flex-col gap-2 border-0 p-0">
      <legend className="mb-2 p-0 text-body font-extrabold">{title}</legend>
      {hint && <p className="m-0 mb-1 text-body-sm font-semibold text-muted">{hint}</p>}
      <div className="flex flex-wrap gap-2">
        {options.map((o) => {
          const on = chosen.includes(o.id);
          return (
            <button key={o.id} type="button" aria-pressed={on} onClick={() => onPick(o.id)}
              className={`bubbles-press min-h-[48px] rounded-full border px-4 text-body-sm font-extrabold leading-tight ${on ? CHIP_ON : CHIP_OFF}`}>
              {o.label}
            </button>
          );
        })}
      </div>
      {error && <p role="alert" className="m-0 text-body-sm font-bold text-bubbles-urgent">{error}</p>}
    </fieldset>
  );
}

/** The browser's language as the starting answer: Hindi for a Hindi browser, English otherwise. The row on the first screen changes it. */
function browserLanguage(): string {
  return typeof navigator !== "undefined" && navigator.language?.toLowerCase().startsWith("hi") ? "hindi" : "english";
}

export function OnboardingClient() {
  const router = useRouter();
  const { loading, session, user, signOut } = useAuth();
  const { fetchBubbles } = useApi();
  const [phase, setPhase] = useState<Phase>("loading");
  const [problem, setProblem] = useState("");
  const [bank, setBank] = useState<Bank | null>(null);
  const [answers, setAnswersState] = useState<Answers>({});
  const [screenId, setScreenId] = useState("first");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [safety, setSafety] = useState<{ field: string; message: string } | null>(null);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState("");
  const [editing, setEditing] = useState(false);
  const [purposes, setPurposes] = useState<ConsentPurpose[] | null>(null);
  const [choicesFailed, setChoicesFailed] = useState(false);
  const [choicesOn, setChoicesOn] = useState<ReadonlySet<string>>(new Set());
  const [choicesNote, setChoicesNote] = useState("");
  const heading = useRef<HTMLHeadingElement>(null);
  const today = useMemo(() => new Date(), []);
  // Auto-advancing taps save in the background, one at a time, from what has changed since the last save.
  const answersRef = useRef<Answers>({});
  const savedRef = useRef<Answers>({});
  const stepRef = useRef(1);
  const chain = useRef<Promise<Sync>>(Promise.resolve({ ok: true }));

  const setAnswers = useCallback((update: (prev: Answers) => Answers) => {
    answersRef.current = update(answersRef.current);
    setAnswersState(answersRef.current);
  }, []);

  useEffect(() => {
    if (!loading && !session) router.replace("/login");
  }, [loading, session, router]);

  const load = useCallback(async () => {
    setPhase("loading");
    setProblem("");
    try {
      const [bankResponse, stateResponse] = await Promise.all([fetchBubbles("/onboarding/questions"), fetchBubbles("/onboarding/state")]);
      if (!bankResponse.ok || !stateResponse.ok) throw new Error("load");
      const bankJson = await bankResponse.json();
      const state = await stateResponse.json();
      const edit = new URLSearchParams(window.location.search).get("edit") === "1";
      setEditing(edit);
      if (state.under_18) {
        setPhase("under18");
        return;
      }
      if (state.complete && !edit) {
        router.replace("/dashboard");
        return;
      }
      const loaded: Bank = { questions: bankJson.questions, screens: bankJson.screens ?? {}, titlesHi: bankJson.titles_hi ?? {} };
      setBank(loaded);
      const server: Answers = state.answers ?? {};
      const start: Answers = { ...server, ...(server.language ? {} : { language: browserLanguage() }) };
      answersRef.current = start;
      setAnswersState(start);
      savedRef.current = Object.fromEntries(Object.entries(server).filter(([k]) => !(state.prefilled ?? []).includes(k)));
      const screens = buildScreens(loaded.questions, loaded.screens, start, today, edit);
      setScreenId(edit ? screens[0]?.id ?? "first" : screens[resumeIndex(screens, loaded.questions, start, Number(state.step) >= 2, today)]?.id ?? "first");
      setPhase("form");
    } catch {
      setProblem("Bubbles couldn't load the setup just now. Your connection may be slow, or Bubbles may be waking up.");
      setPhase("error");
    }
  }, [fetchBubbles, router, today]);

  useEffect(() => {
    if (session) void load();
  }, [session, load]);

  useEffect(() => {
    heading.current?.focus();
  }, [screenId, phase]);

  const screens = useMemo(() => (bank ? buildScreens(bank.questions, bank.screens, answers, today, editing) : []), [bank, answers, today, editing]);
  const index = Math.max(0, screens.findIndex((s) => s.id === screenId));
  const screen: Screen | undefined = screens[index];
  const qs = bank?.questions ?? [];
  const screenQs = screen ? screenQuestions(screen, qs) : [];
  const language = answers.language;
  const last = index === screens.length - 1;

  // The choices are read when that step is reached, not before.
  useEffect(() => {
    if (screen?.kind !== "choices" || purposes || choicesFailed) return;
    let alive = true;
    (async () => {
      try {
        const response = await fetchBubbles("/consents");
        const overview = response.ok ? readOverview(await response.json()) : null;
        if (!alive) return;
        const offered = (overview?.purposes ?? []).filter((p) => p.available && (OFFERED_PURPOSES as readonly string[]).includes(p.id));
        if (!offered.length) throw new Error("none");
        setPurposes(offered);
        setChoicesOn(new Set(offered.filter((p) => p.granted).map((p) => p.id)));
      } catch {
        if (alive) setChoicesFailed(true);
      }
    })();
    return () => { alive = false; };
  }, [screen?.kind, purposes, choicesFailed, fetchBubbles]);

  const set = (id: string, value: unknown) => {
    setAnswers((prev) => {
      const next = { ...prev };
      if (value === undefined || value === "") delete next[id];
      else next[id] = value;
      return next;
    });
    setErrors((prev) => (prev[id] ? { ...prev, [id]: "" } : prev));
  };

  async function failureOf(response: Response): Promise<Failure> {
    try {
      const body = await response.json();
      const detail = body?.detail;
      if (detail && typeof detail === "object") return { field: typeof detail.field === "string" ? detail.field : undefined, message: String(detail.message ?? "Please check your answer.") };
      if (typeof detail === "string") return { message: detail };
    } catch {
      /* fall through */
    }
    return { message: "Bubbles couldn't save that just now. Please try again." };
  }

  /** Sends what changed for the screens up to `upTo`. Runs one at a time so a quick second tap cannot overtake the first. */
  function sync(list: readonly Screen[], upTo: number): Promise<Sync> {
    const run = async (): Promise<Sync> => {
      if (!bank) return { ok: true };
      const patch = pendingPatch(list, upTo, bank.questions, answersRef.current, savedRef.current, today);
      if (!patch || Object.keys(patch).length === 0) return { ok: true };
      try {
        const response = await fetchBubbles("/onboarding/answers", { method: "PUT", body: JSON.stringify({ answers: patch, step: stepRef.current }) });
        if (!response.ok) {
          const failure = await failureOf(response);
          if (response.status === 403 && failure.message.includes("18")) {
            setPhase("under18");
            return { ok: false };
          }
          if (failure.field) {
            setErrors({ [failure.field]: failure.message });
            const home = list.find((s) => s.ids.includes(failure.field!));
            if (home) setScreenId(home.id);
          } else setNotice(failure.message);
          return { ok: false };
        }
        const result = await response.json();
        if (result.under_18) {
          setPhase("under18");
          return { ok: false };
        }
        savedRef.current = result.answers ?? { ...savedRef.current, ...patch };
        const dropped: string[] = result.dropped ?? [];
        if (dropped.length) setAnswers((prev) => Object.fromEntries(Object.entries(prev).filter(([k]) => !dropped.includes(k))));
        if (result.safety) {
          setAnswers((prev) => Object.fromEntries(Object.entries(prev).filter(([k]) => k !== result.safety.field)));
          setSafety({ field: result.safety.field, message: result.safety.message });
          setNotice("Thank you for telling Bubbles. That part wasn't saved. You can carry on when you are ready.");
          return { ok: false, safety: true };
        }
        setSafety(null);
        setNotice("");
        return { ok: true };
      } catch {
        setNotice("Bubbles couldn't reach the server. Your answers are still here: please try again.");
        return { ok: false };
      }
    };
    chain.current = chain.current.then(run);
    return chain.current;
  }

  const stageStep = (s: Screen | undefined) => (s?.stage === "core" ? 1 : s?.stage === "extras" ? 2 : 3);

  /** The screen after the current one, looked up again from `withAnswers` (an answer can add or remove screens). */
  function followingScreen(withAnswers: Answers): { list: Screen[]; at: number } {
    const list = bank ? buildScreens(bank.questions, bank.screens, withAnswers, today, editing) : [];
    return { list, at: list.findIndex((s) => s.id === screenId) };
  }

  function finish() {
    setPhase("creating");
  }

  async function finishWithSave() {
    setSaving(true);
    setNotice("");
    const outcome = await sync(screens, screens.length - 1);
    setSaving(false);
    if (outcome.ok) finish();
  }

  /** Next / Skip: saves this screen, then moves on (or finishes after the last one). */
  async function next(withAnswers: Answers = answersRef.current) {
    if (!bank || !screen) return;
    if (screen.kind === "questions") {
      const missing = missingRequired(screenQs, withAnswers, today);
      if (missing.length) {
        setErrors(Object.fromEntries(missing.map((id) => [id, "Please answer this one to continue."])));
        document.getElementById(`q-${missing[0]}`)?.scrollIntoView({ block: "center", behavior: "smooth" });
        return;
      }
    }
    stepRef.current = stageStep(screen);
    const { list, at } = followingScreen(withAnswers);
    const following = list[at + 1];
    setSaving(true);
    setNotice("");
    const outcome = await sync(list, Math.max(at, 0));
    setSaving(false);
    if (!outcome.ok) return;
    if (following) setScreenId(following.id);
    else finish();
  }

  /** A single-choice tap: record it and, when nothing else on the screen is waiting, move on at once while the save runs behind it. */
  function onPick(q: Question, optionId: string) {
    const value = pick(q, answersRef.current[q.id], optionId);
    set(q.id, value);
    if (!screen || !bank) return;
    const withAnswers = { ...answersRef.current };
    if (value === undefined) delete withAnswers[q.id];
    if (!advancesOnPick(screen, bank.questions, q.id, withAnswers)) return;
    // the first screen only moves on once the date of birth can be checked, so it waits for nothing: it just moves
    if (ageOn(withAnswers.birth_date, today) !== null) {
      const { list, at } = followingScreen(withAnswers);
      const following = list[at + 1];
      stepRef.current = stageStep(screen);
      void sync(list, Math.max(at, 0));
      if (following) setScreenId(following.id);
      else void finishWithSave();
    } else {
      const { list, at } = followingScreen(withAnswers);
      if (list[at + 1]) setScreenId(list[at + 1].id);
    }
  }

  function back() {
    setNotice("");
    const previous = screens[index - 1];
    if (previous) setScreenId(previous.id);
  }

  async function saveChoices(granted: ReadonlySet<string>) {
    if (!purposes) {
      advanceFromChoices();
      return;
    }
    setSaving(true);
    const results = await Promise.allSettled(purposes.map(async (p) => {
      const wanted = granted.has(p.id);
      if (wanted === p.granted) return;                      // nothing changed for this one
      const response = await fetchBubbles(`/consents/${p.id}`, { method: "PUT", body: changeBody(p, wanted, "onboarding") });
      if (!response.ok) throw new Error(p.id);
    }));
    setSaving(false);
    setChoicesNote(results.some((r) => r.status === "rejected") ? "One of your choices didn't save. You can set it in Settings, under Privacy choices." : "");
    advanceFromChoices();
  }

  function advanceFromChoices() {
    const following = screens[index + 1];
    stepRef.current = 2;
    if (following) setScreenId(following.id);
    else void finishWithSave();
  }

  const run = useCallback(async () => {
    const response = await fetchBubbles("/onboarding/complete", { method: "POST", body: "{}" });
    if (!response.ok) throw new Error((await failureOf(response)).message);
    const body = await response.json();
    return { lines: (body.applied as { label: string }[]).map((a) => a.label) };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- failureOf has no state
  }, [fetchBubbles]);

  const open = useCallback(() => {
    resetExperience();
    router.replace("/dashboard");
  }, [router]);

  // ---------------------------------------------------------------------------------------------------------------------

  if (loading || !session || phase === "loading") {
    return (
      <main className="flex min-h-dvh items-center justify-center bg-blush">
        <div role="status" className="text-center">
          <BubblesMascot size={88} mood="thinking" className="mx-auto" />
          <p className="mt-4 text-body font-bold text-muted">Getting your setup ready…</p>
        </div>
      </main>
    );
  }

  if (phase === "error") {
    return (
      <main className="flex min-h-dvh items-center justify-center bg-blush px-5">
        <div role="alert" className="max-w-[440px] text-center">
          <BubblesMascot size={88} mood="calm" className="mx-auto" />
          <p className="mt-4 text-body text-muted">{problem}</p>
          <button type="button" onClick={() => void load()} className={`${BUTTON} mt-5`}>Try again</button>
        </div>
      </main>
    );
  }

  if (phase === "under18") {
    return (
      <main className="flex min-h-dvh items-center justify-center bg-blush px-5 py-10">
        <div className="bubbles-rise w-full max-w-[480px] text-center">
          <BubblesMascot size={104} mood="calm" className="mx-auto" />
          <h1 ref={heading} tabIndex={-1} className="mt-5 font-display text-h1 text-ink outline-none">Bubbles is for people 18 and over</h1>
          <p className="mt-3 text-body text-muted">
            For now Bubbles can only be used by adults. If you are younger, a parent, a school nurse or a doctor is a great person to talk to about your health.
            Nothing you entered has been saved.
          </p>
          <p className="mt-3 text-body-sm text-muted">Made a mistake with your date of birth? Sign out and start again, or write to hello@heybubbles.in and we will remove the account.</p>
          <div className="mt-6 flex flex-wrap justify-center gap-3">
            <button type="button" onClick={() => void signOut()} className={GHOST}>Sign out</button>
            <button type="button" onClick={() => { answersRef.current = {}; savedRef.current = {}; setAnswersState({}); setScreenId("first"); void load(); }} className={GHOST}>I entered it wrong</button>
          </div>
        </div>
      </main>
    );
  }

  if (phase === "creating") {
    return <Creating run={run} name={String(answers.preferred_name ?? user?.display_name ?? "")} note={choicesNote} editing={editing} onOpen={open} onBack={() => setPhase("form")} />;
  }

  function render(q: Question): ReactNode {
    const title = bank ? titleFor(q, language, bank.titlesHi) : q.title;
    const value = answers[q.id];
    const error = errors[q.id] || undefined;
    const needed = isRequired(q, answers, today);
    const control = ((): ReactNode => {
      if (q.type === "text") {
        const props = { id: `q-${q.id}`, label: title, value: typeof value === "string" ? value : "", onChange: (v: string) => set(q.id, v), hint: q.why || undefined, error, maxLength: q.maxlength };
        return (q.maxlength ?? 0) > 100 ? <TextArea {...props} /> : <TextField {...props} placeholder={q.id === "preferred_name" ? "Your first name" : undefined} />;
      }
      if (q.type === "date") {
        const max = q.id === "birth_date" || q.id === "last_period" || q.id === "baby_birth_date" ? today.toLocaleDateString("en-CA") : undefined;
        return <DateField id={`q-${q.id}`} label={title} value={typeof value === "string" ? value : ""} onChange={(v) => set(q.id, v)} hint={q.why || undefined} error={error} max={max} />;
      }
      if (q.type === "single" || q.type === "multi") {
        return <ChipGroup q={q} title={title} hint={q.why} value={value} error={error} options={visibleOptions(q, answers, today)} onPick={(id) => (q.type === "single" ? onPick(q, id) : set(q.id, pick(q, value, id)))} />;
      }
      if (q.type === "slider") {
        return (
          <Stepper id={`q-${q.id}`} label={title} value={value === undefined ? "" : String(value)} onChange={(v) => set(q.id, v === "" ? undefined : Number(v))}
            hint={q.why || undefined} error={error} min={q.min ?? 0} max={q.max ?? 100} step={q.increment ?? 1} unit={q.unit ?? ""} fallback={6} signal="pink" />
        );
      }
      if (q.type === "number_pair") {
        const pair = (value && typeof value === "object" ? value : {}) as { height_cm?: number; weight_kg?: number };
        const update = (key: "height_cm" | "weight_kg", raw: string) => {
          const nextPair = { ...pair };
          if (raw === "") delete nextPair[key];
          else nextPair[key] = Number(raw);
          set(q.id, Object.keys(nextPair).length ? nextPair : undefined);
        };
        return (
          <fieldset id={`q-${q.id}`} className="m-0 flex min-w-0 flex-col gap-4 border-0 p-0">
            <legend className="mb-2 p-0 text-body font-extrabold">{title}</legend>
            {q.why && <p className="m-0 text-body-sm font-semibold text-muted">{q.why}</p>}
            <Stepper id="q-height_cm" label="Height" value={pair.height_cm === undefined ? "" : String(pair.height_cm)} onChange={(v) => update("height_cm", v)} min={120} max={230} step={1} unit="cm" fallback={165} signal="pink" />
            <Stepper id="q-weight_kg" label="Weight" value={pair.weight_kg === undefined ? "" : String(pair.weight_kg)} onChange={(v) => update("weight_kg", v)} min={30} max={300} step={0.5} unit="kg" fallback={60} signal="pink" />
            {error && <p role="alert" className="m-0 text-body-sm font-bold text-bubbles-urgent">{error}</p>}
          </fieldset>
        );
      }
      return null;
    })();
    return (
      <div key={q.id}>
        {needed && <Needed />}
        {control}
        {safety?.field === q.id && (
          <div role="alert" className="mt-3 rounded-3xl border-2 border-[#FFD3C2] bg-tint-urgent p-4"><SafetyText message={safety.message} /></div>
        )}
      </div>
    );
  }

  const label = screen ? progressLabel(screens, index, answers) : "";
  const anyAnswered = screenQs.some((q) => isAnswered(q, answers[q.id]));
  const needsAnswer = screenQs.some((q) => isRequired(q, answers, today));
  const inExtras = !editing && screen?.stage === "extras";
  const primary = saving ? "Saving…" : last ? (editing ? "Save my setup" : "Set up my app") : needsAnswer || anyAnswered ? "Next" : "Skip";

  return (
    <main className="min-h-dvh bg-blush px-4 pb-16 pt-8 sm:px-8">
      <div className="mx-auto w-full max-w-[600px]">
        <div className="mb-6 flex items-center justify-between gap-3">
          <span className="flex items-center gap-2">
            <BubblesMascot size={36} animated={false} />
            <span className="font-display text-[1.5rem] leading-none text-ink">bubbles</span>
          </span>
          <details className="relative text-right">
            <summary className="cursor-pointer list-none rounded-full border border-line bg-surface px-4 py-2 text-body-sm font-extrabold text-ink-soft">Need help right now?</summary>
            <div role="note" className="absolute right-0 z-10 mt-2 w-[min(88vw,360px)] rounded-3xl border border-line bg-surface p-4 text-left shadow-[var(--shadow-sm)]">
              <p className="m-0 text-body-sm font-bold text-ink">If you or someone else is in danger, or this is a medical emergency, call your local emergency number now.</p>
              <p className="m-0 mt-2 text-body-sm text-ink-soft">If you are thinking about harming yourself, please reach out to someone you trust or a local helpline right away. You are not a bother.</p>
            </div>
          </details>
        </div>

        <form onSubmit={(e) => { e.preventDefault(); if (screen?.kind === "questions") void next(); }} className="bubbles-rise rounded-[28px] border border-line bg-surface p-5 sm:p-8" noValidate>
          <h1 ref={heading} tabIndex={-1} className="m-0 text-body-sm font-extrabold uppercase tracking-wide text-muted outline-none">{label}</h1>

          {screen?.kind === "extras-intro" && (
            <div className="mt-4 flex flex-col gap-4">
              <h2 className="m-0 font-display text-h2 text-ink">A little more, skip any</h2>
              <p className="m-0 text-body text-muted">A few quick ones make Bubbles fit you better. Skip whatever you like, or all of them.</p>
              <div className="mt-2 flex flex-wrap items-center justify-between gap-3">
                <button type="button" onClick={back} className={GHOST}>Back</button>
                <div className="flex flex-wrap items-center gap-3">
                  <button type="button" disabled={saving} onClick={() => void finishWithSave()} className={GHOST}>Skip all extras</button>
                  <button type="button" onClick={() => { stepRef.current = 2; const following = screens[index + 1]; if (following) setScreenId(following.id); }} className={BUTTON}>Show me</button>
                </div>
              </div>
            </div>
          )}

          {screen?.kind === "choices" && (
            <div className="mt-4">
              <ChoicesStep
                purposes={purposes} on={choicesOn} failed={choicesFailed} busy={saving} onBack={back}
                onToggle={(id) => setChoicesOn((prev) => { const copy = new Set(prev); if (copy.has(id)) copy.delete(id); else copy.add(id); return copy; })}
                onNotNow={() => void saveChoices(new Set())}
                onContinue={() => void saveChoices(choicesOn)}
              />
            </div>
          )}

          {screen?.kind === "questions" && (
            <>
              {screen.title && <h2 className="m-0 mt-3 font-display text-h2 text-ink">{screen.title}</h2>}
              {screen.id === "first" && <p className="m-0 mt-2 text-body-sm font-semibold text-muted">About a minute. Most of it is one tap each.</p>}
              <div className="mt-5 flex flex-col gap-7">{screenQs.map((q) => render(q))}</div>

              {notice && <p role="status" className="m-0 mt-5 rounded-2xl bg-blush px-4 py-3 text-body-sm font-bold text-ink-soft">{notice}</p>}

              <div className="mt-8 flex flex-wrap items-center justify-between gap-3">
                {index > 0 ? <button type="button" onClick={back} className={GHOST}>Back</button> : <span />}
                <button type="submit" disabled={saving} className={BUTTON}>{primary}</button>
              </div>
              {inExtras && !last && (
                <div className="mt-2 text-center">
                  <button type="button" disabled={saving} onClick={() => void finishWithSave()} className={LINK}>Skip all extras</button>
                </div>
              )}
            </>
          )}
        </form>
      </div>
    </main>
  );
}
