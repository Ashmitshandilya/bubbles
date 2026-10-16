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
