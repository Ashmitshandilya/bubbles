"use client";

import { useEffect, useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { supabase } from "../../lib/supabase";
import { BubblesMascot } from "../../components/BubblesMascot";
import { needsSecondStep } from "../../lib/mfa";

/** Where to go once the link has signed the person in: the code step first when the account has two-step sign-in on. */
async function nextPath(): Promise<string> {
  try {
    const { data } = await supabase.auth.mfa.getAuthenticatorAssuranceLevel();
    return needsSecondStep(data) ? "/login?mfa=1" : "/dashboard";
  } catch {
    return "/dashboard";
  }
}

function CallbackContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");
  const [message, setMessage] = useState("Processing authentication...");

  useEffect(() => {
    async function handleAuth() {
      // Check for access token in URL fragment (magic link redirect)
      const hash = window.location.hash;
      const code = searchParams.get("code");
      const tokenHash = searchParams.get("token_hash");
      if (code || tokenHash) {
        // Newer link styles carry a one-time code or token hash in the query string instead of the fragment.
        try {
          const { error } = code
            ? await supabase.auth.exchangeCodeForSession(code)
            : await supabase.auth.verifyOtp({ token_hash: tokenHash ?? "", type: (searchParams.get("type") as "signup" | "magiclink" | "email" | null) ?? "email" });
          if (error) {
            setStatus("error");
            setMessage("Your sign-in link may have expired or been used already. Please request a new one.");
          } else {
            setStatus("success");
            setMessage("Signed in! Redirecting...");
            router.push(await nextPath());
            router.refresh();
          }
        } catch {
          setStatus("error");
          setMessage("Bubbles couldn't confirm your sign-in. Please try again.");
        }
        return;
      }
      if (hash && hash.includes("access_token")) {
        const params = new URLSearchParams(hash.replace("#", ""));
        const accessToken = params.get("access_token");
        const refreshToken = params.get("refresh_token");
        // const expiresIn = params.get("expires_in"); // Unused but available if needed

        if (accessToken) {
          try {
            const { error } = await supabase.auth.setSession({
              access_token: accessToken,
              refresh_token: refreshToken || "",
            });

            if (error) {
              setStatus("error");
              setMessage("That sign-in link could not be used. It may have expired. Please request a new one.");
            } else {
              setStatus("success");
              setMessage("Signed in! Redirecting...");
              // Clean up URL and redirect
              window.history.replaceState({}, document.title, window.location.pathname);
              router.push(await nextPath());
              router.refresh();
            }
          } catch {
            setStatus("error");
            setMessage("Your sign-in link may have expired. Please request a new one.");
          }
        } else {
          // `#access_token=` with no value: without this branch the page would say "Signing you in…" forever.
          setStatus("error");
          setMessage("That sign-in link was incomplete. Please request a new one.");
        }
      } else {
        // Supabase reports a bad or expired link in the URL fragment (#error=...), other flows in the query string.
        const fragment = new URLSearchParams(hash.replace("#", ""));
        const error = searchParams.get("error") ?? fragment.get("error");
        const errorDescription = searchParams.get("error_description") ?? fragment.get("error_description");
        if (error) {
          setStatus("error");
          setMessage(
            fragment.get("error_code") === "otp_expired" || /expired/i.test(errorDescription ?? "")
              ? "That link has expired or was already used. Request a new one and open it on the same device."
              : `${error}: ${errorDescription || "Unknown error"}`,
          );
        } else {
          // Try to get session from Supabase (cookie-based)
          try {
            const { data: { session }, error } = await supabase.auth.getSession();
            if (session && !error) {
              setStatus("success");
              setMessage("Signed in! Redirecting...");
              router.push(await nextPath());
              router.refresh();
            } else {
              setStatus("error");
              setMessage("No valid session found. Please try logging in again.");
            }
          } catch {
            setStatus("error");
            setMessage("Bubbles couldn't confirm your sign-in. Please try again.");
          }
        }
      }
    }

    handleAuth();
  }, [router, searchParams]);

  return (
    <main className="flex min-h-dvh items-center justify-center bg-blush px-6">
      <div className="flex w-full max-w-md flex-col items-center gap-4 text-center bubbles-rise" role={status === "error" ? "alert" : "status"}>
        <BubblesMascot size={112} mood={status === "loading" ? "thinking" : status === "success" ? "happy" : "caring"} />
        {status === "loading" && (
          <>
            <h1 className="m-0 font-display text-h2">Signing you in…</h1>
            <span className="flex gap-1.5" aria-hidden="true">
              <span className="bubbles-thinking-dot" />
              <span className="bubbles-thinking-dot" />
              <span className="bubbles-thinking-dot" />
            </span>
          </>
        )}
        {status === "success" && <h1 className="m-0 font-display text-h2">You&apos;re in! Taking you to Bubbles…</h1>}
        {status === "error" && (
          <>
            <h1 className="m-0 font-display text-h2">That sign-in link didn&apos;t work</h1>
            <p className="m-0 text-body text-ink-soft">{message}</p>
            <button
              type="button"
              onClick={() => router.push("/login")}
              className="bubbles-press mt-2 min-h-[48px] rounded-full bg-bubbles-pink-ink px-6 font-extrabold text-white shadow-[0_5px_0_var(--bubbles-pink-deep)]"
            >
              Back to sign in
            </button>
          </>
        )}
      </div>
    </main>
  );
}

export default function CallbackPage() {
  return (
    <Suspense fallback={<div className="flex min-h-dvh items-center justify-center bg-blush"><BubblesMascot size={112} mood="thinking" /></div>}>
      <CallbackContent />
    </Suspense>
  );
}