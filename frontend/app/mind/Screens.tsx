"use client";

// Gentle PHQ-2 / GAD-2 style check-ins. The wording comes from the server and is never a diagnosis; the result card uses
// the API's own kind sentence. No mascot, no score ranking, no colour-coded "severity".

import { useState } from "react";
import { BTN_PRIMARY, BTN_SECONDARY } from "../../components/hub/HubKit";
import { ErrorNotice, LiveRegion, Notice, Panel } from "../../components/wellness/ui";
import { useWellnessSend } from "../../components/wellness/useWellness";
import { shortDay } from "../../app/lib/wellness-format";
import type { MindOverview, ScreenQuestions, ScreenResult } from "../../app/lib/wellness-types";

const KINDS = [
  { kind: "phq2", title: "Mood check-in", blurb: "2 questions about interest and low mood" },
  { kind: "gad2", title: "Worry check-in", blurb: "2 questions about worry and feeling on edge" },
] as const;

export function Screens({ screen, onSaved }: { screen: MindOverview["screen"]; onSaved: () => void }) {
  const send = useWellnessSend();
  const [loading, setLoading] = useState<string | null>(null);
  const [questions, setQuestions] = useState<ScreenQuestions | null>(null);
  const [answers, setAnswers] = useState<(number | null)[]>([]);
  const [result, setResult] = useState<ScreenResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function start(kind: string) {
    setLoading(kind);
    setError("");
    setResult(null);
    const r = await send<ScreenQuestions>(`/wellness/mind/screen?kind=${kind}`, "GET", undefined, { tz: false });
    setLoading(null);
    if (!r.ok) return setError(r.message);
    setQuestions(r.data);
    setAnswers(r.data.questions.map(() => null));
  }

  async function submit() {
    if (!questions) return;
    if (answers.some((a) => a === null)) {
      setError("Please answer each question. You can take your time.");
      return;
    }
    setBusy(true);
    setError("");
    const r = await send<ScreenResult>("/wellness/mind/screen", "POST", { kind: questions.kind, answers });
    setBusy(false);
    if (!r.ok) return setError(`${r.message} Your answers are still here.`);
    setResult(r.data);
    setQuestions(null);
    onSaved();
  }

  return (
    <Panel id="check-ins" title="Gentle check-ins" kicker="Every two weeks or so">
      <p className="m-0 text-body-sm text-muted">
        Two short questions that sometimes help you notice how things have been. This is a check-in, not a medical assessment, and it can&apos;t tell you if something is wrong.
      </p>
      <p className="m-0 text-body-sm font-bold text-ink-soft">
        {screen.due ? "A check-in is available if you'd like one." : `You did one on ${screen.last ? shortDay(screen.last) : "recently"}. The next is offered after about ${screen.every_days} days, but you can do one any time.`}
      </p>

      {!questions && (
        <div className="flex flex-wrap gap-3">
          {KINDS.map((k) => (
            <button key={k.kind} type="button" disabled={loading !== null} onClick={() => void start(k.kind)} className={`${BTN_SECONDARY} h-auto flex-col py-2`}>
              <span>{loading === k.kind ? "Opening…" : k.title}</span>
              <span className="text-body-sm font-semibold text-muted">{k.blurb}</span>
            </button>
          ))}
        </div>
      )}

      {questions && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void submit();
          }}
          className="flex flex-col gap-5"
        >
          <p className="m-0 text-body font-bold text-ink">{questions.intro}</p>
          {questions.questions.map((q, qi) => (
            <fieldset key={q} className="m-0 flex min-w-0 flex-col gap-2 border-0 p-0">
              <legend className="mb-2 p-0 text-body font-extrabold">{q}</legend>
              <div className="grid gap-2 sm:grid-cols-2">
                {questions.options.map((o) => (
                  <label key={o.value} className="relative block">
                    <input
                      type="radio" name={`${questions.kind}-${qi}`} value={o.value} checked={answers[qi] === o.value}
                      onChange={() => setAnswers((cur) => cur.map((a, i) => (i === qi ? o.value : a)))}
                      className="peer sr-only"
                    />
                    <span className="bubbles-press flex min-h-[48px] cursor-pointer items-center gap-2 rounded-2xl border border-line bg-surface px-4 py-2 text-body-sm font-extrabold text-ink-soft peer-checked:border-bubbles-sun-deep peer-checked:bg-tint-sun peer-checked:text-ink peer-focus-visible:ring-4 peer-focus-visible:ring-bubbles-grape/40">
                      <span aria-hidden="true" className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full border ${answers[qi] === o.value ? "border-bubbles-sun-deep bg-bubbles-sun-deep" : "border-line-strong"}`}>
                        {answers[qi] === o.value && <span className="h-2 w-2 rounded-full bg-white" />}
                      </span>
                      {o.label}
                    </span>
                  </label>
                ))}
              </div>
            </fieldset>
          ))}
          {error && <ErrorNotice message={error} />}
          <p className="m-0 text-body-sm text-muted">{questions.note}</p>
          <div className="flex flex-wrap gap-3">
            <button type="submit" disabled={busy} className={BTN_PRIMARY}>
              {busy ? "Saving…" : "See my check-in"}
            </button>
            <button type="button" onClick={() => setQuestions(null)} className={BTN_SECONDARY}>
              Not now
            </button>
          </div>
        </form>
      )}

      {!questions && error && <ErrorNotice message={error} />}

      {result && (
        <div className="rounded-3xl bg-blush p-5">
          <LiveRegion message="Your check-in result is ready." />
          <h3 className="m-0 font-display text-h4 text-default">Thank you for checking in</h3>
          <p className="m-0 mt-2 whitespace-pre-line text-body text-ink">{result.message}</p>
          <p className="m-0 mt-3 text-body-sm text-muted">Your answers added up to {result.score} of {result.max_score}. This is not a diagnosis.</p>
          <button type="button" onClick={() => setResult(null)} className={`${BTN_SECONDARY} mt-3`}>
            Close
          </button>
        </div>
      )}
      <Notice tone="calm">If you ever feel you might harm yourself, please contact your local emergency number or a crisis line right away.</Notice>
    </Panel>
  );
}
