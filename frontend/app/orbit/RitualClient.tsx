"use client";

import { useCallback, useEffect, useState } from "react";
import { Field, Gap, Section } from "../../components/pearl";
import { readCheckin, readQuestion, readSafety, type Checkin, type DailyQuestion, type SafetyAnswer } from "./orbit";
import { OrbitFrame, SafetyNotice, useOrbitCall } from "./OrbitKit";

/** Today's small question and the weekly check-in. Paired answers appear for both only once both have answered (the server decides). */
export function RitualClient() {
  const call = useOrbitCall();
  const [question, setQuestion] = useState<DailyQuestion | null>(null);
  const [checkin, setCheckin] = useState<Checkin | null>(null);
  const [answer, setAnswer] = useState("");
  const [weekly, setWeekly] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [safety, setSafety] = useState<SafetyAnswer | null>(null);
  const [problem, setProblem] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [q, c] = await Promise.all([call("/orbit/question"), call("/orbit/checkin")]);
      setQuestion(readQuestion(q.json));
      setCheckin(readCheckin(c.json));
    } catch {
      setProblem("Orbit did not load. Please try again.");
    }
  }, [call]);

  useEffect(() => {
    void load();
  }, [load]);

  async function send(kind: "question" | "checkin") {
    setBusy(kind);
    setProblem(null);
    setSafety(null);
    try {
      const { json } = await call(`/orbit/${kind}`, "POST", kind === "question" ? { answer } : { answers: weekly });
      const s = readSafety(json);
      if (s) return setSafety(s);
      const next = kind === "question" ? readQuestion(json) : readCheckin(json);
      if (!next) return setProblem("That did not save. Please try again.");
      if (kind === "question") setQuestion(next as DailyQuestion);
      else setCheckin(next as Checkin);
    } catch {
      setProblem("That did not save. Please try again.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <OrbitFrame title="Today's question" lede="One small question a day. Answer for yourself, or with someone you are connected with.">
      {problem && <p role="alert" className="pearl-error">{problem}</p>}
      {safety && <SafetyNotice safety={safety} />}
      {question && (
        <Section>
          <p className="pearl-lede" style={{ marginTop: 0 }}>{question.text}</p>
          {question.answered ? (
            <>
              <p className="pearl-quote-text" style={{ marginTop: 16 }}>{question.myAnswer}</p>
              {question.paired && question.state === "revealed" && question.partnerAnswer && (
                <div className="pearl-quote pearl-rise">
                  <p className="pearl-quote-tone">Their answer</p>
                  <p className="pearl-quote-text">{question.partnerAnswer}</p>
                </div>
              )}
              {question.paired && question.state !== "revealed" && <p className="pearl-note">Their answer appears here once you have both answered and both switched shared questions on.</p>}
            </>
          ) : (
            <>
              <Field id="answer" label="Your answer" value={answer} onChange={setAnswer} rows={3} maxLength={500} />
              <p style={{ marginTop: 16 }}>
                <button type="button" className="pearl-btn primary" disabled={busy !== null || !answer.trim()} onClick={() => void send("question")}>{busy === "question" ? "Saving…" : "Save"}</button>
              </p>
            </>
          )}
        </Section>
      )}
      {checkin && (
        <Section label="This week">
          {checkin.answered ? (
            <>
              {Object.entries(checkin.mine).map(([k, v]) => (
                <div key={k}>
                  <p className="pearl-quote-tone" style={{ marginTop: 16 }}>{checkin.prompts[k] ?? k}</p>
                  <p className="pearl-quote-text">{v}</p>
                </div>
              ))}
              {checkin.paired && checkin.state === "revealed" && checkin.partner ? (
                <div className="pearl-rise" style={{ marginTop: 22 }}>
                  <p className="pearl-label">Theirs</p>
                  {Object.entries(checkin.partner).map(([k, v]) => (
                    <div key={k}>
                      <p className="pearl-quote-tone" style={{ marginTop: 12 }}>{checkin.prompts[k] ?? k}</p>
                      <p className="pearl-quote-text">{v}</p>
                    </div>
                  ))}
                </div>
              ) : checkin.paired ? (
                <Gap>Waiting for them. You will both see everything at the same time.</Gap>
              ) : null}
            </>
          ) : (
            <>
              <p className="pearl-note">Three short questions. Skip any you like.</p>
              {Object.entries(checkin.prompts).map(([k, label]) => (
                <Field key={k} id={`w-${k}`} label={label} value={weekly[k] ?? ""} onChange={(v) => setWeekly((w) => ({ ...w, [k]: v }))} rows={2} maxLength={300} />
              ))}
              <p style={{ marginTop: 16 }}>
                <button type="button" className="pearl-btn primary" disabled={busy !== null || !Object.values(weekly).some((v) => v.trim())} onClick={() => void send("checkin")}>{busy === "checkin" ? "Saving…" : "Save my check-in"}</button>
              </p>
            </>
          )}
        </Section>
      )}
    </OrbitFrame>
  );
}
