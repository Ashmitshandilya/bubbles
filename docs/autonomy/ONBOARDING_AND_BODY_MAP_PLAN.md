# Bubbles: body map upgrade and first-run onboarding (research and build plan)

Date: 2026-10-15. Status: plan for execution. No application code was changed to write this file.
Branch to build on: `claude/vibrant-cori-r6b9wu` (or a fresh branch from `main`). Repo root: `bubbles/`.
Read `CLAUDE.md` and `docs/autonomy/PLAN.md` (operating rules) before starting. Paths below are relative to the repo root.

---

## 0. Read this first (for the executing session)

### What the founder asked for
1. **Body map:** more visible (today it is faint and see-through), add **eyes**, add every body part that can and should be tracked, and **track the eyes** for real. When an organ is selected it should **bump and pump up** (highlight).
2. **Female anatomy:** people with a female body see a female body map.
3. **First-run onboarding:** landing page, sign in, then a set of predefined questions (some cannot be skipped, such as gender and age), with later questions chosen by **gender and age**. It should cover health, mental health, friends (asked gently and indirectly, never hurtful), and what irritates or drains them. After submitting, a **"Creating your personal companion"** loading screen, while Bubbles sets up the UI, features and experience from the answers. The answers become the base of the account.

### Non-negotiable rules (from CLAUDE.md and PLAN.md)
- No diagnosis, no dosing, no "healthy" verdicts. Missing data is a gap, never "fine". Organ views say "not enough data", never "healthy".
- `safety_engine.py` and `health_semantics.py` safety behaviour must not change except by additions with tests. Any free text a person types goes through `assess_safety` first.
- **No Supabase schema changes.** New data uses signed documents (`backend/doc_store.py`) and the existing `health_events` ledger, like Fitness, Cycle, Mind and Consent already do.
- `$0 AI` default stays. Nothing in onboarding calls an AI model. All rules are deterministic and tested.
- Every API call from the app goes through `useApi().fetchBubbles`. No direct `fetch`.
- Copy is plain and calm, no em-dashes in visible text, no diagnosis words, every button does something real (no fake progress bars).
- Before changing Next.js code, read the guide under `frontend/node_modules/next/dist/docs/` (Next 15.5, React 19.3, three 0.186, @react-three/fiber 9, drei 10).

### Gates for every chunk (run all, all green before pushing)
```
cd backend && python -m pytest tests -q -p no:warnings && python -m compileall -q main.py
cd frontend && npx tsc --noEmit && npm run lint && npx vitest run && npm run build
```
Do not build with a custom `NEXT_DIST_DIR` inside the repo (it rewrites `tsconfig.json` and leaves a 280 MB folder). Use the default `.next`.

### Execution order (section 9 has the detail)
C1 body map look and selection, C2 eyes end to end, C3 the other new body systems, C4 onboarding backend, C5 onboarding app, C6 personalisation consumers, C7 QA, docs and clinical packet. Each chunk is independently shippable.

---

## 1. Decisions for the founder (defaults apply if no answer)

| # | Decision | Default | Why |
|---|---|---|---|
| D1 | Minimum age | **18+ only.** Under 18 sees a kind stop screen; no health data is stored | The Terms already say 18+. India's DPDP Act treats under-18s as children and needs verifiable parental consent, which Bubbles cannot do today |
| D2 | The required "body" question | **"Which body should Bubbles plan your health guidance for?"** Female / Male / Intersex / Prefer not to say. Required, but "Prefer not to say" is a valid answer | Guidance (cycle, screening, formulas, anatomy) depends on body, not on identity. Separating body from gender identity is the standard inclusive practice |
| D3 | Gender identity | Separate, optional: Woman / Man / Non-binary / Self-describe / Prefer not to say | Respectful, and used only for how Bubbles addresses the person |
| D4 | Body map art | Improved **stylised procedural** 3D (fits the brand) in v1. A licensed anatomical `.glb` (male and female) can replace it later | Procedural ships now with no licence risk |
| D5 | What onboarding answers go to the outside AI model | Only: preferred name, tone, reply length, language, goals, topics to avoid. Stressors, support people and screening answers stay on the server and drive deterministic personalisation only | Keeps the AI consent honest; anything more needs a consent version bump (section 6.4) |
| D6 | Existing users | Shown onboarding once, pre-filled from what Bubbles already knows, only the missing required questions are mandatory | Everyone gets the same personalised base |
| D7 | Cycle section for a male body | Hidden from the main menu (still reachable from Settings, "Show Cycle") | Less clutter, nothing deleted |

---

## 2. Research summary (what the plan is based on)

**Onboarding length and drop-off.** Health and fitness apps ask about 4 to 6 question screens on average (median 4.5, max 21). Long forms lose people: the consistent advice is to ask what decides the main route first, then stop once the product can give a useful first result, and ask the rest later (progressive profiling). Splitting questions across short screens with a progress bar helps. Plan consequence: about **7 required answers**, everything else skippable, grouped in 8 short steps, about 3 to 4 minutes total, and "Finish later" saves progress. Later questions are asked in context (Mind, Cycle, Care) rather than all at once.

**Sex and gender questions.** Ask body (for health) and gender identity separately, say why each is asked, offer non-binary or self-describe and "prefer not to say", and explain how the data is used and stored. Plan consequence: D2 and D3.

**Mental health at first run.** The WHO-5 is positively worded (cheerful, calm, active, rested, interested over the last 2 weeks), 0 to 5 per item, raw score below 13 (out of 25) suggests poor well-being and further assessment. PHQ-2 and GAD-2 (already built in `mind_checkins.py`, cut-off 3) are symptom screens that need a defined next step. Plan consequence: onboarding asks one gentle "how have you been feeling" question and **offers** the existing PHQ-2/GAD-2 check (skippable). A positive screen shows calm, non-diagnostic support text and the existing help resources, never a label.

**Friends and loneliness.** The ONS recommends the three-item UCLA scale (how often you feel you lack companionship, left out, isolated) plus a direct question. Those are measurement items, not first-run questions: asked cold they can hurt. Plan consequence: onboarding asks only an indirect, strength-based question ("When something is on your mind, who do you usually turn to?") where "I mostly work things through on my own" is a neutral, valid answer with no follow-up. No loneliness score is computed at onboarding.

**Alcohol and tobacco.** AUDIT-C is three items (frequency, typical amount, six or more drinks), 0 to 4 each. Plan consequence: ask frequency only; the other two appear only if the person drinks. Tobacco includes chewing forms common in India (gutka, paan with tobacco, khaini), which matter for oral health.

**India screening context.** The national NCD programme (NP-NCD) targets adults **30 and over** for blood pressure, diabetes and three cancers (oral, breast, cervical). Plan consequence: age 30+ gets "when did you last check your blood pressure and sugar", women 30+ get a gentle cervical-screening question, and tobacco users get oral-health prompts. These become a **Care checklist**, worded as "worth asking your doctor about", never as orders.

**Eyes.** Digital eye strain causes tired or dry eyes, blur, headache and neck or shoulder discomfort; the American Optometric Association's 20-20-20 break (every 20 minutes, look 20 feet away for 20 seconds) is the common advice, with limited trial evidence; persistent blur, double vision or eye pain needs an exam. For diabetes, the ADA recommends a dilated eye exam at type 2 diagnosis (within 5 years for type 1), then yearly, possibly every 1 to 2 years after clean exams. Plan consequence: an Eyes tracker (screen time, eye comfort, symptoms, glasses, breaks), an "eyes" body system, a 20-20-20 reminder option, and a "last eye exam" Care item that is yearly for people with diabetes. Sudden vision loss is already a RED safety pattern and stays one.

**Privacy (India DPDP Act 2023 and 2025 Rules).** Under-18 data needs verifiable parental consent (OTP to a parent, ID, DigiLocker), and tracking or profiling children is restricted. Plan consequence: D1.

Sources are listed in section 11.

---

## 3. What exists today (verified in the code on 2026-10-15)

| Area | Where | Notes |
|---|---|---|
| 3D body | `frontend/components/Anatomy3D.tsx` | Head sphere opacity 0.55, torso capsule and two leg capsules opacity 0.45 on a blush background, so the figure is faint. **No arms, neck or pelvis.** 9 organ dots (all spheres). Selection only scales to 1.35 instantly with a purple emissive. No anatomy variants |
| Body systems page | `frontend/app/health/OrganTracker.tsx` | Accessible list plus optional 3D (dynamic import, error boundary). Fetches `GET /intelligence/body-systems?days=90` |
| Dashboard panel | `frontend/app/dashboard/dashboard/BodyComponents.tsx` (`OrganPanel`) | **Not imported anywhere** and does not pass `selected` to `Anatomy3D`. Either delete it or fix and use it (C1) |
| Organ logic | `backend/organ_tracker.py` (`ORGANS`, `RISK_FACTORS`, `DIRECT_EVIDENCE_FIELDS`, `assess_organ`), `backend/organ_intelligence.py`, endpoint in `backend/main.py` (`/intelligence/body-systems`) | 9 systems: brain, heart, lungs, liver, kidneys, pancreas, digestive_system, reproductive_system, musculoskeletal_system. No eyes |
| Eye language | `backend/health_semantics.py` concept `blurred_vision`; sudden vision loss is in the RED stroke pattern | No eye strain, dry eye, red eye, eye pain concepts |
| Profile | `profiles` table: display_name, date_of_birth, height_cm, gender, timezone. `GET /profile` | No onboarding fields |
| Body profile (fitness) | `doc_store` kind `profile` key `me`, `GET/PUT /profile/body` in `backend/fitness_api.py` (`clean_profile`: birth_date, height_cm, weight_kg, formula_basis male/female/average, activity_level, units, diet_style, list fields) | Reuse, do not duplicate |
| Cycle settings | `doc_store` kind `cycle_settings` key `main`, `GET/PUT /cycle/settings` in `backend/cycle_api.py` (mode, age_group, pregnancy, postpartum...) | Onboarding sets the mode |
| AI consent | `backend/consent.py` (kind `consent`, key `ai_chat`, `VERSION`), `GET/PUT /me/consent` | Onboarding shows the same choice |
| Mind screens | `backend/mind_checkins.py`, `POST /wellness/mind/screen` (PHQ-2, GAD-2, score only) | Reuse for the optional check |
| Eating sensitivity | `doc_store` kind `eating_screen` in `fitness_api.py` | A positive screen already hides deficits; "avoid weight and calories" must use the same switch |
| Tracker domains | `backend/health_logs.py` `DOMAINS` (nutrition already stores in `health_events` filtered by `event_type`) | Eyes uses the same pattern: no new table |
| Sign-in routing | `frontend/app/login/page.tsx` and `frontend/app/callback/page.tsx` go to `/dashboard`; signed-in shells `components/hub/HubKit.tsx` (`HubPage`) and `components/tracking/kit.tsx` redirect to `/login` without a session | The onboarding gate goes in these shells |
| Navigation | `frontend/components/Navigation.tsx` (`SECTIONS`, `ME`) | Sections become filterable by the experience profile |
| Preview mode | `NEXT_PUBLIC_UI_PREVIEW=1` + `backend/preview_server.py` (`BUBBLES_PREVIEW=1`, token `preview`) | Use it for screenshots and the end-to-end test |

---

## 4. Part A: the body map

### A1. Make it clearly visible (C1)
File: `frontend/components/Anatomy3D.tsx`.
- Build a complete stylised figure: head, neck, shoulders, two arms (upper and fore capsules), torso, pelvis, two legs. Proportions come from an anatomy preset (A2).
- Body material: `meshPhysicalMaterial` (or standard) with **opacity about 0.78**, `depthWrite={false}` so organs inside stay visible, plus an outline (`<Outlines>` from drei, thickness about 0.012, colour from a token) and a soft rim light. Organs render after the body (`renderOrder` higher) at full opacity.
- Colours as tokens (CSS variables read once, or a small constants map) with **at least 3:1 contrast** against the canvas background (WCAG 1.4.11 non-text contrast). Use a slightly deeper blush or lilac skin tone and a lighter canvas, or the reverse, and check both light and dark themes.
- Stronger lighting: ambient 0.6, key directional 1.1, a back rim light 0.6.
- Organs get simple recognisable shapes instead of identical dots: paired eyes (small spheres), heart (slightly flattened sphere), lungs (two capsules), kidneys (two small beans), liver (wide flattened ellipsoid), stomach and gut (rounded block), bladder, thyroid (small bow at the neck), and so on. Keep each a separate mesh with its own click target; small parts (eyes, thyroid) get an invisible larger hit sphere so they are easy to tap.
- Keep `aria-hidden` on the canvas: the list stays the accessible source of truth.

### A2. Anatomy variants (C1, driven by onboarding in C6)
- New prop `anatomy: "female" | "male" | "neutral"` and `organs: string[]` (which systems to draw). Presets in a small pure module `frontend/components/anatomy/presets.ts` with tests:
  - **female:** narrower shoulders, wider hips, subtle chest shape, reproductive system drawn as uterus and ovaries, plus a `breasts` system.
  - **male:** broader shoulders, narrower hips, reproductive system drawn as prostate and testes.
  - **neutral:** average proportions, reproductive system drawn as a single soft marker labelled "Reproductive", no breasts.
- The organ list comes from the experience profile (`experience.anatomy.organs`), not from a gender label. People who choose Intersex or Prefer not to say get **neutral** plus a Settings choice: "Which of these should your body map include?" (uterus and ovaries, breasts, prostate and testes). This also serves trans people correctly.
- Labels change with anatomy: `reproductive_system` shows as "Uterus and ovaries", "Prostate and testes" or "Reproductive".

### A3. Every body part worth tracking (C2 eyes, C3 the rest)
Add systems to `backend/organ_tracker.py` (`ORGANS`, `DIRECT_EVIDENCE_FIELDS`, `RISK_FACTORS` product weights, `_actions_for`), to the label maps in `OrganTracker.tsx`, and positions in the anatomy presets. Every new rule goes into `docs/clinical/BUBBLES_CLINICAL_REVIEW_PACKET.md` as "awaiting clinician sign-off".

| System id | Shown as | Direct evidence fields | Risk factors (existing or new) | Symptom concepts that count | Why it matters |
|---|---|---|---|---|---|
| `eyes` | Eyes | `last_eye_exam`, `vision_prescription`, `eye_diagnosis`, `eye_pressure` | persistent_high_glucose, persistent_high_bp, smoking, **high_screen_time** (new), poor_sleep | blurred_vision (exists), **eye_strain, dry_eyes, red_eye, eye_pain, eye_itch** (new) | Founder request; diabetes and BP affect eyes; screen strain is common |
| `thyroid` | Thyroid | `tsh`, `t3`, `t4`, `thyroid_diagnosis` | none (labs only) | fatigue is not mapped (too unspecific) | Thyroid conditions are common in India |
| `mouth` | Mouth and teeth | `dental_visit`, `oral_diagnosis` | smoking, **tobacco_chewing** (new), alcohol_excess | **mouth_ulcer, toothache, gum_bleeding** (new) | NP-NCD oral cancer screening; chewing tobacco |
| `ears` | Ears and hearing | `hearing_test`, `ear_diagnosis` | **loud_noise_exposure** (new, optional) | **ear_pain, tinnitus, hearing_loss** (new; sudden hearing loss is an urgent-review pattern, add to safety tests) | Earphone use, hearing |
| `skin` | Skin | `skin_diagnosis` | none | rash, itching (if concepts exist; else add) | Commonly reported |
| `bladder` | Bladder and urine | `urine_test`, `urinary_diagnosis` | persistent_high_glucose | **burning_urination, frequent_urination** (new) | UTIs are common, especially in women |
| `breasts` | Breasts (female anatomy only) | `breast_exam`, `mammogram`, `breast_diagnosis` | none | **breast_lump, breast_pain** (new; a new lump maps to "see a doctor soon", not RED) | NP-NCD breast screening |

Notes for the executor:
- New symptom concepts are added to `health_semantics.py` with the same negation and tense machinery, plus Hinglish terms in `hinglish_terms.py` where known ("aankh mein jalan", "aankhen laal", "dhundla dikhna"). Add corpus cases to `tests/health_language_corpus.py` and the eval sets. Do not change existing concept behaviour.
- The organ assessment keeps the same rules: no direct evidence and no risk signals means `unknown`, confidence low, "not enough data".
- The symptom-to-system mapping: check how existing symptoms reach `organ_tracker` via the snapshot built in `organ_intelligence.py`. If symptoms are not used yet, add a small explicit `SYMPTOM_SYSTEMS` map with tests rather than guessing from names.

### A4. Selected organ bumps and pumps (C1)
In `Anatomy3D.tsx`, one `OrganMesh` component per organ with `useFrame`:
- **Select:** a damped spring on scale: 1 to 1.5 and settle at 1.3 in about 450 ms (critically damped, no overshoot loops). Emissive ramps to 0.6 in the brand grape colour. A thin halo ring (torus, additive, opacity 0.5) fades in around it.
- **Pump while selected:** a gentle breathing pulse of about ±5% at about 1 Hz (heart can use a two-beat "lub-dub" curve, lungs a slower 0.25 Hz expand). Other organs dim to about 55% opacity so the selected one stands out.
- **Camera:** OrbitControls target eases toward the selected organ (lerp over about 600 ms) and slightly closer. Never fight a user who is dragging (pause the ease while the pointer is down).
- **Two-way sync:** selecting in the list triggers the same animation; tapping in 3D selects in the list (already wired through `onSelect`).
- **Reduced motion** (`prefers-reduced-motion: reduce`, read with `matchMedia`): no pulse, no camera move, the scale steps to 1.3 and the colour changes. Also pause animation when the tab is hidden.
- Performance: no per-frame allocations (reuse vectors), `frameloop="demand"` when nothing animates is a nice extra.
- Fix the unused `OrganPanel` (pass `selected`) or delete it.

### A5. Eyes tracking end to end (C2)
1. **Track page:** new tab "Eyes" in the Track section (`Navigation.tsx` Track tabs) at `frontend/app/eyes/` using the shared tracker kit (`components/tracking/kit.tsx`). A log entry: screen time today (hours, 0 to 18), eye comfort (5 faces), symptoms (chips: dry, itchy, red, strained, blurry, watery, headache), glasses or lenses worn (yes/no), 20-20-20 breaks taken (count, optional), note (optional, through `assess_safety`).
2. **Storage:** a new `health_logs.DOMAINS["eyes"]` over `health_events` with `event_type="eye_check"` (same pattern as `nutrition`), so it is no schema change and appears in exports and deletes. Tests like the existing domain tests.
3. **Chat:** "my eyes are burning after the laptop", "aankhon mein jalan" produce eye symptom events (pending, confirmable), dated with `event_dates.py`. Sudden vision loss stays RED.
4. **Body system:** `eyes` uses screen time (high_screen_time when the 7-day average is 6 hours or more: a product threshold for the clinical packet), symptoms, last eye exam and glucose/BP risk factors.
5. **Patterns:** add association pairs in `backend/association_insights.py` (`PAIRS`) and series in `association_loader.py`: screen time with eye comfort, screen time with sleep. Each needs a test (the false-discovery correction covers all pairs).
6. **Care:** "Last eye exam" item; yearly when the person has diabetes (ADA), otherwise "worth a check if you notice changes, or every couple of years" worded as a suggestion and listed in the clinical packet.
7. **Reminder:** optional 20-20-20 reminder (every 20 minutes during chosen hours, off by default) through `backend/notifications.py`. Opt-in only.

---

## 5. Part B: onboarding

### B1. Flow
```
Landing  ->  /login (sign up or sign in)  ->  /dashboard
                                              |  gate: GET /onboarding/state
                                              v  not complete
                                          /onboarding  (steps 0-8, saves after every step)
                                              |  Submit
                                              v
                                   "Creating your personal companion" (POST /onboarding/complete)
                                              |  done
                                              v
                                          /dashboard (personalised)
```
- **Gate:** `HubPage` (`components/hub/HubKit.tsx`) and the tracker shell (`components/tracking/kit.tsx`) call a new `useOnboarding()` hook (state in `components/Providers.tsx`, fetched once per session through `fetchBubbles`, cached). If `complete` is false and the path is not `/onboarding`, `router.replace("/onboarding")`. While loading, keep the existing "Opening Bubbles" screen (no flash).
- **Never block help:** `/onboarding` has a visible "Need help right now?" link that opens the deterministic urgent-help sheet (the same text `safety_engine` produces), and `/companion` stays reachable for an urgent message. Login and callback stay unchanged (they go to `/dashboard` and the gate does the rest).
- **Resume:** every step is saved with `PUT /onboarding/answers`; closing the tab and coming back resumes at the first unanswered step.
- **Finish later:** available once the required "About you" step is done; the gate then shows a dismissible "Finish setting up Bubbles" card on Today instead of forcing the page again. Required answers are always required.
- **Existing users:** answers are pre-filled from `profiles`, `/profile/body`, `/cycle/settings` and `/me/consent`; already answered required questions are skipped.

### B2. The question bank
The bank lives on the **backend** (`backend/onboarding.py`, versioned, `BANK_VERSION = "2026-10a"`) and is served by `GET /onboarding/questions`, so validation and branching rules have one source. The app renders it generically. Each question: `id`, `step`, `type` (single, multi, date, number, slider, text, faces, consent), `required`, `show_if` (a small rule: `age_gte`, `age_lt`, `body_in`, `answer_in`), `options` (id + label), `why` (one line shown under the question), `maps_to`.

`R` = required (cannot be skipped; "Prefer not to say" counts as an answer where offered). Everything else has a Skip button. Ages come from the date of birth.

**Step 0: Welcome** (no questions)
"Let's set Bubbles up for you. About 3 minutes. Answer what you're comfortable with: most questions can be skipped, and you can change everything later in Settings. Bubbles never diagnoses, and your answers stay private to your account."

**Step 1: About you**
| id | Question | Type | R | Options or rule | maps_to |
|---|---|---|---|---|---|
| `preferred_name` | What should Bubbles call you? | text (40) | R | prefilled from sign-up | `profiles.display_name` |
| `birth_date` | When were you born? | date | R | age 18 to 110; under 18 goes to the stop screen (D1) | `profiles.date_of_birth`, `/profile/body.birth_date` |
| `body` | Which body should Bubbles plan your health guidance for? | single | R | female, male, intersex, prefer_not. Why: "This sets things like cycle tracking, screening reminders and your body map." | the onboarding doc (`body`) and `/profile/body.formula_basis` (female, male, average). `profiles.gender` stays for gender identity only |
| `gender_identity` | How do you describe your gender? | single + text | | woman, man, non_binary, self_describe, prefer_not | `profiles.gender` |
| `language` | Which language feels easiest? | single | R | English, Hinglish, Hindi (default English) | experience.companion.language |

**Step 2: What brings you here**
| id | Question | Type | R | Options (show_if) |
|---|---|---|---|---|
| `goals` | What would you like help with? Pick any. | multi (1 to 6) | R | understand_symptoms, sleep, stress_mood, fitness_weight, food, manage_condition, doctor_visits, cycle (body in female, intersex, prefer_not), pregnancy (body female or intersex, age 18 to 50), just_exploring |

**Step 3: Your health**
| id | Question | Type | R | Options (show_if) |
|---|---|---|---|---|
| `conditions` | Has a doctor ever told you that you have any of these? | multi | R | diabetes, prediabetes, high_bp, thyroid, pcos (body female/intersex/prefer_not), asthma_copd, heart, migraine, anaemia, depression_anxiety, kidney, liver, arthritis, other (text), none, prefer_not |
| `takes_medicines` | Do you take any medicines or supplements regularly? | single | | yes, no, prefer_not. If yes: "You can add them now or later" (link to the Medications page after onboarding) |
| `allergies` | Any allergies? | single + multi | | no, yes (foods, medicines, dust or pollen, other), not_sure |
| `family_history` | Has anyone in your close family had any of these? | multi | | heart_disease, diabetes, high_bp, cancer, mental_health, none, not_sure |
| `height_weight` | Height and weight (optional, used for fitness and food) | number pair | | metric or imperial |

**Step 4: Your body and life stage** (each question only when its rule matches)
| id | Shown when | Question | Options | maps_to |
|---|---|---|---|---|
| `periods` | body female/intersex, age 18 to 55 | Do you get periods? | regular, irregular, not_now, prefer_not | cycle mode `track` |
| `periods_reason` | periods = not_now | What fits best? | pregnant, recently_gave_birth, breastfeeding, contraception_stops_them, menopause, other, prefer_not | cycle mode `pregnancy` / `postpartum` / `menopause`... (use `engine.MODES`) |
| `last_period` | periods regular/irregular | When did your last period start? (optional) | date, within the last 120 days | cycle log |
| `pregnancy_plans` | body female/intersex, age 18 to 50, not already pregnant | Are you trying to get pregnant? | no, trying, prefer_not | cycle mode `conceive` |
| `due_date` / `birth_date_baby` | pregnant / recently gave birth | Due date / date of birth | date | cycle settings pregnancy / postpartum |
| `midlife_changes` | body female/intersex, age 40+ | In the last few months, have you noticed any of these? | hot_flushes, night_sweats, period_changes, sleep_changes, none, prefer_not | menopause content in Cycle and Mind |
| `bp_sugar_check` | age 30+ | When did you last get your blood pressure and blood sugar checked? | within_year, one_to_three_years, longer_or_never, not_sure | Care checklist (NP-NCD) |
| `cervical_screen` | body female/intersex, age 30 to 65 | Have you ever had a cervical screening test (Pap, HPV or VIA)? | last_5_years, longer_ago, never, not_sure, prefer_not | Care checklist, gentle info only |
| `urinary_changes` | body male/intersex, age 45+ | Do you often get up at night to pass urine, or notice a weaker flow? | yes, no, prefer_not | Care checklist ("worth mentioning to a doctor") |

**Step 5: Daily life**
| id | Question | Type | Notes |
|---|---|---|---|
| `sleep_hours` | On a usual night, how long do you sleep? | slider 3 to 12 h | sleep goal default |
| `activity` | How active is a usual week? | single | maps to `/profile/body.activity_level` values |
| `diet_style` | How do you usually eat? | single | vegetarian, eggetarian, non_vegetarian, vegan, jain (existing `DIET_STYLES`) |
| `tobacco` | Do you use tobacco in any form? | multi | no, smoke, chew (gutka, paan with tobacco, khaini), used_to, prefer_not |
| `alcohol_freq` | How often do you have a drink with alcohol? | single (AUDIT-C 1) | never, monthly_or_less, 2_4_month, 2_3_week, 4_plus_week, prefer_not |
| `alcohol_amount`, `alcohol_heavy` | only if alcohol_freq is not never | AUDIT-C 2 and 3 | score kept server-side; never shown as a label |
| `screen_hours` | About how many hours a day are you on screens? | slider 0 to 16 | eyes system |
| `eyes` | About your eyes | multi | wear_glasses, wear_lenses, often_tired_or_dry, none |
| `last_eye_exam` | When was your last eye check? | single | within_year, one_to_two_years, longer, never_not_sure |

**Step 6: Your mind** (fully skippable; gentle)
| id | Question | Type | Notes |
|---|---|---|---|
| `feeling_lately` | Over the last two weeks, how have you been feeling overall? | faces 1 to 5 | no score label shown |
| `mind_check` | Would you like a 1-minute check on mood and worry? | yes / not now | yes runs the existing PHQ-2 and GAD-2 through `POST /wellness/mind/screen` (score only). A positive result shows: "Thanks for sharing. These feelings are worth talking about with someone you trust or a professional. Here's where to find support." plus the existing resources. No diagnosis words |
| `mind_note` | Anything on your mind you'd like Bubbles to know? | text (optional, 300) | **through `assess_safety` first.** Crisis wording: the deterministic crisis response appears immediately (India helplines), the step offers "Continue setup later", nothing else runs on that text |

**Step 7: People around you** (skippable; strength-based, never "how many friends")
| id | Question | Type | Options |
|---|---|---|---|
| `support_people` | When something's on your mind, who do you usually turn to? | multi | family, partner, friends, colleagues_classmates, online_communities, a_pet, faith_or_community, mostly_on_my_own, rather_not_say |
| `checkins_wanted` | Would you like Bubbles to check in on you now and then? | single | yes_daily, sometimes, no |
Copy note: "mostly_on_my_own" is shown as "I mostly work things through on my own" with no follow-up, no sympathy message and no score. If chosen, the companion is warmer and offers check-ins, nothing more.

**Step 8: What drains you, what helps** (skippable)
| id | Question | Type | Options |
|---|---|---|---|
| `drains` | What tends to drain or irritate you? | multi | work_study_pressure, money, family_or_relationship_tension, not_enough_sleep, health_worries, noise_or_crowds, traffic_commute, screens_social_media, heat, being_rushed, something_else (text, through assess_safety) |
| `helps` | What usually helps you feel better? | multi | music, a_walk, talking_to_someone, prayer_or_meditation, sleep, good_food, exercise, games, time_alone, nature |
| `avoid_topics` | Anything you'd rather Bubbles didn't bring up unless you ask? | multi | weight, calories_food_numbers, periods, family, none |

**Step 9: How Bubbles talks with you**
| id | Question | Type | R | Options |
|---|---|---|---|---|
| `tone` | How should Bubbles talk with you? | single | R | gentle_warm, calm_direct, cheerful_playful (default gentle_warm) |
| `reply_length` | Replies | single | | short, detailed (default short) |
| `ai_consent` | The existing AI consent card (same text as `consent.py`) | consent | | yes / not_now (a real choice; "not now" still completes onboarding) |
| `reminders` | A gentle daily check-in reminder? | single + time | | off (default), on at a chosen time |

**Review screen:** a short summary of answers per step with "Edit" links, then **Create my companion**.

### B3. Where each answer is stored (no schema change)
| Store | What | Written by |
|---|---|---|
| `profiles` (existing columns) | display_name, date_of_birth, gender (identity) | `POST /onboarding/complete` (server, owner-scoped) |
| `doc_store` kind `onboarding`, key `v1` (new, signed) | All answers, `bank_version`, `started_at`, `completed_at`, `step` | `PUT /onboarding/answers` and complete |
| `doc_store` kind `experience`, key `main` (new, signed) | The computed experience profile (B5) | complete, and recomputed when answers change in Settings |
| `/profile/body` doc (existing) | birth_date, height, weight, formula_basis (female/male/average from `body`), activity_level, diet_style | complete, through `clean_profile` (reuse its validation) |
| `/cycle/settings` doc (existing) | mode, pregnancy or postpartum dates | complete, through the cycle settings cleaner |
| Cycle log (existing) | last period start | complete |
| `/me/consent` doc (existing) | AI consent | the consent endpoint, unchanged |
| `mind_screen` docs (existing) | PHQ-2 / GAD-2 scores | the existing screen endpoint |
| `medical_conditions`, `allergies` (existing tables via `health_logs`) | conditions and allergies the person ticked, as **user-confirmed** entries with `source="onboarding"` | complete (they are the person's own statements, not AI-derived, so they may be written as confirmed) |
| Notifications (existing) | reminder opt-ins | complete |

Under 18: store only `{"age_gate": "under_18", "at": ...}` in the onboarding doc, nothing else, and offer "Delete my account" (existing data-rights flow).

### B4. Backend API (C4)
New files: `backend/onboarding.py` (pure: bank, rules, validation, experience builder; no I/O) and `backend/onboarding_api.py` (router, registered in `main.py` like `consent_api`). All routes authenticated, owner-scoped, rate-limited with the existing guards, bodies capped.

| Route | Purpose |
|---|---|
| `GET /onboarding/questions` | The bank (questions, options, rules, why-text), `bank_version` |
| `GET /onboarding/state` | `{complete, step, answers (prefilled for existing users), required_missing: [...], under_18: bool}` |
| `PUT /onboarding/answers` | Partial save of one step: validates types, options, ranges and `show_if`; drops answers whose rule no longer matches (for example `periods` after `body` changes to male). Free text through `assess_safety`: crisis wording returns `{safety: <deterministic payload>}` and the text is **not stored** |
| `POST /onboarding/complete` | Requires every required answer. Idempotent (same answers give the same result). Writes the stores in B3, computes and saves the experience profile, returns `{status: "success", experience, applied: [ {id, label} ... ]}` where `applied` lists what was really set up (for the loading screen) |
| `GET /experience` | The saved experience profile, for the app shell |

Validation rules: dates are calendar days (never shift through UTC; reuse `event_dates.user_today` for today), age from date of birth, numbers within `clinical_constants.MIN_PLAUSIBLE`, option ids from a fixed list, text length caps, no HTML.

Data rights: make sure `backend/data_rights.py` export and delete include the new doc kinds (check how it enumerates `doc_store` kinds; add `onboarding` and `experience`).

### B5. The experience profile (pure function, heavily tested) (C4)
`build_experience(answers, today) -> dict`, deterministic. Output:
```
{
  "version": "2026-10a",
  "anatomy": {"base": "female|male|neutral", "organs": [...]},          # A2: female adds breasts and uterus/ovaries; male adds prostate/testes; neutral asks in Settings
  "sections": {"visible": [...], "order": [...]},                        # Cycle hidden for male body (D7) unless goal cycle; never removed from Settings
  "today_cards": [...],                                                   # ordered by goals: sleep goal puts Sleep first, manage_condition puts the condition card first ...
  "body_map_focus": [...],                                                # systems to light first: diabetes -> pancreas, eyes, kidneys, heart; high_bp -> heart, kidneys, brain, eyes; screens 6h+ -> eyes; tobacco -> lungs, mouth, heart
  "trackers_suggested": [...],                                            # e.g. diabetes -> Vitals (glucose); screens -> Eyes; sleep goal -> Sleep
  "care_checklist": [ {"id", "title", "why", "source"} ],                 # age 30+ BP and sugar check (NP-NCD); female 30-65 cervical screening info; diabetes yearly eye exam (ADA); tobacco oral check; male 45+ urinary mention
  "companion": {"tone", "reply_length", "language", "name", "avoid_topics", "comfort_actions", "check_ins"},
  "fitness": {"formula_basis": "female|male|average", "deficits_allowed": bool},   # false when pregnant, recently gave birth, breastfeeding, or avoid_topics has weight/calories
  "cycle": {"mode": "...", "visible": bool},
  "mind": {"offer_checkin_weekly": bool},                                  # true when feeling_lately <= 2 or a positive screen; never a label
  "reminders": [...]                                                      # only what the person opted into
}
```
Rules to encode (each with a test):
- Hide numbers about weight and calories everywhere when `avoid_topics` has weight or calories, using the same switch as a positive eating screen.
- Never infer a condition. Goals and answers only change ordering, suggestions and wording.
- "Prefer not to say" never narrows features: neutral anatomy, average formulas, Cycle visible but not pinned.
- Pregnancy or postpartum: fitness deficits off, strict plans off (reuse existing cycle-mode safeguards).

### B6. "Creating your personal companion" screen (C5)
- Shown immediately on Submit while `POST /onboarding/complete` runs. Bubbles mascot (existing `BubblesMascot`, mood "thinking"), title "Creating your personal companion", soft animated bubbles in the background (CSS only; reduced motion: static).
- **Honest progress:** while waiting, one line "Setting things up for you". When the response arrives, the `applied` lines from the server appear one by one (about 350 ms apart), each with a check: "Your body map is set to female anatomy", "Cycle tracking is on", "Today now starts with Sleep and Stress", "Bubbles will talk with you gently, in Hinglish", "3 health checks added to Care", "Eye tracking is ready". A minimum on-screen time of about 2 seconds keeps it from flashing, but no line is shown before the server confirms it.
- Then "All set, {name}" and a button **Open Bubbles** (auto-continue after 2 s). `apiCache.clear()` so Today reloads with the new profile.
- Failure: "Your answers are saved. Bubbles couldn't finish setting up just now." with **Try again** (same request, idempotent). Never lose answers. A cold API host shows the existing "waking up" banner.

### B7. Where the app uses the experience profile (C6)
- **Navigation** (`Navigation.tsx`): filter and order `SECTIONS` by `experience.sections`; Settings gets "Show Cycle" and "Body map organs".
- **Today** (`app/dashboard`): card order from `today_cards`; the "Finish setting up" card when onboarding was deferred.
- **Body map**: `Anatomy3D` gets `anatomy.base`, `anatomy.organs`, and `body_map_focus` (those systems glow softly on first open, with a one-line "Based on what you told Bubbles").
- **Companion**: `context_engine.py` adds a short "PREFERENCES" block (tone, length, language, avoid topics) for the AI path and for deterministic replies (greeting by name, Hinglish copy where it exists). Only the D5 fields reach the model.
- **Care**: the checklist from `care_checklist` at the top of `/care`, each item with "why" and a dismiss.
- **Fitness**: `formula_basis` and `deficits_allowed`.
- **Cycle**: mode and visibility.
- **Mind**: the optional weekly gentle check-in offer.
- **Settings**: a "Your setup" page to change any onboarding answer (re-runs `build_experience`).

### B8. Safety and privacy checklist (must all hold)
- Any free text (mind_note, drains "something else", condition "other") goes through `assess_safety` before anything else; crisis wording returns the deterministic response and the text is not saved.
- No diagnosis or risk labels are shown from screens; PHQ-2/GAD-2 show supportive text only.
- The friends question has no "lonely" wording, no counts, and no follow-up for "on my own".
- Under 18: stop screen, no health data stored (D1).
- Consent: if more than the D5 fields ever go to the AI model, update `consent.py` text and bump `VERSION` so everyone is asked again, and update the consent card in the app.
- Logs never contain answers (only ids and counts), like the existing chat logging.
- Export and delete cover the new documents.
- Every new clinical rule (care checklist intervals, screen-time threshold, new organ weights, symptom mappings) is added to `docs/clinical/BUBBLES_CLINICAL_REVIEW_PACKET.md` as awaiting sign-off.

### B9. Copy rules for this feature
Plain, warm, short. Say why a question is asked in one line. Use "you can skip this". No em-dashes. No "healthy", "normal", "risk score", "diagnosis", "disorder" in visible text. Hinglish versions for the question titles when `language` is Hinglish (keep a small dictionary in the bank; English is the fallback).

---

## 6. Tests to add (minimum)

Backend (`backend/tests/`):
- `test_onboarding_bank.py`: every question has a valid type, options and rule; required ids are exactly the agreed list; `show_if` evaluates correctly for every age and body combination (table-driven: ages 18, 29, 30, 39, 40, 44, 45, 50, 55, 65, 70 with each body).
- `test_onboarding_api.py`: auth required; partial save; invalid option rejected; answers dropped when their rule stops matching; crisis text in `mind_note` returns the safety payload and stores nothing; under-18 stores only the age gate; complete is idempotent; complete writes profile, body profile, cycle settings and conditions with `source="onboarding"`; export and delete include the new docs.
- `test_experience.py`: anatomy per body; Cycle visibility; deficits off for pregnancy, postpartum, breastfeeding and avoid weight; focus systems for diabetes, high BP, screens 6h+, tobacco; care checklist per age and body; "prefer not to say" keeps every feature available; no condition is ever inferred.
- `test_organ_tracker_new_systems.py`: each new system is `unknown` with no data, uses only direct evidence and listed risk factors, never says healthy.
- Health language corpus and safety eval cases for the new eye, ear, mouth, bladder and breast concepts (including negation: "no eye pain", other people: "my mom's eyes are red", Hinglish), and that sudden vision loss and sudden hearing loss keep their safety level.
- Eyes domain tests (save, list, export, delete) and the new association pairs.

Frontend (`frontend/app/**/*.test.ts`, vitest):
- Anatomy presets (organs per anatomy, labels).
- The question renderer's rule evaluation mirrors the server (`show_if` cases).
- The loading screen shows only server-confirmed lines.
- Navigation filtering by `experience.sections`.

End to end (Playwright, `playwright-cli` skill, preview mode): sign in with the preview token, land on `/onboarding`, answer the required questions as a 32-year-old female, see the cycle and cervical questions, submit, see the loading screen and the real applied lines, land on Today with Cycle in the menu and the female body map. Repeat as a 50-year-old male: no cycle questions, urinary question shown, Cycle hidden. Screenshot both body maps (selected organ mid-pulse) for the founder.

---

## 7. Acceptance criteria (the founder's words, made checkable)
1. The body figure is clearly visible on light and dark themes (silhouette contrast at least 3:1 against its background), with arms, neck and pelvis.
2. Eyes are on the map, selectable, and have their own tracker, chat understanding, patterns and Care item.
3. Selecting any organ (in 3D or in the list) makes it bump up, glow and gently pulse; others dim; reduced motion shows a still highlight.
4. A female body shows female anatomy; a male body shows male anatomy; others choose.
5. A new account cannot reach the app before answering the required questions (name, date of birth, body, language, goals, conditions, tone). Everything else can be skipped.
6. Questions change with age and body exactly as in B2.
7. The friends question never hurts: no loneliness wording, no counts, no follow-up for "on my own".
8. Submitting shows "Creating your personal companion" with only real, server-confirmed setup lines, then a personalised Today.
9. Nothing is diagnosed, no AI model is called by onboarding, no schema change, all gates green.

---

## 8. Risks and how the plan handles them
| Risk | Handling |
|---|---|
| People drop off a long setup | 7 required answers, short steps, progress bar, autosave, Finish later, the rest asked in context later |
| Sensitive questions hurt or feel intrusive | Strength-based wording, a "why" line under each, Prefer not to say, everything optional except the core |
| A crisis disclosure in a text box | `assess_safety` first, deterministic crisis response, nothing stored |
| Under-18 sign-ups | Age gate, nothing stored (D1) |
| WebGL fails or a slow phone | The list view stays the source of truth; 3D is optional and behind an error boundary; reduced-motion and hidden-tab pauses |
| Personalisation hides something someone needs | Nothing is deleted, only reordered or moved to Settings; "Prefer not to say" keeps everything |
| AI context grows quietly | D5 limits plus a consent version bump if it ever changes |
| Existing users are locked out | Pre-fill, and only missing required answers are mandatory |

---

## 9. Execution chunks (for the executing session, one at a time, gates green after each)

**C1. Body map look and selection** (frontend only, plus deletion or fix of `OrganPanel`)
Files: `frontend/components/Anatomy3D.tsx`, new `frontend/components/anatomy/presets.ts` (+ `presets.test.ts`), `frontend/app/health/OrganTracker.tsx`.
Done when: A1, A2 (driven by a temporary prop default "neutral"), A4 work; screenshots of selection captured in preview mode; gates green.

**C2. Eyes end to end**
Files: `backend/organ_tracker.py`, `backend/health_semantics.py` (+ `hinglish_terms.py`), `backend/health_logs.py`, `backend/association_insights.py`, `backend/association_loader.py`, `backend/notifications.py`, new `frontend/app/eyes/` page, `frontend/components/Navigation.tsx` (Track tab), presets (eye positions), tests listed in section 6, clinical packet entries.
Done when: A5 steps 1 to 7 work and are tested.

**C3. The other new body systems** (thyroid, mouth, ears, skin, bladder, breasts)
Files: as C2 for each system, smallest useful version: system plus symptom concepts plus labels and positions. Each system can be its own commit.

**C4. Onboarding backend**
Files: new `backend/onboarding.py`, `backend/onboarding_api.py`, registration in `backend/main.py`, `backend/data_rights.py`, tests in section 6.
Done when: B2 to B5 are implemented and tested; no I/O in `onboarding.py`.

**C5. Onboarding app**
Files: new `frontend/app/onboarding/page.tsx` and `OnboardingClient.tsx` (generic renderer, one step per screen, progress bar, Back, Skip, autosave), `frontend/app/onboarding/flow.ts` (+ test, rule evaluation), `frontend/app/onboarding/Creating.tsx` (B6), `useOnboarding` in `components/Providers.tsx`, the gate in `components/hub/HubKit.tsx` and `components/tracking/kit.tsx`, the under-18 stop screen.
Done when: B1 and B6 work in preview mode, keyboard and screen reader friendly (labels, focus moves to the step title on each step, 44 px targets).

**C6. Personalisation consumers**
Files: `Navigation.tsx`, `app/dashboard/*`, `Anatomy3D` props from `/experience`, `backend/context_engine.py` (preferences block, D5 only), `/care` checklist, fitness and cycle settings writes, a Settings "Your setup" page.
Done when: B7 works for the two end-to-end personas.

**C7. QA, docs, clinical packet**
Playwright end-to-end for both personas, accessibility pass (`design:accessibility-review` skill), update `CLAUDE.md` (frontend and backend sections: onboarding, experience profile, eyes), `docs/clinical/BUBBLES_CLINICAL_REVIEW_PACKET.md`, and the log in `docs/autonomy/PLAN.md`. Merge to `main` only after the founder approves.

---

## 10. Sample copy (ready to use)
- Welcome: "Let's set Bubbles up for you. About 3 minutes. Skip anything you'd rather not answer, and change it later in Settings."
- Body question why-line: "This sets cycle tracking, health check reminders and your body map. It is not about how you identify."
- Under 18: "Bubbles is for people 18 and over for now. If you're younger, a parent, school nurse or doctor is a great person to talk to. You can delete this account in one tap."
- Friends: "When something's on your mind, who do you usually turn to?" Option: "I mostly work things through on my own".
- Drains: "What tends to drain or irritate you? This helps Bubbles notice what's behind a rough day."
- Mind positive screen: "Thanks for sharing. Feelings like these are worth talking about with someone you trust or a professional. Here's where to find support."
- Loading: "Creating your personal companion" / "Setting things up for you" / "All set, {name}".
- Failure: "Your answers are saved. Bubbles couldn't finish setting up just now." Button: "Try again".

---

## 11. Sources
- Onboarding length benchmarks: [Lazyweb, quiz questions in Health and Fitness apps](https://www.lazyweb.com/research/how-many-quiz-questions-health-fitness-apps), [Lazyweb, onboarding quiz length](https://www.lazyweb.com/research/how-many-quiz-questions-onboarding.md)
- Progressive profiling: [involve.me](https://involve.me/blog/progressive-profiling-101-collect-more-data-without-friction), [Kompassify](https://kompassify.com/blog/progressive-profiling-guide), [screensdesign: personalised onboarding](https://screensdesign.com/articles/personalized-app-onboarding/), [Saasfactor: reducing drop-off](https://www.saasfactor.co/blogs/what-steps-should-your-signup-and-onboarding-include-to-reduce-drop-off)
- Sex and gender questions: [Princeton GSRC, creating inclusive forms](https://gsrc.princeton.edu/creating-inclusive-forms), [Queen's University Belfast, asking about sex and gender identity](https://qub.ac.uk/directorates/HumanResources/diversity-and-inclusion/TransEquality/AskingaboutSexGenderIdentity), [Cemplicity, gender and sex survey questions](https://www.cemplicity.com/blog/how-to-ask-gender-and-sex-survey-questions/), [ALBA inclusive forms guideline](https://www.alba.network/GSDinclusiveforms), [Intellisurvey](https://blog.intellisurvey.com/how-to-ask-gender-questions-online-surveys)
- Loneliness measures: [ONS recommended loneliness measures](https://www.ons.gov.uk/peoplepopulationandcommunity/wellbeing/compendium/nationalmeasurementofloneliness/2018/recommendednationalindicatorsofloneliness), [UCLA Loneliness Scale v3 (Russell 1996)](https://pubmed.ncbi.nlm.nih.gov/8576833/), [Campaign to End Loneliness, measuring](https://www.campaigntoendloneliness.org/evaluation/)
- WHO-5: [Blueprint WHO-5](https://help.blueprint.ai/en/articles/8264194-wellbeing-index-5-who-5), [Valant WHO-5](https://valant.helpjuice.com/who-five-well-being-index-who-5), [Topp et al. systematic review](https://karger.com/pps/article/84/3/167/282903/The-WHO-5-Well-Being-Index-A-Systematic-Review-of)
- PHQ-2 and GAD-2: [Annals of Family Medicine 2023](https://www.annfammed.org/content/21/5/444), [Modern Health GAD-2](https://support.modernhealth.com/hc/en-us/articles/360044295112)
- AUDIT-C: [Vanderbilt SBIRT AUDIT-C protocol](https://www.vumc.org/trauma-and-scc/sites/default/files/public_files/Protocols/SBIRT_AUDIT-C_%20PMG%202024.pdf), [Froedtert alcohol screening guideline](https://www.froedtert.com/sites/default/files/upload/docs/services/trauma/guidelines/alcohol-screening-and-intervention-for-the-inpatient-guideline.pdf)
- India NCD screening (age 30+, BP, diabetes, oral, breast, cervical): [MoHFW NPCBVI training manual](https://npcbvi.mohfw.gov.in/Douments/Training_Manuals/Expanded_services_HWC_non_Eye/Prevention_Control%20_PBS_of_Hypertension.pdf), [Medical Dialogues report](https://health.medicaldialogues.in/health/over-5-crore-diagnosed-with-hypertension-3-crore-with-diabetes-govt-report-153037), [Morung Express, screening drive](https://morungexpress.com/health-ministry-launches-screening-drive-against-high-bp-diabetes-cancer-in-adults)
- Eyes: [All About Vision, 20-20-20 rule](https://allaboutvision.com/conditions/myopia/20-20-20-rule/), [HealthXchange, computer vision syndrome](https://www.healthxchange.sg/how-to-prevent/tired-eyes/how-to-prevent-eye-strain-computer-vision-syndrome), ADA retinopathy screening: [PMC9810462](https://pmc.ncbi.nlm.nih.gov/articles/PMC9810462), [diabetesed.net on ADA 2026](https://diabetesed.net/taking-a-new-look-at-diabetic-retinopathy-screening/), [diaTribe](https://diatribe.org/diabetes-complications/get-most-out-your-retinopathy-screenings)
- India DPDP Act and children: [EY DPDP Act and Rules 2025](https://www.ey.com/content/dam/ey-unified-site/ey-com/en-in/pdf/2025/11/ey-india-dpdp-act-2023-and-rules-2025-pov.pdf), [Mondaq](https://www.mondaq.com/india/privacy-protection/1710322/), [King Stubb and Kasiva, parental consent rules](https://ksandk.com/data-protection-and-data-privacy/child-data-protection-under-dpdp-act-parental-consent-rules/), [IIT BHU summary](https://iitbhu.ac.in/contents/institute/cf/cis/doc/dpdp_act_rules_summary.pdf)

Caveats: the onboarding benchmarks come from a small sample by one research firm; several screening sources are summaries rather than the guideline texts; clinical thresholds in this plan (screen time 6 h, eye-exam wording, organ weights) are product choices that must go through the clinical review packet before they are presented as guidance.
