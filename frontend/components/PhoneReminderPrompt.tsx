"use client";

// Android app, first run: one card that offers phone reminders (docs/FIREBASE.md). Shown once per phone after setup, only when the
// build and the server have Firebase and reminders are not on yet. "Turn on" is the consent; "Not now" never asks again here
// (Settings, Reminders still has the switch). Android's own permission prompt only follows the tap on "Turn on".

import { useEffect, useState } from "react";
import { useApi } from "./Providers";
import { BTN_PRIMARY, BTN_SECONDARY } from "./hub/HubKit";
import { phoneProblemMessage } from "../app/lib/phone-reminders";

export function PhoneReminderPrompt() {
  const { fetchBubbles } = useApi();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    const timer = window.setTimeout(() => {
      void import("../lib/firebase-native").then((m) => m.shouldOfferPhone(fetchBubbles)).then((offer) => active && setOpen(offer)).catch(() => undefined);
    }, 1500);   // let the first screen settle before asking anything
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [fetchBubbles]);

  if (!open) return null;

  async function answer(yes: boolean) {
    const m = await import("../lib/firebase-native");
    if (!yes) {
      m.markPhoneOffered();
      return setOpen(false);
    }
    setBusy(true);
    setError("");
    const result = await m.turnOnPhoneReminders(fetchBubbles);
    setBusy(false);
    if (!result.ok && result.problem !== "denied") return setError(phoneProblemMessage(result.problem));
    m.markPhoneOffered();   // a "no" on Android's prompt is an answer too; Settings can turn it on later
    setOpen(false);
  }

  return (
    <div role="dialog" aria-modal="false" aria-labelledby="phone-offer-title" className="fixed inset-x-4 bottom-24 z-50 mx-auto max-w-md rounded-3xl bg-surface p-5 shadow-lg ring-2 ring-line">
      <h2 id="phone-offer-title" className="m-0 font-display text-h4 text-ink">Get reminders on this phone?</h2>
      <p className="mb-4 mt-1 text-body-sm text-muted">Plain reminders for water, medicine check-ins and wind-down. Never what you logged. You can change this in Settings.</p>
      {error && <p role="alert" className="mb-3 mt-0 text-body-sm font-bold text-bubbles-pink-deep">{error}</p>}
      <div className="flex flex-wrap gap-3">
        <button type="button" disabled={busy} onClick={() => void answer(true)} className={BTN_PRIMARY}>{busy ? "Turning on…" : "Turn on"}</button>
        <button type="button" disabled={busy} onClick={() => void answer(false)} className={BTN_SECONDARY}>Not now</button>
      </div>
    </div>
  );
}
