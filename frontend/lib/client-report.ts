// Tells the server that something broke, as one fixed code (backend/ops_telemetry.py CLIENT_CODES). Never text, never an error
// message, never an id: the server reads nothing but `code`. Fire-and-forget, once per code per page load, never throws.

export type ClientCode = "render_error" | "unhandled_rejection" | "chunk_load_failed" | "api_unreachable" | "sign_in_refresh_failed" | "stream_fallback";

const sent = new Set<ClientCode>();

/** The website calls the API through its own address on https (see next.config.ts); the app and local development call it directly. */
export function reportUrl(env: string | undefined, here: { protocol: string; origin: string }, native = process.env.NEXT_PUBLIC_BUBBLES_NATIVE === "1"): string {
  if (here.protocol === "https:" && !native) return `${here.origin}/bubbles-api/telemetry/client`;
  return `${(env || "http://127.0.0.1:8000").replace(/\/+$/, "")}/telemetry/client`;
}

/** A React error or a failed script download, as a code. Only the error's name and kind are looked at, never shown or sent. */
export function codeForError(error: unknown): ClientCode {
  const e = error as { name?: unknown; message?: unknown } | null;
  return e?.name === "ChunkLoadError" || /loading (css )?chunk|failed to fetch dynamically imported module/i.test(String(e?.message ?? "")) ? "chunk_load_failed" : "render_error";
}

export function reportClientProblem(code: ClientCode): void {
  try {
    if (typeof window === "undefined" || sent.has(code)) return;
    sent.add(code);
    const url = reportUrl(process.env.NEXT_PUBLIC_API_URL, window.location);
    const body = JSON.stringify({ code });
    if (navigator.sendBeacon?.(url, new Blob([body], { type: "application/json" }))) return;
    void fetch(url, { method: "POST", body, headers: { "Content-Type": "application/json" }, keepalive: true }).catch(() => undefined);
  } catch {
    // reporting must never be the second thing that breaks
  }
}
