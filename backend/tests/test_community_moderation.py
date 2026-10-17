"""Community moderation rules (community_moderation.py): at least 60 bad and 60 good examples, English and Hinglish.

Good examples include the near-misses a careless filter would remove: loneliness, sex and body words used medically, a person's own
dose, "should I stop my medicine?", "don't stop your medicines", water and walking advice.
"""
from __future__ import annotations

import community_moderation as cm
import pytest

REMOVE = [
    # threats
    ("I will kill you", "threat"),
    ("you should kill yourself", "threat"),
    ("kys", "threat"),
    ("go die already", "threat"),
    ("I know where you live", "threat"),
    ("I'll find you and hurt you", "threat"),
    ("tujhe maar dunga", "threat"),
    ("mar jao tum sab", "threat"),
    ("tumhe jaan se maar denge", "threat"),
    ("kill all muslims", "hate"),
    # slurs and hate
    ("you filthy nigger", "hate"),
    ("what a retard", "hate"),
    ("faggot", "hate"),
    ("these chamar people are useless", "hate"),
    ("tranny freak", "hate"),
    ("hindus should die", "hate"),
    # abuse aimed at a person
    ("you are such a bitch", "abuse"),
    ("fuck you", "abuse"),
    ("tu pagal hai chutiya", "abuse"),
    ("madarchod tera dimaag kharab hai", "abuse"),
    ("shut up you bastard", "abuse"),
    ("you stupid asshole nobody asked", "abuse"),
    ("tum log harami ho", "abuse"),
    ("f*ck you idiot", "abuse"),
    ("you fuuuuck off", "abuse"),
    # sexual content
    ("send nudes", "sexual"),
    ("anyone want to hookup tonight", "sexual"),
    ("I am so horny", "sexual"),
    ("sexting karna hai kisi ko", "sexual"),
    ("bf video leak link", "sexual"),
    ("nangi photo bhejo", "sexual"),
    ("looking for a call girl", "sexual"),
    ("chudai ki baatein karo", "sexual"),
    ("pussy", "sexual"),
    ("selling onlyfans content", "sexual"),
    # selling and soliciting
    ("DM me for medicine", "selling"),
    ("WhatsApp me 9876543210 for cheap pills", "selling"),
    ("Order now 100% cure for PCOS call 98765 43210", "selling"),
    ("Buy now weight loss pills only Rs 499", "selling"),
    ("Inbox me for herbal product course", "selling"),
    ("dm karo sasti dawai milegi", "selling"),
    ("contact me for medicine at www.cheapmeds.com", "selling"),
    ("Abortion pills available whatsapp 9988776655", "selling"),
    ("Join my channel, telegram me for guaranteed cure pills", "selling"),
    # dose advice
    ("Take 500 mg paracetamol every 4 hours", "dose_advice"),
    ("just take 2 tablets of metformin and you will be fine", "dose_advice"),
    ("You should take 10 mg of melatonin every night", "dose_advice"),
    ("have two pills of iron daily", "dose_advice"),
    ("Try taking 1000 mcg of B12 daily", "dose_advice"),
    ("Double your dose to 20 mg", "dose_advice"),
    ("dolo 650 mg le lo", "dose_advice"),
    ("aap 2 goli kha lo subah", "dose_advice"),
    # stop your medicine or skip the doctor
    ("Stop taking your medicines, they are poison", "stop_medicine"),
    ("Throw away your insulin and eat bitter gourd", "stop_medicine"),
    ("don't take antibiotics, they ruin your gut", "stop_medicine"),
    ("no need to see a doctor for this, just drink tulsi tea", "stop_medicine"),
    ("tum dawai band karo, ghar ka ilaaj kar lo", "stop_medicine"),
    ("Skip your thyroid tablet, ashwagandha works better", "stop_medicine"),
    ("you don't need any medicines if you do yoga", "stop_medicine"),
    ("Never go to a doctor for this", "stop_medicine"),
]

HOLD = [
    ("behenchod", "profanity"),
    ("this is such bullshit honestly", "profanity"),
    ("What the fuck is wrong with my cycle", "profanity"),
    ("kutta saala", "profanity"),
    ("gandu", "profanity"),
    ("FREE FREE FREE FREE FREE FREE FREE FREE FREE", "spam"),
    ("buy buy buy buy buy buy buy buy", "spam"),
    ("aaaaaaaaaaaaaaaaaaaa", "spam"),
    ("https://a.example.com https://b.example.org check these out", "spam"),
    ("HELP ME I HAVE NOT SLEPT IN DAYS AND NOBODY CARES PLEASE ANSWER", "shouting"),
    ("You definitely have PCOS", "diagnosis_claim"),
    ("you have thyroid, no doubt", "diagnosis_claim"),
    ("This is clearly diabetes", "diagnosis_claim"),
    ("tumhe pakka PCOS hai", "diagnosis_claim"),
    ("ye PCOD hi hai", "diagnosis_claim"),
    ("You are pregnant for sure", "diagnosis_claim"),
    ("Turmeric milk cures diabetes 100%", "cure_claim"),
    ("ashwagandha reverses PCOS permanently", "cure_claim"),
    ("paracetamol 500 mg works best for cramps", "dose_review"),
    ("xxx pics here", "sexual_review"),
    ("follow me for tips", "selling_review"),
    ("earn money from home, link in bio", "selling_review"),
]

GOOD = [
    "I am so lonely, any advice?",
    "Anyone else get really bad cramps on day 1 of their period?",
    "I can't sleep at night, my mind keeps racing. What helped you?",
    "Feeling low after a breakup, just need to talk",
    "My periods are irregular since last year, is that common?",
    "How do I stop my hair fall? It's getting worse.",
    "I was diagnosed with PCOS last year and I'm still figuring things out",
    "I think I might have thyroid issues, anyone else tired all the time?",
    "Could it be anaemia? I feel dizzy when I stand up.",
    "My doctor told me to take 500 mg twice daily, anyone else on this?",
    "I take iron 65 mg every morning and it makes me nauseous",
    "Should I stop my medicine if I feel better?",
    "Please don't stop your medicines without asking your doctor",
    "Never skip your tablets, ask your doctor first",
    "Pain during sex lately, has anyone been through this?",
    "Boobs feel so sore before my period, is that normal?",
    "My vagina feels dry and itchy, what could help?",
    "Heavy bleeding on day 2, soaking a pad every 3 hours",
    "Drink 500 ml of water first thing in the morning, it helped my skin",
    "Take a 20 minute walk after dinner, it helps my sleep",
    "Have 2 eggs a day? I'm trying to build protein intake",
    "Eat a handful of almonds and see how you feel",
    "I feel like nobody understands me, anyone here?",
    "Mujhe period me bahut dard hota hai, koi tips?",
    "Neend nahi aati raat ko, kya karun?",
    "Aaj bahut akela feel kar raha hoon, kisi se baat karni hai",
    "Mera weight badh raha hai, thyroid ho sakta hai kya?",
    "Doctor ne bola dawai band mat karna",
    "Kya main apni dawai band kar sakti hoon?",
    "Maine dawai chhod di thi, ab pachtaa rahi hoon",
    "Does anyone use ashwagandha for stress? Is it safe?",
    "I'm 24 and my periods stopped for 3 months",
    "Just got my blood report: ferritin 12, B12 low. What foods help?",
    "Tried yoga and walking, feeling a bit better today",
    "Thank you all, this community is so kind",
    "Anyone from Pune? Looking for a good gynecologist recommendation",
    "Does cinnamon really help with sugar levels?",
    "I get anxious before every exam and my heart races",
    "My mother has diabetes and I'm worried about my own risk",
    "If you have PCOS, did you notice more acne?",
    "Do you have thyroid? How are you managing?",
    "I stopped taking my pill and now my cycle is all over the place",
    "Sleep has been terrible, 4 hours a night for a week",
    "Has anyone tried a 10 minute breathing exercise before bed?",
    "My sister said to take it easy this week and rest",
    "Is 1500 mg of calcium too much? Asking for my mom",
    "I'm so tired of being tired",
    "What do you all eat for breakfast? I'm bored of poha",
    "Period cramps are killing me today",
    "This heat is killing me and my skin is breaking out",
    "I could kill for a good night's sleep",
    "Hair fall after delivery, is it normal? 6 months postpartum",
    "Slept 7 hours, drank 2 litres of water, walked 8000 steps",
    "BP was 120/80 and pulse 72 today",
    "Started a new job and I feel overwhelmed. How do you cope?",
    "I hate how bloated I feel every evening",
    "Bloating after dal chawal? Anyone else?",
    "Skin has been so dry this winter, any moisturiser suggestions?",
    "Stress se pimples aa gaye hain, koi solution?",
    "Aap sab ka bahut shukriya, aaj thoda better feel ho raha hai",
    "Missing my family, living alone in a new city",
    "I need to assess my class schedule and the passage of time",
    "Peacock feathers and a cocktail at the scunthorpe cafe",
    "Anal fissure pain after dal, piles maybe? Any home tips",
    "Took my thyroid tablet at 7am and felt nauseous",
    "I take 5 mg folic acid daily as prescribed",
    "Is it ok to take paracetamol 500 mg for cramps?",
    "Pregnancy test came back positive, I'm scared and excited",
    "I feel hopeless some days and I don't know who to tell",
    "Instagram makes me feel worse about my body",
    "Anyone tried a 3 day juice fast? Worried it is too much",
    "Mere bal jhad rahe hain, kya iron ki kami ho sakti hai?",
    "Period late by 10 days, test negative, bahut tension hai",
    "Tulsi tea helps my cough, drink it warm",
]


@pytest.mark.parametrize("text,reason", REMOVE)
def test_bad_examples_are_removed_with_a_reason(text, reason):
    d = cm.moderate(text)
    assert (d.action, d.reason) == (cm.REMOVE, reason), (text, d)


@pytest.mark.parametrize("text,reason", HOLD)
def test_unsure_examples_are_held_not_removed(text, reason):
    d = cm.moderate(text)
    assert (d.action, d.reason) == (cm.HOLD, reason), (text, d)


@pytest.mark.parametrize("text", GOOD)
def test_good_examples_pass(text):
    d = cm.moderate(text)
    assert d.action == cm.ALLOW, (text, d)


def test_the_example_sets_are_big_enough():
    assert len(REMOVE) + len(HOLD) >= 60
    assert len(GOOD) >= 60


def test_contact_details_are_stripped_and_the_post_still_passes():
    d = cm.moderate("Call me on +91 98765 43210 or mail riya.k@example.com, my insta: riya_k99 or see https://example.com/me, feeling low")
    assert d.action == cm.ALLOW
    assert "98765" not in d.text and "example.com" not in d.text and "riya_k99" not in d.text
    assert d.text.count("[removed]") >= 4 and d.notes == ("contact_removed",)


def test_numbers_that_are_not_phone_numbers_are_left_alone():
    d = cm.moderate("Weight 62.5 kg, BP 118/76, 8000 steps on 2026-10-16 and 1,200 kcal")
    assert d.action == cm.ALLOW and d.text.startswith("Weight 62.5 kg") and "[removed]" not in d.text


def test_crisis_wording_about_oneself_is_never_removed_even_with_strong_language():
    d = cm.moderate("I fucking want to die, nobody would notice", crisis=True)
    assert d.action == cm.ALLOW


def test_crisis_does_not_excuse_a_threat_at_someone_else():
    assert cm.moderate("you should kill yourself", crisis=True).action == cm.REMOVE


def test_a_crisis_post_still_has_contact_details_removed():
    d = cm.moderate("I want to end it all, call me 9876543210", crisis=True)
    assert d.action == cm.ALLOW and "9876543210" not in d.text


def test_a_missing_word_list_holds_everything(monkeypatch):
    monkeypatch.setattr(cm, "_LISTS", cm._Lists.__new__(cm._Lists))
    cm._LISTS.ready = False
    assert cm.moderate("hello there").action == cm.HOLD


def test_a_rule_that_breaks_holds_the_text(monkeypatch):
    def boom(*_a, **_k):
        raise RuntimeError("x")
    monkeypatch.setattr(cm, "_moderate", boom)
    assert cm.moderate("fine text").action == cm.HOLD


def test_every_reason_has_plain_text_without_authority_names():
    banned = ("NHS", "WHO ", "CDC", "guideline", "according to", "studies show")
    for code, text in cm.REASON_TEXT.items():
        assert text and not any(b.lower() in text.lower() for b in banned), code
        assert "—" not in text   # no em-dash in visible text


def test_safety_signal_finds_crisis_and_urgent_and_stays_quiet_for_loneliness():
    assert cm.safety_signal("I want to kill myself").crisis
    assert cm.safety_signal("I have chest pain right now") is not None
    assert cm.safety_signal("I am so lonely, any advice?") is None


@pytest.mark.parametrize("text,reason", [
    ("k.i.l.l yourself", "threat"), ("k i l l yourself", "threat"), ("kill yourself", "threat"),
    ("T@ke 5OO mg of dolo 650 twice daily", "dose_advice"), ("take 5OO mg paracetamol every 4 hours", "dose_advice"),
])
def test_disguised_text_is_read_through(text, reason):
    d = cm.moderate(text)
    assert (d.action, d.reason) == (cm.REMOVE, reason)


@pytest.mark.parametrize("text", ["Slept 7 hours, woke at 5 am, felt ok", "I take my thyroid tablet at 6 am as my doctor said", "My a1c was 5.4 last month"])
def test_decoding_does_not_flag_ordinary_numbers(text):
    assert cm.moderate(text).action == cm.ALLOW
