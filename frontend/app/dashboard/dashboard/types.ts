// Response shapes for the endpoints the Today screen reads.
// Source of truth: backend/schemas.py response models and backend/health_logs.py.

export interface ProfileData {
  id?: string;
  display_name?: string;
  created_at?: string;
}

/** GET /health/summary (also used by /health). */
export interface HealthSummary {
  categories_with_data?: number;
  total_entries?: number;
  days_tracked?: number;
  last_update?: string;
}

export type SignalSlug = "cycle" | "sleep" | "mood" | "activity" | "hydration" | "nutrition";

/** One row of GET /health/<slug>; only the fields of that tracker are present. */
export interface TrackerEntry {
  id: string;
  date: string;
  duration?: number; // sleep: hours, activity: minutes
  quality?: number;
  mood?: number; // 1-10
  volume?: number; // ml
  type?: string;
  phase?: string;
  description?: string;
  meal_type?: string;
  calories?: number;
  doctor_name?: string;
  specialty?: string;
  reason?: string;
  /** visits: the form's "Next visit" date arrives here as "Next visit: YYYY-MM-DD". */
  recommendations?: string;
  notes?: string;
}

/** `summary` returned by GET /health/cycle. */
export interface CycleSummary {
  period_start_count: number;
  last_period?: string;
  average_cycle_length?: number;
  next_predicted?: string;
}

export interface TrackerResponse {
  entries: TrackerEntry[];
  summary?: CycleSummary;
}

/** GET /insights/weekly -> { insights: WeeklyInsights } */
export interface InsightItem {
  /** Stable id (rec:..., co:...) that GET /insights/{id} resolves; absent on an older server. */
  id?: string | null;
  /** The server's one confidence word ("low" | "medium" | "high"), the same one the Patterns page shows. */
  confidence_label?: string | null;
  title: string;
  description: string;
  category: string;
  confidence: number;
  supporting_events: string[];
  actionable: boolean;
  suggested_action?: string | null;
}

export interface WeeklyInsights {
  insights: InsightItem[];
  disclaimer: string;
  /** Entries Bubbles recorded in the last 7 days; `sufficient_for_pattern_detection` is true from 3 entries. */
  data_quality?: { event_count?: number; sufficient_for_pattern_detection?: boolean } | null;
  /** Event types recorded in the same window, most frequent first. */
  trend?: { signals?: Array<{ event_type: string; count: number }> } | null;
}

export interface CorrelationItem {
  id?: string | null;
  confidence_label?: string | null;
  kind: string;
  pair_count: number;
  strength: number;
  interpretation: string;
}

export interface BriefAction {
  id: string;
  title: string;
  detail: string;
  target: string;
  priority: string;
}

/** POST /intelligence/brief -> { brief: IntelligenceBrief } */
export interface IntelligenceBrief {
  state?: {
    status?: string;
    correlations?: { items: CorrelationItem[] };
    /** This window against the person's usual, per metric (sleep_hours, water_ml, ...). */
    deviations?: Record<string, { current?: number | null; baseline?: number | null; delta?: number | null; percent?: number | null } | null>;
  } | null;
  companion?: { safety_note?: string | null; disclaimer?: string | null } | null;
  actions?: BriefAction[] | null;
}

export interface LivingMapSignal {
  kind: string;
  label: string;
  direction?: string | null;
  confidence: string;
  evidence: string;
}

/** GET /intelligence/living-map -> { map: LivingMapData } */
export interface LivingMapData {
  status: string;
  observed_signal_count: number;
  baseline_change_count: number;
  data_gap_count: number;
  signals: LivingMapSignal[];
  data_gaps: string[];
  coverage: string;
  interpretation_policy: string;
}

/** Per-request state: every view renders loading, error and ready explicitly. */
export type Loadable<T> = { status: "loading" } | { status: "error" } | { status: "ready"; data: T };
