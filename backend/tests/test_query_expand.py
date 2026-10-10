import pytest

from query_expand import MAX_ADDED, expand, lexical, terms


@pytest.mark.parametrize("query,added", [
    ("mujhe bukhar hai", "fever"), ("BP high rehta hai", "blood pressure"), ("my sugar badh gayi", "blood glucose"),
    ("pet dard", "abdominal pain"), ("kabz ho raha hai", "constipation"), ("loose motion since morning", "diarrhoea"),
    ("meri periods late hain", "menstrual irregularity"), ("saans phoolna", "breathlessness"),
    ("जोड़ों का दर्द", "joint pain"), ("बुखार है", "fever"), ("piles ka ilaaj", "haemorrhoids"),
    ("safed paani", "vaginal discharge"), ("loo lagna", "heat stroke"), ("khujli", "itching"),
    ("gas problem after meals", "bloating"), ("sugar level high hai", "blood glucose"),
])
def test_lay_terms_gain_english_words(query, added):
    assert expand(query).startswith(query) and added in expand(query)


def test_unrelated_and_partial_words_unchanged():
    for q in ["", "  ", "ferritin blood test", "knee brace sizing", "motion sickness", "bpm resting", "sugarcane juice"]:
        assert expand(q) == q and lexical(q) == q


@pytest.mark.parametrize("q", ["sugar free biscuits", "how much sugar in mango", "added sugar in tea", "gas stove repair", "gas cylinder price",
                               "sugar", "gas", "is brown sugar healthy"])
def test_ambiguous_everyday_words_do_not_expand_in_food_or_household_phrases(q):
    assert terms(q) == [] and expand(q) == q


def test_no_condition_names_are_invented():
    # A symptom or a test name never becomes a diagnosis word; only a phrase that itself names the condition does.
    for q in ["my sugar is high", "sugar level high hai", "jodon ka dard", "chakkar aa rahe hain"]:
        out = expand(q).lower()
        assert "diabetes" not in out and "arthritis" not in out and "anxiety" not in out
    assert "diabetes" in expand("sugar ki bimari ke lakshan") and "diabetes" in expand("madhumeh")
    assert "anxiety" in expand("ghabrahat hoti hai") and "palpitations" in expand("ghabrahat hoti hai")  # ambiguous: both readings


def test_keyword_search_gets_alternatives_not_extra_requirements():
    assert lexical("mujhe bukhar hai") == "mujhe bukhar hai or fever"
    assert lexical("gas problem") == "gas problem or flatulence or bloating or indigestion"
    assert lexical("loo lagna") == "loo lagna or heat stroke or heat exhaustion"   # phrases stay together


def test_never_adds_a_word_the_user_wrote_and_is_capped_and_deterministic():
    assert expand("fever bukhar") == "fever bukhar"
    q = "bukhar khansi zukam chakkar ulti kamzori thakan peeliya khujli daad pathri"
    assert len(expand(q).split()) - len(q.split()) <= MAX_ADDED and expand(q) == expand(q)
    assert sum(len(a) for a in terms(q)) <= MAX_ADDED


@pytest.mark.parametrize("query,added", [
    ("pet mein jalan ho rahi hai khane ke baad", "heartburn"), ("baal bahut jhad rahe hain", "hair loss"), ("paon mein sujan hai", "swelling"),
    ("gale mein kharash aur dard", "sore throat"), ("motapa kaise kam karein", "obesity"), ("very thirsty and passing urine a lot, tired", "excessive thirst"),
    ("period pain so bad I miss work", "dysmenorrhoea"),
])
def test_more_everyday_phrases_gain_english_words(query, added):
    assert added in lexical(query)


@pytest.mark.parametrize("query,added", [
    ("bellyache since morning", "abdominal pain"), ("the runs and cramps", "diarrhea"), ("what is pcos", "polycystic ovary syndrome"),
    ("afib symptoms", "atrial fibrillation"), ("backache after sitting", "back pain"),
])
def test_also_called_names_from_the_lay_terms_sheet_become_or_alternatives(query, added):
    out = lexical(query)
    assert out.startswith(query) and f" or {added}" in out


def test_synonyms_never_exceed_two_additions_or_repeat_a_word_already_asked():
    assert terms("what is pcos polycystic ovary syndrome") == []                      # already said in full
    assert len(terms("bellyache backache afib pimples zits")) <= 3 + 2                 # manual rules plus at most two synonym additions
