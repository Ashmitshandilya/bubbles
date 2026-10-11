// Pure derivations for the Today screen. Everything here is computed from the
// user's own tracker entries; nothing is invented. Missing data stays missing.
import { readEntries } from "../../lib/api-adapters";
import { calendarDay } from "../../lib/dates";
import type { BriefAction, CorrelationItem, InsightItem, SignalSlug, TrackerEntry, TrackerResponse } from "./types";

export const WEEK_DAYS = 7;
/** Trackers are read for 4 weeks: this week, plus the previous 3 weeks as "your usual". */
export const WINDOW_DAYS = 28;

type DailySlug = Exclude<SignalSlug, "cycle">;

const pad = (n: number) => String(n).padStart(2, "0");
const round1 = (n: number) => Math.round(n * 10) / 10;
const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? "" : "s"}`;

/** Local calendar day (YYYY-MM-DD). Calendar days (date-only, or the UTC midnight a day-only pick comes back as) are kept as written. */
export function dayKey(value: string | Date): string {
  if (typeof value === "string") {
    const day = calendarDay(value);
    if (day) return day;
  }
  const d = typeof value === "string" ? new Date(value) : value;
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function dayNumber(key: string): number {
  const [y, m, d] = key.split("-").map(Number);
  return Date.UTC(y, m - 1, d) / 86_400_000;
}

/** Whole calendar days from `value` until `now`: 0 = today, negative = future, NaN = unparseable. */
export function daysAgo(value: string, now: Date): number {
  return dayNumber(dayKey(now)) - dayNumber(dayKey(value));
}

export function toLocalDate(value: string): Date {
  const [y, m, d] = dayKey(value).split("-").map(Number);
  return new Date(y, m - 1, d);
}

export function formatDay(value: string): string {
  return toLocalDate(value).toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

/** Plain words for an internal metric id ("sleep_hours" is "sleep", "water_ml" is "water intake"), same table as backend/metric_names.py. */
const METRIC_PLAIN: Record<string, string> = {
  sleep_hours: "sleep", sleep_duration: "sleep", sleep_quality: "sleep quality", water_ml: "water intake", hydration_ml: "water intake",
  water: "water intake", hydration: "water intake", mood_score: "mood", weight_kg: "weight", heart_rate: "heart rate",
  resting_hr: "resting heart rate", activity_minutes: "activity", calories: "food intake", calories_kcal: "food intake",
};
export function plainMetric(metric: string): string {
  const key = metric.trim().toLowerCase();
  return METRIC_PLAIN[key] ?? (key.replace(/_(ml|hours?|minutes?|mins?|kg|lbs?|bpm|score|count|level)$/, "").replaceAll("_", " ") || "this");
}

export function greeting(now: Date): string {
  const h = now.getHours();
  return h < 5 ? "Hi" : h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
}

/** GET /health/<slug> -> well-formed entries (a row without a date would otherwise throw while rendering Today). */
export function readTracker(raw: unknown): TrackerResponse {
  const body = (raw && typeof raw === "object" ? raw : {}) as { entries?: unknown; summary?: TrackerResponse["summary"] };
  return { entries: readEntries<TrackerEntry>(body.entries), summary: body.summary };
}

// ── Signals ────────────────────────────────────────────────────────────────

const METRICS: Record<DailySlug, { pick: (e: TrackerEntry) => number | undefined; perDay: "sum" | "avg"; week: "avg" | "total"; format: (n: number) => string }> = {
  sleep: { pick: (e) => e.duration, perDay: "sum", week: "avg", format: (n) => `${round1(n)} h` },
  mood: { pick: (e) => e.mood, perDay: "avg", week: "avg", format: (n) => `${round1(n)} / 10` },
  hydration: { pick: (e) => e.volume, perDay: "sum", week: "avg", format: (n) => (n >= 1000 ? `${round1(n / 1000)} L` : `${Math.round(n)} ml`) },
  activity: { pick: (e) => e.duration, perDay: "sum", week: "total", format: (n) => `${Math.round(n)} min` },
  nutrition: { pick: () => 1, perDay: "sum", week: "total", format: (n) => plural(n, "meal") },
};

/** Direction of this week against the user's own previous weeks. Only set when there are enough logged days on both sides. */
export type Trend = "up" | "down" | "steady";

export interface Change {
  direction: "up" | "down";
  percent: number;
  usual: string;
  confidence: "low" | "medium";
  evidence: string[];
}

export interface SignalSummary {
  slug: DailySlug;
  /** Any entry inside the 4-week window. */
  logged: boolean;
  weekDays: number;
  weekCount: number;
  value?: string;
  detail: string;
  /** Last 7 days, oldest first, scaled 0..1 (0 = nothing logged that day). */
  bars: number[];
  lastLogged?: string;
  change?: Change;
  /** up/down = a 15% or larger move, steady = within 15%; undefined = not enough logged days to compare (a gap, not "steady"). */
  trend?: Trend;
}

const average = (xs: number[]) => xs.reduce((a, b) => a + b, 0) / xs.length;

export function summarizeSignal(slug: DailySlug, entries: TrackerEntry[], now: Date): SignalSummary {
  const metric = METRICS[slug];
  const byDay = new Map<number, number[]>();
  let weekCount = 0;
  let lastLogged: string | undefined;
  for (const entry of entries) {
    const ago = daysAgo(entry.date, now);
    const value = metric.pick(entry);
    if (!Number.isFinite(ago) || ago < 0 || ago >= WINDOW_DAYS || typeof value !== "number" || !Number.isFinite(value)) continue;
    byDay.set(ago, [...(byDay.get(ago) ?? []), value]);
    if (ago < WEEK_DAYS) weekCount += 1;
    if (!lastLogged || daysAgo(lastLogged, now) > ago) lastLogged = entry.date;
  }
  const daily = new Map([...byDay].map(([ago, xs]) => [ago, metric.perDay === "sum" ? xs.reduce((a, b) => a + b, 0) : average(xs)]));
  const week = [...daily].filter(([ago]) => ago < WEEK_DAYS).map(([, v]) => v);
  const base = [...daily].filter(([ago]) => ago >= WEEK_DAYS).map(([, v]) => v);

  const raw = Array.from({ length: WEEK_DAYS }, (_, i) => daily.get(WEEK_DAYS - 1 - i) ?? 0);
  const max = Math.max(...raw);
  const bars = raw.map((v) => (max > 0 ? v / max : 0));
  const summary: SignalSummary = { slug, logged: daily.size > 0, weekDays: week.length, weekCount, bars, lastLogged, detail: "" };

  if (!week.length) {
    summary.detail = lastLogged ? `Last logged ${formatDay(lastLogged)} · tap to log` : "Tap to log";
    return summary;
  }

  const current = metric.week === "avg" ? average(week) : week.reduce((a, b) => a + b, 0);
  summary.value = metric.format(current);

  // Compare with the user's own previous 3 weeks only for per-day signals,
  // and only with enough days on both sides to mean something.
  if (metric.week === "avg" && week.length >= 3 && base.length >= 5) {
    const usual = average(base);
    const percent = usual ? Math.round(((current - usual) / usual) * 100) : 0;
    const usualText = metric.format(usual);
    summary.trend = Math.abs(percent) >= 15 ? (percent > 0 ? "up" : "down") : "steady";
    if (Math.abs(percent) >= 15) {
      summary.change = {
        direction: percent > 0 ? "up" : "down",
        percent,
        usual: usualText,
        confidence: week.length >= 5 && base.length >= 10 ? "medium" : "low",
        evidence: [
          `This week: ${summary.value} on average across ${plural(week.length, "logged day")}.`,
          `Previous 3 weeks: ${usualText} on average across ${plural(base.length, "logged day")}.`,
          "Bubbles compares you with your own recent weeks, not with population averages.",
        ],
      };
      summary.detail = `${percent > 0 ? "Above" : "Below"} your usual ${usualText}`;
    } else {
      summary.detail = `Close to your usual ${usualText}`;
    }
    return summary;
  }

  summary.detail =
    slug === "sleep" ? `Average of ${plural(week.length, "logged night")}`
    : slug === "mood" ? `${plural(weekCount, "check-in")} this week`
    : slug === "hydration" ? `A day, logged on ${week.length} of 7 days`
    : slug === "activity" ? `${plural(weekCount, "session")} this week`
    : `Logged on ${week.length} of 7 days`;
  return summary;
}

// ── Cycle ──────────────────────────────────────────────────────────────────

export interface CycleInfo {
  logged: boolean;
  /** Cycle day counted from the last logged period start (day 1). */
  day?: number;
  lastPeriod?: string;
  next?: string;
  daysUntil?: number;
  average?: number;
  starts: number;
  latestPhase?: { phase: string; date: string };
  value?: string;
  detail: string;
}

export function summarizeCycle(response: TrackerResponse, now: Date): CycleInfo {
  const summary = response.summary;
  const starts = summary?.period_start_count ?? 0;
  const info: CycleInfo = { logged: response.entries.length > 0, starts, detail: "Tap to log" };
  if (!info.logged) return info;

  const latest = [...response.entries].sort((a, b) => daysAgo(a.date, now) - daysAgo(b.date, now))[0];
  if (latest?.phase) info.latestPhase = { phase: latest.phase, date: latest.date };

  if (summary?.last_period) {
    info.lastPeriod = summary.last_period;
    info.day = daysAgo(summary.last_period, now) + 1;
    info.value = `Day ${info.day}`;
  } else if (info.latestPhase) {
    info.value = info.latestPhase.phase.charAt(0).toUpperCase() + info.latestPhase.phase.slice(1);
    info.detail = `Phase you logged on ${formatDay(info.latestPhase.date)}`;
  }
  if (summary?.average_cycle_length) info.average = summary.average_cycle_length;

  if (summary?.next_predicted) {
    info.next = summary.next_predicted;
    const until = -daysAgo(summary.next_predicted, now);
    info.daysUntil = until;
    info.detail =
      until > 1 ? `Next period in about ${until} days`
      : until === 1 ? "Next period in about a day"
      : until === 0 ? "Period may start around today"
      : `Period was expected around ${formatDay(summary.next_predicted)}`;
  } else if (info.day) {
    info.detail = "Log one more period start to predict the next";
  }
  return info;
}

// ── "What matters today" ─────────────────────────────────────────────────────

export type PillKind = "high" | "medium" | "low" | "gap";

export interface TodayItem {
  id: string;
  slug: SignalSlug | null;
  label: string;
  pill: { text: string; kind: PillKind };
  headline: string;
  body: string;
  /** Plain-language reasons shown under "Why does Bubbles think this?". */
  evidence?: string[];
  /** When set, "Why does Bubbles think this?" links here instead of expanding. */
  whyHref?: string;
  primary: { label: string; href: string } | "add-water";
  secondary?: { label: string; href: string };
  /** Set for "this week vs your usual" cards; absent when there is nothing to compare. */
  trend?: Trend;
}

/** `log` opens the tracker with its log sheet ready (`?log=1`, see useOpenFromHub in components/tracking/kit.tsx). The Cycle page has no such flag. */
export const SIGNAL_META: Record<SignalSlug, { label: string; href: string; log: string; noun: string }> = {
  cycle: { label: "Cycle", href: "/cycle", log: "/cycle", noun: "period" },
  sleep: { label: "Sleep", href: "/sleep", log: "/sleep?log=1", noun: "sleep" },
  mood: { label: "Mood", href: "/mood", log: "/mood?log=1", noun: "mood" },
  activity: { label: "Activity", href: "/activity", log: "/activity?log=1", noun: "movement" },
  hydration: { label: "Hydration", href: "/hydration", log: "/hydration?log=1", noun: "water" },
  nutrition: { label: "Nutrition", href: "/nutrition", log: "/nutrition?log=1", noun: "meals" },
};

const CHANGE_HEADLINE: Record<"sleep" | "mood" | "hydration", Record<"up" | "down", string>> = {
  sleep: { up: "You've been sleeping longer than usual this week.", down: "Your sleep has been shorter than usual this week." },
  mood: { up: "Your mood check-ins are higher than usual this week.", down: "Your mood check-ins are lower than usual this week." },
  hydration: { up: "You're drinking more water than usual this week.", down: "You're drinking less water than usual this week." },
};

/** Metric names used by the chat-derived health state → tracker slug. */
const STATE_METRIC_SLUG: Record<string, SignalSlug> = {
  sleep_hours: "sleep",
  water_ml: "hydration",
  activity_minutes: "activity",
  mood: "mood",
};

const GAP_ORDER: DailySlug[] = ["hydration", "sleep", "mood", "activity", "nutrition"];

export function buildTodayItems(signals: SignalSummary[], cycle: CycleInfo | null, briefActions: BriefAction[]): TodayItem[] {
  const items: TodayItem[] = [];

  if (cycle?.next && cycle.daysUntil !== undefined && cycle.daysUntil <= 3 && cycle.daysUntil >= -7) {
    const intervals = Math.max(cycle.starts - 1, 1);
    const kind: PillKind = intervals >= 4 ? "high" : intervals >= 2 ? "medium" : "low";
    const late = cycle.daysUntil < 0;
    items.push({
      id: "cycle-next",
      slug: "cycle",
      label: "Cycle",
      pill: { text: `${kind[0].toUpperCase()}${kind.slice(1)} confidence · ${plural(intervals, "cycle")}`, kind },
      headline: late
        ? `Your period was expected around ${formatDay(cycle.next)}.`
        : cycle.daysUntil === 0
          ? "Your period may start around today."
          : `Your period may start in about ${plural(cycle.daysUntil, "day")}.`,
      body: late
        ? "Cycles often shift by a few days. Log it when it starts, or talk to Bubbles if something feels off."
        : "Cycles vary, so treat this as a rough guide rather than a date.",
      evidence: [
        ...(cycle.lastPeriod ? [`Your last logged period started on ${formatDay(cycle.lastPeriod)}.`] : []),
        ...(cycle.average ? [`Your logged cycles average ${round1(cycle.average)} days.`] : []),
        "The estimate is your last start plus your average cycle length. It is not a diagnosis.",
      ],
      primary: { label: "Log period", href: "/cycle" },
    });
  }

  const changed = signals
    .filter((s): s is SignalSummary & { change: Change; slug: "sleep" | "mood" | "hydration" } => Boolean(s.change))
    .sort((a, b) => Math.abs(b.change.percent) - Math.abs(a.change.percent));
  for (const s of changed) {
    items.push({
      id: `change-${s.slug}`,
      slug: s.slug,
      label: SIGNAL_META[s.slug].label,
      pill: { text: `${s.change.confidence === "medium" ? "Medium" : "Low"} confidence`, kind: s.change.confidence },
      headline: CHANGE_HEADLINE[s.slug][s.change.direction],
      body: `About ${s.value} compared with your usual ${s.change.usual}. Worth keeping an eye on, not a cause for alarm on its own.`,
      evidence: s.change.evidence,
      trend: s.change.direction,
      primary: { label: `Open ${SIGNAL_META[s.slug].noun} tracker`, href: SIGNAL_META[s.slug].href },
    });
  }

  for (const action of briefActions) {
    if (!action.id.startsWith("review-") || action.priority !== "high") continue;
    const metric = action.id.slice("review-".length);
    const slug = STATE_METRIC_SLUG[metric] ?? null;
    if (slug && items.some((i) => i.slug === slug)) continue;
    const label = plainMetric(metric);
    items.push({
      id: action.id,
      slug,
      label: slug ? SIGNAL_META[slug].label : label.charAt(0).toUpperCase() + label.slice(1),
      pill: { text: "Low confidence · from chat", kind: "low" },
      headline: `Your ${label} has moved compared with your usual.`,
      // The headline already says what moved; the line below says where it comes from and what to do with it (never a repeat of the headline).
      body: "This comes from what you told Bubbles in chat, so treat it as a hint. Ask Bubbles what changed, or look at your own entries first.",
      whyHref: "/insights",
      primary: { label: "Ask Bubbles about it", href: `/companion?ask=${encodeURIComponent(`What changed in my ${label} recently?`)}` },
    });
  }

  let gaps = 0;
  for (const slug of GAP_ORDER) {
    if (items.length >= 3 || gaps >= 2) break;
    const s = signals.find((x) => x.slug === slug);
    if (!s || s.weekDays > 0) continue;
    gaps += 1;
    const meta = SIGNAL_META[slug];
    items.push({
      id: `gap-${slug}`,
      slug,
      label: meta.label,
      pill: { text: "Data gap", kind: "gap" },
      headline: s.lastLogged ? `No ${meta.noun} logged since ${formatDay(s.lastLogged)}.` : `No ${meta.noun} logged in the last 4 weeks.`,
      body: "Bubbles can't tell how you're doing here yet. A quick log keeps your picture complete.",
      evidence: ["Bubbles only uses what you log. Days without a log stay blank instead of counting as fine."],
      primary: slug === "hydration" ? "add-water" : { label: `Log ${meta.noun}`, href: meta.log },
      secondary: slug === "hydration" ? { label: "Log another amount", href: meta.log } : undefined,
    });
  }

  return items.slice(0, 3);
}

// ── Patterns & coming up ───────────────────────────────────────────────────

export interface PatternItem {
  id: string;
  title: string;
  detail?: string;
  pill: { text: string; kind: PillKind };
}

export function confidenceKind(confidence: number): Exclude<PillKind, "gap"> {
  return confidence >= 0.75 ? "high" : confidence >= 0.5 ? "medium" : "low";
}

export function buildPatterns(insights: InsightItem[], correlations: CorrelationItem[]): PatternItem[] {
  const fromInsights = insights
    .filter((i) => i.category !== "data_gap" && i.title)
    .map((i, index): PatternItem => {
      const kind = confidenceKind(i.confidence);
      // No log count here: `supporting_events` is a capped sample of ids (8 of 14), so its length understates the
      // real count, which the description already states.
      return {
        id: `insight-${index}`,
        title: i.title,
        detail: i.description,
        pill: { text: `${kind[0].toUpperCase()}${kind.slice(1)} confidence`, kind },
      };
    });
  const fromCorrelations = correlations.map((c, index): PatternItem => ({
    id: `corr-${index}`,
    title: c.interpretation,
    pill: { text: `Exploratory · seen ${plural(c.pair_count, "time")}`, kind: "low" },
  }));
  return [...fromInsights, ...fromCorrelations].slice(0, 3);
}

const NEXT_VISIT = /next visit:\s*(\d{4}-\d{2}-\d{2})/i;

/**
 * Visits on or after today, soonest first. The visit form's "Next visit" date comes back from the API inside
 * `recommendations` ("Next visit: 2027-01-02"), so a past visit that names a next one also yields an upcoming row.
 */
export function upcomingVisits(entries: TrackerEntry[], now: Date): TrackerEntry[] {
  return entries
    .flatMap((e) => {
      const next = NEXT_VISIT.exec(e.recommendations ?? "")?.[1];
      return next ? [e, { ...e, id: `${e.id}-next`, date: next }] : [e];
    })
    .filter((e) => daysAgo(e.date, now) <= 0)
    .sort((a, b) => daysAgo(b.date, now) - daysAgo(a.date, now))
    .slice(0, 2);
}
