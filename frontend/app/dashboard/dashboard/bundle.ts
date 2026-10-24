// Pure reading of GET /today (the one call Today makes) and the bubble row built from it. No React: unit-tested in bundle.test.ts.
// A part the server could not read is null there; here it becomes `undefined`, so the page shows a gap or a retry, never a guess.
import type { BubbleSignal, Domain } from "../../lib/bubbles-layout";
import { readNudges, type Nudge } from "../../lib/nutrients";
import { readTracker, SIGNAL_META, type SignalSummary } from "./today";
import type { IntelligenceBrief, LivingMapData, ProfileData, SignalSlug, TrackerEntry, TrackerResponse, WeeklyInsights } from "./types";

export const TODAY_PATH = "/today?days=14";

export interface TodayLede { kind: string; text: string }

export interface TodayBundle {
  lede?: TodayLede;
  checked?: string;
  trackers: Partial<Record<SignalSlug, TrackerResponse>>;
  visits?: TrackerEntry[];
  brief?: IntelligenceBrief;
  weekly?: WeeklyInsights;
  livingMap?: LivingMapData;
  nudges: Nudge[];
  profile?: ProfileData;
  orbit?: { question?: { text?: string; answered?: boolean } };
}

const object = (value: unknown): Record<string, unknown> | undefined =>
  value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : undefined;

export function readBundle(raw: unknown): TodayBundle {
  const body = object(raw) ?? {};
  const trackers: TodayBundle["trackers"] = {};
  const sent = object(body.trackers) ?? {};
  for (const slug of Object.keys(SIGNAL_META) as SignalSlug[]) if (object(sent[slug])) trackers[slug] = readTracker(sent[slug]);
  const lede = object(body.lede);
  const profile = object(body.profile);
  return {
    lede: typeof lede?.text === "string" && lede.text ? { kind: String(lede.kind ?? "warm"), text: lede.text } : undefined,
    checked: typeof (object(body.learned)?.checked) === "string" ? String(object(body.learned)?.checked) : undefined,
    trackers,
    visits: object(body.visits) ? readTracker(body.visits).entries : undefined,
    brief: object(body.brief) as IntelligenceBrief | undefined,
    weekly: object(body.weekly) as WeeklyInsights | undefined,
    livingMap: object(body.living_map) as LivingMapData | undefined,
    nudges: readNudges(body.nudges),
    profile: (object(profile?.profile) ?? profile) as ProfileData | undefined,
    orbit: object(body.orbit) as TodayBundle["orbit"],
  };
}

const BUBBLES: Array<{ slug: "sleep" | "mood" | "hydration" | "activity"; label: string; domain: Domain }> = [
  { slug: "sleep", label: "Sleep", domain: "sleep" },
  { slug: "mood", label: "Mood", domain: "mood" },
  { slug: "hydration", label: "Water", domain: "food" },
  { slug: "activity", label: "Move", domain: "move" },
];

const TREND = { up: 0.6, down: -0.6, steady: 0 } as const;

/** One bubble per daily signal. Size is how full the week's logging was; nothing logged this week is an empty outline, never a small bubble. */
export function bubbleSignals(signals: SignalSummary[]): BubbleSignal[] {
  return BUBBLES.map(({ slug, label, domain }) => {
    const s = signals.find((x) => x.slug === slug);
    const logged = s?.bars.filter((b) => b > 0) ?? [];
    const amount = s?.value && logged.length ? Math.min(1, Math.max(0.2, logged.reduce((a, b) => a + b, 0) / logged.length)) : null;
    return { id: slug, label, domain, amount, trend: amount !== null && s?.trend ? TREND[s.trend] : null, valueText: amount !== null ? s?.value : undefined };
  });
}
