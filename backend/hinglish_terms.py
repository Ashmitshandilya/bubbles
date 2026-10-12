"""Hinglish (romanized Hindi) and Devanagari vocabulary for Bubbles' deterministic health semantics.

Why: Bubbles is India-first, and the RED safety gate must recognise an emergency however it is typed:
"I can't breathe", "saans nahi aa rahi" or "साँस नहीं आ रही". Devanagari is first transliterated to the
romanized spelling Hinglish users type (:func:`transliterate`, called from ``health_semantics.normalize``), so the
ONE vocabulary below covers both scripts.

This file is data plus a transliterator; the decisions stay in ``health_semantics`` / ``safety_engine``.
Patterns follow the lexicon conventions there: a space matches any run of whitespace/hyphens, and every pattern
is literals with bounded repetition (linear time).

REVIEW: chosen by an engineer from common usage, not by a clinician or a native-speaker panel. The list, and the
choices that are genuinely uncertain, are in docs/clinical/HINGLISH_SAFETY_TERMS_REVIEW.md.
"""
from __future__ import annotations

import re

# --------------------------------------------------------------------------
# Devanagari -> Hinglish spelling
# --------------------------------------------------------------------------

_CONS = {
    "क": "k", "ख": "kh", "ग": "g", "घ": "gh", "ङ": "n", "च": "ch", "छ": "chh", "ज": "j", "झ": "jh", "ञ": "n",
    "ट": "t", "ठ": "th", "ड": "d", "ढ": "dh", "ण": "n", "त": "t", "थ": "th", "द": "d", "ध": "dh", "न": "n",
    "प": "p", "फ": "f", "ब": "b", "भ": "bh", "म": "m", "य": "y", "र": "r", "ल": "l", "व": "v", "श": "sh",
    "ष": "sh", "स": "s", "ह": "h", "ळ": "l",
    # precomposed nukta letters
    "क़": "q", "ख़": "kh", "ग़": "g", "ज़": "z", "ड़": "d", "ढ़": "dh", "फ़": "f", "य़": "y",
}
_NUKTA = {"क": "q", "ज": "z", "फ": "f"}          # consonant + combining nukta
_MATRA = {"ा": "a", "ि": "i", "ी": "i", "ु": "u", "ू": "u", "ृ": "ri", "ॄ": "ri",
          "ॅ": "e", "ॆ": "e", "े": "e", "ै": "ai", "ॉ": "o", "ॊ": "o", "ो": "o", "ौ": "au"}
_VOWEL = {"अ": "a", "आ": "a", "इ": "i", "ई": "i", "उ": "u", "ऊ": "u", "ऋ": "ri",
          "ऍ": "e", "ऎ": "e", "ए": "e", "ऐ": "ai", "ऑ": "o", "ऒ": "o", "ओ": "o", "औ": "au"}
#: words whose rule-based spelling is not the one people type (looked up after chandrabindu -> anusvara)
_OVERRIDE = {
    "में": "mein", "मैं": "main", "है": "hai", "हैं": "hain", "नहीं": "nahi", "नही": "nahi", "हूं": "hoon",
    "आ": "aa", "आज": "aaj", "मां": "maa", "रात": "raat", "साल": "saal", "बार": "baar", "सांस": "saans",
    "स्ट्रोक": "stroke", "पेन": "pain", "ब्लीडिंग": "bleeding",
}
_DEVA_RX = re.compile(r"[ऀ-ॿ]")
_WORD_RX = re.compile(r"[ऀ-ॣ॰-ॿ]+")   # a Devanagari word (danda and digits excluded)
_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")


def _word(w: str) -> str:
    w = w.replace("ँ", "ं").replace("ऀ", "ं")      # chandrabindu -> anusvara
    if w in _OVERRIDE:
        return _OVERRIDE[w]
    units: list[list] = []      # [consonant, vowel (None = inherent schwa), nasal]
    for i, ch in enumerate(w):
        if ch in _CONS:
            units.append([_CONS[ch], None, ""])
        elif ch == "़":                                            # nukta
            if units and w[i - 1] in _NUKTA:
                units[-1][0] = _NUKTA[w[i - 1]]
        elif ch in _MATRA and units and units[-1][0] and units[-1][1] is None:
            units[-1][1] = _MATRA[ch]
        elif ch == "्" and units and units[-1][1] is None:         # virama
            units[-1][1] = ""
        elif ch in _VOWEL:
            units.append(["", _VOWEL[ch], ""])
        elif ch in "ंः" and units:                            # anusvara / visarga
            units[-1][2] += "n" if ch == "ं" else "h"
    # Hindi schwa deletion: the word-final inherent 'a', then V C _ C V medially, left to right ("तकलीफ" -> taklif)
    if len(units) > 1 and units[-1][0] and units[-1][1] is None and not units[-1][2]:
        units[-1][1] = ""
    for k in range(1, len(units) - 1):
        u, prev, nxt = units[k], units[k - 1], units[k + 1]
        if u[0] and u[1] is None and not u[2] and prev[1] != "" and nxt[0] and nxt[1] != "":
            u[1] = ""
    return "".join(c + ("a" if v is None else v) + n for c, v, n in units)


def transliterate(text: str) -> str:
    """Devanagari words -> the romanized spelling Hinglish users type ("सीने में दर्द" -> "sine mein dard"). Other text is untouched."""
    if not _DEVA_RX.search(text):
        return text
    text = re.sub(r"[।॥]\s*", ". ", text).translate(_DIGITS)   # danda (।) ends a sentence
    return _WORD_RX.sub(lambda m: _word(m.group(0)), text)


# --------------------------------------------------------------------------
# Red-flag lexicon: (concept, tier, label, patterns). Labels match the English entries so the safety
# copy and reasons are identical whatever language the user typed in.
# --------------------------------------------------------------------------

NEG = r"(?:nahi|nahin|nahee|nahii|nhi|nai)"
#: one free word that is not a negator (a symptom phrase must never swallow "nahi")
_W = r"(?!(?:nahi|nahin|nahee|nahii|nhi|nai|na|mat|bilkul)\b)[a-z]+ "
_AUX = r"(?:rahi|raha|rahe|rhi|rha|rhe)"
_WANT = r"(?:chaa?ht[aei]|chahata|chahati|chaa?hu|chaa?hun|chaa?hoon|chahunga|chahungi)"
_MOD = (r"(?:(?:bahut|bohot|bahot|bhut|bht|bohat|kaafi|kafi|thoda|thodi|halka|halki|tez|tej|zor ka|zordar|zabardast|bhayankar|"
        r"bhayanak|bhaari|bhari|teekha|tikha|ajeeb|ajib|achanak|ekdum|ek dum|lagatar|lagataar|zyada|jyada|sa|si|se|ka|ki|ek|koi|"
        r"kuch|bilkul|hi) ){0,4}")
_CHEST = r"(?:s(?:ee|i)n[aeiy]|seenay|seeney|chh?aa?t(?:i|ee)|chest)"
_LOC = r"(?:mein|me|mai|main|men|mei|m|pe|par|pr|ke (?:beech|bich|andar|upar|left side|baayi taraf|bayi taraf) (?:mein|me|mai|pe))"
_PAIN = (r"(?:dard|dardh|drd|dukh\w*|peeda|pida|dabaa?v|dabaw|dabao|jakdan|jakadan|jakad\w*|jakdahat|bhaa?ri(?: )?pan|bojh|bojha|"
         r"jalan|jalaan|kasaa?v|khinchaa?v|khichaa?v|chubhan|takl(?:ee|i)f|tklif|dikk?at|pain|pressure|tightness|heaviness|discomfort|probl[ae]m)")
_BREATH = r"(?:saa?ns|saa?nse|saa?nsein|saas|shvaa?s|shwaa?s|swaa?s)"
_THIK = r"(?:(?:theek|thik|sahi|achhe|acche) se )?"
_TROUBLE = r"(?:takl(?:ee|i)f|tklif|dikk?at|probl[ae]m|pareshani|preshani|mushkil)"
_BLOOD = r"(?:kh(?:oo|u|uu)n|bleeding|blood)"
_MUCH = r"(?:bahut|bohot|bahot|bhut|bht|zyada|jyada|kaafi|kafi|lagatar|lagataar|itna|itni|kitna|kitni|bhayankar|tez|tej)"
_FACE = r"(?:chehr[ae]|chehera|munh|muh|moonh|mooh)"
_LIMB = r"(?:haath|hath|baazu|bazu|bazoo|baanh|pair|paer|pao|paon|taang|tang)"
_SIDE = (r"(?:left|right|baa?yan|baa?ya|baa?yen|baa?ye|baen|baa?yi|daa?yan|daa?ya|daa?yen|daa?ye|daen|daa?yi|ulta|ulte|seedha|seedhe|sidha)")
_BECAME = r"(?:ho|pad|par) (?:gaya|gayi|gaye|gya|gyi|gye|gai|gae|raha|rahi|rahe|rha|rhi|jata|jati|ja raha|ja rahi|chuka|chuki)"

LEXICON: tuple[tuple[str, str | None, str, tuple[str, ...]], ...] = (
    ("chest_pain", "red", "chest pain or pressure", (
        _CHEST + " " + _LOC + " " + _MOD + _PAIN,                                   # seene mein bahut tez dard
        _CHEST + " (?:ka|ki|ke) " + _MOD + _PAIN,                                   # seene ka dard
        _CHEST + r" (?:dukh|jakad|jakd|bhaa?ri (?:lag|ho)|kas (?:raha|rahi|gaya|gayi))\w*",   # seena dukh raha hai
        r"(?:dard|dardh|dabaa?v|jakdan|bhaa?ri(?: )?pan|jalan) (?:ho (?:raha|rahi) (?:hai )?|hai )?(?:mere |meri )?" + _CHEST
        + " (?:mein|me|mai|main|men|pe|par)",                                       # dard ho raha hai seene mein
        _CHEST + " (?:pe|par|pr) (?:" + _W + r"){0,3}(?:baith\w*|rakh\w*|pathar|patthar|bojh)",   # seene pe koi baitha hai
        "dil (?:mein|me|mai|ke paas|ke aas paas|ki jagah) " + _MOD + r"(?:dard|dabaa?v|jakdan|bhaa?ri(?: )?pan|pain)",
    )),
    ("shortness_of_breath", "red", "breathing difficulty", (
        _BREATH + " (?:lene|lena|lete|leney|lenay) (?:mein|me|mai|main|men|m) " + _MOD + "(?:" + _TROUBLE + "|dard|tension)",
        _BREATH + " (?:ki|ka|ke|mein|me|mai) " + _MOD + _TROUBLE,
        _BREATH + " " + _THIK + NEG + " (?:aa|a) (?:pa |paa )?" + _AUX,                     # saans nahi aa rahi
        _BREATH + " " + _THIK + NEG + r" (?:aa?ti|aa?ta|aa?y[ai]|aa?i)",
        _BREATH + " " + _THIK + "(?:" + NEG + " (?:le|lee|li) |(?:le|lee) " + NEG + " )(?:pa|paa) (?:" + _AUX
        + "|sakta|sakti|sakte|pata|pati|pate)",                                       # saans nahi le pa raha
        _BREATH + " (?:phool|phul|fool|ful)(?:na|ne|ti|ta|te|i|a|e)?(?: " + _AUX + "| lagi| laga| gayi| gaya| gai| jati| jata)?",
        _BREATH + " (?:ruk|ruki|rukti|rukta|ukhad|ukhd|ukhar|atak|atk|atki|tham|band|bandh|ghut|ghutt|chadh|chad|chadhi|chadhti)"
        "(?: ho| ja)? (?:" + _AUX + "|jati|jata|jaati|jaata|gayi|gaya|gyi|gya|gai|si|sa|ne lagi|ne laga)",
        _BREATH + r" (?:ruk|atak|atk) (?:ruk|atak|atk) (?:ke|kar|kr)",                # saans ruk ruk ke aa rahi
        r"(?:dam|dum) ghutt?\w*|ghutan|ghutn\w*",                                     # dam ghut raha hai
        r"breathing (?:mein|me|mai) " + _MOD + "(?:" + _TROUBLE + "|issue)",
        "(?:hoth|honth|hont|hothon|honthon|ungliyan|ungliyon|naakhun|nakhun|nakhoon|lips?|nails?) (?:" + _W + ")?"
        "(?:neel[aeiy]|nile|neeley|baingani)",                                        # hoth neele pad gaye
    )),
    ("fainting", "red", "loss of consciousness", (
        r"be(?: )?hosh\w*",
        "hosh (?:kho|khona|khoya|kho diya|kho di|kho gaya|kho gayi|kho baitha|kho baithi|ud gaya|ud gaye|gum|" + NEG + " raha)",
        r"(?:chakkar|chakar) (?:aa|a|kha|khaa)\w* (?:ke|kar|kr|kar ke|karke) gir\w*",
        r"gash (?:aa|kha|khaa)\w*",
    )),
    ("seizure", "red", "seizure", (
        r"mirgi\w*|mirgee",
        r"daur[ae] (?:pad|aa|aaye|aaya|aate|aata)\w*",                                 # not "daure par" (= on tour)
        r"jhatke (?:aa|pad)\w*",
        "(?:fits?|fitt?) (?:aa (?:gaya|gayi|gai|raha|rahi|rahe|jata|jati|gya|gyi)|aata|aati|aate|aaya|aayi|pad (?:gaya|gayi|gai|raha|rahi|gya|gyi))",
    )),
    ("heavy_bleeding", "red", "heavy bleeding", (
        _MUCH + " (?:" + _MUCH + " )?(?:(?:sa|saara|sara|saari|sari) )?" + _BLOOD + r" (?:beh|bah|nikal|nikl|aa|a|ja|jaa|gir|ho)\w*",
        _BLOOD + " (?:" + _MUCH + r" ){1,2}(?:beh|bah|nikal|nikl|aa|a|ja|jaa|gir|ho)\w*",
        _BLOOD + " (?:ruk|ruka|rukta|band|bandh|tham|thama) (?:hi )?" + NEG + " (?:" + _AUX
        + "|ho raha|ho rahi|ho rha|ho rhi|hota|hoti|ho pa raha|ho pa rahi)",          # khoon ruk nahi raha
        "(?:har|ek) (?:ghante|ghanta) (?:(?:mein|me|main) )?(?:" + _W + r"){0,2}(?:pads?|padd) (?:badal|change|bhar|bheeg|bhig|geel|gil)\w*",
        "(?:bade|bade bade|badi|badi badi|bahut bade|bahut badi) (?:" + _W + ")?(?:thakke|thakka|thakkey|thakkay|clots?|gaanth|gaanthein|gutthe)",
    )),
    ("vomiting_blood", "urgent", "blood in vomit", (
        _BLOOD + r" (?:ki|wali|vali) (?:ulti|ultiyan|ultiyaan|ultee|vomit\w*)",
        "(?:ulti|ultiyan|ultee|vomit) (?:mein|me|mai|main) " + _BLOOD,
    )),
    ("suicidal_ideation", "red", "possible self-harm crisis language", (
        "khud(?: )?k?h?ushi|aa?tm(?: )?a?hatya",                                     # khudkushi, aatmahatya
        "mar(?:na|ne|jana|jaana| jana| jaana| jaun| jau| jaaun| jaoon| jaaon| jaau) (?:" + _W + ")?" + _WANT,   # marna chahta hoon
        "mar(?:ne|jaane|jane| jaane| jane) (?:ka|ki|ke|ko) (?:mann?|dil|khayal|khyal|khayaal|vichar|vichaar|soch|iccha|ichha|ichchha|irada|iraada)",
        "(?:jeene|jine|jeena|jina|jeenay) (?:ka|ki|ke) (?:koi )?(?:mann?|dil|iccha|ichha|ichchha|wajah|vajah|matlab|maksad|maqsad|mood) "
        "(?:hi )?(?:" + NEG + "|na|khatam|khatm)",                                    # jeene ka mann nahi karta
        "(?:koi )?(?:wajah|vajah) (?:hi )?" + NEG + " (?:jeene|jine) (?:ki|ka)",
        "(?:jeena|jina|zinda rehna|zinda rahna) (?:hi )?" + NEG + " (?:hai|" + _WANT + "|chahiye)",
        NEG + " (?:jeena|jina)",                                                      # mujhe nahi jeena
        "(?:jeena|jina) (?:hi )?" + NEG,                                              # ab jeena nahi
        NEG + " (?:jee|ji|jii) (?:sakta|sakti|sakte|paunga|paungi|paaunga|paaungi|pa raha|pa rahi)",   # ab aur nahi jee sakta
        "mar(?:na|ne|jana|jaana| jana| jaana) (?:hi )?hai",                           # mujhe marna hai
        "(?:main|mai|me) mar (?:jaunga|jaungi|jaaunga|jaaungi|jaoonga|jaoongi)",       # main mar jaunga
        "(?:khud|apne aap|apne) ko (?:khatam|khatm|khtm) kar (?:lunga|lungi|dunga|dungi|lu|lun|loon|du|dun|doon|lena|dena)",
        "(?:neend ki|saari|sari|bahut saari|bahut sari|dher saari|ek saath|ek sath) (?:" + _W + ")?(?:goliyan|goliya|goliyaan|golian|"
        "tablets?|pills?) (?:(?:ek saath|ek sath) )?kha (?:lunga|lungi|lu|lun|loon|li)",     # neend ki goliyan kha lunga
        "sab (?:kuch )?khatam kar (?:dunga|dungi)",
        "(?:zinda?gi|jinda?gi|jeevan|jivan) (?:" + _W + ")?(?:khatam|khatm|khtm|samapt) (?:kar|karna|karne|kr|krna|krne|kardu|kar du|kar dun|"
        "kar doon|kar lu|kar lun|kar loon|kar lena|kar dena|kar lunga|kar lungi|kar dunga|kar dungi)",
        "apni (?:jaan|jan) (?:le|lena|lene|lunga|lungi|loon|lu|lun|lelu|le lu|le lunga|le lungi)",   # not "jaan de dunga" (often a figure of speech)
        "(?:jaan|jan) (?:dena|de dena|de du|de dun) " + _WANT,
        "kaa?sh (?:(?:main|mai|me) )?(?:mar|mr) (?:jaun|jau|jaaun|jaata|jaati|jata|jati|gaya hota|gayi hoti)",
        "kaa?sh (?:(?:main|mai|me) )?(?:paida|peda|paeda) (?:hi )?(?:na|" + NEG + ") (?:hota|hoti|hua|hui)",
        "mere (?:bina|bagair|baghair|jaane ke baad|jane ke baad) (?:(?:sab|sabhi|sab log|sabka|ghar wale|gharwale|log) )?(?:" + _W
        + r"){0,2}(?:better|behtar|achha|accha|acche|achhe|khush|sukhi)\w*",
        "(?:khud|apne aap|apne) ko (?:maar|mar|khatam) (?:du|dun|doon|dunga|dungi|lu|lun|loon|lunga|lungi|dalu|dalun|daalu|daalun|dalunga|dena|lena|dalna|daalna)",
        "(?:zinda?gi|jinda?gi|jeevan) se haar (?:gaya|gayi|gya|gyi|chuka|chuki)",
        "sab (?:kuch )?khatam kar (?:dena|lena) " + _WANT,
    )),
    ("self_harm", "red", "possible self-harm crisis language", (
        "(?:khud|apne aap|apne|khud ke) ko (?:nuk?saa?n|nukasan|nuqsan|chot|hurt|harm|zakhmi|jakhmi|takl(?:ee|i)f|dard) "
        r"(?:pahunch|pohoch|pahuncha|pohcha|de|dena|dene|du|dun|kar|karna|karne|kr|krna|krne|karta|karti|karte)\w*",
        "(?:kalai|kalaai|nas|nass|nasen|nase|nasein|wrist) (?:" + _W + r")?(?:kaat|kaatna|kaatne|kaati|kaata|cut kar|cut kr|cut kiya)\w*",
        "(?:ek saath|ek sath|ek baar mein|ek bar me|dher saari|dher sari|bahut saari|bahut sari|saari ki saari|sari ki sari|puri strip|"
        "poori strip|pura patta|poora patta|pura pack|poora pack) (?:" + _W + ")?(?:(?:goliyan|goliya|goliyaan|golian|tablets?|pills?|"
        r"dawai|dawaiyan|dawaiyaan|dawa|davai|davaiyan) )?(?:kha|khaa|nigal)\w*",
    )),
    ("stroke_signs", "red", "possible stroke warning signs", (
        _FACE + " (?:" + _W + r"){0,3}(?:tedha|tedhi|tedhe|terha|terhi|tirchha|tircha)\w*",          # munh tedha ho gaya
        _FACE + " (?:(?:ka|ki|ke) )?(?:ek|aadha|adha|" + _SIDE + ") (?:(?:taraf|side|hissa|hisse) )?(?:(?:se|ka|ki) )?(?:" + _W
        + r"){0,2}(?:latak|latka|lataka|latki|jhuk|jhuka|gir|sunn|lakwa|lakva)\w*",   # chehra ek taraf latak gaya
        _FACE + " (?:" + _W + "){0,2}sunn? " + _BECAME,
        "(?:zubaan|zuban|jubaan|juban|zabaan|zaban|jeebh|jibh) (?:" + _W + r"){0,2}(?:ladkh|lad khad|ladkhar|atak|atk)\w*",   # zubaan ladkhada rahi
        "(?:bolne|bolte|baat karne) (?:mein|me|mai|main|men) (?:" + _W + r"){0,2}(?:ladkh|lad khad|atak|atk)\w*",
        "achanak (?:se )?(?:bolne|bolte|baat karne) (?:mein|me|mai|main|men) (?:" + _W + "){0,2}" + _TROUBLE,
        r"(?:awaa?z|aawaa?z|aavaz) (?:" + _W + r"){0,2}(?:ladkh|lad khad|atak)\w*",
        r"(?:theek se|thik se|saaf|saf) (?:bol|bola|bolna) " + NEG + r" (?:pa|paa|ja)\w*",
        "(?:ek (?:taraf|side|hissa|hisse)|aadh[ae]|adh[ae]) (?:(?:ka|ki|ke) )?(?:" + _W
        + r"){0,3}(?:sunn|kamzor|kamjor|kamzori|kamjori|bejaan|be jaan|lakwa|lakva)\w*",  # ek taraf ka haath pair sunn
        "(?:" + _SIDE + " )?" + _LIMB + "(?: (?:aur|or) " + _LIMB + ")?(?: (?:mein|me|mai|main))? (?:achanak (?:se )?)?"
        "(?:sunn?|kamzor|kamjor|bejaan|be jaan|lakwa|lakva) " + _BECAME,             # left haath sunn ho gaya
        "achanak (?:se )?(?:" + _SIDE + " )?" + _LIMB + "(?: (?:mein|me|mai|main))? (?:kamzori|kamjori|sunnpan|sunnapan)",
        _LIMB + " (?:" + _W + "){0,2}(?:hil|hila|hilaa) " + NEG + " (?:" + _AUX + "|pa|paa|pata|pati|sakta|sakti|pa raha|pa rahi|paa raha|paa rahi)",
        "(?:" + _LIMB + "|" + _FACE + ") (?:(?:mein|me|mai|main|ka|ki|ke) )?(?:koi )?(?:jaan|jan|ehsaas|ehsas|mehsoos|mehsus|feeling|sensation) "
        + NEG + "(?: (?:ho raha|ho rahi|aa raha|aa rahi|hai|ho rha|ho rhi|ho rahe))?",   # haath mein jaan nahi
        "lakwa|lakva|lakwaa|laqwa|faalij|falij",
        r"achanak (?:se )?(?:dikhna|dikhai|dikhayi|nazar aana) (?:dena )?(?:band|" + NEG + r")\w*",
    )),
    ("allergic_reaction", "red", "possible severe allergic reaction", (
        "(?:gala|gale|galaa|throat) (?:(?:mein|me|mai|main|ka|ki) )?(?:" + _W + ")?(?:band|bandh|sikud|sukud|sooj|suj|soojan|sujan|phool|"
        r"phul|ful|kas|jakad|jakd)\w* (?:ho|ja|gaya|gayi|gya|gyi|gai|gae|" + _AUX + "|hai|lag|hui|hua)",   # gala band ho raha hai
        "(?:chehr[ae]|chehera|hoth|honth|hont|hothon|honthon|jeebh|jibh|zubaan|zuban|zabaan|tongue|lips?|face) "
        "(?:(?:mein|me|mai|main|par|pe) )?(?:" + _W + r")?(?:sooj|suj|soojan|sujan)\w*",  # hoth sooj gaye
        "(?:soojan|sujan) (?:" + _W + ")?(?:chehre|hothon|honthon|hoth|honth|jeebh|jibh|gale|zubaan|zuban)",
        "(?:(?:bahut|bohot) )?(?:tez|tej|bhayankar|bahut zyada|bahut jyada|khatarnak) (?:allergy|reaction)",
    )),
    ("heart_attack", "red", "possible heart attack", (
        "(?:dil|hriday|hirday|hridaya|heart) (?:ka|ke) (?:daura|dora|dauraa|daure|attack|atak|ataik)",   # dil ka daura
        "(?:hart|haart|heart) (?:atak|ataik|attak|atek|atack)",
    )),
    ("headache", "red", "sudden severe headache", (
        "(?:zinda?gi|jinda?gi|life|jeevan) ka sabse (?:bura|tez|tej|zyada|jyada|bhayankar|khatarnak|kharab|bada) (?:sar|sir)(?: )?(?:dard|dardh)",
        "achanak (?:se )?(?:(?:bahut|bohot|ekdum|ek dum) )?(?:tez|tej|bhayankar|bhayanak|zordar|zabardast) (?:sar|sir)(?: )?(?:dard|dardh)",
        "(?:sar|sir) (?:mein|me|mai|main) achanak (?:se )?(?:(?:bahut|bohot|ekdum) )?(?:tez|tej|bhayankar|bhayanak|zordar) (?:dard|dardh)",
    )),
)

# --------------------------------------------------------------------------
# Meaning cues. Only consulted for sentences that look Hindi (GATE), so English text is never affected.
# Hindi is verb-final: "seene mein dard NAHI hai" = no chest pain, the negator comes AFTER the symptom.
# These are compiled as-is (no space -> [\s-]+ rewriting).
# --------------------------------------------------------------------------

GATE = (r"[ऀ-ॿ]|\b(?:hai|hain|hoon|hun|nahi|nahin|nhi|mujhe|mujhko|mera|meri|mere|raha|rahi|rahe|rha|rhi|hua|hui|tha|thi|"
        r"mein|aur|bhi|kya|ki|ke|agar|lekin|abhi|saans|seene|dard)\b")
#: negator right after the symptom, followed only by a copula, then a clause end ("dard nahi hai", "takleef nahi ho rahi").
#: "dard nahi ruk raha" (pain is NOT stopping) and "saans nahi aa rahi" (can't breathe) are never denials.
NEG_POST = (r"\s*(?:(?:bilkul|bilkool|ab|abhi|koi|zara bhi|zara sa bhi|bhi)\s+){0,2}" + NEG
            + r"(?:\s+(?:hai|hain|he|h|ho|raha|rahi|rahe|rha|rhi|hota|hoti|hote|hua|hui|hue|tha|thi|the|karta|karti|karte|lag|lagta|lagti|"
            r"laga|lagi|hu|hoon|hun|ab|abhi|bilkul|tak|mehsoos|feel)){0,4}"
            r"(?=\s*(?:[,.;:!?)\]]|$)|\s+(?:aur|or|lekin|magar|parantu|but|and|bas|sirf|ya|na)\b)")
#: "dard nahi THA lekin AB ho raha hai" (no pain before, but now there is): a past denial followed by "but now" denies nothing
BUT_NOW = r"\b(?:lekin|magar|par|but)\b.*\b(?:ab|abhi)\b"
PRE_NEG = r"\bbina\b"                                       # "bina dard ke" = without pain
HYPO = r"\b(?:agar|agr|yadi|maan lo|maan lijiye|maan lete hain|man lo|maanlo|manlo)\b"
_KIN = (r"papa|papaji|pitaji|pita ji|pita|daddy|dad|mummy|mumma|mummi|mammi|mamma|mom|maa|maaji|mata ji|mataji|mata|ammi|ammy|abbu|"
        r"abba|bhai|bhaiya|bhaiyya|bhayya|bhaisaab|behen|behan|bahan|didi|beta|beti|bete|bachcha|bachche|bacche|baccha|bachchi|bacchi|"
        r"bachi|bacha|pati|patni|biwi|bibi|wife|husband|dost|friend|nani|nana|naani|naana|dadi|dada|daadi|daada|chacha|chachi|chachu|"
        r"mama|mami|mamu|mausi|masi|mausa|bua|fufa|fufi|tau|tai|taiji|bhabhi|jiju|jija|sasur|saasu|padosi|padosan|uncle|aunty|aunti|"
        r"nanu|dadu|bhatija|bhatiji|bhanja|bhanji|devar|nanad|saala|saali|grandma|grandpa")
#: someone else as the experiencer ("papa ko seene mein dard hai"): the kin word with its case marker
OTHER = (r"\b(?:(?:" + _KIN + r")(?:\s+(?:ji|jee))?\s+(?:ko|ke|ki|ka|kaa|kii)|usko|unko|unhe|unhein|unhen|isko|inko|inhe|inhein|"
         r"kisi\s+ko|kisiko|logon\s+ko)\b")
#: first person (Hindi drops the pronoun, so first-person verb forms count too: "kya karun?" = what do I do?)
SELF = (r"\b(?:mujhe|mujhko|mujh|main|mai|maine|mera|meri|mere|hum|humein|hamein|humko|hamko|hamara|hamari|hamare|hoon|hun|karun|"
        r"karu|karoon|jaun|jaaun)\b")
#: "papa ko bataya ki seene mein dard hai" = I TOLD dad I have chest pain: never someone else's symptom
COMM = (r"\b(?:bata\w*|bola|bole|boli|bol|kaha|kehna|keh|kehte|kehti|puchh\w*|pooch\w*|bula\w*|call|phone|fone|dikha\w*|samjha\w*|"
        r"likh\w*|lejao|le\s+ja\w*)\b")
POSS = r"\b(?:mera|meri|mere)\s+(?:\w+\s+)?$"
WORSEN = r"\s+(?:aur\s+)?(?:badh|badhe|badhta|badhti|zyada\s+ho|jyada\s+ho|bigad|kam\s+(?:na|nahi)\s+ho|theek\s+(?:na|nahi)\s+ho)"
#: educational questions only ("kya seene mein dard heart attack ka lakshan hai?"); everything else stays a report
Q_START = r"^\W*(?:kya|kyaa|kyun|kyon|kyu|kaise|kab|kaun|kitna|kitni|kitne)\b"
Q_END = r"(?:\bkya|\?)\W*$"
GENERIC = (r"\b(?:hota|hoti|hote|ho\s+sakta|ho\s+sakti|ho\s+sakte|lakshan|laxan|sign|signs|symptom|symptoms|nishani|nishaani|sanket|"
           r"matlab|normal|khatarnak|khatra|kaaran|karan|wajah|vajah|ilaaj|ilaj|treatment|pehchan|pehchaan|pahchan)\b")
FAMILY = r"\b(?:khandaan|khaandaan|parivaar|parivar|pariwar|family|gharwalon|ghar\s+walon|ghar)\s+(?:mein|me|mai|main)\b"
HISTORY = r"\b(?:history|itihaas|itihas|khandaani|khandani|hereditary)\b"
#: list glue for a trailing negator ("seene mein dard aur saans ki takleef nahi hai")
GLUE = frozenset("aur ya na koi bhi ki ka ke".split())

# ---- time. Downgrades (history/resolved/recurring) only from the symptom's own clause; "now" anywhere keeps it current.
CLAUSE = r",|;|\b(?:aur|or|lekin|magar|parantu|kintu|phir|fir|kyunki|kyonki|kyuki|isliye|jabki|and|but|then)\b"
_NUM = r"(?:\d+|ek|do|teen|char|chaar|paanch|panch|kuch|kai|bahut)"
_BEFORE = r"(?:pehle|pahle|pehele)"
OLD = (r"\b(?:" + _NUM + r"\s+(?:mahine|mahino|mahinon|saal|saalon|sal|salon|varsh)\s+" + _BEFORE + r"|saalon\s+" + _BEFORE
       + r"|pichh?l[ae]y?\s+(?:saal|sal|year|mahine|month)|bachpan\s+(?:mein|me)|"
       r"jab\s+(?:main|mai)\s+(?:chhota|chhoti|chota|choti|bachcha|bachchi|bacha|bachi|bacchi|baccha)|(?:ki|ka|ke)\s+(?:history|itihaas|itihas))\b")
PAST = (r"\b(?:parson|pichh?l[ae]y?\s+(?:hafte|haftey|week|baar|bar)|" + _NUM + r"\s+(?:din|dino|dinon|hafte|hafton|week)\s+" + _BEFORE
        + r"|(?:pehle|pahle)\s+kabhi|kal(?!\s+raat)(?=(?:\s+\w+){0,8}\s+(?:tha|thi|the|hua|hui|hue)\b))\b")
RECURRING = (r"\b(?:kabhi\s+(?:kabhi|kabhaar|kabhar)|kabhi-kabhi|aksar|akser|roz|rozana|roj|har\s+(?:roz|din|raat|subah|shaam|baar|bar|hafte|mahine|waqt)|"
             r"jab\s+(?:bhi|jab)|baar\s+baar|bar\s+bar|(?:seedhi|seedhiyan|sidhi|sidhiyan|seedhiyon|sidhiyon)\s+chadh\w*|"
             r"(?:chadhte|chalte|daudte|bhaagte)\s+(?:waqt|samay|hue|time)|(?:chalne|daudne|chadhne|kasrat\s+karne|exercise\s+karne)\s+(?:par|pe|ke\s+baad|se))\b")
_RES_CORE = (r"th(?:ee|i)k\s+ho\s+(?:gaya|gayi|gaye|gya|gyi|gai|gae|chuka|chuki)|(?:band|bandh|khatam|khatm|khtm)\s+ho\s+(?:gaya|gayi|gya|gyi|gai|chuka|chuki)|"
             r"ruk\s+(?:gaya|gayi|gya|gyi|gai)|utar\s+(?:gaya|gayi|gya|gyi|gai)|ab\s+(?:th(?:ee|i)k|normal|better|achha|accha|acha|sahi)\s+(?:hai|hoon|hun|hu|hain|lag|ho)|"
             r"ab\s+" + NEG + r"\s+(?:hai|ho\s+raha|ho\s+rahi|raha|rahi)")
#: right after the symptom ("dard chala gaya"); "chala gaya" alone elsewhere is just "went" (papa office chale gaye)
RESOLVED_AFTER = r"^\s*(?:\w+\s+){0,3}?(?:" + _RES_CORE + r"|chal[ae]\s+(?:gaya|gayi|gaye|gya|gyi|gai)|chali\s+(?:gayi|gyi|gai))\b"
#: a short next clause that ends the episode ("..., ab theek hoon")
RESOLVED_CLAUSE = r"\b(?:" + _RES_CORE + r")\b"
CURRENT = (r"\b(?:abhi|is\s+waqt|iss\s+waqt|is\s+samay|filhaal|filhal|ab\s+bhi|ab\s+tak|lagatar|lagataar|"
           r"(?:subah|kal|raat|dopahar|shaam|sham|" + _NUM + r"\s+(?:ghante|ghanton|minute|minat|din|dino|dinon|hafte|hafton))\s+se|"
           r"pichh?l[ae]y?\s+\w+\s+se|\w+\s+\w+\s+(?:pehle|pahle)\s+se|aaj\s+bhi|wapas\s+aa\w*|shuru\s+ho\w*|"
           r"fir\s+se|phir\s+se|dobara|ab\s+(?:\w+\s+)?(?:ho\s+raha|ho\s+rahi|ho\s+rahe|hone\s+lag\w*))\b")
SAME_DAY = r"\b(?:aaj|aj|subah|dopahar|shaam|sham|abhi|thodi\s+der|kuch\s+der|(?:\d+|ek|do|teen|kuch)\s+(?:ghante|ghanta|minute|minat)\s+(?:pehle|pahle))\b"
PAST_TENSE = r"\b(?:tha|thi|the)\b"
#: a report verb ("aa rahi", "ho raha"): "saans nahi aa rahi kya ye normal hai?" reports first, asks second
REPORT_VERB = r"\b(?:rah[aie]|rh[aie])\b"
