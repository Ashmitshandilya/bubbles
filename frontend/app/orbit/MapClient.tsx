"use client";

import { useCallback, useEffect, useState } from "react";
import { Field, Gap, Rows, Section } from "../../components/pearl";
import { readLoveMap, readSafety, type LoveMap, type SafetyAnswer } from "./orbit";
import { OrbitFrame, SafetyNotice, useOrbitCall } from "./OrbitKit";

/** Understand them: what you know about them, and a few questions worth asking. Your notes stay private. */
export function MapClient() {
  const call = useOrbitCall();
  const [map, setMap] = useState<LoveMap | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [safety, setSafety] = useState<SafetyAnswer | null>(null);
  const [problem, setProblem] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setMap(readLoveMap((await call("/orbit/love-map")).json));
    } catch {
      setProblem("Orbit did not load. Please try again.");
    }
  }, [call]);

  useEffect(() => {
    void load();
  }, [load]);

  async function save(questionId: string) {
    setBusy(true);
    setProblem(null);
    setSafety(null);
    try {
      const { json } = await call("/orbit/notes", "POST", { kind: "love_map", text, question_id: questionId });
      const s = readSafety(json);
      if (s) return setSafety(s);
      if ((json as { status?: string } | null)?.status !== "success") return setProblem("That did not save. Please try again.");
      setText("");
      setOpen(null);
      await load();
    } catch {
      setProblem("That did not save. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <OrbitFrame title="Understand them" lede="The small things you know about someone make them feel known. Here is what you have told me, and what could be worth asking.">
      {problem && <p role="alert" className="pearl-error">{problem}</p>}
      {safety && <SafetyNotice safety={safety} />}
      {map && (
        <>
          <Section label="What you know">
            {map.known.length === 0 ? <Gap>Nothing yet. Tell me about them in a chat, or answer a question below.</Gap> : (
              <ul style={{ margin: 0, padding: 0, listStyle: "none" }}>
                {map.known.map((k) => <li key={k.id} style={{ padding: "12px 0", borderBottom: "1px solid var(--hairline)" }}>{k.text}</li>)}
              </ul>
            )}
          </Section>
          {map.ask.length > 0 && (
            <Section label="Worth asking tonight">
              <Rows>
                {map.ask.map((q) => (
                  <li key={q.id} style={{ borderBottom: "1px solid var(--hairline)", padding: "14px 0" }}>
                    <button type="button" className="pearl-link" style={{ textAlign: "left", textDecoration: "none", color: "var(--ink)", fontWeight: 600 }} onClick={() => { setOpen(open === q.id ? null : q.id); setText(""); }} aria-expanded={open === q.id}>{q.text}</button>
                    {open === q.id && (
                      <div>
                        <Field id={`ans-${q.id}`} label="What you learned (only you can see this)" value={text} onChange={setText} rows={2} maxLength={600} />
                        <p style={{ marginTop: 12 }}>
                          <button type="button" className="pearl-btn primary" disabled={busy || !text.trim()} onClick={() => void save(q.id)}>Keep it</button>
                        </p>
                      </div>
                    )}
                  </li>
                ))}
              </Rows>
            </Section>
          )}
        </>
      )}
    </OrbitFrame>
  );
}
