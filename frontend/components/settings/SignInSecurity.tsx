"use client";

import { useCallback, useEffect, useState } from "react";
import { supabase } from "../../lib/supabase";
import { keepSignedInChoice, setKeepSignedIn } from "../../lib/auth-storage";
import { cleanCode, friendlyMfaError, isValidCode, verifiedTotp, type FactorLike } from "../../lib/mfa";
import { BTN_PRIMARY, BTN_SECONDARY, CARD } from "../hub/HubKit";

type Phase = "loading" | "off" | "enrolling" | "on";

interface Enrolment {
  factorId: string;
  qr: string;
  secret: string;
}

/** Two-step sign-in with an authenticator app (TOTP through Supabase Auth). Optional, off by default. */
export function TwoStepCard() {
  const [phase, setPhase] = useState<Phase>("loading");
  const [enrolment, setEnrolment] = useState<Enrolment | null>(null);
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ kind: "error" | "info"; text: string } | null>(null);

  const load = useCallback(async () => {
    try {
      const { data, error } = await supabase.auth.mfa.listFactors();
      if (error) throw error;
      setPhase(verifiedTotp(data?.all as FactorLike[] | undefined) ? "on" : "off");
    } catch {
      setPhase("off");
      setMessage({ kind: "error", text: "Bubbles couldn't check your two-step sign-in just now." });
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function startEnrolment() {
    setBusy(true);
    setMessage(null);
    try {
      // A half-finished attempt would make the name clash, so it is cleared first.
      const { data: existing } = await supabase.auth.mfa.listFactors();
      for (const f of (existing?.all ?? []) as FactorLike[]) {
        if (f.factor_type === "totp" && f.status !== "verified") await supabase.auth.mfa.unenroll({ factorId: f.id });
      }
      const { data, error } = await supabase.auth.mfa.enroll({ factorType: "totp", friendlyName: "Bubbles" });
      if (error || !data?.totp) throw error ?? new Error("no secret");
      setEnrolment({ factorId: data.id, qr: data.totp.qr_code, secret: data.totp.secret });
      setCode("");
      setPhase("enrolling");
    } catch {
      setMessage({ kind: "error", text: "Bubbles couldn't start two-step sign-in. Please try again in a moment." });
    } finally {
      setBusy(false);
    }
  }

  async function confirm(e: React.FormEvent) {
    e.preventDefault();
    if (!enrolment) return;
    if (!isValidCode(code)) {
      setMessage({ kind: "error", text: "Enter the 6 digit code from your authenticator app." });
      return;
    }
    setBusy(true);
    setMessage(null);
    try {
      const { error } = await supabase.auth.mfa.challengeAndVerify({ factorId: enrolment.factorId, code: cleanCode(code) });
      if (error) {
        setMessage({ kind: "error", text: friendlyMfaError(error.message) });
      } else {
        setEnrolment(null);
        setCode("");
        setPhase("on");
        setMessage({ kind: "info", text: "Two-step sign-in is on. From now on Bubbles asks for a code after your password." });
      }
    } catch {
      setMessage({ kind: "error", text: friendlyMfaError("Failed to fetch") });
    } finally {
      setBusy(false);
    }
  }

  async function cancel() {
    if (enrolment) await supabase.auth.mfa.unenroll({ factorId: enrolment.factorId }).catch(() => undefined);
    setEnrolment(null);
    setCode("");
    setMessage(null);
    setPhase("off");
  }

  async function turnOff() {
    setBusy(true);
    setMessage(null);
    try {
      const { data } = await supabase.auth.mfa.listFactors();
      const factor = verifiedTotp(data?.all as FactorLike[] | undefined);
      if (!factor) {
        setPhase("off");
        return;
      }
      const { error } = await supabase.auth.mfa.unenroll({ factorId: factor.id });
      if (error) {
        setMessage({ kind: "error", text: "Bubbles couldn't turn it off. Sign out, sign in with your code, and try again." });
      } else {
        setPhase("off");
        setMessage({ kind: "info", text: "Two-step sign-in is off." });
      }
    } catch {
      setMessage({ kind: "error", text: friendlyMfaError("Failed to fetch") });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className={`${CARD} space-y-3 p-5`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 max-w-[30rem]">
          <h3 className="m-0 font-bold text-ink">Two-step sign-in</h3>
          <p className="m-0 mt-1 text-body-sm text-muted">
            After your password, Bubbles asks for a 6 digit code from an authenticator app on your phone. It protects your health notes if someone learns your password.
          </p>
        </div>
        {phase === "loading" && <span className="text-body-sm font-bold text-muted">Checking...</span>}
        {phase === "off" && (
          <button type="button" onClick={() => void startEnrolment()} disabled={busy} className={BTN_SECONDARY}>
            Turn on
          </button>
        )}
        {phase === "on" && (
          <button type="button" onClick={() => void turnOff()} disabled={busy} className={BTN_SECONDARY}>
            Turn off
          </button>
        )}
      </div>

      {phase === "on" && <p className="m-0 text-body-sm font-bold text-bubbles-mint-deep">On. Keep your authenticator app safe: if you lose it you will need help to get back in.</p>}

      {phase === "enrolling" && enrolment && (
        <form onSubmit={confirm} className="space-y-3 rounded-[18px] bg-blush p-4">
          <p className="m-0 text-body-sm font-bold text-ink">
            1. Scan this picture with an authenticator app (Google Authenticator, Microsoft Authenticator, Authy or similar).
          </p>
          {/* The picture is a data: SVG made by the sign-in service for this one setup; next/image adds nothing here. */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={enrolment.qr} alt="QR code for your authenticator app" width={176} height={176} className="rounded-[12px] bg-white p-2" />
          <p className="m-0 text-body-sm text-muted">
            Cannot scan? Type this key into the app instead: <code className="break-all font-bold text-ink">{enrolment.secret}</code>
          </p>
          <label className="flex flex-col gap-2 text-body-sm font-extrabold text-ink">
            2. Type the 6 digit code the app shows
            <input
              type="text"
              inputMode="numeric"
              autoComplete="one-time-code"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              maxLength={9}
              className="min-h-[48px] w-full max-w-[14rem] rounded-[14px] border-2 border-line bg-surface px-4 text-body tracking-[0.3em] text-ink outline-none focus:border-bubbles-grape"
            />
          </label>
          <p className="m-0 text-body-sm text-muted">If you lose the app, you will not be able to sign in without help. Save the key above somewhere safe.</p>
          <div className="flex flex-wrap gap-2">
            <button type="submit" disabled={busy} className={BTN_PRIMARY}>
              {busy ? "Checking..." : "Turn on"}
            </button>
            <button type="button" onClick={() => void cancel()} disabled={busy} className={BTN_SECONDARY}>
              Cancel
            </button>
          </div>
        </form>
      )}

      {message && (
        <p role={message.kind === "error" ? "alert" : "status"} className={`m-0 rounded-[14px] px-4 py-2 text-body-sm font-bold ${message.kind === "error" ? "bg-tint-urgent text-bubbles-urgent" : "bg-tint-mint text-bubbles-mint-deep"}`}>
          {message.text}
        </p>
      )}
    </div>
  );
}

/** "Keep me signed in on this device": off by default, so the session is not written to localStorage. */
export function KeepSignedInRow({ labelledBy, describedBy }: { labelledBy: string; describedBy: string }) {
  const [on, setOn] = useState(false);

  useEffect(() => {
    setOn(keepSignedInChoice());
  }, []);

  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      aria-labelledby={labelledBy}
      aria-describedby={describedBy}
      onClick={() => {
        setKeepSignedIn(!on);
        setOn(!on);
      }}
      className={`bubbles-press relative inline-flex h-8 w-14 shrink-0 items-center rounded-full border-2 transition-colors ${
        on ? "border-bubbles-grape bg-bubbles-grape" : "border-line-strong bg-surface"
      }`}
    >
      <span aria-hidden="true" className={`inline-block h-5 w-5 rounded-full bg-white shadow transition-transform ${on ? "translate-x-7" : "translate-x-1 !bg-line-strong"}`} />
    </button>
  );
}
