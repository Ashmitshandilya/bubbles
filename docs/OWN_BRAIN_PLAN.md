# Own Brain: Bubbles answers for itself, and asks an outside model less

Written 2026-10-24. Goal from the owner: Bubbles should do as much as possible on its own, learn and adapt to each person from their own data, and
reach an outside language model (LLM) only when its own logic cannot do the job, so health data leaves the server less and Bubbles depends less on
free-tier providers. It should still sound like a friend: warm, real, never robotic.

## Principles

1. **Own logic first, model last.** A message is answered by Bubbles itself whenever it can do so correctly. The model is a fallback, not the default.
2. **Only what is provably right is answered locally.** A wrong local answer is worse than a model call. Every local route has a labelled evaluation set
   with a precision target (no wrong local answers) and a measured coverage number.
3. **Safety order never changes.** Emergency, Safe Harbor, correction, clarification and the other safety routes stay first. Local answers apply only
   to messages that safety triage rated clear (`NO_REDFLAG`) and that carry no symptom facts of their own.
4. **Honest about data.** Answers come from the person's own logs; a missing log is a gap in the answer, never a guess and never "fine".
5. **Learn and adapt per person, visibly.** Bubbles learns which of its own answers help each person (thumbs), what tone and length they like (Person
   Model), and when to stop answering a kind of question itself and hand it to the model instead.
6. **Make the model's job easy when it is needed.** The prompt gets a short sheet of facts Bubbles already computed from the person's logs (use these
   numbers exactly), so the model rewrites and connects instead of recalling, and has less to invent.
7. **Measure it.** The share of turns answered without a model is already counted in the admin console; the new routes are counted separately so the owner
   can see what grows.

## What exists today (before this work)

Deterministic routes: emergency, safe_harbor, correction, clarification, daily_log, fitness_support, fitness_answer, small_talk, safety_followup, recall,
remembered. Everything else (`ai` and `orbit`) calls a model. Person Model, association engine, pattern cards (Orbit), RAG evidence, fitness chat.

## The plan

| Phase | What | Result |
|---|---|---|
| 1. Ask your data (`data_answers.py`) | Questions about the person's own logs ("how did I sleep this week?", "am I drinking enough water?", "what was my best mood day?", "compare this week to last") are answered from their series: last value, average, best and worst day, change against the week before, days logged. English and Hinglish. | a large share of everyday questions never leave the server |
| 2. Self-care knowledge (`knowledge_cards.py`, `data/knowledge_cards.json`) | About 30 reviewed cards for common, low-risk lifestyle and comfort questions (sleep, hydration, caffeine, cramps comfort, eye strain, posture, iron and protein foods, stress breathing, post-meal walks, and more), each with what helps, when to see a clinician, and no doses or diagnoses. | common "what should I do about..." questions answered by reviewed text |
| 3. Friend voice (`companion_voice.py`) | Warm, varied replies for feelings (stress, loneliness, low mood, worry, tiredness) and good news, in the person's tone and length, English or Hinglish, with one small step and one caring question. | Bubbles answers feelings itself, like a friend, without sending them out |
| 4. Make the model's job easy (`brain_facts.py`) | A "what Bubbles already knows" sheet from the person's own data is added to the prompt for the questions that still need a model. | shorter, more accurate model answers |
| 5. Learn and adapt (`brain_stats.py`) | Thumbs on local answers are counted per person and kind of question; a kind that keeps missing for a person is handed to the model for them, one that keeps helping stays local. Coarse topic counts (no text) show the owner what the model still handles most. | Bubbles gets better at deciding for each person; the owner sees what to build next |
| 6. Prove it (`tests/eval/own_brain_cases.jsonl`) | Labelled messages for every route. Gates: no wrong local answer on the "must go to the model or to safety" set; coverage reported. | regressions are caught |

## Limits kept on purpose

- No local diagnosis, no doses, no medicine advice, no "you are fine".
- Weight is not answered locally (it is stored in the person's chosen unit and has its own eating-disorder safeguards in Fitness).
- Cards and replies are general self-care guidance and are added to the clinical review packet; a clinician should read them before they are called final.
- Devanagari Hindi still goes to the model (there is not yet a reviewed Hindi text bank); Roman Hindi (Hinglish) is handled.
- Open-ended or personal advice, relationship decisions, anything medical beyond comfort care, and anything the router is unsure about still goes to the model (with consent) as before.
- Nothing here trains a model on private chats. "Learning" is counted choices and preferences in the person's own signed documents.

## Done means

Merged to `main` with tests; a measured coverage figure on the labelled set; the admin console shows the new routes in the answer mix; `DECISIONS.md`
and `CLAUDE.md` describe the modules. Items not finished are listed at the end of `DECISIONS.md` under this entry.
