"use client";

import { useState } from "react";
import { Field, InlineNote, Quote } from "../../components/pearl";
import { readDraft, readSafety, type SafetyAnswer } from "./orbit";
import { copyText, OrbitFrame, SafetyNotice, useOrbitCall } from "./OrbitKit";

/** After a fight: what happened, what I felt, what I needed, what I can own. A short repair message comes back; the person decides what to do with it. */
export function FightClient() {
  const call = useOrbitCall();
  const [parts, setParts] = useState({ happened: "", felt: "", needed: "", own: "" });
  const [busy, setBusy] = useState(false);
  const [draft, setDraft] = useState<string | null>(null);
  const [safety, setSafety] = useState<SafetyAnswer | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [kept, setKept] = useState(false);
  const ready = Object.values(parts).every((v) => v.trim());
  const set = (k: keyof typeof parts) => (v: string) => setParts((p) => ({ ...p, [k]: v }));

  async function make() {
    setBusy(true);
    setProblem(null);
    setSafety(null);
    setKept(false);
    try {
      const { json } = await call("/orbit/repair", "POST", parts);
      const s = readSafety(json);
      if (s) {
        setDraft(null);
        return setSafety(s);
      }
      const d = readDraft(json);
      if (!d) return setProblem("That did not work. Please try again.");
      setDraft(d);
    } catch {
      setProblem("That did not work. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  async function keep() {
    if (!draft) return;
    try {
      const { json } = await call("/orbit/notes", "POST", { kind: "repair", text: draft });
      setKept((json as { status?: string } | null)?.status === "success");
    } catch {
      setProblem("That did not save. Please try again.");
    }
  }

  return (
    <OrbitFrame title="After a fight" lede="Four short answers, just for you. I'll turn them into a calm message you can send, change or throw away.">
      <Field id="happened" label="What happened" value={parts.happened} onChange={set("happened")} rows={3} maxLength={400} />
      <Field id="felt" label="What I felt" value={parts.felt} onChange={set("felt")} rows={2} maxLength={400} />
      <Field id="needed" label="What I needed" value={parts.needed} onChange={set("needed")} rows={2} maxLength={400} />
      <Field id="own" label="What I can own" value={parts.own} onChange={set("own")} rows={2} maxLength={400} />
      <p style={{ marginTop: 20 }}>
        <button type="button" className="pearl-btn primary" disabled={busy || !ready} onClick={() => void make()}>{busy ? "Writing…" : "Write a repair message"}</button>
      </p>
      {problem && <p role="alert" className="pearl-error">{problem}</p>}
      {safety && <SafetyNotice safety={safety} />}
      {draft && (
        <div className="pearl-rise">
          <Quote tone="A draft you can change">{draft}</Quote>
          <p style={{ margin: "6px 0 0 18px", display: "flex", gap: 14 }}>
            <button type="button" className="pearl-link" onClick={() => copyText(draft)}>Copy</button>
            <button type="button" className="pearl-link" onClick={() => void keep()} disabled={kept}>{kept ? "Kept" : "Keep it"}</button>
          </p>
          {kept && <InlineNote>Saved to your private notes. No one else can see it.</InlineNote>}
        </div>
      )}
    </OrbitFrame>
  );
}
