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

## 13e. The Eyes area on the body map (added 2026-10-15; awaiting sign-off)

The body map has an **Eyes** area (two eyes drawn in the 3D model; illustrative, not anatomy from a scan). It reads the Eyes tracker and chat words, the same way the "eyes" body system in 13c does. Same product thresholds, over the last **14 days**:

* screen time averaging **6 h or more** a day on **3 or more logged days** = worth watching (an average over fewer days says nothing);
* eye symptoms (chips or chat words) or eye comfort of **2 or less (of 5)** on **3 or more different days** = worth watching;
* a severe-pain or sudden-sight-loss message goes through the safety engine again and makes the area "talk to a doctor", with the safety message first (same rule as chat);
* a recorded eye-exam date is shown as a note only, never as evidence about the eyes; no entries is "no data", never "steady". The "headache" chip is not read as an eye symptom.
* Wording shown: "Short breaks help tired eyes: look at something about 6 metres away for 20 seconds every 20 minutes. If it keeps coming back, an eye check is worth it." Please confirm or correct the thresholds and the wording.

## 13d. First-run setup suggestions (added 2026-10-15; awaiting sign-off)

The setup builds a short Care checklist from what a person says. Each item is worded as "worth asking your doctor", never as an order or a finding. Please confirm the ages and wording.
* **Blood pressure and sugar check** from age **30** when the last check was over a year ago or unknown (follows India's national NCD screening programme, which targets adults 30 and over).
* **Cervical screening** for women aged **30 to 65** who answer longer ago, never or not sure.
* **Eye exam for diabetes** when someone says they have diabetes and the last eye exam was not in the last year (ADA: dilated exam at diagnosis, then regularly, often yearly). Bubbles states no interval.
* **An eye check** when daily screen time is 6 h or more and the last exam was long ago or unknown (6 h is a product choice).
* **A dental and oral check** for people who smoke or chew tobacco.
* **Night-time urination or weaker flow** (male, age 45 and over, answered yes): "worth mentioning at your next visit".
* Alcohol: the three drinking questions follow the AUDIT-C items (frequency, usual amount, six or more drinks). The answers are stored but **no score or label is shown**.
* Mood: the first-run mood check re-uses the existing PHQ-2 / GAD-2 screens (score only, supportive wording, no label).
* Under 18: nothing is stored and no health content is shown (the Terms already say 18 and over).
* Cycle mode from setup: not now + pregnant = pregnancy; recently gave birth or breastfeeding = postpartum; contraception stops periods = birth control; menopause = perimenopause; trying to conceive = conceive. Pregnancy, postpartum and "avoid weight or calories" switch off calorie deficits in Fitness.

## 14. Sign-off

| Role | Name | Registration no. | Sections reviewed | Date | Signature |
|---|---|---|---|---|---|
| Medical doctor | | | | | |
| Registered dietitian | | | | | |
| Pharmacist | | | | | |
| Gynaecologist (section 9) | | | | | |

**Release rule:** the owner sets `BUBBLES_CLINICALLY_REVIEWED=true` in `backend/.env` only after this table is signed and any
requested changes are made in `clinical_constants.py`. Until then every plan carries the "pending clinician review" banner.

## Draft addition (2026-10): passive-ideation phrases

Added to the `suicidal_ideation` pattern in `backend/health_semantics.py`, all treated as crisis language (the deterministic crisis reply, nothing stored):
"burden to everyone / my family / my friends", "nobody would miss me", "everyone would be better off without me", "I am / I feel worthless", and Hinglish "marna chahta/chahti hun", "jeena nahi chahta/chahti", "jeene ka mann nahi", "main bojh hun", "koi miss nahi karega".
Near-misses that must stay quiet are covered by tests (for example "my worthless ex", "a burden on the team"). Clinician sign-off needed on the list and on whether "worthless" alone should escalate.

## Mega task additions (2026-10, awaiting clinician sign-off)

# L1 clinical packet draft

For the lead to add as new numbered section(s) in `docs/clinical/BUBBLES_CLINICAL_REVIEW_PACKET.md`. Nothing here adds a symptom word or a threshold
to the safety engine. These are rules about how replies are phrased and what history the model is shown.

## Resumed-chat age limit (48 hours)

- Rule: when a chat is resumed, what the person said in earlier messages is treated as history once it is more than **48 hours** old
  (`HISTORY_NOW_HOURS = 48` in `chat_pipeline.py`). Those turns are shown to the model labelled "earlier, N days ago, not necessarily true now";
  symptoms they reported are listed as past or resolved (never "reported now or recently"); an old denial ("no chest pain") and an old
  "maybe" are dropped from the standing state, so they cannot be read as true today.
- Why: a person who opens the latest chat days later should not be told about a headache from last week as if it were today, and should not be
  reassured by a denial that was true then. Missing is unknown, never "all clear".
- Safety effect: none on the alarm. The safety engine reads only the current message; this rule only changes the background the model sees and
  the contradiction check against old statements.
- Needs clinician review: whether 48 hours is the right cut-off (it is a deliberate default), and whether an old denial of a red-flag symptom
  should instead be kept as "denied earlier" rather than dropped.

## Reply wording rules (friend voice)

- No organisation, guideline, study or source name in reply prose (NHS, WHO, CDC, NICE, NIH, ICMR, AHA, ADA, MedlinePlus, Mayo, "guidelines say",
  "studies show", "according to"). Enforced in the prompt and, for AI text only, by `strip_attribution` and the `authority_citation` lint code.
  Reading links under a reply remain the only place sources appear.
- Soft, not scary: lead with what is common; never a list of scary possibilities; say a pattern gently and leave the decision to the person; never
  a verdict about their body (`heavy_verdict` lint: "this means you have", "you are suffering from", "it is probably cancer/diabetes/tumour/heart disease").
- Warn without alarm: name the one or two specific signs that mean "get checked" in calm concrete words.
- URGENT replies: the softness is dropped, and if the model's text does not already say today, doctor, clinician, urgent care or emergency, the fixed
  line "Please speak to a clinician or an urgent-care service today." is appended. The fixed safety texts on the freeze list are unchanged (hash-tested).
- Length: about 60 to 90 words by default, up to about 120 for a symptom question, about 160 for people who asked for fuller answers (was 250).
- Care checklist copy (first-run setup, not yet shown) now says "Worth asking your doctor..." and no longer names a programme or society.

## What the new batch confirmation does with a person's decision (data handling)

- Saving a detail promotes it to memory by the existing promotion rules (live, present, first-person observations only, L2 types need the person's yes).
  Dismissing keeps nothing. A detail the person dismissed can still not be saved later if it was withdrawn by a correction (409).

## 15. Mind: loneliness, anxiety, separation anxiety (added 2026-10-16; awaiting sign-off)

Draft from lane L3, for the lead to fold in as the next numbered section. Nothing here diagnoses, labels or advises a medicine. Every item needs clinician sign-off; the Hinglish items also need a native-speaker check (add to HINGLISH_SAFETY_TERMS_REVIEW.md).

### 15.1 Passive-ideation wording (the safety path: crisis reply 112 / Tele-MANAS 14416, nothing stored)
Each pattern needs a first-person feeling or being cue. English (`health_semantics._LEX_SRC`, `suicidal_ideation`, second list):
- "I am / I'm / I feel / I feel like / I have become ... (such a / a / nothing but a) burden" ("I feel like a burden to everyone", "I've become a burden")
- "no one / nobody would (even) miss me"
- "no one / nobody would (even) notice / care / know (if / when) I was / am / died / disappeared / am gone"
- "I am / I feel / feeling (so, really, completely...) worthless"
Must stay quiet (tested): "I don't want to be a burden" (a wish), "he called me worthless", "I'm not worthless", "I used to feel worthless years ago", "my friend feels worthless", "this phone is worthless", "nobody would miss that show", "burden of proof", "What does it mean to feel worthless?".
Hinglish (`hinglish_terms.py`): "main sabke liye bojh hoon", "mere jaane se kisi ko farak nahi padega", "koi meri kami mehsoos nahi karega", "main kisi kaam ka nahi hoon", "meri koi value nahi hai", "main worthless / useless feel karta hoon", "main bilkul bekaar hoon". Near-misses kept quiet: "mujhe nahi lagta main bojh hoon", "kisi kaam ka nahi hai ye phone", "main bekaar hoon yaar cooking mein".
Open question for the reviewer: "main kisi kaam ka nahi hoon" and "main bilkul bekaar hoon" can be said in frustration; they are treated as crisis wording on purpose (the reply is caring and nothing is lost). Say if they should be softened to a clarification.

### 15.2 Ordinary concepts (never escalate alone; a self report that is current, recent or recurring)
- `loneliness`: lonely / lonesome, "I feel (so) alone", "nobody to talk to / nobody talks to me", "I have no friends", "feel isolated / left out / cut off / unwanted"; Hinglish: akela / akeli / akelapan / tanha / tanhai with lagta / lagti / feel, "koi dost nahi", "koi baat karne wala nahi".
- `panic_attack` (child of `anxiety`): panic / panic attack / panicky, "can't calm down".
- `separation_anxiety` (child of `anxiety`): "separation anxiety", homesick, "anxious / scared when I'm apart / away", "can't bear being apart", "miss my mom so much"; Hinglish: "mummy ki bahut yaad aa rahi hai", "door rehna nahi ho pata".
- `anxiety` (parent) gains the Hinglish ghabrahat / ghabra* / bechain* and "mujhe chinta / fikr / tension hai".
Quiet by test: "I live alone and I like it", "leave me alone", "I'm not lonely", "Lonely Planet", "don't panic", other people's panic or loneliness, "I miss the bus".
All four map to the brain area on the body map. No concept alone changes a safety state.

### 15.3 Quick scores (no sum, no label, no diagnosis; a score is stored, never free text)
- Loneliness: one question, "How often do you feel lonely?", answers 1 Never, 2 Rarely, 3 Sometimes, 4 Often, 5 Almost always. Offer-to-talk threshold: 4 or more.
- Anxiety right now: 0 to 10. Threshold for the "talk to someone you trust, a counsellor or your doctor" line and the breathing offer: 7 or more.
Both thresholds are Bubbles' own (not from a validated instrument) and are described to the user only as "a check-in, not a medical assessment". The PHQ-2 / GAD-2 rules are unchanged.

### 15.4 Brain map
An average anxiety score of 7 or more (`STRESS_HIGH_AVERAGE`) across at least `ORGAN_MIN_ENTRIES_FOR_AVERAGE` check-ins makes the brain "worth watching" with: "Your anxiety scores averaged N/10 across M check-ins. If it keeps feeling like a lot, talking to someone can help." The tracker's stress number now also reaches the existing stress rule. Nothing here sets "talk to a doctor".

### 15.5 Chat behaviour (`mind_chat.py`)
When the person reports their own current, recent or recurring panic, separation anxiety, loneliness, anxiety or low mood, the model gets: reply like a close friend; one warm line, one small step, at most one question; name the matching Mind tool; never name or label a condition; never say it is nothing or promise it will pass; no medicine or supplement advice; if they mention not coping or feeling unsafe, stay gentle and point to a person they trust. Safety routing is unchanged and runs first.
Without the AI yes, loneliness gets this fixed reply (then the frozen consent text): "I'm really glad you said that. Feeling lonely is more common than people admit, and it doesn't mean something is wrong with you. One small thing that often helps is a short message to one person you like. The Loneliness check-in in the Mind section is there whenever you want it."

### 15.6 Static supportive copy (Mind hub; friend voice, no labels)
- Loneliness: "Feeling lonely is more common than people say, and it doesn't mean something is wrong with you. A small reach-out often helps: a short message to one person, or a walk where other people are around." Steps: send one short message to someone you like; go somewhere with other people nearby for ten minutes; say it in chat.
- Panic: "You are safe right now. This feeling is strong, and it passes. Let's slow it down together." Steps: breathe in for 4; breathe out slowly for 6, longer than the breath in; press your feet into the floor and name 3 things you can see. (The "you are safe right now" and "it passes" sentences are reassurance about the feeling, not about health; reviewer to confirm they are acceptable.)
- Missing someone / apart: "Missing someone you love is a sign of how much they matter. Being apart can feel heavy, and small rituals make it easier." Steps: pick a regular time to talk; send a voice note or a photo of your day; keep one small thing of theirs close and do one kind thing for yourself.
- Result lines for a high loneliness or anxiety score end with the unchanged support line (reach out right away; 112; Tele-MANAS 14416).
- Brain row wording: nothing to read yet; nothing stands out in what you have logged; worth a gentle look; worth talking through with someone you trust or a doctor. None says healthy or fine.

## Insight detail wording (A6)

No new threshold, symptom word or safety phrase. The sheet reuses existing confidence cut-offs (average entry confidence below 0.5 reads Low; score 0.75 / 0.5 for High / Medium on older responses).
New fixed user-visible sentences for sign-off:
- "It is not a diagnosis, and it does not mean something is wrong."
- "Days with no log are blanks, not good days."
- "It does not show that one thing causes the other."
- "A gap is not a sign that all is well." / "It does not mean something is wrong either."
- Try-this lines: "Keep logging when it happens, with what you were doing. If it bothers you, it is worth mentioning to a clinician." and "Keep logging both for a few more weeks and see whether they still show up together."

# L5 draft: clinical packet

B1 and B2 add no threshold, symptom word, supportive-content rule or safety phrase. For sign-off only:

1. **The frozen consent reply.** `consent.consent_needed_reply`: the last sentence ("If something feels urgent, call your local emergency number.") is unchanged and is pinned by `tests/test_consent_purposes.py::test_the_frozen_consent_reply_is_unchanged`. The rest of the text is unchanged too. An urgent message never receives this reply: it keeps the fixed urgent text (`urgent_fallback_response`).
2. **A new calm reply after a "No".** `consent.declined_reply`: "No problem. Nothing is sent to an outside AI. I can still log things, show your patterns and answer questions about your cycle, sleep and fitness. If you change your mind, it is one switch in Privacy choices." followed by the same emergency sentence. It is shown for at most 14 days after a No, then the question is asked again (once). It contains no medical advice.
3. **When health details noticed in chat are not saved.** With `health_memory_from_chat` off, chat still answers, deterministic safety (including emergency routing) still runs first and unchanged, and details are not extracted into storage. Anything the person logs themselves is still saved. A clinician may want to confirm that not saving a symptom mentioned in chat (until the person agrees) is acceptable, given that Bubbles then cannot remind them later of a symptom they mentioned.

# D1 intelligence: problem statement and findings (lane L7)

## Problem
After onboarding, Bubbles had no way to relate logs, labs and symptoms to vitamin, mineral, blood-marker and hormone gaps. Labs were
only read by organ_map_engine (thyroid TSH rules). Chat context carried no lab or nutrient hint. The RAG corpus (rag_sources.json, 11
sources) had no vitamin/mineral/hormone lab-test pages, so questions like "what does a ferritin test show" relied on whatever was
already stored.

## Findings
- backend/rag.py hybrid_search + rag_links.py LINK_DOCS had links only for sleep/mood/activity/cycle/fatigue-labs; nothing for
  nutrient-energy, iron-hair, vitaminD-mood, b12-diet, thyroid-cycle, hormones-cycle (rag_links.py, before this lane).
- The live store was not reachable from the sandbox: topic-tag coverage was audited from rag_sources.json and the ingest scripts only.
  No recall numbers are claimed (recall@5 1.00 / recall@1 0.85 was the last measurement, before these changes).
- WIP defects found and fixed: lab_status accepted NaN/inf/negative/huge values and reversed or half ranges (deficiency_map.py
  lab_status); free-text lab names/units were interpolated into user text and the chat context (now `_plain`, else the map's own
  name); non-dict profile lists crashed signals_from_rows; the ingest validator accepted an empty manifest, non-dict rows and
  non-list tags and crashed on odd types; 11 manifest titles had no LINK_DOCS prefix so `rag_links.py --apply` would not tag them
  (prefixes added).
- Onboarding keys `diet_style` exists (onboarding.py); `recent_blood_test` is not in the bank yet. Both are read defensively
  (missing = a gap line, never a nudge).

## What changed
- deficiency_map.py: pure map (11 entries), nudges (low/medium, max 3), lab notes against the person's own range only.
- deficiency_api.py: GET /nutrients/nudges (auth, owner-scoped, under-18 empty, best-effort sources named in `unavailable`);
  chat_block(): one sentence, cached, never waits, needs consent `ai_chat_processing`; hooked in main.py `_context_stage`.
- rag_nutrient_ingest.py + rag_nutrient_manifest.json (31 documents, MedlinePlus/NIDDK/NICHD/ODS; ICMR-NIN RDA deferred: priced,
  copyrighted). Dry run by default. rag_sources.json: + NIH ODS, NICHD. rag_links.py: 6 new link ids.
- tests/eval/retrieval_cases.jsonl: +23 cases (D101-D123).

## Open (not verified, left out)
- Per-page licence check of MedlinePlus/ODS pages before --apply (some MedlinePlus pages carry third-party credits).
- Ingest and eval re-run need network + backend/.env: `python rag_nutrient_ingest.py --check-urls`, then `--apply --from-dir pages`
  (ods_* are fetch=manual), `python rag_links.py --apply`, `python eval_retrieval.py`.
- No unit-mismatch check: Bubbles keeps no range table, so a value is compared only to the range the person entered.
- Today/Patterns closed row (frontend) is not built; API shape is ready. Android: no native work.
- Clinical sign-off: rules, thresholds (30-day window, 2 days per sign, 90-day quiet lab, 365-day freshness, 2 heavy days) and
  sentence templates are in deficiency_map.py; fold into the clinical packet.

# D1 intelligence: problem statement and findings (lane L7)

## Problem
After onboarding, Bubbles had no way to relate logs, labs and symptoms to vitamin, mineral, blood-marker and hormone gaps. Labs were
only read by organ_map_engine (thyroid TSH rules). Chat context carried no lab or nutrient hint. The RAG corpus (rag_sources.json, 11
sources) had no vitamin/mineral/hormone lab-test pages, so questions like "what does a ferritin test show" relied on whatever was
already stored.

## Findings
- backend/rag.py hybrid_search + rag_links.py LINK_DOCS had links only for sleep/mood/activity/cycle/fatigue-labs; nothing for
  nutrient-energy, iron-hair, vitaminD-mood, b12-diet, thyroid-cycle, hormones-cycle (rag_links.py, before this lane).
- The live store was not reachable from the sandbox: topic-tag coverage was audited from rag_sources.json and the ingest scripts only.
  No recall numbers are claimed (recall@5 1.00 / recall@1 0.85 was the last measurement, before these changes).
- WIP defects found and fixed: lab_status accepted NaN/inf/negative/huge values and reversed or half ranges (deficiency_map.py
  lab_status); free-text lab names/units were interpolated into user text and the chat context (now `_plain`, else the map's own
  name); non-dict profile lists crashed signals_from_rows; the ingest validator accepted an empty manifest, non-dict rows and
  non-list tags and crashed on odd types; 11 manifest titles had no LINK_DOCS prefix so `rag_links.py --apply` would not tag them
  (prefixes added).
- Onboarding keys `diet_style` exists (onboarding.py); `recent_blood_test` is not in the bank yet. Both are read defensively
  (missing = a gap line, never a nudge).

## What changed
- deficiency_map.py: pure map (11 entries), nudges (low/medium, max 3), lab notes against the person's own range only.
- deficiency_api.py: GET /nutrients/nudges (auth, owner-scoped, under-18 empty, best-effort sources named in `unavailable`);
  chat_block(): one sentence, cached, never waits, needs consent `ai_chat_processing`; hooked in main.py `_context_stage`.
- rag_nutrient_ingest.py + rag_nutrient_manifest.json (31 documents, MedlinePlus/NIDDK/NICHD/ODS; ICMR-NIN RDA deferred: priced,
  copyrighted). Dry run by default. rag_sources.json: + NIH ODS, NICHD. rag_links.py: 6 new link ids.
- tests/eval/retrieval_cases.jsonl: +23 cases (D101-D123).

## Open (not verified, left out)
- Per-page licence check of MedlinePlus/ODS pages before --apply (some MedlinePlus pages carry third-party credits).
- Ingest and eval re-run need network + backend/.env: `python rag_nutrient_ingest.py --check-urls`, then `--apply --from-dir pages`
  (ods_* are fetch=manual), `python rag_links.py --apply`, `python eval_retrieval.py`.
- No unit-mismatch check: Bubbles keeps no range table, so a value is compared only to the range the person entered.
- Today/Patterns closed row (frontend) is not built; API shape is ready. Android: no native work.
- Clinical sign-off: rules, thresholds (30-day window, 2 days per sign, 90-day quiet lab, 365-day freshness, 2 heavy days) and
  sentence templates are in deficiency_map.py; fold into the clinical packet.

## Own Brain: self-care cards and friend-voice replies (2026-10-25), awaiting clinician sign-off

- `backend/data/knowledge_cards.json`: 32 general self-care cards (sleep, caffeine, water, headache and cramp comfort, eye strain, back and neck, iron and protein foods, digestion, acidity, calming breathing, exam stress, walking, exercise start, afternoon energy, screens at night, cold comfort, nausea comfort, PMS mood, hair fall, acne, dark circles, sunlight, snacks, cutting down alcohol or smoking, loneliness). Each has a "when to see a clinician" line (a few harmless lifestyle cards have none). No doses, no medicine, no diagnosis. Please check every tip and every clinician line.
- What keeps a card from answering: any dose or medicine word, severity or long duration, pregnancy or a baby, a chronic condition word (heart, diabetes, thyroid, kidney, asthma and others), a red-flag word, or two topics at once. These guards are in `knowledge_cards._NEEDS_CARE`.
- `backend/companion_voice.py`: fixed supportive replies for stress, worry, panic, loneliness, missing someone, a low day, tiredness and good news (English and Hinglish). Panic replies always carry the line about getting medical help. Anything with hopelessness, harm, severity, long duration, a diagnosis question, a number, medicine or someone else's feelings is not answered there.
- `backend/data_answers.py`: sleep guide of 7 to 9 hours and movement guide of 150 minutes a week, quoted as "what most adults do well on" with "how rested you feel matters more".

## Saving from chat: what is saved by itself and what is asked (2026-10-25), awaiting clinician sign-off

`backend/event_policy.py`. A rule-extracted item stated plainly (sleep, water, exercise, weight, mood, meals, lifestyle) with confidence 0.8 or more is saved without asking. Everything else is asked once (Save or Skip): symptoms, fever, injuries, medicines, supplements, period and cycle items, conditions, any vital outside the range below, anything proposed by a model, and a second sleep, weight or mood on the same day.

Vital-sign ranges treated as "normal, safe to save without asking" (outside these, or at the edge, the person is asked):

| Reading | Range |
| --- | --- |
| Temperature | 35.5 to 37.7 °C |
| Heart rate | 50 to 110 per minute |
| Systolic / diastolic | 91 to 139 / 61 to 89 mmHg |
| Oxygen saturation | 95 to 100 % |

Please confirm these ranges, and whether any further item type (for example weight changes of more than a few kilograms in a day) should always be asked about.

## Personal guess checking (2026-10-25), awaiting review

`backend/prediction_ledger.py`. Bubbles makes small guesses from a person's own history and scores them against what they log. It speaks a link only after at least 6 scored guesses with a hit rate of 65% or more, and stops using it below 50%. Wording is always "in your own history", never a cause, and never advice. Please confirm the thresholds and the four links (sleep and mood, activity and next sleep, water and mood, sleep and movement).

### Own Brain, 15 more self-care cards (2026-10-25), awaiting clinician sign-off

Added to `backend/data/knowledge_cards.json`: sleep_routine, energy_foods, drink_more_water, healthy_breakfast, overthinking_night, wake_early, nap_length, calcium_foods, screen_time, homesick, anger_handling, balanced_plate, study_burnout, beginner_exercise, interview_nerves. Same rules as the first set: general self-care only, no doses, no diagnoses, each names when to see a clinician. Please read them in the file.
