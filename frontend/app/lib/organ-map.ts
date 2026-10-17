/**
 * Body map: typed reader for GET /organs/map plus the status vocabulary shared by the 3D viewer, the flat fallback,
 * the organ list and the panel. Every reader here tolerates missing or malformed fields: an organ the server says
 * little about is shown as "No data yet", never as fine.
 */

import { parseWhen } from "./dates";

export type OrganStatus = "no_data" | "steady" | "worth_watching" | "talk_to_doctor";
export type Confidence = "low" | "medium" | "high";

export interface OrganEvidence {
  date: string | null;
  value: string;
  source: string | null;
}

export interface Organ {
  id: string;
  name: string;
  status: OrganStatus;
  /** Server wording for this organ, when it sends one. The panel falls back to the status meaning. */
  explanation: string | null;
  /** Every further reason the server gives (its `reasons` list minus the one used as the explanation). */
  reasons: string[];
  /** Background the server adds without changing the status (e.g. a cycle note). */
  notes: string[];
  /** Day of the newest entry behind this organ, not when the map was built. */
  updatedAt: string | null;
  evidence: OrganEvidence[];
  /** How many entries sit behind this organ. The server sends only the newest few in `evidence`, so this can be larger. */
  evidenceCount: number;
  confidence: Confidence | null;
  /** Why Bubbles is that sure (or unsure), in the server's words. */
  confidenceReason: string | null;
  missing: string[];
  nextStep: string | null;
  chatPrompt: string;
  /** Safety guidance the server puts first (a red flag re-checked by the safety engine), shown above everything else. */
  safety: string | null;
}

/**
 * The API reports grouped areas ("kidneys_bladder"); the model and the flat body draw separate parts ("kidneys",
 * "bladder"). An id the table does not know is drawn by its own name, if a part with that name exists.
 */
export const ORGAN_PARTS: Record<string, readonly string[]> = {
  heart: ["heart"],
  lungs: ["lungs"],
  brain: ["brain"],
  eyes: ["eye_left", "eye_right"],
  stomach_intestines: ["stomach", "intestines"],
  liver_pancreas: ["liver", "pancreas"],
  kidneys_bladder: ["kidneys", "bladder"],
  thyroid: ["thyroid"],
  uterus_ovaries: ["uterus", "ovaries"],
  skeleton_muscles: ["skeleton"],
  skin: ["skin"],
};

export const partsOf = (organId: string): readonly string[] => ORGAN_PARTS[organId] ?? [organId];

/** Drawn part -> the organ it belongs to. */
export function partOwners(organs: readonly Organ[]): Map<string, Organ> {
  const owners = new Map<string, Organ>();
  for (const organ of organs) for (const part of partsOf(organ.id)) if (!owners.has(part)) owners.set(part, organ);
  return owners;
}

export const STATUS_ORDER: readonly OrganStatus[] = ["talk_to_doctor", "worth_watching", "steady", "no_data"];

/**
 * `color` is a tokens.css variable (read at runtime by the 3D viewer, used directly by the SVG). "Talk to a doctor" is
 * the deep red-brown, never a bright red: it should read as serious and steady, not alarming.
 */
export const STATUS_META: Record<OrganStatus, { label: string; meaning: string; nextStep: string; color: string; pill: string }> = {
  talk_to_doctor: {
    label: "Talk to a doctor",
    meaning: "Your entries include something a doctor should look at.",
    nextStep: "Book a visit with a doctor and bring these entries with you.",
    color: "--bubbles-peach-deep",
    pill: "bg-tint-peach text-bubbles-peach-deep",
  },
  worth_watching: {
    label: "Worth watching",
    meaning: "Something in your entries is worth keeping an eye on.",
    nextStep: "Keep logging for the next week so Bubbles can see whether it settles.",
    color: "--bubbles-sun",
    pill: "bg-tint-sun text-bubbles-sun-deep",
  },
  steady: {
    label: "Steady",
    meaning: "Your recent entries don't point to a change. That is not an all-clear.",
    nextStep: "Keep logging as you do now. Bubbles will tell you if something shifts.",
    color: "--bubbles-mint",
    pill: "bg-tint-mint text-bubbles-mint-deep",
  },
  no_data: {
    label: "No data yet",
    meaning: "Bubbles has nothing recent to go on. Missing data is never read as healthy.",
    nextStep: "Log anything that relates to this part of the body, and Bubbles will start a picture.",
    color: "--bubbles-line-strong",
    pill: "border border-dashed border-line-strong text-ink-soft",
  },
};

/** Calm base tint per organ (tokens.css variables). Status shows as a glow on top, not as the organ's colour. */
/** Keyed by drawn part. */
export const ORGAN_TINT: Record<string, string> = {
  brain: "--tint-grape",
  eye_left: "--bubbles-white",
  eye_right: "--bubbles-white",
  heart: "--tint-pink",
  lungs: "--tint-pink",
  liver: "--tint-peach",
  stomach: "--tint-peach",
  intestines: "--tint-peach",
  pancreas: "--tint-sun",
  kidneys: "--tint-grape",
  bladder: "--tint-sky",
  thyroid: "--tint-sky",
  uterus: "--tint-pink",
  ovaries: "--tint-pink",
  skeleton: "--tint-sun",
  skin: "--bubbles-white",
};

export const CONFIDENCE_LABEL: Record<Confidence, string> = { low: "Low", medium: "Medium", high: "High" };

const STATUSES = new Set<string>(STATUS_ORDER);

const text = (value: unknown): string | null => {
  if (typeof value === "number" && Number.isFinite(value)) return String(value);
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
};

const humanize = (id: string) => {
  const s = id.replaceAll("_", " ").trim();
  return s ? s[0].toUpperCase() + s.slice(1) : s;
};

/** Accepts "low|medium|high", a 0-1 score or a 0-100 percentage. Anything else is unknown, not "high". */
export function readConfidence(value: unknown): Confidence | null {
  if (typeof value === "string") {
    const word = value.trim().toLowerCase();
    if (word === "low" || word === "medium" || word === "high") return word;
    const n = Number(word);
    return word && Number.isFinite(n) ? readConfidence(n) : null;
  }
  if (typeof value !== "number" || !Number.isFinite(value) || value < 0) return null;
  const score = value > 1 ? value / 100 : value;
  if (score > 1) return null;
  return score >= 0.7 ? "high" : score >= 0.4 ? "medium" : "low";
}

function readEvidence(value: unknown): OrganEvidence | null {
  const direct = text(value);
  if (direct) return { date: null, value: direct, source: null };
  if (!value || typeof value !== "object") return null;
  const item = value as Record<string, unknown>;
  const label = text(item.label) ?? text(item.name);
  const reading = text(item.value) ?? text(item.summary) ?? text(item.text);
  const unit = text(item.unit);
  const shown = reading ? `${reading}${unit ? ` ${unit}` : ""}` : null;
  const line = label && shown ? `${label}: ${shown}` : shown ?? label;
  if (!line) return null;
  const source = text(item.source);
  return { date: text(item.date) ?? text(item.observed_at) ?? null, value: line, source: source ? humanize(source) : null };
}

const strings = (value: unknown): string[] =>
  Array.isArray(value) ? value.map(text).filter((s): s is string => s !== null) : [];

function readOrgan(value: unknown): Organ | null {
  if (!value || typeof value !== "object") return null;
  const raw = value as Record<string, unknown>;
  const id = text(raw.organ_id) ?? text(raw.id);
  if (!id) return null;
  const name = text(raw.name) ?? humanize(id);
  const evidence = Array.isArray(raw.evidence) ? raw.evidence.map(readEvidence).filter((e): e is OrganEvidence => e !== null) : [];
  const said = typeof raw.status === "string" ? raw.status.trim().toLowerCase() : "";
  let status: OrganStatus = STATUSES.has(said) ? (said as OrganStatus) : "no_data";
  // "Steady" needs something to be steady about. With no evidence it is a gap, not a reassurance.
  if (status === "steady" && evidence.length === 0) status = "no_data";
  const confidence = raw.confidence && typeof raw.confidence === "object" ? (raw.confidence as Record<string, unknown>) : null;
  const prompt = raw.chat_prompt && typeof raw.chat_prompt === "object" ? (raw.chat_prompt as Record<string, unknown>).text : raw.chat_prompt;
  const safety = text(raw.safety && typeof raw.safety === "object" ? (raw.safety as Record<string, unknown>).message : raw.safety);
  // The map is never calmer than its own safety message.
  if (safety) status = "talk_to_doctor";
  const explanation = text(raw.explanation) ?? text(raw.summary);
  return {
    id,
    name,
    status,
    explanation,
    reasons: strings(raw.reasons).filter((r) => r !== explanation),
    notes: strings(raw.notes),
    updatedAt: text(raw.updated_at),
    evidence,
    evidenceCount: Math.max(evidence.length, typeof raw.evidence_count === "number" && Number.isFinite(raw.evidence_count) ? Math.floor(raw.evidence_count) : 0),
    confidence: status === "no_data" ? null : readConfidence(confidence ? confidence.level : raw.confidence),
    confidenceReason: confidence ? text(confidence.reason) : null,
    missing: strings(raw.missing),
    nextStep: text(raw.next_step),
    chatPrompt: text(prompt) ?? `What do my recent entries say about my ${name.toLowerCase()}?`,
    safety,
  };
}

/** Reads `[...]` or `{ organs: [...] }`. Entries without an id are dropped, repeated ids keep the first. */
export function readOrganMap(data: unknown): Organ[] {
  const list = Array.isArray(data)
    ? data
    : data && typeof data === "object" && Array.isArray((data as { organs?: unknown }).organs)
      ? (data as { organs: unknown[] }).organs
      : [];
  const seen = new Set<string>();
  const organs: Organ[] = [];
  for (const item of list) {
    const organ = readOrgan(item);
    if (!organ || seen.has(organ.id)) continue;
    seen.add(organ.id);
    organs.push(organ);
  }
  return organs;
}

/** Sources the server could not read this time (e.g. "labs"): the map may be missing their entries. */
export function readUnavailable(data: unknown): string[] {
  return data && typeof data === "object" ? strings((data as { unavailable?: unknown }).unavailable) : [];
}

/** The organ the page opens on: the most serious one with data, else none (the panel then invites a choice). */
export function defaultOrganId(organs: readonly Organ[]): string | null {
  for (const status of STATUS_ORDER) {
    if (status === "no_data") break;
    const hit = organs.find((o) => o.status === status);
    if (hit) return hit.id;
  }
  return null;
}

export function countByStatus(organs: readonly Organ[]): Record<OrganStatus, number> {
  const counts: Record<OrganStatus, number> = { talk_to_doctor: 0, worth_watching: 0, steady: 0, no_data: 0 };
  for (const organ of organs) counts[organ.status] += 1;
  return counts;
}

export interface DeviceHints {
  webgl: boolean;
  reducedMotion: boolean;
  saveData?: boolean;
  hardwareConcurrency?: number | null;
}

/** 3D only where it will run smoothly and is wanted; everyone else gets the flat body with the same interaction. */
export function prefer3D(hints: DeviceHints): boolean {
  if (!hints.webgl || hints.reducedMotion || hints.saveData) return false;
  return !(typeof hints.hardwareConcurrency === "number" && hints.hardwareConcurrency <= 2);
}

/** Browser probe for prefer3D. Safe to call only in the browser. */
export function readDeviceHints(): DeviceHints {
  const nav = navigator as Navigator & { connection?: { saveData?: boolean } };
  let webgl = false;
  try {
    webgl = Boolean(document.createElement("canvas").getContext("webgl2"));
  } catch {
    webgl = false;
  }
  return {
    webgl,
    reducedMotion: window.matchMedia("(prefers-reduced-motion: reduce)").matches,
    saveData: nav.connection?.saveData === true,
    hardwareConcurrency: nav.hardwareConcurrency,
  };
}

// The server writes "14 Sep" in its sentences; en-GB would say "14 Sept" here, so the months are spelled out once.
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "12 Oct" (or "12 Oct 2025" for another year). Unreadable dates come back as null rather than "Invalid Date". */
export function formatEvidenceDate(iso: string | null, now: Date = new Date()): string | null {
  if (!iso) return null;
  const d = parseWhen(iso); // calendar days stay on their day in every time zone
  if (Number.isNaN(d.getTime())) return null;
  const day = `${d.getDate()} ${MONTHS[d.getMonth()]}`;
  return d.getFullYear() !== now.getFullYear() ? `${day} ${d.getFullYear()}` : day;
}
