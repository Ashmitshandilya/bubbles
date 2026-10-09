// The partner page is public (no login), so it cannot use the signed-in API provider: AuthProvider sends visitors
// without a session to /login. These helpers build the one anonymous request that page makes.

export function apiBase(env: string | undefined = process.env.NEXT_PUBLIC_API_URL): string {
  return (env || "http://127.0.0.1:8000").replace(/\/+$/, "");
}

export function partnerEndpoint(token: string, base: string = apiBase()): string {
  return `${base}/cycle/partner/${encodeURIComponent(token)}`;
}

/** Kind wording for a failed partner-link request. `status` is null when no answer arrived at all. */
export function partnerErrorMessage(status: number | null): string {
  if (status === 404 || status === 410) return "This link is no longer active.";
  if (status === null) return "Bubbles could not be reached right now. Please try again in a moment.";
  if (status === 429) return "Too many tries just now. Please wait a minute and try again.";
  return "Something went wrong on our side. Please try again later.";
}
