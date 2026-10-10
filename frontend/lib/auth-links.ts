/** Where Supabase should send people after they click an email link, and how to catch links that land on the wrong page. */

const PRODUCTION_SITE = "https://heybubbles.in";

const LOCAL = /^(localhost|127\.0\.0\.1|\[::1\]|[^.]+\.localhost)$/;

/** The public address of the site: NEXT_PUBLIC_SITE_URL, else the production domain, never with a trailing slash. */
export function siteUrl(configured: string | undefined = process.env.NEXT_PUBLIC_SITE_URL): string {
  return (configured?.trim() || PRODUCTION_SITE).replace(/\/+$/, "");
}

/**
 * The address confirmation and sign-in emails send people back to.
 * Local development stays local; everywhere else (including a *.vercel.app deployment) uses the real site address,
 * so an email link never points at a throwaway Vercel URL.
 */
export function authCallbackUrl(origin: string, configured?: string): string {
  let host = "";
  try {
    host = new URL(origin).hostname;
  } catch {
    /* an unreadable origin falls through to the site address */
  }
  return `${LOCAL.test(host) ? origin.replace(/\/+$/, "") : siteUrl(configured)}/callback`;
}

/** True when the current page is not /callback but the address carries the result of an email-link sign-in. */
export function looksLikeAuthReturn(pathname: string, search: string, hash: string): boolean {
  if (pathname === "/callback" || pathname.startsWith("/callback/")) return false;
  const fragment = new URLSearchParams(hash.replace(/^#/, ""));
  if (fragment.has("access_token") || fragment.has("error_code") || (fragment.has("error") && fragment.has("error_description"))) return true;
  const query = new URLSearchParams(search.replace(/^\?/, ""));
  return query.has("token_hash") || (query.has("code") && pathname === "/");
}
