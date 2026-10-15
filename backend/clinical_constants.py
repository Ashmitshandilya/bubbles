"""Every clinical number and rule Bubbles' Fitness / Transformation / Cycle features use, in ONE place.

STATUS: PENDING CLINICIAN REVIEW. These are conservative proposals compiled from public guidance, NOT medical
advice. docs/clinical/BUBBLES_CLINICAL_REVIEW_PACKET.md lists every value below with its rationale and a sign-off
table for a doctor / registered dietitian / pharmacist. Nothing else in the code base may hard-code a clinical
threshold: other modules import from here, so a reviewer's change is a one-line edit.

Each constant carries a short source tag:
  [WHO]  World Health Organization guidance        [CDC] US Centers for Disease Control guidance
  [NHS]  UK National Health Service guidance       [ACOG] American College of Obstetricians & Gynecologists
  [LIT]  widely used published formula/convention  [BUBBLES] Bubbles design choice (needs clinical agreement)
"""
from __future__ import annotations

REVIEW_STATUS = "PENDING_CLINICIAN_REVIEW"
REVIEW_NOTICE = ("Bubbles' targets are general wellness estimates compiled from public guidance and are pending "
                 "review by a clinician. They are not medical advice. Talk to a doctor or dietitian before a "
                 "big change to how you eat or exercise.")

# --- energy expenditure -------------------------------------------------------------------------
# Mifflin-St Jeor resting energy: 10*kg + 6.25*cm - 5*age + constant                        [LIT] Mifflin 1990
MIFFLIN_KG, MIFFLIN_CM, MIFFLIN_AGE = 10.0, 6.25, 5.0
MIFFLIN_CONSTANT = {"male": 5.0, "female": -161.0, "average": -78.0}   # "average" = midpoint, for users who pick neither basis [BUBBLES]
FORMULA_BASES = tuple(MIFFLIN_CONSTANT)
ACTIVITY_FACTORS = {"sedentary": 1.2, "light": 1.375, "moderate": 1.55, "very_active": 1.725, "extra_active": 1.9}  # [LIT]
KCAL_PER_KG_BODY_MASS = 7700.0   # rough energy content of 1 kg of body-mass change; used for ESTIMATES with ranges only [LIT]
KCAL_PER_KG_RANGE = (6500.0, 7700.0)   # lower bound reflects that early loss includes water/glycogen [BUBBLES]

# --- eligibility --------------------------------------------------------------------------------
MIN_ADULT_AGE = 18                 # strict mode and any weight-loss plan are refused below this          [BUBBLES]
MAX_AGE_WITHOUT_CLEARANCE = 70     # strict mode needs a clinician acknowledgement from this age           [BUBBLES]
CAUTION_AGE = 60                   # extra clinician note from this age                                    [BUBBLES]
MIN_PLAUSIBLE = {"height_cm": (120.0, 230.0), "weight_kg": (30.0, 300.0), "age": (13, 100)}  # input sanity [BUBBLES]
RED_FLAG_LOOKBACK_DAYS = 14        # a red-flag symptom in this window blocks strict mode                  [BUBBLES]

# --- BMI ----------------------------------------------------------------------------------------
BMI_UNDERWEIGHT, BMI_OVERWEIGHT, BMI_OBESE = 18.5, 25.0, 30.0       # [WHO]
BMI_ASIAN_OVERWEIGHT, BMI_ASIAN_OBESE = 23.0, 27.5                  # WHO expert consultation 2004 for Asian populations
MIN_TARGET_BMI = 18.5              # a target below this is refused                                          [WHO/BUBBLES]
MIN_START_BMI_FOR_LOSS = 18.5      # a loss plan from an underweight start is refused                        [BUBBLES]

# --- pace and intake safety (hard rules) ----------------------------------------------------------
PACE_PCT_PER_WEEK = (0.25, 0.75)   # default planned loss, % of body weight per week                       [BUBBLES]
HARD_CAP_KG_PER_WEEK = 1.0         # never plan or accept faster; CDC: ~1-2 lb/week is the steady pace      [CDC]
HARD_CAP_PCT_PER_WEEK = 1.0        # and never above 1% of body weight per week                            [BUBBLES]
MAX_DEFICIT_PCT_OF_TDEE = 0.25     # deficit never exceeds 25% of TDEE                                      [BUBBLES]
MAX_DEFICIT_KCAL = 1000.0          # ...nor 1000 kcal/day                                                    [BUBBLES]
INTAKE_FLOOR_KCAL = {"female": 1200.0, "male": 1500.0, "average": 1350.0}   # no plan below, ever, unsupervised [LIT] common unsupervised floors
INTAKE_FLOOR_ABSOLUTE_KCAL = 1200.0  # no basis may ever go below this                                       [LIT]
MAX_SURPLUS_KCAL = 500.0           # gain goals never add more than this per day                            [BUBBLES]
MAX_GAIN_KG_PER_WEEK = 0.5         # gain pace cap                                                          [BUBBLES]

# --- macros -------------------------------------------------------------------------------------
PROTEIN_G_PER_KG = (1.2, 2.0)      # of reference weight, in a deficit with training up to PROTEIN_G_PER_KG_MAX_TRAINING [LIT]
PROTEIN_G_PER_KG_MAX_TRAINING = 2.2
PROTEIN_G_PER_KG_TRAINING = 1.4    # default target when the user does resistance training (middle of the range) [BUBBLES]
PROTEIN_G_PER_KG_KIDNEY_NOTE = 0.8  # "kidney disease" users get no high-protein target, only a clinician note   [BUBBLES]
FAT_MIN_PCT_KCAL = 0.20            # [LIT]
FAT_MAX_PCT_KCAL = 0.35            # [LIT]
FIBRE_G_PER_DAY = (25.0, 30.0)     # [LIT]
SODIUM_LIMIT_MG = 2000.0           # WHO: <2 g sodium (<5 g salt) per day for adults                         [WHO]
ADDED_SUGAR_PCT_KCAL = 0.10        # WHO: <10% of energy from free sugars                                    [WHO]
OBESE_REFERENCE_WEIGHT_WEIGHT = 0.25  # for BMI>=30, protein uses ideal + 0.25*(actual-ideal)               [BUBBLES]
IDEAL_BMI_FOR_REFERENCE = 22.5

# --- activity / exercise ---------------------------------------------------------------------------
WHO_MODERATE_MIN_PER_WEEK = (150, 300)    # [WHO]
WHO_VIGOROUS_MIN_PER_WEEK = (75, 150)     # [WHO]
WHO_STRENGTH_DAYS_MIN = 2                 # [WHO]
MAX_WEEKLY_VOLUME_INCREASE = 0.10         # no more than ~10% more volume week to week                      [LIT/BUBBLES]
DELOAD_EVERY_WEEKS = 5                    # lighter week every 4th-6th week                                  [BUBBLES]
EXERCISE_CALORIE_CREDIT = 0.5             # only half of the estimated burn is added back to the food budget [BUBBLES]
EXERCISE_CREDIT_MAX_KCAL = 300            # and never more than this per day, however long the logged workouts [BUBBLES]
EATING_SCREEN_STICKY_DAYS = 30            # a positive eating screen keeps weight-loss numbers off for this long, even if the answers are re-entered [BUBBLES]
CLEARANCE_VALID_DAYS = 365                # a recorded clinician go-ahead lasts a year, then must be renewed [BUBBLES]
STEPS_BY_ACTIVITY = {"sedentary": 6000, "light": 7500, "moderate": 9000, "very_active": 10000, "extra_active": 10000}  # daily step goals [BUBBLES]
CHECKIN_MIN_DAYS_BETWEEN = 6              # the weekly check-in cannot be repeated sooner [BUBBLES]
MET_VALUES = {                            # Compendium of Physical Activities (approximate, labelled estimates) [LIT]
    "walking_slow": 2.8, "walking_brisk": 4.3, "walking_uphill": 6.0, "jogging": 7.0, "running": 9.8,
    "cycling_easy": 4.0, "cycling_moderate": 6.8, "cycling_vigorous": 10.0, "swimming_easy": 5.8, "swimming_vigorous": 9.8,
    "yoga": 2.8, "pilates": 3.0, "strength_light": 3.5, "strength_vigorous": 6.0, "hiit": 8.0, "dance": 5.0,
    "stairs": 8.8, "skipping": 11.0, "stretching": 2.3, "household": 3.0, "badminton": 5.5, "football": 7.0,
    "cricket": 4.8, "basketball": 6.5, "tennis": 7.3, "zumba": 6.5, "surya_namaskar": 3.3, "elliptical": 5.0, "rowing": 7.0,
}
RPE_TARGET_MODERATE = (3, 6)              # 0-10 effort scale; "moderate" = can talk but not sing               [LIT]

# --- hydration ----------------------------------------------------------------------------------
HYDRATION_ML_PER_KG = 33.0                # total daily fluid from drinks, a rough baseline                    [LIT]
HYDRATION_ML_PER_EXERCISE_MIN = 10.0      # add per minute of moderate exercise                                [BUBBLES]
HYDRATION_PREGNANCY_ADD_ML, HYDRATION_BREASTFEEDING_ADD_ML = 300.0, 700.0   # [LIT]
HYDRATION_MIN_ML, HYDRATION_MAX_ML = 1500.0, 4000.0   # we never suggest less/more than this                   [BUBBLES]
HYDRATION_SINGLE_LOG_MAX_ML = 2000.0      # one logged drink above this is rejected as a typo                  [BUBBLES]
BEVERAGE_HYDRATION_FACTOR = {"water": 1.0, "tea": 0.9, "coffee": 0.8, "milk": 0.9, "juice": 0.85, "buttermilk": 0.95,
                             "coconut_water": 0.95, "soda": 0.8, "alcohol": 0.0, "other": 0.8}   # [LIT/BUBBLES]
FLUID_RESTRICTION_CONDITIONS = ("heart failure", "kidney", "dialysis", "ckd", "cirrhosis", "fluid restriction", "siadh", "hyponatremia")

# --- sleep --------------------------------------------------------------------------------------
SLEEP_HOURS_ADULT = (7.0, 9.0)            # [NHS/AASM]
SLEEP_HOURS_TEEN = (8.0, 10.0)            # [BUBBLES]
SLEEP_REGULARITY_GOOD_MINUTES = 30        # bedtime/wake variation considered consistent                       [BUBBLES]
SLEEP_DEBT_WINDOW_DAYS = 7

# --- cycle (menstrual) ----------------------------------------------------------------------------
CYCLE_NORMAL_RANGE_DAYS = (21, 35)        # adults; outside this = suggest a clinician                         [ACOG]
CYCLE_ADOLESCENT_RANGE_DAYS = (21, 45)    # [ACOG]
CYCLE_PLAUSIBLE_DAYS = (15, 90)           # gaps outside this are treated as missed logs, not cycles           [BUBBLES]
PERIOD_NORMAL_MAX_DAYS = 7                # bleeding longer than this = suggest a clinician                    [ACOG]
MISSED_CYCLES_FLAG = 3                    # >= 3 missed periods (not pregnant/menopause) = clinician            [ACOG]
POSTMENOPAUSAL_AFTER_MONTHS_WITHOUT_PERIOD = 12   # bleeding after this gap = clinician                        [BUBBLES/NHS]
HEAVY_BLEEDING_PADS_PER_HOUR_FLAG = 1     # soaking a pad/tampon every hour for 2+ hours = urgent advice       [ACOG]
LUTEAL_LENGTH_DAYS, LUTEAL_RANGE_DAYS = 14, (10, 16)   # ovulation ~14 days before the next period             [LIT]
FERTILE_WINDOW_DAYS_BEFORE_OVULATION = 5  # sperm can survive ~5 days; window = 5 days before + ovulation day  [LIT]
CYCLE_MIN_CYCLES_FOR_PREDICTION = 3       # until then predictions carry a "learning" label                    [BUBBLES]
CYCLE_HISTORY_WEIGHT_DECAY = 0.8          # most recent cycle weighs 1, previous 0.8, then 0.64...             [BUBBLES]
CYCLE_HISTORY_MAX_CYCLES = 12
BBT_SHIFT_RISE_C = 0.2                    # coverline rule: 3 temps >= 0.2C above the previous 6              [LIT]
BBT_SHIFT_DAYS, BBT_BASELINE_DAYS = 3, 6
IRREGULAR_SD_DAYS = 4.0                   # cycle-length SD above this => irregular mode, wider windows         [BUBBLES]
POSTPARTUM_UNPREDICTABLE_MONTHS = 6       # predictions are labelled low-confidence                            [BUBBLES]
PERIMENOPAUSE_TYPICAL_AGE = (40, 58)      # [BUBBLES]
# additive cycle constants used by backend/cycle_engine.py, cycle_flags.py and cycle_api.py (all PENDING CLINICIAN REVIEW)
CYCLE_DEFAULT_LENGTH_DAYS = 28            # used only while "learning" and for the first prediction                [LIT]
CYCLE_LEARNING_HALF_WINDOW_DAYS = 4       # +/- days around a prediction made from fewer than 3 cycles            [BUBBLES]
CYCLE_WINDOW_SD_MULTIPLIER = 1.5          # prediction half-window = 1.5 x personal SD of cycle length             [BUBBLES]
CYCLE_WINDOW_HALF_DAYS = (1, 14)          # clamp for the half-window                                              [BUBBLES]
CYCLE_HIGH_CONFIDENCE = (6, 2.0)          # (min cycles, max SD days) for a "high" confidence label                [BUBBLES]
PERIOD_MERGE_WITHIN_DAYS = 7              # a second "start" within this many days belongs to the same period      [BUBBLES]
PERIOD_DEFAULT_LENGTH_DAYS = 5            # used for phase maths until the user's own period length is known       [BUBBLES]
PERIOD_MAX_PLAUSIBLE_DAYS = 14            # longer runs of bleeding are not treated as one period                  [BUBBLES]
MISSED_PERIOD_GRACE_DAYS = 7              # a period counts as missed once it is this many days overdue            [BUBBLES]
SEVERE_PAIN_LEVEL = 8                     # 0-10 self-rated pain at or above this = suggest a clinician            [BUBBLES]
CYCLE_SUDDEN_CHANGE_DAYS = 10             # latest cycle differs from the usual by more than this = gentle note    [BUBBLES]
POSTPARTUM_LOCHIA_DAYS = 42               # bleeding in the first 6 weeks after birth is not a period              [NHS]
PREGNANCY_DAYS = 280                      # 40 weeks from the first day of the last period (Naegele)               [LIT]
BBT_VALID_C = (34.0, 40.0)                # a logged temperature outside this is rejected as a typo                [BUBBLES]
LH_OVULATION_AFTER_POSITIVE_DAYS = (0, 2) # ovulation is usually within ~1-2 days after a positive LH test         [LIT]
INSIGHT_MIN_CYCLES = 3                    # phase insights need this many cycles with data                         [BUBBLES]
INSIGHT_MIN_POINTS_PER_PHASE = 5          # ...and this many data points in each phase compared                    [BUBBLES]
INSIGHT_MIN_DIFFERENCE_FRACTION = 0.10    # phases closer than 10% of the metric's range are called "no clear difference" [BUBBLES]

# --- strict transformation mode -----------------------------------------------------------------------
STRICT_MIN_LOG_DAYS_FOR_CHECKIN = 4       # a weekly check-in needs this many logged food days                  [BUBBLES]
STRICT_MIN_WEIGH_INS_FOR_CHECKIN = 3
STRICT_MIN_WEEKS_FOR_EXPENDITURE_ESTIMATE = 2
TREND_SMOOTHING_ALPHA = 0.1               # exponentially weighted weight trend (Hacker's Diet style)           [LIT]
PLATEAU_WEEKS = 3                         # trend change below PLATEAU_PCT_PER_WEEK for this long = plateau     [BUBBLES]
PLATEAU_PCT_PER_WEEK = 0.1
DIET_BREAK_AFTER_WEEKS = 12               # suggest a 1-2 week maintenance break                                [BUBBLES]
DIET_BREAK_WEEKS = (1, 2)
MAINTENANCE_RETURN_KCAL_PER_WEEK = 100.0  # reverse-diet step when finishing                                    [BUBBLES]
MAX_WEEKLY_CALORIE_CHANGE = 150.0         # the weekly check-in never moves the target by more than this         [BUBBLES]
SAFETY_LOW_INTAKE_DAYS_OF_7 = 3           # logged days under the floor in a week => pause                      [BUBBLES]
SAFETY_RAPID_LOSS_KG_PER_WEEK = 1.2       # trend loss above this for 2 weeks => pause and soften                [BUBBLES]
SAFETY_RAPID_LOSS_WEEKS = 2
SAFETY_REGAIN_KG_IN_WEEK = 2.0
SAFETY_MISSED_PERIOD_MONTHS = 3           # amenorrhoea >= 3 months => possible low energy availability          [ACOG/BUBBLES]
SAFETY_HIGH_EXERCISE_MIN_PER_WEEK = 420   # with very low intake, flags relative energy deficiency risk          [BUBBLES]
SAFETY_BINGE_RESTRICT_SWING_KCAL = 1500   # alternating day-to-day intake swing                                  [BUBBLES]
SAFETY_COOLDOWN_DAYS = 7                  # after a pause, gentle check-in before any restart                    [BUBBLES]

# --- screening -----------------------------------------------------------------------------------
SCOFF_POSITIVE_AT = 2                     # SCOFF (Morgan 1999): 2+ yes answers                                  [LIT]
SCOFF_QUESTIONS = (
    "Do you make yourself sick because you feel uncomfortably full?",
    "Do you worry you have lost control over how much you eat?",
    "Have you recently lost more than about 6 kg (one stone) in a three-month period?",
    "Do you believe yourself to be fat when others say you are too thin?",
    "Would you say that food dominates your life?",
)
PHQ2_POSITIVE_AT = 3                      # PHQ-2 (public domain): score 0-6, >=3 suggests talking to someone    [LIT]
GAD2_POSITIVE_AT = 3                      # GAD-2 (public domain)                                                [LIT]
PHQ2_QUESTIONS = ("Little interest or pleasure in doing things",
                  "Feeling down, depressed, or hopeless")
GAD2_QUESTIONS = ("Feeling nervous, anxious, or on edge",
                  "Not being able to stop or control worrying")
PARQ_QUESTIONS = (   # own wording, in the spirit of the free PAR-Q+; "yes" to any of the first five blocks strict plans [BUBBLES]
    ("heart", "Has a doctor ever said you have a heart condition, or that you should only do exercise recommended by a doctor?"),
    ("chest", "Do you feel pain in your chest when you are active or at rest?"),
    ("dizzy", "Do you lose your balance because of dizziness, or have you lost consciousness in the last 12 months?"),
    ("bp", "Has a doctor told you your blood pressure is high and not controlled?"),
    ("breath", "Do you get unusually short of breath with light activity?"),
    ("bone_joint", "Do you have a bone or joint problem that could get worse with more activity?"),
    ("meds", "Are you taking medicine for blood pressure, a heart problem, diabetes or breathing right now?"),
    ("pregnant", "Are you pregnant or within 6 weeks of giving birth?"),
    ("other", "Do you know of any other reason you should not do more physical activity?"),
)
PARQ_BLOCKING_KEYS = ("heart", "chest", "dizzy", "bp", "breath")   # clinician clearance first; walking/mobility only

# --- condition keyword rules (matched case-insensitively against conditions/medications the user recorded) --
STRICT_BLOCKING_CONDITIONS = {   # hard exclusions: refuse strict mode without clinician clearance [BUBBLES]
    "eating disorder": ("anorexia", "bulimia", "binge eating", "eating disorder", "orthorexia", "arfid"),
    "type 1 diabetes": ("type 1 diabetes", "t1d", "type-1 diabetes", "type i diabetes"),
    "kidney disease": ("kidney disease", "ckd", "renal failure", "dialysis", "nephrotic"),
    "heart disease": ("heart disease", "heart failure", "coronary", "angina", "cardiomyopathy", "arrhythmia", "atrial fibrillation", "heart attack", "myocardial"),
    "uncontrolled hypertension": ("uncontrolled hypertension", "hypertensive crisis"),
    "pregnancy or breastfeeding": ("pregnant", "pregnancy", "breastfeeding", "lactating"),
    "liver disease": ("cirrhosis", "liver failure", "hepatic failure"),
    "recent surgery or injury": ("post-surgery", "post surgery", "recent surgery", "fracture", "torn", "acute injury"),
    "cancer treatment": ("chemotherapy", "radiotherapy", "cancer treatment"),
    "epilepsy on ketogenic diet": (),   # placeholder for a reviewer's list
}
STRICT_BLOCKING_MEDICATIONS = {  # insulin / sulfonylureas: hypoglycaemia risk when intake drops [BUBBLES]
    "insulin or sulfonylurea": ("insulin", "glipizide", "glimepiride", "glibenclamide", "glyburide", "gliclazide", "tolbutamide"),
    "anticoagulant (diet vitamin K changes)": ("warfarin", "acenocoumarol"),
    "lithium": ("lithium",),
}
SOFT_CAUTION_CONDITIONS = {      # allowed, but the plan adapts and a clinician note is shown [BUBBLES]
    "type 2 diabetes": ("type 2 diabetes", "t2d", "diabetes", "prediabetes", "insulin resistance"),
    "hypertension": ("hypertension", "high blood pressure"),
    "pcos": ("pcos", "polycystic"),
    "thyroid condition": ("hypothyroid", "hyperthyroid", "thyroid", "hashimoto", "graves"),
    "anaemia": ("anemia", "anaemia", "low iron", "iron deficiency", "ferritin"),
    "asthma": ("asthma", "copd"),
    "joint issue": ("arthritis", "knee pain", "back pain", "osteoarthritis", "sciatica", "slipped disc"),
    "osteoporosis": ("osteoporosis", "osteopenia"),
    "gerd": ("gerd", "reflux", "gastritis", "ulcer"),
    "ibs": ("ibs", "irritable bowel", "celiac", "coeliac", "crohn", "colitis"),
    "gout": ("gout", "high uric acid"),
    "endometriosis": ("endometriosis", "adenomyosis", "fibroid"),
    "depression or anxiety": ("depression", "anxiety", "panic"),
    "high cholesterol": ("cholesterol", "dyslipidemia", "dyslipidaemia", "hyperlipidemia"),
}
GLP1_MEDICATIONS = ("semaglutide", "ozempic", "wegovy", "rybelsus", "tirzepatide", "mounjaro", "zepbound", "liraglutide", "saxenda", "victoza", "dulaglutide", "trulicity")
CONTRACEPTIVE_PILL_KEYWORDS = ("pill", "ocp", "contraceptive", "levonorgestrel", "ethinyl", "drospirenone", "norethindrone")

# --- red-flag wording shown on every plan (plain language) ---------------------------------------------------------
PLAN_PAUSE_SYMPTOMS = (
    "chest pain or pressure", "fainting or near-fainting", "a racing or irregular heartbeat that does not settle",
    "severe or lasting dizziness", "missing your period for 3 months or more (and you are not pregnant)",
    "feeling that you cannot stop thinking about food, or that you are losing control of eating",
    "sudden swelling, severe weakness, or confusion",
)

# --- calculated limits others read ---------------------------------------------------------------------------------
FORBIDDEN_ADVICE = ("supplement dose", "prescription change", "stop your medicine", "diagnosis")  # for copy tests [BUBBLES]


# =====================================================================================================================
# WELLNESS: sleep / hydration / medications / mind / notifications  (added by the wellness backend; PENDING REVIEW)
# Additive only: nothing above this line was changed. Source tags as at the top of the file.
# =====================================================================================================================

# --- sleep (extends SLEEP_HOURS_ADULT / SLEEP_HOURS_TEEN) -------------------------------------------------------------
SLEEP_HOURS_CHILD = (9.0, 12.0)           # about 6-12 years                                                    [AASM/BUBBLES]
SLEEP_HOURS_OLDER = (7.0, 8.0)            # 65 and over                                                         [AASM/NHS]
SLEEP_CHILD_MAX_AGE, SLEEP_TEEN_MAX_AGE, SLEEP_OLDER_MIN_AGE = 12, 17, 65       # age bands for the goal       [BUBBLES]
SLEEP_GOAL_BOUNDS_H = (4.0, 12.0)         # a user-set goal outside this is refused as a typo                    [BUBBLES]
SLEEP_SCORE_WEIGHTS = {"duration": 50, "regularity": 30, "quality": 20}   # 0-100 score parts; missing parts are re-weighted [BUBBLES]
SLEEP_REGULARITY_ZERO_MINUTES = 120       # bed/wake variation at which the regularity part reaches 0            [BUBBLES]
SLEEP_MIN_NIGHTS_FOR_REGULARITY = 3
SLEEP_ON_TRACK_TOLERANCE_H = 0.5          # a night within this of the goal counts for the "near my goal" streak [BUBBLES]
SLEEP_DEBT_MIN_NIGHTS = 3                 # fewer logged nights than this => debt is labelled partial            [BUBBLES]
SLEEP_WEEKDAY_MIN_NIGHTS, SLEEP_WEEKDAY_MIN_SPREAD_H = 2, 0.5   # best/worst weekday needs this much data/spread [BUBBLES]
SLEEP_INSIGHT_MIN_NIGHTS = 10             # tag insights need this many nights with tags logged                  [BUBBLES]
SLEEP_INSIGHT_MIN_PER_GROUP = 3           # ...and this many nights with AND without the tag                     [BUBBLES]
SLEEP_INSIGHT_MIN_DIFF_MIN = 20           # ...and at least this much difference to mention                      [BUBBLES]
SLEEP_WINDDOWN_MINUTES = 45               # suggested wind-down starts this long before bedtime                  [BUBBLES]
SLEEP_TAGS = ("caffeine", "alcohol", "stress", "late_meal", "screen", "exercise")   # [BUBBLES]
SLEEP_NAP_MAX_MIN = 300                   # one logged nap above this is refused as a typo                       [BUBBLES]

# --- hydration (extends the block above) -------------------------------------------------------------------------------
HYDRATION_DEFAULT_ML = 2000.0             # shown (labelled "general") until a body weight is known              [BUBBLES]
HYDRATION_CUSTOM_MIN_ML = 10.0            # a custom log below this is refused as a typo                         [BUBBLES]
HYDRATION_PRESETS_ML = {"cup": 150, "glass": 250, "bottle_500": 500, "bottle_750": 750, "bottle_1000": 1000}   # one-tap sizes [BUBBLES]
HYDRATION_REMINDER_EVERY_MIN = 120        # reminder slots inside waking hours                                   [BUBBLES]
HYDRATION_REMINDER_BEFORE_SLEEP_MIN = 120 # no reminder in the last 2 h before sleep (no catch-up at night)       [BUBBLES]
HYDRATION_REMINDER_TOLERANCE_ML = 200     # a slot is "needed" only if behind the day's pace by at least this     [BUBBLES]
HYDRATION_GARDEN_LEVELS = ((0, "seed"), (3, "sprout"), (7, "leaves"), (14, "blossom"), (30, "pond"), (60, "oasis"))   # (goal days, level) [BUBBLES]

# --- medications ---------------------------------------------------------------------------------------------------------
MED_DOSE_WINDOW_MIN = 60                  # a dose is "due" from this long before to this long after its time     [BUBBLES]
MED_SNOOZE_OPTIONS_MIN = (10, 15, 30, 60)
MED_REFILL_ALERT_DAYS = 7                 # default: flag when about this many days of tablets are left           [BUBBLES]
MED_ADHERENCE_MIN_DOSES = 5               # no percentage is shown below this many scheduled doses                [BUBBLES]
MED_ADHERENCE_STEADY_PCT = 90             # wording only                                                         [BUBBLES]
MED_SKIP_REASONS = ("side_effects", "ran_out", "forgot", "felt_unwell", "advised_by_clinician", "travelling", "other")   # [BUBBLES]
GLP1_NAUSEA_TALK_AT = 7                   # 0-10 nausea at/above this => suggest speaking to the prescriber        [BUBBLES]
GLP1_INJECTION_SITES = ("abdomen_left", "abdomen_right", "thigh_left", "thigh_right", "upper_arm_left", "upper_arm_right")   # [BUBBLES]

# Interaction checker: class -> names (generic + common brand) matched as whole words, case-insensitively. A pharmacist
# edits THESE lists and INTERACTION_RULES; the rules must keep matching the table in BUBBLES_CLINICAL_REVIEW_PACKET.md s.10.
DRUG_CLASSES = {
    "warfarin": ("warfarin", "coumadin", "jantoven", "uniwarfin", "warf"),   # "warf" = Indian brand; brand aliases below need pharmacist review
    "nsaid": ("nsaid", "nsaids", "ibuprofen", "diclofenac", "naproxen", "brufen", "advil", "motrin", "voltaren", "naprosyn", "aleve",
              "ketorolac", "mefenamic acid", "etoricoxib", "celecoxib", "nimesulide", "indomethacin", "piroxicam", "meloxicam",
              "aceclofenac", "combiflam", "voveran", "zerodol", "dolonex", "nimulid", "mobic", "arcoxia"),   # last 8: common Indian names/brands (pharmacist to confirm)
    "aspirin": ("aspirin", "ecosprin", "disprin", "acetylsalicylic acid"),
    "ssri_snri": ("ssri", "snri", "fluoxetine", "sertraline", "paroxetine", "citalopram", "escitalopram", "fluvoxamine", "venlafaxine",
                  "duloxetine", "desvenlafaxine", "prozac", "zoloft", "lexapro", "cipralex", "celexa", "paxil", "effexor", "cymbalta"),
    "ace_arb": ("ace inhibitor", "arb", "lisinopril", "enalapril", "ramipril", "perindopril", "captopril", "benazepril", "losartan",
                "valsartan", "telmisartan", "olmesartan", "irbesartan", "candesartan", "cozaar", "diovan", "telma", "repace"),
    "potassium": ("potassium", "potassium chloride", "slow-k", "k-dur"),
    "spironolactone": ("spironolactone", "aldactone"),
    "tramadol": ("tramadol", "ultram"),
    "triptan": ("sumatriptan", "rizatriptan", "zolmitriptan", "eletriptan", "naratriptan", "imitrex", "triptan"),
    "linezolid": ("linezolid", "zyvox"),
    "st_johns_wort": ("st john's wort", "st johns wort", "st. john's wort", "hypericum"),
    "nitrate": ("isosorbide", "nitroglycerin", "nitroglycerine", "glyceryl trinitrate", "gtn", "nitrate", "sorbitrate", "isordil"),
    "pde5": ("sildenafil", "tadalafil", "viagra", "cialis", "revatio"),
    "simvastatin": ("simvastatin", "zocor"),
    "clarithromycin": ("clarithromycin", "klacid", "biaxin"),
    "grapefruit": ("grapefruit",),
    "levothyroxine": ("levothyroxine", "thyroxine", "eltroxin", "synthroid", "thyronorm"),
    "calcium": ("calcium", "calcium carbonate", "shelcal", "caltrate"),
    "iron": ("iron", "ferrous", "ferrous sulfate", "ferrous sulphate", "ferrous fumarate", "ferrous ascorbate"),
    "antacid": ("antacid", "gelusil", "digene", "mylanta", "magnesium hydroxide", "aluminium hydroxide", "aluminum hydroxide"),
    "dairy": ("dairy", "milk", "curd", "yogurt", "yoghurt", "cheese", "paneer"),
    "tetracycline_cipro": ("tetracycline", "doxycycline", "ciprofloxacin", "vibramycin", "ciplox", "cipro"),
    "metformin": ("metformin", "glucophage", "glycomet"),
    "alcohol": ("alcohol", "wine", "beer", "whisky", "whiskey", "rum", "vodka"),
    "methotrexate": ("methotrexate", "trexall"),
    "trimethoprim": ("trimethoprim", "co-trimoxazole", "cotrimoxazole", "bactrim", "septran"),
    "digoxin": ("digoxin", "lanoxin"),
    "diuretic": ("diuretic", "water pill", "furosemide", "frusemide", "lasix", "hydrochlorothiazide", "hctz", "chlorthalidone",
                 "indapamide", "torsemide", "torasemide", "bumetanide", "metolazone"),
    "insulin_sulfonylurea": ("insulin", "sulfonylurea", "glipizide", "glimepiride", "glibenclamide", "glyburide", "gliclazide",
                             "tolbutamide", "lantus", "humalog", "novorapid", "tresiba", "levemir", "humulin", "novolin", "amaryl"),
    "calorie_cut": ("calorie deficit", "calorie cut", "calorie restriction", "very low calorie", "crash diet", "fasting"),
    "lithium": ("lithium", "lithosun"),
    "chc": ("combined pill", "combined oral contraceptive", "contraceptive pill", "birth control pill", "oral contraceptive", "ocp",
            "ethinyl estradiol", "ethinylestradiol", "yasmin", "microgynon", "mala-d", "diane-35", "cilest"),
    "rifampicin": ("rifampicin", "rifampin", "rimactane"),
    "antiepileptic": ("carbamazepine", "phenytoin", "phenobarbital", "phenobarbitone", "primidone", "oxcarbazepine", "topiramate"),
    # allergy-only families (no interaction rule uses these)
    "penicillin": ("penicillin", "amoxicillin", "ampicillin", "augmentin", "amoxyclav", "co-amoxiclav", "flucloxacillin", "piperacillin"),
    "sulfa": ("sulfa", "sulfonamide", "sulfamethoxazole", "co-trimoxazole", "cotrimoxazole", "bactrim", "septran"),
}
# One entry per row of the packet's s.10 table. "pair"/"concern"/"level" are copied VERBATIM from the packet (a test compares them);
# "plain" is the friendly wording shown to users; copy never forbids anything, it only says "check with your pharmacist".
INTERACTION_RULES = (
    {"id": "warfarin_nsaid", "a": "warfarin", "b": ("nsaid", "aspirin"), "level": "high",
     "pair": "warfarin + NSAIDs (ibuprofen, diclofenac, naproxen) or aspirin", "concern": "bleeding",
     "plain": "the chance of bleeding can go up"},
    {"id": "nsaid_ssri", "a": "nsaid", "b": ("ssri_snri",), "level": "moderate",
     "pair": "NSAID + SSRI/SNRI", "concern": "bleeding, stomach", "plain": "the chance of bleeding or stomach upset can go up"},
    {"id": "acearb_potassium", "a": "ace_arb", "b": ("potassium", "spironolactone"), "level": "high",
     "pair": "ACE inhibitor / ARB + potassium supplements or spironolactone", "concern": "high potassium",
     "plain": "potassium in the blood can rise"},
    {"id": "acearb_nsaid", "a": "ace_arb", "b": ("nsaid",), "level": "moderate",
     "pair": "ACE inhibitor / ARB + NSAID", "concern": "kidney strain, less BP effect",
     "plain": "the kidneys can be strained and the blood pressure medicine may work less well"},
    {"id": "ssri_serotonergic", "a": "ssri_snri", "b": ("tramadol", "triptan", "linezolid", "st_johns_wort"), "level": "high",
     "pair": "SSRI + tramadol / triptan / linezolid / St John's wort", "concern": "serotonin syndrome",
     "plain": "serotonin levels can get too high (serotonin syndrome)"},
    {"id": "nitrate_pde5", "a": "nitrate", "b": ("pde5",), "level": "high",
     "pair": "nitrate + sildenafil / tadalafil", "concern": "severe low BP", "plain": "blood pressure can drop very low"},
    {"id": "simvastatin_cyp3a4", "a": "simvastatin", "b": ("clarithromycin", "grapefruit"), "level": "high",
     "pair": "statin (simvastatin) + clarithromycin / grapefruit", "concern": "muscle toxicity",
     "plain": "the statin level can rise and affect the muscles"},
    {"id": "levothyroxine_minerals", "a": "levothyroxine", "b": ("calcium", "iron", "antacid"), "level": "timing",
     "pair": "levothyroxine + calcium / iron / antacid", "concern": "absorption — separate by 4 h",
     "plain": "the thyroid tablet may be absorbed less well when taken close together; many people space them about 4 hours apart"},
    {"id": "tetracycline_minerals", "a": "tetracycline_cipro", "b": ("dairy", "calcium", "iron", "antacid"), "level": "timing",
     "pair": "tetracycline / doxycycline / ciprofloxacin + dairy / calcium / iron / antacid", "concern": "absorption — separate",
     "plain": "the antibiotic may be absorbed less well when taken close together, so the timing between them can matter"},
    {"id": "metformin_alcohol", "a": "metformin", "b": ("alcohol",), "level": "moderate",
     "pair": "metformin + heavy alcohol", "concern": "lactic acidosis risk",
     "plain": "drinking alcohol, especially a lot, can raise the chance of a build-up of lactic acid"},
    {"id": "methotrexate_nsaid", "a": "methotrexate", "b": ("nsaid", "trimethoprim"), "level": "high",
     "pair": "methotrexate + NSAID / trimethoprim", "concern": "toxicity", "plain": "methotrexate levels can rise too high"},
    {"id": "digoxin_diuretic", "a": "digoxin", "b": ("diuretic",), "level": "high",
     "pair": "digoxin + diuretics (low potassium)", "concern": "digoxin toxicity",
     "plain": "a water tablet can lower potassium, which makes digoxin more likely to build up"},
    {"id": "hypoglycaemia", "a": "insulin_sulfonylurea", "b": ("alcohol", "calorie_cut"), "level": "high",
     "pair": "insulin / sulfonylurea + alcohol / big calorie cuts", "concern": "low blood sugar",
     "plain": "blood sugar can drop too low"},
    {"id": "lithium_renal", "a": "lithium", "b": ("nsaid", "ace_arb", "diuretic"), "level": "high",
     "pair": "lithium + NSAID / ACE inhibitor / diuretic", "concern": "lithium toxicity", "plain": "lithium levels can rise too high"},
    {"id": "chc_inducers", "a": "chc", "b": ("rifampicin", "antiepileptic", "st_johns_wort"), "level": "high",
     "pair": "combined hormonal contraceptive + rifampicin / some anti-epileptics / St John's wort",
     "concern": "contraceptive less effective", "plain": "the contraceptive may work less well"},
)

# --- mind ------------------------------------------------------------------------------------------------------------------
MIND_SCREEN_INTERVAL_DAYS = 14            # a gentle PHQ-2 / GAD-2 check-in is offered at most this often          [BUBBLES]
MIND_INSIGHT_MIN_DAYS = 10                # mood correlations need this many paired days                           [BUBBLES]
MIND_INSIGHT_MIN_PER_GROUP = 3            # ...and this many days in each group                                    [BUBBLES]
MIND_INSIGHT_MIN_DIFF = 1.0               # ...and a difference of at least this on the 1-10 mood scale             [BUBBLES]
MIND_ACTIVITIES = ("exercise", "social", "outdoors", "work", "family", "rest", "hobby", "meditation", "reading", "music", "cooking", "travel")   # [BUBBLES]
MIND_JOURNAL_MAX_CHARS = 5000

# --- notifications -------------------------------------------------------------------------------------------------------
NOTIFY_DAILY_CAP_DEFAULT, NOTIFY_DAILY_CAP_MAX = 5, 20      # [BUBBLES]
NOTIFY_QUIET_HOURS_DEFAULT = ("23:00", "07:00")             # no notifications are created inside this window (wind-down fires before it) [BUBBLES]
NOTIFY_KINDS = ("water", "med", "winddown", "system")       # [BUBBLES]

# =====================================================================================================================
# ORGAN MAP (organ_map_engine.py; PENDING CLINICIAN REVIEW). Additive only. These numbers decide when an area of the
# body map says "worth watching" or "talk to a doctor". They never diagnose; every crossing is shown to the user with
# the exact readings that caused it.
# =====================================================================================================================
ORGAN_WINDOW_DAYS = (7, 180)              # allowed look-back for the organ map                                     [BUBBLES]
ORGAN_WINDOW_DEFAULT_DAYS = 30            # [BUBBLES]
ORGAN_RED_FLAG_LOOKBACK_DAYS = 7          # symptoms this recent go through the safety engine again                 [BUBBLES]
ORGAN_EVIDENCE_MAX = 12                   # evidence items returned per organ (newest first, red flags first)       [BUBBLES]
ORGAN_CONFIDENCE_MEDIUM_ENTRIES = 4       # entries for a "medium" confidence label                                 [BUBBLES]
ORGAN_CONFIDENCE_HIGH_ENTRIES = 10        # ...and for "high" (also needs two different kinds of data)              [BUBBLES]
# heart
BP_HIGH_MMHG = (140, 90)                  # systolic or diastolic at/above = high reading                           [NHS/NICE]
BP_VERY_HIGH_MMHG = (180, 120)            # at/above = talk to a doctor promptly                                    [AHA]
BP_LOW_SYSTOLIC_MMHG = 90                 # below = worth noting (especially with dizziness)                       [NHS]
BP_HIGH_READINGS_TALK = 3                 # this many high readings in the window = talk to a doctor                [BUBBLES]
HEART_RATE_STEADY_BPM = (50, 100)         # typical adult range at rest (fit people can sit lower)                  [AHA/BUBBLES]
HEART_RATE_TALK_BPM = (40, 120)           # median of readings outside this = talk to a doctor                      [BUBBLES]
# lungs
SPO2_WATCH_BELOW_PCT = 95                 # [NHS]
SPO2_TALK_BELOW_PCT = 92                  # 92% or lower = get advice promptly                                      [NHS]
COUGH_TALK_SPAN_DAYS = 21                 # a cough logged across 3 weeks or more = see a doctor                    [NHS]
# brain
MOOD_LOW_AVERAGE = 4.0                    # 0-10 mood average at/below = worth watching (needs 3 entries)          [BUBBLES]
MOOD_LOW_DAY_SCORE = 3                    # a 0-10 mood at/below this counts as a low day                           [BUBBLES]
MOOD_LOW_DAYS_TALK = 10                   # low days in the window = talk to a doctor (NHS: most days for 2 weeks) [NHS/BUBBLES]
STRESS_HIGH_AVERAGE = 7.0                 # 0-10 stress average at/above = worth watching                           [BUBBLES]
HEADACHE_DAYS_WATCH = 4                   # headache days in the window                                             [BUBBLES]
HEADACHE_DAYS_TALK = 15                   # 15+ headache days (ICHD-3 chronic headache is 15+ a month)              [LIT]
ORGAN_MIN_ENTRIES_FOR_AVERAGE = 3         # an average needs this many entries                                      [BUBBLES]
# stomach and intestines
DIGESTIVE_DAYS_WATCH = 3                  # days with digestive symptoms in the window                              [BUBBLES]
DIGESTIVE_DAYS_TALK = 14                  # [BUBBLES]
# liver and pancreas (patterns only; gentle notes)
ALCOHOL_DAYS_PER_WEEK_WATCH = 3.0         # average drinking days a week (UK CMO: spread drinks, keep drink-free days) [NHS/BUBBLES]
SUGARY_DAYS_PER_WEEK_WATCH = 5.0          # average days a week with sweets or sugary drinks                        [WHO/BUBBLES]
ORGAN_ALCOHOL_TERMS = DRUG_CLASSES["alcohol"] + ("gin", "brandy", "cocktail", "cocktails", "tequila", "champagne", "daru", "sharab", "toddy")
ORGAN_SUGARY_TERMS = ("soda", "cola", "coke", "pepsi", "soft drink", "cold drink", "energy drink", "cake", "pastry", "ice cream",
                      "chocolate", "dessert", "sweets", "mithai", "candy", "doughnut", "donut", "cookies", "brownie", "halwa")
# kidneys and bladder
WATER_LOW_ML_PER_DAY = 1200.0             # average on logged days below this = worth watching                      [BUBBLES]
# thyroid
TSH_RANGE_MIU_L = (0.4, 4.0)              # used only when the lab entry has no reference range of its own          [LIT]
TSH_TALK_MIU_L = (0.1, 10.0)              # outside this = talk to a doctor                                         [LIT/BUBBLES]
ORGAN_LAB_STALE_DAYS = 365                # an older lab lowers confidence                                          [BUBBLES]
