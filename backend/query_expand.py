"""Deterministic lay / Hinglish / Hindi query expansion for evidence retrieval.

terms("mujhe bukhar hai") -> [["fever"]]; expand() -> "mujhe bukhar hai fever" (used for the meaning/embedding search);
lexical() -> "mujhe bukhar hai or fever" (used for the keyword search: the added words are extra ALTERNATIVES, they never
make the keyword match stricter). Pure and side-effect free.

Safety: it only appends the English medical word for a term the user actually wrote. It never adds a diagnosis. Ambiguous
everyday words (sugar, gas) expand only when the sentence also carries a health cue ("my sugar is high", "gas problem") and
not in food/household phrases ("sugar free", "sugar in mango", "gas stove"). Matching is case-insensitive on whole words
(ASCII and Devanagari). At most MAX_ADDED words are appended.
"""
import json
import os
import re

MAX_ADDED = 8

# key spellings (lowercase) -> English alternatives separated by '|'; words inside one alternative stay together (AND)
_ENTRIES: dict[tuple[str, ...], str] = {
    ("sugar", "shugar"): "blood glucose",
    ("bp", "b.p"): "blood pressure",
    ("gas", "gas problem"): "flatulence|bloating|indigestion",
    ("acidity", "acidity problem"): "acid reflux|heartburn",
    ("motions", "loose motion", "loose motions", "potty"): "diarrhoea|stool",
    ("kabz", "kabj"): "constipation",
    ("bukhar", "bukhaar", "बुखार"): "fever",
    ("sar dard", "sir dard", "sardard", "sirdard", "सिर दर्द", "सिरदर्द"): "headache",
    ("pet dard", "pet me dard", "pet mein dard", "पेट दर्द", "पेट में दर्द"): "abdominal pain|stomach ache",
    ("ulti", "ulti aana", "उल्टी"): "vomiting|nausea",
    ("khansi", "khasi", "खांसी", "खाँसी"): "cough",
    ("zukam", "zukaam", "sardi", "जुकाम", "सर्दी"): "common cold",
    ("chakkar", "chakkar aana", "चक्कर"): "dizziness",
    ("ghabrahat", "ghabrahat hona", "घबराहट"): "anxiety|palpitations|nervousness",   # ambiguous word: fetch both readings
    ("sugar ki bimari", "sugar ki beemari", "shugar ki bimari", "madhumeh", "मधुमेह", "शुगर की बीमारी"): "diabetes",   # names the condition itself
    ("kamzori", "kamjori", "कमजोरी", "कमज़ोरी"): "weakness|fatigue",
    ("thakan", "thakaan", "थकान"): "fatigue|tiredness",
    ("peeliya", "piliya", "पीलिया"): "jaundice",
    ("khoon ki kami", "khoon ki kami hai", "खून की कमी"): "anaemia|iron deficiency",
    ("hb", "haemoglobin low"): "haemoglobin|anaemia",
    ("thyroid",): "thyroid gland|TSH",
    ("piles", "bawasir", "bavasir", "बवासीर"): "haemorrhoids",
    ("safed paani", "safed pani", "सफेद पानी"): "vaginal discharge",
    ("periods late", "period late", "periods delay", "periods delayed", "late periods"): "menstrual irregularity|delayed period",
    ("neend nahi aati", "neend nahi", "neend na aana", "नींद नहीं आती"): "insomnia|sleep",
    ("dhadkan", "dil ki dhadkan", "धड़कन"): "palpitations|heartbeat",
    ("saans phoolna", "saans phulna", "सांस फूलना"): "breathlessness|shortness of breath",
    ("jodon ka dard", "jodo ka dard", "jodon mein dard", "जोड़ों का दर्द"): "joint pain",
    ("pathri", "पथरी"): "kidney stones",
    ("loo lagna", "loo lag gayi", "लू लगना"): "heat stroke|heat exhaustion",
    ("daad", "दाद"): "ringworm|fungal skin infection",
    ("khujli", "khujlee", "खुजली"): "itching",
    ("cholesterol",): "lipid profile",
    ("dahi",): "curd|yoghurt",
    ("chhole", "chole"): "chickpea",
    ("tb",): "tuberculosis",
    ("uti",): "urinary tract infection",
    # more everyday Hindi / Hinglish
    ("pet mein jalan", "pet me jalan", "seene mein jalan", "seene me jalan", "पेट में जलन", "सीने में जलन"): "heartburn|acid reflux|indigestion",
    ("dast", "dast ho rahe", "dast lag", "दस्त"): "diarrhoea",
    ("baal jhad", "baal bahut jhad", "baal jhad rahe", "baal jhadna", "baal girna", "baal gir", "बाल झड़", "बाल झड़ना"): "hair loss",
    ("sujan", "सूजन"): "swelling",
    ("gale mein dard", "gale me dard", "gale mein kharash", "gale me kharash", "gala kharab", "गले में दर्द", "गले में खराश"): "sore throat",
    ("chaale", "chhale", "mooh mein chaale", "मुंह में छाले"): "mouth ulcers",
    ("motapa", "mota hona", "मोटापा"): "obesity|weight loss",
    ("peshab mein jalan", "peshab me jalan", "पेशाब में जलन"): "burning urination|urinary tract infection",
    ("baar baar peshab", "bar bar peshab", "बार बार पेशाब"): "frequent urination",
    ("pyaas", "bahut pyaas", "प्यास"): "excessive thirst",
    ("kamar dard", "kamar mein dard", "kamar me dard", "कमर दर्द"): "back pain",
    ("ghutne mein dard", "ghutno ka dard", "ghutne ka dard", "घुटनों में दर्द"): "knee pain",
    ("aankh lal", "aankhen lal", "आंख लाल"): "red eye|conjunctivitis",
    ("kaan dard", "kaan mein dard", "kaan me dard", "कान दर्द"): "earache|ear infection",
    ("daant dard", "daant mein dard", "daant me dard", "दांत दर्द"): "toothache",
    ("pet fulna", "pet phoolna", "पेट फूलना"): "bloating|flatulence",
    ("tanav", "तनाव"): "stress|anxiety",
    ("udaasi", "udaas", "उदासी"): "low mood|depression",
    ("bhookh nahi", "bhook nahi", "भूख नहीं"): "loss of appetite",
    ("vajan badh", "vajan badhna", "वजन बढ़"): "weight gain",
    ("vajan kam", "वजन कम"): "weight loss",
    ("periods mein dard", "period mein dard", "period dard", "painful periods", "period pain"): "period pain|menstrual cramps|dysmenorrhoea",
    # plain-English symptom phrases
    ("thirsty", "very thirsty", "always thirsty"): "excessive thirst",
    ("passing urine a lot", "urinating a lot", "peeing a lot", "pee a lot", "peeing more"): "frequent urination",
    ("hair fall", "hairfall"): "hair loss",
    ("swollen feet", "swollen ankles"): "swelling ankles",
    ("bloated",): "bloating",
    ("constipated",): "constipation",
    ("breathless",): "breathlessness|shortness of breath",
}

# words that mean something else without a health cue
_NEEDS_CUE = {"sugar", "shugar", "gas"}
_CUE = re.compile(r"(?<![\w])(my|mera|meri|mere|mujhe|mujhko|high|low|level|levels|test|report|check|normal|control|"
                  r"problem|trouble|pain|dard|hai|ho|hota|hoti|badh|kam|fasting|random|bloating|acid|stomach|pet)(?![\w])")
_NOT_LAY = re.compile(r"sugar[- ]?free|sugar ?cane|added sugar|brown sugar|white sugar|sugar (?:in|intake|content|cravings?|cube|syrup)|"
                      r"gas (?:stove|cylinder|price|prices|bill|station|burner|leak|connection|subsidy)")

_RULES: list[tuple[re.Pattern[str], str, list[list[str]]]] = []
for _keys, _terms in _ENTRIES.items():
    _alts = [a.split() for a in _terms.split("|")]
    for _key in _keys:
        # Whole-word match; the lookarounds (not \b) keep Devanagari vowel signs inside a word.
        _RULES.append((re.compile(r"(?<![\wऀ-ॿ])" + re.escape(_key) + r"(?![\wऀ-ॿ])"), _key, _alts))


# English "also called" names from the MedlinePlus lay-terms sheet: synonym -> the topic's usual name. Built by build_lay_synonyms.py
# (clear one-to-one mappings only). A missing file just means no synonym help.
MAX_SYN_WORDS = 6
_SYN_SKIP = {"drinking", "nursing", "medications", "feces"}   # everyday words where adding the usual name would only add noise
try:
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "lay_synonyms.json"), encoding="utf-8") as _f:
        _SYN: dict[str, list[str]] = {
            k: [w for w in re.sub(r"[^\w\s\-]", " ", v).split() if w not in ("or", "and")]
            for k, v in json.load(_f).items() if k not in _SYN_SKIP
        }
except (OSError, ValueError):
    _SYN = {}
_WORD = re.compile(r"[\wऀ-ॿ][\wऀ-ॿ'\-]*")


def _synonym_terms(text: str, have: set[str], budget: int) -> list[list[str]]:
    """Longest-match scan of the query for 'also called' names (1 to 4 words); at most two additions, MAX_SYN_WORDS words."""
    words = _WORD.findall(text)
    out: list[list[str]] = []
    i, spent = 0, 0
    while i < len(words) and len(out) < 2:
        for n in (4, 3, 2, 1):
            alt = _SYN.get(" ".join(words[i:i + n])) if i + n <= len(words) else None
            if alt:
                if not all(w in have for w in alt) and spent + len(alt) <= min(MAX_SYN_WORDS, budget) and alt not in out:
                    out.append(alt)
                    spent += len(alt)
                i += n
                break
        else:
            i += 1
    return out


def terms(query: str) -> list[list[str]]:
    """English alternatives (each a list of words) for the lay terms in the query; capped at MAX_ADDED words in total."""
    if not query or not query.strip():
        return []
    text = " ".join(query.lower().split())
    have = set(re.findall(r"[\wऀ-ॿ]+", text))
    out: list[list[str]] = []
    total = 0
    for pattern, key, alts in _RULES:
        if not pattern.search(text):
            continue
        if key in _NEEDS_CUE and (not _CUE.search(text) or _NOT_LAY.search(text)):
            continue
        for alt in alts:
            if all(w.lower() in have for w in alt) or alt in out or total + len(alt) > MAX_ADDED:
                continue
            out.append(alt)
            total += len(alt)
    if _SYN and total < MAX_ADDED:
        out += _synonym_terms(text, have, MAX_ADDED - total)
    return out


def expand(query: str) -> str:
    """The query plus the English words (for the embedding / meaning search); unchanged when nothing matches."""
    added = [w for alt in terms(query) for w in alt]
    return f"{query.strip()} {' '.join(added)}" if added else query


def lexical(query: str) -> str:
    """The query plus the English alternatives joined with 'or' (for the keyword search); unchanged when nothing matches."""
    alts = terms(query)
    return query.strip() + "".join(f" or {' '.join(a)}" for a in alts) if alts else query
