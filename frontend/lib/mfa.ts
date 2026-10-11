/** Pure helpers for two-step sign-in (an authenticator app code). The Supabase calls themselves stay in the components. */

export interface FactorLike {
  id: string;
  factor_type?: string;
  status?: string;
}

export interface AssuranceLike {
  currentLevel?: string | null;
  nextLevel?: string | null;
}

/** True when the password step is done but the account also needs its authenticator code before the session counts. */
export function needsSecondStep(aal: AssuranceLike | null | undefined): boolean {
  return aal?.nextLevel === "aal2" && aal?.currentLevel !== "aal2";
}

/** The verified authenticator-app factor to challenge, if the account has one. */
export function verifiedTotp(factors: FactorLike[] | null | undefined): FactorLike | null {
  return (factors ?? []).find((f) => f.factor_type === "totp" && f.status === "verified") ?? null;
}

/** Authenticator apps show "123 456"; spaces and dashes are removed, anything but six digits is not a code. */
export function cleanCode(input: string): string {
  return input.replace(/[\s-]/g, "");
}

export function isValidCode(input: string): boolean {
  return /^\d{6}$/.test(cleanCode(input));
}

/** Plain wording for the errors Supabase returns while checking a code. */
export function friendlyMfaError(raw: string | null | undefined): string {
  const lower = String(raw ?? "").toLowerCase();
  if (lower.includes("invalid") || lower.includes("incorrect")) return "That code didn't work. Codes change every 30 seconds, so wait for a new one and try again.";
  if (lower.includes("rate limit") || lower.includes("too many")) return "Too many tries. Please wait a minute and try again.";
  if (lower.includes("failed to fetch") || lower.includes("network")) return "Bubbles couldn't reach the sign-in service. Check your connection and try again.";
  return "Bubbles couldn't check that code. Please try again.";
}
