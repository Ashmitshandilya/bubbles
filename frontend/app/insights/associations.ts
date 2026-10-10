// Pure view-model for "Links between what you log" (GET /wellness/associations).
// Shapes: backend/association_insights.py analyze(). Nothing here claims a cause: every line says "may be linked".

export interface AssociationSource {
  title?: string | null;
  source_name?: string | null;
  source_url?: string | null;
  snippet?: string | null;
}

export interface Association {
  id: string;
  status: string;
  strength: "weak" | "moderate" | "strong";
  /** "up" = the two tend to be high on the same days; "down" = one tends to be high when the other is low. */
  direction?: "up" | "down";
  /** [x, y] series ids such as "sleep_hours", "mood". */
  domains?: string[];
  lag_days?: number;
  n_days: number;
  text: string;
  sources?: AssociationSource[];
}

export interface AssociationGap {
  id: string;
  text: string;
  domains?: string[];
  /** Days where both things were logged so far. */
  n_days?: number;
  /** Days where both are needed before the link can be checked. */
  need?: number;
}

export interface AssociationsResponse {
  insights?: Association[];
  gaps?: AssociationGap[];
  /** Days with a value, per series (only series that have any). */
  data_days?: Record<string, number>;
  message?: string;
}

// Same words as TOPIC in backend/association_insights.py.
const TOPIC: Record<string, string> = {
  sleep_hours: "sleep",
  sleep_quality: "sleep ratings",
  mood: "mood",
  activity_minutes: "activity",
  hydration_ml: "drinks",
  symptom_severity: "symptoms",
  calories: "meals",
  resting_hr: "heart rate",
  luteal: "cycle phase",
};

export const topic = (key: string) => TOPIC[key] ?? key.replaceAll("_", " ");

const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? "" : "s"}`;

/** Filled steps of the strength bar (of 3). An unknown word reads as the weakest, never the strongest. */
export function strengthSteps(strength: string): 1 | 2 | 3 {
  return strength === "strong" ? 3 : strength === "moderate" ? 2 : 1;
}

export function directionInfo(direction: string | undefined): { arrow: "up" | "down"; text: string } | null {
  if (direction === "up") return { arrow: "up", text: "Tend to be higher on the same days" };
  if (direction === "down") return { arrow: "down", text: "One tends to be higher when the other is lower" };
  return null;
}

/** A neutral next step: keep logging to see whether the link holds. No advice to change anything, no dosing, no cause. */
export function whatToTry(item: Pick<Association, "domains">): string {
  const [x, y] = item.domains ?? [];
  if (!x || !y) return "Keep logging as you normally do and see whether this link is still there in a few weeks.";
  return `To see whether this holds, keep logging ${topic(x)} and ${topic(y)} on the same days for a few more weeks. It does not mean either one affects the other.`;
}

export interface Progress {
  id: string;
  pair: string;
  have: number;
  need: number;
  remaining: number;
  /** 0..1 */
  fraction: number;
}

/** The pair closest to being checkable, from the gaps the backend already sent. Null when no gap carries counts. */
export function closestGap(gaps: AssociationGap[]): Progress | null {
  let best: Progress | null = null;
  for (const gap of gaps) {
    const [x, y] = gap.domains ?? [];
    const have = gap.n_days;
    const need = gap.need;
    if (!x || !y || typeof have !== "number" || typeof need !== "number" || need <= 0 || !Number.isFinite(have)) continue;
    const progress: Progress = {
      id: gap.id,
      pair: `${topic(x)} and ${topic(y)}`,
      have,
      need,
      remaining: Math.max(need - have, 0),
      fraction: Math.min(Math.max(have / need, 0), 1),
    };
    if (!best || progress.fraction > best.fraction) best = progress;
  }
  return best;
}

/** "You logged sleep on 12 days, mood on 3 days and drinks on 5 days" for the busiest series, or null when nothing is logged. */
export function loggedDaysLine(dataDays: Record<string, number> | undefined, limit = 3): string | null {
  const parts = Object.entries(dataDays ?? {})
    .filter(([, n]) => Number.isFinite(n) && n > 0)
    .sort((a, b) => b[1] - a[1])
    .slice(0, limit)
    .map(([key, n]) => `${topic(key)} on ${plural(n, "day")}`);
  if (!parts.length) return null;
  const list = parts.length > 1 ? `${parts.slice(0, -1).join(", ")} and ${parts[parts.length - 1]}` : parts[0];
  return `In this window you logged ${list}.`;
}

/** Sentence for the empty state. Counts come only from the response; with none, it says what to log, not how long. */
export function emptyProgressLine(progress: Progress | null): string {
  if (!progress) return "A link can only be checked on days when two things were logged together, so log a pair on the same days.";
  if (progress.remaining === 0) return `${progress.pair} are logged together on ${plural(progress.have, "day")}. Bubbles checks again as you keep logging.`;
  return `${progress.pair}: ${progress.have} of ${progress.need} days logged together. About ${plural(progress.remaining, "more day")} of both, then Bubbles can check this link.`;
}

// The server sends "<sentence> (N days logged). <caveats>": show the sentence, keep the caveats one tap away.
export const sentence = (text: string) => text.split(" (")[0];
export const caveats = (text: string) => {
  const i = text.indexOf(". ");
  return i === -1 ? "" : text.slice(i + 2);
};
