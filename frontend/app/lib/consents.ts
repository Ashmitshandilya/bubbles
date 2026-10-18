/** Privacy choices: the shapes the server sends (GET /consents, GET /consents/history) and the few decisions the screens make from them. */

export interface ConsentPurpose {
  id: string;
  title: string;
  description: string;
  textVersion: string;
  /** Fingerprint of the wording shown. A yes must quote it, so a stale screen cannot say yes to new wording. */
  textHash: string;
  available: boolean;
  granted: boolean;
  decision: "granted" | "declined" | "none";
  decidedAt: string | null;
}

export interface ConsentHistoryItem {
  purpose: string;
  title: string;
  granted: boolean;
  source: string;
  createdAt: string;
  kind: "consent" | "acknowledgement";
}

export interface Disclosure {
  id: string;
  title: string;
  text: string;
}

export interface ConsentOverview {
  policyVersion: string;
  purposes: ConsentPurpose[];
  disclosures: Disclosure[];
}

const text = (value: unknown): string => (typeof value === "string" ? value : "");

export function readPurpose(raw: unknown): ConsentPurpose | null {
  if (!raw || typeof raw !== "object") return null;
  const r = raw as Record<string, unknown>;
  if (!text(r.id) || !text(r.title) || !text(r.text_hash) || typeof r.granted !== "boolean") return null;
  const decision = r.decision === "granted" || r.decision === "declined" ? r.decision : "none";
  return {
    id: text(r.id),
    title: text(r.title),
    description: text(r.description),
    textVersion: text(r.text_version),
    textHash: text(r.text_hash),
    available: r.available !== false,
    granted: r.granted,
    decision,
    decidedAt: typeof r.decided_at === "string" ? r.decided_at : null,
  };
}

function readDisclosure(raw: unknown): Disclosure | null {
  if (!raw || typeof raw !== "object") return null;
  const r = raw as Record<string, unknown>;
  return text(r.id) ? { id: text(r.id), title: text(r.title), text: text(r.text) } : null;
}

export function readOverview(raw: unknown): ConsentOverview | null {
  if (!raw || typeof raw !== "object") return null;
  const r = raw as Record<string, unknown>;
  if (!Array.isArray(r.purposes)) return null;
  const purposes = r.purposes.map(readPurpose).filter((p): p is ConsentPurpose => p !== null);
  if (purposes.length === 0) return null;
  const disclosures = (Array.isArray(r.disclosures) ? r.disclosures : []).map(readDisclosure).filter((d): d is Disclosure => d !== null);
  return { policyVersion: text(r.policy_version), purposes, disclosures };
}

export function readHistory(raw: unknown): ConsentHistoryItem[] {
  const events = raw && typeof raw === "object" ? (raw as Record<string, unknown>).events : null;
  if (!Array.isArray(events)) return [];
  const out: ConsentHistoryItem[] = [];
  for (const e of events) {
    if (!e || typeof e !== "object") continue;
    const r = e as Record<string, unknown>;
    if (!text(r.purpose) || !text(r.created_at)) continue;
    out.push({
      purpose: text(r.purpose),
      title: text(r.title) || text(r.purpose),
      granted: r.granted === true,
      source: text(r.source),
      createdAt: text(r.created_at),
      kind: r.kind === "acknowledgement" ? "acknowledgement" : "consent",
    });
  }
  return out;
}

const SOURCE_LABEL: Record<string, string> = {
  settings: "in Privacy choices",
  chat_card: "in chat",
  onboarding: "when you set up",
  signup: "when you signed up",
  system: "by Bubbles when you deleted your data",
};

/** One plain line for "What you agreed to", e.g. "Turned on in chat, 14 Oct 2026". */
export function historyLine(item: ConsentHistoryItem, locale = "en-IN"): string {
  const when = new Date(item.createdAt);
  const day = Number.isNaN(when.getTime()) ? "" : when.toLocaleDateString(locale, { day: "numeric", month: "short", year: "numeric" });
  const verb = item.kind === "acknowledgement" ? "Read" : item.granted ? "Turned on" : "Turned off";
  const where = SOURCE_LABEL[item.source] ?? "";
  return [verb, where].filter(Boolean).join(" ") + (day ? `, ${day}` : "");
}

/** The body of PUT /consents/{id}. A yes carries the wording fingerprint; a withdrawal never needs it. */
export function changeBody(purpose: ConsentPurpose, granted: boolean, source: "settings" | "chat_card" | "onboarding" = "settings"): string {
  return JSON.stringify(granted ? { granted: true, source, text_hash: purpose.textHash } : { granted: false, source });
}

/** Whether saving `wanted` adds something to the ledger. A "not now" on a fresh account is a decision too (granted=false); only a repeat is skipped. */
export function needsDecision(purpose: ConsentPurpose, wanted: boolean): boolean {
  return wanted ? !purpose.granted : purpose.granted || purpose.decision !== "declined";
}

/** What the "outside AI" question in chat shows: the Yes / No card, a quiet line after a No, or nothing once it is on. */
export function aiCardView(purpose: ConsentPurpose | null | undefined): "ask" | "declined" | "granted" {
  if (!purpose) return "ask";
  if (purpose.granted) return "granted";
  return purpose.decision === "declined" ? "declined" : "ask";
}

/** Replace one purpose with the state the server just sent back (the list keeps its order). */
export function withPurpose(list: ConsentPurpose[], next: ConsentPurpose | null): ConsentPurpose[] {
  return next ? list.map((p) => (p.id === next.id ? next : p)) : list;
}
