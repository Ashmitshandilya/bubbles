// Pure helpers for the Orbit screens (orbit.test.ts). The server decides everything; this only reads its answers tolerantly and holds the fixed words.



export const STATUS_OPTIONS: readonly { id: string; label: string }[] = [
  { id: "single", label: "Single" },
  { id: "dating", label: "Dating someone" },
  { id: "situationship", label: "It's undefined" },
  { id: "committed", label: "In a relationship" },
  { id: "married", label: "Married" },
  { id: "separated", label: "Separated" },
  { id: "complicated", label: "It's complicated" },
  { id: "prefer_not", label: "Prefer not to say" },
];

export const CARED_OPTIONS: readonly { id: string; label: string }[] = [
  { id: "words", label: "Kind words" },
  { id: "time", label: "Time together" },
  { id: "help", label: "Help with things" },
  { id: "touch", label: "A hug or touch" },
  { id: "gifts", label: "Thoughtful gifts" },
];

export const CONFLICT_OPTIONS: readonly { id: string; label: string }[] = [
  { id: "pursues", label: "I want to talk it through right away" },
  { id: "withdraws", label: "I need some space first" },
  { id: "balanced", label: "Somewhere in between" },
];

export type Rec = Record<string, unknown>;
const rec = (v: unknown): Rec | null => (v !== null && typeof v === "object" && !Array.isArray(v) ? (v as Rec) : null);
const str = (v: unknown, fallback = ""): string => (typeof v === "string" ? v : fallback);
const strs = (v: unknown): string[] => (Array.isArray(v) ? v.filter((x): x is string => typeof x === "string") : []);

export interface OrbitProfile {
  status: string | null;
  partnerWord: string;
  caredForBy: string[];
  conflictStyle: string | null;
}

export interface OrbitHome {
  profile: OrbitProfile;
  paired: boolean;
  partnerName: string | null;
  question: { text: string; answered: boolean; state: string };
  checkin: { week: string; answered: boolean; state: string };
  weather: string | null;
  weatherPaused: boolean;
  sharing: { rituals: boolean; weather: boolean };
}

export function readProfile(raw: unknown): OrbitProfile {
  const p = rec(raw) ?? {};
  return { status: typeof p.status === "string" ? p.status : null, partnerWord: str(p.partner_word), caredForBy: strs(p.cared_for_by), conflictStyle: typeof p.conflict_style === "string" ? p.conflict_style : null };
}

export function readHome(raw: unknown): OrbitHome | null {
  const r = rec(raw);
  if (!r || r.status !== "success") return null;
  const q = rec(r.question) ?? {};
  const c = rec(r.checkin) ?? {};
  const s = rec(r.sharing) ?? {};
  return {
    profile: readProfile(r.profile),
    paired: r.paired === true,
    partnerName: typeof r.partner_name === "string" ? r.partner_name : null,
    question: { text: str(q.text), answered: q.answered === true, state: str(q.state, "solo") },
    checkin: { week: str(c.week), answered: c.answered === true, state: str(c.state, "solo") },
    weather: typeof r.weather === "string" && r.weather ? r.weather : null,
    weatherPaused: r.weather_paused === true,
    sharing: { rituals: s.rituals === true, weather: s.weather === true },
  };
}

/** The line Bubbles speaks under the title: the partner weather if there is one, else a warm line that fits where the person is. */
export function ledeFor(home: OrbitHome | null): string {
  if (!home) return "A quiet place for the people closest to you.";
  if (home.weather) return home.weather;
  if (home.profile.status === null) return "Tell me a little about where you are, and I'll fit Orbit to you.";
  if (home.paired && home.question.state === "revealed") return "You both answered today's question. Worth a look together.";
  if (home.paired && !home.question.answered) return "Today's question is waiting for you both.";
  if (home.profile.status === "single") return "Orbit is for everyone you hold close, not only a partner.";
  return "A small moment of attention goes a long way. What would help today?";
}

export interface SafetyAnswer {
  kind: "emergency" | "safe_harbor";
  message: string;
  resources: { name: string; number: string; note: string }[];
}

/** The server answered a free-text input with a fixed safety message instead of doing the thing: show it, do not treat it as saved. */
export function readSafety(raw: unknown): SafetyAnswer | null {
  const r = rec(raw);
  if (!r || r.status !== "safety") return null;
  const harbor = rec(r.harbor);
  const resources = Array.isArray(harbor?.resources) ? (harbor!.resources as unknown[]).flatMap((x) => {
    const o = rec(x);
    return o && typeof o.name === "string" ? [{ name: o.name, number: str(o.number), note: str(o.note) }] : [];
  }) : [];
  return { kind: r.kind === "emergency" ? "emergency" : "safe_harbor", message: str(r.message), resources };
}

export interface ConsentNeeded {
  message: string;
}

/** A 403 body asking for the yes to outside-AI processing. */
export function readConsentNeeded(status: number, raw: unknown): ConsentNeeded | null {
  if (status !== 403) return null;
  const detail = rec(rec(raw)?.detail);
  return detail && detail.code === "consent_required" ? { message: str(detail.message, "Turn on outside AI help to use this.") } : null;
}

export interface Reply {
  tone: string;
  text: string;
  why: string;
}

export interface ReplyHelp {
  feelings: string[];
  replies: Reply[];
  declined: string | null;
  source: string;
}

export function readReplies(raw: unknown): ReplyHelp | null {
  const r = rec(raw);
  if (!r) return null;
  if (r.status === "declined") return { feelings: [], replies: [], declined: str(r.message), source: "none" };
  if (r.status !== "success" || !Array.isArray(r.replies)) return null;
  return {
    feelings: strs(r.feelings),
    replies: (r.replies as unknown[]).flatMap((x) => {
      const o = rec(x);
      return o && typeof o.text === "string" ? [{ tone: str(o.tone), text: o.text, why: str(o.why) }] : [];
    }),
    declined: null,
    source: str(r.source, "template"),
  };
}

export const TONE_LABEL: Record<string, string> = { gentle: "Gentle", light: "Light", clear: "Clear" };

export interface DailyQuestion {
  text: string;
  answered: boolean;
  myAnswer: string | null;
  partnerAnswer: string | null;
  state: string;
  paired: boolean;
}

export function readQuestion(raw: unknown): DailyQuestion | null {
  const r = rec(raw);
  if (!r || r.status !== "success") return null;
  return { text: str(r.text), answered: r.answered === true, myAnswer: typeof r.my_answer === "string" ? r.my_answer : null, partnerAnswer: typeof r.partner_answer === "string" ? r.partner_answer : null, state: str(r.state, "solo"), paired: r.paired === true };
}

export interface Checkin {
  prompts: Record<string, string>;
  answered: boolean;
  mine: Record<string, string>;
  partner: Record<string, string> | null;
  state: string;
  paired: boolean;
}

const answersOf = (v: unknown): Record<string, string> => Object.fromEntries(Object.entries(rec(v) ?? {}).filter((e): e is [string, string] => typeof e[1] === "string"));

export function readCheckin(raw: unknown): Checkin | null {
  const r = rec(raw);
  if (!r || r.status !== "success") return null;
  return { prompts: answersOf(r.prompts), answered: r.answered === true, mine: answersOf(r.my_answers), partner: r.partner_answers ? answersOf(r.partner_answers) : null, state: str(r.state, "solo"), paired: r.paired === true };
}

export interface LoveMap {
  known: { id: string; text: string }[];
  ask: { id: string; text: string }[];
}

export function readLoveMap(raw: unknown): LoveMap | null {
  const r = rec(raw);
  if (!r || r.status !== "success") return null;
  const items = (v: unknown) => (Array.isArray(v) ? v.flatMap((x) => { const o = rec(x); return o && typeof o.id === "string" && typeof o.text === "string" ? [{ id: o.id, text: o.text }] : []; }) : []);
  return { known: items(r.known), ask: items(r.ask) };
}

/** A heated draft: the 20-minute pause, then the softer version. */
export function readCooldown(raw: unknown): { heated: boolean; rewrite: string | null; pauseMinutes: number } | null {
  const r = rec(raw);
  if (!r || r.status !== "success") return null;
  return { heated: r.heated === true, rewrite: typeof r.rewrite === "string" ? r.rewrite : null, pauseMinutes: typeof r.pause_minutes === "number" ? r.pause_minutes : 0 };
}

export function readDraft(raw: unknown): string | null {
  const r = rec(raw);
  return r && r.status === "success" && typeof r.draft === "string" ? r.draft : null;
}

export function readHarbor(raw: unknown): { title: string; resources: { name: string; number: string; note: string }[]; note: string } | null {
  const r = rec(raw);
  if (!r || r.status !== "success" || !Array.isArray(r.resources)) return null;
  return {
    title: str(r.title, "Feeling unsafe at home?"),
    note: str(r.note),
    resources: (r.resources as unknown[]).flatMap((x) => { const o = rec(x); return o && typeof o.name === "string" ? [{ name: o.name, number: str(o.number), note: str(o.note) }] : []; }),
  };
}

/** A number that is safe to put in a tel: link (digits, an optional leading +), or "". */
export function dial(raw: string): string {
  const compact = raw.replace(/[\s().-]/g, "");
  return /^\+?\d{2,6}$/.test(compact) ? compact : "";
}

// ---- the safety plan: fixed items, kept only in this browser unless the person chooses otherwise ----------------------------------------------

export const SAFETY_PLAN_ITEMS: readonly { id: string; text: string }[] = [
  { id: "numbers", text: "Save the numbers you may need under a neutral name in your phone." },
  { id: "person", text: "Choose one person you trust who knows you may need help." },
  { id: "word", text: "Agree a code word with them that means please call for help." },
  { id: "bag", text: "Keep a small bag ready: ID, some money, medicines, a charger, spare keys." },
  { id: "documents", text: "Keep copies of important documents somewhere safe outside your home." },
  { id: "place", text: "Know the nearest safe place you can go, and how to get there at night." },
  { id: "phone", text: "Keep your phone charged and your locked screen free of anything private." },
  { id: "exit", text: "Notice which room in your home has an exit and no weapons or tight spaces." },
];

const PLAN_KEY = "bubbles.safety-plan.v1";

export function loadPlan(storage: Pick<Storage, "getItem"> | undefined): string[] {
  try {
    const raw = storage?.getItem(PLAN_KEY);
    const ids = raw ? (JSON.parse(raw) as unknown) : [];
    return Array.isArray(ids) ? ids.filter((x): x is string => typeof x === "string" && SAFETY_PLAN_ITEMS.some((i) => i.id === x)) : [];
  } catch {
    return [];
  }
}

export function savePlan(storage: Pick<Storage, "setItem"> | undefined, ids: string[]): void {
  try {
    storage?.setItem(PLAN_KEY, JSON.stringify(ids.filter((x) => SAFETY_PLAN_ITEMS.some((i) => i.id === x))));
  } catch {
    // private windows and blocked storage: the list simply is not kept
  }
}

export function clearPlan(storage: Pick<Storage, "removeItem"> | undefined): void {
  try {
    storage?.removeItem(PLAN_KEY);
  } catch {
    // nothing to clear
  }
}
