"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { BubblesMascot } from "../../components/BubblesMascot";
import { resetExperience, useApi, useAuth } from "../../components/Providers";
import { DateField, Stepper, TextArea, TextField } from "../../components/tracking/kit";
import { Creating } from "./Creating";
import {
  activeSteps, isAnswered, missingRequired, pick, picked, stepPatch, titleFor, visibleOptions, visibleQuestions,
  type Answers, type Question, type Step,
} from "./flow";

interface Bank {
  steps: Step[];
  questions: Question[];
  titlesHi: Record<string, string>;
}

type Phase = "loading" | "error" | "form" | "creating" | "under18";
type Failure = { field?: string; message: string };

const BUTTON = "bubbles-press bubbles-glow inline-flex min-h-[56px] items-center justify-center rounded-full bg-bubbles-pink-ink px-8 text-[1.0625rem] font-extrabold text-white disabled:cursor-wait disabled:opacity-70";
const GHOST = "bubbles-press inline-flex min-h-[52px] items-center justify-center rounded-full border border-line bg-surface px-6 font-extrabold text-ink-soft";
const CHIP_ON = "border-bubbles-pink-ink bg-tint-pink text-bubbles-pink-deep";
const CHIP_OFF = "border-line bg-surface text-muted hover:border-line-strong hover:text-default";

const FACES = ["1 · Very low", "2 · Low", "3 · Okay", "4 · Good", "5 · Very good"];

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

function ChipGroup({ q, title, hint, value, options, error, onPick }: {
  q: Question; title: string; hint: string; value: unknown; options: { id: string; label: string }[]; error?: string; onPick: (optionId: string) => void;
}) {
  const chosen = picked(value);
  return (
    <fieldset id={`q-${q.id}`} aria-invalid={error ? true : undefined} className="m-0 flex min-w-0 flex-col gap-2 border-0 p-0">
      <legend className="mb-2 p-0 text-body font-extrabold">
        {title}
        {!q.required && <span className="font-semibold text-muted"> (optional)</span>}
      </legend>
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

export function OnboardingClient() {
  const router = useRouter();
  const { loading, session, user, signOut } = useAuth();
  const { fetchBubbles } = useApi();
  const [phase, setPhase] = useState<Phase>("loading");
  const [problem, setProblem] = useState("");
  const [bank, setBank] = useState<Bank | null>(null);
  const [answers, setAnswers] = useState<Answers>({});
  const [stepId, setStepId] = useState<string>("welcome");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [safety, setSafety] = useState<{ field: string; message: string } | null>(null);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState("");
  const [editing, setEditing] = useState(false);
  const heading = useRef<HTMLHeadingElement>(null);
  const today = useMemo(() => new Date(), []);

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
      const loaded: Bank = { steps: bankJson.steps, questions: bankJson.questions, titlesHi: bankJson.titles_hi ?? {} };
      setBank(loaded);
      setAnswers(state.answers ?? {});
      const steps = activeSteps(loaded.steps, loaded.questions, state.answers ?? {}, today);
      const saved = Number(state.step) || 0;
      const resume = steps.find((s) => loaded.steps.findIndex((x) => x.id === s.id) >= saved - 1 && saved > 0);
      setStepId(edit ? steps[0]?.id ?? "welcome" : resume && saved > 1 ? resume.id : "welcome");
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
  }, [stepId, phase]);

  const steps = useMemo(() => (bank ? activeSteps(bank.steps, bank.questions, answers, today) : []), [bank, answers, today]);
  const index = steps.findIndex((s) => s.id === stepId);
  const step = index >= 0 ? steps[index] : null;
  const stepQuestions = useMemo(() => (bank && step ? visibleQuestions(bank.questions, answers, today).filter((q) => q.step === step.id) : []), [bank, step, answers, today]);
  const language = answers.language;

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

  /** Saves the answers of the current step. Returns true when it is safe to move on. */
  async function saveStep(): Promise<boolean> {
    if (!bank || !step) return true;
    const missing = missingRequired(stepQuestions, answers);
    if (missing.length) {
      setErrors(Object.fromEntries(missing.map((id) => [id, "Please answer this one to continue."])));
      document.getElementById(`q-${missing[0]}`)?.scrollIntoView({ block: "center", behavior: "smooth" });
      return false;
    }
    setSaving(true);
    setNotice("");
    try {
      const response = await fetchBubbles("/onboarding/answers", {
        method: "PUT",
        body: JSON.stringify({ answers: stepPatch(stepQuestions, answers), step: bank.steps.findIndex((s) => s.id === step.id) + 1 }),
      });
      if (!response.ok) {
        const failure = await failureOf(response);
        if (response.status === 403 && failure.message.includes("18")) {
          setPhase("under18");
          return false;
        }
        if (failure.field) setErrors({ [failure.field]: failure.message });
        else setNotice(failure.message);
        return false;
      }
      const result = await response.json();
      if (result.under_18) {
        setPhase("under18");
        return false;
      }
      setAnswers(result.answers ?? answers);
      if (result.safety) {
        setSafety({ field: result.safety.field, message: result.safety.message });
        setNotice("Thank you for telling Bubbles. That part wasn't saved. You can carry on when you are ready.");
        return false;
      }
      setSafety(null);
      return true;
    } catch {
      setNotice("Bubbles couldn't reach the server. Your answers are still here: please try again.");
      return false;
    } finally {
      setSaving(false);
    }
  }

  async function next() {
    if (!(await saveStep())) return;
    const following = steps[index + 1];
    // the saved answers may have changed which steps exist (the body decides), so look the next one up again
    if (following) setStepId(following.id);
    else setPhase("creating");
  }

  function back() {
    const previous = steps[index - 1];
    setNotice("");
    setStepId(previous ? previous.id : "welcome");
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
            <button type="button" onClick={() => { setAnswers({}); setStepId("welcome"); setPhase("form"); void load(); }} className={GHOST}>I entered it wrong</button>
          </div>
        </div>
      </main>
    );
  }

  if (phase === "creating") {
    return <Creating run={run} name={String(answers.preferred_name ?? "")} onOpen={open} onBack={() => setPhase("form")} />;
  }

  const name = String(answers.preferred_name ?? user?.display_name ?? "");

  function render(q: Question): ReactNode {
    const title = bank ? titleFor(q, language, bank.titlesHi) : q.title;
    const value = answers[q.id];
    const error = errors[q.id] || undefined;
    const optional = !q.required;
    if (q.type === "text") {
      const props = { id: `q-${q.id}`, label: title, value: typeof value === "string" ? value : "", onChange: (v: string) => set(q.id, v), hint: q.why || undefined, error, optional, maxLength: q.maxlength };
      return (q.maxlength ?? 0) > 100 ? <TextArea key={q.id} {...props} /> : <TextField key={q.id} {...props} placeholder={q.id === "preferred_name" ? "Your first name" : undefined} />;
    }
    if (q.type === "date") {
      const max = q.id === "birth_date" || q.id === "last_period" || q.id === "baby_birth_date" ? today.toLocaleDateString("en-CA") : undefined;
      return <DateField key={q.id} id={`q-${q.id}`} label={title} value={typeof value === "string" ? value : ""} onChange={(v) => set(q.id, v)} hint={q.why || undefined} error={error} optional={optional} max={max} />;
    }
    if (q.type === "single" || q.type === "multi") {
      return <ChipGroup key={q.id} q={q} title={title} hint={q.why} value={value} error={error} options={bank ? visibleOptions(q, answers, today) : []} onPick={(id) => set(q.id, pick(q, value, id))} />;
    }
    if (q.type === "slider") {
      const unit = q.unit ?? "";
      return (
        <Stepper key={q.id} id={`q-${q.id}`} label={title} value={value === undefined ? "" : String(value)} onChange={(v) => set(q.id, v === "" ? undefined : Number(v))}
          hint={q.why || undefined} error={error} optional={optional} min={q.min ?? 0} max={q.max ?? 100} step={q.increment ?? 1} unit={unit} fallback={q.id === "sleep_hours" ? 7 : 6} signal="pink" />
      );
    }
    if (q.type === "faces") {
      const current = typeof value === "number" ? value : undefined;
      return (
        <fieldset key={q.id} id={`q-${q.id}`} className="m-0 flex min-w-0 flex-col gap-2 border-0 p-0">
          <legend className="mb-2 p-0 text-body font-extrabold">{title}<span className="font-semibold text-muted"> (optional)</span></legend>
          {q.why && <p className="m-0 mb-1 text-body-sm font-semibold text-muted">{q.why}</p>}
          <div className="grid grid-cols-5 gap-1.5 sm:gap-2">
            {FACES.map((label, i) => (
              <button key={label} type="button" aria-pressed={current === i + 1} onClick={() => set(q.id, current === i + 1 ? undefined : i + 1)}
                className={`bubbles-press min-h-[60px] break-words rounded-[20px] border px-1 text-[0.8125rem] font-extrabold leading-tight sm:text-[0.9375rem] ${current === i + 1 ? CHIP_ON : CHIP_OFF}`}>
                {label}
              </button>
            ))}
          </div>
        </fieldset>
      );
    }
    if (q.type === "number_pair") {
      const pair = (value && typeof value === "object" ? value : {}) as { height_cm?: number; weight_kg?: number };
      const update = (key: "height_cm" | "weight_kg", raw: string) => {
        const next = { ...pair };
        if (raw === "") delete next[key];
        else next[key] = Number(raw);
        set(q.id, Object.keys(next).length ? next : undefined);
      };
      return (
        <fieldset key={q.id} id={`q-${q.id}`} className="m-0 flex min-w-0 flex-col gap-4 border-0 p-0">
          <legend className="mb-2 p-0 text-body font-extrabold">{title}<span className="font-semibold text-muted"> (optional)</span></legend>
          {q.why && <p className="m-0 text-body-sm font-semibold text-muted">{q.why}</p>}
          <Stepper id="q-height_cm" label="Height" value={pair.height_cm === undefined ? "" : String(pair.height_cm)} onChange={(v) => update("height_cm", v)} optional min={120} max={230} step={1} unit="cm" fallback={165} signal="pink" />
          <Stepper id="q-weight_kg" label="Weight" value={pair.weight_kg === undefined ? "" : String(pair.weight_kg)} onChange={(v) => update("weight_kg", v)} optional min={30} max={300} step={0.5} unit="kg" fallback={60} signal="pink" />
          {error && <p role="alert" className="m-0 text-body-sm font-bold text-bubbles-urgent">{error}</p>}
        </fieldset>
      );
    }
    return null;
  }

  const isWelcome = stepId === "welcome" || !step;
  const last = index === steps.length - 1;
  const percent = steps.length ? Math.round((Math.max(index, 0) / steps.length) * 100) : 0;

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

        {isWelcome ? (
          <div className="bubbles-rise rounded-[28px] border border-line bg-surface p-6 text-center sm:p-9">
            <BubblesMascot size={112} mood="happy" className="mx-auto" />
            <h1 ref={heading} tabIndex={-1} className="mt-5 font-display text-h1 text-ink outline-none">{name ? `Hi ${name}, let's set Bubbles up for you` : "Let's set Bubbles up for you"}</h1>
            <p className="mx-auto mt-3 max-w-[440px] text-body text-muted">
              About three minutes. Answer what you are comfortable with: most questions can be skipped, and you can change everything later. Bubbles never diagnoses,
              and your answers stay private to your account.
            </p>
            <button type="button" onClick={() => { const first = steps[0]; if (first) setStepId(first.id); }} className={`${BUTTON} mt-6`}>Let&apos;s start</button>
          </div>
        ) : (
          <form
            onSubmit={(e) => { e.preventDefault(); void next(); }}
            className="bubbles-rise rounded-[28px] border border-line bg-surface p-5 sm:p-8"
            noValidate
          >
            <div className="mb-5">
              <div className="flex items-center justify-between text-body-sm font-bold text-muted">
                <span>Step {index + 1} of {steps.length}</span>
                <span>{percent}%</span>
              </div>
              <div role="progressbar" aria-valuemin={0} aria-valuemax={steps.length} aria-valuenow={index + 1} aria-label="Setup progress" className="mt-2 h-2.5 overflow-hidden rounded-full bg-blush">
                <div className="h-full rounded-full bg-bubbles-pink transition-[width] duration-300" style={{ width: `${((index + 1) / steps.length) * 100}%` }} />
              </div>
            </div>
            <h1 ref={heading} tabIndex={-1} className="m-0 font-display text-h2 text-ink outline-none">{step.title}</h1>
            <p className="m-0 mt-1 text-body text-muted">{step.intro}</p>

            <div className="mt-6 flex flex-col gap-7">{stepQuestions.map((q) => (
              <div key={q.id}>
                {render(q)}
                {safety?.field === q.id && (
                  <div role="alert" className="mt-3 rounded-3xl border-2 border-[#FFD3C2] bg-tint-urgent p-4"><SafetyText message={safety.message} /></div>
                )}
              </div>
            ))}</div>

            {notice && <p role="status" className="m-0 mt-5 rounded-2xl bg-blush px-4 py-3 text-body-sm font-bold text-ink-soft">{notice}</p>}

            <div className="mt-8 flex flex-wrap items-center justify-between gap-3">
              <button type="button" onClick={back} className={GHOST}>Back</button>
              <button type="submit" disabled={saving} className={BUTTON}>{saving ? "Saving…" : last ? (editing ? "Save my setup" : "Create my companion") : "Next"}</button>
            </div>
            {stepQuestions.every((q) => !q.required) && !stepQuestions.some((q) => isAnswered(q, answers[q.id])) && (
              <p className="m-0 mt-3 text-center text-body-sm text-muted">Nothing here is required. Press Next to skip this step.</p>
            )}
          </form>
        )}
      </div>
    </main>
  );
}
