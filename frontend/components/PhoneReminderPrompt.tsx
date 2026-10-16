"use client";

// Android app, first run: one full-screen step that asks for permissions up front (docs/FIREBASE.md). Shown once per phone,
// right after setup, only when the build and the server have Firebase and phone reminders are not on yet. It shows what a
// reminder looks like and why it helps before Android's own prompt appears (asking cold gets a reflex "no", and Android
// may not ask twice). "Turn on reminders" is the consent; crash reports are a separate box, off by default.
// "Maybe later", Back or Escape never asks again on this phone; Settings keeps both switches.

import { useEffect, useRef, useState } from "react";
import { useApi } from "./Providers";
import { BubblesMascot } from "./BubblesMascot";
import { phoneProblemMessage } from "../app/lib/phone-reminders";

const REASONS = [
  { title: "At the right moments", body: "Water, medicine check-ins and wind-down, timed to your day." },
  { title: "Never what you logged", body: "Plain words only. Nothing about your health on the lock screen." },
  { title: "Quiet when you want", body: "Quiet hours and a daily limit. Change or stop it any time." },
] as const;

export function PhoneReminderPrompt() {
  const { fetchBubbles } = useApi();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [crash, setCrash] = useState(false);
  const [error, setError] = useState("");
  const primary = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    let active = true;
    const timer = window.setTimeout(() => {
      void import("../lib/firebase-native").then((m) => m.shouldOfferPhone(fetchBubbles)).then((offer) => active && setOpen(offer)).catch(() => undefined);
    }, 600);   // let the first screen paint before asking
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [fetchBubbles]);

  useEffect(() => {
    if (!open) return;
    primary.current?.focus();
    // Android Back (NativeBridge sends Escape to an open role="dialog") counts as "Maybe later".
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") void answer(false);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  if (!open) return null;

  async function answer(yes: boolean) {
    const m = await import("../lib/firebase-native");
    if (!yes) {
      m.markPhoneOffered();
      return setOpen(false);
    }
    setBusy(true);
    setError("");
    if (crash) await m.setCrashReports(true).catch(() => undefined);
    const result = await m.turnOnPhoneReminders(fetchBubbles);
    setBusy(false);
    if (!result.ok && result.problem !== "denied") return setError(phoneProblemMessage(result.problem));
    m.markPhoneOffered();   // a "no" on Android's prompt is an answer too; Settings can turn it on later
    setOpen(false);
  }

  return (
    <div role="dialog" aria-modal="true" aria-labelledby="perm-title" aria-describedby="perm-lede" className="perm">
      <div className="perm-inner">
        <BubblesMascot size={96} mood="happy" className="perm-mascot" />
        <h1 id="perm-title" className="perm-title">Let Bubbles nudge you, gently</h1>
        <p id="perm-lede" className="perm-lede">Small reminders help habits stick. This is what one looks like:</p>

        <div className="perm-preview" aria-hidden="true">
          <span className="perm-preview-icon" />
          <span className="perm-preview-text">
            <span className="perm-preview-app">Bubbles · now</span>
            <span className="perm-preview-title">A little water break?</span>
            <span className="perm-preview-body">Time for a sip of water.</span>
          </span>
        </div>

        <ul className="perm-reasons">
          {REASONS.map((r) => (
            <li key={r.title}>
              <span className="perm-check" aria-hidden="true">
                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12.5l4.5 4.5L19 7.5" /></svg>
              </span>
              <span>
                <strong>{r.title}</strong>
                <span className="perm-reason-body">{r.body}</span>
              </span>
            </li>
          ))}
        </ul>

        <label className="perm-crash">
          <input type="checkbox" checked={crash} onChange={(e) => setCrash(e.target.checked)} />
          <span>Also send crash reports, so we can fix problems faster. Never your entries or messages.</span>
        </label>

        {error && <p role="alert" className="perm-error">{error}</p>}

        <div className="perm-actions">
          <button ref={primary} type="button" disabled={busy} onClick={() => void answer(true)} className="perm-primary">
            {busy ? "Turning on…" : "Turn on reminders"}
          </button>
          <button type="button" disabled={busy} onClick={() => void answer(false)} className="perm-later">Maybe later</button>
        </div>
        <p className="perm-fine">Reminders are not a safety system. In an emergency, call your local emergency number.</p>
      </div>
    </div>
  );
}
