// Response shapes for the Whole-Health OS wellness API (backend/wellness_api.py, notifications.py, data_rights.py).
// Only what the UI reads is typed; every optional field is read defensively.

export interface SafetyResponse {
  status: "safety";
  state: string;
  level?: string;
  crisis: boolean;
  message: string;
  saved: false;
  note?: string;
}

/** The deterministic safety engine answered instead of saving (urgent or crisis wording in free text). */
export function isSafety(value: unknown): value is SafetyResponse {
  return !!value && typeof value === "object" && (value as { status?: unknown }).status === "safety" && typeof (value as { message?: unknown }).message === "string";
}

/* ── Sleep ──────────────────────────────────────────────────────────── */

export interface SleepScore {
  value: number;
  label: string;
  /** duration / regularity / quality, each 0-100. A missing part had no data. */
  parts: Record<string, number>;
}

export interface SleepGoal {
  hours: number;
  source: "you" | "age";
  recommended_min: number;
  recommended_max: number;
  age_group: string;
  bedtime?: string;
  wake_time?: string;
}

export interface SleepInsight {
  tag: string;
  label: string;
  with_n: number;
  without_n: number;
  diff_minutes: number;
  confidence: "low" | "moderate";
  text: string;
}

export interface SleepOverview {
  goal: SleepGoal;
  window_days: number;
  nights_logged: number;
  disclaimer: string;
  average_hours: number | null;
  score: SleepScore | null;
  last_night: { date: string; hours: number; quality: number | null; score: number | null } | null;
  regularity: { minutes: number; basis: "times" | "duration"; consistent: boolean } | null;
  debt: { hours: number; nights_logged: number; window_days: number; partial: boolean; message: string } | null;
  streak: { current: number; best: number; message: string };
  weekday: { best: { weekday: string; hours: number }; worst: { weekday: string; hours: number }; message: string } | null;
  naps: { total_minutes: number; days_with_naps: number; window_days: number; note: string };
  insights: SleepInsight[];
  winddown: { bedtime: string; winddown: string; basis: string; message: string };
  series?: { date: string; hours: number; quality: number | null }[];
  data_gaps: string[];
  tags: string[];
}

/* ── Hydration ──────────────────────────────────────────────────────── */

export interface HydrationGoal {
  goal_ml: number | null;
  base_ml: number | null;
  workout_bonus_ml: number;
  fluid_restricted: boolean;
  basis: string;
  message: string;
}

export interface HydrationGarden {
  level: number;
  name: string;
  caption: string;
  goal_days: number;
  total_litres: number;
  next_level: string | null;
  days_to_next: number;
  progress: number;
}

export interface HydrationOverview {
  date: string;
  goal: HydrationGoal;
  raw_ml: number;
  effective_ml: number;
  by_type: Record<string, number>;
  entries: { id?: string; time?: string; ml: number; type: string }[];
  presets: { id: string; ml: number; label: string }[];
  beverage_factors: Record<string, number>;
  percent: number | null;
  remaining_ml: number | null;
  reminders: { enabled: boolean; next: string | null; due_now: string | null; reason: string | null };
  streak: { current: number; best: number; message: string } | null;
  garden: HydrationGarden | null;
  message: string;
  logged?: { ml: number; type: string; hydrating_ml: number };
}

/* ── Medications ────────────────────────────────────────────────────── */

export type MedKind = "regular" | "as_needed" | "taper" | "cycle_pill" | "glp1";

export interface Refill {
  pills_left: number;
  days_left: number | null;
  alert: boolean;
  message: string | null;
}

export interface Schedule {
  id: string;
  name: string;
  dose_label?: string | null;
  kind: MedKind;
  active: boolean;
  times: string[];
  weekdays: number[];
  start_date?: string;
  end_date?: string;
  taper_steps?: { from_date: string; dose_label: string; times?: string[] }[];
  cycle?: { pattern: "21_7" | "28"; pack_start: string };
  pill_count?: number;
  units_per_dose?: number;
  refill_alert_days?: number;
  describe?: string;
  refill?: Refill | null;
}

export interface Interaction {
  rule: string;
  names: string[];
  level: "high" | "moderate" | "timing";
  concern: string;
  message: string;
}

export interface AllergyWarning {
  medicine: string;
  allergen: string;
  message: string;
}

export interface Warnings {
  interactions: Interaction[];
  allergy_warnings: AllergyWarning[];
}

export type DoseStatus = "upcoming" | "due" | "late" | "taken" | "skipped" | "snoozed";

export interface DueItem {
  schedule_id: string;
  name: string;
  dose_label: string | null;
  time: string;
  status: DoseStatus;
  placebo: boolean;
  kind: MedKind;
  window: { start: string; end: string };
  message?: string;
  snoozed_until?: string;
}

export interface MedsToday extends Warnings {
  date: string;
  items: DueItem[];
  as_needed: { schedule_id: string; name: string; dose_label: string | null; taken_today: number }[];
  pill_free: { schedule_id: string; name: string; message: string }[];
  counts: Record<DoseStatus, number>;
  refill_alerts: { schedule_id: string; name: string; message: string | null; pills_left: number; days_left: number | null }[];
  missed_dose_help: string;
  snooze_options: number[];
  skip_reasons: string[];
}

export interface Adherence {
  window_days: number;
  total: { taken: number; skipped: number; not_recorded: number };
  percent: number | null;
  scheduled: number;
  message: string;
}

export interface Glp1Overview {
  detected: boolean;
  note: string;
  nudges: string[];
  recent_logs: { date: string; appetite?: number; nausea?: number; notes?: string }[];
  schedule: {
    schedule_id: string;
    name: string;
    dose_label: string | null;
    next_dose_date: string | null;
    days_until: number | null;
    dose_day_today: boolean;
    reminder: string | null;
    suggested_site: string;
    suggested_site_label: string;
    last_site: string | null;
    site_note: string;
  } | null;
}

export interface Logbook {
  generated_on: string;
  window_days: number;
  medications: {
    name: string;
    dose_label: string | null;
    kind: string;
    schedule: string;
    active: boolean;
    taken: number;
    skipped: number;
    not_recorded: number;
    percent: number | null;
    skip_reasons: Record<string, number>;
    last_taken: string | null;
  }[];
  allergies: string[];
  interaction_flags: Interaction[];
  allergy_warnings: AllergyWarning[];
  adherence: { total: { taken: number; skipped: number; not_recorded: number }; percent: number | null; scheduled: number; message: string };
  glp1_logs: { date: string; appetite?: number; nausea?: number }[];
  text: string;
}

/* ── Mind ───────────────────────────────────────────────────────────── */

export interface MindOverview {
  window_days: number;
  entries: { id?: string; date: string; mood?: number; notes?: string | null; activities: string[] }[];
  average_mood: number | null;
  days_logged: number;
  today: { m: number; n: number } | null;
  faces: { face: number; mood: number; label: string }[];
  activities: string[];
  screen: { due: boolean; last: string | null; every_days: number };
  exercises: { id: string; name: string; kind: string }[];
  note: string;
}

export interface PixelDay {
  date: string;
  mood: number | null;
  level: number | null;
  entries: number;
}

export interface Pixels {
  year: number;
  days: PixelDay[];
  logged_days: number;
  level_counts: Record<string, number>;
  legend: Record<string, string>;
}

export interface ScreenQuestions {
  kind: "phq2" | "gad2";
  intro: string;
  questions: string[];
  options: { value: number; label: string }[];
  note: string;
}

export interface ScreenResult {
  kind: "phq2" | "gad2";
  score: number;
  max_score: number;
  suggest_talking_to_someone: boolean;
  message: string;
}

export interface JournalEntry {
  id: string;
  date: string;
  text: string;
  local_only: boolean;
  created_at?: string;
}

export interface Exercise {
  id: string;
  name: string;
  kind: "breathing" | "grounding";
  minutes: number;
  pattern: { inhale?: number; hold?: number; exhale?: number; hold_empty?: number } | null;
  steps: string[];
}

export interface MindInsight {
  factor: string;
  diff: number;
  with_n: number;
  without_n: number;
  confidence: "low" | "moderate";
  text: string;
}

/* ── Notifications ──────────────────────────────────────────────────── */

export interface AppNotification {
  id: string;
  kind: "water" | "med" | "winddown" | "system";
  title: string;
  body: string;
  created_at: string;
  read: boolean;
}

export interface NotificationList {
  notifications: AppNotification[];
  unread_count: number;
}

export interface NotificationSettings {
  channels: { in_app: boolean; email: boolean; push: boolean };
  quiet_hours: { enabled: boolean; start: string; end: string };
  daily_cap: number;
  types: { water: boolean; med: boolean; winddown: boolean };
  tz_offset_minutes: number;
}

export interface ChannelStatus {
  in_app: { available: boolean };
  email: { available: boolean; note?: string };
  push: { available: boolean; note?: string };
}

export interface NotificationSettingsResponse {
  settings: NotificationSettings;
  channels: ChannelStatus;
}

export interface ExportPayload {
  exported_at: string;
  count: number;
  /** True when the account had more documents than one file holds, so the download is partial. */
  truncated?: boolean;
  kinds: Record<string, number>;
  documents: unknown[];
  note: string;
}

export interface DeleteResult {
  deleted: number;
  analytics_copies_removed?: number;
  note?: string;
}
