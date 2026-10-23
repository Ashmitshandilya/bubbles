"use client";

import Link from "next/link";
import { useState } from "react";
import { Field, Quote } from "../../components/pearl";
import { readConsentNeeded, readReplies, readSafety, TONE_LABEL, type ReplyHelp, type SafetyAnswer } from "./orbit";
import { copyText, OrbitFrame, SafetyNotice, useOrbitCall } from "./OrbitKit";

export function ReplyClient() {
  const call = useOrbitCall();
  const [theirs, setTheirs] = useState("");
  const [context, setContext] = useState("");
  const [busy, setBusy] = useState(false);
  const [help, setHelp] = useState<ReplyHelp | null>(null);
  const [safety, setSafety] = useState<SafetyAnswer | null>(null);
  const [needsYes, setNeedsYes] = useState<string | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [copied, setCopied] = useState<number | null>(null);

  async function ask(extra?: string) {
    setBusy(true);
    setProblem(null);
    setNeedsYes(null);
    setSafety(null);
    try {
      const { status, json } = await call("/orbit/reply-helper", "POST", { their_message: theirs, context: [context, extra].filter(Boolean).join(" ") });
      const consent = readConsentNeeded(status, json);
      if (consent) return setNeedsYes(consent.message);
      const s = readSafety(json);
      if (s) {
        setHelp(null);
        return setSafety(s);
      }
      const r = readReplies(json);
      if (!r) return setProblem(status === 429 ? "You're going quickly. Please wait a moment and try again." : "That did not work. Please try again.");
      setHelp(r);
    } catch {
      setProblem("That did not work. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <OrbitFrame title="Help me reply" lede="Paste what they said, and I'll suggest how they may be feeling and three ways to answer. Nothing is saved.">
      <Field id="their-message" label="What they said" value={theirs} onChange={setTheirs} rows={5} maxLength={1500} />
      <Field id="context" label="Anything I should know? (optional)" value={context} onChange={setContext} rows={2} maxLength={600} />
      <p style={{ marginTop: 20 }}>
        <button type="button" className="pearl-btn primary" disabled={busy || !theirs.trim()} onClick={() => void ask()}>{busy ? "Thinking…" : "Help me reply"}</button>
      </p>
      {problem && <p role="alert" className="pearl-error">{problem}</p>}
      {needsYes && (
        <p role="status" className="pearl-note">
          {needsYes} <Link href="/privacy-choices" className="pearl-link">Open Privacy choices</Link>
        </p>
      )}
      {safety && <SafetyNotice safety={safety} />}
      {help?.declined && <p role="status" className="pearl-note">{help.declined}</p>}
      {help && !help.declined && (
        <div className="pearl-rise">
          {help.feelings.length > 0 && (
            <>
              <p className="pearl-label">What may be underneath</p>
              <ul style={{ margin: 0, paddingLeft: 18, color: "var(--ink)" }}>{help.feelings.map((f) => <li key={f}>{f}</li>)}</ul>
            </>
          )}
          {help.replies.map((r, i) => (
            <div key={`${r.tone}-${i}`}>
              <Quote tone={TONE_LABEL[r.tone] ?? r.tone} why={r.why}>{r.text}</Quote>
              <p style={{ margin: "6px 0 0 18px", display: "flex", gap: 14, flexWrap: "wrap" }}>
                <button type="button" className="pearl-link" onClick={() => { copyText(r.text); setCopied(i); }}>{copied === i ? "Copied" : "Copy"}</button>
              </p>
            </div>
          ))}
          <p style={{ marginTop: 22, display: "flex", gap: 14, flexWrap: "wrap" }}>
            <button type="button" className="pearl-link" disabled={busy} onClick={() => void ask("Make the replies softer.")}>Make it softer</button>
            <button type="button" className="pearl-link" disabled={busy} onClick={() => void ask("Make the replies shorter.")}>Shorter</button>
            <button type="button" className="pearl-link" disabled={busy} onClick={() => void ask("Write the replies in Hinglish.")}>More Hinglish</button>
          </p>
          <p className="pearl-note">{help.source === "ai" ? "Written for you by Bubbles." : "Bubbles could not reach its writing helper just now, so these are gentle starting points."}</p>
        </div>
      )}
    </OrbitFrame>
  );
}
