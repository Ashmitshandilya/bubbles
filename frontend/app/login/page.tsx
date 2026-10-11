"use client";

import Link from "next/link";
import { Suspense, useEffect, useId, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { isSupabaseConfigured, supabase } from "../../lib/supabase";
import { authCallbackUrl } from "../../lib/auth-links";
import { RESEND_COOLDOWN_SECONDS, friendlyAuthError } from "../../lib/auth-errors";
import { BubblesMascot } from "../../components/BubblesMascot";

type Mode = "login" | "signup" | "magic";

const MODES: Array<{ id: Mode; label: string }> = [
  { id: "login", label: "Sign in" },
  { id: "signup", label: "Create account" },
  { id: "magic", label: "Email link" },
];

const HEADINGS: Record<Mode, { title: string; body: string }> = {
  login: { title: "Welcome back!", body: "Bubbles has been keeping your health story safe." },
  signup: { title: "Nice to meet you!", body: "Create your Bubbles and start with one message." },
  magic: { title: "No password needed", body: "We'll email you a secure sign-in link." },
};

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const formId = useId();

  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [message, setMessage] = useState<{ kind: "error" | "info"; text: string } | null>(null);
  const [loading, setLoading] = useState(false);
  /** Offer "send the confirmation email again" (after sign-up, or when sign-in says the email is not confirmed). */
  const [canResend, setCanResend] = useState(false);
  const [cooldown, setCooldown] = useState(0);

  useEffect(() => {
    const requested = searchParams?.get("mode");
    if (requested === "signup" || requested === "magic" || requested === "login") setMode(requested);
  }, [searchParams]);

  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = window.setTimeout(() => setCooldown((n) => n - 1), 1000);
    return () => window.clearTimeout(timer);
  }, [cooldown]);

  function switchMode(next: Mode) {
    setMode(next);
    setMessage(null);
    setCanResend(false);
  }

  async function resendConfirmation() {
    if (!email || cooldown > 0) return;
    setCooldown(RESEND_COOLDOWN_SECONDS);
    try {
      const { error } = await supabase.auth.resend({ type: "signup", email, options: { emailRedirectTo: authCallbackUrl(window.location.origin) } });
      setMessage(
        error
          ? { kind: "error", text: friendlyAuthError(error.message, (error as { code?: string }).code).text }
          : { kind: "info", text: "If that address has an unconfirmed account, we sent the email again. It can take a minute, and spam folders sometimes catch it." },
      );
    } catch {
      setMessage({ kind: "error", text: "Bubbles couldn't reach the sign-in service. Check your connection and try again." });
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    if (!isSupabaseConfigured) {
      setMessage({ kind: "error", text: "Bubbles isn't connected to its account service yet. Add the Supabase settings to frontend/.env.local." });
      return;
    }

    setLoading(true);
    setMessage(null);

    try {
      if (mode === "magic") {
        const { error } = await supabase.auth.signInWithOtp({
          email,
          options: { emailRedirectTo: authCallbackUrl(window.location.origin) },
        });
        setMessage(error ? { kind: "error", text: friendlyAuthError(error.message, (error as { code?: string }).code).text } : { kind: "info", text: "Check your inbox. Your sign-in link is on its way." });
      } else if (mode === "signup") {
        const { data, error } = await supabase.auth.signUp({
          email,
          password,
          // after the email is confirmed, come back to THIS site (that address must also be in Supabase -> Authentication -> URL Configuration -> Redirect URLs)
          options: { data: { display_name: displayName }, emailRedirectTo: authCallbackUrl(window.location.origin) },
        });
        if (error) {
          setMessage({ kind: "error", text: friendlyAuthError(error.message, (error as { code?: string }).code).text });
        } else if (data.session) {
          router.push("/dashboard");
        } else {
          setMessage({ kind: "info", text: "Account created! Please open the link we emailed you to confirm it, then sign in. Check spam if you can't see it." });
          setCanResend(true);
        }
      } else {
        const { error } = await supabase.auth.signInWithPassword({ email, password });
        if (error) {
          const friendly = friendlyAuthError(error.message, (error as { code?: string }).code);
          setMessage({ kind: "error", text: friendly.text });
          setCanResend(friendly.needsConfirmation);
        } else {
          router.push("/dashboard");
        }
      }
    } catch {
      setMessage({ kind: "error", text: "Bubbles couldn't reach the sign-in service. Check your connection and try again." });
    } finally {
      setLoading(false);
    }
  }

  const heading = HEADINGS[mode];
  const inputClass =
    "min-h-[52px] w-full rounded-[18px] border-2 border-line bg-surface px-4 text-body text-ink outline-none transition-colors focus:border-bubbles-grape";

  return (
    <div className="w-full max-w-[440px] bubbles-rise">
      <div className="mb-6 flex flex-col items-center gap-3 text-center">
        <BubblesMascot size={96} mood={mode === "signup" ? "happy" : "calm"} />
        <h1 className="m-0 font-display text-h1">{heading.title}</h1>
        <p className="m-0 text-body text-ink-soft">{heading.body}</p>
      </div>

      <div className="rounded-[32px] border-2 border-line bg-surface p-6 shadow-md sm:p-8">
        <div role="tablist" aria-label="How would you like to continue?" className="mb-6 grid grid-cols-3 gap-1 rounded-full bg-blush p-1">
          {MODES.map((item) => (
            <button
              key={item.id}
              type="button"
              role="tab"
              id={`${formId}-${item.id}`}
              aria-selected={mode === item.id}
              aria-controls={`${formId}-panel`}
              onClick={() => switchMode(item.id)}
              className={`min-h-[44px] rounded-full px-2 text-body-sm font-extrabold transition-colors ${
                mode === item.id ? "bg-bubbles-pink-ink text-white shadow-[0_3px_0_var(--bubbles-pink-deep)]" : "text-ink-soft hover:text-ink"
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>

        {!isSupabaseConfigured && (
          <p role="alert" className="mb-4 rounded-[18px] bg-tint-sun px-4 py-3 text-body-sm font-bold text-bubbles-sun-deep">
            Sign-in isn&apos;t set up on this device yet. Add NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY to frontend/.env.local.
          </p>
        )}

        <div id={`${formId}-panel`} role="tabpanel" aria-labelledby={`${formId}-${mode}`}>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          {mode === "signup" && (
            <label className="flex flex-col gap-2 text-body-sm font-extrabold">
              What should Bubbles call you?
              <input type="text" autoComplete="nickname" value={displayName} onChange={(e) => setDisplayName(e.target.value)} className={inputClass} required maxLength={80} />
            </label>
          )}

          <label className="flex flex-col gap-2 text-body-sm font-extrabold">
            Email
            <input type="email" autoComplete="email" inputMode="email" value={email} onChange={(e) => setEmail(e.target.value)} className={inputClass} required />
          </label>

          {mode !== "magic" && (
            <label className="flex flex-col gap-2 text-body-sm font-extrabold">
              Password
              <input
                type="password"
                autoComplete={mode === "signup" ? "new-password" : "current-password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className={inputClass}
                required
                minLength={6}
              />
              {mode === "signup" && <span className="text-caption font-semibold text-ink-soft">At least 6 characters.</span>}
            </label>
          )}

          <button
            type="submit"
            disabled={loading}
            className="bubbles-press mt-2 inline-flex min-h-[56px] items-center justify-center gap-2 rounded-full bg-bubbles-pink-ink px-6 text-[1.0625rem] font-extrabold text-white shadow-[0_5px_0_var(--bubbles-pink-deep)] disabled:cursor-wait disabled:opacity-70"
          >
            {loading ? (
              <>
                <span className="flex gap-1" aria-hidden="true">
                  <span className="bubbles-thinking-dot !bg-white" />
                  <span className="bubbles-thinking-dot !bg-white" />
                  <span className="bubbles-thinking-dot !bg-white" />
                </span>
                Just a moment…
              </>
            ) : mode === "login" ? (
              "Sign in to Bubbles"
            ) : mode === "signup" ? (
              "Create my Bubbles"
            ) : (
              "Email me a link"
            )}
          </button>
        </form>
        </div>

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

        {canResend && (
          <button
            type="button"
            onClick={() => void resendConfirmation()}
            disabled={cooldown > 0 || !email}
            className="bubbles-press mt-3 inline-flex min-h-[48px] w-full items-center justify-center rounded-full border-2 border-line bg-surface px-5 text-body-sm font-extrabold text-bubbles-pink-ink disabled:cursor-not-allowed disabled:opacity-60"
          >
            {cooldown > 0 ? `Send the email again in ${cooldown}s` : "Send the confirmation email again"}
          </button>
        )}
      </div>

      <p className="mt-6 text-center text-body-sm font-semibold text-ink-soft">
        Bubbles does not diagnose. <Link href="/" className="font-extrabold text-bubbles-pink-ink">Learn about Bubbles</Link>
      </p>
      <p className="mt-2 text-center text-body-sm font-semibold text-ink-soft">
        <Link href="/privacy" className="font-extrabold text-bubbles-pink-ink">Privacy</Link>
        {" · "}
        <Link href="/terms" className="font-extrabold text-bubbles-pink-ink">Terms</Link>
      </p>
    </div>
  );
}

export default function LoginPage() {
  return (
    <main className="relative flex min-h-dvh items-center justify-center overflow-hidden bg-blush px-5 py-10">
      <div className="bubbles-drift pointer-events-none absolute -left-24 -top-24 h-72 w-72 rounded-full bg-tint-pink" aria-hidden="true" />
      <div className="bubbles-drift-slow pointer-events-none absolute -bottom-28 -right-20 h-80 w-80 rounded-full bg-tint-grape" aria-hidden="true" />
      <div className="relative z-base flex w-full justify-center">
        <Suspense fallback={<p className="text-ink-soft">Loading…</p>}>
          <LoginForm />
        </Suspense>
      </div>
    </main>
  );
}
