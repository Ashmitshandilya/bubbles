"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "../../lib/supabase";
import { BubblesMascot } from "../../components/BubblesMascot";
import { isNativeApp } from "../../lib/native";

// Set or change the account password: reached from a password-recovery email (via /callback?next=password) or from
// Settings. Needs a signed-in session; a password is what signs you in to the Android app.
export default function PasswordPage() {
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [message, setMessage] = useState<{ kind: "error" | "info"; text: string } | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    let active = true;
    supabase.auth.getSession().then(({ data }) => {
      if (!active) return;
      if (data.session) setReady(true);
      else router.replace("/login");
    });
    return () => {
      active = false;
    };
  }, [router]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (password !== confirm) {
      setMessage({ kind: "error", text: "The two passwords don't match." });
      return;
    }
    setSaving(true);
    setMessage(null);
    try {
      const { error } = await supabase.auth.updateUser({ password });
      if (error) setMessage({ kind: "error", text: error.message });
      else setSaved(true);
    } catch {
      setMessage({ kind: "error", text: "Bubbles couldn't reach the sign-in service. Check your connection and try again." });
    } finally {
      setSaving(false);
    }
  }

  const inputClass =
    "min-h-[52px] w-full rounded-[18px] border-2 border-line bg-surface px-4 text-body text-ink outline-none transition-colors focus:border-bubbles-grape";
  const buttonClass =
    "bubbles-press mt-2 inline-flex min-h-[56px] items-center justify-center rounded-full bg-bubbles-pink-ink px-6 text-[1.0625rem] font-extrabold text-white bubbles-glow disabled:cursor-wait disabled:opacity-70";

  return (
    <main className="flex min-h-dvh items-center justify-center bg-blush px-5 py-10">
      <div className="w-full max-w-[440px] bubbles-rise">
        <div className="mb-6 flex flex-col items-center gap-3 text-center">
          <BubblesMascot size={96} mood={saved ? "happy" : "calm"} />
          <h1 className="m-0 font-display text-h1">{saved ? "Password saved" : "Choose a password"}</h1>
          <p className="m-0 text-body text-ink-soft">
            {saved
              ? isNativeApp
                ? "You're all set."
                : "You can now sign in with your email and this password, on the website and in the Android app."
              : "Use it to sign in with your email, on the website and in the Android app."}
          </p>
        </div>

        <div className="rounded-[32px] border-2 border-line bg-surface p-6 shadow-md sm:p-8">
          {!ready ? (
            <p role="status" className="m-0 text-center text-ink-soft">Loading…</p>
          ) : saved ? (
            <button type="button" onClick={() => router.replace("/dashboard")} className={`${buttonClass} w-full`}>
              Continue to Bubbles
            </button>
          ) : (
            <form onSubmit={handleSubmit} className="flex flex-col gap-4">
              <label className="flex flex-col gap-2 text-body-sm font-extrabold">
                New password
                <input type="password" autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} className={inputClass} required minLength={6} />
                <span className="text-caption font-semibold text-ink-soft">At least 6 characters.</span>
              </label>
              <label className="flex flex-col gap-2 text-body-sm font-extrabold">
                Type it again
                <input type="password" autoComplete="new-password" value={confirm} onChange={(e) => setConfirm(e.target.value)} className={inputClass} required minLength={6} />
              </label>
              <button type="submit" disabled={saving} className={buttonClass}>
                {saving ? "Just a moment…" : "Save password"}
              </button>
            </form>
          )}

          {message && (
            <p
              role={message.kind === "error" ? "alert" : "status"}
              className={`mt-4 rounded-[18px] px-4 py-3 text-body-sm font-bold ${
                message.kind === "error" ? "bg-tint-urgent text-bubbles-urgent" : "bg-tint-mint text-bubbles-mint-deep"
              }`}
            >
              {message.text}
            </p>
          )}
        </div>
      </div>
    </main>
  );
}
