// What the first-run setup decided for this person, and the small pure rules that apply it. No React here, so it is all tested
// (experience.test.ts). The server builds the profile (backend/onboarding.py build_experience); this only reads it, tolerantly.

export type Anatomy = "female" | "male" | "neutral";

export interface Experience {
  version: string;
  bodyMap: { visible: boolean; anatomy: Anatomy; reproductive: "uterus_ovaries" | "none" | "by_use" };
  hiddenSections: string[];
  cycleVisible: boolean;
  companion: { name: string | null; tone: string; replyLength: string; language: string };
  focus: string[];
  care: { id: string; title: string; why: string; source: string }[];
  trackers: { tracker: string; why: string }[];
  hideNumbers: boolean;
}

const rec = (v: unknown): Record<string, unknown> | null => (v !== null && typeof v === "object" && !Array.isArray(v) ? (v as Record<string, unknown>) : null);
const strings = (v: unknown): string[] => (Array.isArray(v) ? v.filter((x): x is string => typeof x === "string") : []);
const str = (v: unknown, fallback = ""): string => (typeof v === "string" ? v : fallback);

/** Reads the server's profile. Anything missing falls back to the general experience: nothing hidden, the general body. */
export function readExperience(raw: unknown): Experience | null {
  const e = rec(raw);
  if (!e) return null;
  const map = rec(e.body_map);
  const anatomy = rec(e.anatomy);
  const sections = rec(e.sections);
  const cycle = rec(e.cycle);
  const companion = rec(e.companion);
  const fitness = rec(e.fitness);
  const base = str(map?.anatomy ?? anatomy?.base);
  const reproductive = str(map?.reproductive ?? anatomy?.reproductive);
  return {
    version: str(e.version),
    bodyMap: {
      visible: map?.visible !== false,
      anatomy: base === "female" || base === "male" ? base : "neutral",
      reproductive: reproductive === "uterus_ovaries" || reproductive === "none" ? reproductive : "by_use",
    },
    hiddenSections: strings(sections?.hidden),
    cycleVisible: cycle?.visible !== false,
    companion: { name: typeof companion?.name === "string" ? companion.name : null, tone: str(companion?.tone, "gentle_warm"), replyLength: str(companion?.reply_length, "short"), language: str(companion?.language, "english") },
    focus: strings(e.body_map_focus),
    care: (Array.isArray(e.care_checklist) ? e.care_checklist : []).flatMap((c) => {
      const r = rec(c);
      return r && typeof r.id === "string" && typeof r.title === "string" ? [{ id: r.id, title: r.title, why: str(r.why), source: str(r.source) }] : [];
    }),
    trackers: (Array.isArray(e.trackers_suggested) ? e.trackers_suggested : []).flatMap((t) => {
      const r = rec(t);
      return r && typeof r.tracker === "string" ? [{ tracker: r.tracker, why: str(r.why) }] : [];
    }),
    hideNumbers: fitness?.hide_numbers === true,
  };
}

type Tab = { label: string; href: string };
type Sec = { id: string; tabs?: readonly Tab[] };

/**
 * The menu for this person: a section they should not see (Cycle for a male body) is left out, and the Body map tab is left out
 * when their body map is switched off. With no experience yet, nothing is hidden.
 */
export function filterSections<S extends Sec>(sections: readonly S[], experience: Experience | null): S[] {
  if (!experience) return [...sections];
  return sections
    .filter((s) => !experience.hiddenSections.includes(s.id))
    .map((s) => (s.tabs ? { ...s, tabs: s.tabs.filter((t) => experience.bodyMap.visible || t.href !== "/body") } : s));
}

/** Paths that never wait for or are redirected by the setup gate. */
const GATE_EXEMPT = ["/onboarding", "/login", "/callback", "/password", "/terms", "/privacy", "/legal", "/android", "/partner", "/cycle/partner", "/not-found"];

export function gateApplies(pathname: string): boolean {
  if (pathname === "/" || pathname === "") return false;
  return !GATE_EXEMPT.some((p) => pathname === p || pathname.startsWith(`${p}/`));
}

/** Pages that have no signed-in app behind them (landing, sign-in, legal, share links) get no providers. */
export function needsProviders(pathname: string): boolean {
  if (pathname === "/" || pathname === "") return false;
  return !["/login", "/callback", "/password", "/terms", "/privacy", "/android", "/partner/", "/cycle/partner/"].some(
    (p) => pathname === p || pathname.startsWith(p.endsWith("/") ? p : `${p}/`),
  );
}

export interface SetupState {
  complete: boolean;
  under18: boolean;
}

/** What to do for a signed-in person on `pathname`: wait for the answer, send them to setup, or let them through. */
export function gateDecision(pathname: string, state: SetupState | "loading" | "error"): "wait" | "setup" | "pass" {
  if (!gateApplies(pathname)) return "pass";
  if (state === "error") return "pass";          // never lock someone out because the check failed
  if (state === "loading") return "wait";
  return state.complete ? "pass" : "setup";
}

export function readSetupState(raw: unknown): SetupState | null {
  const r = rec(raw);
  if (!r || typeof r.complete !== "boolean") return null;
  return { complete: r.complete, under18: r.under_18 === true };
}
