"use client";

import { useEffect, useRef, useState } from "react";
import { Field, Quote } from "../../components/pearl";
import { readCooldown, readSafety, type SafetyAnswer } from "./orbit";
import { copyText, OrbitFrame, SafetyNotice, useOrbitCall } from "./OrbitKit";

/** Before I text them: if the draft is heated, a 20-minute pause, then the same point in a softer form. Nothing is saved. */
export function TextClient() {
  const call = useOrbitCall();
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<{ heated: boolean; rewrite: string | null; pauseMinutes: number } | null>(null);
  const [safety, setSafety] = useState<SafetyAnswer | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [left, setLeft] = useState<number | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => () => { if (timer.current) clearInterval(timer.current); }, []);

  async function check() {
    setBusy(true);
    setProblem(null);
    setSafety(null);
    setResult(null);
    try {
      const { json } = await call("/orbit/cooldown", "POST", { draft });
      const s = readSafety(json);
      if (s) return setSafety(s);
      const r = readCooldown(json);
      if (!r) return setProblem("That did not work. Please try again.");
      setResult(r);
    } catch {
      setProblem("That did not work. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  function startPause(minutes: number) {
    if (timer.current) clearInterval(timer.current);
    setLeft(minutes * 60);
    timer.current = setInterval(() => setLeft((s) => (s === null || s <= 1 ? (timer.current && clearInterval(timer.current), 0) : s - 1)), 1000);
  }

  const clock = left === null ? "" : `${Math.floor(left / 60)}:${String(left % 60).padStart(2, "0")}`;

  return (
    <OrbitFrame title="Before I text them" lede="Write the message you want to send. If it sounds heated, take a breath before it goes.">
      <Field id="draft" label="Your message" value={draft} onChange={setDraft} rows={5} maxLength={1500} />
      <p style={{ marginTop: 20 }}>
        <button type="button" className="pearl-btn primary" disabled={busy || !draft.trim()} onClick={() => void check()}>{busy ? "Reading…" : "Check it"}</button>
      </p>
      {problem && <p role="alert" className="pearl-error">{problem}</p>}
      {safety && <SafetyNotice safety={safety} />}
      {result && !result.heated && <p role="status" className="pearl-note">This reads calm. Send it when you are ready.</p>}
      {result?.heated && (
        <div className="pearl-rise">
          <p className="pearl-label">This sounds heated. A short pause usually helps.</p>
          <p style={{ margin: 0 }}>
            {left === null ? (
              <button type="button" className="pearl-btn" onClick={() => startPause(result.pauseMinutes || 20)}>Start a {result.pauseMinutes || 20}-minute pause</button>
            ) : left > 0 ? (
              <span role="timer" aria-live="off" style={{ fontFamily: "var(--font-fraunces), serif", fontSize: "2rem" }}>{clock}</span>
            ) : (
              <span role="status">Pause done. Take a slow breath, then read the softer version.</span>
            )}
          </p>
          {result.rewrite && (
            <>
              <Quote tone="A softer way to say it">{result.rewrite}</Quote>
              <p style={{ margin: "6px 0 0 18px" }}>
                <button type="button" className="pearl-link" onClick={() => copyText(result.rewrite ?? "")}>Copy</button>
              </p>
            </>
          )}
        </div>
      )}
    </OrbitFrame>
  );
}
