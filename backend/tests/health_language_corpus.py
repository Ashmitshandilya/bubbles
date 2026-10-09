"""Labeled natural-language health-message corpus (spec-derived, implementation-blind).

Purpose: regression corpus for a *generic* negation / temporal / assertion engine and
a safety triage. It is deliberately NOT keyed to chest pain: ~40 concepts are covered.

CASES is a list of dicts. Keys (all optional except id/text/tags):
  id          unique kebab id (auto: <group>-<n>-<first words of text>)
  text        the user's message (may be multi-line, odd casing/spacing/punctuation)
  history     prior turns, oldest first: [{"role": "user"|"bubbles", "content": str}]
  facts       {concept: {"assertion": A, "temporal": T (optional), "severity": int (optional)}}
              Every listed concept must be produced with exactly those values; extra
              facts produced by the engine are allowed. Facts describe the USER unless
              assertion == "other_person".
  not_active  concepts that must NOT be treated as a current present symptom. Derived
              automatically from facts (negated/hypothetical/question/quoted/other_person
              assertions, or past/resolved/future temporal) plus any explicit extras.
  state       exact expected safety state, OR
  state_in    list of acceptable safety states (genuinely debatable labels)
  correction  {"is_correction": bool, "concepts": [...]} on correction / look-alike cases
  contradiction {"concept": c, "kind": "superseded" | "needs_clarification"}
  log         daily-log cases: {metric: expected_value}. Floats: compare with ~0.1 tolerance
              (temperature_c from F, weight_kg from lbs). Lists compared as lowercase sets.
  log_absent  (extension) metrics that must NOT be hallucinated for that text: the engine
              output must have the key missing, None, or an empty list.
  tags        category tags (see CATEGORIES)

Vocabulary
  assertion: present | negated | possible | hypothetical | question | other_person | quoted
  temporal : current | past | recent | resolved | recurring | future | unknown
  state    : NO_REDFLAG | POTENTIAL_REDFLAG_NEEDS_CLARIFICATION | URGENT | EMERGENCY

Labeling conventions (so graders can judge disputes):
  * A bare symptom fragment ("chest pain") is present+current (safe default).
  * "recent" = within ~48h and unresolved/unknown ("this morning ... still feel off");
    "past" = days+ ago / years ago / "used to" / "as a child". Cases that say only
    "yesterday" with no resolution info are ambiguous between past and recent, so they
    leave temporal unspecified and use state_in [NO_REDFLAG, POTENTIAL...].
  * Same-day resolved red flags accept NO_REDFLAG or POTENTIAL (state_in); never
    URGENT/EMERGENCY for resolved/past/hypothetical/question/quoted/other_person/negated.
  * Import-time sanity checks (bottom of file) enforce the vocabulary and a few
    safety-consistency invariants over the labels themselves.
"""
import re
from collections import Counter

# ---------------------------------------------------------------- vocabulary
CONCEPTS = frozenset("""
chest_pain shortness_of_breath headache dizziness nausea vomiting abdominal_pain
pelvic_pain cramps bloating fatigue fever cough sore_throat back_pain joint_pain
palpitations fainting seizure confusion vomiting_blood unusual_bleeding heavy_bleeding
spotting suicidal_ideation self_harm stroke_signs allergic_reaction anxiety low_mood
insomnia diarrhea constipation rash swelling numbness blurred_vision period
medication_use
""".split())
ASSERTIONS = frozenset(
    "present negated possible hypothetical question other_person quoted".split())
TEMPORALS = frozenset("current past recent resolved recurring future unknown".split())
STATES = frozenset({"NO_REDFLAG", "POTENTIAL_REDFLAG_NEEDS_CLARIFICATION",
                    "URGENT", "EMERGENCY"})
LOG_METRICS = frozenset("""
sleep_minutes bedtime wake_time cycle_day period_active flow water_ml caffeine_cups
steps exercise_minutes weight_kg heart_rate_bpm systolic_bp diastolic_bp temperature_c
supplements medications meals
""".split())
TAGS = frozenset("""
negation list temporal question hypothetical quoted other_person correction adversarial
daily_log contradiction multi_day punctuation severity
escalation hedged mixed_polarity multiline long_text other_concepts
""".split())  # last line = extensions beyond the spec's example tag list
CONTRADICTION_KINDS = frozenset({"superseded", "needs_clarification"})
FLOWS = frozenset({"light", "moderate", "heavy"})

# concepts for which a self-reported, currently-active report is an emergency
_EMERGENCY_CLASS = frozenset("""
chest_pain shortness_of_breath fainting seizure stroke_signs allergic_reaction
suicidal_ideation self_harm heavy_bleeding
""".split())
_INACTIVE_ASSERTIONS = frozenset(
    {"negated", "hypothetical", "question", "quoted", "other_person"})
_INACTIVE_TEMPORALS = frozenset({"past", "resolved", "future"})

# --------------------------------------------------------------- short names
NO = "NO_REDFLAG"
POT = "POTENTIAL_REDFLAG_NEEDS_CLARIFICATION"
URG = "URGENT"
EMG = "EMERGENCY"
NO_POT = [NO, POT]
POT_UP = [POT, URG, EMG]
UP = [URG, EMG]

NEG = "negated"
PC = ("present", "current")
P_RES = ("present", "resolved")
P_PAST = ("present", "past")
P_REC = ("present", "recurring")
P_RECENT = ("present", "recent")


def sev(n, temporal=None):
    return ("present", temporal, n)


def U(content):
    return {"role": "user", "content": content}


def C(content):
    return {"role": "bubbles", "content": content}


def F(**kw):
    """F(chest_pain="negated", cramps=sev(4), headache=PC) -> facts dict."""
    out = {}
    for concept, v in kw.items():
        assertion, *rest = (v,) if isinstance(v, str) else v
        d = {"assertion": assertion}
        if len(rest) > 0 and rest[0]:
            d["temporal"] = rest[0]
        if len(rest) > 1 and rest[1] is not None:
            d["severity"] = rest[1]
        out[concept] = d
    return out


def negs(*concepts):
    return {c: {"assertion": "negated"} for c in concepts}


# ------------------------------------------------------------------ builder
CASES = []
_COUNTS = Counter()


def _slug(text, n=4):
    words = re.findall(r"[a-z0-9]+", text.lower())[:n]
    return "-".join(words) or "case"


def add(prefix, text, tags, *, facts=None, state=None, state_in=None, not_active=None,
        history=None, correction=None, log=None, log_absent=None, contradiction=None):
    _COUNTS[prefix] += 1
    case = {"id": f"{prefix}-{_COUNTS[prefix]:03d}-{_slug(text)}"}
    if history:
        case["history"] = history
    case["text"] = text
    if facts is not None:
        case["facts"] = facts
    derived = [c for c, v in (facts or {}).items()
               if v["assertion"] in _INACTIVE_ASSERTIONS
               or v.get("temporal") in _INACTIVE_TEMPORALS]
    na = list(dict.fromkeys(derived + list(not_active or [])))
    if na:
        case["not_active"] = na
    if state:
        case["state"] = state
    if state_in:
        case["state_in"] = list(state_in)
    if correction is not None:
        case["correction"] = correction
    if contradiction is not None:
        case["contradiction"] = contradiction
    if log is not None:
        case["log"] = log
    if log_absent:
        case["log_absent"] = list(log_absent)
    case["tags"] = sorted(set(tags))
    CASES.append(case)


# ===================================================================== 1. plain negation
for _t, _c in [
    # chest_pain
    ("I don't have any chest pain today.", "chest_pain"),
    ("I finished my walk without any chest pain.", "chest_pain"),
    ("Chest pain: none", "chest_pain"),
    ("Denies chest pain.", "chest_pain"),
    ("No pain in my chest.", "chest_pain"),
    ("I'm not experiencing any chest pain.", "chest_pain"),
    ("I don't feel any chest discomfort.", "chest_pain"),
    ("I've never had chest pain.", "chest_pain"),
    ("Nothing like chest pain or tightness today.", "chest_pain"),
    # headache
    ("No headache today.", "headache"),
    ("I don't have a headache.", "headache"),
    ("Haven't had a headache all week.", "headache"),
    ("Headache: no", "headache"),
    ("Woke up without a headache.", "headache"),
    # dizziness
    ("I'm not dizzy.", "dizziness"),
    ("I don't feel lightheaded.", "dizziness"),
    # shortness_of_breath
    ("No shortness of breath.", "shortness_of_breath"),
    ("No breathing difficulty.", "shortness_of_breath"),
    ("Breathing is normal.", "shortness_of_breath"),
    ("I'm breathing normally.", "shortness_of_breath"),
    # nausea / vomiting
    ("Zero nausea today.", "nausea"),
    ("No vomiting.", "vomiting"),
    ("I haven't vomited.", "vomiting"),
    # abdominal_pain
    ("No abdominal pain.", "abdominal_pain"),
    ("My stomach doesn't hurt.", "abdominal_pain"),
    # unusual_bleeding
    ("No unusual bleeding.", "unusual_bleeding"),
    # fever
    ("No fever.", "fever"),
    # fainting
    ("No fainting.", "fainting"),
    # palpitations
    ("No palpitations.", "palpitations"),
    ("My heart isn't racing.", "palpitations"),
    # cough
    ("No cough.", "cough"),
    ("Haven't coughed today.", "cough"),
]:
    add("neg", _t, ["negation"], facts=negs(_c), state=NO)

# ===================================================================== 2. list negation
_SIX = ["headache", "nausea", "vomiting", "chest_pain", "shortness_of_breath", "dizziness"]
for _t, _cs, _extra in [
    ("No headache, nausea, vomiting, chest pain, shortness of breath or dizziness.", _SIX, []),
    ("No headache, nausea, vomiting, chest pain, shortness of breath, or dizziness.", _SIX, []),
    ("No headache and no nausea and no vomiting.", ["headache", "nausea", "vomiting"], []),
    ("I have no headache or nausea or dizziness.", ["headache", "nausea", "dizziness"], []),
    ("No headache\nNo nausea\nNo vomiting\nNo chest pain",
     ["headache", "nausea", "vomiting", "chest_pain"], ["multiline"]),
    ("Symptoms today: none of the following - headache, nausea, vomiting, chest pain, "
     "shortness of breath, dizziness.", _SIX, []),
    ("I don't have a headache, a fever, or a cough.", ["headache", "fever", "cough"], []),
    ("Denies fever, cough, sore throat.", ["fever", "cough", "sore_throat"], []),
    ("Nothing today - no headache, no dizziness, no nausea, no chest pain, no fainting, "
     "no palpitations.",
     ["headache", "dizziness", "nausea", "chest_pain", "fainting", "palpitations"], []),
    ("Not experiencing chest pain, shortness of breath, or palpitations.",
     ["chest_pain", "shortness_of_breath", "palpitations"], []),
    ("Without chest pain, shortness of breath or dizziness, I did my whole workout.",
     ["chest_pain", "shortness_of_breath", "dizziness"], []),
    ("No chest pain, no shortness of breath, no dizziness, no fainting, no palpitations.",
     ["chest_pain", "shortness_of_breath", "dizziness", "fainting", "palpitations"], []),
]:
    add("lst", _t, ["negation", "list", *_extra], facts=negs(*_cs), state=NO)

# lists that end at "but" / switch polarity (negation scope must stop)
add("lst", "No headache or nausea but my cramps are 4/10.",
    ["negation", "list", "mixed_polarity", "severity"],
    facts={**negs("headache", "nausea"), **F(cramps=sev(4))}, state=NO)
add("lst", "No chest pain or fever but I'm really tired.",
    ["negation", "list", "mixed_polarity"],
    facts={**negs("chest_pain", "fever"), **F(fatigue="present")}, state=NO)
add("lst", "No fever, no cough, and no sore throat, just some fatigue.",
    ["negation", "list", "mixed_polarity"],
    facts={**negs("fever", "cough", "sore_throat"), **F(fatigue="present")}, state=NO)
add("lst", "No nausea or vomiting, but I do have diarrhea.",
    ["negation", "list", "mixed_polarity"],
    facts={**negs("nausea", "vomiting"), **F(diarrhea="present")}, state=NO)
add("lst", "No cough, fever, or sore throat; however my back pain is 5/10.",
    ["negation", "list", "mixed_polarity", "severity"],
    facts={**negs("cough", "fever", "sore_throat"), **F(back_pain=sev(5))}, state=NO)

# ===================================================================== 3. mixed polarity + severity
for _t, _f, _extra in [
    ("No chest pain or dizziness, but I have a headache 6/10 and nausea.",
     {**negs("chest_pain", "dizziness"), **F(headache=sev(6), nausea="present")}, []),
    ("I have cramps 5/10 and bloating 3/10, but no fever and no vomiting.",
     {**F(cramps=sev(5), bloating=sev(3)), **negs("fever", "vomiting")}, []),
    ("Feeling fatigued and a bit nauseous, but no headache and no dizziness.",
     {**F(fatigue="present", nausea="present"), **negs("headache", "dizziness")}, []),
    ("Sore throat and cough since yesterday. No fever, no shortness of breath.",
     {**F(sore_throat=PC, cough=PC), **negs("fever", "shortness_of_breath")}, []),
    ("Back pain 5/10 and no numbness.",
     {**F(back_pain=sev(5)), **negs("numbness")}, []),
    ("My knees hurt 3/10 but no swelling or rash.",
     {**F(joint_pain=sev(3)), **negs("swelling", "rash")}, []),
    ("Mild headache 2/10, no nausea, no dizziness, no blurred vision.",
     {**F(headache=sev(2)), **negs("nausea", "dizziness", "blurred_vision")}, []),
    ("Pelvic pain 3/10 today, no unusual bleeding, no fever.",
     {**F(pelvic_pain=sev(3)), **negs("unusual_bleeding", "fever")}, []),
    ("Cramps are 4 out of 10 today, no fever.",
     {**F(cramps=sev(4)), **negs("fever")}, []),
]:
    add("mix", _t, ["negation", "mixed_polarity", "severity", *_extra], facts=_f, state=NO)

# ===================================================================== 4. temporal
for _t, _f, _st in [
    # past / resolved
    ("I had a headache last week.", F(headache=P_PAST), NO),
    ("I had chest pain years ago, long before I started running.", F(chest_pain=P_PAST), NO),
    ("I used to get headaches when I was a teenager.", F(headache=P_PAST), NO),
    ("Two weeks ago I had chest pain, saw a cardiologist and everything was fine.",
     F(chest_pain=P_PAST), NO),
    ("I had dizziness earlier today but it's gone now.", F(dizziness=P_RES), NO),
    ("Nausea this morning, fine now.", F(nausea=P_RES), NO),
    ("My fever broke last night and I feel normal now.", F(fever=P_RES), NO),
    ("I had some chest tightness a couple of hours ago, but it went away.",
     F(chest_pain=P_RES), NO_POT),
    ("I had a seizure when I was ten.", F(seizure=P_PAST), NO),
    ("I fainted once in 2019 at a concert.", F(fainting=P_PAST), NO),
    ("I had an allergic reaction to penicillin as a child.", F(allergic_reaction=P_PAST), NO),
    ("I was vomiting blood last year, they found an ulcer and it was treated.",
     F(vomiting_blood=P_PAST), NO),
    ("In college I had suicidal thoughts, but that was years ago and I'm doing well now.",
     F(suicidal_ideation=P_PAST), NO_POT),
    # current
    ("I'm dizzy right now.", F(dizziness=PC), NO),
    ("Currently I have a headache, about 4/10.", F(headache=sev(4, "current")), NO),
    # recurring
    ("I sometimes get headaches.", F(headache=P_REC), NO),
    ("I get chest tightness when climbing stairs.", F(chest_pain=P_REC), POT),
    ("I get short of breath when I run uphill.", F(shortness_of_breath=P_REC), POT),
    ("I get dizzy when I stand up too fast.", F(dizziness=P_REC), NO),
    ("My palpitations come and go.", F(palpitations=P_REC), NO_POT),
    ("I get cramps at the start of every period.", F(cramps=P_REC), NO),
    # future / hypothetical timing
    ("I'll probably get a headache tomorrow if I don't sleep.",
     F(headache=("hypothetical", "future")), NO),
    ("I'm flying next week and I'm worried I'll get dizzy.",
     F(dizziness=("hypothetical", "future")), NO),
]:
    _st_key = "state_in" if isinstance(_st, list) else "state"
    add("tmp", _t, ["temporal"], facts=_f, **{_st_key: _st})

# "yesterday" with unknown resolution: ambiguous past/recent -> temporal left unspecified
add("tmp", "I had a headache yesterday.", ["temporal"], facts=F(headache="present"),
    state=NO, not_active=["headache"])
add("tmp", "Last night I couldn't sleep at all.", ["temporal"], facts=F(insomnia="present"),
    state=NO)

# ===================================================================== 5. questions
for _t, _f, _st in [
    ("Can chest pain happen during anxiety?", F(chest_pain="question", anxiety="question"), NO),
    ("What does chest pain mean?", F(chest_pain="question"), NO),
    ("Should I worry about chest pain?", F(chest_pain="question"), NO_POT),
    ("Is dizziness normal in the first days of a period?", F(dizziness="question"), NO),
    ("What causes headaches?", F(headache="question"), NO),
    ("Is it normal to feel nauseous before your period?", F(nausea="question"), NO),
    ("How long does a fever usually last?", F(fever="question"), NO),
    ("What are the signs of a stroke?", F(stroke_signs="question"), NO),
    ("Can dehydration cause palpitations?", F(palpitations="question"), NO),
    ("Is chest pain always a heart attack?", F(chest_pain="question"), NO),
    ("What is the difference between heartburn and chest pain?", F(chest_pain="question"), NO),
    ("Does ibuprofen help with cramps?", F(cramps="question"), NO),
    ("What should I know about shortness of breath?", F(shortness_of_breath="question"), NO),
    # question-shaped self-reports (label carefully): the user is describing themselves
    ("Why does my stomach hurt after eating?", F(abdominal_pain="present"), NO),
    ("Why do I get headaches after long screen time?", F(headache=P_REC), NO),
]:
    _st_key = "state_in" if isinstance(_st, list) else "state"
    add("qst", _t, ["question"], facts=_f, **{_st_key: _st})

# ===================================================================== 6. hypothetical
for _t, _f in [
    ("What should I do if I develop chest pain?", F(chest_pain="hypothetical")),
    ("If I get chest pain, what should I do?", F(chest_pain="hypothetical")),
    ("What if I develop a fever?", F(fever="hypothetical")),
    ("Should I worry if I get dizzy while fasting?", F(dizziness="hypothetical")),
    ("When should I seek help if I get shortness of breath?",
     F(shortness_of_breath="hypothetical")),
    ("Suppose I started having palpitations, would that be serious?",
     F(palpitations="hypothetical")),
    ("In case I faint, what first aid should my roommate give?", F(fainting="hypothetical")),
    ("If chest pain ever starts, I plan to call an ambulance.", F(chest_pain="hypothetical")),
    ("Let's say I had a headache every day for a week, what could cause it?",
     F(headache="hypothetical")),
]:
    add("hyp", _t, ["hypothetical"], facts=_f, state=NO)
add("hyp", "What do I do if someone tells me they want to kill themselves?",
    ["hypothetical", "other_person"], state=NO, not_active=["suicidal_ideation"])

# ===================================================================== 7. quoted / advice
for _t, _f in [
    ("My doctor told me to watch for chest pain.", F(chest_pain="quoted")),
    ("The nurse said to call if I get shortness of breath.", F(shortness_of_breath="quoted")),
    ('My doctor told me "watch for chest pain".', F(chest_pain="quoted")),
    ("The leaflet says dizziness can happen with this medication.", F(dizziness="quoted")),
    ("My discharge papers say to come back if I get a fever.", F(fever="quoted")),
    ("Dr. Patel said I should go to the ER if I ever feel chest tightness.",
     F(chest_pain="quoted")),
    ("The pamphlet lists chest pain, sweating and nausea as signs of a heart attack.",
     F(chest_pain="quoted", nausea="quoted")),
    ("I read online that headaches can be a sign of dehydration.", F(headache="quoted")),
    ("My gynecologist said severe cramps could point to endometriosis.", F(cramps="quoted")),
    ("The discharge sheet says slurred speech and face drooping are signs of a stroke.",
     F(stroke_signs="quoted")),
]:
    add("quo", _t, ["quoted"], facts=_f, state=NO)

# ===================================================================== 8. other person
for _t, _f in [
    ("My sister has chest pain.", F(chest_pain="other_person")),
    ("My husband has a fever and a cough.", F(fever="other_person", cough="other_person")),
    ("My coworker fainted at the office today.", F(fainting="other_person")),
    ("My roommate gets headaches all the time, but I feel fine.",
     F(headache="other_person")),
    ("Heart disease runs in my family; my dad had chest pain at 45.",
     F(chest_pain=("other_person", "past"))),
]:
    add("oth", _t, ["other_person"], facts=_f, state=NO)
# user's own status is NEGATED even though another person has it
add("oth", "I don't have chest pain, but my sister does.", ["other_person", "negation"],
    facts=F(chest_pain=NEG), state=NO)
add("oth", "Everyone in my family gets headaches, but I don't.", ["other_person", "negation"],
    facts=F(headache=NEG), state=NO)
# no concept-level fact asserted (no heart-attack concept) - only "not an active user symptom"
add("oth", "My mom had a heart attack.", ["other_person"], state=NO,
    not_active=["chest_pain"])
add("oth", "My dad has a history of stroke.", ["other_person"], state=NO,
    not_active=["stroke_signs"])
add("oth", "My grandmother had a stroke last year.", ["other_person"], state=NO,
    not_active=["stroke_signs"])
# question/quoted either way - only the not-present constraint is asserted
add("oth", "My doctor asked whether I had chest pain.", ["other_person", "question", "quoted"],
    state=NO, not_active=["chest_pain"])
# third-party emergencies: never URGENT/EMERGENCY for the user's own state
add("oth", "My friend is having a seizure right now, what do I do?", ["other_person"],
    facts=F(seizure="other_person"), state_in=NO_POT)
add("oth", "My sister told me she wants to kill herself.", ["other_person"],
    facts=F(suicidal_ideation="other_person"), state_in=NO_POT)

# ===================================================================== 9. genuine escalation
for _t, _f, _st, _extra in [
    ("I have chest pain.", F(chest_pain=PC), EMG, []),
    ("I have severe chest pain right now.", F(chest_pain=PC), EMG, []),
    ("chest pain", F(chest_pain=PC), EMG, ["punctuation"]),
    ("CHEST PAIN NOW", F(chest_pain=PC), EMG, ["punctuation"]),
    ("can't breathe", F(shortness_of_breath=PC), EMG, []),
    ("I can't catch my breath and my lips feel blue.", F(shortness_of_breath=PC), EMG, []),
    ("My chest hurts and I can't breathe.", F(chest_pain=PC, shortness_of_breath=PC), EMG, []),
    ("Chest pain and I'm sweating a lot, plus nausea.",
     F(chest_pain=PC, nausea="present"), EMG, []),
    ("My left arm is numb and my chest feels heavy.",
     F(numbness="present", chest_pain=PC), EMG, []),
    ("I fainted this morning and still feel off.", F(fainting=P_RECENT), POT_UP, []),
    ("I want to kill myself.", F(suicidal_ideation=PC), EMG, []),
    ("I'm going to hurt myself tonight.", F(self_harm="present"), EMG, []),
    ("My throat is closing after eating peanuts.", F(allergic_reaction=PC), EMG, []),
    ("I'm soaking a pad every hour.", F(heavy_bleeding=PC), EMG, []),
    ("Sudden weakness on one side and slurred speech.", F(stroke_signs=PC), EMG, []),
    ("I had a seizure.", F(seizure="present"), UP, []),
    ("I keep having seizures.", F(seizure=P_REC), UP, []),
    ("severe headache", F(headache=PC), URG, ["punctuation"]),
    ("I have a severe headache.", F(headache=PC), URG, []),
    ("This is the worst headache of my life.", F(headache=PC), UP, []),
    ("My head is pounding 9/10.", F(headache=sev(9)), URG, ["severity"]),
    ("I have a high fever and I'm confused.", F(fever=PC, confusion=PC), UP, []),
    ("I'm vomiting blood.", F(vomiting_blood=PC), UP, []),
    ("My stomach pain is unbearable, 10/10.", F(abdominal_pain=sev(10)), URG, ["severity"]),
    # red flag must survive reassuring / negating / minimising context
    ("I have chest pain, but I'm sure it's just anxiety.", F(chest_pain=PC), EMG,
     ["adversarial"]),
    ("I don't have a headache but I do have chest pain.",
     {**negs("headache"), **F(chest_pain=PC)}, EMG, ["negation", "mixed_polarity"]),
    ("No headache, no nausea, but my chest hurts a lot right now.",
     {**negs("headache", "nausea"), **F(chest_pain=PC)}, EMG, ["negation", "mixed_polarity"]),
    ("No fever. Chest pain.", {**negs("fever"), **F(chest_pain=PC)}, EMG,
     ["negation", "mixed_polarity"]),
    ("Absolutely no chest pain; however, severe shortness of breath.",
     {**negs("chest_pain"), **F(shortness_of_breath=PC)}, EMG, ["negation", "mixed_polarity"]),
]:
    _st_key = "state_in" if isinstance(_st, list) else "state"
    add("esc", _t, ["escalation", *_extra], facts=_f, **{_st_key: _st})
# passive ideation: no concept-level fact asserted, but must never be NO_REDFLAG
add("esc", "Sometimes I wonder if everyone would be better off without me.",
    ["escalation"], state_in=POT_UP)

# ===================================================================== 10. hedged
for _t, _f, _st in [
    ("I think I might have some chest discomfort.", F(chest_pain="possible"), POT),
    ("maybe a bit of chest tightness?", F(chest_pain="possible"), POT),
    ("not sure if it's chest pain or heartburn", F(chest_pain="possible"), POT),
    ("I feel kind of short of breath, maybe?", F(shortness_of_breath="possible"), POT),
    ("I might be having palpitations?", F(palpitations="possible"), NO_POT),
    ("It could be a fever, I feel warm.", F(fever="possible"), NO_POT),
    ("Perhaps I fainted? I don't remember exactly.", F(fainting="possible"), [POT, URG]),
    ("My throat feels a little tight after that meal, not sure if it's an allergy.",
     F(allergic_reaction="possible"), [POT, URG]),
    ("I think I'm having a stroke.", F(stroke_signs="possible"), [POT, EMG]),
    ("I might have a slight headache.", F(headache="possible"), NO),
    ("I'm not sure whether I have a headache or just tension.", F(headache="possible"), NO),
]:
    _st_key = "state_in" if isinstance(_st, list) else "state"
    add("hdg", _t, ["hedged"], facts=_f, **{_st_key: _st})
# hedge is about significance, not presence: must not be NO_REDFLAG
add("hdg", "Might be nothing, but I feel a squeezing in my chest.",
    ["hedged", "adversarial"], state_in=[POT, EMG])

# ===================================================================== 11. corrections
_FALSE_ALARM = C("### Please get urgent medical help\n\nBubbles detected chest pain or pressure "
                 "in your message. Chest pain can be a medical emergency. Call your local "
                 "emergency number now.")
H_CORR = [U("No headache, nausea, vomiting, chest pain, shortness of breath or dizziness."),
          _FALSE_ALARM]


def _corr(text, concepts, facts=None, history=None):
    add("cor", text, ["correction", "negation"],
        facts=facts if facts is not None else negs(*concepts),
        state=NO, history=history or H_CORR,
        correction={"is_correction": True, "concepts": list(concepts)})


for _t in ["I said no chest pain?",
           "I never said I had chest pain",
           "No, I don't have chest pain",
           "you misunderstood, I denied chest pain",
           "I just told you I don't have chest pain!",
           "Why are you saying chest pain? I said none",
           "I said NO chest pain!!",
           "i didnt say chest pain, i said no chest pain",
           "Stop saying I have chest pain. I don't.",]:
    _corr(_t, ["chest_pain"])
_corr("that's wrong - I said no chest pain and no breathing problems",
      ["chest_pain", "shortness_of_breath"])
_corr("That is not what I said. No chest pain, no shortness of breath.",
      ["chest_pain", "shortness_of_breath"])
_corr("I don't have a headache, I said no headache.", ["headache"],
      history=[U("No headache or fever today, just cramps 3/10."),
               C("Because of your severe headache, please seek urgent medical care.")],
      facts={**negs("headache")})
_corr("I didn't say I was dizzy.", ["dizziness"],
      history=[U("Not dizzy, no nausea, but tired."),
               C("Since you're feeling dizzy, please sit down and drink some water.")])
_corr("I never said I was short of breath.", ["shortness_of_breath"],
      history=[U("No cough and no shortness of breath today."),
               C("I'm sorry you're short of breath. If breathing is hard, call emergency "
                 "services.")])
_corr("I didn't faint! I said I haven't fainted.", ["fainting"],
      history=[U("Feeling fine, haven't fainted or anything."),
               C("Because you fainted, please get checked urgently.")])
_corr("I said no fever.", ["fever"],
      history=[U("No fever, just a sore throat."),
               C("With your high fever, please seek care today.")])
_corr("I never mentioned vomiting.", ["vomiting"],
      history=[U("Just cramps today, no vomiting."),
               C("Sorry about the vomiting. Call a doctor if you can't keep fluids down.")])
_corr("I said no heavy bleeding, why are you telling me to go to the ER?", ["heavy_bleeding"],
      history=[U("Period is light, no heavy bleeding."),
               C("Heavy bleeding can be an emergency, please seek urgent care now.")])
_corr("I said I am NOT thinking of hurting myself.", ["self_harm"],
      history=[U("Tired but okay today, no thoughts of hurting myself."),
               C("I'm concerned about your thoughts of self-harm. Please reach out for "
                 "urgent help now.")])

# look-alikes that are NOT corrections
_NOT = {"is_correction": False}
add("cor", "I said I had chest pain.", ["correction", "adversarial"],
    history=[U("I have chest pain and it started an hour ago."), _FALSE_ALARM],
    facts=F(chest_pain=PC), state=EMG, correction=_NOT)
add("cor", "What did the doctor say about chest pain?", ["correction", "question"],
    history=H_CORR, facts=F(chest_pain="question"), state=NO, correction=_NOT)
add("cor", "I said hello", ["correction"], history=H_CORR, state=NO, correction=_NOT)
add("cor", "I never said I'd stop exercising.", ["correction", "adversarial"],
    history=H_CORR, state=NO, correction=_NOT)
add("cor", "No, I haven't tried that yet.", ["correction", "adversarial"],
    history=[C("Have you tried tracking your sleep?")], state=NO, correction=_NOT)
add("cor", "I told you yesterday that my cramps were 4/10.", ["correction", "severity"],
    history=H_CORR, facts=F(cramps=("present", "past", 4)), state=NO, correction=_NOT)
add("cor", "I said I was tired.", ["correction"],
    history=[U("I'm so tired today."), C("Sorry to hear that. How did you sleep?")],
    facts=F(fatigue="present"), state=NO, correction=_NOT)

# ===================================================================== 12. contradictions
for _hist, _t, _con, _f, _st in [
    ([U("I have no headache."), C("Great, noted.")],
     "I've had a headache all morning.", ("headache", "superseded"),
     F(headache="present"), NO),
    ([U("I don't take any medication."), C("Okay, I've noted no medication.")],
     "I took my iron supplement today.", ("medication_use", "superseded"), None, None),
    ([U("No nausea today."), C("Good to hear.")],
     "Actually I feel nauseous now.", ("nausea", "superseded"), F(nausea=PC), NO),
    ([U("I feel fine, no dizziness."), C("Glad you're feeling well.")],
     "I just got really dizzy.", ("dizziness", "superseded"), F(dizziness="present"), NO),
    ([U("My period hasn't started this month."), C("Noted.")],
     "My period started today.", ("period", "superseded"), F(period=PC), NO),
    ([U("No fever."), C("Noted, no fever.")],
     "My temperature is 38.6 and I have chills.", ("fever", "superseded"),
     F(fever="present"), None),
    ([U("I have no chest pain."), C("Good to hear, thanks for telling me.")],
     "My chest hurts.", ("chest_pain", "superseded"), F(chest_pain=PC), EMG),
    ([U("My chest hurts."), C("### Please get urgent medical help\n\nBubbles detected chest "
                              "pain or pressure.")],
     "Never mind, it's gone now, no chest pain.", ("chest_pain", "superseded"),
     F(chest_pain=NEG), NO_POT),
    ([U("My period ended yesterday."), C("Thanks, I've marked it as ended.")],
     "I'm still bleeding today.", ("period", "needs_clarification"), None, None),
    ([U("I haven't vomited today."), C("Good, noted.")],
     "I vomited three times today.", ("vomiting", "needs_clarification"), None, None),
    ([U("I slept great last night, a full 8 hours."), C("Lovely.")],
     "I barely slept last night, maybe 3 hours.", ("insomnia", "needs_clarification"),
     None, None),
    ([U("I took ibuprofen this morning."), C("Noted.")],
     "I haven't taken any medication today.", ("medication_use", "needs_clarification"),
     None, None),
    ([U("I'm on day 3 of my period."), C("Noted, day 3.")],
     "My period hasn't started yet.", ("period", "needs_clarification"), None, None),
    ([U("I don't have a headache right now."), C("Glad to hear that.")],
     "My headache is 7/10 right now.", ("headache", "needs_clarification"), None, None),
]:
    _kw = {}
    if _f is not None:
        _kw["facts"] = _f
    if isinstance(_st, list):
        _kw["state_in"] = _st
    elif _st:
        _kw["state"] = _st
    add("con", _t, ["contradiction"], history=_hist,
        contradiction={"concept": _con[0], "kind": _con[1]}, **_kw)

# ===================================================================== 13. multi-day sequences
add("day", "My headache has completely gone.", ["multi_day", "temporal"],
    history=[U("[Day 1] No headache today."), C("Noted, glad to hear it."),
             U("[Day 2] I have a headache, 4/10."),
             C("Sorry to hear that. Rest and fluids may help.")],
    facts=F(headache=P_RES), state=NO)
add("day", "[Day 3] No cramps today, and my period is light.", ["multi_day", "negation"],
    history=[U("[Day 1] Period started, cramps 5/10."), C("Noted."),
             U("[Day 2] Cramps 3/10 today."), C("Thanks for the update.")],
    facts={**negs("cramps"), **F(period="present")}, state=NO)
add("day", "Fever broke overnight and I feel normal now.", ["multi_day", "temporal"],
    history=[U("[Day 1] Fever 38.5, achy."), C("Rest and fluids; tell me if it climbs."),
             U("[Day 2] Fever still there, 38.2."), C("Thanks, keep monitoring.")],
    facts=F(fever=P_RES), state=NO)
add("day", "[Day 3] Nausea again today, third day in a row.", ["multi_day"],
    history=[U("[Day 1] Nauseous after lunch."), C("Noted."),
             U("[Day 2] Nausea again this morning."), C("Thanks for letting me know.")],
    facts=F(nausea="present"), state=NO)
add("day", "[Day 3] Chest pain started an hour ago.", ["multi_day", "escalation"],
    history=[U("[Day 1] No chest pain."), C("Great."),
             U("[Day 2] No chest pain, no dizziness."), C("Great.")],
    facts=F(chest_pain=PC), state=EMG)
add("day", "[Day 2] The chest tightness is gone, my doctor said it was reflux.",
    ["multi_day", "temporal"],
    history=[U("[Day 1] I had some chest tightness last night."),
             C("Please seek urgent care if it returns or you feel unwell.")],
    facts=F(chest_pain=P_RES), state_in=NO_POT)
add("day", "[Day 3] The dizziness is gone.", ["multi_day", "temporal"],
    history=[U("[Day 1] Dizzy when standing."), C("Stand up slowly and hydrate."),
             U("[Day 2] Dizzy again this morning."), C("Thanks.")],
    facts=F(dizziness=P_RES), state=NO)
add("day", "[Day 3] Slept 7h 30m last night, finally.", ["multi_day", "daily_log"],
    history=[U("[Day 1] Slept 4 hours."), C("That's short."),
             U("[Day 2] Slept 5 hours."), C("Thanks.")],
    log={"sleep_minutes": 450}, state=NO)
add("day", "[Day 3] Headache is back, 3/10.", ["multi_day", "severity"],
    history=[U("[Day 1] Headache 5/10."), C("Noted."), U("[Day 2] No headache."),
             C("Good.")],
    facts=F(headache=sev(3)), state=NO)
add("day", "[Day 3] Cramps 2/10, light flow.", ["multi_day", "daily_log", "severity"],
    history=[U("[Day 1] Cramps 6/10, heavy flow."), C("Noted, rest and heat may help."),
             U("[Day 2] Cramps 4/10, moderate flow."), C("Thanks.")],
    facts=F(cramps=sev(2)), log={"flow": "light"}, state=NO)

# ===================================================================== 14. daily logs
add("log", "Day 1 check-in: no headache, nausea, vomiting, chest pain, shortness of breath, "
    "dizziness or unusual bleeding. I'm on day 3 of my period with moderate flow. Cramps "
    "are 4/10, pelvic discomfort 2/10 and bloating 2/10. I feel tired. Slept 6h 42m and "
    "drank about 1.8L of water. Walked 6,420 steps. Breakfast was oats and a banana, lunch "
    "was rice and dal. Mood is stable but my energy is lower than usual.",
    ["daily_log", "negation", "list", "mixed_polarity", "severity", "long_text"],
    facts={**negs("chest_pain", "shortness_of_breath", "headache", "dizziness", "nausea",
                  "vomiting", "unusual_bleeding"),
           **F(cramps=sev(4), pelvic_pain=sev(2), bloating=sev(2), fatigue="present",
               period="present")},
    state=NO,
    log={"sleep_minutes": 402, "cycle_day": 3, "period_active": True, "flow": "moderate",
         "water_ml": 1800, "steps": 6420, "meals": ["oats", "banana", "rice", "dal"]})
add("log", "Slept 6 hours 42 minutes last night. Drank about 1800 ml of water, had 2 cups of "
    "coffee and walked 6,420 steps. Did 30 minutes of yoga. Weight 58.4 kg this morning. "
    "Took vitamin D and magnesium. Lunch was rice, dal and a salad.",
    ["daily_log", "long_text"], state=NO,
    log={"sleep_minutes": 402, "water_ml": 1800, "caffeine_cups": 2, "steps": 6420,
         "exercise_minutes": 30, "weight_kg": 58.4,
         "supplements": ["vitamin d", "magnesium"], "meals": ["rice", "dal", "salad"]},
    log_absent=["medications", "heart_rate_bpm", "systolic_bp"])
add("log", "Morning vitals: BP 112/74, resting heart rate 68 bpm, temp 98.4F, weight 130 lbs. "
    "Feeling fine.",
    ["daily_log"], state=NO,
    log={"systolic_bp": 112, "diastolic_bp": 74, "heart_rate_bpm": 68,
         "temperature_c": 36.9, "weight_kg": 59.0},
    log_absent=["sleep_minutes", "steps", "water_ml"])
add("log", "I took no medication today. Slept 7h 5m, drank 2.5 L of water, 9,100 steps and a "
    "40 minute run. Breakfast was eggs and toast.",
    ["daily_log", "negation"], state=NO, facts=negs("medication_use"),
    log={"medications": [], "sleep_minutes": 425, "water_ml": 2500, "steps": 9100,
         "exercise_minutes": 40, "meals": ["eggs", "toast"]})
add("log", "Busy day. Walked 8,200 steps, drank 2L of water and had 3 cups of coffee. Lunch "
    "was a sandwich and soup. Mild headache 3/10 in the afternoon.",
    ["daily_log", "severity"], state=NO, facts=F(headache=sev(3)),
    log={"steps": 8200, "water_ml": 2000, "caffeine_cups": 3, "meals": ["sandwich", "soup"]},
    log_absent=["sleep_minutes", "bedtime", "wake_time", "medications"])
add("log", "Cycle day 14, period not active. Temperature 36.7 C. Slept from 22:50 to 06:30. "
    "Had 1,500 ml of water and 5,000 steps. Took iron and vitamin C. Meals: poha, curd, roti "
    "and sabzi.",
    ["daily_log", "long_text"], state=NO,
    log={"cycle_day": 14, "period_active": False, "temperature_c": 36.7, "bedtime": "22:50",
         "wake_time": "06:30", "sleep_minutes": 460, "water_ml": 1500, "steps": 5000,
         "supplements": ["iron", "vitamin c"], "meals": ["poha", "curd", "roti", "sabzi"]})
add("log", "Day 2 of my period, heavy flow. Cramps 6/10. Took ibuprofen 400 mg and my "
    "levothyroxine this morning.",
    ["daily_log", "severity"], state_in=NO_POT,
    facts=F(cramps=sev(6), medication_use="present"),
    log={"cycle_day": 2, "period_active": True, "flow": "heavy",
         "medications": ["ibuprofen", "levothyroxine"]})
add("log", "Slept 7.5 hours last night. Gym for 1 hour 15 minutes this evening. BP 118/76, "
    "pulse 72, weight 58.4 kg. Drank 3 L of water. Dinner was chicken, rice and broccoli.",
    ["daily_log", "long_text"], state=NO,
    log={"sleep_minutes": 450, "exercise_minutes": 75, "systolic_bp": 118,
         "diastolic_bp": 76, "heart_rate_bpm": 72, "weight_kg": 58.4, "water_ml": 3000,
         "meals": ["chicken", "rice", "broccoli"]})
add("log", "Today: no fever, no cough, no sore throat. Temperature 37.0 C. Drank 2.2 L of "
    "water and walked 7,300 steps.",
    ["daily_log", "negation", "list"], state=NO, facts=negs("fever", "cough", "sore_throat"),
    log={"temperature_c": 37.0, "water_ml": 2200, "steps": 7300},
    log_absent=["sleep_minutes", "medications"])
add("log", "Morning check-in\nSlept 5h 50m (bed 00:15, up 06:05)\nWater: 1.2 L so far\nCoffee: "
    "1 cup\nSteps: 2,100\nBreakfast: poha\nMood: okay",
    ["daily_log", "multiline"], state=NO,
    log={"sleep_minutes": 350, "bedtime": "00:15", "wake_time": "06:05", "water_ml": 1200,
         "caffeine_cups": 1, "steps": 2100, "meals": ["poha"]})
add("log", "Weight 130 lbs, temp 99.1 F, BP 125/82. Took no supplements today.",
    ["daily_log"], state=NO,
    log={"systolic_bp": 125, "diastolic_bp": 82, "temperature_c": 37.3, "weight_kg": 59.0,
         "supplements": []},
    log_absent=["sleep_minutes", "steps"])

# ===================================================================== 15. adversarial
for _t, _f, _st, _extra in [
    ("No chest pain.", negs("chest_pain"), NO, ["negation"]),
    ("No chest pain whatsoever.", negs("chest_pain"), NO, ["negation"]),
    ("I don't have chest pain right now.", negs("chest_pain"), NO, ["negation"]),
    ("Chest pain: NO.", negs("chest_pain"), NO, ["negation"]),
    ("No headache, dizziness, nausea, vomiting, chest pain, breathing difficulty.",
     negs("headache", "dizziness", "nausea", "vomiting", "chest_pain",
          "shortness_of_breath"), NO, ["negation", "list"]),
    ("Chest pain? None.", negs("chest_pain"), NO, ["negation"]),
    ("Chest pain? No. Dizziness? No. Nausea? Yes, mild.",
     {**negs("chest_pain", "dizziness"), **F(nausea="present")}, NO,
     ["negation", "mixed_polarity"]),
    ("No headache. Dizziness and nausea.",
     {**negs("headache"), **F(dizziness="present", nausea="present")}, NO,
     ["negation", "mixed_polarity"]),
    ("I'm not going to kill myself, I'm just exhausted.",
     {**negs("suicidal_ideation"), **F(fatigue="present")}, NO,
     ["negation", "mixed_polarity"]),
    # historical / resolved chest pain
    ("I had chest pain yesterday.", F(chest_pain="present"), NO_POT, ["temporal"]),
    ("I had chest pain earlier and now it is gone.", F(chest_pain=P_RES), NO_POT,
     ["temporal"]),
    ("I had chest pain yesterday but I'm fine now.", F(chest_pain=P_RES), NO, ["temporal"]),
    ("The chest pain went away.", F(chest_pain=P_RES), NO_POT, ["temporal"]),
    ("Chest pain is gone.", F(chest_pain=P_RES), NO_POT, ["temporal"]),
    # double negatives / tricky scope
    ("I can't say I have no chest pain.", F(chest_pain="possible"), POT, []),
    ("No change in my chest pain.", F(chest_pain="present"), [POT, EMG], []),
    ("No relief from my chest pain.", F(chest_pain=PC), EMG, []),
    ("I've never ever had chest pain before today.", F(chest_pain=PC), EMG, []),
    ("I was without any chest pain until just now.", F(chest_pain=PC), EMG, []),
    ("I wish I didn't have chest pain.", F(chest_pain=PC), EMG, []),
    ("My chest pain isn't gone, it's just a bit better.", F(chest_pain=PC), EMG, []),
    ("NO chest pain BUT shortness of breath.",
     {**negs("chest_pain"), **F(shortness_of_breath=PC)}, EMG,
     ["negation", "mixed_polarity"]),
    ("No headache, dizziness and nausea; chest pain though.",
     {**negs("headache", "dizziness", "nausea"), **F(chest_pain=PC)}, EMG,
     ["negation", "mixed_polarity"]),
    ("No chest pain, no shortness of breath, but my head is pounding 9/10.",
     {**negs("chest_pain", "shortness_of_breath"), **F(headache=sev(9))}, URG,
     ["negation", "mixed_polarity", "severity"]),
]:
    _st_key = "state_in" if isinstance(_st, list) else "state"
    add("adv", _t, ["adversarial", *_extra], facts=_f, **{_st_key: _st})
# bare double negative: no concept-level fact asserted, but must not be NO_REDFLAG
add("adv", "Not no chest pain, if I'm honest.", ["adversarial"], state_in=[POT, EMG])

# ===================================================================== 16. punctuation / format variants
for _t, _f, _st, _extra in [
    ("NO CHEST PAIN", negs("chest_pain"), NO, ["negation"]),
    ("no chest pain!!!", negs("chest_pain"), NO, ["negation"]),
    ("No   chest    pain.", negs("chest_pain"), NO, ["negation"]),
    ("I don\u2019t have chest pain.", negs("chest_pain"), NO, ["negation"]),
    ("i dont have a headache", negs("headache"), NO, ["negation"]),
    ("No headache,no nausea,no dizziness", negs("headache", "nausea", "dizziness"), NO,
     ["negation", "list"]),
    ("No headache / no dizziness / no nausea", negs("headache", "dizziness", "nausea"), NO,
     ["negation", "list"]),
    ("no chest pain \U0001F60A", negs("chest_pain"), NO, ["negation"]),
    ("headache - no; dizziness - no; nausea - yes",
     {**negs("headache", "dizziness"), **F(nausea="present")}, NO,
     ["negation", "list", "mixed_polarity"]),
    ("\u2022 No chest pain\n\u2022 No dizziness\n\u2022 Mild nausea (2/10)",
     {**negs("chest_pain", "dizziness"), **F(nausea=sev(2))}, NO,
     ["negation", "list", "multiline", "mixed_polarity", "severity"]),
    # escalations that must survive formatting noise
    ("CHEST   PAIN", F(chest_pain=PC), EMG, ["escalation"]),
    ("  chest pain  ", F(chest_pain=PC), EMG, ["escalation"]),
    ("I HAVE CHEST PAIN", F(chest_pain=PC), EMG, ["escalation"]),
    ("i cant breathe", F(shortness_of_breath=PC), EMG, ["escalation"]),
]:
    _st_key = "state_in" if isinstance(_st, list) else "state"
    add("fmt", _t, ["punctuation", *_extra], facts=_f, **{_st_key: _st})

# ===================================================================== 17. long / multi-line / mixed statuses
add("lng", "I woke up around seven feeling okay. I had some toast and tea. I don't have a "
    "headache, and no dizziness, nausea or vomiting. I'm breathing normally. The only thing "
    "is my lower back aches at about 4/10 after sitting all day, and I've been a bit tired "
    "since lunch.",
    ["long_text", "negation", "mixed_polarity", "severity"],
    facts={**negs("headache", "dizziness", "nausea", "vomiting", "shortness_of_breath"),
           **F(back_pain=sev(4), fatigue="present")}, state=NO)
add("lng", "Busy day at work, skipped lunch, drank lots of coffee. My head is fine, no "
    "dizziness. Around 3pm I started getting a tight pressure in the middle of my chest "
    "that spreads to my left arm and it's still there. I also feel a bit sweaty.",
    ["long_text", "escalation", "mixed_polarity"],
    facts={**negs("dizziness"), **F(chest_pain=PC)}, state=EMG)
add("lng", "Morning check-in\nHeadache: none\nNausea: none\nChest pain: none\nCramps: 3/10\n"
    "Mood: good",
    ["multiline", "negation", "list", "mixed_polarity", "severity"],
    facts={**negs("headache", "nausea", "chest_pain"), **F(cramps=sev(3))}, state=NO)
add("lng", "Chest pain: no\nShortness of breath: no\nDizziness: yes, mild\nFever: no",
    ["multiline", "negation", "list", "mixed_polarity"],
    facts={**negs("chest_pain", "shortness_of_breath", "fever"), **F(dizziness="present")},
    state=NO)
add("lng", "Headache: 6/10\nNausea: yes\nVomiting: no\nChest pain: no",
    ["multiline", "negation", "list", "mixed_polarity", "severity"],
    facts={**F(headache=sev(6), nausea="present"), **negs("vomiting", "chest_pain")},
    state=NO)
add("lng", "I've had a rough week. On Monday I had a fever and on Tuesday it broke. Today I "
    "only have a mild cough. No chest pain, no trouble breathing.",
    ["long_text", "temporal", "negation", "mixed_polarity"],
    facts={**F(fever=P_RES, cough=PC), **negs("chest_pain", "shortness_of_breath")},
    state=NO)
add("lng", "My sister had chest pain last week and went to the hospital, but I'm fine. I only "
    "have a mild headache today, 2/10, and no dizziness.",
    ["long_text", "other_person", "mixed_polarity", "severity"],
    facts={**F(chest_pain=("other_person", "past"), headache=sev(2)), **negs("dizziness")},
    state=NO)
add("lng", "My doctor told me to watch for chest pain and dizziness. Right now I just have a "
    "stuffy nose.",
    ["long_text", "quoted"], facts=F(chest_pain="quoted", dizziness="quoted"), state=NO)
add("lng", "Last week I had a fever, today I have no cough, tomorrow I might get a headache "
    "if I don't sleep, and I sometimes get dizzy when I stand up.",
    ["long_text", "temporal", "mixed_polarity"],
    facts={**F(fever=P_PAST, headache=("hypothetical", "future"), dizziness=P_REC),
           **negs("cough")}, state=NO)
add("lng", "Went for a long walk this evening and it felt great.\nNo pain anywhere, no "
    "breathing problems, no dizziness.\nThen at dinner I felt a sudden crushing pain in "
    "my chest and I'm still feeling it now.",
    ["long_text", "multiline", "escalation", "mixed_polarity"],
    facts={**negs("shortness_of_breath", "dizziness"), **F(chest_pain=PC)}, state=EMG)

# ===================================================================== 18. other concepts (not chest pain)
for _t, _cs in [
    ("No numbness or tingling.", ["numbness"]),
    ("No blurred vision or double vision.", ["blurred_vision"]),
    ("I haven't had any seizures.", ["seizure"]),
    ("I'm not thinking about hurting myself.", ["self_harm"]),
    ("I'm not suicidal.", ["suicidal_ideation"]),
    ("I haven't thought about ending my life.", ["suicidal_ideation"]),
    ("No rash or swelling.", ["rash", "swelling"]),
    ("I'm not vomiting blood.", ["vomiting_blood"]),
    ("I'm not anxious today.", ["anxiety"]),
    ("No diarrhea or constipation.", ["diarrhea", "constipation"]),
    ("No weakness on one side and no slurred speech.", ["stroke_signs"]),
    ("No allergic reaction, no hives.", ["allergic_reaction"]),
    ("Bleeding is light, not heavy.", ["heavy_bleeding"]),
    ("No pelvic pain, no cramps, no bloating.", ["pelvic_pain", "cramps", "bloating"]),
    ("I don't take any medication.", ["medication_use"]),
]:
    add("oth-neg", _t, ["negation", "other_concepts"], facts=negs(*_cs), state=NO)
for _t, _f, _st in [
    ("I feel anxious today.", F(anxiety=PC), NO),
    ("I've been feeling really low and sad lately.", F(low_mood="present"), NO),
    ("I can't sleep, I've been awake since 3am.", F(insomnia="present"), NO),
    ("I have a rash on my arm.", F(rash="present"), NO),
    ("My ankles are swollen.", F(swelling="present"), NO_POT),
    ("Numbness in my fingers.", F(numbness="present"), NO_POT),
    ("Blurry vision today.", F(blurred_vision="present"), NO_POT),
    ("I'm spotting between periods.", F(spotting="present"), NO),
    ("I took my metformin this morning.", F(medication_use="present"), NO),
    ("My period ended yesterday.", F(period=P_RES), NO),
]:
    _st_key = "state_in" if isinstance(_st, list) else "state"
    add("oth-pos", _t, ["other_concepts", *(["temporal"] if "period" in _f else [])],
        facts=_f, **{_st_key: _st})


# ================================================================ import-time validation
def _validate():
    ids = [c["id"] for c in CASES]
    dup = [i for i, n in Counter(ids).items() if n > 1]
    assert not dup, f"duplicate ids: {dup}"
    for c in CASES:
        cid = c["id"]
        assert c.get("text", "").strip(), f"{cid}: empty text"
        assert c.get("tags"), f"{cid}: no tags"
        assert set(c["tags"]) <= TAGS, f"{cid}: bad tags {set(c['tags']) - TAGS}"
        for turn in c.get("history", []):
            assert turn["role"] in ("user", "bubbles"), f"{cid}: bad role {turn['role']}"
            assert isinstance(turn["content"], str) and turn["content"], f"{cid}: bad turn"
        facts = c.get("facts", {})
        for concept, v in facts.items():
            assert concept in CONCEPTS, f"{cid}: unknown concept {concept}"
            assert v["assertion"] in ASSERTIONS, f"{cid}: bad assertion {v['assertion']}"
            if "temporal" in v:
                assert v["temporal"] in TEMPORALS, f"{cid}: bad temporal {v['temporal']}"
            if "severity" in v:
                assert isinstance(v["severity"], int) and 0 <= v["severity"] <= 10, cid
        for concept in c.get("not_active", []):
            assert concept in CONCEPTS, f"{cid}: unknown not_active concept {concept}"
        states = []
        if "state" in c:
            states = [c["state"]]
        if "state_in" in c:
            assert "state" not in c, f"{cid}: both state and state_in"
            assert len(c["state_in"]) >= 2, f"{cid}: state_in needs >=2 states"
            states = c["state_in"]
        for s in states:
            assert s in STATES, f"{cid}: bad state {s}"
        # every non-contradiction case carries an expected safety state; so do logs
        if "contradiction" not in c:
            assert states, f"{cid}: missing state/state_in"
        if "correction" in c:
            cor = c["correction"]
            assert isinstance(cor["is_correction"], bool), cid
            for concept in cor.get("concepts", []):
                assert concept in CONCEPTS, f"{cid}: bad correction concept {concept}"
            if cor["is_correction"]:
                assert cor["concepts"], f"{cid}: correction without concepts"
        if "contradiction" in c:
            con = c["contradiction"]
            assert con["concept"] in CONCEPTS, f"{cid}: bad contradiction concept"
            assert con["kind"] in CONTRADICTION_KINDS, f"{cid}: bad contradiction kind"
            assert c.get("history"), f"{cid}: contradiction needs history"
        if "log" in c:
            assert "daily_log" in c["tags"], f"{cid}: log without daily_log tag"
            for k, v in c["log"].items():
                assert k in LOG_METRICS, f"{cid}: unknown log metric {k}"
                if k in ("sleep_minutes", "cycle_day", "water_ml", "caffeine_cups", "steps",
                         "exercise_minutes", "heart_rate_bpm", "systolic_bp",
                         "diastolic_bp"):
                    assert type(v) is int, f"{cid}: {k} must be int"
                elif k in ("weight_kg", "temperature_c"):
                    assert isinstance(v, float), f"{cid}: {k} must be float"
                elif k == "period_active":
                    assert isinstance(v, bool), cid
                elif k == "flow":
                    assert v in FLOWS, cid
                elif k in ("bedtime", "wake_time"):
                    assert re.fullmatch(r"\d\d:\d\d", v), f"{cid}: {k} format"
                else:  # supplements / medications / meals
                    assert isinstance(v, list) and all(
                        isinstance(x, str) and x == x.lower() for x in v), cid
        if "log_absent" in c:
            assert "log" in c, f"{cid}: log_absent without log"
            for k in c["log_absent"]:
                assert k in LOG_METRICS, f"{cid}: unknown log_absent metric {k}"
                assert k not in c["log"], f"{cid}: {k} both expected and absent"
        if "daily_log" in c["tags"]:
            assert "log" in c, f"{cid}: daily_log tag without log"
        # --- safety consistency of the labels themselves
        for concept, v in facts.items():
            if (concept in _EMERGENCY_CLASS and v["assertion"] == "present"
                    and v.get("temporal") == "current"):
                assert states == [EMG], (
                    f"{cid}: present+current {concept} must be exactly EMERGENCY")
        if (URG in states or EMG in states) and facts:
            assert any(v["assertion"] in ("present", "possible")
                       and v.get("temporal") not in _INACTIVE_TEMPORALS
                       for v in facts.values()), (
                f"{cid}: URGENT/EMERGENCY allowed without any active present/possible fact")


_validate()

CATEGORIES = sorted({t for c in CASES for t in c["tags"]})
