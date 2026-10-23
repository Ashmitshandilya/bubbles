// Response shapes of backend/fitness_api.py (read from the real routes + backend/tests/test_fitness_api.py).
// Only the fields the UI reads are typed; the server may send more.

export type Review = { reviewed: boolean; status: string; notice: string };

export type Range2 = [number, number];

export interface Targets {
  goal: "lose" | "maintain" | "gain" | string;
  kcal: number;
  floor_kcal: number;
  tdee_kcal: number;
  bmr_kcal: number;
  deficit_kcal: number;
  pace_kg_per_week: number;
  limited_by: string[];
  at_floor: boolean;
  protein_g: number;
  fat_g: number;
  carbs_g: number;
  fibre_g: number;
  water_ml: number;
  steps: number;
  sleep_hours: Range2;
  notes: string[];
  healthy_weight_range_kg?: Range2;
  time_to_goal?: { weeks_low: number; weeks_high: number; gap_kg: number } | null;
  target_weight_kg?: number | null;
  current_weight_kg: number;
  bmi?: { bmi: number; who_band: string; note: string };
}

export interface Eaten {
  kcal: number;
  kcal_low: number;
  kcal_high: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  fibre_g: number;
}

export interface Budget {
  budget_kcal: number;
  eaten_kcal: number;
  remaining_kcal: number;
  exercise_credit_kcal: number;
  over: boolean;
  label?: string;
}

export interface Summary {
  date: string;
  targets: Targets | null;
  message: string | null;
  eaten: Eaten;
  entries: number;
  workout_kcal: number;
  transform: { status: string; target_weight_kg: number } | null;
  has_diet_plan: boolean;
  has_workout_plan: boolean;
  /** false when nothing has been logged today: show "not logged", never a 0 that reads as "ate nothing" */
  intake_logged?: boolean;
  /** How ready the person looks to train today, in words with the reasons. `level` is null when nothing recent was logged. */
  readiness?: { level: "go" | "moderate" | "recovery" | null; label: string; reasons: string[] };
  review: Review;
  latest_weight_kg: number | null;
  budget?: Budget;
}

export interface BodyProfile {
  birth_date?: string;
  height_cm?: number;
  weight_kg?: number;
  target_weight_kg?: number;
  formula_basis?: "male" | "female" | "average";
  activity_level?: string;
  units?: "metric" | "imperial";
  diet_style?: string;
  cuisines?: string[];
  likes?: string[];
  dislikes?: string[];
  equipment?: string[];
  injuries?: string[];
  pregnant?: boolean;
  breastfeeding?: boolean;
  trying_to_conceive?: boolean;
  menstruating?: boolean;
  clinician_clearance?: { cleared: boolean; date: string; areas?: string[] };
  [key: string]: unknown;
}

export interface BodyResponse {
  profile: BodyProfile;
  known: { conditions: string[]; medications: string[]; allergies: string[]; latest_weight_kg: number | null };
  age: number | null;
  missing: string[];
  review: Review;
  scoff_questions: string[];
  parq_questions: { key: string; text: string; blocking: boolean }[];
}

export interface FoodItem {
  text?: string;
  food: string;
  category?: string;
  quantity: number;
  unit: string;
  grams: number;
  kcal: number;
  kcal_low: number;
  kcal_high: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  fibre_g: number;
  micros?: Record<string, number>;
  match?: string;
}

export interface Parsed {
  items: FoodItem[];
  totals: Eaten;
  micros?: Record<string, number>;
  unrecognised: string[];
  notes: string[];
  warnings: string[];
  support?: string;
  approximate?: boolean;
}

export interface FoodEntry {
  id: string;
  ts: string;
  meal: string | null;
  text: string;
  items: FoodItem[];
  totals: Eaten;
  unrecognised: string[];
}

export interface FoodLog {
  date: string;
  entries: FoodEntry[];
  totals: Eaten;
  budget: Budget | null;
  targets: Targets | null;
}

export interface FoodCard {
  name: string;
  category: string;
  serving: string;
  unit: string;
  serving_g: number;
  kcal: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  fibre_g: number;
  diet: string;
}

export interface PlanMeal {
  template_id: string;
  name: string;
  slot: string;
  label: string;
  target_kcal: number;
  items: FoodItem[];
  totals: Eaten;
  tags: string[];
}

export interface PlanDay {
  day: number;
  meals: PlanMeal[];
  totals: Eaten;
  micros?: Record<string, number>;
  target_kcal: number;
  protein_target_g: number;
  kcal_gap: number;
  protein_ok: boolean;
}

export interface DietPlanDoc {
  exists?: boolean;
  plan?: { days: PlanDay[]; ok: boolean; meals_per_day: number; summary: { avg_kcal: number; avg_protein_g: number; variety: number } };
  prefs?: { diet_style?: string; must_include?: string[]; seed?: number };
  meals_per_day?: number;
  created?: string;
  review: Review;
}

export interface GroceryItem { food: string; quantity: string; grams: number; note: string | null }

export interface Move { id: string; name: string; sets?: number; reps?: number; seconds?: number; rest_s?: number; cue: string; category?: string }

export interface Session {
  type: string;
  label: string;
  minutes: number;
  main: Move[];
  warmup: Move[];
  cooldown: Move[];
  kcal_estimate: number;
  day: string;
}

export interface WorkoutPlan {
  ok: boolean;
  week_index: number;
  deload: boolean;
  level: number;
  mode: string;
  sessions: Session[];
  notes: string[];
  flags: string[];
  summary: { cardio_minutes: number; moderate_equivalent_minutes: number; strength_days: number; meets_who: boolean; rest_days: string[]; kcal_estimate: number };
  screen?: ScreenResult;
  reason?: string;
}

export interface ScreenResult { mode: string; message: string; blocking: string[]; adapt: string[]; unanswered: string[]; cleared: boolean; answers?: Record<string, boolean>; clinician_cleared?: boolean }

export interface WorkoutPlanDoc { exists: boolean; plan?: WorkoutPlan; week_index?: number; params?: Record<string, unknown>; screen?: ScreenResult | null }

export interface Exercise { id: string; name: string; category: string; pattern: string; equipment: string[]; level: number; cue: string }

export interface WorkoutLogDay { date: string; sessions: { id: string; title: string; minutes: number; rpe: number | null; kcal_estimate: number }[] }

export interface Exclusion { code: string; label: string; message: string; clearable: boolean; area?: string | null }

export interface Screening {
  decision: "allowed" | "allowed_with_cautions" | "refused" | "incomplete" | string;
  exclusions: Exclusion[];
  cautions: string[];
  alternative: string | null;
  scoff_positive: boolean;
  gentle_available: boolean;
  message: string;
  bmi?: number;
}

export interface Preview {
  targets: Targets;
  diet: { days: PlanDay[]; ok: boolean; summary: { avg_kcal: number; avg_protein_g: number } };
  exercise: WorkoutPlan;
  good_day: string[];
  commit_text: string[];
  pause_symptoms: string[];
}

export interface TransformPlan {
  id: string;
  status: "active" | "paused" | "completed" | string;
  start_date: string;
  start_weight_kg: number;
  target_weight_kg: number;
  pace_pct_per_week: number;
  targets: Targets;
  selections: Record<string, unknown>;
  weeks_on_plan: number;
  paused: { reason?: string; ts?: string; safety?: boolean } | null;
  maintenance?: { week: number; kcal: number }[] | null;
  history: { ts: string; event: string }[];
}

export interface TodayView {
  plan_status: string;
  view: {
    budget: Budget;
    protein: { eaten_g: number; target_g: number };
    water: { drunk_ml: number; target_ml: number };
    steps: { done: number; target: number };
    message: string;
  };
  meals: { meals: PlanMeal[]; totals: Eaten; day: number } | null;
  good_day: string[];
}

export interface Checkin {
  decision: "insufficient_data" | "continue" | "adjust" | "pause" | string;
  messages: string[];
  options: string[];
  reasoning: string[];
  new_kcal: number;
  change_kcal: number;
  applied: boolean;
  plateau?: boolean;
  trend_rate_kg_per_week?: number | null;
}

export interface Progress {
  weights: { date: string; weight_kg: number }[];
  trend: { date: string; weight_kg: number; trend_kg: number }[];
  rate_kg_per_week: number | null;
  measurements: { date: string; waist_cm?: number; hip_cm?: number; chest_cm?: number; arm_cm?: number; thigh_cm?: number }[];
  adherence: { days_logged_28: number; label: string };
  plan: { status: string; start_weight_kg: number; target_weight_kg: number } | null;
  luteal_note: string;
}

export interface ScreenResponse extends Screening {
  review: Review;
  scoff_questions: string[];
}

export interface PreviewResponse {
  screening: Screening;
  preview: Preview | null;
  review: Review;
}

export interface PlanResponse {
  exists: boolean;
  plan: TransformPlan | null;
  review: Review;
}
