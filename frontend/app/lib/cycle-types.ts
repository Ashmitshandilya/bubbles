// Contract for the /cycle/* API (backend/cycle_api.py). One source of truth for the cycle UI; the backend returns exactly
// these shapes. Every date is an ISO calendar day "YYYY-MM-DD" (never an instant). Predictions are ESTIMATES with
// ranges and are not contraception.

export type CycleMode = "track" | "birth_control" | "conceive" | "pregnancy" | "postpartum" | "perimenopause";
export type PhaseId = "menstrual" | "follicular" | "ovulatory" | "luteal";
/** "learning" until 3 cycles are logged; "low" when cycles are irregular or the life stage is hard to predict. */
export type Confidence = "learning" | "low" | "medium" | "high";
export type Flow = "none" | "spotting" | "light" | "medium" | "heavy";
export type Product = "pad" | "tampon" | "cup" | "disc" | "period_underwear" | "liner" | "none";
export type Discharge = "none" | "dry" | "sticky" | "creamy" | "watery" | "egg_white" | "other";
export type Protection = "none" | "condom" | "pill" | "iud" | "withdrawal" | "other";
export type OvulationTest = "negative" | "faint" | "positive" | "peak";
export type PregnancyTest = "negative" | "faint" | "positive";
export type FlagSeverity = "info" | "talk" | "urgent";

export const MODES: ReadonlyArray<{ id: CycleMode; label: string; blurb: string }> = [
  { id: "track", label: "Track my cycle", blurb: "Learn my rhythm and see what is coming." },
  { id: "birth_control", label: "On birth control", blurb: "Hormonal methods change bleeding; ovulation estimates are hidden." },
  { id: "conceive", label: "Trying to conceive", blurb: "Highlights the fertile window and ovulation signs." },
  { id: "pregnancy", label: "Pregnancy", blurb: "Week by week; period predictions pause." },
  { id: "postpartum", label: "After birth", blurb: "Cycles can take a while to settle; predictions are low-confidence." },
  { id: "perimenopause", label: "Perimenopause", blurb: "Cycles often change; ranges are wide and low-confidence." },
];

export const FLOW_LEVELS: Flow[] = ["none", "spotting", "light", "medium", "heavy"];
export const PRODUCTS: Product[] = ["pad", "tampon", "cup", "disc", "period_underwear", "liner", "none"];
export const DISCHARGES: Discharge[] = ["none", "dry", "sticky", "creamy", "watery", "egg_white", "other"];
export const PROTECTIONS: Protection[] = ["none", "condom", "pill", "iud", "withdrawal", "other"];
export const OVULATION_TESTS: OvulationTest[] = ["negative", "faint", "positive", "peak"];
export const PREGNANCY_TESTS: PregnancyTest[] = ["negative", "faint", "positive"];
export const PAIN_TYPES: ReadonlyArray<{ id: string; label: string }> = [
  { id: "cramps", label: "Cramps" }, { id: "lower_back", label: "Lower back" }, { id: "headache", label: "Headache" },
  { id: "migraine", label: "Migraine" }, { id: "breast", label: "Breast" }, { id: "pelvic", label: "Pelvic" },
  { id: "ovulation", label: "Mid-cycle (ovulation)" }, { id: "joint", label: "Joint or muscle" }, { id: "other", label: "Other" },
];

/** Shown wherever a fertile window or ovulation estimate appears. */
export const NOT_CONTRACEPTION =
  "These are estimates from your own logs. They are not birth control and can be wrong, so do not rely on them to prevent pregnancy.";

/* ── Overview ──────────────────────────────────────────── */

export interface PhaseInfo { id: PhaseId; label: string; summary: string; estimated: boolean }
export interface NextPeriod {
  date: string; earliest: string; latest: string; in_days: number;
  status: "upcoming" | "due" | "late"; late_by_days: number | null;
}
export interface OvulationEstimate {
  date: string; earliest: string; latest: string; confirmed: boolean; source: "calendar" | "bbt" | "lh_test"; passed: boolean;
}
export interface FertileWindow {
  start: string; end: string; earliest: string; latest: string; active_today: boolean; passed: boolean;
}
export interface Flag {
  id: string; severity: FlagSeverity; title: string; message: string; detail: string | null;
}
export interface Weather { tone: "bright" | "steady" | "heavier"; label: string; line: string }
export interface Regularity { score: number; label: string }
export interface CycleStats {
  cycles_used: number;
  average_length: number | null;
  sd: number | null;
  shortest: number | null;
  longest: number | null;
  recent_lengths: number[];          // oldest -> newest, at most 12
  period_length_average: number | null;
  regularity: Regularity | null;     // null until 3 cycles
  irregular: boolean;
}
export interface PmsHint {
  from: string; to: string;          // dates of the likely window before the next period
  text: string;                      // "Around day 22-27, based on your last 4 cycles."
  personal: boolean;                 // false = a general window, not learned from this user's logs
}
export interface PregnancyInfo {
  week: number; day: number; trimester: 1 | 2 | 3; due_date: string; days_to_go: number; note: string; next_step: string;
}
export interface PostpartumInfo {
  delivery_date: string; days_since: number; weeks_since: number; lochia_expected: boolean; note: string;
}
export interface Overview {
  status: "success";
  today: string;
  mode: CycleMode;
  mode_label: string;
  has_data: boolean;
  cycle_day: number | null;
  phase: PhaseInfo | null;
  last_period_start: string | null;
  next_period: NextPeriod | null;
  ovulation: OvulationEstimate | null;
  fertile_window: FertileWindow | null;
  fertility_note: string | null;      // why fertility is hidden (birth control), or a mode-specific note
  confidence: Confidence;
  confidence_note: string;
  stats: CycleStats;
  pms: PmsHint | null;
  flags: Flag[];
  urgent: Flag | null;                // first urgent flag, if any: render it first, with no mascot
  weather: Weather | null;
  pregnancy: PregnancyInfo | null;
  postpartum: PostpartumInfo | null;
  today_log: DayLog | null;
  notices: string[];                  // always includes the not-contraception notice
  privacy: { local_only: boolean };
  empty_state: string | null;         // friendly first-run copy when has_data is false
}

/* ── Day log ───────────────────────────────────────────── */

export interface DayLog {
  flow: Flow | null;
  products: Product[];
  soaking_hourly: boolean;            // soaked a pad/tampon every hour for 2+ hours
  pain_level: number | null;          // 0-10
  pain_types: string[];
  energy: number | null;              // 1-5
  sleep_quality: number | null;       // 1-5
  factors: string[];                  // chip ids from /cycle/factors
  custom_factors: string[];           // free text, <= 40 chars, <= 10
  discharge: Discharge | null;
  sex: { had: boolean; protection: Protection | null } | null;
  ovulation_test: OvulationTest | null;
  pregnancy_test: PregnancyTest | null;
  bbt_c: number | null;               // 34.0-40.0 (the UI converts to/from Fahrenheit for display)
  medications: string[];              // <= 10 items, <= 60 chars
  birth_control_taken: boolean | null;
  period_start: boolean;
  period_end: boolean;
  notes: string | null;               // <= 2000 chars
}
export const EMPTY_DAY_LOG: DayLog = {
  flow: null, products: [], soaking_hourly: false, pain_level: null, pain_types: [], energy: null, sleep_quality: null,
  factors: [], custom_factors: [], discharge: null, sex: null, ovulation_test: null, pregnancy_test: null, bbt_c: null,
  medications: [], birth_control_taken: null, period_start: false, period_end: false, notes: null,
};
/** Returned instead of normal chatter when a note contains words the safety engine treats as urgent. No mascot. */
export interface SafetySignal { state: "URGENT" | "EMERGENCY"; level: "AMBER" | "RED"; message: string }
export interface DayResponse {
  status: "success";
  date: string;
  log: DayLog | null;
  cycle_day: number | null;
  phase: PhaseInfo | null;
  flags: Flag[];                      // flags raised by THIS day's entries (empty when `safety` is set)
  safety: SafetySignal | null;
  overview: Overview | null;          // present on PUT and the period start/end POSTs (null when `safety` is set)
  saved?: boolean;
}

/* ── Calendar ──────────────────────────────────────────── */

export interface CalendarDay {
  date: string;
  cycle_day: number | null;
  phase: PhaseId | null;
  /** "logged" = you logged bleeding; "predicted" = the likely days; "possible" = inside the uncertainty range only. */
  period: "logged" | "predicted" | "possible" | null;
  fertile: "predicted" | "possible" | null;
  ovulation: "predicted" | "confirmed" | null;
  period_start: boolean;
  flow: Flow | null;
  has_log: boolean;
  symptom_count: number;
  pain_level: number | null;
  is_today: boolean;
  is_future: boolean;
}
export interface CalendarResponse {
  status: "success";
  month: string | null;               // "YYYY-MM" when requested by month
  year: number | null;                // when requested by year
  mode: CycleMode;
  confidence: Confidence;
  days: CalendarDay[];
}

/* ── Settings ──────────────────────────────────────────── */

export interface CycleSettings {
  mode: CycleMode;
  age_group: "adult" | "teen";
  luteal_days: number | null;         // 10-16 override; null = default 14
  temp_unit: "c" | "f";
  privacy: { local_only: boolean };
  partner_share: { enabled: boolean; created_at: string | null };
  pregnancy: { lmp: string | null; due_date: string | null };
  postpartum: { delivery_date: string | null; breastfeeding: boolean | null };
  mode_history: Array<{ mode: CycleMode; since: string }>;
}
export interface SettingsResponse { status: "success"; settings: CycleSettings; overview?: Overview | null }

/* ── Insights ──────────────────────────────────────────── */

export interface PhaseStat { phase: PhaseId; mean: number | null; n: number; cycles: number }
export interface InsightMetric {
  id: string;                         // energy | mood | pain | sleep_quality | sleep_hours | weight | tracker_mood
  label: string;
  unit: string;
  source: string;                     // human label of where the numbers came from
  ready: boolean;
  needs: string | null;               // what is missing when not ready
  per_phase: PhaseStat[];
  difference: number | null;          // highest phase mean - lowest phase mean
  summary: string | null;             // never causal: "tends to be", "in your logs"
  confidence: "low" | "moderate" | null;
}
export interface SymptomByPhase {
  id: string; label: string; total_days: number;
  per_phase: Array<{ phase: PhaseId; days: number; share: number }>;
  most_common_phase: PhaseId | null;
}
export interface InsightsResponse {
  status: "success";
  ready: boolean;
  cycles_used: number;
  min_cycles: number;
  message: string;
  metrics: InsightMetric[];
  symptoms: SymptomByPhase[];
  notes: string[];
  disclaimer: string;
}

/* ── Report ────────────────────────────────────────────── */

export interface ReportResponse {
  status: "success";
  generated_on: string;
  mode: CycleMode;
  mode_label: string;
  window: { from: string; to: string; months: number };
  summary: {
    cycles_tracked: number; average_length: number | null; sd: number | null; shortest: number | null; longest: number | null;
    period_length_average: number | null; regularity: Regularity | null; last_period_start: string | null;
    next_period_estimate: string | null; confidence: Confidence;
  };
  cycles: Array<{ start: string; length: number | null; period_days: number | null }>;
  symptoms: Array<{ label: string; days: number; share: number }>;
  pain: { logged_days: number; average: number | null; maximum: number | null; days_at_or_above_severe: number };
  flags: Flag[];
  medications: string[];
  questions_for_clinician: string[];
  notes: Array<{ date: string; text: string }> | null;   // only with ?include_notes=true
  disclaimers: string[];
}

/* ── Factors, education, partner ───────────────────────── */

export interface Chip { id: string; label: string; group: string; keywords: string[]; signal: string }
export interface ChipGroup { id: string; label: string; chips: Chip[] }
export interface FactorsResponse { status: "success"; total: number; groups: ChipGroup[]; query: string | null }
export interface Article {
  id: string; title: string; summary: string; body: string[]; tags: string[]; modes: CycleMode[];
  label: string;                      // "General knowledge, not from your data"
  source_class: "EXTERNAL_KNOWLEDGE";
}
export interface EducationResponse { status: "success"; label: string; articles: Article[] }
export interface PartnerViewResponse {
  status: "success";
  enabled: boolean;
  created_at: string | null;
  token?: string;                     // only returned once, on action "create"
  share_path?: string;                // "/cycle/partner/<token>" only on create
  shares: string[];                   // what a partner can see
}
export interface PartnerPublicResponse {
  status: "success";
  label: string;
  next_period: { earliest: string; latest: string } | null;
  phase_hint: string | null;
  notice: string;
}
export interface DeleteResponse { status: "success"; deleted: { days: number; settings: boolean; partner: boolean; tracker_entries: number } }
