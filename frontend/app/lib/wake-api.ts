/** Where to send the quiet "wake up" call: the website's own route to the API (same site, no CORS), or nothing when there is no such route
 * (plain-http local development and the Android app talk to the API directly and are not waiting on a sleeping host). */
export function wakeUrl(protocol: string, origin: string, native: boolean): string | null {
  if (native || protocol !== "https:") return null;
  return `${origin}/bubbles-api/health`;
}
