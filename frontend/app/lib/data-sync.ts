// "Something changed": one place that decides which successful writes count as a change to the person's record, what
// to call them ("Weight"), and how that change is remembered and shared with other tabs. Pure helpers plus a small
// browser store, so the rules are testable and every screen reacts to the same signal.

export interface LastUpdate {
  /** Plain label for what changed ("Weight", "Sleep", "Chat"). */
  label: string;
  /** Epoch ms of the change. */
  at: number;
}

const LABELS: Record<string, string> = {
  weight: "Weight", sleep: "Sleep", mood: "Mood", activity: "Activity", hydration: "Water", nutrition: "Food",
  cycle: "Cycle", vitals: "Vitals", symptoms: "Symptoms", medications: "Medications", allergies: "Allergies",
  conditions: "Conditions", labs: "Lab results", visits: "Visits", mind: "Mind", fitness: "Fitness",
};

/** Writes that are about settings or plumbing, not the person's record. They never move the "last updated" card. */
const NOT_RECORD = ["/health", "/consents", "/me/consent", "/admin", "/onboarding", "/chat/feedback", "/experience"];

function pathOnly(path: string): string {
  return path.split("?")[0].replace(/\/+$/, "");
}

function isHealthProbe(path: string): boolean {
  return path === "/health";
}

/**
 * What a successful write changed, or null when it is not a change to the person's record (a GET, a consent, a probe).
 * Chat messages and confirming a picked-up event count: Companion is part of the record too.
 */
export function describeWrite(path: string, method: string | undefined): string | null {
  if ((method || "GET").toUpperCase() === "GET") return null;
  const p = pathOnly(path);
  if (isHealthProbe(p)) return null;
  const tracker = /^\/health\/([a-z-]+)/.exec(p)?.[1];
  if (tracker && tracker !== "summary") return LABELS[tracker] ?? tracker.charAt(0).toUpperCase() + tracker.slice(1);
  if (NOT_RECORD.some((prefix) => p === prefix || p.startsWith(`${prefix}/`))) return null;
  if (p === "/chat" || p.startsWith("/chat/")) return "Chat";
  if (p.startsWith("/health-events") || p.startsWith("/memory")) return "Companion notes";
  if (p.startsWith("/profile")) return "Profile";
  if (p.startsWith("/cycle")) return "Cycle";
  if (p.startsWith("/fitness")) return "Fitness";
  if (p.startsWith("/medical") || p.startsWith("/doctor")) return "Care";
  return "Your record";
}

/** "just now", "5 minutes ago", "2 hours ago", "yesterday", or a short date. */
export function agoText(at: number, now = Date.now()): string {
  const seconds = Math.max(0, Math.round((now - at) / 1000));
  if (seconds < 45) return "just now";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} minute${minutes === 1 ? "" : "s"} ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} hour${hours === 1 ? "" : "s"} ago`;
  const days = Math.round(hours / 24);
  if (days === 1) return "yesterday";
  if (days < 7) return `${days} days ago`;
  return new Date(at).toLocaleDateString("en-GB", { day: "numeric", month: "short" });
}

/**
 * The newer of what this browser saw and what the server reports for the person (so a change made on another device
 * shows too). The server only knows the day, so a local change from the same day or later wins.
 */
export function pickLastUpdate(local: LastUpdate | null, serverIso: string | null | undefined): LastUpdate | null {
  const serverAt = serverIso ? Date.parse(serverIso) : NaN;
  const server = Number.isFinite(serverAt) ? { label: "Your record", at: serverAt } : null;
  if (local && server) return local.at >= server.at ? local : server;
  return local ?? server;
}

const KEY = (uid: string) => `bubbles:last-update:${uid}`;
const CHANNEL = "bubbles-data";

function storage(): Storage | null {
  try { return typeof window === "undefined" ? null : window.localStorage; } catch { return null; }
}

export function readLastUpdate(uid: string | null): LastUpdate | null {
  if (!uid) return null;
  try {
    const raw = JSON.parse(storage()?.getItem(KEY(uid)) ?? "null") as Partial<LastUpdate> | null;
    return raw && typeof raw.label === "string" && typeof raw.at === "number" ? { label: raw.label, at: raw.at } : null;
  } catch { return null; }
}

/** Remember a change and tell the other tabs of this browser. Never throws. */
export function announceChange(uid: string | null, update: LastUpdate): void {
  if (uid) {
    try { storage()?.setItem(KEY(uid), JSON.stringify(update)); } catch { /* private mode: the signal below still works */ }
  }
  try {
    if (typeof BroadcastChannel !== "undefined") {
      const channel = new BroadcastChannel(CHANNEL);
      channel.postMessage({ uid, ...update });
      channel.close();
    }
  } catch { /* other tabs refresh on their next focus instead */ }
}

/** Call `onChange` when another tab announces a change for the same person. Returns the cleanup. */
export function listenForChanges(uid: string | null, onChange: (update: LastUpdate) => void): () => void {
  if (typeof BroadcastChannel === "undefined") return () => undefined;
  const channel = new BroadcastChannel(CHANNEL);
  channel.onmessage = (event: MessageEvent) => {
    const data = event.data as { uid?: string | null } & Partial<LastUpdate>;
    if (data && data.uid === uid && typeof data.label === "string" && typeof data.at === "number") {
      onChange({ label: data.label, at: data.at });
    }
  };
  return () => channel.close();
}
