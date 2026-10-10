"""Deterministic lay / Hinglish / Hindi query expansion for evidence retrieval.

terms("mujhe bukhar hai") -> [["fever"]]; expand() -> "mujhe bukhar hai fever" (used for the meaning/embedding search);
lexical() -> "mujhe bukhar hai or fever" (used for the keyword search: the added words are extra ALTERNATIVES, they never
make the keyword match stricter). Pure and side-effect free.

Safety: it only appends the English medical word for a term the user actually wrote. It never adds a diagnosis. Ambiguous
everyday words (sugar, gas) expand only when the sentence also carries a health cue ("my sugar is high", "gas problem") and
not in food/household phrases ("sugar free", "sugar in mango", "gas stove"). Matching is case-insensitive on whole words
(ASCII and Devanagari). At most MAX_ADDED words are appended.
"""
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
    return out


def expand(query: str) -> str:
    """The query plus the English words (for the embedding / meaning search); unchanged when nothing matches."""
    added = [w for alt in terms(query) for w in alt]
    return f"{query.strip()} {' '.join(added)}" if added else query


def lexical(query: str) -> str:
    """The query plus the English alternatives joined with 'or' (for the keyword search); unchanged when nothing matches."""
    alts = terms(query)
    return query.strip() + "".join(f" or {' '.join(a)}" for a in alts) if alts else query
