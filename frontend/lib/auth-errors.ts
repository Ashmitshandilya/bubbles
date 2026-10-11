/** Plain-language versions of the messages Supabase returns when sign-in or sign-up does not go through. */
export function friendlyAuthError(raw: string | null | undefined): { text: string; needsConfirmation: boolean } {
  const message = String(raw ?? "");
  const lower = message.toLowerCase();
  if (lower.includes("email not confirmed"))
    return { text: "Please confirm your email first. Open the link we sent (check spam too), or send it again below.", needsConfirmation: true };
  if (lower.includes("invalid login credentials"))
    return { text: "That email and password don't match. If you just created your account, confirm your email first.", needsConfirmation: false };
  if (lower.includes("already registered") || lower.includes("already been registered"))
    return { text: "That email already has an account. Try signing in instead.", needsConfirmation: false };
  const wait = /after (\d+) seconds?/.exec(lower);
  if (wait) return { text: `Please wait ${wait[1]} seconds before asking for another email.`, needsConfirmation: false };
  if (lower.includes("rate limit")) return { text: "A lot of emails were sent just now. Please wait a few minutes and try again.", needsConfirmation: false };
  if (lower.includes("password") && (lower.includes("at least") || lower.includes("should be")))
    return { text: "Please choose a password with at least 6 characters.", needsConfirmation: false };
  return { text: message || "Something went wrong. Please try again.", needsConfirmation: false };
}

/** Seconds a person must wait before asking for another confirmation email. */
export const RESEND_COOLDOWN_SECONDS = 60;
