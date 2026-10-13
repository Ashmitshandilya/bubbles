/**
 * Admin console wording and small decisions, kept pure so they are tested (format.test.ts).
 * Copy rules: plain words, units always shown, no em-dashes, "None yet" for a missing value, small samples say so.
 */

export const TABS = [
  { id: "overview", label: "Overview" },
  { id: "ai", label: "AI providers" },
  { id: "live", label: "Live" },
  { id: "api", label: "API routes" },
  { id: "logs", label: "Logs" },
  { id: "settings", label: "Settings" },
] as const;
export type TabId = (typeof TABS)[number]["id"];

export const RANGES = [
  { id: "15m", label: "15 min" },
  { id: "1h", label: "1 h" },
  { id: "6h", label: "6 h" },
  { id: "24h", label: "24 h" },
  { id: "7d", label: "7 days" },
  { id: "30d", label: "30 days" },
] as const;
export type RangeId = (typeof RANGES)[number]["id"];

export const NONE = "None yet";

/** Tab, range and open request from the address bar (unknown values fall back to the defaults). */
export function parseView(search: string): { tab: TabId; range: RangeId; request: string | null } {
  const q = new URLSearchParams(search);
  const tab = TABS.find((t) => t.id === q.get("tab"))?.id ?? "overview";
  const range = RANGES.find((r) => r.id === q.get("range"))?.id ?? "1h";
  const request = q.get("request");
  return { tab, range, request: request && /^[0-9a-f]{8,12}$/.test(request) ? request : null };
}

export function viewSearch(view: { tab: TabId; range: RangeId; request: string | null }): string {
  const q = new URLSearchParams();
  if (view.tab !== "overview") q.set("tab", view.tab);
  if (view.range !== "1h") q.set("range", view.range);
  if (view.request) q.set("request", view.request);
  const s = q.toString();
  return s ? `?${s}` : "";
}

export function num(n: number | null | undefined): string {
  return n === null || n === undefined ? NONE : Math.round(n).toLocaleString("en-IN");
}

/** "840 ms" under a second, then "2.4 s", then "1 min 5 s". */
export function ms(value: number | null | undefined): string {
  if (value === null || value === undefined) return NONE;
  if (value < 1000) return `${Math.round(value)} ms`;
  if (value < 60_000) return `${(value / 1000).toFixed(1)} s`;
  const m = Math.floor(value / 60_000);
  return `${m} min ${Math.round((value % 60_000) / 1000)} s`;
}

/** A 0..1 rate as a percentage: "0.4%" under 1%, whole numbers above, "None yet" without data. */
export function pct(rate: number | null | undefined): string {
  if (rate === null || rate === undefined) return NONE;
  const p = rate * 100;
  if (p > 0 && p < 1) return `${p.toFixed(1)}%`;
  return `${Math.round(p)}%`;
}

export function duration(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)} s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)} min`;
  const parts = (big: number, bigUnit: string, small: number, smallUnit: string) => (small ? `${big} ${bigUnit} ${small} ${smallUnit}` : `${big} ${bigUnit}`);
  if (seconds < 86_400) return parts(Math.floor(seconds / 3600), "h", Math.floor((seconds % 3600) / 60), "min");
  const days = Math.floor(seconds / 86_400);
  return parts(days, days === 1 ? "day" : "days", Math.floor((seconds % 86_400) / 3600), "h");
}

/** Local 24 h clock time, e.g. "09:12:03". */
export function clock(iso: string | null | undefined): string {
  if (!iso) return NONE;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return NONE;
  return d.toLocaleTimeString("en-GB", { hour12: false });
}

/** "just now", "2 min ago", "3 h ago", "4 days ago". */
export function ago(iso: string | null | undefined, now: number = Date.now()): string {
  if (!iso) return NONE;
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return NONE;
  const s = Math.max(0, (now - t) / 1000);
  if (s < 45) return "just now";
  if (s < 3600) return `${Math.round(s / 60)} min ago`;
  if (s < 86_400) return `${Math.round(s / 3600)} h ago`;
  return `${Math.round(s / 86_400)} days ago`;
}

/** Percentiles need enough calls to mean anything: p50 from 5, p95/p99 from 20. */
export function sampleNote(n: number, min: number): string | null {
  return n >= min ? null : `Not enough data yet (${n} of ${min} calls)`;
}

export function shortId(id: string | null | undefined): string {
  return id ? id.slice(0, 8) : NONE;
}

export type Health = "ok" | "warn" | "fail";
export type PillTone = "mint" | "sun" | "urgent" | "plain" | "sky" | "grape";

export const PILL_TONE: Record<PillTone, string> = {
  mint: "bg-tint-mint text-bubbles-mint-deep",
  sun: "bg-tint-sun text-bubbles-sun-deep",
  urgent: "bg-tint-urgent text-bubbles-urgent",
  plain: "border border-line bg-blush text-ink-soft",
  sky: "bg-tint-sky text-bubbles-sky-deep",
  grape: "bg-tint-grape text-bubbles-grape-deep",
};
export const DOT_TONE: Record<PillTone, string> = {
  mint: "bg-bubbles-mint", sun: "bg-bubbles-sun", urgent: "bg-bubbles-urgent", plain: "bg-line-strong", sky: "bg-bubbles-sky", grape: "bg-bubbles-grape",
};

export function healthTone(status: Health): PillTone {
  return status === "ok" ? "mint" : status === "warn" ? "sun" : "urgent";
}

export function healthWords(status: Health): string {
  return status === "ok" ? "Bubbles is OK" : status === "warn" ? "Bubbles is working, with warnings" : "Bubbles needs attention";
}

/** A provider's status from its success rate (needs 10 calls to judge). */
export function providerTone(row: { requests: number; success_rate: number | null }, paused: boolean): { tone: PillTone; word: string } {
  if (paused) return { tone: "plain", word: "Paused" };
  if (row.requests < 10 || row.success_rate === null) return { tone: "plain", word: "Too few calls" };
  if (row.success_rate >= 0.9) return { tone: "mint", word: "Healthy" };
  if (row.success_rate >= 0.6) return { tone: "sun", word: "Shaky" };
  return { tone: "urgent", word: "Failing" };
}

const WORDS: Record<string, string> = { ai: "AI", ok: "OK", api: "API", rag: "RAG", json: "JSON", nvidia: "NVIDIA" };

/** "ai_provider" -> "AI provider": lower case words, known short words kept as people write them. */
export function words(value: string | null | undefined): string {
  if (!value) return NONE;
  return value.replace(/[_.]+/g, " ").trim().split(/\s+/).map((w) => WORDS[w.toLowerCase()] ?? w.toLowerCase()).join(" ");
}

export function humanize(value: string | null | undefined): string {
  const s = words(value);
  return s === NONE ? s : s.charAt(0).toUpperCase() + s.slice(1);
}

export type OpsEvent = {
  seq?: number;
  id?: number;
  at: string;
  kind: "api" | "ai_attempt" | "ai_reply" | "error" | "audit";
  request_id: string | null;
  data: Record<string, unknown>;
};

const str = (v: unknown) => (typeof v === "string" ? v : v === null || v === undefined ? "" : String(v));
const n = (v: unknown) => (typeof v === "number" ? v : null);

export function kindLabel(kind: OpsEvent["kind"]): { word: string; tone: PillTone } {
  switch (kind) {
    case "api": return { word: "Request", tone: "plain" };
    case "ai_attempt": return { word: "AI try", tone: "sky" };
    case "ai_reply": return { word: "AI reply", tone: "mint" };
    case "error": return { word: "Error", tone: "urgent" };
    default: return { word: "Admin", tone: "grape" };
  }
}

const OUTCOME_WORDS: Record<string, string> = {
  success: "answered", error: "failed", timeout: "ran out of time", budget_spent: "had no time left", invalid_json: "gave an unusable answer",
};

/** One plain sentence per event for the live feed and the logs. Never more than the event holds. */
export function eventSentence(e: OpsEvent): string {
  const d = e.data;
  switch (e.kind) {
    case "api": {
      const extra = d.route_kind ? `, ${words(str(d.route_kind))}${d.ai_called === false ? ", no AI used" : ""}` : "";
      return `${str(d.method)} ${str(d.route)} ${str(d.status)} in ${ms(n(d.latency_ms))}${extra}`;
    }
    case "ai_attempt": {
      const why = d.error_category && d.outcome !== "success" ? ` (${words(str(d.error_category))})` : "";
      return `${str(d.provider)} ${OUTCOME_WORDS[str(d.outcome)] ?? str(d.outcome)} in ${ms(n(d.latency_ms))}, try ${str(d.position) || "1"}${why}`;
    }
    case "ai_reply":
      if (d.outcome === "degraded") return `No AI answer, calm message sent after ${ms(n(d.total_ms))}`;
      return `${str(d.provider)} answered${n(d.attempts) && (n(d.attempts) as number) > 1 ? ` after ${str(d.attempts)} tries` : ""}, ${ms(n(d.total_ms))}`;
    case "error": {
      const where = d.component && words(str(d.component)) !== words(str(d.category)) ? ` in ${words(str(d.component))}` : "";
      return `${humanize(str(d.category))} error${where}${d.route ? ` on ${str(d.route)}` : ""}`;
    }
    case "audit":
      if (d.action === "admin_denied") return `Someone was refused the admin portal (${words(str(d.target))})`;
      if (d.action === "setting_changed") return settingSentence(str(d.target), d.old, d.new);
      if (d.action === "setting_rejected") return `A change to ${str(d.target)} was refused`;
      if (d.action === "caches_cleared") return "Server caches were cleared";
      return humanize(str(d.action));
  }
}

/** An audited settings change in words: "Groq paused", "Consent cache turned off", "Log retention changed from 14 to 30 days". */
export function settingSentence(key: string, from: unknown, to: unknown): string {
  const [group, name] = key.split(".");
  if (group === "provider_paused" && name) return `${name} ${to === true ? "paused" : "running again"}`;
  if (group === "cache_enabled" && name) return `${humanize(name)} cache turned ${to === true ? "on" : "off"}`;
  if (key === "telemetry_retention_days") return `Log retention changed from ${str(from)} to ${str(to)} days`;
  return `${humanize(key)} changed`;
}

/** Gives a new live page: newest first, at most `cap` rows. */
export function mergeLive(current: OpsEvent[], incoming: OpsEvent[], cap = 200): OpsEvent[] {
  return [...[...incoming].reverse(), ...current].slice(0, cap);
}
