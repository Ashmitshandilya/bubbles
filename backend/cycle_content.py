"""Cycle section content: symptom chips, education, weather lines, mode notes. [BUBBLES]

Pure data plus tiny helpers (stdlib only, no I/O). Copy rules: ranges not points, kind and
non-shaming, never diagnose, never any contraception claim, never dose or medication advice.
"""
from __future__ import annotations


NOT_CONTRACEPTION_NOTICE = (
    "These are estimates from your own logs. They are not birth control and can be wrong, "
    "so do not rely on them to prevent pregnancy."
)
GENERAL_KNOWLEDGE_LABEL = "General knowledge, not from your data"

# --------------------------------------------------------------------------- chips
CHIP_GROUPS: tuple[tuple[str, str], ...] = (
    ("mood", "Mood"),
    ("mind", "Mind"),
    ("body", "Body"),
    ("skin_hair", "Skin and hair"),
    ("digestion", "Digestion"),
    ("appetite", "Appetite"),
    ("sleep_energy", "Sleep and energy"),
    ("activity", "Movement"),
    ("lifestyle", "Lifestyle"),
    ("sexual", "Sex and intimacy"),
    ("reproductive", "Bleeding and discharge"),
    ("medication", "Medicines and supplements taken"),
    ("other", "Other"),
)

_SIGNALS = {
    "sy": "symptom", "mp": "mood_positive", "mn": "mood_negative",
    "po": "positive", "ne": "neutral", "li": "lifestyle",
}

# group -> "id|Label|keyword,keyword|signal" ; signal codes in _SIGNALS
_SPEC: dict[str, tuple[str, ...]] = {
    "mood": (
        "happy|Happy|cheerful,good mood,joyful|mp",
        "calm|Calm|relaxed,peaceful,settled|mp",
        "content|Content|okay,at ease,fine|mp",
        "confident|Confident|self assured,capable|mp",
        "affectionate|Affectionate|loving,warm,cuddly|mp",
        "social|Social|chatty,outgoing,sociable|mp",
        "grateful|Grateful|thankful,appreciative|mp",
        "anxious|Anxious|worried,nervous,on edge|mn",
        "irritable|Irritable|snappy,short tempered,grumpy|mn",
        "sad|Sad|low,down,blue|mn",
        "mood_swings|Mood swings|up and down,emotional,changeable|mn",
        "tearful|Tearful|crying,weepy,teary|mn",
        "angry|Angry|furious,rage,cross|mn",
        "overwhelmed|Overwhelmed|too much,swamped|mn",
        "lonely|Lonely|isolated,alone|mn",
        "restless|Restless|fidgety,unsettled|mn",
        "numb|Numb|flat,empty,detached|mn",
    ),
    "mind": (
        "brain_fog|Brain fog|foggy,cloudy,hazy|sy",
        "poor_focus|Hard to focus|concentration,distracted,scatterbrained|sy",
        "forgetful|Forgetful|memory,absent minded|sy",
        "racing_thoughts|Racing thoughts|overthinking,busy mind|sy",
        "clear_headed|Clear-headed|sharp,focused,alert|po",
        "motivated|Motivated|driven,productive,get up and go|mp",
        "creative|Creative|inspired,ideas|mp",
        "low_motivation|Low motivation|unmotivated,flat,cant be bothered|mn",
        "indecisive|Indecisive|cant decide,unsure|sy",
    ),
    "body": (
        "cramps|Cramps|period pain,tummy cramps,abdominal pain|sy",
        "cramps_severe|Severe cramps|very painful,strong pain,bad cramps|sy",
        "bloating|Bloating|tummy,swelling,bloated|sy",
        "breast_tenderness|Tender breasts|sore breasts,breast pain,boobs|sy",
        "headache|Headache|head pain,head hurts|sy",
        "migraine|Migraine|aura,severe headache|sy",
        "back_pain|Back pain|lower back,backache|sy",
        "joint_pain|Joint pain|achy joints,stiff joints|sy",
        "muscle_aches|Muscle aches|sore muscles,body aches|sy",
        "dizzy|Dizzy|lightheaded,faint,woozy|sy",
        "hot_flashes|Hot flushes|hot flashes,flushing,sudden heat|sy",
        "night_sweats|Night sweats|sweaty at night,damp sheets|sy",
        "swollen_hands|Swollen hands|puffy hands,tight rings,swelling|sy",
        "water_retention|Water retention|puffy,fluid,swollen|sy",
        "pelvic_pain|Pelvic pain|lower tummy,pelvis,groin|sy",
        "ovulation_pain|Ovulation twinge|one sided pain,mid cycle pain|sy",
        "leg_heaviness|Heavy legs|tired legs,leg ache|sy",
        "chills|Chills|shivers,cold|sy",
    ),
    "skin_hair": (
        "acne|Acne|spots,pimples,breakouts|sy",
        "oily_skin|Oily skin|greasy,shiny|sy",
        "dry_skin|Dry skin|flaky,tight skin|sy",
        "hair_loss|Hair shedding|hair fall,thinning,losing hair|sy",
        "oily_hair|Oily hair|greasy hair,lank|sy",
        "dry_hair|Dry hair|brittle hair,frizzy|sy",
        "glowing_skin|Glowing skin|radiant,clear skin,glow|po",
        "itchy_skin|Itchy skin|itch,rash,irritated|sy",
        "sensitive_skin|Sensitive skin|reactive,redness|sy",
    ),
    "digestion": (
        "nausea|Nausea|queasy,feeling sick,sick|sy",
        "constipation|Constipation|hard stools,backed up|sy",
        "diarrhoea|Diarrhoea|loose stools,runny,diarrhea|sy",
        "gas|Gas|wind,trapped wind,flatulence|sy",
        "heartburn|Heartburn|reflux,acid|sy",
        "stomach_ache|Stomach ache|tummy ache,upset stomach|sy",
        "indigestion|Indigestion|upset tummy,heavy stomach|sy",
        "vomiting|Vomiting|being sick,throwing up|sy",
        "bowel_changes|Bowel changes|irregular bowels,toilet habits|sy",
        "regular_digestion|Digestion felt easy|comfortable,regular|po",
    ),
    "appetite": (
        "cravings_sweet|Sweet cravings|sugar,chocolate,sweets|ne",
        "cravings_salty|Salty cravings|crisps,savoury,chips|ne",
        "cravings_carbs|Carb cravings|bread,pasta,rice|ne",
        "low_appetite|Low appetite|not hungry,off food|ne",
        "high_appetite|Hungrier than usual|extra hungry,always hungry|ne",
        "thirsty|Very thirsty|dry mouth,thirst|ne",
        "skipped_meals|Skipped meals|missed meals,didnt eat|li",
        "ate_well|Ate regular meals|balanced,well fed|po",
    ),
    "sleep_energy": (
        "fatigue|Tired|fatigue,exhausted,drained|sy",
        "insomnia|Trouble falling asleep|insomnia,cant sleep,awake|sy",
        "energetic|Energetic|full of energy,bouncy,lively|po",
        "poor_sleep|Poor sleep|bad night,slept badly,broken sleep|sy",
        "slept_well|Slept well|good sleep,rested|po",
        "restless_sleep|Restless sleep|tossing,turning,woke often|sy",
        "vivid_dreams|Vivid dreams|strange dreams,nightmares|ne",
        "oversleeping|Slept more than usual|long sleep,overslept|ne",
        "daytime_sleepy|Sleepy in the day|drowsy,nodding off|sy",
        "low_energy|Low energy|flat,sluggish,wiped out|sy",
        "woke_early|Woke very early|early waking,up before alarm|sy",
    ),
    "activity": (
        "exercised|Exercised|workout,gym,training|po",
        "walked|Went for a walk|walking,steps,stroll|po",
        "yoga|Yoga|pilates,stretching class|po",
        "strength_training|Strength training|weights,lifting|po",
        "ran|Went running|run,jog,cardio|po",
        "swam|Swimming|swim,pool|po",
        "cycling|Cycling|bike,spin|po",
        "dance|Dancing|dance class,zumba|po",
        "rest_day|Rest day|day off,took it easy|ne",
        "stretching|Gentle stretching|mobility,stretch|po",
        "low_exercise_energy|Not up for exercise|no energy to work out,skipped workout|ne",
        "sports|Played a sport|team sport,badminton,football|po",
    ),
    "lifestyle": (
        "alcohol|Alcohol|drinks,wine,beer|li",
        "caffeine|Caffeine|coffee,tea,energy drink|li",
        "stress_high|High stress|stressed,pressure,tense|li",
        "stress_low|Low-stress day|chilled,relaxed day|po",
        "travel|Travel|trip,journey,away from home|li",
        "travel_jet_lag|Jet lag|time zone,flight|li",
        "illness|Feeling unwell|ill,cold,flu,sick day|sy",
        "fever|Fever|high temperature,temperature,feverish|sy",
        "late_night|Late night|stayed up,up late|li",
        "night_shift|Night shift|shift work,nights|li",
        "smoked|Smoked or vaped|smoking,cigarettes,vape|li",
        "hydrated_well|Drank plenty of water|hydrated,water|po",
        "busy_work|Busy at work|deadline,workload|li",
        "exams|Exams or deadlines|study,test|li",
        "screen_late|Late-night screens|phone in bed,scrolling|li",
        "meditation|Meditation or breathing|mindfulness,breathing,calm time|po",
        "time_outside|Time outdoors|fresh air,sunshine,nature|po",
    ),
    "sexual": (
        "sex_drive_high|Higher sex drive|libido high,in the mood|ne",
        "sex_drive_low|Lower sex drive|libido low,not in the mood|ne",
        "had_sex|Had sex|intercourse,intimacy|ne",
        "protected_sex|Used a condom|condom,protected|ne",
        "unprotected_sex|Sex without a condom|unprotected,no condom|ne",
        "pain_during_sex|Pain during sex|painful sex,uncomfortable|sy",
        "vaginal_dryness|Vaginal dryness|dry,lubrication|sy",
    ),
    "reproductive": (
        "spotting_between|Spotting between periods|light bleeding,breakthrough|sy",
        "spotting_after_sex|Spotting after sex|bleeding after sex,light bleeding|sy",
        "heavy_flow|Heavy flow|soaking,heavy period,flooding|sy",
        "light_flow|Light flow|scanty,light period|ne",
        "clots|Clots|blood clots,lumps|sy",
        "brown_discharge|Brown discharge|brown spotting,old blood|ne",
        "egg_white_mucus|Egg-white mucus|stretchy,clear mucus,fertile mucus|ne",
        "creamy_discharge|Creamy discharge|white discharge,lotion|ne",
        "watery_discharge|Watery discharge|wet,clear discharge|ne",
        "dry_mucus|Dry, little mucus|no discharge,dry days|ne",
        "odd_discharge|Unusual discharge|smelly,itchy,different discharge|sy",
        "positive_ovulation_test|Positive ovulation test|lh surge,opk positive|ne",
        "negative_ovulation_test|Negative ovulation test|lh negative,opk negative|ne",
        "positive_pregnancy_test|Positive pregnancy test|pregnancy test positive,two lines|ne",
        "negative_pregnancy_test|Negative pregnancy test|pregnancy test negative,one line|ne",
        "period_late|Period later than expected|late,missed,overdue|ne",
        "vaginal_itching|Vaginal itching|itchy,irritation,sore|sy",
    ),
    "medication": (
        "took_painkiller|Took a painkiller|pain relief,paracetamol,ibuprofen|ne",
        "took_supplement|Took a supplement|vitamin,supplements,tablet|ne",
        "took_iron_supplement|Took iron|iron tablet,ferrous|ne",
        "took_vitamin|Took a vitamin|multivitamin,vitamin d,folic acid|ne",
        "took_birth_control_pill|Took birth control pill|the pill,contraceptive pill,oral contraceptive|ne",
        "missed_pill|Missed a pill or dose|forgot pill,late dose,forgot medicine|ne",
        "took_thyroid_medicine|Took thyroid medicine|thyroid tablet,levothyroxine|ne",
        "took_antibiotics|Took antibiotics|antibiotic course,infection tablets|ne",
        "took_antihistamine|Took an antihistamine|allergy tablet,hay fever|ne",
        "took_antacid|Took an antacid|heartburn tablet,indigestion remedy|ne",
        "took_hormone_therapy|Used hormone therapy|hrt,patch,gel|ne",
        "took_antidepressant|Took antidepressant|mood medicine,ssri|ne",
        "new_medication|Started a new medicine|new tablet,changed medicine|ne",
        "took_fever_reducer|Took something for fever|temperature tablet,paracetamol|ne",
    ),
    "other": (
        "good_day|Good day|great day,easy day|po",
        "hard_day|Hard day|rough day,tough day|ne",
        "felt_normal|Felt pretty normal|usual,nothing special,fine|po",
        "something_unusual|Something felt unusual|odd,different,new symptom|ne",
        "measured_late|Temperature taken at a different time|late reading,different time,off schedule|ne",
        "mention_to_clinician|Want to mention to my clinician|ask doctor,follow up,note for doctor|ne",
        "breastfeeding|Breastfeeding|nursing,feeding baby,chestfeeding|ne",
    ),
}

# things that make a morning temperature unreliable
_DISTURBS_BBT = frozenset({
    "illness", "fever", "alcohol", "late_night", "poor_sleep", "travel", "travel_jet_lag",
    "night_shift", "restless_sleep", "took_antibiotics", "new_medication",
    "took_fever_reducer", "measured_late",
})


def _build_catalogue() -> tuple[dict, ...]:
    out = []
    for group, lines in _SPEC.items():
        for line in lines:
            cid, label, kws, sig = line.split("|")
            keywords = tuple(kws.split(","))
            assert 2 <= len(keywords) <= 5, cid
            out.append({
                "id": cid, "label": label, "group": group, "keywords": keywords,
                "signal": _SIGNALS[sig], "disturbs_bbt": cid in _DISTURBS_BBT,
            })
    return tuple(out)


CHIP_CATALOGUE: tuple[dict, ...] = _build_catalogue()
CHIP_BY_ID: dict[str, dict] = {c["id"]: c for c in CHIP_CATALOGUE}
assert len(CHIP_BY_ID) == len(CHIP_CATALOGUE), "duplicate chip ids"
assert set(_SPEC) == {g for g, _ in CHIP_GROUPS}, "chip groups out of sync"
assert _DISTURBS_BBT <= set(CHIP_BY_ID), "unknown bbt chip id"

_GROUP_IDS = frozenset(g for g, _ in CHIP_GROUPS)


def _score(chip: dict, q: str) -> int | None:
    label = chip["label"].lower()
    cid = chip["id"].replace("_", " ")
    if q in (label, cid):
        return 0
    if label.startswith(q) or cid.startswith(q):
        return 1
    kws = chip["keywords"]
    if any(k.startswith(q) for k in kws) or any(w.startswith(q) for w in label.split()):
        return 2
    if q in label or q in cid or any(q in k for k in kws):
        return 3
    return None


def search_chips(query: str | None, group: str | None = None, limit: int = 60) -> list[dict]:
    """Case-insensitive chip search; never raises. Empty query returns catalogue order."""
    try:
        limit = max(1, min(300, int(limit)))
    except (TypeError, ValueError):
        limit = 60
    pool = CHIP_CATALOGUE
    if group:
        pool = tuple(c for c in pool if c["group"] == group)
    q = " ".join(str(query).lower().split()) if query is not None else ""
    if not q:
        return list(pool[:limit])
    scored = [(s, i, c) for i, c in enumerate(pool) if (s := _score(c, q)) is not None]
    scored.sort(key=lambda t: (t[0], t[1]))
    return [c for _, _, c in scored[:limit]]


def chips_by_group(query: str | None = None, group: str | None = None) -> list[dict]:
    """Grouped chips in CHIP_GROUPS order; only non-empty groups."""
    found = search_chips(query, group, limit=300)
    out = []
    for gid, glabel in CHIP_GROUPS:
        chips = [c for c in found if c["group"] == gid]
        if chips:
            out.append({"id": gid, "label": glabel, "chips": chips})
    return out


# --------------------------------------------------------------------------- phases, modes, weather
PHASE_INFO: dict[str, dict] = {
    "menstrual": {
        "label": "Menstrual phase",
        "summary": "The days you bleed, counted from day 1. Many people feel lower energy or cramps early on, and often lighter as bleeding eases.",
    },
    "follicular": {
        "label": "Follicular phase",
        "summary": "From the end of your period until ovulation. Many people notice energy and mood lifting as oestrogen rises, though this varies.",
    },
    "ovulatory": {
        "label": "Ovulatory phase",
        "summary": "Around the time an egg is released, often mid-cycle. Some people notice clearer mucus, a one-sided twinge or a higher sex drive.",
    },
    "luteal": {
        "label": "Luteal phase",
        "summary": "From ovulation until your next period. Many people notice PMS-type changes like tender breasts, bloating or mood dips near the end.",
    },
}

MODE_LABELS: dict[str, str] = {
    "track": "Track my cycle",
    "birth_control": "On birth control",
    "conceive": "Trying to conceive",
    "pregnancy": "Pregnancy",
    "postpartum": "After birth",
    "perimenopause": "Perimenopause",
}

WEATHER_LINES: dict[str, dict[str, tuple[str, ...]]] = {
    "bright": {
        "menstrual": (
            "We're seeing a lighter day than usual for this stretch. Enjoy it gently.",
            "Even in these days there's a little sunshine in today's logs.",
        ),
        "follicular": (
            "Sunny skies in the logs today. We're feeling hopeful about the days ahead.",
            "A bright morning here. Let's make the most of the lift, at your pace.",
        ),
        "ovulatory": (
            "Warm and bright around here today. Many people feel their best at this point.",
            "We're catching a little extra sparkle in today's logs.",
        ),
        "luteal": (
            "A surprisingly clear sky for this part of the cycle. We'll gladly take it.",
            "Bright spells today, even this late in the cycle. Lovely to see.",
        ),
        "none": (
            "A bright one today. We're glad to see it.",
            "Clear skies in the logs. Let's enjoy it together.",
        ),
    },
    "steady": {
        "menstrual": (
            "Calm and even today. We can take these days one at a time.",
            "Steady weather in the logs. Nothing needs to be rushed.",
            "A quiet, level day. We're here whichever way it turns.",
        ),
        "follicular": (
            "Fairly even skies today. A good day for easy rhythms.",
            "Steady and settled. We're keeping you company.",
        ),
        "ovulatory": (
            "Even weather in the middle of the cycle. We're just watching along.",
            "A steady day. Whatever you feel is welcome here.",
        ),
        "luteal": (
            "Even-keeled so far. We'll keep an eye out together as the cycle winds down.",
            "Steady weather, with the cycle slowly turning. We're here.",
        ),
        "none": (
            "Steady skies today. Nothing much to report, and that's fine.",
            "An even day. We're here whatever the weather does next.",
        ),
    },
    "heavier": {
        "menstrual": (
            "A heavier-feeling day. A gentler pace is a fine plan today.",
            "Today looks a bit stormy. Rest counts as doing something.",
            "We're sitting with you through the heavy bits. Small steps are plenty.",
        ),
        "follicular": (
            "Cloudier than this part of the cycle often brings, and that's okay. Go easy today.",
            "A heavy-ish day. We can take it slowly together.",
        ),
        "ovulatory": (
            "Heavier skies than usual. It's okay to give today less than everything.",
            "A cloudy one. Be as gentle with yourself as you'd be with a friend.",
        ),
        "luteal": (
            "Clouds are gathering, which many people notice late in the cycle. Be kind to yourself.",
            "A heavier day. A gentler pace is a fine plan today.",
            "It's okay for today to feel heavy. We're right here.",
        ),
        "none": (
            "A heavier day. A gentler pace is a fine plan today.",
            "Today feels weighty. Rest, water and kindness all count.",
        ),
    },
}

# --------------------------------------------------------------------------- education
_ALL_MODES = tuple(MODE_LABELS)
_G = GENERAL_KNOWLEDGE_LABEL


def _article(aid, title, summary, tags, modes, *body):
    return {
        "id": aid, "title": title, "summary": summary, "body": tuple(body),
        "tags": tuple(tags), "modes": tuple(modes), "label": _G,
        "source_class": "EXTERNAL_KNOWLEDGE",
    }


EDUCATION_ARTICLES: tuple[dict, ...] = (
    _article(
        "how_the_cycle_works", "How the menstrual cycle works",
        "A cycle runs from the first day of one period to the day before the next. It has four phases, and what people feel in each differs.",
        ("cycle", "phases", "basics", "hormones"), _ALL_MODES,
        "Your cycle is counted from day 1 of one period to the day before the next period starts. Hormones rise and fall through the cycle, and these shifts drive the four phases below.",
        "Menstrual phase: the days you bleed, as the womb lining is shed. Some people have cramps, low energy or a heavy feeling early on.",
        "Follicular phase: from your period until ovulation. Oestrogen rises, and many people notice energy and mood lifting, though this varies a lot from person to person.",
        "Ovulatory phase: an egg is released around the middle of a typical cycle. Some people notice clearer, stretchy mucus, a twinge on one side, or a higher sex drive.",
        "Luteal phase: from ovulation until your next period. Many people notice PMS-type changes in the last few days, such as tender breasts, bloating or mood dips. Every cycle is a little different.",
    ),
    _article(
        "typical_cycle_length", "What is a typical cycle length?",
        "Cycles of 21 to 35 days are usual for adults, and longer cycles are common in the first years of periods. Some variation is normal.",
        ("cycle length", "normal", "variation", "teens"),
        _ALL_MODES,
        "Cycle length is the number of days from the first day of one period to the first day of the next. For most adults, anything from 21 to 35 days is considered usual.",
        "In teenagers, cycles are often longer and less regular for the first few years after periods start. Cycles of up to about 45 days can be usual at that age.",
        "Even if your average is steady, one cycle can run a few days early or late. Stress, illness, travel, changes in sleep or routine, and many other things can nudge it.",
        "A cycle that is often shorter than 21 days or longer than 35 days is worth mentioning to a clinician, so it can be looked at. It does not mean something is wrong.",
    ),
    _article(
        "period_length_and_flow", "Period length and flow",
        "Periods often last a few days up to a week. Very heavy flow, or bleeding for more than 7 days, is worth getting checked.",
        ("period", "flow", "heavy", "bleeding"),
        _ALL_MODES,
        "Many periods last between 2 and 7 days. Flow is often heavier at the start and lighter by the end. What is usual for you matters more than any average.",
        "Bleeding for more than 7 days is worth mentioning to a clinician.",
        "Flow that stops you doing your usual things, or leaves you feeling very tired, dizzy or breathless, is also worth raising. Noting how many pads or tampons you use can help that conversation.",
        "Get urgent help if you are soaking through a pad or tampon every hour for two hours or more. Contact a doctor, an urgent care service or your local emergency service straight away.",
    ),
    _article(
        "period_pain", "Period pain and when to mention it",
        "Mild to moderate cramps are common. Pain that stops you living normally, or that has changed, is worth mentioning to a clinician.",
        ("pain", "cramps", "period pain", "dysmenorrhoea"),
        _ALL_MODES,
        "Many people have some cramping in the lower tummy, back or thighs just before or during a period. It comes from the womb tightening to shed its lining.",
        "Many people find that heat, such as a hot water bottle or warm bath, gentle movement and rest can help. A pharmacist can talk through pain relief options that suit you.",
        "It is worth mentioning to a clinician if pain keeps you from school, work or normal life, is getting worse, began suddenly after years of easier periods, or comes with heavy bleeding.",
        "Many people are told painful periods are just normal for years. Pain that disrupts your life deserves to be taken seriously.",
        "Sudden severe pain, fainting or fever needs urgent care.",
    ),
    _article(
        "pms_changes", "Changes before a period (PMS)",
        "Many people notice physical and emotional changes in the days before a period. If they are hard to cope with, it is worth talking to someone.",
        ("pms", "premenstrual", "mood", "symptoms"),
        _ALL_MODES,
        "Premenstrual changes are shifts many people notice in the one to two weeks before a period, which often ease soon after bleeding starts.",
        "Common ones include tender breasts, bloating, headaches, tiredness, food cravings, trouble sleeping, and feeling irritable, tearful or low.",
        "Your own logs can show whether a pattern repeats from cycle to cycle. That can be reassuring, and useful to share with a clinician.",
        "If mood changes are severe, make daily life hard to manage, or leave you feeling hopeless, talk to a clinician or someone you trust.",
        "If you ever feel unsafe or think about harming yourself, contact your local emergency service or a crisis line straight away.",
    ),
    _article(
        "irregular_cycles", "Irregular cycles and common reasons",
        "Cycles can vary for many reasons. A clinician can look into lasting changes; Bubbles cannot tell you why a cycle is irregular.",
        ("irregular", "missed period", "stress", "thyroid", "pcos"),
        _ALL_MODES,
        "A cycle is often called irregular when its length changes a lot from month to month, or when periods come less often than every 35 days or more often than every 21.",
        "Reasons a clinician may look into include stress, changes in sleep, a big change in weight, a lot of exercise, breastfeeding, thyroid conditions and polycystic ovary syndrome (PCOS). Some medicines can also change cycles.",
        "In the first years of periods, and in the years before menopause, irregular cycles are also very common.",
        "Missing three or more periods in a row, when you are not pregnant or menopausal, is worth raising with a clinician. Your logs and dates make that conversation easier.",
        "Bubbles shows wider ranges when your cycle lengths vary a lot, so its estimates stay honest.",
    ),
    _article(
        "pcos_awareness", "PCOS awareness",
        "PCOS is a common hormone-related condition that a clinician can assess. Bubbles cannot tell whether someone has it.",
        ("pcos", "polycystic", "hormones", "irregular"),
        ("track", "birth_control", "conceive", "perimenopause"),
        "Polycystic ovary syndrome (PCOS) is a common hormone-related condition. Many people with it have irregular or infrequent periods.",
        "Other things people sometimes notice include acne, extra hair growth on the face or body, thinning hair on the scalp, and trouble conceiving. Noticing one of these does not mean you have it.",
        "A clinician can look into it with a conversation, blood tests and sometimes an ultrasound. Bubbles cannot tell whether someone has PCOS.",
        "If several of these sound familiar, your cycle history can help a clinician. Support and options exist.",
    ),
    _article(
        "endometriosis_awareness", "Endometriosis awareness",
        "Endometriosis can cause long-lasting pelvic pain. Pain that disrupts your life is worth raising with a clinician.",
        ("endometriosis", "pelvic pain", "painful periods"),
        ("track", "birth_control", "conceive", "perimenopause"),
        "Endometriosis is when tissue similar to the womb lining grows in other places, often in the pelvis. It affects people in different ways.",
        "People sometimes notice painful periods, pelvic pain at other times, pain during or after sex, painful bowel movements or peeing during periods, heavy bleeding, deep tiredness, or trouble conceiving.",
        "It can take a long time to be recognised, partly because period pain is so often brushed off. Pain that disrupts your life is worth raising.",
        "Only a clinician can look into this. Bubbles cannot tell whether someone has endometriosis. A symptom diary, like the one you can keep here, can help the conversation.",
    ),
    _article(
        "bbt_basics", "Basal body temperature: how to, and its limits",
        "Basal body temperature can suggest that ovulation probably happened, after the fact. It is easily disturbed and is not precise.",
        ("temperature", "bbt", "ovulation", "thermometer"),
        ("track", "conceive", "perimenopause"),
        "Basal body temperature is your temperature at rest. Many people measure it with a sensitive thermometer at the same time every morning, before getting up, eating or drinking.",
        "After ovulation, hormones usually raise it slightly, and it stays higher until the next period. Bubbles looks for three higher readings in a row compared with the previous six.",
        "Illness, fever, alcohol, a late night, poor sleep, travel across time zones and some medicines can all make a reading unreliable. Flagging those days lets Bubbles treat them with care.",
        "A rise only shows after ovulation has happened, so it cannot predict ovulation in the current cycle. It is also not birth control and cannot be used to prevent pregnancy.",
        "A missing or odd day is normal. Patterns over several cycles matter more than any one reading.",
    ),
    _article(
        "ovulation_tests", "Ovulation (LH) tests",
        "Ovulation tests detect a hormone surge that usually comes a day or two before ovulation. They point to a likely window, not a certainty.",
        ("ovulation test", "lh", "opk", "fertile"),
        ("track", "conceive", "perimenopause"),
        "Ovulation tests, also called LH tests, are urine strips or devices that look for a rise in luteinising hormone (LH). This surge usually comes about a day or two before an egg is released.",
        "A positive test suggests ovulation may be near. It does not confirm that ovulation has happened.",
        "Follow the instructions in the pack for when in the cycle to start testing and what time of day to test. Drinking a lot of fluid before testing can make results harder to read.",
        "Some medicines, hormonal methods and conditions can affect results, and a pharmacist or clinician can tell you more. These tests are not birth control and cannot be relied on to prevent pregnancy.",
    ),
    _article(
        "fertile_window", "The fertile window",
        "The fertile window is roughly the five days before ovulation plus ovulation day. It is an estimate and is not contraception.",
        ("fertile window", "ovulation", "conceive", "timing"),
        ("track", "conceive", "perimenopause"),
        "The fertile window is the stretch of the cycle when pregnancy is possible. It is roughly the five days before ovulation, plus the day of ovulation itself.",
        "That is because sperm can live for several days in the body, while an egg survives for only a day or so after it is released.",
        "Ovulation does not always happen on the same day each cycle. Stress, illness, travel and other things can shift it, so Bubbles shows a range rather than one day.",
        "These estimates come from your own logs and can be wrong. They are not birth control. Please do not rely on them to prevent pregnancy; a clinician or pharmacist can talk through methods designed for that.",
        "If you are trying to conceive, the fertile window can help you notice patterns that may be useful for timing.",
    ),
    _article(
        "pregnancy_tests", "Pregnancy tests: the basics",
        "Home tests look for a pregnancy hormone in urine. Follow the pack, and ask a clinician to confirm a result.",
        ("pregnancy test", "hcg", "missed period", "testing"),
        ("track", "birth_control", "conceive", "pregnancy"),
        "Home pregnancy tests look for the hormone hCG in urine. Many can be used from the first day of a missed period, and some a few days earlier, but the pack will tell you.",
        "Testing too early can give a negative result even when pregnant, because the hormone is still low. Morning urine is often the most concentrated.",
        "Follow the instructions on the pack, including how long to wait before reading the result.",
        "If a test is negative but your period still hasn't come, try again in a few days. If a test is positive, or you are unsure, ask a clinician to confirm and talk about next steps.",
        "Missed periods can also have other causes, such as stress or illness. Bubbles cannot confirm a pregnancy.",
    ),
    _article(
        "after_hormonal_birth_control", "Cycles after hormonal birth control",
        "Cycles can take a few months to settle after hormonal birth control. Wider ranges are expected during that time.",
        ("birth control", "pill", "coming off", "contraception", "settling"),
        ("birth_control", "track", "conceive"),
        "Hormonal methods such as the pill, patch, ring, injection or implant change, or can stop, your usual bleeding pattern. After a method ends, your body's own cycle needs time to restart.",
        "For many people, periods return within a few months. It can take longer, and the first cycles may be longer, shorter or different from what you remember.",
        "Periods from before the method started may not show how your cycle looks now. Bubbles shows wide ranges and says learning until it has enough cycles.",
        "Some people ovulate soon after a method ends, others take much longer. If avoiding or planning pregnancy matters to you, a clinician can talk it through before you make any change.",
        "If periods have not settled after a few months, or you have symptoms that worry you, a clinician can look into it.",
    ),
    _article(
        "after_birth", "After birth: bleeding and periods",
        "Bleeding for around six weeks after birth is lochia, not a period. Cycles can take months to return, and breastfeeding changes things.",
        ("postpartum", "lochia", "breastfeeding", "after birth"),
        ("postpartum", "track"),
        "After birth, bleeding and discharge called lochia can go on for around six weeks. It is expected, starts heavier and red, and gradually gets lighter. It is not a period.",
        "Get urgent help if you are soaking a pad every hour, passing large clots, feeling faint, or have a fever or foul-smelling discharge. Contact your midwife, doctor or local emergency service.",
        "Periods can take months to come back, and the first ones may be heavier, lighter or irregular. Breastfeeding often delays them, but not for everyone and not on a fixed schedule.",
        "Because of this, Bubbles' predictions are low-confidence in the months after birth.",
        "Your postnatal check, midwife or health visitor are good people to ask about bleeding, mood and anything else that feels off.",
    ),
    _article(
        "perimenopause", "Perimenopause: when cycles change",
        "Perimenopause is the lead-up to menopause. Cycles often change, so Bubbles shows wider ranges.",
        ("perimenopause", "menopause", "hot flushes", "irregular"),
        ("perimenopause", "track"),
        "Perimenopause is the time before periods stop for good. It often starts in the 40s but can begin earlier or later. Hormone levels go up and down, so cycles can become irregular.",
        "Cycles may get shorter, longer or skip, and flow may change. Many people also notice hot flushes, night sweats, sleep changes or mood changes.",
        "Menopause is usually confirmed after 12 months without a period. Any bleeding after that point is worth mentioning to a clinician.",
        "Bleeding that is very heavy, comes between periods or after sex, or lasts much longer than usual is also worth raising with a clinician at any stage.",
        "Periods can stay unpredictable, so Bubbles' estimates are wide here. They are not birth control. If pregnancy matters to you either way, ask a clinician.",
    ),
    _article(
        "how_bubbles_predicts", "How Bubbles makes predictions",
        "Bubbles uses your recent cycles to estimate ranges, not exact dates. Estimates can be wrong and are marked learning until there are three cycles.",
        ("predictions", "estimates", "ranges", "learning", "irregular mode"),
        _ALL_MODES,
        "Bubbles looks at the lengths of your logged cycles, gives more weight to recent ones, and estimates when your next period may start as a range of days rather than one date.",
        "Until Bubbles has seen at least three cycles, it labels estimates as learning. They get better as you log more, but they are still estimates.",
        "If your cycle lengths vary a lot, Bubbles switches to an irregular mode and shows wider ranges so it does not sound surer than it is.",
        "Ovulation is usually estimated about 14 days before the next period, within a range of roughly 10 to 16 days.",
        "Predictions can be wrong. Illness, stress, travel, medicines and many other things can change a cycle. They are estimates from your own logs and are not birth control.",
    ),
    _article(
        "when_to_talk_to_clinician", "When to talk to a clinician",
        "A short list of changes worth mentioning to a doctor or nurse, and the signs that need urgent care.",
        ("clinician", "doctor", "urgent", "red flags"),
        _ALL_MODES,
        "Worth mentioning to a clinician: cycles often shorter than 21 days or longer than 35; periods lasting more than 7 days; missing three or more periods in a row when not pregnant or menopausal.",
        "Also worth mentioning: pain that disrupts daily life, bleeding between periods or after sex, a sudden big change from your usual pattern, or any bleeding after 12 months without a period.",
        "And: mood changes that feel hard to cope with, or symptoms that keep coming back and worry you.",
        "Needs urgent care: soaking a pad or tampon every hour for two hours or more, sudden severe pain, fainting, or bleeding or pain while pregnant. Contact a doctor or your local emergency service.",
        "Your Bubbles logs and report can be shared with your clinician to help the conversation. They are your own notes, not a medical assessment.",
    ),
    _article(
        "cycle_sleep_mood_energy", "Cycle, sleep, mood, energy and exercise",
        "Many people notice patterns in sleep, mood, energy and exercise across the cycle. Your logs show patterns, not causes.",
        ("sleep", "mood", "energy", "exercise", "patterns"),
        _ALL_MODES,
        "Hormone levels change across the cycle, and many people notice sleep, mood, energy or exercise feel different at different times. Some notice little at all.",
        "Common reports include lighter or more broken sleep and lower energy in the days before a period, and a lift in energy after it. These are common experiences, not rules.",
        "Bubbles can show patterns in your own logs, like energy often dipping in the last days of a cycle. A pattern is not proof of a cause; stress, food, work and sleep all play a part.",
        "You can plan around what you notice: harder days may suit rest, easier days gentle movement or whatever feels good. There is no right amount of exercise at any phase.",
        "If tiredness or low mood is severe or does not lift, talk to a clinician.",
    ),
)
assert len({a["id"] for a in EDUCATION_ARTICLES}) == len(EDUCATION_ARTICLES), "duplicate article ids"


def _plain(a: dict) -> dict:
    return {k: list(v) if isinstance(v, tuple) else v for k, v in a.items()}


def articles(mode: str | None = None, topic: str | None = None) -> list[dict]:
    """Education articles as JSON-friendly dicts, filtered by mode and/or topic text."""
    t = " ".join(str(topic).lower().split()) if topic else ""
    out = []
    for a in EDUCATION_ARTICLES:
        if mode and mode not in a["modes"]:
            continue
        if t and t not in " ".join((a["title"], a["summary"], *a["tags"])).lower():
            continue
        out.append(_plain(a))
    return out


# --------------------------------------------------------------------------- pregnancy
_NUDGE = " Keep your antenatal appointments."

_WEEK_BASE: dict[int, str] = {
    1: "Week 1 is counted from the first day of your last period, so the pregnancy hasn't started yet. Your body is simply beginning a new cycle.",
    2: "Week 2 is still counted from your last period. In a 28-day cycle, ovulation often happens around the end of this week.",
    3: "Fertilisation usually happens around now. The fertilised egg starts dividing as it travels towards the womb.",
    4: "The embryo usually settles into the womb lining around now. A missed period is often the first thing many people notice.",
    5: "Many people start to notice tiredness, tender breasts or needing the toilet more often around now. Others notice nothing yet, which is normal too.",
    6: "A heartbeat can usually be seen on ultrasound around now. Nausea and tiredness are common in these early weeks.",
    7: "Nausea, which can happen at any time of day, is common now. If it is hard to keep anything down, tell your midwife or doctor.",
    8: "Tiredness, nausea and mood swings are very common now. Ask your midwife or doctor about vitamins.",
    9: "Many people feel emotional or very tired this week. Both are common in the first trimester, and rest is welcome.",
    10: "Early pregnancy symptoms can be strong or barely there; both are normal. Mention anything that worries you to your midwife.",
    11: "The first trimester is nearly over. Some people find nausea starts to ease around now, while others find it lasts longer.",
    12: "A first scan is often offered around the end of the first trimester. Many people find nausea starts to ease.",
    13: "The second trimester begins around now. Many people find energy returns and nausea settles, though it varies a lot.",
    14: "Many people feel more energetic in the second trimester. Your body is still changing, so go at your own pace.",
    15: "Some people notice a pulling feeling at the sides of the tummy as the womb grows. Mention pain that is strong or does not settle.",
    16: "Baby's first movements are often felt between weeks 16 and 25, like flutters or bubbles.",
    17: "Movements may be felt now or soon. Not being sure yet is common, especially in a first pregnancy.",
    18: "The mid-pregnancy scan is usually offered around weeks 18 to 21. Write down any questions you'd like to ask.",
    19: "Backache, leg cramps and skin changes are common now. Tell your midwife if anything worries you.",
    20: "You are about halfway there. Movements are often easier to notice now.",
    21: "Movements are often easier to notice now. Each baby has their own pattern, so it helps to get to know yours.",
    22: "Heartburn, swollen ankles and tiredness are common as the womb grows. Tell your midwife about sudden swelling of the face or hands.",
    23: "Some people notice practice tightenings (Braxton Hicks) from around now. They are usually irregular and ease with rest.",
    24: "Sleep can get harder as the bump grows. Many people find extra pillows help.",
    25: "Movements are usually felt by now. If you haven't felt any, tell your midwife.",
    26: "Backache and pelvic aches are common. Gentle movement and rest help many people; ask your midwife if pain is strong.",
    27: "The second trimester is nearly over. Tiredness often returns, and it's fine to slow down.",
    28: "The third trimester usually starts now. If baby's movements slow or change, contact your midwife or maternity unit the same day.",
    29: "Breathlessness, heartburn and needing the toilet more often are common as baby grows. Tell your midwife about anything worrying.",
    30: "Many people feel tired again and find sleep harder. Rest when you can; going to sleep on your side is often suggested now.",
    31: "Practice tightenings may become more noticeable. Regular, painful contractions before week 37 need a call to your midwife or maternity unit.",
    32: "You may be thinking about birth plans and packing a bag. Your midwife can talk through your options.",
    33: "Aches, tiredness and trouble sleeping are common. Be kind to yourself; many people feel the same.",
    34: "Routine checks like blood pressure and bump measurements continue. They are how your midwife keeps an eye on you both.",
    35: "Many people feel pressure low in the pelvis and need the toilet often. Tell your midwife about swelling, bad headaches or vision changes.",
    36: "Baby often settles head-down by now, though some turn later. Your midwife can tell you the position at appointments.",
    37: "From week 37 a pregnancy is considered full term. Waiting can feel long; it helps to know the signs of labour and who to call.",
    38: "Many births happen between weeks 37 and 42. Tell your midwife about leaking fluid, regular contractions or reduced movements straight away.",
    39: "Every pregnancy is different, and labour can start before or after the due date. Keep your bag and phone numbers handy.",
    40: "Week 40 is the estimated due date. Only a small share of babies arrive on the day, so a few days either side is normal.",
    41: "Going past the due date is common, especially in a first pregnancy. Your midwife will talk you through what happens next.",
    42: "By week 42 your midwife or doctor will usually have talked with you about options and extra checks. Ask them anything on your mind.",
}
PREGNANCY_WEEK_NOTES: dict[int, str] = {
    w: (t + _NUDGE if w % 4 == 0 else t) for w, t in _WEEK_BASE.items()
}
assert set(PREGNANCY_WEEK_NOTES) == set(range(1, 43)), "pregnancy weeks 1..42 required"

TRIMESTER_NOTES: dict[int, str] = {
    1: "The first trimester (up to about week 12) is when the pregnancy is settling in. Many people feel tired, sick or emotional; others feel little. All of this can be normal.",
    2: "The second trimester (about weeks 13 to 27) is often calmer, with energy returning for many people. Movements are often first felt now, and a mid-pregnancy scan is usually offered.",
    3: "The third trimester (about week 28 to birth) brings tiredness, aches and thoughts of labour. Full term starts at week 37, and many babies arrive between weeks 37 and 42.",
}

PREGNANCY_NEXT_STEPS: dict[int, str] = {
    1: "Tell your midwife or doctor about the pregnancy and ask about booking antenatal care and vitamins.",
    2: "Book or keep your antenatal appointments; bring questions you have noted.",
    3: "Keep your antenatal appointments, note questions about labour, and save your midwife's contact number.",
}
PREGNANCY_URGENT_NOTE = (
    "Heavy bleeding, severe pain, fever, reduced baby movements or anything that frightens you needs "
    "urgent care: contact your midwife, doctor or local emergency service."
)

# --------------------------------------------------------------------------- mode notes
POSTPARTUM_NOTES: dict[str, str] = {
    "lochia": "Bleeding in the first six weeks or so after birth is expected and is not a period. Soaking a pad every hour or passing large clots needs urgent help.",
    "settling": "Cycles can take months to come back after birth, and breastfeeding can delay them. The first few can look different from before.",
    "low_confidence": "Predictions in this stage are low-confidence, so Bubbles shows wide ranges and will keep learning from your logs.",
}

PERIMENOPAUSE_NOTE = (
    "In perimenopause, cycles often get shorter, longer or less predictable, so Bubbles shows wider ranges. "
    "After 12 months without a period, any bleeding is worth mentioning to a clinician."
)
BIRTH_CONTROL_NOTE = (
    "Hormonal methods change bleeding patterns, so Bubbles hides ovulation and fertile-window estimates here. "
    "A withdrawal bleed is not a period in the same sense. Ask a clinician about missed pills."
)
CONCEIVE_NOTE = (
    "Estimates can help you notice patterns, but they can be wrong. The fertile window is about five days "
    "before ovulation plus the day of ovulation. If you have been trying for a while and feel worried, a clinician can help."
)

DISCLAIMER_LINES: tuple[str, ...] = (
    "Bubbles does not diagnose conditions, and this report is not a medical assessment.",
    "This report is built from information you recorded yourself.",
    "Estimates and predictions can be wrong.",
    "Please discuss anything that worries you with your clinician.",
)

__all__ = [
    "NOT_CONTRACEPTION_NOTICE", "GENERAL_KNOWLEDGE_LABEL", "CHIP_GROUPS", "CHIP_CATALOGUE",
    "CHIP_BY_ID", "search_chips", "chips_by_group", "PHASE_INFO", "MODE_LABELS", "WEATHER_LINES",
    "EDUCATION_ARTICLES", "articles", "PREGNANCY_WEEK_NOTES", "TRIMESTER_NOTES",
    "PREGNANCY_NEXT_STEPS", "PREGNANCY_URGENT_NOTE", "POSTPARTUM_NOTES", "PERIMENOPAUSE_NOTE",
    "BIRTH_CONTROL_NOTE", "CONCEIVE_NOTE", "DISCLAIMER_LINES",
]
