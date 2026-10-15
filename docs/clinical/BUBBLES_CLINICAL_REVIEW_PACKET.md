# Bubbles — Clinical Review Packet

**For:** a licensed doctor, a registered dietitian / nutritionist, and a pharmacist
**From:** the Bubbles product team
**Status of everything below:** **PENDING CLINICIAN REVIEW — proposals, not medical advice**
**Where the numbers live in code:** `backend/clinical_constants.py` (one file; a change you request is a one-line edit)

---

## 1. What Bubbles is, and what we are asking you to check

Bubbles is a chat-first personal health companion. It is **not** a diagnostic tool and never replaces a clinician.
We are adding a **Fitness** section (diet planner, exercise planner, calorie calculator) and a **Strict
Transformation mode** that joins the three to move a user toward a target weight, plus a much deeper
**Menstrual cycle** section, richer sleep, hydration, medication and mind trackers.

Because these features touch eating, exercise and medication, **no user should reach Strict Transformation mode
until a clinician has signed off the sections below** (the app shows "pending clinician review" on every plan
until the owner flips the review flag). Please mark each item **Approve / Change to ___ / Reject** and add comments.

Bubbles does **not** diagnose, prescribe, recommend supplements, or advise medication dose changes. Anything that
looks like a symptom or condition is routed to a deterministic safety check first, and the user is told to see a
clinician. All estimates are shown as ranges.

How to read the "source" column: **WHO / CDC / NHS / ACOG** = public guidance we believe matches the value;
**LIT** = widely used published formula or convention; **BUBBLES** = our own design choice that needs your agreement.
*We could not verify every figure against its primary source while drafting; please treat the "source" column as
"where we believe this comes from", not as a citation.*

---

## 2. Energy and weight-change numbers

| # | Constant (code name) | Proposed value | Source | Why / how it is used | Your decision |
|---|---|---|---|---|---|
| 2.1 | `MIFFLIN_*` Mifflin-St Jeor resting energy | `10·kg + 6.25·cm − 5·age + 5` (male basis) or `− 161` (female basis); **“average” basis uses −78** | LIT | Starting estimate of resting energy. Users pick the formula basis (we do not assume from sex or gender). | |
| 2.2 | `ACTIVITY_FACTORS` | 1.2 / 1.375 / 1.55 / 1.725 / 1.9 | LIT | Multiplies resting energy to estimate daily energy use (TDEE). | |
| 2.3 | `PACE_PCT_PER_WEEK` | planned loss **0.25 – 0.75 %** of body weight per week | BUBBLES | Default pace we propose. | |
| 2.4 | `HARD_CAP_KG_PER_WEEK`, `HARD_CAP_PCT_PER_WEEK` | **never faster than 1.0 kg/week and never > 1 % of body weight/week** | CDC | Hard ceiling; engine will not plan or accept more. | |
| 2.5 | `MAX_DEFICIT_PCT_OF_TDEE`, `MAX_DEFICIT_KCAL` | deficit **≤ 25 % of TDEE and ≤ 1000 kcal/day** | BUBBLES | Limits how aggressive the calorie target can be. | |
| 2.6 | `INTAKE_FLOOR_KCAL` | **female basis 1200, male basis 1500, average basis 1350** kcal/day; absolute floor 1200 | LIT | Bubbles never outputs a calorie target below this for any input (fuzz-tested). | |
| 2.7 | `KCAL_PER_KG_RANGE` | 6500 – 7700 kcal per kg of body mass | LIT/BUBBLES | Only used to show a **time-to-goal range**, never a single date. | |
| 2.8 | `MAX_SURPLUS_KCAL`, `MAX_GAIN_KG_PER_WEEK` | gain goals: ≤ +500 kcal/day, ≤ 0.5 kg/week | BUBBLES | For underweight/gain goals (gentle plan only). | |
| 2.9 | `EXERCISE_CALORIE_CREDIT` | only **50 %** of estimated exercise burn is added back to the food budget | BUBBLES | Wearable/MET burn estimates are noisy; this avoids over-eating *or* under-eating. | |
| 2.10 | `KCAL` weekly changes | the weekly check-in moves the calorie target by **at most 150 kcal** | BUBBLES | Prevents swings from noisy weight data. | |

**Questions for the dietitian**
1. Is a 1200 / 1500 kcal floor acceptable for an unsupervised consumer app, or should it be higher (e.g. never below estimated resting energy)?
2. Should the floor differ for very short, older, or very active people?
3. Should we require the user to be above a minimum BMI **to start a deficit** (we propose ≥ 18.5; Indian users may prefer the Asian BMI cut-offs, see 3.1)?
4. Is 25 % / 1000 kcal the right deficit ceiling? Is the “7700 kcal/kg” rule acceptable if shown only as a range?

---

## 3. BMI, targets and body composition

| # | Constant | Value | Source | Note | Decision |
|---|---|---|---|---|---|
| 3.1 | `BMI_UNDERWEIGHT/OVERWEIGHT/OBESE`, `BMI_ASIAN_*` | 18.5 / 25 / 30 (WHO); **Asian cut-offs 23 / 27.5** | WHO | We show both and caveat that BMI ignores muscle, age, sex and ethnicity. | |
| 3.2 | `MIN_TARGET_BMI` | **a target weight below BMI 18.5 is refused** | WHO/BUBBLES | | |
| 3.3 | `MIN_START_BMI_FOR_LOSS` | a weight-**loss** plan from BMI < 18.5 is refused | BUBBLES | | |
| 3.4 | Input sanity ranges `MIN_PLAUSIBLE` | height 120–230 cm, weight 30–300 kg, age 13–100 | BUBBLES | Prevents nonsense calculations. | |

---

## 4. Macros and nutrients

| # | Constant | Value | Source | Note | Decision |
|---|---|---|---|---|---|
| 4.1 | `PROTEIN_G_PER_KG` (+ `PROTEIN_G_PER_KG_TRAINING`) | **1.2 – 2.0 g/kg** (default **1.4** with resistance training, **1.2** without) of reference weight (up to 2.2 with resistance training in a deficit) | LIT | Reference weight for BMI ≥ 30 = ideal + 25 % of the excess (`OBESE_REFERENCE_WEIGHT_WEIGHT`). | |
| 4.2 | `PROTEIN_G_PER_KG_KIDNEY_NOTE` | users who record kidney disease get **no high-protein target**, only a clinician note | BUBBLES | Strict mode is also blocked for them. | |
| 4.3 | `FAT_MIN_PCT_KCAL`, `FAT_MAX_PCT_KCAL` | 20 % – 35 % of energy | LIT | | |
| 4.4 | `FIBRE_G_PER_DAY` | 25 – 30 g | LIT | | |
| 4.5 | `SODIUM_LIMIT_MG` | < 2000 mg sodium (< 5 g salt) per day | WHO | Hypertension users get a stricter note, no number change by us. | |
| 4.6 | `ADDED_SUGAR_PCT_KCAL` | < 10 % of energy from free sugars | WHO | | |
| 4.7 | Micronutrient attention list | iron, calcium, vitamin B12, vitamin D, folate | BUBBLES | We **show gaps and suggest foods only**. We never advise supplements or doses. | |

**Question:** Are the vitamin/mineral “attention” nutrients right for vegetarian/vegan Indian diets and for menstruating users (iron, B12, folate)? Anything missing (iodine, zinc, omega-3)?

---

## 5. Exercise

| # | Constant | Value | Source | Decision |
|---|---|---|---|---|
| 5.1 | `WHO_MODERATE_MIN_PER_WEEK` / `WHO_VIGOROUS_MIN_PER_WEEK` | 150–300 min moderate **or** 75–150 min vigorous per week | WHO | |
| 5.2 | `WHO_STRENGTH_DAYS_MIN` | muscle-strengthening on ≥ 2 days/week | WHO | |
| 5.3 | `MAX_WEEKLY_VOLUME_INCREASE` | ≤ ~10 % more volume than last week | LIT/BUBBLES | |
| 5.4 | `DELOAD_EVERY_WEEKS` | a lighter week every 5th week | BUBBLES | |
| 5.5 | `MET_VALUES` | table of activity MET values (walking 2.8–6.0, running 9.8, yoga 2.8, etc.) | LIT (Compendium of Physical Activities) | Used for **estimated** calories burned only. Please review the table. |
| 5.6 | `RPE_TARGET_MODERATE` | effort 3–6 on a 0–10 scale | LIT | |

### 5.7 Pre-participation screening (our wording, in the spirit of the free PAR-Q+)

Asked before any exercise plan. A **yes to any of the first five** → the app says *talk to a clinician before
starting*, and offers only easy walking and gentle mobility until the user says they have been cleared.

1. Heart condition, or told to only exercise on a doctor's advice? *(blocking)*
2. Chest pain with activity or at rest? *(blocking)*
3. Dizziness causing loss of balance, or loss of consciousness in the last 12 months? *(blocking)*
4. High blood pressure that is not controlled? *(blocking)*
5. Unusual breathlessness with light activity? *(blocking)*
6. Bone or joint problem that could worsen? *(adapts the plan)*
7. Taking medicine for blood pressure, heart, diabetes or breathing? *(adds a note)*
8. Pregnant or within 6 weeks of birth? *(pregnancy/postpartum plan only)*
9. Any other reason not to be more active? *(clinician note)*

**Question for the doctor:** Is this screen adequate? Should any “adapts the plan” question be blocking?

### 5.8 Condition-specific exercise adaptations we propose (please correct)

| Condition | What the plan does |
|---|---|
| Hypertension | no heavy straining/Valsalva moves, moderate cardio, longer warm-up |
| Type 2 diabetes | regular timing, carry fast sugar, avoid very long fasted sessions |
| Asthma / COPD | warm-up, longer intervals, no forced cold-air intensity |
| Knee / back / joint issues | low-impact options (cycling, swimming, chair/band work), no jumping/deep loaded flexion |
| Osteoporosis | weight-bearing + balance, no loaded spinal flexion/twisting |
| PCOS | strength training emphasis + moderate cardio |
| Pregnancy / postpartum | WHO pregnancy guidance only; no strict mode; no supine-heavy or contact moves |
| Obesity (BMI ≥ 30) | low-impact start, shorter bouts, gradual build |

---

## 6. Strict Transformation mode

Strict mode combines the diet planner + exercise planner + calorie log into one plan toward a target weight.
It is **off for everyone unless every rule below passes**.

### 6.1 Hard exclusions — strict mode is refused (user is offered a gentle plan or told to see a clinician)

| # | Rule | Decision |
|---|---|---|
| 1 | Age under 18 | |
| 2 | Pregnant, breastfeeding, or actively trying to conceive | |
| 3 | Positive eating-disorder screen (SCOFF ≥ 2) **or** any eating-disorder history the user records | |
| 4 | Target BMI < 18.5, or starting BMI < 18.5 for a weight-loss goal | |
| 5 | Type 1 diabetes; or insulin / sulfonylurea use — unless the user confirms a clinician has approved the plan | |
| 6 | Kidney disease (advanced), heart disease, uncontrolled hypertension, liver cirrhosis, cancer treatment — unless a clinician has approved | |
| 7 | Missed periods for ≥ 3 months not explained by pregnancy (possible low energy availability) | |
| 8 | Recent surgery or an active injury — unless cleared | |
| 9 | Any red-flag symptom reported in the last 14 days | |
| 10 | Age ≥ 70 without a clinician acknowledgement | |
| 11 | Warfarin/acenocoumarol (steady vitamin-K intake matters) or lithium (salt/fluid shifts) — unless approved | |

**Condition keyword lists** (what text counts as each condition) are in `STRICT_BLOCKING_CONDITIONS` and
`STRICT_BLOCKING_MEDICATIONS` in `clinical_constants.py`. *Please review the wording lists — they are matched
against free text the user entered.*

### 6.2 Soft cautions (allowed, but the plan adapts and a clinician note is shown)

Age > 60; type 2 diabetes / prediabetes / insulin resistance (carbohydrate spread, low-GI emphasis, hypoglycaemia
awareness); hypertension (sodium note); PCOS (low-GI, strength training); thyroid conditions; anaemia (iron-rich
foods + vitamin C pairing, no supplement advice); asthma; joint issues; osteoporosis; GERD; IBS/coeliac/IBD;
gout; endometriosis; depression/anxiety; high cholesterol; GLP-1 medicine use (protein and fluids emphasised,
**Bubbles never suggests dose changes**); perimenopause (protein, strength, calcium and vitamin D foods).

### 6.3 What the always-on safety monitors do (`transformation` module)

| Trigger | Response | Constant |
|---|---|---|
| Logged intake under the floor on ≥ 3 of 7 days | pause strict mode, raise targets to the floor, gentle check-in | `SAFETY_LOW_INTAKE_DAYS_OF_7` |
| Weight trend falling faster than 1.2 kg/week for 2 weeks | pause and soften | `SAFETY_RAPID_LOSS_*` |
| Regain > 2 kg in a week | gentle check-in (could be water/cycle), no punishment | `SAFETY_REGAIN_KG_IN_WEEK` |
| Very low intake **and** > 420 min/week exercise | pause, recommend a clinician (relative energy deficiency risk) | `SAFETY_HIGH_EXERCISE_MIN_PER_WEEK` |
| Missed period ≥ 3 months | pause, recommend a clinician | `SAFETY_MISSED_PERIOD_MONTHS` |
| Dizziness / fainting / chest pain / palpitations in chat | deterministic emergency/urgent safety response first | existing safety engine |
| Language such as “starve myself”, “punish”, “purge”, “can't stop thinking about food” | pause, supportive message, point to professional help | restriction-language check |
| Day-to-day intake swing > 1500 kcal repeatedly | gentle check-in about restricting/bingeing patterns | `SAFETY_BINGE_RESTRICT_SWING_KCAL` |

Bubbles never uses guilt or shame language; “off-plan” days are treated as normal.

### 6.4 Weekly adaptive check-in

* Weight trend: exponentially weighted moving average, factor `TREND_SMOOTHING_ALPHA = 0.1`.
* Needs ≥ 4 food-logged days and ≥ 3 weigh-ins in the week to adjust anything.
* After ≥ 2 weeks, real energy expenditure is estimated from average intake and the trend; the calorie target moves at most 150 kcal and never below the floor.
* Plateau = trend change below 0.1 %/week for 3 weeks → options (diet break, add steps, review logging). After 12 weeks of dieting the app suggests a 1–2 week maintenance break.
* For users with cycles the trend is read with menstrual-cycle water retention in mind (no “failure” message for a luteal-phase uptick).
* Finishing: gradual return to maintenance by +100 kcal/week.

**Questions:** Is the pause logic safe and sensible? Anything you would add (e.g. blood-pressure or glucose logging prompts, mandatory medical check-in interval)? Should a clinician acknowledgement expire after N months?

### 6.5 What Bubbles says in chat (please review the wording)

* **Restriction / disordered-eating language** (for example "starve myself", "make myself throw up", "can't stop thinking about food", "skip all my meals") gets a fixed, kind reply: it pauses an active strict plan, encourages a doctor, counsellor or trusted person, and gives an emergency / crisis-line reminder. No numbers or tips follow. The phrase list is in `transformation.py` (`_RESTRICT`); please add or remove phrases.
* **A request to eat below the floor** (for example "I want to eat 800 calories") is declined: Bubbles says it cannot plan below about 1200-1500 kcal, explains why in plain words, says very-low-calorie diets need medical supervision, and offers a steady plan instead.
* **Plan questions** ("how many calories should I eat?", "what's my workout?") are answered from the saved plan with the word *estimate* and, until you sign off, the pending-review notice. Chat never changes a plan; it points to the screen where the user confirms a change.
* **Data rights:** a user can export all Fitness / Cycle / plan data and delete it all (`/me/whole-health/export`, `/me/whole-health/data?confirm=true`).

---

## 7. Hydration

| Constant | Value | Source | Decision |
|---|---|---|---|
| `HYDRATION_ML_PER_KG` | 33 ml per kg body weight per day (from drinks), a rough baseline | LIT | |
| `HYDRATION_ML_PER_EXERCISE_MIN` | + 10 ml per minute of moderate exercise | BUBBLES | |
| Pregnancy / breastfeeding additions | + 300 ml / + 700 ml | LIT | |
| Min / max suggestion | 1500 ml / 4000 ml | BUBBLES | |
| Single drink cap | a logged drink > 2000 ml is rejected as a typo | BUBBLES | |
| Beverage factors | water 1.0, tea 0.9, coffee 0.8, milk 0.9, juice 0.85, buttermilk 0.95, coconut water 0.95, soda 0.8, alcohol 0 | LIT/BUBBLES | |
| Fluid-restricted conditions | heart failure, kidney disease/dialysis, cirrhosis, SIADH, hyponatraemia → **no target is shown**, only a clinician note | BUBBLES | |

---

## 8. Sleep

Adult 7–9 h, teen 8–10 h, older adults and children have their own bands (`SLEEP_HOURS_OLDER`, `SLEEP_HOURS_CHILD`, `SLEEP_GOAL_BOUNDS_H` in `clinical_constants.py` — please confirm these too); “consistent” = bedtime/wake variation ≤ 30 min; sleep debt = shortfall against the
user's own goal over 7 days. No audio recording. No claim to detect sleep disorders; persistent problems → see a clinician.

---

## 9. Menstrual-cycle section (flags — Bubbles never diagnoses)

| # | Rule | Value | Source | Decision |
|---|---|---|---|---|
| 9.1 | Typical cycle length shown as normal | 21–35 days (adults), 21–45 (teens) | ACOG | |
| 9.2 | Suggest a clinician when a cycle is | < 21 or > 35 days | ACOG | |
| 9.3 | Bleeding longer than | 7 days | ACOG | |
| 9.4 | Soaking a pad/tampon **every hour for 2+ hours** | prompt for urgent care | ACOG | |
| 9.5 | Missed periods | ≥ 3 in a row (and not pregnant / menopausal) | ACOG | |
| 9.6 | Bleeding after 12 months without a period | prompt for clinician | NHS | |
| 9.7 | Severe pain, bleeding between periods, sudden big change | prompt for clinician (severe → safety engine) | BUBBLES | |
| 9.8 | Ovulation estimate | ~14 days before the next period (range 10–16); fertile window = 5 days before + day of ovulation | LIT | |
| 9.9 | Temperature shift detection | 3 consecutive days ≥ 0.2 °C above the previous 6 | LIT | |
| 9.10 | Predictions | weighted recent cycles (decay 0.8), window widens with variability; labelled “learning” until 3 cycles; irregular mode when SD > 4 days | BUBBLES | |

**Further cycle constants to review** (all in `clinical_constants.py`, cycle section): `CYCLE_DEFAULT_LENGTH_DAYS`, `CYCLE_LEARNING_HALF_WINDOW_DAYS`, `CYCLE_WINDOW_SD_MULTIPLIER`, `CYCLE_WINDOW_HALF_DAYS`, `CYCLE_HIGH_CONFIDENCE`, `PERIOD_MERGE_WITHIN_DAYS`, `PERIOD_DEFAULT_LENGTH_DAYS`, `PERIOD_MAX_PLAUSIBLE_DAYS`, `MISSED_PERIOD_GRACE_DAYS`, `SEVERE_PAIN_LEVEL`, `CYCLE_SUDDEN_CHANGE_DAYS`, `POSTPARTUM_LOCHIA_DAYS`, `PREGNANCY_DAYS`, `BBT_VALID_C`, `LH_OVULATION_AFTER_POSITIVE_DAYS`, `INSIGHT_MIN_CYCLES`, `INSIGHT_MIN_POINTS_PER_PHASE`, `INSIGHT_MIN_DIFFERENCE_FRACTION`. Also please review the **education articles** (18) and the **pregnancy week notes** (42) in `backend/cycle_content.py`, the 156 symptom/factor chips, and the Bubbles "inner weather" one-liners. Notes: the postpartum mode ignores bleeding for the first 42 days; the "3-over-6" temperature rule here is deliberately stricter than the common version; the fertile-window range is wider than the single 14-day luteal estimate.

**Not offered:** contraception claims, “safe days”, pregnancy diagnosis, or any claim that a fertile-window estimate
prevents pregnancy. Copy states plainly that predictions are estimates and are not a method of birth control.

**Questions for the doctor / gynaecologist:** Are the flag thresholds right? Postpartum, post-pill and perimenopause
wording? PCOS/endometriosis/PMDD tracking templates (symptom lists) — anything missing or misleading?

---

## 10. Medications

Bubbles stores what the user enters; **it never changes a dose, never says to stop a medicine, never recommends a drug**.

* **Interaction warnings** use a short curated list (below) plus an optional online lookup of NIH RxNav. They are
  warnings to “check with your pharmacist”, never prohibitions.
* **Pharmacist: please review each pair** (and tell us which to drop):

| Pair | Concern | Level |
|---|---|---|
| warfarin + NSAIDs (ibuprofen, diclofenac, naproxen) or aspirin | bleeding | high |
| NSAID + SSRI/SNRI | bleeding, stomach | moderate |
| ACE inhibitor / ARB + potassium supplements or spironolactone | high potassium | high |
| ACE inhibitor / ARB + NSAID | kidney strain, less BP effect | moderate |
| SSRI + tramadol / triptan / linezolid / St John's wort | serotonin syndrome | high |
| nitrate + sildenafil / tadalafil | severe low BP | high |
| statin (simvastatin) + clarithromycin / grapefruit | muscle toxicity | high |
| levothyroxine + calcium / iron / antacid | absorption — separate by 4 h | timing |
| tetracycline / doxycycline / ciprofloxacin + dairy / calcium / iron / antacid | absorption — separate | timing |
| metformin + heavy alcohol | lactic acidosis risk | moderate |
| methotrexate + NSAID / trimethoprim | toxicity | high |
| digoxin + diuretics (low potassium) | digoxin toxicity | high |
| insulin / sulfonylurea + alcohol / big calorie cuts | low blood sugar | high |
| lithium + NSAID / ACE inhibitor / diuretic | lithium toxicity | high |
| combined hormonal contraceptive + rifampicin / some anti-epileptics / St John's wort | contraceptive less effective | high |

* **GLP-1 tracker:** dose-day reminders, injection-site rotation, appetite/nausea log, protein and fluid prompts.
  Bubbles never suggests dose changes and states that a prescriber decides.
* **Strict mode and medicines:** insulin/sulfonylurea, anticoagulants and lithium block strict mode unless the user
  confirms a clinician approved the plan.

---

## 11. Mind (mood) check-ins

PHQ-2 and GAD-2 style questions are used as a **gentle check-in**, not a diagnosis: a score ≥ 3 shows kind wording
and suggests speaking with a professional. Any self-harm language goes straight to the existing emergency safety
response with crisis resources. Please confirm wording and thresholds.

---

## 12. Food data

Calorie and nutrient values are **reference estimates** compiled from typical published values (IFCT 2017, USDA
FoodData Central, Open Food Facts). Every row is tagged with its source and `verified: false` until a dietitian
confirms it. Portions use Indian household units (katori, roti, ladle, glass, piece, tsp/tbsp). Values are shown as
ranges when uncertain. **Dietitian: please check the most-used staples first (roti, rice, dal, idli, dosa, paneer,
chicken curry, biryani, poha, upma, curd, milk, tea) and the oil/ghee adjustment defaults.**

---

## 13. Language and disclaimers shown to users

* “Estimates, not medical advice. Talk to a doctor or dietitian before big changes.”
* Never “you will lose X kg by date”; always “typically between A and B”.
* Never shaming, never calorie-counting “red numbers”, never moralising food as good/bad.
* Never recommends supplements, drugs or doses. Never diagnoses.
* Please review the **commit screen** text in `docs/plans/whole-health-os.md` §7.

---

## 13b. Other limits in the code (please confirm)

`EXERCISE_CREDIT_MAX_KCAL` (at most 300 kcal of exercise added back per day), `SAFETY_COOLDOWN_DAYS` (7-day wait after a safety pause),
`EATING_SCREEN_STICKY_DAYS` (a positive eating screen keeps weight-loss numbers off for 30 days), `CHECKIN_MIN_DAYS_BETWEEN` (6),
`CLEARANCE_VALID_DAYS` (a recorded clinician go-ahead lasts 365 days and must name what it covers), `STEPS_BY_ACTIVITY` (6000-10000 steps),
and the wellness constants at the end of `clinical_constants.py` (sleep score weights and bands, hydration presets and reminder cadence,
medication dose windows and refill alerts, mind check-in thresholds, notification caps and quiet hours). The Cycle section's pregnancy,
trying-to-conceive and postpartum modes also switch off any calorie deficit.

## 13c. Eyes and the body map (added 2026-10-15; awaiting sign-off)

Bubbles now tracks the eyes (Track > Eyes, the "eyes" body system, chat understanding). Nothing here diagnoses; please confirm or correct each rule.

* **Eye tracker (what a person logs):** screen time today (0-18 h), eye comfort (1 = very uncomfortable to 5 = very comfortable), symptom chips
  (dry, itchy, red, strained, blurry, watery, headache), glasses yes/no, break count, date of the last eye exam. Stored as the person's own record.
* **Eyes body-system signals (`organ_tracker.RISK_FACTORS`, product weights, not odds ratios):** high screen time = average of at least **6 h/day**
  over at least 3 logged days in the last 14 (weight 0.14); frequent eye symptoms = eye symptoms or comfort of 2 or less on at least **3 different days
  in the last 14** (weight 0.16); persistent high blood glucose 0.14; persistent high blood pressure 0.12; smoking 0.06. Status bands are the existing
  ones (0.25 = "watch", 0.45 = "needs attention"). Both 6 h and 3 days are product choices, not clinical cut-offs. A recorded exam date is **not** counted as
  evidence about the eyes. Please confirm the thresholds or give better ones.
* **Wording shown with the eyes system:** "Short screen breaks, such as looking at something about 6 metres away for 20 seconds every 20 minutes, are a common
  habit for tired eyes. If symptoms keep coming back, an eye check is worth considering." (the 20-20-20 habit has limited trial evidence; we say "common habit".)
  With high BP or glucose: "High blood pressure and high blood sugar can affect the eyes, so it is worth asking your doctor how often you should have an eye exam."
  (The ADA advises a dilated eye exam at type 2 diabetes diagnosis, within 5 years for type 1, then at least yearly, or every 1-2 years after clean exams. Bubbles
  does not state an interval; please say whether it should.)
* **Chat symptom words (`health_semantics`):** eye strain (tired, burning, heavy), dry eyes, red eyes (incl. pink eye / conjunctivitis), eye pain, itchy or watery
  eyes, with Hinglish spellings (aankh / aankhen / aankhon: jalan, dard, lal, khujli, sookhi, thakan). **Severe eye pain** (the word "severe" or 8/10 or more) now
  joins the existing "severe pain" rule and gives the urgent (AMBER) response. Mild or ordinary eye discomfort does not escalate. Please confirm severe eye pain
  should be urgent.
* **Sudden loss of sight (RED, existing rule extended):** the stroke-warning pattern already caught "sudden loss of vision". It now also catches everyday wordings when
  a "sudden" cue is present: "I suddenly can't see out of my left eye", "all of a sudden I cannot see anything", "I suddenly lost my vision", "a curtain fell over my vision",
  "suddenly went blind". Known gaps (please advise): "a curtain **came / is coming down** over my vision" is read as a resolved symptom ("came down" is on the existing
  resolution list); Hinglish "bahut tez" (very severe) is not read as a severity word for eye pain, so Hinglish severe eye pain does not escalate yet.
* **Patterns:** two new links are checked: screen time with eye comfort (same day), and screen time with the next night's sleep rating. They are worded as associations only.

### 13c-2. Ears, mouth, thyroid, bladder, skin and breasts (added 2026-10-15; awaiting sign-off)

The body map now has 16 systems. For ears, mouth, bladder, skin and breasts the only signal is **the person's own symptom days: 3 or more different days in the last 14**
(weight 0.16, a product threshold, not a clinical cut-off), with the advice line "These symptoms keep coming back in your logs. If they continue, it is worth mentioning to a
clinician." The mouth also counts chewed tobacco (0.16), smoking (0.10) and alcohol excess (0.06) and says "a regular dental and oral check is worth asking your dentist or doctor
about". High blood glucose adds 0.08 to the bladder. The thyroid has **no** symptom signals (only results: TSH, T3, T4, a diagnosis). A dentist visit, hearing test, mammogram or
exam **date** is never counted as evidence about the organ. Breasts are shown only for the female body map (or if the person chooses it).

New chat words (English and Hinglish): ear pain, ringing in the ears, hearing loss, toothache, mouth ulcers, bleeding gums, burning when urinating, frequent urination, breast pain.
**Two are "urgent" (the existing AMBER tier: prompt assessment, not an emergency call):**
* **Sudden hearing loss** ("sudden hearing loss", "I suddenly lost my hearing in one ear", "my hearing suddenly dropped overnight").
* **A new breast lump** ("I found a lump in my breast", "a hard lump on my left breast", "breast lump"). Past, denied and other-person mentions do not escalate.
Please confirm both should be urgent, or tell us the right tier. Known gaps: "hearing loss in my grandfather" is read as the speaker's own (the existing other-person detection
does not cover "X in my <relative>"); Hinglish for a breast lump (gaanth) is included but untested by a native speaker.

## 14. Sign-off

| Role | Name | Registration no. | Sections reviewed | Date | Signature |
|---|---|---|---|---|---|
| Medical doctor | | | | | |
| Registered dietitian | | | | | |
| Pharmacist | | | | | |
| Gynaecologist (section 9) | | | | | |

**Release rule:** the owner sets `BUBBLES_CLINICALLY_REVIEWED=true` in `backend/.env` only after this table is signed and any
requested changes are made in `clinical_constants.py`. Until then every plan carries the "pending clinician review" banner.
