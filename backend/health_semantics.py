"""Generic health-language semantics for Bubbles.

A health *mention* is not a health *fact*. "No chest pain", "can chest pain
happen with anxiety?", "my doctor told me to watch for chest pain" and "I have
chest pain" all contain the same words and mean completely different things.
This module turns free text into :class:`Fact` records that carry that meaning:

* ``assertion`` - present | negated | possible | hypothetical | question |
  other_person | quoted
* ``temporal``  - current | recent | past | resolved | recurring | future | unknown
* severity, experiencer, certainty, confidence, provenance and a short machine
  readable ``reason`` (for diagnostics; never shown as free text to users).

The engine is deterministic, generic (a lexicon of concepts, no per-symptom
special cases in the logic) and linear-time: every pattern is built from
literals with bounded repetition, so an 8k-character message cannot blow up.
It is a conservative *routing* layer, not a diagnostic engine; when the text is
ambiguous the safe default is "present, current" for red-flag concepts and the
caller decides whether to ask a clarifying question.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable

import hinglish_terms as _hi

ENGINE = "bubbles-semantics/2"   # 2: Hinglish/Devanagari red flags and Hindi word-order cues

ASSERTIONS = ("present", "negated", "possible", "hypothetical", "question", "other_person", "quoted")
TEMPORALS = ("current", "recent", "past", "resolved", "recurring", "future", "unknown")

# --------------------------------------------------------------------------
# Concept metadata
# --------------------------------------------------------------------------

#: crisis concepts: any current/recurring mention must reach a human resource.
CRISIS = frozenset({"suicidal_ideation", "self_harm"})
#: hedged mentions of these ("I think I'm having a heart attack") still escalate.
POSSIBLE_IS_EMERGENCY = frozenset({"heart_attack", "stroke_signs", "allergic_reaction", "suicidal_ideation", "self_harm"})
#: concepts whose severity adjective ("severe", 9/10) makes them urgent.
PAIN_CONCEPTS = frozenset({"headache", "abdominal_pain", "pelvic_pain", "cramps", "back_pain", "joint_pain", "muscle_pain", "chest_pain", "severe_pain", "eye_pain"})

DISPLAY = {
    "chest_pain": "chest pain", "shortness_of_breath": "shortness of breath", "headache": "headache",
    "dizziness": "dizziness", "nausea": "nausea", "vomiting": "vomiting", "abdominal_pain": "abdominal pain",
    "pelvic_pain": "pelvic discomfort", "cramps": "cramps", "bloating": "bloating", "fatigue": "fatigue",
    "fever": "fever", "cough": "cough", "sore_throat": "sore throat", "back_pain": "back pain",
    "joint_pain": "joint pain", "muscle_pain": "muscle pain", "palpitations": "palpitations",
    "fainting": "fainting", "seizure": "seizure", "confusion": "confusion", "vomiting_blood": "vomiting blood",
    "persistent_vomiting": "persistent vomiting", "unusual_bleeding": "unusual bleeding",
    "heavy_bleeding": "heavy bleeding", "spotting": "spotting", "suicidal_ideation": "thoughts of suicide",
    "self_harm": "self-harm", "stroke_signs": "stroke warning signs", "allergic_reaction": "a severe allergic reaction",
    "heart_attack": "a possible heart attack", "anxiety": "anxiety", "low_mood": "low mood", "insomnia": "trouble sleeping",
    "diarrhea": "diarrhea", "constipation": "constipation", "rash": "rash", "swelling": "swelling",
    "numbness": "numbness", "blurred_vision": "blurred vision", "period": "your period",
    "eye_strain": "eye strain", "dry_eyes": "dry eyes", "red_eye": "red eyes", "eye_pain": "eye pain", "eye_itch": "itchy eyes",
    "medication_use": "medication", "severe_pain": "severe pain",
}


def display_name(concept: str) -> str:
    return DISPLAY.get(concept, concept.replace("_", " "))


# --------------------------------------------------------------------------
# Lexicon: (concept, tier, label, patterns). tier: red | urgent | None.
# `label` is the stable human reason string used by the safety layer.
# Spaces inside a pattern match any run of whitespace/hyphens.
# --------------------------------------------------------------------------

# Only these names are ever recorded as a medication/supplement ("never invent"); shared with daily_log_parser.
SUPPLEMENT_NAME_PATTERN = (
    "iron|magnesium|calcium|zinc|omega[\\s-]?3|folic acid|folate|multivitamins?|probiotics?|melatonin|ashwagandha|vitamin[\\s-]?[a-z]\\d*")
DRUG_NAME_PATTERN = (
    "ibuprofen|paracetamol|acetaminophen|tylenol|aspirin|naproxen|cetirizine|loratadine|metformin|antacids?|birth control|contraceptive pill|"
    "levothyroxine|thyroxine|omeprazole|pantoprazole|amoxicillin|azithromycin|prednisolone|insulin|atorvastatin|amlodipine|losartan|sertraline|escitalopram")
MEDICATION_NAME_PATTERN = SUPPLEMENT_NAME_PATTERN + "|" + DRUG_NAME_PATTERN

# Named group `neg` = a negator that sits INSIDE the symptom phrase ("stomach doesn't hurt"):
# a mention whose own text carries it is read as a denial. At most one `neg` group per concept.
_RED_CHEST = (
    "chest pains?|pains? in (?:my |the )?chest|chest (?:pressure|tightness|discomfort|ache|heaviness|burning)|"
    "(?:pressure|tightness|discomfort|heaviness) in (?:my |the )?chest|crushing chest|tight chest|heavy chest|"
    "chest (?:is |feels )?(?:hurting|hurts|tight|heavy)|my chest (?:hurts|aches|is hurting|feels tight|feels heavy)|"
    "chest (?P<neg>doesn't|does not|isn't|is not|don't) (?:hurt|ache|feel (?:tight|heavy)|hurting|tight|heavy)|"
    "(?:squeez\\w*|tight\\w*|crushing|burning|stabbing|sharp|aching|heavy|heaviness|pressure|pressing|pain)(?: \\w+){0,4} "
    "(?:in|around|across|on) (?:my |the )?(?:(?:middle|centre|center|left side|right side) of (?:my |the )?)?chest|"
    "(?:an? )?elephant (?:sitting )?on (?:my |the )chest|(?:a )?(?:tight )?band around (?:my |the )chest|pressure on (?:my |the )chest"
)

_LEX_SRC: tuple[tuple[str, str | None, str, tuple[str, ...]], ...] = (
    ("chest_pain", "red", "chest pain or pressure", (_RED_CHEST,)),
    ("shortness_of_breath", "red", "breathing difficulty", (
        "shortness of breath|short of breath|breathlessness|breathless",
        "(?:trouble|difficulty|difficulties|problems?|issues?|struggl\\w*) (?:with |in )?breathing",
        "breathing (?:difficulty|difficulties|trouble|problems?|issues?)",
        "(?:can't|cannot|can not|couldn't|could not|unable to|not able to) (?:breathe|catch (?:my|your) breath|get (?:enough |any )?(?:air|breath))",
        "not getting (?:enough|any) air(?! conditioning)|(?:isn't|is not|wasn't) getting (?:enough|any) (?:air|oxygen)",
        "hard (?:time )?(?:to breathe|breathing)|struggling to breathe|labou?red breathing|gasping for (?:air|breath)",
        "(?:blue|bluish|purple|grey|gray) (?:lips|fingertips|fingernails|skin)|"
        "(?:my |his |her )?lips (?:feel|feels|are|is|look|looks|turn|turns|turned|turning|have turned|going|gone)(?: (?:a |slightly |kind of |very |really |bright |dark ))?(?:blue|bluish|purple|grey|gray)")),
    ("fainting", "red", "loss of consciousness", (
        "faint(?:ed|ing)|passed out|pass(?:ing)? out|black(?:ed|ing)? out|blackouts?|lost consciousness|loss of consciousness|unconscious|collapsed|syncope",
        # "I faint when ..." / "about to faint" (the subject stays outside the mention so who-is-it-about still works)
        "(?:(?<=\\bi\\s)|(?<=\\bwe\\s)|(?<=\\byou\\s)|(?<=\\bhe\\s)|(?<=\\bshe\\s)|(?<=\\bthey\\s))faints?|(?:to|will|might|may|could|would|gonna) faint")),
    ("seizure", "red", "seizure", ("seizures?|convulsions?|convulsing",)),
    ("heavy_bleeding", "red", "heavy bleeding", (
        "heavy bleeding|bleeding heavily|bleeding (?:a lot|profusely|badly)|haemorrhag\\w+|hemorrhag\\w+",
        "soaking (?:through )?(?:a |an |my )?(?:pads?|tampons?)(?: (?:every|each) (?:hour|half hour|30 minutes|\\d+ minutes?))?",
        "(?:large|big|huge) clots?|passing clots")),
    ("suicidal_ideation", "red", "possible self-harm crisis language", (
        "suicid\\w*|kill(?:ing)? (?:my|him|her|them|your|our)(?:self|selves)|end(?:ing)? my (?:own )?life|take my own life|want(?:ed)? to die|wish i (?:was|were) dead|"
        "don't want to (?:live|be alive|be here|wake up)|better off dead|no reason to live|end(?:ing)? it all",
        # passive ideation
        "better off without me|wish i (?:was|were) never born|wish i had never been born|(?:there's |there is )?no point (?:in )?(?:living|going on|continuing|any ?more)|"
        "(?:can't|cannot) go on|(?:want|wanted|wish) to (?:just )?disappear|(?:give|giving|gave) up on (?:life|living)")),
    ("self_harm", "red", "possible self-harm crisis language", (
        "self[\\s-]?harm\\w*|(?:harm|hurt|cut)(?:ting|ing)? (?:myself|himself|herself|themselves|yourself)|overdos\\w+",)),
    ("stroke_signs", "red", "possible stroke warning signs", (
        "stroke|face droop\\w*|facial droop\\w*|droop\\w* face|face (?:\\w+ ){1,2}droop\\w*|(?:side of )?(?:my |the )?face (?:is |has |feels )?(?:sagging|drooping|dropping)|slurred speech|slurring (?:my )?(?:words|speech)",
        "sudden weakness (?:on|in) (?:one|my (?:left|right)) (?:side|arm|leg)|weakness on (?:one|my (?:left|right)) side|one[\\s-]sided weakness|sudden (?:loss of|trouble with) (?:vision|speech)",
        # sudden loss of sight, said in everyday words (additive; needs clinician review). Always with a "sudden" cue: "I can't see the board" is not this.
        "(?:sudden(?:ly)?|all of a sudden|out of nowhere|just now) (?:i )?(?:can'?t|cannot|couldn'?t|could not|am unable to|was unable to|unable to) see (?:anything|at all|properly|clearly|out of (?:my |the )?(?:left |right |one )?eye|with (?:my |the )?(?:left |right |one )?eye)",
        "(?:can'?t|cannot|couldn'?t|could not) see (?:out of|with) (?:my |the )?(?:left |right |one )eye (?:suddenly|all of a sudden)|(?:suddenly|all of a sudden) (?:lost|losing) (?:all |my )?(?:vision|sight)|(?:lost|losing) (?:all |my )?(?:vision|sight)(?: in (?:my |the |one )?(?:left |right )?eye)? (?:suddenly|all of a sudden|just now)|(?:suddenly|all of a sudden) (?:went|gone|going|go) blind|curtain (?:coming |falling |came |fell |dropped )?(?:(?:down|over|across) ){1,2}(?:my |the )?(?:vision|eye)",
        # inability to feel/move a limb or half the face is the same warning in other words (additive; needs clinician review)
        "(?:can'?t|cannot|unable to|not able to|no longer) (?:feel|move) (?:my |the )?(?:left |right )?(?:arm|leg|hand|side of (?:my )?face|face)|(?:my |the )?(?:left |right )?(?:arm|leg|hand|side of (?:my )?face) (?:suddenly )?(?:went|has gone|became) (?:numb|dead|limp|weak)")),
    ("allergic_reaction", "red", "possible severe allergic reaction", (
        "severe allergic reaction|anaphyla\\w+",
        "throat (?:is |was |feels |feeling |has been |gets? )?(?:a little |slightly |kind of |somewhat |a bit |getting |really |very |so )?(?:closing|swelling|tight|swollen)",
        "(?:face|tongue|lips?|throat) (?:is |are |was |were )?(?:swelling|swollen|swell\\w*)",
        "swell(?:ing)? (?:of|in) (?:my |the )?(?:face|tongue|throat|lips?)|swollen (?:face|tongue|throat|lips?)")),
    ("heart_attack", "red", "possible heart attack", ("heart attack|cardiac arrest|myocardial infarction",)),
    ("headache", "red", "sudden severe headache", ("worst headache of my life|thunderclap headache|sudden (?:severe|intense|explosive) headache",)),
    # --- urgent tier
    ("vomiting_blood", "urgent", "blood in vomit", (
        "(?:vomit\\w*|throw\\w* up|threw up|puk\\w+) (?:up )?(?:blood|coffee grounds)|blood in (?:my )?(?:vomit|puke|throw[\\s-]?up)|bloody vomit",)),
    ("persistent_vomiting", "urgent", "persistent vomiting", (
        "vomiting (?:a lot|repeatedly|constantly|non[\\s-]?stop)|can't keep (?:anything|food|water|fluids?) down|cannot keep (?:anything|food|water|fluids?) down",)),
    ("confusion", "urgent", "confusion", ("confus\\w+|disorient\\w+",)),
    ("severe_pain", "urgent", "severe pain", (
        "(?:severe|excruciating|unbearable|agonizing|agonising) pain|worst pain (?:of|in) my life",)),
    ("fever", "urgent", "high fever", (
        "(?:very )?high fever|fever (?:of|over|above) (?:10[3-9]|39|4[0-2])(?:\\.\\d)?|temperature (?:of |is |was |at |over |above )?(?:10[3-9]|39|4[0-2])(?:\\.\\d)?(?![\\d:])",)),
    # --- ordinary concepts (never escalate on their own)
    ("allergic_reaction", None, "allergic reaction", ("allergic reactions?",)),
    ("headache", None, "headache", (
        "headaches?|head[\\s-]?aches?|migraines?|head (?:pain|hurts|is pounding|is throbbing)|pain in (?:my )?head",
        "head (?P<neg>doesn't|does not|isn't|is not|don't) (?:hurt|ache|hurting|aching)")),
    ("dizziness", None, "dizziness", ("dizz\\w+|light[\\s-]?headed\\w*|vertigo|woozy|wooziness|(?:feel|feeling|felt) faint|faint feeling|spinning (?:room|sensation)|unsteady",)),
    ("nausea", None, "nausea", ("nausea|nauseous|nauseat\\w+|queasy|queasiness|(?:feel|feeling|felt) sick|sick to (?:my|the) stomach|upset stomach",)),
    ("vomiting", None, "vomiting", ("vomit\\w*|throwing up|threw up|throw up|puk\\w+|retching",)),
    ("abdominal_pain", None, "abdominal pain", (
        "abdominal (?:pain|cramps?|discomfort)|stomach (?:pain|aches?|cramps?|hurts|is hurting|discomfort)|stomachaches?|tummy (?:pain|ache|hurts)|belly (?:pain|ache|hurts)",
        "pains? in (?:my |the )?(?:stomach|abdomen|belly|tummy)|(?:lower )?abdomen (?:hurts|pain)|my stomach (?:hurts?|aches?|is hurting)",
        "(?:stomach|tummy|belly|abdomen) (?P<neg>doesn't |does not |isn't |is not |don't |aren't )?(?:hurt|hurts|ache|aches|aching|hurting|is hurting|are hurting)")),
    ("pelvic_pain", None, "pelvic pain", (
        "pelvic (?:pain|discomfort|cramps?|pressure|ache|heaviness)|pains? in (?:my |the )?pelvi\\w+|(?:pressure|discomfort) in (?:my |the )?pelvi\\w+",)),
    ("cramps", None, "cramps", ("cramps?|cramping|period pains?|menstrual (?:pain|cramps?)|period cramps?",)),
    ("bloating", None, "bloating", ("bloat\\w*",)),
    ("fatigue", None, "fatigue", (
        "fatigue\\w*|tired\\w*|exhaust\\w+|(?:low|lower|less|reduced|no) energy|energy (?:was |is |has been |felt )?(?:low|lower|down|drained)|lethargi\\w+|drained|worn out|sluggish|run[\\s-]?down",)),
    ("fever", None, "fever", (
        "fevers?|feverish|running a (?:high )?temperature|high temperature",
        # a measured fever (>= 38.0 C / 100.4 F); normal readings never create a fever fact
        "(?:temp(?:erature)?|thermometer(?: reading)?) (?:is |was |of |at |reads |read |reading |came (?:out )?(?:to|at) )?(?:38(?:\\.\\d)?|100\\.[4-9]|10[0-2](?:\\.\\d)?)(?![\\d:])(?: ?°)?(?: ?(?:degrees|c|f)\\b)?")),
    ("cough", None, "cough", ("cough\\w*",)),
    ("sore_throat", None, "sore throat", (
        "sore throat|throat (?:pain|ache|hurts|is sore)|scratchy throat",
        "throat (?P<neg>doesn't|does not|isn't|is not|don't) (?:hurt|ache|hurting|feel sore)")),
    ("back_pain", None, "back pain", (
        "(?:lower )?back (?:pain|aches?)|backaches?|pains? in (?:my |the )?(?:lower )?back|my back (?:hurts|aches)",
        "back (?P<neg>doesn't |does not |isn't |is not |don't )?(?:hurt|hurts|ache|aches|aching|hurting)")),
    ("joint_pain", None, "joint pain", (
        "joint (?:pain|aches?|stiffness)|(?:achy|aching|sore|stiff|swollen) joints?|(?:knee|hip|shoulder|elbow|wrist|ankle|neck) (?:pain|aches?)|arthralgia",
        "(?:knees?|hips?|shoulders?|elbows?|wrists?|ankles?|joints?) (?P<neg>doesn't |does not |isn't |is not |don't |aren't )?(?:hurt|hurts|ache|aches|aching|hurting|is hurting|are hurting)")),
    ("muscle_pain", None, "muscle pain", (
        "muscle (?:pain|aches?|soreness|cramps?)|(?:sore|aching|achy) muscles?|myalgia|body (?:aches?|pains?)",
        "muscles? (?P<neg>doesn't |does not |isn't |is not |don't |aren't )?(?:hurt|hurts|ache|aches|aching|hurting|are hurting|is hurting)")),
    ("palpitations", None, "palpitations", (
        "palpitations?|(?:racing|pounding|fluttering|irregular) (?:heart|heartbeat|pulse)|skipped (?:a )?heartbeats?",
        "heart (?:(?P<neg>isn't|is not|doesn't|does not|wasn't|is never) )?(?:is )?(?:racing|pounding|fluttering|skipping|skips)")),
    ("spotting", None, "spotting", ("spotting",)),
    ("unusual_bleeding", None, "unusual bleeding", (
        "(?:unusual|abnormal|unexpected|irregular|excessive|breakthrough) (?:vaginal |menstrual )?bleeding|bleeding between (?:my )?periods|(?:vaginal|rectal) bleeding|blood in (?:my |the )?(?:stool|urine|poop)|bloody (?:stool|urine)|post[\\s-]?coital bleeding",)),
    ("anxiety", None, "anxiety", ("anxi\\w+|panic(?: attacks?)?|panicky",)),
    ("low_mood", None, "low mood", (
        "low mood|depress\\w+|hopeless\\w*|(?:feel|feeling|felt) (?:(?:really|very|so|quite|pretty|rather|extremely|a bit|a little|kind of) )?(?:sad|down|low|blue)|sad|sadness|tearful",)),
    ("insomnia", None, "insomnia", (
        "insomnia|(?:can't|couldn't|cannot|could not|can not|unable to) sleep|trouble sleeping|difficulty (?:falling |getting )?(?:to )?sleep\\w*|sleepless|barely slept",)),
    ("diarrhea", None, "diarrhea", ("diarrh?o?ea|loose (?:stools?|motions?)|watery stools?",)),
    ("constipation", None, "constipation", ("constipat\\w+",)),
    ("rash", None, "rash", ("rash(?:es)?|hives|itchy skin",)),
    ("swelling", None, "swelling", ("swelling|swollen|oedema|edema",)),
    ("numbness", None, "numbness", ("numb\\w*|tingling|pins and needles",)),
    ("blurred_vision", None, "blurred vision", (
        "bl(?:urred|urry) vision|vision (?:is |was )?blurr\\w+|double vision|vision (?:changes?|loss)|loss of vision|can't see (?:properly|clearly)",)),
    # Eyes. Everyday wording only: sudden loss of vision stays a RED stroke pattern (see stroke_signs), never a plain eye symptom.
    # Hinglish spellings ride along (aankh / aankhen / aankhon): "aankhon mein jalan" = burning eyes.
    ("eye_strain", None, "eye strain", (
        "eye[\\s-]?strain|digital eye strain|(?:tired|strained|fatigued|burning|heavy) eyes?|eyes? (?:are |feel |feels |is |get |gets |were )?(?:tired|strained|fatigued|burning|heavy)|eyes? burn\\w*",
        "aa?nkh(?:e|en|ein|on)? (?:(?:mein|me|mai|main|ma) )?(?:jalan|jalna|jal rah\\w*|thak\\w*|thaki|thakan|bhaari|bhari)",)),
    ("dry_eyes", None, "dry eyes", (
        "dry (?:and \\w+ )?eyes?|eyes? (?:are |feel |feels |is |get |gets |were )?(?:dry|gritty|scratchy)|dry eye syndrome",
        "aa?nkh(?:e|en|ein|on)? (?:(?:mein|me|mai|main|ma) )?(?:sukh\\w*|sookh\\w*|dryness)",)),
    ("red_eye", None, "red eyes", (
        "red[\\s-]?eyes?(?! flight)|bloodshot eyes?|eyes? (?:are |look |looks |is |turned |went |were |got )?(?:red|bloodshot|pink)|pink eye|conjunctivitis",
        "aa?nkh(?:e|en|ein|on)? (?:(?:mein|me|mai|main|ma|ka|ki|ke) )?(?:laa?l\\w*|gulabi)",)),
    ("eye_pain", None, "eye pain", (
        "eye (?:pain|ache|aches|soreness)|(?:pain|ache|pressure) (?:in|behind) (?:my |the |both |one )?eyes?|eyes? (?:hurt|hurts|hurting|ache|aches|aching|are sore|is sore|feel sore)|sore eyes?",
        "aa?nkh(?:e|en|ein|on)? (?:(?:mein|me|mai|main|ma) )?(?:\\w+ )?(?:dard|dardh|drd|dukh\\w*)",)),
    ("eye_itch", None, "itchy eyes", (
        "itchy,? (?:and )?(?:watery |red )?eyes?|eyes? (?:are |feel |feels |is |get |gets |were )?(?:itchy|itching|watery|watering)|watery eyes?|itchy eye",
        "aa?nkh(?:e|en|ein|on)? (?:(?:mein|me|mai|main|ma) )?(?:khujl\\w*|khujal\\w*|paani|pani)|aa?nkh(?:e|en|ein|on)? se (?:paani|pani)",)),
    ("period", None, "period", (
        "(?:still |currently )?bleeding (?:today|now|again)|(?:still|currently) bleeding",
        "(?:cycle|period) day \\d{1,2}|day \\d{1,2} of (?:my )?(?:period|cycle)|menstruat\\w+",
        # "my"/"the" stay OUTSIDE the mention: a possessive starts a new clause in a negated list
        "periods?(?! pains?| cramps?)|(?:flow|bleeding) (?:is|was) (?:light|moderate|medium|heavy)")),
    ("medication_use", None, "medication", (
        "(?:medications?|medicines?|meds|pills?|tablets?|supplements?|painkillers?)",
        "(?:took|taking|take|taken|popped|swallowed|had|started|using|on) (?:my |some |a |an |the |one |two |\\d+ )?(?:\\d+ ?(?:mg|mcg|g|iu) )?(?P<name>" + MEDICATION_NAME_PATTERN + ")(?: (?:supplements?|tablets?|pills?|capsules?))?")),
)

# Stated-normal expressions: negation phrased positively.
#: (concept, pattern, context regex that must match the 40 characters before the match, or None)
_NORMAL_SRC: tuple[tuple[str, str, str | None], ...] = (
    ("shortness_of_breath", "breathing (?:is |feels |has been |was |seems )?(?:normal|fine|ok|okay|easy|comfortable|regular|good|clear)|(?:i'm|i am|i can|i was|i've been|i have been) breathing (?:normally|fine|well|easily|comfortably)|breathe (?:normally|fine|easily)", None),
    ("chest_pain", "chest (?:feels |is |seems )(?:fine|normal|ok|okay|clear|comfortable)", None),
    # "my period hasn't started (yet)": the period is explicitly NOT happening
    ("period", "periods?(?: (?:still|even))? (?:hasn't|has not|didn't|did not|isn't|is not|haven't|have not|still hasn't|hasn't even) (?:started|begun|begin|come|arrived|arrive|showed up|due|here|on)(?: yet| this month| today)?", None),
    # "bleeding is light, not heavy": only with a bleeding context, so "the bag is not heavy" never counts
    ("heavy_bleeding", "not (?:that |very |too |so |really )?heavy", r"(?:bleed|flow|period|spotting|pads?|tampons?)"),
)


def _p(pattern: str) -> str:
    return pattern.replace(" ", r"[\s\-]+")


def _compile(patterns: Iterable[str]) -> re.Pattern[str]:
    return re.compile(r"\b(?:" + "|".join(_p(p) for p in patterns) + r")\b", re.I)


# Hinglish/Devanagari red flags share concept, tier and label with the English entries (Devanagari is transliterated first).
_LEX = tuple((c, t, l, _compile(ps)) for c, t, l, ps in _LEX_SRC + _hi.LEXICON)
_NORMAL = tuple((c, _compile([p]), re.compile(ctx, re.I) if ctx else None) for c, p, ctx in _NORMAL_SRC)

# --------------------------------------------------------------------------
# Trigger tables
# --------------------------------------------------------------------------

_NEG_PRE = re.compile(
    r"\b(?:nothing like|not like|no (?:signs?|history|trace|evidence) of|no(?!\s+longer\b)(?!\s*[,.!?]|\s*$)|not(?!\s+(?:any\s?more|only|just|sure|certain|clear)\b)|never|without|denies|denied|deny|denying|"
    r"negative for|free (?:of|from)|absence of|zero|nil|none of (?:the following|these|them|those)|neither|"
    r"don't (?:really )?think (?:i |that i )?(?:have|am|had)?|"
    r"(?:don't|doesn't|didn't|haven't|hasn't|hadn't|isn't|aren't|wasn't|weren't|won't|wouldn't|couldn't|shouldn't|ain't|cannot|can't)|"
    r"(?:do|does|did|have|has|had|am|is|are|was|were|will|would|could|should|can) not)\b", re.I)

_NEG_POST = re.compile(
    r"\s*(?:[:\-–—=(\[]\s*|\?\s*|(?:is|was|are|were|has been)\s+)"
    r"(?:none|nope|nil|negative|absent|denied|not present|nothing|n/a|"
    r"no(?!\s+(?:longer|more|one|body|idea|doubt|change|relief|improvement|matter)\b)|0(?:\s*/\s*10)?(?![\d.]))(?![\w])", re.I)

_BARE_NO_AFTER = re.compile(r"\s+(?:none|nope|nil|negative)(?![\w])|\s+no(?=\s*(?:[,.;)]|$))", re.I)

_PSEUDO_NEG = re.compile(
    r"(?:no|not|never)\s+(?:change|relief|improvement|improving|better|worse|difference|reduction|"
    r"getting better|going away|gone|only|just|doubt|really any (?:better|improvement))\b", re.I)
_UNTIL_NOW = re.compile(r"\b(?:until|till|before)\s+(?:just\s+)?(?:now|today|this|a few|a (?:minute|moment|while)|tonight|last night|this morning)", re.I)
_FIRST_TIME = re.compile(r"\bnever\b[^.?!]{0,40}\bbefore\s+(?:today|now|this|tonight)", re.I)
_DENIED_CLAIM = re.compile(
    r"\bi (?:never|didn't|did not) (?:say|said|mention(?:ed)?|tell|told|claim(?:ed)?|write|wrote)\b(?:\s+(?:that|you))?\s+(?:i|i'm|i've)\b", re.I)
_UNCERTAIN_NEG = re.compile(r"(?:can't|cannot|can not|couldn't)\s+(?:really\s+)?(?:say|tell|claim|swear)(?:\s+that)?(?:\s+i)?(?:\s+(?:have|had|am|feel|felt))?\s*$", re.I)

_POSSIBLE = re.compile(
    r"\b(?:maybe|perhaps|possibly|probably|might|may be|could be|i think|i guess|i suspect|i believe|seems?|"
    r"not (?:very |totally |entirely )?(?:sure|certain)|unsure|uncertain|can't (?:tell|say)|cannot (?:tell|say)|"
    r"don't know (?:if|whether)|not clear|no idea (?:if|whether)|wonder(?:ing)? (?:if|whether)|or maybe)\b", re.I)

# "if/whether" after a doubt verb is uncertainty about the symptom itself ("not sure if it's chest pain"), not a condition.
_IF_AFTER_DOUBT = re.compile(
    r"\b(?:not (?:very |totally |entirely )?(?:sure|certain)|unsure|uncertain|wonder(?:ing)?|don't know|do not know|can't tell|cannot tell|can't say|"
    r"ask(?:ing)?|see|check(?:ing)?|know|no idea|curious|confused|doubt)\s+(?:\w+\s+){0,2}$", re.I)

_HYPO = re.compile(
    r"\b(?:what if|if|in case|suppose|supposing|should i (?:get|develop|have|start|begin|experience|feel)|when to worry|"
    r"in the event|once i get|might develop|could develop|may develop|in the future|going to get|"
    r"let'?s say|imagine (?:i|if|that i)|hypothetically|pretend|"
    r"worried (?:i|that i)(?:'ll| will| might| may)? (?:get|have|develop))\b", re.I)
# "say I had a headache every day..." only as a sentence opener, never "they say I have ..."
_HYPO_SAY = re.compile(r"^\W*say,? (?:i|that i)\b|,\s*say,? (?:i|that i)\b", re.I)
# a future auxiliary directly governing the symptom ("I'll probably get a headache", "tomorrow I might get ...")
_FUTURE_EXP = re.compile(
    r"\b(?:(?:tomorrow|next (?:week|month|day|year)|later today|this weekend)\s*,?\s*(?:i\s+)?(?:might|may|could|would|will|'ll)\s+|"
    r"(?:i'll|i will|i'm going to|i am going to|i'm gonna|i am gonna|going to|gonna|will)\s+)"
    r"(?:probably |definitely |likely |possibly |maybe |just |also |then )?(?:get|have|develop|feel|experience|catch|start|begin|be having)\b", re.I)
_FUTURE_TIME = re.compile(r"\b(?:tomorrow|next (?:week|month|day|year)|later today|this weekend)\b", re.I)
# a bare hedge closing the sentence ("... short of breath, maybe?"). Not "probably just anxiety": that hedges the CAUSE.
_TRAIL_HEDGE = re.compile(r"[,\s]+(?:maybe|perhaps|possibly|i think|i guess|i suppose|i believe|not sure|or something|or so i think)\W*$", re.I)
# "I wish I didn't have X" is a wish, not a denial; "I hope I don't have X" is uncertainty, not a denial.
_WISH = re.compile(r"\b(?:wish(?:ed|ing)?|if only|i'd rather|i would rather)\b(?:\s+\w+){0,3}\s*$", re.I)
_HOPE = re.compile(r"\b(?:hope|hoped|hoping|pray(?:ing)?)\b(?:\s+\w+){0,3}\s*$", re.I)
_FEAR_ABOUT = re.compile(r"\b(?:worried|worry|worrying|afraid|scared|terrified|fear|fearful|concerned|anxious|nervous|paranoid)\s+(?:about|of|over)\b", re.I)
_FEAR_THAT_I = re.compile(r"\b(?:worried|afraid|scared|terrified|fear|concerned|anxious|nervous)\s+(?:that\s+)?(?:i'm|i am|i've|i have)\b", re.I)
_WORSEN = re.compile(
    r"\s+(?:gets? (?:worse|bad|stronger|more)|worsens?|persists?|continues?|doesn't (?:go away|improve|stop|get better)|does not (?:go away|improve|stop|get better)|"
    r"keeps? (?:getting|coming|happening)|is getting worse|isn't (?:getting better|improving|going away))", re.I)

_QSTART = r"(?:can|could|does|do|did|is|are|am|was|were|will|would|should|why|what|how|when|where|who|which|any)"
# (?![\w']) keeps contractions out: "can't breathe" starts with the *statement* "can't", never with the question word "can"
_Q_AT_START = re.compile(r"^\W*" + _QSTART + r"(?![\w'])", re.I)
_Q_AFTER_COMMA = re.compile(r",\s*(?:and\s+)?" + _QSTART + r"(?![\w'])", re.I)
_SELF_IN_QUESTION = re.compile(
    r"\b(?:do|did|am|have|has|why (?:do|am|have|did)|how come)\s+i\s+(?:have|having|had|get|getting|feel|feeling|keep|been|experience|experiencing)\b|"
    r"\bwhy (?:is|does|are|do) my\b|\bmy\b[^?.!]{0,30}\b(?:hurts?|aches?|aching|sore|pounding|burning|cramping)\b", re.I)

# Attribution: something a clinician / leaflet / website / document SAYS is not something the user REPORTS.
_ADV_SOURCE = (
    r"(?:(?:my |the |a |our )?(?:doctor|dr\.?(?:\s+\w+)?|nurse|physician|gp|specialist|pharmacist|clinician|cardiologist|gynecologist|gynaecologist|midwife|"
    r"therapist|surgeon|consultant|professor|paramedic|dentist)|"
    r"(?:my |the |our )?(?:discharge\s+(?:papers|paperwork|sheet|summary|instructions|notes)|pamphlet|handout|brochure|leaflet|label|website|article|app|internet|"
    r"google|book|papers?|reports?|printout|guidelines?|nhs|who|cdc|"
    # documents and examples (not the user's own body): "the example dataset contains chest pain"
    r"(?:\w+ )?(?:example|dataset|data set|sample|case study|textbook|spreadsheet|template|quiz|exam question|test question|handbook|manual|chart|table|study|script|story|novel|movie|film)))")
_ADV_VERB = (
    r"(?:has |had |have )?(?:told|said|says|say|asked|advised|warned|warns|mentioned|mentions|recommended|recommends|explained|explains|suggested|suggests|"
    r"wrote|writes|noted|notes|instructed|reminded|lists?|listed|describes?|described|states?|stated|shows?|showed|reports?|reported|includes?|included|indicates?|indicated|contains?|contained)")
_ADVICE_SOURCE = re.compile(
    r"\b" + _ADV_SOURCE + r"\s+" + _ADV_VERB + r"\b|"
    r"\b(?:told|advised|warned|reminded) me to (?:watch|look|call|be alert|keep an eye|monitor|seek|get help)\b|"
    r"\b(?:i )?(?:have )?(?:read|saw|heard|learned|learnt|found out|was told)(?: online| somewhere| in an article| on the internet| on google| in a book| on \w+)? that\b", re.I)
# Generic educational wording. In a question ("What are the signs of a stroke?") it asks, it does not quote.
_ADVICE_GENERIC = re.compile(
    r"\b(?:watch(?: out)? for|look(?: out)? for|keep an eye out for|be alert for|signs? of|symptoms? of|warning signs?|red flags?|seek (?:help|care) if|call (?:me|us|them|someone) if)\b", re.I)
from contextvars import ContextVar  # noqa: E402
_MSG_FIRST_PERSON: ContextVar = ContextVar("msg_first_person", default=False)  # set per analyze() call
_GENERIC_PREDICATE = re.compile(
    r"\s*(?:is|are|can be|may be|could be|might be|is often|is usually|is commonly|are often|are usually)\s+(?:a |an |one |the |also |often |usually |commonly )*"
    r"(?:(?:common|possible|typical|early|major|classic|potential|key|main)\s+)*(?:symptoms?|signs?|causes?|features?|indicators?|side effects?|complications?)\s+of\b", re.I)
_INVERTED_Q = re.compile(r"\b(?:did|does|do|would|will|can|could|should)\s+$", re.I)
# the user's own possessive right before the mention ("my chest pain"): the doctor's words do not make it someone else's
_OWN_POSSESSIVE = re.compile(r"\bmy\s+(?:\w+\s+)?$", re.I)

_OTHER_SUBJ = re.compile(
    r"\b(?:(?:my|our|his|her|their) )?(?:sister|brother|mom|mum|mother|dad|father|husband|wife|partner|friend|son|daughter|baby|child|kids?|grandmother|grandma|"
    r"grandfather|grandpa|colleague|coworker|boyfriend|girlfriend|aunt|uncle|cousin|roommate|neighbou?r|boss|teacher|patient|family|someone|somebody|everyone|he|she|they)\b", re.I)
_OTHER_VERB = re.compile(r"[a-z']{2,}", re.I)   # any word counts as the verb: "my coworker fainted", "my sister wants to ..."
_FIRST_PERSON = re.compile(r"\b(?:i|i'm|i've|i'd|i'll|me|my|mine|myself|we|us|our)\b", re.I)
_SELF_IN_MENTION = re.compile(r"\b(?:me|my|myself|mine|i)\b", re.I)
_FAMILY_HISTORY = re.compile(r"\b(?:family history of|runs in (?:my |the )?family|hereditary)\b", re.I)

# Hindi/Hinglish cues (vocabulary in hinglish_terms). Consulted only for sentences that look Hindi (_HI_GATE),
# so English sentences take exactly the same path as before.
(_HI_GATE, _HI_NEG_POST, _HI_PRE_NEG, _HI_HYPO, _HI_OTHER, _HI_SELF, _HI_COMM, _HI_POSS, _HI_WORSEN, _HI_Q_START, _HI_Q_END,
 _HI_GENERIC, _HI_FAMILY, _HI_HISTORY, _HI_CLAUSE, _HI_OLD, _HI_PAST, _HI_RECURRING, _HI_RESOLVED_AFTER, _HI_RESOLVED_CLAUSE,
 _HI_CURRENT, _HI_SAME_DAY, _HI_PAST_TENSE, _HI_BUT_NOW, _HI_REPORT_VERB) = (re.compile(p, re.I) for p in (
    _hi.GATE, _hi.NEG_POST, _hi.PRE_NEG, _hi.HYPO, _hi.OTHER, _hi.SELF, _hi.COMM, _hi.POSS, _hi.WORSEN, _hi.Q_START, _hi.Q_END,
    _hi.GENERIC, _hi.FAMILY, _hi.HISTORY, _hi.CLAUSE, _hi.OLD, _hi.PAST, _hi.RECURRING, _hi.RESOLVED_AFTER, _hi.RESOLVED_CLAUSE,
    _hi.CURRENT, _hi.SAME_DAY, _hi.PAST_TENSE, _hi.BUT_NOW, _hi.REPORT_VERB))

_RESOLVED = re.compile(
    r"\b(?:gone|went away|go(?:es)? away|passed(?! out)|subsided|resolved|stopped|ceased|settled|cleared(?: up)?|disappeared|faded|eased|ended|finished|"
    r"(?:is|are|was|were|it's) over|no longer|not any\s?more|isn't there any\s?more|better now|fine now|ok now|okay now|normal now|"
    r"doing (?:well|fine|ok|okay|better|great)|(?:it|fever|pain|headache|nausea) broke|came down|went down)\b", re.I)
# a resolution word is void when something negates it just before: "isn't gone", "hasn't passed", "never stopped"
_RES_NEGATOR = re.compile(r"(?:\bnot|n't|\bnever|\bnor|\bno)\s+(?:\w+\s+){0,1}$", re.I)
_RES_SELF_NEGATIVE = frozenset({"no longer", "not anymore", "not any more", "isn't there anymore", "isn't there any more"})


def _resolved(text: str) -> bool:
    """True if `text` says something has ended - and does not negate that ending ("isn't gone")."""
    for r in _RESOLVED.finditer(text):
        word = r.group(0).lower()
        if word in _RES_SELF_NEGATIVE or word.startswith(("no longer", "not any", "isn't there")):
            return True
        if not _RES_NEGATOR.search(text[max(0, r.start() - 18):r.start()]):
            return True
    return False


_SELF_OK_RX = re.compile(
    r"\b(?:i'm|i am|i feel|i'm feeling|i am feeling|feeling|feel|now i'm|am)\s+(?:fine|ok|okay|well|good|great|better|normal|alright|all right|back to normal)\b", re.I)


class _SelfOk:
    """`.search(text)` for "I'm fine" / "I feel better", but not when negated ("I don't feel well", "I'm not fine")."""

    @staticmethod
    def search(text: str) -> bool:
        for r in _SELF_OK_RX.finditer(text):
            if not _RES_NEGATOR.search(text[max(0, r.start() - 14):r.start()]):
                return True
        return False


_SELF_OK = _SelfOk()

_TIME_STRONG_CURRENT = re.compile(
    r"\b(?:now|right now|currently|at the moment|at present|presently|still|ongoing|constant(?:ly)?|continues?|"
    r"since (?:this )?(?:morning|yesterday|last night|an? hour|\d+)|for the (?:past|last) (?:\d+|few|couple)|"
    r"all (?:day|morning|night|afternoon|evening)|just (?:started|began)|started (?:just )?(?:now|today)|again)\b", re.I)
_TIME_RECENT = re.compile(
    r"\b(?:earlier(?: today| this (?:morning|afternoon|evening))?|this (?:morning|afternoon|evening)|last night|tonight|today|"
    r"(?:a (?:few|couple of) (?:minutes|hours|moments)|(?:\d+|an?|one|two|three|four|five|six|seven|eight|nine|ten|few|couple) (?:minutes?|mins?|hours?|hrs?)) ago|"
    r"just now|moments ago|recently|lately|the other (?:day|night))\b", re.I)
_TIME_SAME_DAY = re.compile(
    r"\b(?:earlier|this (?:morning|afternoon|evening)|tonight|today|(?:a (?:few|couple of) (?:minutes|hours|moments)|(?:\d+|an?|one|two|three|four|five|six|seven|eight|nine|ten|few|couple) (?:minutes?|mins?|hours?|hrs?)) ago|just now|moments ago)\b", re.I)
_WEEKDAY = r"(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
_TIME_PAST = re.compile(
    r"\b(?:yesterday|day before yesterday|(?:\d+|a|an|one|two|three|four|five|six|seven|eight|nine|ten|few|couple of|several) (?:days?|weeks?|months?|years?) ago|"
    r"last (?:week|month|year|time|weekend|summer|winter|" + _WEEKDAY + r")|(?:on|this past|last) " + _WEEKDAY + r"|"
    r"previously|in the past|used to|years ago|a while (?:ago|back)|long ago|"
    r"when i was (?:a )?(?:child|kid|young|younger|little|teen\w*)|as a (?:child|kid|teen\w*)|back in \d{4}|in (?:19|20)\d{2}|history of|years back)\b", re.I)
# Long ago (not just "a few days ago"): wins over "it resolved" - the episode is history either way.
_AGE_NUM = r"(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|\d{1,2})"
_TIME_OLD = re.compile(
    r"\b(?:(?:\d+|a|an|one|two|three|four|five|six|seven|eight|nine|ten|few|couple of|several|many) (?:months?|years?|decades?) ago|years ago|months ago|long ago|a long time ago|"
    r"years back|used to|history of|as a (?:child|kid|teen\w*|baby|toddler)|"
    r"when i was (?:a |an )?(?:" + _AGE_NUM + r"(?: years old)?|young\w*|little|small|child\w*|kid|teen\w*|baby|toddler|student|pregnant|in (?:school|college|high school)|"
    r"about \d+|around \d+|\w+ years old))\b", re.I)
# these need a past-tense verb in the same clause, otherwise "headache at school today" would read as history
_TIME_OLD_CTX = re.compile(
    r"\b(?:(?:in|during) (?:college|university|high school|middle school|grade school|school|childhood|my (?:childhood|teens|twenties|youth|school days))|"
    r"back in (?:19|20)\d{2}|in (?:19|20)\d{2}|at age " + _AGE_NUM + r")\b", re.I)
# "my dad had chest pain at 45": an age, never a clock time ("at 3pm", "at 10:30")
_AT_AGE = re.compile(r"\bat (?:the age of )?\d{2}\b(?!\s*(?::|am\b|pm\b|a\.m|p\.m|o'clock|min|hour|hr|sec|bpm|%|/|degrees|steps|\d))", re.I)
_PAST_VERB = re.compile(r"\b(?:had|was|were|got|developed|suffered|started|diagnosed|died|passed away|collapsed|fainted|survived)\b", re.I)
_TIME_RECURRING = re.compile(
    r"\b(?:sometimes|often|usually|frequently|occasionally|regularly|repeatedly|recurr\w+|periodically|intermittent\w*|on and off|off and on|now and then|"
    r"from time to time|every (?:day|night|morning|week|month|time|period|cycle)|each (?:time|month|period|cycle)|whenever|most (?:days|nights|mornings)|"
    r"once in a while|(?:\d+|once|twice|three times|several times|a few times) (?:a|per|each) (?:day|week|month)|chronic\w*|"
    r"come(?:s)? and go(?:es)?|coming and going|keeps? (?:having|getting|happening|coming)|"
    r"when(?:ever)? (?:i )?(?:climb\w*|exercis\w*|walk\w*|run\w*|work\w* out|lift\w*|exert\w*|stand\w*|stood|sit\w*|lie|lying|bend\w*|wake|waking|eat\w*|cough\w*|sneez\w*|turn\w*|ris\w+|get up|getting up)|"
    r"on (?:the )?stairs|up (?:the )?stairs)\b", re.I)
# habitual present simple ("I get dizzy", "do I get headaches"): no 'now'/'currently' - a pattern, not an event
_HABITUAL_GET = re.compile(r"\b(?:i|we) get(?:\s+\w+){0,2}\s*$", re.I)
_NOW_EXPLICIT = re.compile(r"\b(?:now|right now|currently|at the moment|at present|presently|ongoing|constant(?:ly)?)\b", re.I)
_REITERATE = re.compile(r"\bi (?:just |already |clearly |literally )?(?:said|told you|mentioned|stated|typed|wrote)\b", re.I)
_PRESENT_PERFECT = re.compile(r"\b(?:i've|i have|have|has|'ve)\s+(?:been |had |got |felt |gotten )", re.I)
_PAST_TENSE = re.compile(r"\b(?:had|felt|was|were|got|experienced|developed|woke up with|suffered|noticed|started|began|came|went|took|taken|popped|swallowed|drank|ate)\b", re.I)

_SEV_NUM = re.compile(r"(\d{1,2})\s*(?:/|out of)\s*10\b")
_SEV_LEVEL = re.compile(r"\b(?:pain level|severity|intensity|pain score)\s*(?:is|was|of|:)?\s*(\d{1,2})\b", re.I)
_SEV_WORDS = (
    ("severe", re.compile(r"\b(?:severe|excruciating|unbearable|intense|agonizing|agonising|terrible|awful|worst|extreme|very bad|crippling)\b", re.I)),
    ("moderate", re.compile(r"\b(?:moderate|medium|bad|strong|significant)\b", re.I)),
    # not "faint": "chest pain and I feel faint" is a second symptom, not a mild one
    ("mild", re.compile(r"\b(?:mild|slight|minor|light|little|small|faint (?:pain|ache|discomfort|tightness|pressure)|a bit of|a little)\b", re.I)),
)

_SENT_END = re.compile(r"(?<=[.!?;])\s+")
_ABBREV = re.compile(r"\b(dr|mr|mrs|ms|prof|vs|approx|st)\.(?=\s)|\b(e\.g|i\.e)\.", re.I)
_SEGMENT_SPLIT = re.compile(r"\b(?:but|however|although|though|except(?: for)?|yet|whereas|apart from|aside from|other than|nevertheless)\b", re.I)
_QA_ANSWER_NO = re.compile(r"^\W*(?:(?:i )?(?:said|say|meant|told you|answered) )?(?:no|none|nope|nah|nil|negative|nothing|neither)\W*$", re.I)
_QA_ANSWER_YES = re.compile(
    r"^\W*(?:yes|yeah|yep|yup|affirmative|sure|a bit|a little|some)\b(?:\W+(?:mild|mildly|slight|slightly|a bit|a little|some|sometimes|kind of|just|only|quite|very|really|pretty|moderate|bad|severe|\d{1,2}\s*(?:/|out of)\s*10)){0,3}\W*$", re.I)
# "I don't." / "I do not." / "I'm not." standing alone: the user denies what was just said
_SELF_ELLIPSIS = re.compile(
    r"^\W*(?:(?:no|nope|nah|well)[,.!\s]+)?i(?:'m| am)?\s*(?:don't|do not|haven't|have not|never|didn't|did not|am not|'m not|not)\W*(?:either|though|myself|at all|however)?\W*$", re.I)

_FILLER_FIRST = frozenset("""any a an the of my your kind sort type signs sign symptoms symptom history such as like current noticeable new other additional much real
particular specific at all in on with for from to and or nor feel feeling felt have having had got get getting been experiencing experience experienced notice noticing
noticed seen see really even ever very too that so particularly especially overly significant major serious obvious unusual abnormal slightest slight least bit single
more also take taking taken took use using used need needing needed
thinking thought thoughts planning plans plan intend intending intention considering about currently actually honestly seriously
going gonna want wanting wish trying tempted way ways risk danger""".split())
# "my"/"your" start a NEW noun phrase in a list ("No cramps today, and my period is light"): never list glue
_FILLER_LIST = frozenset("""any a an the of and or nor also other new more unusual abnormal severe mild moderate intense persistent constant frequent sudden bad
terrible slight significant noticeable no""".split())
_HEDGE_FIRST = _FILLER_FIRST | frozenset(
    "i i'm i've i'll i'd it's its it this that is am 'm m might may be there something some if whether maybe perhaps possibly probably few little couple but".split())
_PUNCT_OK = frozenset(",;:/&+-–—()")


# --------------------------------------------------------------------------
# Data model
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Fact:
    concept: str
    assertion: str
    temporal: str
    severity: int | None
    severity_label: str | None
    experiencer: str
    certainty: str          # explicit | hedged | default
    knowledge: str          # USER_REPORTED | USER_DENIED | POSSIBLE | HISTORICAL | NOT_A_SELF_REPORT
    confidence: float
    reason: str
    source: str
    source_text: str
    tier: str | None
    label: str
    same_day: bool
    detail: str | None
    sentence_index: int
    span: tuple[int, int]

    @property
    def present(self) -> bool | None:
        """True = user reports it, False = user explicitly denies it, None = neither."""
        if self.assertion == "present":
            return True
        if self.assertion == "negated":
            return False
        return None

    @property
    def active(self) -> bool:
        """A current/recent/recurring self-report (what safety and trackers care about)."""
        return (
            self.experiencer == "self"
            and self.assertion in {"present", "possible"}
            and self.temporal in {"current", "recent", "recurring", "unknown"}
        )

    def to_dict(self, *, include_text: bool = False) -> dict[str, Any]:
        out: dict[str, Any] = {
            "concept": self.concept, "present": self.present, "assertion": self.assertion,
            "temporal_status": self.temporal, "certainty": self.certainty, "knowledge": self.knowledge,
            "severity": self.severity, "severity_label": self.severity_label, "experiencer": self.experiencer,
            "confidence": round(self.confidence, 2), "reason": self.reason, "source": self.source,
        }
        if include_text:
            out["source_text"] = self.source_text
        return out


@dataclass
class _Mention:
    start: int
    end: int
    concept: str
    tier: str | None
    label: str
    text: str
    detail: str | None = None
    forced: str | None = None


# --------------------------------------------------------------------------
# Text preparation
# --------------------------------------------------------------------------

_CONTRACTIONS = {
    "dont": "don't", "cant": "can't", "wont": "won't", "didnt": "didn't", "doesnt": "doesn't", "havent": "haven't",
    "hasnt": "hasn't", "hadnt": "hadn't", "isnt": "isn't", "arent": "aren't", "wasnt": "wasn't", "werent": "weren't",
    "couldnt": "couldn't", "shouldnt": "shouldn't", "wouldnt": "wouldn't", "ive": "i've", "im": "i'm",
}
_CONTR_RX = re.compile(r"\b(" + "|".join(_CONTRACTIONS) + r")\b", re.I)
_MAX_CHARS = 8000


# "my chest still hurts", "chest is still hurting", "my head keeps hurting": a word between the body part and the verb
# hid the symptom from every body-part pattern (while "my chest hurts" was an emergency). "Still" and "keeps" only say the
# symptom continues now, which is already the default reading, so they are folded away before matching.
_STILL_RX = re.compile(r"\b(?:(is|are) still|still) (hurts?|hurting|aches?|aching|burns?|burning|throbbing|pounding|sore|tight|heavy)\b", re.I)
_KEEPS_RX = re.compile(r"\bkeeps? (hurting|aching|burning|throbbing|pounding)\b", re.I)
_KEEPS = {"hurting": "hurts", "aching": "aches", "burning": "burns", "throbbing": "is throbbing", "pounding": "is pounding"}
# The same in Hinglish: "seene mein abhi bhi dard hai" ("still" right before the pain word) hid the symptom too.
_ABHI_BHI_RX = re.compile(r"\b(?:abhi|ab) bhi (?=(?:dard|pain|jalan|takleef|taklif)\b)", re.I)


def normalize(text: str) -> str:
    t = _hi.transliterate((text or "")[:_MAX_CHARS])
    t = t.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    t = _CONTR_RX.sub(lambda m: _CONTRACTIONS[m.group(1).lower()], t)
    t = _STILL_RX.sub(lambda m: f"{m.group(1)} {m.group(2)}" if m.group(1) else m.group(2), t)
    t = _KEEPS_RX.sub(lambda m: _KEEPS[m.group(1).lower()], t)
    t = _ABHI_BHI_RX.sub("", t)
    return t


def split_sentences(text: str) -> list[str]:
    """Sentences, honouring line breaks and bullet lists; decimals/abbreviations are kept intact."""
    lines: list[str] = []
    for raw in normalize(text).replace("\r", "").split("\n"):
        line = re.sub(r"^\s*(?:[-*•–—]|\d{1,2}[.)])\s+", "", raw).strip()
        if not line:
            continue
        if lines and re.search(r"(?:,|\band|\bor|\bnor)\s*$", lines[-1], re.I):
            lines[-1] = lines[-1] + " " + line
        else:
            lines.append(line)
    out: list[str] = []
    for line in lines:
        protected = _ABBREV.sub(lambda m: m.group(0).replace(".", "\x01"), line)
        for part in _SENT_END.split(protected):
            part = part.replace("\x01", ".").strip()
            if part:
                out.extend(_split_long(part))
    return out


# Work is bounded by construction (re has no timeout): sentences are capped, and so is the
# number of mentions classified. Red-flag mentions get their own budget so a flood of
# harmless words can never crowd out a real "chest pain".
_MAX_SENTENCE = 1500
_MAX_MENTIONS_PER_SENTENCE = 40
_MAX_NONRED_TOTAL = 96
_MAX_RED_TOTAL = 32


def _split_long(part: str) -> list[str]:
    pieces: list[str] = []
    while len(part) > _MAX_SENTENCE:
        cut = max(part.rfind(",", 0, _MAX_SENTENCE), part.rfind(";", 0, _MAX_SENTENCE))
        if cut < _MAX_SENTENCE // 2:
            cut = part.rfind(" ", 0, _MAX_SENTENCE)
        if cut <= 0:
            cut = _MAX_SENTENCE
        pieces.append(part[:cut + 1].strip())
        part = part[cut + 1:].strip()
    if part:
        pieces.append(part)
    return pieces


# --------------------------------------------------------------------------
# Mention detection
# --------------------------------------------------------------------------

def _extra_rx(terms: Iterable[str]) -> tuple[tuple[str, re.Pattern[str]], ...]:
    out = []
    for term in list(dict.fromkeys(t.strip().lower() for t in terms if t and t.strip()))[:12]:
        term = term[:40]
        body = r"[\s\-]+".join(re.escape(w) for w in term.split())
        out.append((f"custom:{term}", re.compile(r"\b" + body + r"\b", re.I)))
    return tuple(out)


def _find_mentions(s: str, extra: tuple[tuple[str, re.Pattern[str]], ...] = ()) -> list[_Mention]:
    cand: list[_Mention] = []
    for cid, rx in extra:
        for m in rx.finditer(s):
            cand.append(_Mention(m.start(), m.end(), cid, None, cid[7:], m.group(0)))
    for concept, tier, label, rx in _LEX:
        for m in rx.finditer(s):
            groups = m.groupdict() if m.re.groupindex else {}
            detail = groups.get("name")
            # a negator inside the phrase itself ("stomach doesn't hurt") makes the mention a denial
            forced = "negated" if (groups.get("neg") or "").strip() else None
            cand.append(_Mention(m.start(), m.end(), concept, tier, label, m.group(0), detail.lower() if detail else None, forced))
    for concept, rx, ctx in _NORMAL:
        for m in rx.finditer(s):
            if ctx is not None and not ctx.search(s[max(0, m.start() - 40):m.start()]):
                continue
            cand.append(_Mention(m.start(), m.end(), concept, None, DISPLAY.get(concept, concept), m.group(0), None, "negated"))
    cand.sort(key=lambda x: (-(x.end - x.start), x.start))
    kept: list[_Mention] = []
    for c in cand:
        if not any(c.start < k.end and k.start < c.end for k in kept):
            kept.append(c)
    kept.sort(key=lambda x: x.start)
    return kept


def keyword_hits(text: str) -> list[tuple[str, str | None, str]]:
    """Raw red/urgent lexicon matches with NO context (concept, tier, label).

    Only for the fail-safe path when :func:`analyze` itself failed: it can say "something that
    looks like a red flag is in this message", never "the user has it".
    """
    t = normalize(text)
    return [(c, tier, label) for c, tier, label, rx in _LEX if tier and rx.search(t)]


def concept_for_text(text: str) -> str | None:
    """Canonical concept id for a free-text symptom/condition name (e.g. an AI-proposed event name)."""
    ms = _find_mentions(normalize(text))
    return ms[0].concept if ms else None


def _outside(spans: list[tuple[int, int]], m: re.Match[str]) -> bool:
    return not any(m.start() < e and s < m.end() for s, e in spans)


#: words that start a new clause or relate the symptom to something else; never an adjective.
_BLOCK = frozenset("""i i'm i've i'd i'll me myself we you he she they it its it's there this that these those but because since so then if when while
although though however yet for from about regarding after before during despite with without as than whether is are was were am be been being do does did
has have had having can could will would should may might must feel feeling felt get got getting take took slept ate drank walked
just only besides except plus thinking thought thoughts planning plans plan intend intending considering about""".split())


def _only(piece: str, allowed: frozenset[str], open_tail: int = 0) -> bool:
    """True if `piece` holds only filler/punctuation, optionally ending in up to `open_tail` modifier words.

    Modifiers ("no *sharp* chest pain", "no *knee* swelling") are part of the noun phrase, so up to two unknown
    alphabetic words directly before the concept do not end a negation scope unless they are clause starters.
    """
    toks = [t for t in re.findall(r"[\w']+|[^\w\s]", piece.lower()) if t not in _PUNCT_OK]
    word_idx = [i for i, t in enumerate(toks) if t not in allowed]
    tail = set(word_idx[-open_tail:]) if open_tail else set()
    for i, tok in enumerate(toks):
        if tok in allowed:
            continue
        # a modifier must sit right in front of the concept (its last two words): "not sleeping AND have chest pain" is two clauses
        if i in tail and i >= len(toks) - 2 and tok.isalpha() and len(tok) >= 3 and tok not in _BLOCK:
            continue
        return False
    return True


def _scope_reaches(s: str, t_end: int, mention: _Mention, spans: list[tuple[int, int]], first_ok: frozenset[str] | None,
                   max_first_words: int = 8, strict: bool = False) -> bool:
    """Does a trigger ending at `t_end` govern `mention`?

    The text between them may contain only filler words (first clause) and,
    after the first concept, only list glue (commas, and/or, adjectives): a new
    clause ("I feel tired") ends the scope. `strict` (crisis concepts) allows no free modifier words at all:
    "I'm not sleeping, thinking about hurting myself" must never read as a denial.
    """
    gap = s[t_end:mention.start]
    if re.search(r"[.?!;]", gap):
        return False
    tail = 0 if strict else 2
    pieces: list[str] = []
    pos = t_end
    for a, b in spans:
        if a >= t_end and b <= mention.start:
            pieces.append(s[pos:a])
            pos = b
    pieces.append(s[pos:mention.start])
    # "my X" opens a new noun phrase: it can never continue a negated list ("No headache, my chest hurts")
    if re.match(r"(?:my|your)\s", mention.text, re.I) and (len(pieces) > 1 or "," in gap):
        return False
    first = True
    for piece in pieces:
        parts = piece.split(",")
        for k, part in enumerate(parts):
            if first:
                first = False
                words = re.findall(r"[\w']+", part)
                if first_ok is None:
                    # "If you ask me, I have chest pain": the comma closes the if-clause, the mention is the main clause
                    if len(words) > max_first_words or (words and k < len(parts) - 1):
                        return False
                # a clause that ends in a comma is finished: "I don't feel well, chest pain" is not a denial
                elif not _only(part, first_ok, 0 if (k < len(parts) - 1 or strict) else tail):
                    return False
            elif not _only(part, _FILLER_LIST, tail):
                return False
    return True


# --------------------------------------------------------------------------
# Per-mention classification
# --------------------------------------------------------------------------

def _segment_of(segments: list[tuple[int, int]], pos: int) -> tuple[int, int]:
    for a, b in segments:
        if a <= pos < b:
            return a, b
    return segments[-1]


def _chunk_of(s: str, seg: tuple[int, int], pos: int) -> tuple[int, int]:
    a, b = seg
    left = max(s.rfind(",", a, pos), s.rfind(";", a, pos))
    right_c = s.find(",", pos, b)
    return (left + 1 if left >= a else a), (right_c if right_c != -1 else b)


def _severity(s: str, chunk: tuple[int, int], m: _Mention, seg_end: int | None = None,
              spans: list[tuple[int, int]] | None = None) -> tuple[int | None, str | None]:
    a, b = chunk
    after = s[m.end:b]
    before = s[a:m.start]
    num = None
    n = _SEV_NUM.search(after[:40])
    if n:
        num = int(n.group(1))
    else:
        lv = _SEV_LEVEL.search(after[:40])
        if lv:
            num = int(lv.group(1))
        else:
            n = None
            for cand in _SEV_NUM.finditer(before[-18:]):
                n = cand
            if n:
                num = int(n.group(1))
    if num is None and seg_end is not None and b < seg_end and s[b:b + 1] == ",":
        # "Headache is back, 3/10." / "My stomach pain is unbearable, 10/10.": the rating follows in the next comma chunk,
        # provided that chunk talks about no other symptom.
        nxt_end = s.find(",", b + 1, seg_end)
        nxt_end = seg_end if nxt_end == -1 else nxt_end
        if not any(b < x and y <= nxt_end for x, y in (spans or ())):
            nn = _SEV_NUM.search(s[b + 1:nxt_end][:30])
            if nn:
                num = int(nn.group(1))
    if num is not None and not 0 <= num <= 10:
        num = None
    label = None
    if num is not None:
        label = "none" if num == 0 else "mild" if num <= 3 else "moderate" if num <= 6 else "severe"
    else:
        window_before = " ".join(before.split()[-4:])
        window_after = " ".join(after.split()[:3])
        for name, rx in _SEV_WORDS:
            if rx.search(window_before) or rx.search(window_after) or rx.search(m.text):
                label = name
                break
    return num, label


#: single events (not ongoing symptoms): "I fainted this morning and still feel off" is a recent event, not a current faint
_EVENT_CONCEPTS = frozenset({"fainting", "seizure", "stroke_signs", "allergic_reaction"})
_PERIOD_ONSET = re.compile(r"\b(?:started|began|begun|came|arrived|showed up|starts?|is here|just)\b", re.I)


def _resolution_follows(s: str, seg: tuple[int, int], chunk: tuple[int, int], spans: list[tuple[int, int]]) -> bool:
    """"Nausea this morning, fine now.": the next comma chunk is a short remark that ends the episode and names no other symptom."""
    pos = chunk[1]
    for _ in range(2):
        if pos >= seg[1] or s[pos:pos + 1] != ",":
            return False
        nxt = s.find(",", pos + 1, seg[1])
        nxt = seg[1] if nxt == -1 else nxt
        text = s[pos + 1:nxt]
        if any(pos < x and y <= nxt for x, y in spans):
            return False          # names another symptom: its resolution is not ours
        if len(text.split()) <= 6 and (_resolved(text) or (_SELF_OK.search(text) and _NOW_EXPLICIT.search(text))):
            return True
        pos = nxt
    return False


def _temporal(s: str, seg: tuple[int, int], chunk: tuple[int, int], m: _Mention, assertion: str,
              spans: list[tuple[int, int]] | None = None) -> tuple[str, bool]:
    if assertion == "hypothetical":
        return "future", False
    if assertion in {"question", "quoted"}:
        return "unknown", False
    spans = spans or []
    text_chunk = s[chunk[0]:chunk[1]]
    text_seg = s[seg[0]:seg[1]]
    for scope in (text_chunk, text_seg):
        if re.search(r"[A-Za-z]", scope) and (_TIME_OLD.search(scope) or _TIME_PAST.search(scope) or _TIME_RECENT.search(scope)
                                              or _TIME_STRONG_CURRENT.search(scope) or _TIME_RECURRING.search(scope) or _resolved(scope)):
            break
    else:
        scope = text_chunk
    before = s[chunk[0]:m.end]  # include the mention itself: "took my iron supplement"
    clause_before = s[chunk[0]:m.start]
    same_day = bool(_TIME_SAME_DAY.search(scope))
    old = bool(_TIME_OLD.search(scope)) or (bool(_TIME_OLD_CTX.search(scope)) and bool(_PAST_VERB.search(before)))
    if not old and _AT_AGE.search(scope) and _PAST_VERB.search(before):
        old = True                                       # "my dad had chest pain at 45"
    if assertion == "negated":
        return ("past" if (old or _TIME_PAST.search(scope)) else "current"), same_day
    if old:
        return "past", False                             # history beats "and it's gone now"
    if _REITERATE.search(clause_before) and not _TIME_PAST.search(scope):
        return "current", False                          # "I said I had chest pain": a repeat of a present symptom
    if _resolved(scope) or _resolution_follows(s, seg, chunk, spans):
        return "resolved", same_day or bool(_TIME_RECENT.search(scope) and not _TIME_PAST.search(scope)) or bool(_TIME_SAME_DAY.search(text_seg))
    present_perfect = bool(_PRESENT_PERFECT.search(before))
    past_tense = bool(_PAST_TENSE.search(before)) and not present_perfect
    if m.concept in _EVENT_CONCEPTS and not present_perfect and (past_tense or re.search(r"\w+ed$", m.text.lower())) \
            and _TIME_RECENT.search(scope) and not _NOW_EXPLICIT.search(scope):
        return "recent", True                            # the faint/seizure happened; "still feel off" is about afterwards
    if _TIME_STRONG_CURRENT.search(scope):
        return "current", same_day
    if _TIME_RECURRING.search(scope) or _HABITUAL_GET.search(clause_before):
        return "recurring", same_day
    if _TIME_PAST.search(scope):
        return "past", False
    if m.concept == "period" and _PERIOD_ONSET.search(before):
        return "current", same_day                       # "My period started today": she is on her period now
    if _TIME_RECENT.search(scope):
        return ("recent" if past_tense else "current"), True
    if past_tense:
        return "recent", False
    return "current", same_day


def _blank(s: str, spans: list[tuple[int, int]]) -> str:
    """`s` with every symptom mention replaced by spaces: "saans ruk gayi" (breath stopped) must not read as "it stopped"."""
    out = list(s)
    for a, b in spans:
        out[a:b] = " " * (b - a)
    return "".join(out)


def _hi_temporal(blank: str, seg: tuple[int, int], m: _Mention, spans: list[tuple[int, int]],
                 temporal: str, same_day: bool) -> tuple[str, bool]:
    """Hindi time words. Hindi is verb-final ("seene mein dard THA" = there was chest pain), so they are read around the
    symptom on text with mentions blanked. Downgrades (history, resolved, recurring) need a cue in the symptom's own
    clause; a "now" anywhere in the sentence keeps it current. No Hindi cue at all: the English reading stands."""
    a = seg[0]
    for c in _HI_CLAUSE.finditer(blank, seg[0], m.start):
        a = c.end()
    nxt = _HI_CLAUSE.search(blank, m.end, seg[1])
    b = nxt.start() if nxt else seg[1]
    clause, sentence = blank[a:b], blank[seg[0]:seg[1]]
    same_day = same_day or bool(_HI_SAME_DAY.search(sentence))
    if _HI_CURRENT.search(sentence):                 # "...history hai aur abhi ho raha hai", "ruk gaya tha, phir se shuru"
        return "current", same_day
    if _HI_OLD.search(clause):
        return "past", False
    follows = False
    if nxt:                                  # "..., ab theek hoon" / "... lekin ab theek hai": a short clause that ends it
        c_end = _HI_CLAUSE.search(blank, nxt.end(), seg[1])
        e = c_end.start() if c_end else seg[1]
        follows = (not any(nxt.end() <= x < e for x, _y in spans) and len(blank[nxt.end():e].split()) <= 6
                   and bool(_HI_RESOLVED_CLAUSE.search(blank[nxt.end():e])))
    if _HI_RESOLVED_AFTER.search(blank[m.end:b]) or follows:
        return "resolved", same_day or not _HI_PAST.search(sentence)   # an episode that just ended: ask, as in English
    if _HI_RECURRING.search(clause):
        return "recurring", same_day
    if _HI_PAST.search(clause):
        return "past", False
    if _HI_PAST_TENSE.search(blank[m.end:b]):
        return "recent", same_day
    return temporal, same_day


def _cap_mentions(mentions: list[_Mention], allowance: dict[str, int]) -> list[_Mention]:
    """Keep at most the per-sentence limit and the remaining per-message budget, red-flag mentions first."""
    reds = [m for m in mentions if m.tier == "red"]
    others = [m for m in mentions if m.tier != "red"]
    reds = reds[:min(_MAX_MENTIONS_PER_SENTENCE, allowance["red"])]
    others = others[:max(0, min(_MAX_MENTIONS_PER_SENTENCE - len(reds), allowance["nonred"]))]
    allowance["red"] -= len(reds)
    allowance["nonred"] -= len(others)
    return sorted(reds + others, key=lambda m: m.start)


def _classify(s: str, idx: int, allowance: dict[str, int] | None = None, extra: tuple[tuple[str, re.Pattern[str]], ...] = ()) -> list[Fact]:
    mentions = _find_mentions(s, extra)
    if not mentions:
        return []
    if allowance is None:
        allowance = {"red": _MAX_RED_TOTAL, "nonred": _MAX_NONRED_TOTAL}
    mentions = _cap_mentions(mentions, allowance)
    if not mentions:
        return []
    spans = [(m.start, m.end) for m in mentions]
    segments: list[tuple[int, int]] = []
    pos = 0
    for sp in _SEGMENT_SPLIT.finditer(s):
        segments.append((pos, sp.start()))
        pos = sp.end()
    segments.append((pos, len(s)))

    quotes = [(q.start(), q.end()) for q in re.finditer(r'"[^"]{1,300}"', s)]
    hi = bool(_HI_GATE.search(s))
    negs = [t for t in _NEG_PRE.finditer(s) if _outside(spans, t)]
    if hi:
        right_after = [t for t in _HI_PRE_NEG.finditer(s) if _outside(spans, t)
                       and any(re.fullmatch(r"\s+(?:(?:kisi|koi)\s+)?", s[t.end():a]) for a, _b in spans)]
        negs = sorted(negs + right_after, key=lambda t: t.start())
    possibles = [t for t in _POSSIBLE.finditer(s) if _outside(spans, t)]
    hypos = [t for t in _HYPO.finditer(s) if _outside(spans, t)
             and not (t.group(0).lower() == "if" and _IF_AFTER_DOUBT.search(s[max(0, t.start() - 40):t.start()]))]
    hypos += [t for t in _HYPO_SAY.finditer(s) if _outside(spans, t)]
    if hi:
        hypos += [t for t in _HI_HYPO.finditer(s) if _outside(spans, t)]
    fears = [t for t in list(_FEAR_ABOUT.finditer(s)) if _outside(spans, t)]
    fears_that = [t for t in _FEAR_THAT_I.finditer(s) if _outside(spans, t)]
    adv_src = [t for t in _ADVICE_SOURCE.finditer(s) if _outside(spans, t)]
    adv_gen = [t for t in _ADVICE_GENERIC.finditer(s) if _outside(spans, t)]
    futures = [t for t in _FUTURE_EXP.finditer(s) if _outside(spans, t)]
    others = [t for t in _OTHER_SUBJ.finditer(s) if _outside(spans, t)]
    if hi:   # "he" is also how people type "hai"; Hindi marks the experiencer with ko/ke/ki ("papa ko")
        others = sorted([t for t in others if t.group(0).lower() != "he"]
                        + [t for t in _HI_OTHER.finditer(s) if _outside(spans, t)], key=lambda t: t.start())
    trail_hedge = _TRAIL_HEDGE.search(s)

    q_start: int | None = None
    if hi:
        # Hindi words collide with English question cues ("do din se" = for two days, "is waqt" = right now), so a Hindi
        # sentence is a question only when it is clearly educational and the speaker is not in it.
        if _HI_GENERIC.search(s) and not _HI_SELF.search(s):
            if _HI_Q_START.match(s):
                q_start = 0
            elif _HI_Q_END.search(s):
                brk = max(s.rfind(","), s.rfind(";"))
                if brk >= 0:
                    q_start = brk + 1                  # "saans nahi aa rahi, kya ye normal hota hai?": only the tail asks
                elif not _HI_REPORT_VERB.search(s):
                    q_start = 0
    elif _Q_AT_START.match(s):
        q_start = 0
    else:
        qc = _Q_AFTER_COMMA.search(s)
        if qc:
            q_start = qc.start()
    # A trailing "?" alone does not make an information question: "I said no chest pain?" is a
    # declarative with rising intonation. Only bare fragments ("Chest pain?") count.
    # ...and not when the speaker is in it ("Perhaps I fainted?") or hedging: that is a hedged report, not a question.
    if (not hi and q_start is None and s.rstrip().endswith("?") and len(s.split()) <= 4
            and not _FIRST_PERSON.search(s) and not _POSSIBLE.search(s)):
        q_start = 0

    result: list[tuple[_Mention, str, str, str, str]] = []  # mention, assertion, reason, certainty, experiencer
    post_neg_idx: set[int] = set()
    for i, m in enumerate(mentions):
        hpn = _HI_NEG_POST.match(s, m.end) if hi else None
        if hpn and _HI_PAST_TENSE.search(hpn.group(0)) and _HI_BUT_NOW.search(s, hpn.end()):
            hpn = None
        pn = _NEG_POST.match(s, m.end) or _BARE_NO_AFTER.match(s, m.end) or hpn
        if pn and not (m.concept == "period" and re.match(r"\s*(?:is|was)\s+(?:over)", s[m.end:])):
            post_neg_idx.add(i)
    # a trailing ": none" governs the whole list that precedes it
    for j in sorted(post_neg_idx):
        k = j
        while k > 0 and _only(s[mentions[k - 1].end:mentions[k].start], (_FILLER_LIST | _hi.GLUE) if hi else _FILLER_LIST):
            k -= 1
            post_neg_idx.add(k)

    for i, m in enumerate(mentions):
        seg = _segment_of(segments, m.start)
        before_text = s[seg[0]:m.start]
        in_quote = any(a <= m.start and m.end <= b for a, b in quotes)
        assertion, reason, certainty, who = "present", "default", "default", "self"

        # ---- who is it about / is it a report at all
        strict = m.concept in CRISIS
        in_question = q_start is not None and m.start >= q_start
        # who is it about? "my coworker fainted" / "my sister told me she wants to kill herself". A mention that itself
        # names the speaker ("better off without me", "kill myself", "my chest hurts") is always the user.
        other = None
        if not _SELF_IN_MENTION.search(m.text):
            for t in others:
                if seg[0] <= t.start() and t.end() <= m.start and t.end() > (other.end() if other else -1):
                    gap = s[t.end():m.start]
                    # any verb (or none: "my coworker fainted" - the mention is the verb), no first-person word, no clause break
                    if (not _FIRST_PERSON.search(gap) and len(gap.split()) <= 5 and not re.search(r"[,;:]|\bbut\b", gap)
                            and not (hi and (_HI_SELF.search(gap) or _HI_COMM.search(gap)))):
                        other = t
        fam = _FAMILY_HISTORY.search(s[seg[0]:m.start]) or (
            hi and _HI_FAMILY.search(s[seg[0]:m.start]) and _HI_HISTORY.search(s[seg[0]:seg[1]]))

        # what a doctor/leaflet SAYS is not what the user REPORTS - unless it is the user's own symptom ("told me my chest pain is ...")
        own_poss = m.text[:3].lower() == "my " or bool(_OWN_POSSESSIVE.search(s[max(seg[0], m.start - 16):m.start]))
        adv = None
        if not own_poss:
            for t in adv_src:
                if _INVERTED_Q.search(s[max(0, t.start() - 14):t.start()]):
                    continue                    # "What did the doctor say about chest pain?" asks; it does not quote
                if seg[0] <= t.start() and t.end() <= m.start and _scope_reaches(s, t.end(), m, spans, None, 12):
                    adv = t
            if adv is None and not in_question:
                for t in adv_gen:
                    if seg[0] <= t.start() and t.end() <= m.start and _scope_reaches(s, t.end(), m, spans, None, 12):
                        adv = t
        if adv is None and not own_poss and not (_MSG_FIRST_PERSON.get() or _FIRST_PERSON.search(s)):  # any first-person word in the MESSAGE => may be a report, stay conservative
            # definition-style statement AFTER the mention: "chest pain is a symptom of a heart attack" teaches, it does not report
            adv = _GENERIC_PREDICATE.match(s, m.end)
        hyp = None
        hyp_is_fear = False
        for t in hypos:
            if t.end() <= m.start and _scope_reaches(s, t.end(), m, spans, None, 10) and seg[0] <= t.start():
                hyp = t
        if hyp is None:
            for t in fears:
                if t.end() <= m.start and _scope_reaches(s, t.end(), m, spans, None, 6):
                    hyp, hyp_is_fear = t, True
        fut = None
        if hyp is None:
            for t in futures:
                gap = s[t.end():m.start]
                if (seg[0] <= t.start() and t.end() <= m.start and len(gap.split()) <= 3 and not re.search(r"[,.;:!?]", gap)):
                    fut = t
        fear_self = any(t.end() <= m.start and _scope_reaches(s, t.end(), m, spans, _HEDGE_FIRST, strict=strict) for t in fears_that)
        has_my = bool(re.search(r"\bmy\b", s[max(seg[0], m.start - 12):m.start] + m.text, re.I)) or (
            hi and bool(_HI_POSS.search(s[max(seg[0], m.start - 16):m.start])))
        trailing = bool(trail_hedge) and trail_hedge.start() >= m.end and "," not in s[m.end:trail_hedge.start()] \
            and not re.search(r"[.?!;]", s[m.end:trail_hedge.start()])

        if in_quote:
            assertion, reason, certainty, who = "quoted", "inside_quotation", "explicit", "other"
        elif adv is not None:
            assertion, reason, certainty, who = "quoted", "reported_advice", "explicit", "other"
        elif other is not None or fam:
            assertion, reason, certainty, who = "other_person", "other_experiencer", "explicit", "other"
        elif hyp is not None and not (in_question and hyp_is_fear) and not (
                has_my and (_WORSEN.match(s, m.end) or (hi and _HI_WORSEN.match(s, m.end)))):
            assertion, reason, certainty = "hypothetical", "conditional_or_fear", "explicit"
        elif fut is not None:
            if m.tier == "red" and not _FUTURE_TIME.search(s[seg[0]:seg[1]]):
                # "I'm going to have chest pain" with no date is as likely a description of now as of the future
                assertion, reason, certainty = "possible", "future_marker_red_flag", "hedged"
            else:
                assertion, reason, certainty = "hypothetical", "future_event", "explicit"
        elif in_question and not (has_my or _SELF_IN_QUESTION.search(s)):
            assertion, reason, certainty = "question", "information_question", "explicit"
        else:
            neg = None
            neg_t = None
            pseudo = False
            wish = hope = False
            if m.forced == "negated":
                neg = "stated_normal"
            else:
                for t in reversed([t for t in negs if seg[0] <= t.start() and t.end() <= m.start]):
                    pre = s[seg[0]:t.start()]
                    if _WISH.search(pre):
                        wish = True
                        continue
                    if _HOPE.search(pre):
                        hope = True
                        continue
                    if _PSEUDO_NEG.match(s, t.start()):
                        pseudo = True
                        continue
                    if _scope_reaches(s, t.end(), m, spans, _FILLER_FIRST, strict=strict):
                        neg, neg_t = t.group(0).lower(), t
                        break
                if neg is None and i in post_neg_idx:
                    neg = "post_colon_none"
                if neg is None:
                    dc = _DENIED_CLAIM.search(s[seg[0]:m.start])
                    if dc and _only(s[seg[0] + dc.end():m.start], _FILLER_FIRST | {"was", "am", "were"}):
                        neg = "denied_claim"  # "I never said I had chest pain"
            until_now = bool(_UNTIL_NOW.search(s[m.end:seg[1]])) or bool(_FIRST_TIME.search(s[seg[0]:seg[1]]))
            if neg and until_now:
                assertion, reason, certainty = "present", "negation_until_now", "explicit"
            elif neg:
                uncertain = neg_t is not None and _UNCERTAIN_NEG.search(s[seg[0]:neg_t.start()].rstrip())
                double = (neg_t is not None and neg_t.group(0).lower() in {"no", "without"}
                          and re.search(r"(?:^|[,;:.!?]\s*|\b(?:and|but|or|well|honestly|actually|really)\s+)not\s+$", s[seg[0]:neg_t.start()], re.I))
                if uncertain:
                    assertion, reason, certainty = "possible", "uncertain_double_negation", "hedged"
                elif double:
                    assertion, reason, certainty = "present", "double_negation", "hedged"   # "not no chest pain" = some chest pain
                else:
                    assertion, reason = "negated", f"negation:{neg}"
                    certainty = "hedged" if neg.startswith("don't think") else "explicit"
            elif wish:
                assertion, reason, certainty = "present", "counterfactual_wish", "explicit"   # "I wish I didn't have chest pain"
            elif hope:
                assertion, reason, certainty = "possible", "hoped_not", "hedged"             # "I hope I don't have X"
            elif pseudo:
                assertion, reason, certainty = "present", "pseudo_negation", "explicit"
            else:
                poss = None
                for t in possibles:
                    if seg[0] <= t.start() and t.end() <= m.start and _scope_reaches(s, t.end(), m, spans, _HEDGE_FIRST, strict=strict):
                        poss = t
                if poss is not None or fear_self or trailing:
                    assertion, reason, certainty = "possible", "hedged_language", "hedged"
                elif in_question:
                    assertion, reason, certainty = "present", "self_report_in_question", "explicit"
                else:
                    explicit = bool(re.search(r"\b(?:i have|i've got|i'm having|i am having|i feel|i'm feeling|i am feeling|i got|i had|my|having|feeling)\b", before_text + " " + m.text, re.I))
                    assertion, reason, certainty = "present", "affirmed", "explicit" if explicit else "default"
        if hyp is not None and assertion == "present":
            reason = "conditional_on_existing_symptom"  # "if my chest pain gets worse" => the user has it now
        result.append((m, assertion, reason, certainty, who))

    facts: list[Fact] = []
    blank = _blank(s, spans) if hi else s
    for m, assertion, reason, certainty, who in result:
        seg = _segment_of(segments, m.start)
        chunk = _chunk_of(s, seg, m.start)
        temporal, same_day = _temporal(s, seg, chunk, m, assertion, spans)
        if hi and assertion in {"present", "possible"}:
            temporal, same_day = _hi_temporal(blank, seg, m, spans, temporal, same_day)
        if reason in {"negation_until_now", "conditional_on_existing_symptom"}:
            temporal, same_day = "current", True  # "never had it before today" == it is happening now
        elif reason in {"counterfactual_wish", "double_negation"}:
            temporal = "current"                  # a wish/double negative is about how things are right now
        sev, sev_label = _severity(s, chunk, m, seg[1], spans)
        if assertion == "negated" and sev_label == "none":
            sev, sev_label = None, None
        confidence = {"present": 0.9 if certainty == "explicit" else 0.75, "negated": 1.0 if certainty == "explicit" else 0.7,
                      "possible": 0.5, "hypothetical": 0.9, "question": 0.9, "other_person": 0.85, "quoted": 0.85}[assertion]
        if reason in {"affirmed"} and certainty == "default":
            confidence = 0.7
        knowledge = {"present": "USER_REPORTED", "negated": "USER_DENIED", "possible": "POSSIBLE"}.get(assertion, "NOT_A_SELF_REPORT")
        if assertion == "present" and temporal in {"past", "resolved"}:
            knowledge = "HISTORICAL"
        facts.append(Fact(
            concept=m.concept, assertion=assertion, temporal=temporal, severity=sev, severity_label=sev_label,
            experiencer="self" if who == "self" else "other", certainty=certainty, knowledge=knowledge,
            confidence=confidence, reason=reason, source="user_message", source_text=s[:240], tier=m.tier,
            label=m.label, same_day=same_day, detail=m.detail, sentence_index=idx, span=(m.start, m.end),
        ))
    return facts


def _resolve_followups(sentences: list[str], per_sentence: list[list[Fact]]) -> list[list[Fact]]:
    """Answers and corrections that refer back to the previous sentence ("Chest pain? No." / "It's gone now.")."""
    out = [list(f) for f in per_sentence]
    for i in range(1, len(sentences)):
        if out[i] or not out[i - 1]:
            continue
        s = sentences[i]
        prev_q = sentences[i - 1].rstrip().endswith("?")
        if prev_q and _QA_ANSWER_NO.match(s):
            out[i - 1] = [_replace(f, assertion="negated", reason="qa_answer_no", certainty="explicit", confidence=1.0, knowledge="USER_DENIED", temporal="current") for f in out[i - 1]]
        elif prev_q and _QA_ANSWER_YES.match(s):
            num, label = _answer_severity(s)
            out[i - 1] = [_replace(f, assertion="present", reason="qa_answer_yes", certainty="explicit", knowledge="USER_REPORTED", temporal="current",
                                   severity=num if num is not None else f.severity, severity_label=label or f.severity_label) for f in out[i - 1]]
        elif _SELF_ELLIPSIS.match(s):
            # "Stop saying I have chest pain. I don't." / "Do you have chest pain? I don't."
            out[i - 1] = [
                _replace(f, assertion="negated", reason="elliptical_denial", certainty="explicit", confidence=1.0, knowledge="USER_DENIED", temporal="current")
                if f.experiencer == "self" and f.assertion in {"present", "possible", "question"} else f
                for f in out[i - 1]
            ]
        elif len(s.split()) <= 10 and (_resolved(s) or (_SELF_OK.search(s) and _NOW_EXPLICIT.search(s)) or _HI_RESOLVED_CLAUSE.search(s)):
            out[i - 1] = [
                _resolve_fact(f, "+resolved_followup") if f.assertion in {"present", "possible"} and f.experiencer == "self" else f
                for f in out[i - 1]
            ]
        elif len(s.split()) <= 10 and _SELF_OK.search(s):
            # "I'm fine." only settles an episode that is already in the past tense ("I felt chest pain earlier. I'm fine.")
            out[i - 1] = [
                _resolve_fact(f, "+resolved_followup")
                if f.assertion in {"present", "possible"} and f.experiencer == "self" and f.temporal in {"recent", "past"} else f
                for f in out[i - 1]
            ]
    return out


def _replace(f: Fact, **kw: Any) -> Fact:
    data = {name: getattr(f, name) for name in f.__dataclass_fields__}
    data.update(kw)
    return Fact(**data)


def _resolve_fact(f: Fact, suffix: str) -> Fact:
    """Mark a fact resolved. An episode that started and ended inside this conversation is same-day unless it names an earlier day."""
    return _replace(f, temporal="resolved", knowledge="HISTORICAL", reason=f.reason + suffix,
                    same_day=f.same_day or not _TIME_PAST.search(f.source_text))


def _answer_severity(s: str) -> tuple[int | None, str | None]:
    n = _SEV_NUM.search(s)
    if n and 0 <= int(n.group(1)) <= 10:
        v = int(n.group(1))
        return v, "none" if v == 0 else "mild" if v <= 3 else "moderate" if v <= 6 else "severe"
    for name, rx in _SEV_WORDS:
        if rx.search(s):
            return None, name
    return None, None


def _segment_bounds(s: str) -> list[tuple[int, int]]:
    pos, bounds = 0, []
    for sp in _SEGMENT_SPLIT.finditer(s):
        bounds.append((pos, sp.start()))
        pos = sp.end()
    bounds.append((pos, len(s)))
    return bounds


def _apply_resolution_across_segments(s: str, facts: list[Fact]) -> list[Fact]:
    """"I had chest pain yesterday but I'm fine now": the second clause resolves the first."""
    bounds = _segment_bounds(s)
    if len(bounds) < 2:
        return facts
    out = list(facts)
    for n in range(1, len(bounds)):
        a, b = bounds[n]
        seg = s[a:b]
        if any(a <= f.span[0] < b for f in facts):
            continue
        # "but I'm fine" alone does not end a symptom the speaker has right now; "but I'm fine now" / "but it's gone" does
        settles_all = _resolved(seg) and len(seg.split()) <= 8
        settles_past = bool(_SELF_OK.search(seg))
        if settles_all or settles_past:
            for k, f in enumerate(out):
                if not (f.span[0] < a and f.assertion in {"present", "possible"} and f.experiencer == "self" and f.temporal != "resolved"):
                    continue
                own = next(((x, y) for x, y in bounds if x <= f.span[0] < y), (0, len(s)))
                if _TIME_OLD.search(s[own[0]:own[1]]):
                    continue                                  # already history; "fine now" changes nothing
                if settles_all or _NOW_EXPLICIT.search(seg) or f.temporal in {"recent", "past"}:
                    out[k] = _resolve_fact(f, "+resolved_clause")
    return out


def _same_sentence_ellipsis(s: str, facts: list[Fact]) -> list[Fact]:
    """"Everyone in my family gets headaches, but I don't.": the user denies it for themselves."""
    bounds = _segment_bounds(s)
    if len(bounds) < 2 or not facts:
        return facts
    a, _b = bounds[-1]
    if not _SELF_ELLIPSIS.match(s[a:]):
        return facts
    out = list(facts)
    seen: set[str] = set()
    for f in facts:
        if f.span[0] < a and f.assertion == "other_person" and f.concept not in seen:
            seen.add(f.concept)
            out.append(_replace(f, assertion="negated", experiencer="self", certainty="explicit", knowledge="USER_DENIED", confidence=0.9,
                                reason="elliptical_self_negation", temporal="current"))
    return out


def analyze(text: str, *, recorded_at: str | None = None, extra_terms: Iterable[str] = ()) -> list[Fact]:
    """All facts mentioned in `text`, in order. Pure and deterministic.

    `extra_terms` are additional free-text names (e.g. an AI-proposed event name) to classify with the same
    negation/tense logic; their facts carry concept ``custom:<term>``.
    """
    sentences = split_sentences(text)
    allowance = {"red": _MAX_RED_TOTAL, "nonred": _MAX_NONRED_TOTAL}
    extra = _extra_rx(extra_terms)
    token = _MSG_FIRST_PERSON.set(bool(_FIRST_PERSON.search(text or "")))
    try:
        per = [_classify(s, i, allowance, extra) for i, s in enumerate(sentences)]
    finally:
        _MSG_FIRST_PERSON.reset(token)
    per = [_apply_resolution_across_segments(s, f) if f else f for s, f in zip(sentences, per)]
    per = [_same_sentence_ellipsis(s, f) if f else f for s, f in zip(sentences, per)]
    per = _resolve_followups(sentences, per)
    return [f for group in per for f in group]


# --------------------------------------------------------------------------
# Helpers for callers
# --------------------------------------------------------------------------

def facts_by_concept(facts: Iterable[Fact]) -> dict[str, list[Fact]]:
    out: dict[str, list[Fact]] = {}
    for f in facts:
        out.setdefault(f.concept, []).append(f)
    return out


def net_state(facts: Iterable[Fact]) -> dict[str, dict[str, Any]]:
    """One entry per concept for the *user themselves* (latest report wins, conflicts flagged)."""
    out: dict[str, dict[str, Any]] = {}
    for f in facts:
        if f.experiencer != "self" or f.assertion not in {"present", "negated", "possible"}:
            continue
        cur = out.get(f.concept)
        entry = {"assertion": f.assertion, "temporal": f.temporal, "severity": f.severity, "conflict": False}
        if cur and cur["assertion"] != f.assertion:
            entry["conflict"] = True
        out[f.concept] = entry
    return out
