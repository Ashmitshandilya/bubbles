# C1 first-run setup: problem statement (lane L6)

## Problem
The first run asked 44 questions in 9 steps (about 30 answered), required 7, hid Skip, put gender third, said "About three minutes",
ran the 18+ check only when `birth_date` was in the same request (a body saved first was stored before the age was known), and held
people on a 4.5 s "Creating your personal companion" screen. Most answers changed nothing visible. There was no tour.

## Every old question, what it changed, what became of it
Real effect = it is read by a feature today. Kept = asked on first run. Later = only in Me > Your setup (`edit=1`). Dropped = gone.

| Old question(s) | What it changed in the product | Now |
|---|---|---|
| body | menu (Cycle), body map, cycle mode, profiles.gender, formula basis | Kept, FIRST screen, one tap, required |
| language | chat style (Hinglish/Hindi), Hinglish question titles | Kept, same first screen as a 3-chip row (default from browser), required |
| birth_date | profile, age-based care checklist, 18+ gate | Kept, required, saved in the same request as body |
| preferred_name | profile display name, chat greeting | Kept, required |
| goals (multi 10) | trackers_suggested, mind offer | Merged into `main_goal` (single, 9 options, cycle only for REPRO bodies), required |
| conditions (16, required) | saved to Care conditions | `conditions_any` yes/no/prefer not (required) then the 16-list only after yes |
| conditions_other | Care condition, safety-checked free text | Kept as follow-up after "other" |
| feeling_lately | mind offer | Replaced by `stress_level` (4 chips, required): drives mind check-in offer and trackers |
| sleep_hours (slider, optional) | stored, never read | Replaced by `sleep_pattern` (4 chips, required): drives sleep tracker and a Care item; old hours convert on load |
| periods (+ reason, last_period, pregnancy_plans, due_date, baby_birth_date) | cycle settings, cycle mode, body profile flags | `periods` required for a female body only (`REQUIRED_IF`); follow-ups are optional extras |
| height_weight, activity, diet_style | body profile, fitness and food plans | Kept as optional extras; `diet_style` key kept (L7) |
| (new) recent_blood_test | read by the deficiency work (L7) | Optional extra, key kept |
| allergies, allergy_types | Care allergies | Optional extra |
| takes_medicines | stored, never read | Optional extra yes/no (one tap; stored for later use) |
| avoid_topics, tone, reply_length | chat style block | Optional extras ("How Bubbles talks") |
| support_people, drains, drains_other, checkins_wanted | companion context only (comfort and stressors) | Optional extras |
| helps, mind_check, mind_note | stored, never read; mind_note was free text about distress | Dropped (mind_note removed: no reason to collect free text about distress at sign-up) |
| family_history, tobacco(4 forms), alcohol_freq/amount/heavy | stored, never read | Family history and alcohol dropped; tobacco moved to Later |
| eyes, last_eye_exam, screen_hours | stored, never read | Eyes dropped; last_eye_exam and screen_hours in Later |
| bp_sugar_check, cervical_screen, midlife_changes, urinary_changes | one care-checklist line each | Later only (never on first run) |
| ai_consent (inside the bank) | wrote a consent | REMOVED as a question. Consent is a separate "Your choices" step writing the consent ledger; setup itself never writes a consent |

Result: required core is 7 taps for a male body, 8 for a female body (body, language, date and name on one screen, main goal,
conditions yes/no, sleep, stress, periods). Optional extras are grouped on 6 screens behind one intro with "Skip all extras".

## What was built
- Server bank (`backend/onboarding.py`): screens, `REQUIRED_IF`, answer migration from the old bank, `BANK_VERSION 2026-10b` (finished people are not sent back).
- Gate ordering (`onboarding_api.py`): the age check runs on the date in the request or the date already known; no date means 422 and nothing is stored; under 18 stores only `age_gate`.
- Client (`flow.ts`, `OnboardingClient.tsx`): body is a single tap that waits; it is sent only together with a valid date. Auto-advance on single choice, explicit Skip, "Needed" lock tag, "Question n of N" then "A few extras (skip any)", honest "About a minute" copy.
- Setup screen: "Setting up your app" / "Set up my app", min 1200 ms, 250 ms per line, at most 4 lines, auto-open 2000 ms, retry state kept.
- Tour (`tour.ts`, `FirstRunTour.tsx`, `GET/PUT /onboarding/tour`): five coach marks on Today, skippable (button or Esc), focus kept inside, replay from Settings.

## Defaults chosen
Hindi browsers default `language` to Hindi, everyone else English. Tour state lives in a signed doc (`tour/v1`), no schema change.
`tone` and `reply_length` moved out of the required set (the brief asked tone stay short; it is now an optional 3-chip extra defaulting to gentle).
