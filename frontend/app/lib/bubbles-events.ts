/**
 * Canonical adapter for the Bubbles chat response contract.
 *
 * The backend returns:
 *   health_events: { id, event_type, extracted_data, confidence, assertion, temporal, status }
 *   health_event_ids: (string|null)[]  — deprecated, parallel to health_events by index
 *   safety:        { level, state, reasons, retracted, correction? }
 *   evidence:      { chunk_id, title, source_name, source_url,
 *                    publisher, evidence_level, fused_score }
 *
 * Views must not reshape these inline. One adapter, one shape, so the
 * contract has exactly one place to change when the backend moves.
 *
 * Every field added after the first contract is optional here: an older
 * backend, a half-migrated one and a malformed payload must all render.
 *
 * Note on ids: each health event carries its own `id` (null when unsaved). The
 * deprecated parallel `health_event_ids` array is used only as a fallback for an
 * older backend, and only when it lines up one-to-one with the events.
 */

/** Effective triage level the UI branches on. URGENT and EMERGENCY both render as RED. */
export type SafetyLevel = "GREEN" | "AMBER" | "RED";
export type SafetyState = "NO_REDFLAG" | "POTENTIAL_REDFLAG_NEEDS_CLARIFICATION" | "URGENT" | "EMERGENCY";
export type ReplyKind = "reply" | "clarification" | "emergency" | "correction_ack" | "daily_log_summary";

export interface SafetyView {
  /** Effective level: GREEN once the warning was retracted, otherwise the most cautious of state and level. */
  level: SafetyLevel;
  /** The level as persisted, kept so a retracted warning can still say what it was. */
  originalLevel: SafetyLevel;
  state: SafetyState | null;
  reasons: string[];
  retracted: boolean;
  retractedAt: string | null;
  retractedBy: string | null;
}

/** A correction reported by POST /chat: the user told Bubbles it misread an earlier message. */
export interface Correction {
  retractedMessageId: string;
  concepts: string[];
  retractedEventIds: string[];
  keptEventIds: string[];
}

export interface ExtractedHealthEvent {
  /** Stable backend id. Null when the backend did not persist the event. */
  id: string | null;
  eventType: string;
  description: string;
  confidence: number | null;
  /** present | negated | possible | hypothetical | question | other_person | quoted. Null when the backend did not say. */
  assertion: string | null;
  /** current | recent | past | resolved | recurring | future | unknown. Null when the backend did not say. */
  temporal: string | null;
  /** pending | confirmed | rejected | superseded | retracted. Null when the backend did not say. */
  status: string | null;
  /** Concepts the user explicitly denied (a symptom screen), shown read-only. Empty otherwise. */
  notPresent: string[];
  /** Whether this event can be confirmed: it has an id, is asserted as present and is still pending. */
  isConfirmable: boolean;
}

export interface EvidenceItem {
  chunkId: string | null;
  title: string;
  sourceName: string;
  sourceUrl: string | null;
  publisher: string | null;
  evidenceLevel: string | null;
  fusedScore: number | null;
}

/** Raw shapes as returned by POST /chat. Kept narrow on purpose. */
interface RawHealthEvent {
  id?: unknown;
  event_type?: unknown;
  extracted_data?: unknown;
  confidence?: unknown;
  assertion?: unknown;
  temporal?: unknown;
  status?: unknown;
}

interface RawEvidence {
  chunk_id?: unknown;
  title?: unknown;
  source_name?: unknown;
  source_url?: unknown;
  publisher?: unknown;
  evidence_level?: unknown;
  fused_score?: unknown;
}

function asString(value: unknown): string | null {
  return typeof value === "string" && value.length > 0 ? value : null;
}

function asNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : null;
}

function asStrings(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((v): v is string => typeof v === "string" && v.trim() !== "").map((v) => v.trim())
    : [];
}

// ---------------------------------------------------------------------------
// Safety
// ---------------------------------------------------------------------------

const RANK: Record<SafetyLevel, number> = { GREEN: 0, AMBER: 1, RED: 2 };
const STATE_LEVEL: Record<SafetyState, SafetyLevel> = {
  NO_REDFLAG: "GREEN",
  POTENTIAL_REDFLAG_NEEDS_CLARIFICATION: "AMBER",
  URGENT: "RED",
  EMERGENCY: "RED",
};

function isSafetyState(value: string): value is SafetyState {
  return Object.prototype.hasOwnProperty.call(STATE_LEVEL, value);
}

/** Level named by a raw value. Missing means "no opinion"; anything unrecognised fails toward caution (AMBER). */
function levelOf(value: unknown): SafetyLevel | null {
  if (value === null || value === undefined) return null;
  if (typeof value === "string") {
    const text = value.trim().toUpperCase();
    if (text === "") return null;
    if (text === "GREEN" || text === "AMBER" || text === "RED") return text;
  }
  return "AMBER";
}

/**
 * One reading of the backend's safety object. `state` and `level` are both consulted and the more cautious wins,
 * so a renamed or half-migrated backend can never turn a warning into silence. Only a wholly missing safety
 * object means GREEN. `retracted` counts only when it is the boolean true.
 */
export function adaptSafety(rawSafety: unknown, legacyLevel?: unknown): SafetyView {
  const raw = asRecord(rawSafety);
  const rawState = raw?.state;
  const stateText = typeof rawState === "string" ? rawState.trim().toUpperCase() : "";
  const state = isSafetyState(stateText) ? stateText : null;

  const fromState = state ? STATE_LEVEL[state] : levelOf(rawState);
  const fromLevel = levelOf(raw?.level) ?? levelOf(legacyLevel);
  const original = [fromState, fromLevel].reduce<SafetyLevel>(
    (worst, level) => (level !== null && RANK[level] > RANK[worst] ? level : worst),
    "GREEN"
  );
  const retracted = raw?.retracted === true;

  return {
    level: retracted ? "GREEN" : original,
    originalLevel: original,
    state,
    reasons: asStrings(raw?.reasons),
    retracted,
    retractedAt: asString(raw?.retracted_at),
    retractedBy: asString(raw?.retracted_by_message_id),
  };
}

const REPLY_KINDS: ReplyKind[] = ["reply", "clarification", "emergency", "correction_ack", "daily_log_summary"];

export function adaptKind(raw: unknown): ReplyKind | undefined {
  return REPLY_KINDS.find((kind) => kind === raw);
}

/** The safety fields of one assistant message, shared by live replies and reloaded history. */
export function adaptReplySafety(
  rawSafety: unknown,
  legacyLevel: unknown,
  rawKind: unknown
): {
  safetyLevel: SafetyLevel;
  safetyState: SafetyState | null;
  safetyReasons: string[];
  retracted: boolean;
  kind: ReplyKind | undefined;
} {
  const safety = adaptSafety(rawSafety, legacyLevel);
  const kind = adaptKind(rawKind);
  // A reply that calls itself an emergency is never shown as calm, even if the safety object is missing or stale.
  const escalate = kind === "emergency" && !safety.retracted && safety.level !== "RED";
  return {
    safetyLevel: escalate ? "RED" : safety.level,
    safetyState: escalate ? "EMERGENCY" : safety.state,
    safetyReasons: safety.reasons,
    retracted: safety.retracted,
    kind,
  };
}

/** Red alert styling and the hidden mascot key on this; a retracted warning never counts. */
export function isUrgentMessage(message: { retracted?: boolean; safetyLevel?: SafetyLevel }): boolean {
  return !message.retracted && message.safetyLevel === "RED";
}

export function adaptCorrection(raw: unknown): Correction | null {
  const data = asRecord(raw);
  const retractedMessageId = asString(data?.retracted_message_id);
  if (!data || !retractedMessageId) return null;
  return {
    retractedMessageId,
    concepts: asStrings(data.concepts),
    retractedEventIds: asStrings(data.retracted_event_ids),
    keptEventIds: asStrings(data.kept_event_ids),
  };
}

/** "chest pain", "chest pain or headache", "chest pain, headache or nausea". */
function joinConcepts(concepts: string[]): string {
  return concepts.length < 2 ? concepts.join("") : `${concepts.slice(0, -1).join(", ")} or ${concepts[concepts.length - 1]}`;
}

/**
 * The reasons behind a warning, as a sentence for the banner. A reason the backend already phrased as what the user
 * said ("you mentioned chest pain yesterday") is printed as given. A bare concept keeps the "Bubbles noticed" framing,
 * except for a POTENTIAL state, where "Bubbles noticed" would claim a symptom Bubbles is not sure about: there it is
 * "You mentioned". Empty string when there are no reasons.
 */
export function reasonSentence(reasons: string[] | undefined, state?: SafetyState | null): string {
  if (!reasons || reasons.length === 0) return "";
  const text = reasons.join(", ");
  const full = (t: string) => `${t.charAt(0).toUpperCase()}${t.slice(1)}${/[.!?]$/.test(t) ? "" : "."} `;
  if (/^you\b/i.test(text)) return full(text);
  if (state === "POTENTIAL_REDFLAG_NEEDS_CLARIFICATION") return `You mentioned ${text}. `;
  return `Bubbles noticed ${text}. `;
}

/** Calm note shown on a withdrawn warning. Names the concepts only when the correction told us which. */
export function retractionNote(concepts: string[] | undefined): string {
  const told = concepts?.length
    ? ` You told Bubbles you did not have ${joinConcepts(concepts)}, so that warning no longer applies.`
    : " That warning no longer applies.";
  return `Bubbles misread what you said.${told} If anything changes or you feel unwell, tell Bubbles or contact a clinician.`;
}

/**
 * Mark the corrected message as retracted. Idempotent, ignores unknown ids, and returns the very same array
 * when nothing changed so React skips the re-render.
 */
export function applyCorrection<T extends { id: string; retracted?: boolean; retractionConcepts?: string[] }>(
  messages: T[],
  correction: Correction | null
): T[] {
  if (!correction) return messages;
  const target = messages.findIndex((m) => m.id === correction.retractedMessageId);
  if (target === -1 || messages[target].retracted) return messages;
  const next = messages.slice();
  next[target] = { ...messages[target], retracted: true, retractionConcepts: correction.concepts };
  return next;
}

/** Replace the message with the same id, or append. Keeps a replayed reply from rendering twice. */
export function upsertById<T extends { id: string }>(messages: T[], message: T): T[] {
  const at = messages.findIndex((m) => m.id === message.id);
  if (at === -1) return [...messages, message];
  const next = messages.slice();
  next[at] = message;
  return next;
}

/**
 * Give an optimistic bubble its server id. The old id is kept as `clientId` so the React key stays stable.
 * No-op when `fromId` is unknown or `toId` is already in the list.
 */
export function replaceId<T extends { id: string; clientId?: string }>(messages: T[], fromId: string, toId: string): T[] {
  if (fromId === toId || messages.some((m) => m.id === toId)) return messages;
  const at = messages.findIndex((m) => m.id === fromId);
  if (at === -1) return messages;
  const next = messages.slice();
  next[at] = { ...messages[at], id: toId, clientId: messages[at].clientId ?? fromId };
  return next;
}

// ---------------------------------------------------------------------------
// Health events
// ---------------------------------------------------------------------------

/** Keys that describe the record rather than the health event. Never shown to the user. */
const METADATA_KEYS = new Set(["assertion", "temporal", "status", "provenance"]);
const isMetadataKey = (key: string) => key.startsWith("_") || METADATA_KEYS.has(key);

/**
 * Turn structured extracted_data into one readable sentence.
 * Falls back to the raw JSON only as a last resort so the UI is never
 * blank, but JSON is not the normal path — a user should read English.
 */
function describe(extractedData: unknown): string {
  const data = asRecord(extractedData);
  if (!data) return "No additional detail was recorded for this event.";

  const denied = asStrings(data.pertinent_negatives);
  if (denied.length) return `Not present: ${denied.join(", ")}`;

  const entries = Object.entries(data).filter(
    ([key, value]) =>
      !isMetadataKey(key) &&
      value !== null &&
      value !== undefined &&
      value !== "" &&
      !(Array.isArray(value) && value.length === 0)
  );

  if (entries.length === 0) return "No additional detail was recorded for this event.";

  return entries
    .map(([key, value]) => {
      const label = key.replace(/_/g, " ");
      if (typeof value === "number") return `${label}: ${value}`;
      if (typeof value === "boolean") return `${label}: ${value ? "yes" : "no"}`;
      if (Array.isArray(value)) return `${label}: ${value.map(String).join(", ")}`;
      return `${label}: ${String(value)}`;
    })
    .join(" · ");
}

export function adaptHealthEvents(raw: unknown, rawIds: unknown): ExtractedHealthEvent[] {
  if (!Array.isArray(raw)) return [];
  // The parallel id array is only trusted when it lines up one-to-one; a shorter list means a skipped event
  // shifted every later id, and guessing would confirm the wrong row.
  const parallel = Array.isArray(rawIds) && rawIds.length === raw.length ? rawIds : null;

  return raw.map((item: RawHealthEvent, index: number) => {
    const event = asRecord(item);
    const eventType = asString(event?.event_type) ?? "health event";
    // An inline id wins. An explicit null means the backend did not save this event, so no fallback.
    const id = event && "id" in event ? asString(event.id) : asString(parallel?.[index]);
    const data = asRecord(event?.extracted_data);
    const prov = asRecord(data?._prov);
    const assertion = asString(event?.assertion) ?? asString(prov?.assertion) ?? (data?.present === false ? "negated" : null);
    const status = asString(event?.status);
    return {
      id,
      eventType,
      // The backend's one-line summary ("Slept 6h 42m") wins; the key dump is only the fallback for older replies.
      description: asString(event?.summary) ?? describe(event?.extracted_data),
      confidence: asNumber(event?.confidence),
      assertion,
      temporal: asString(event?.temporal),
      status,
      notPresent: asStrings(data?.pertinent_negatives),
      isConfirmable: id !== null && (assertion === null || assertion === "present") && (status === null || status === "pending"),
    };
  });
}

/** What the server already says about an event, so a reloaded message does not re-offer a settled one. */
export function settledState(event: ExtractedHealthEvent): "saved" | "dismissed" | "retracted" | null {
  if (event.status === "confirmed") return "saved";
  if (event.status === "rejected") return "dismissed";
  if (event.status === "retracted" || event.status === "superseded") return "retracted";
  return null;
}

const ASSERTION_NOTES: Record<string, string> = {
  negated: "You said this isn't happening, so it won't be saved as a symptom.",
  possible: "Not confirmed yet, so it won't be saved.",
  hypothetical: "Hypothetical, so it won't be saved.",
  question: "You asked about this rather than reporting it, so it won't be saved.",
  other_person: "This was about someone else, so it won't be saved to your record.",
  quoted: "This was quoted rather than reported as yours, so it won't be saved.",
};

/** Why an event has no save button, or null when it is simply waiting for a decision. */
export function eventNote(event: ExtractedHealthEvent): string | null {
  if (event.isConfirmable || settledState(event)) return null;
  if (event.id === null) return "This one couldn't be staged, so it won't be saved.";
  if (event.assertion !== null && event.assertion !== "present") {
    return ASSERTION_NOTES[event.assertion] ?? "Bubbles isn't sure this applies to you, so it won't be saved.";
  }
  return null;
}

export function adaptEvidence(raw: unknown): EvidenceItem[] {
  if (!Array.isArray(raw)) return [];
  return raw.map((item: RawEvidence) => ({
    chunkId: asString(item?.chunk_id),
    title: asString(item?.title) ?? "Source",
    sourceName: asString(item?.source_name) ?? "Unknown source",
    // Only http(s) links become clickable; anything else (javascript:, data:) is dropped.
    sourceUrl: /^https?:\/\//i.test(asString(item?.source_url) ?? "") ? asString(item?.source_url) : null,
    publisher: asString(item?.publisher),
    evidenceLevel: asString(item?.evidence_level),
    fusedScore: asNumber(item?.fused_score),
  }));
}

/**
 * Bubbles replies use a small markdown subset (headings, bullets, numbered
 * lists, **bold**). Parse it into plain blocks so views render real elements
 * from text nodes — never HTML from the response.
 */
export type ChatBlock =
  | { kind: "heading"; text: string }
  | { kind: "paragraph"; text: string }
  | { kind: "list"; ordered: boolean; items: string[] };

export function parseChatMarkdown(text: string): ChatBlock[] {
  const blocks: ChatBlock[] = [];
  let para: string[] = [];
  const flush = () => {
    if (para.length) blocks.push({ kind: "paragraph", text: para.join("\n") });
    para = [];
  };
  for (const raw of String(text ?? "").split(/\r?\n/)) {
    const line = raw.trim();
    const heading = /^#{1,6}\s+(.+)$/.exec(line);
    const item = /^(?:[-*•]|(\d+)[.)])\s+(.+)$/.exec(line);
    if (!line) {
      flush();
    } else if (heading) {
      flush();
      blocks.push({ kind: "heading", text: heading[1] });
    } else if (item) {
      flush();
      const ordered = item[1] !== undefined;
      const last = blocks[blocks.length - 1];
      if (last?.kind === "list" && last.ordered === ordered) last.items.push(item[2]);
      else blocks.push({ kind: "list", ordered, items: [item[2]] });
    } else {
      para.push(line);
    }
  }
  flush();
  return blocks;
}

/** Split `**bold**` runs out of a line. Odd split indexes are the captured bold text. */
export function splitBold(text: string): { text: string; bold: boolean }[] {
  return text
    .split(/\*\*(.+?)\*\*/g)
    .map((part, index) => ({ text: part, bold: index % 2 === 1 }))
    .filter((part) => part.text);
}

/** Human label for a confidence score. Uncertainty is preserved, not rounded into certainty. */
export function confidenceLabel(confidence: number | null): string | null {
  if (confidence === null) return null;
  const pct = Math.round(confidence * 100);
  if (pct >= 85) return `${pct}%, high`;
  if (pct >= 60) return `${pct}%, moderate`;
  return `${pct}%, low, worth checking`;
}
