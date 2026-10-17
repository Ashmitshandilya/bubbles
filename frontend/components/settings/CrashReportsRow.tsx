"use client";

// Settings, This device: the crash-report switch (Firebase Crashlytics, docs/FIREBASE.md). Only in the Android app, and only in a
// build made with Firebase; renders nothing anywhere else. Off until the person turns it on; the choice belongs to this phone.

import { useEffect, useState } from "react";
import { isNativeApp } from "../../lib/native";

export function CrashReportsRow({ rowClass }: { rowClass: string }) {
  const [state, setState] = useState<{ configured: boolean; on: boolean } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!isNativeApp) return;
    let active = true;
    void import("../../lib/firebase-native")
      .then((m) => m.firebaseStatus())
      .then((status) => active && setState({ configured: status.configured, on: status.crashReports }))
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, []);

  if (!isNativeApp || !state?.configured) return null;

  async function toggle() {
    if (!state) return;
    setBusy(true);
    setError("");
    try {
      const on = await import("../../lib/firebase-native").then((m) => m.setCrashReports(!state.on));
      setState({ configured: true, on });
    } catch {
      setError("Couldn't change this right now. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className={rowClass}>
      <dt className="min-w-0 max-w-[26rem] font-bold text-ink">
        <span id="crash-label">Send crash reports</span>
        <span id="crash-hint" className="block text-body-sm font-normal text-muted">
          If the app crashes, a technical report (phone model, Android version, where the app broke) goes to Google Firebase. Never your entries or messages.
        </span>
        {error && <span role="alert" className="block text-body-sm font-bold text-bubbles-pink-deep">{error}</span>}
      </dt>
      <dd className="m-0">
        <button
          type="button"
          role="switch"
          aria-checked={state.on}
          aria-labelledby="crash-label"
          aria-describedby="crash-hint"
          disabled={busy}
          onClick={() => void toggle()}
          className="bubbles-press inline-flex min-h-[44px] items-center gap-3 rounded-full px-1"
        >
          <span className="text-body-sm font-bold text-muted">{state.on ? "On" : "Off"}</span>
          <span aria-hidden="true" className={`relative block h-7 w-12 rounded-full border transition-colors ${state.on ? "border-bubbles-grape bg-bubbles-grape" : "border-ink-faint bg-surface"}`}>
            <span className={`absolute left-0 top-1 block h-4 w-4 rounded-full transition-transform motion-reduce:transition-none ${state.on ? "translate-x-6 bg-white" : "translate-x-1 bg-ink-faint"}`} />
          </span>
        </button>
      </dd>
    </div>
  );
}
