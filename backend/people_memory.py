"""The people and pets in a person's life, as they tell Bubbles about them ("my boyfriend's name is Ashmit", "my dog is called Bruno").

Pure text rules, no database and no model, so they are instant, free, and the same every time:
- ``extract_people_facts``: what the person said, as facts for memory_manager to save (same shape as its other facts);
- ``recall_target``: whether a message asks Bubbles to recall one of them ("what's my boyfriend's name?", "do you remember my name?");
- ``remembered_reply`` / ``recall_reply``: the warm one-line answers for those two cases.

Only first-person statements count. A negated, hypothetical, quoted or questioning phrasing is ignored (memory_manager._is_hedged), and a
sentence about someone else ("his boyfriend is...") never matches because every pattern needs "my" or "I".

Hinglish and Hindi work the same way ("mera boyfriend Ashmit hai", "meri behen ka naam Priya hai", "Rahul mera dost hai", "मेरे पति का नाम राहुल है"),
with their own hedges (agar, shayad, kya, kaun, nahi, kaash, "?") and reported speech (usne kaha). Where a Hindi sentence has no capital letter to tell a name
from a describing word ("मेरी बहन टीचर है"), only the explicit forms are trusted: a miss is better than a wrong name in someone's memory. So a bare
"mera dost Rahul ..." counts only when the name is followed by "hai", by a mood word and "hai", or by nothing at all: "mera pati Rahul mujhe maar dalega" is a
disclosure that merely names someone, never an introduction. The English patterns, stop list and hedges are exactly what they were before Hinglish was added.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Any, Callable

# relation word as typed -> (group, spoken word). Groups: partner and mother/father hold one person; the rest can hold several.
_RELATIONS: dict[str, tuple[str, str]] = {
    "boyfriend": ("partner", "boyfriend"), "bf": ("partner", "boyfriend"), "girlfriend": ("partner", "girlfriend"), "gf": ("partner", "girlfriend"),
    "partner": ("partner", "partner"), "husband": ("partner", "husband"), "hubby": ("partner", "husband"), "wife": ("partner", "wife"),
    "spouse": ("partner", "spouse"), "fiance": ("partner", "fiancé"), "fiancee": ("partner", "fiancée"), "fiancé": ("partner", "fiancé"),
    "fiancée": ("partner", "fiancée"),
    "mom": ("mother", "mother"), "mum": ("mother", "mother"), "mother": ("mother", "mother"), "mommy": ("mother", "mother"), "mama": ("mother", "mother"),
    "dad": ("father", "father"), "father": ("father", "father"), "papa": ("father", "father"), "daddy": ("father", "father"),
    "brother": ("brother", "brother"), "sister": ("sister", "sister"), "son": ("son", "son"), "daughter": ("daughter", "daughter"),
    "grandmother": ("grandmother", "grandmother"), "grandma": ("grandmother", "grandmother"), "grandfather": ("grandfather", "grandfather"),
    "grandpa": ("grandfather", "grandfather"), "aunt": ("aunt", "aunt"), "uncle": ("uncle", "uncle"), "cousin": ("cousin", "cousin"),
    "best friend": ("best friend", "best friend"), "friend": ("friend", "friend"), "roommate": ("roommate", "roommate"),
    "flatmate": ("roommate", "roommate"),
    "dog": ("dog", "dog"), "puppy": ("dog", "dog"), "cat": ("cat", "cat"), "kitten": ("cat", "cat"), "pet": ("pet", "pet"),
    "mother-in-law": ("mother-in-law", "mother-in-law"), "father-in-law": ("father-in-law", "father-in-law"),
    "brother-in-law": ("brother-in-law", "brother-in-law"), "sister-in-law": ("sister-in-law", "sister-in-law"),
    "mother in law": ("mother-in-law", "mother-in-law"), "father in law": ("father-in-law", "father-in-law"),   # typed without the hyphens
    "brother in law": ("brother-in-law", "brother-in-law"), "sister in law": ("sister-in-law", "sister-in-law"),
}
_ONE_PERSON = frozenset({"partner", "mother", "father", "mother-in-law", "father-in-law"})   # a new name for these is a correction of the old one
_PETS = frozenset({"dog", "cat", "pet"})
# The English patterns only know English words ("Ana is my beta tester" is not a family); the Hinglish ones below also know the Hindi words.
_REL = "|".join(sorted((re.escape(r) for r in _RELATIONS), key=len, reverse=True))

# Hindi and Hinglish relation words, in Latin and Devanagari, each with the English word Bubbles says back. Words on one line share a meaning.
# "mama" stays a mother (English); a Hinglish "mera mama" is the mother's brother, see _relation_for.
_HINDI_ROWS = (
    ("pati shohar gharwala पति शौहर घरवाला हस्बैंड", "partner", "husband"), ("patni biwi bivi gharwali पत्नी बीवी बिवी घरवाली वाइफ", "partner", "wife"),
    ("बॉयफ्रेंड", "partner", "boyfriend"), ("गर्लफ्रेंड", "partner", "girlfriend"),
    ("mummy mumma maa ma मम्मी मम्मा माँ मां मामा", "mother", "mother"), ("पापा", "father", "father"),
    ("bhai bhaiya bhaiyya भाई भैया भइया", "brother", "brother"), ("behen behan bahan bahen didi बहन बहिन दीदी", "sister", "sister"),
    ("dost saheli दोस्त सहेली", "friend", "friend"), ("beta bete बेटा बेटे", "son", "son"), ("beti बेटी", "daughter", "daughter"),
    ("saas सास", "mother-in-law", "mother-in-law"), ("sasur ससुर", "father-in-law", "father-in-law"),
    ("devar देवर", "brother-in-law", "brother-in-law"), ("nanad bhabhi ननद भाभी", "sister-in-law", "sister-in-law"),
    ("nana dada नाना दादा", "grandfather", "grandfather"), ("nani dadi नानी दादी", "grandmother", "grandmother"),
    ("chacha चाचा", "uncle", "uncle"), ("chachi mami bua चाची मामी बुआ", "aunt", "aunt"),
    ("kutta kutte कुत्ता कुत्ते", "dog", "dog"), ("billi बिल्ली", "cat", "cat"),
)
_RELATIONS.update({w: (group, spoken) for words, group, spoken in _HINDI_ROWS for w in words.split()})
_REL_H = "|".join(sorted((re.escape(r) for r in _RELATIONS), key=len, reverse=True))
_WORD = r"[A-Za-z][A-Za-z'’-]*"
_NAME = rf"({_WORD}(?:[ \t]+{_WORD})?)"
_POSS = r"(?:['’]s|s)?"

# Words that are not a name after a plain "my boyfriend is ..." (English). This is the list the English patterns have always used, and the only one they use:
# a real name that spells like a Hindi word ("my friend is called Mai", "Ye is my friend") must keep working there.
_NOT_NAMES_EN = frozenset("""a an the my your his her their our not no so very really quite too just also still always never now here there who what why how when where
he she it they we you i this that these those someone somebody anyone nobody something nothing everyone also doing fine ok okay good bad sad happy angry upset
tired sick ill unwell away home late early busy gone back coming leaving going getting being feeling mine yours his hers ours theirs one two three""".split()) | frozenset("""muslim hindu sikh jewish buddhist jain catholic atheist gay lesbian straight bisexual trans
violent abusive alcoholic drunk unemployed jobless rich poor indian american british jealous possessive toxic rude kind caring controlling cheating lying lazy strict""".split())
# ^ added with Hinglish memory: a capital letter after "my boyfriend is" can be a religion or a trait ("my boyfriend is Muslim"), which must never be saved as a name


def _key(word: str) -> str:
    """A word as the Hinglish stop lists spell it: lower case, the Devanagari nukta dropped (नाराज़ with or without it), chandrabindu as anusvara."""
    return unicodedata.normalize("NFC", word).replace("\u093c", "").replace("\u0901", "\u0902").lower()


# Hinglish and Hindi: pronouns and little words. A pet may well be called Happy, so a name that was said outright ("ka naam Happy hai") is only checked
# against these.
_NEVER_NAMES_H = frozenset(_key(w) for w in """a an the my your his her their our not no so very really quite too just also still always never now here there who what why how
when where he she it they we you i this that these those someone somebody anyone nobody something nothing everyone mine yours hers ours theirs
main mai mein me hum ham tum tu aap wo woh vo voh ye yeh yah ve vah wahi yahi usne isne unhone inhone usko isko unko inko mujhe mera meri mere tera teri tere
uska uski uske iska iski iske apna apni apne koi kuch sab sabhi kaun kon kya kab kyun kyu kaise kahan kitna kitni kitne kisne kisi hai hain hu hoon ho tha thi the
hae hy h ka ki ke ko se ne par pe tak bhi hi toh to nahi nahin nhi aur ya lekin magar kyunki jis jiska jiski jab tab agar shayad phir bas sirf bahut bohot bahot bhut
ab abhi aaj kal parso ek haan han ji arre oye dekho suno hello hey bubbles bhai yaar bro naam
है हैं हूँ हूं हो था थी थे का की के को से में पर और या भी तो ना नहीं नही क्या कौन कब कहाँ क्यों कैसे यह वह ये वो वे मेरा मेरी मेरे आप तुम तू मैं हम उसने ने अगर शायद जब कभी
बहुत नाम सुनो देखो हाँ हां अरे ओके हेलो""".split())
# ...and, after a bare "mera dost X ...", also the feelings, states, places, times, jobs and shop-talk words a capital letter could still fool (and, in
# Devanagari, which has no capital letters to give them away). Words that are also common pet and first names (Lucky, Sunny, Rose, Moti) stay off it.
_NOT_NAMES_H = _NEVER_NAMES_H | frozenset(_key(w) for w in _NOT_NAMES_EN) | frozenset(_key(w) for w in """
naraz bimar bemar thaka thaki khush udaas pareshan theek thik accha achha acha bura buri single free
fit healthy alive dead safe alone akela akeli online offline available ready hungry sleepy bored sorry sure right wrong nice great cute funny smart strong weak lazy
mad old young tall short fat thin married engaged divorced pregnant diabetic depressed anxious stressed injured hurt fever cold cough well normal better worse best worst
jealous confused lost missing mast zinda kamzor gussa
bilkul thoda thodi zyada jyada kaafi kafi ekdum ekdam itna itni itne utna wahan yahan waha yaha andar bahar upar neeche saath sath pass door paas
subah shaam raat dopahar din week weekend kabhi hamesha aksar pakka pura puri sach sachmuch waise vaise aise jaise isliye
doctor engineer teacher student nurse lawyer manager driver officer professor tutor designer developer cop police army soldier farmer banker clerk accountant chef cook
maid servant pilot actor singer artist writer businessman
monday tuesday wednesday thursday friday saturday sunday
delhi mumbai kolkata chennai bengaluru bangalore hyderabad pune jaipur lucknow india noida gurgaon gurugram ghaziabad faridabad ahmedabad surat vadodara indore bhopal nagpur
nashik patna ranchi kanpur varanasi agra chandigarh amritsar ludhiana dehradun shimla goa kerala punjab bihar gujarat rajasthan assam odisha haryana kashmir mysore kochi thane
dubai abroad canada usa uk america london paris singapore australia germany japan china nepal pakistan bangladesh europe asia africa toronto sydney melbourne
hospital clinic office school college university class gym shop market home ghar work job lab airport station mall hostel pg flat room bed icu
instagram whatsapp facebook youtube snapchat google netflix twitter telegram
बीमार नाराज़ थका थकी खुश उदास परेशान ठीक अच्छा अच्छी बुरा बुरी सिंगल अकेला अकेली व्यस्त बिज़ी बिजी मस्त फ्री जिंदा ज़िंदा कमज़ोर गुस्से शादीशुदा गर्भवती प्रेग्नेंट डिप्रेस्ड
बिल्कुल बिलकुल थोड़ा थोड़ी ज़्यादा ज्यादा काफ़ी काफी एकदम इतना इतनी उतना वहाँ वहां यहाँ यहां अंदर बाहर ऊपर नीचे साथ पास दूर
अभी आज कल परसों सुबह शाम रात दोपहर दिन हमेशा सच सही गलत ग़लत नया नई पुराना पुरानी बड़ा बड़ी छोटा छोटी
घर दिल्ली मुंबई कोलकाता चेन्नई बेंगलुरु हैदराबाद पुणे जयपुर लखनऊ भारत नोएडा गुड़गांव पटना भोपाल इंदौर अहमदाबाद गोवा केरल पंजाब बिहार दुबई कनाडा लंदन अमेरिका विदेश
स्कूल कॉलेज ऑफिस दफ्तर अस्पताल हॉस्पिटल क्लिनिक दुकान बाज़ार जिम क्लास
टीचर डॉक्टर इंजीनियर नर्स वकील ड्राइवर पुलिस अफसर मैनेजर स्टूडेंट छात्र शिक्षक
सोमवार मंगलवार बुधवार गुरुवार शुक्रवार शनिवार रविवार""".split())

_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    # my boyfriend's name is Ashmit / my boyfriends name is ashmit / my dog's name is called Bruno
    ("named", re.compile(rf"\bmy\s+(?P<rel>{_REL}){_POSS}\s+name\s+is\s+(?:called\s+|named\s+)?{_NAME}", re.I)),
    # my dog is called Bruno / my dog named Bruno
    ("named", re.compile(rf"\bmy\s+(?P<rel>{_REL})\s+(?:is\s+|was\s+)?(?:called|named)\s+{_NAME}", re.I)),
    # I have a dog called Bruno / I've got a sister named Riya
    ("named", re.compile(rf"\b(?:i\s+have|i've\s+got|i\s+got)\s+an?\s+(?P<rel>{_REL})\s+(?:called|named)\s+{_NAME}", re.I)),
    # my boyfriend is Ashmit (the name must start with a capital: "my boyfriend is tired" is not a name)
    ("capital", re.compile(rf"\bmy\s+(?P<rel>{_REL})\s+(?:is|was)\s+{_NAME}", re.I)),
    # I'm dating Ashmit
    ("dating", re.compile(rf"\b(?:i'm|i’m|im|i\s+am)\s+dating\s+{_NAME}", re.I)),
)
# Ashmit is my boyfriend (case-sensitive on purpose: the name is a capitalised word that is not a pronoun)
_NAME_FIRST = re.compile(rf"\b(?P<n>[A-Z][a-z'’-]+(?:\s+[A-Z][a-z'’-]+)?)\s+(?i:is\s+my\s+(?P<rel>{_REL}))\b")

# Hinglish and Hindi. \b does not work next to Devanagari vowel signs, so the word edges are spelled out.
_DEV = "\u0900-\u097F"
_DEVN = "\u0900-\u0963\u0971-\u097F"   # a Devanagari letter or vowel sign (not the full stop)
_START = rf"(?<![\w{_DEV}])"
_END = rf"(?![\w{_DEV}])"
_POSS_H = r"(?i:mera|meri|mere)|मेरा|मेरी|मेरे"
_IS_H = r"(?:(?i:hai|hain|hae|hy|h)|है|हैं)"
_CAP = r"[A-Z][a-z'-]+"                           # a capitalised Latin word
_DEVW = rf"[{_DEVN}]+"
_ANY = rf"(?:[A-Za-z][A-Za-z'-]*|{_DEVW})"
# meri behen ka naam Priya hai / मेरे पति का नाम राहुल है (the name may be lower case: "ka naam" says it is one)
_NAMED_H = re.compile(
    rf"{_START}(?P<poss>{_POSS_H})[ \t]+(?P<rel>{_REL_H})[ \t]+(?:ka|ki|ke|का|की|के)[ \t]+(?:naam|nam|name|नाम)[ \t]+(?P<n>{_ANY}(?:[ \t]+{_ANY})?)[ \t]+{_IS_H}{_END}", re.I)
# A bare name ("mera dost Rahul ...") is only trusted when it is followed by "hai", by a mood word and "hai" ("Rahul bimar hai"), or by nothing but the end of
# the message. Anything else after it ("Rahul mujhe maar dalega", "Goa gaya hai", "Rahul Dubai gaya hai") is a sentence about something else that happens
# to hold a capitalised word, and a disclosure must reach the model, never the cheerful "remembered" line.
_STATE_H = r"(?:(?i:bimar|bemar|naraz|busy|theek|thik)|बीमार|नाराज\u093c?|ठीक|व्यस्त|बिज\u093c?ी)"
_BARE_CLOSE = rf"(?=[ \t]+(?:{_IS_H}|{_STATE_H}[ \t]+{_IS_H}){_END}|[.!\u0964\s]*\Z)"
# mera boyfriend Ashmit hai / mera dost Rahul bimar hai (the capital letter is what says it is a name; "Delhi hai" is a place, see _NOT_NAMES_H)
_BARE_H = re.compile(
    rf"{_START}(?P<poss>{_POSS_H})[ \t]+(?P<rel>(?i:{_REL_H}))[ \t]+(?P<n>{_CAP}(?:[ \t]+{_CAP})?){_END}{_BARE_CLOSE}")
# mera boyfriend राहुल hai: a Devanagari word inside a Latin sentence is a name
_BARE_DEV_H = re.compile(rf"{_START}(?P<poss>(?i:mera|meri|mere))[ \t]+(?P<rel>(?i:{_REL_H}))[ \t]+(?P<n>{_DEVW}){_END}{_BARE_CLOSE}")
# Ashmit mera boyfriend hai / राहुल मेरा दोस्त है
_FIRST_H = re.compile(
    rf"{_START}(?P<n>{_CAP}(?:[ \t]+{_CAP})?|{_DEVW}(?:[ \t]+{_DEVW})?)[ \t]+(?P<poss>{_POSS_H})[ \t]+(?P<rel>(?i:{_REL_H}))[ \t]+{_IS_H}{_END}")
# mere husband ka naam Aman nahi balki Arman hai: a correction, the new name is the one to keep
_CORRECT_H = re.compile(
    rf"{_START}(?P<poss>{_POSS_H})[ \t]+(?P<rel>{_REL_H})[ \t]+(?:ka|ki|ke|का|की|के)[ \t]+(?:naam|nam|name|नाम)[ \t]+{_ANY}[ \t]+(?:nahi|nahin|nhi|नहीं|नही)[ \t]+"
    rf"(?:balki|balke|bulki|but|lekin|magar|बल्कि|लेकिन)[ \t]+(?P<n>{_ANY}(?:[ \t]+{_ANY})?)[ \t]+{_IS_H}{_END}", re.I)
_PATTERNS_H: tuple[tuple[str, re.Pattern[str]], ...] = (("named", _NAMED_H), ("correct", _CORRECT_H), ("capital", _BARE_H), ("capital", _BARE_DEV_H))


def _tidy_name(raw: str, *, need_capital: bool, stop: frozenset[str] = _NOT_NAMES_EN) -> str | None:
    """One or two words from the capture: the second only when both are capitalised ("Mary Ann"); lower-case typing is title-cased.
    Devanagari has no capitals, so its words count as capitalised. ``stop`` is the list of words that are not a name: the English one unless the
    pattern is a Hinglish one."""
    words = [w for w in raw.replace("’", "'").split() if w]
    if not words:
        return None
    first = words[0]
    if _key(first) in stop or (need_capital and first[0].islower()):
        return None
    keep = [first]
    if len(words) > 1 and not first[0].islower() and not words[1][0].islower() and _key(words[1]) not in stop:
        keep.append(words[1])
    name = " ".join(keep)
    return name.title() if name == name.lower() else name


def _fact(group: str, spoken: str, name: str) -> dict[str, Any]:
    pet = group in _PETS
    key = group if group in _ONE_PERSON else f"{'pet' if pet else 'person'}:{group}:{name.lower()}"
    if group == "partner" and spoken == "partner":
        content = f"The user's partner is called {name}."
    elif pet:
        content = f"The user has a {spoken} called {name}."
    else:
        content = f"The user's {spoken} is called {name}."
    return {"key": key, "value": name, "content": content, "confidence": 0.97, "relation": spoken}


_REPORTED = re.compile(r"\b(?:said|says|told\s+me|thinks?|claims?|heard|reckons?|guess(?:ed)?|assume[sd]?)\b", re.I)
# A wish or a maybe in the same clause ("I wish my husband was Shah Rukh", "maybe my best friend is Sana") is not a statement. memory_manager._is_hedged does not
# know these, so the English patterns check them here: before the match, and right after the name.
_WISH_EN = re.compile(r"\b(?:wish(?:ed|es|ing)?|maybe|perhaps|possibly|if\s+only|dreaming)\b", re.I)
_WISH_EN_AFTER = re.compile(r"^[ \t]*(?:maybe|perhaps|possibly|i\s+guess|or\s+something)\b", re.I)


def _wished(text: str, m: re.Match) -> bool:
    clause = _sentence_before(text, m.start(), 60)
    clause = clause[max(clause.rfind(","), clause.rfind(";")) + 1:]
    return bool(_WISH_EN.search(clause) or _WISH_EN_AFTER.match(text[m.end():m.end() + 30]))


def _words(*alternatives: str) -> re.Pattern[str]:
    """Whole words (Latin or Devanagari) from the list; a space inside one means any gap."""
    return re.compile(_START + "(?:" + "|".join(a.replace(" ", r"[ \t]+") for a in alternatives) + ")" + _END, re.I)


# Hinglish and Hindi twins of the English hedges. They run on Hinglish matches only; the English patterns keep the English rules.
# Said, thought, asked or heard by someone ("usne kaha", "Riya keh rahi thi", "unka kehna hai", "uske hisaab se", "mujhe lagta hai")...
_SAID_DEV = ("कहा", "कहता", "कहती", "कहते", "कहना", "बोला", "बोली", "बोलता", "बोलती", "बताया", "बताता", "बताती", "सुना", "सोचा", "लगता", "लगती",
             "पूछा", "समझता", "समझती", "मानता", "मानती", "अनुसार", "हिसाब")
_SAID_H = _words("kaha", "kahaa", "kah", "kahte", "kehta", "kehti", "kehte", "keh", "kehna", "kehne", "bola", "boli", "bolta", "bolti", "bolte", "bol",
                 "bataya", "batayi", "batata", "batati", "batate", "sunaya", "suna", "socha", "sochta", "sochti", "sochte", "lagta", "lagti", "lagte",
                 "puchha", "pucha", "poochha", "poocha", "samajh", "samajhta", "samajhti", "samajhte", "samjha", "samjhi", "manta", "manti", "maanta", "maanti",
                 "hisaab", "hisab", "anusaar", "anusar", "mutabik", "mutabiq", "according", *_SAID_DEV)
_SAID_H_DEV = _words(*_SAID_DEV)
# ...a question or a maybe ("kya", "kaun", "agar", "shayad")...
_DOUBT_H = _words("agar", "agr", "shayad", "shayd", "kya", "kyaa", "kaun", "kon", "kab", "kyun", "kyu", "kyon", "kaise", "kisne", "kitna", "jab", "kabhi",
                  "maan lo", "maano", "socho", "अगर", "शायद", "क्या", "कौन", "कब", "क्यों", "कैसे", "जब", "कभी", "मान लो")
# ...a wish or a dream ("kaash mera boyfriend Ashmit hota", "... ho sakta hai", "..., but only in my dreams")...
_WISH_H = _words("kaash", "kash", "hota", "hoti", "hote", "ho sakta", "ho sakti", "ho sakte", "ho jaye", "ho jaaye", "ho jayega", "ho jayegi", "ban jaye",
                 "ban jaaye", "ban jayega", "ban jayegi", "ban sakta", "ban sakti", "dream", "dreams", "sapne", "sapna", "wish", "imagine", "pretend", "pretending",
                 "काश", "होता", "होती", "होते", "हो सकता", "हो सकती", "हो जाए", "बन जाए", "बन जाएगा", "बन जाएगी", "सपने", "सपना")
# ...or a no ("nahi" and its text-speak forms; a trailing "na" is a tag question: "hai na?").
_NO_H = _words("nahi", "nahin", "nhi", "nhin", "nahee", "nahii", "ni", "nai", "naa", "na", "नहीं", "नही", "ना")
# ...a name the person cannot place ("yaad nahi aa raha", "pata nahi") or an "or" between two names ("Mohit hai ya Rohit"); a new clause after the name
# ("... hai lekin shayad hum ...", "... hai aur ...") starts a different thought, so a maybe in it does not hedge the name.
_UNSURE_H = _words("yaad nahi", "yaad nhi", "yad nahi", "pata nahi", "pata nhi", "pta nahi", "maloom nahi", "sure nahi", "pakka nahi", "confirm nahi",
                   "याद नहीं", "पता नहीं", "मालूम नहीं", "पक्का नहीं")
_OR_H = _words("ya", "या")
_CLAUSE_H = _words("lekin", "magar", "but", "aur", "and", "jabki", "parantu", "however", "लेकिन", "मगर", "और", "परंतु")
_WAS_H = re.compile(rf"[ \t]*(?:tha|thi|था|थी|थे){_END}", re.I)   # "mera boyfriend Ashmit tha" is somebody from before
_STOPS = ".!?\n\u0964"                                         # \u0964 is the Hindi full stop (danda)
_LOOK = 240    # how far a Hinglish hedge looks (characters): a longer run with no full stop is not one thought, and it keeps a very long message cheap


def _sentence_before(text: str, start: int, reach: int | None = None) -> str:
    """The same sentence, up to ``start``. ``reach`` caps how far back it looks (None means the whole sentence)."""
    low = 0 if reach is None else max(start - reach, 0)
    return text[max(max(text.rfind(c, low, start) for c in _STOPS) + 1, low):start]


def _reported(text: str, m: re.Match, *, hinglish: bool = False) -> bool:
    """True when the same sentence passes the statement on from someone else ("she said my boyfriend is Ashmit"). On a Hinglish match the Hinglish words
    count too ("usne kaha mera boyfriend Ashmit hai", "Riya ke hisaab se ...")."""
    said = _sentence_before(text, m.start(), _LOOK if hinglish else None)
    if _REPORTED.search(said):
        return True
    # The match counts for the Devanagari words only: a Devanagari name capture can swallow "बताया", but a Latin name that spells like one ("Bola") is just a name.
    return hinglish and bool(_SAID_H.search(said) or _SAID_H_DEV.search(m.group(0)))


def _doubtful(text: str, m: re.Match) -> bool:
    """memory_manager._is_hedged for Hinglish and Hindi (never run on English matches): a question word or "agar/shayad" earlier in the sentence or just
    after the name, a "nahi" in the same clause, a wish or a dream anywhere in the sentence, the name being from the past ("tha"), or a "?" ending the clause.
    The match itself counts too ("ka naam Ashmit nahi hai")."""
    sentence = _sentence_before(text, m.start(), _LOOK)
    clause = sentence[max(sentence.rfind(","), sentence.rfind(";")) + 1:]
    rest = text[m.end():m.end() + _LOOK]
    ender = re.search(r"[,.;!?\n\u0964]", rest)
    near = (rest[:ender.start()] if ender else rest)[:24]
    new_clause = _CLAUSE_H.search(near)
    if new_clause:
        near = near[:new_clause.start()]                       # "... Tanmay hai lekin shayad hum breakup kar lein": the maybe is about something else
    tail = re.split(r"[.!?\n\u0964]", rest, maxsplit=1)[0]
    whole = m.group(0)
    return bool(_DOUBT_H.search(sentence) or _DOUBT_H.search(near) or _DOUBT_H.search(whole) or _NO_H.search(clause) or _NO_H.search(near) or _NO_H.search(whole)
                or _WISH_H.search(sentence) or _WISH_H.search(tail) or _WISH_H.search(whole) or _WAS_H.match(rest) or (ender and ender.group() == "?")
                or _UNSURE_H.search(sentence) or _UNSURE_H.search(tail) or _OR_H.search(near))


def _doubtful_correction(text: str, m: re.Match) -> bool:
    """``_doubtful`` for "X nahi balki Y hai": the "nahi" belongs to the old name, so it does not count; a question, a maybe or a wish still do."""
    sentence = _sentence_before(text, m.start(), _LOOK)
    tail = re.split(r"[.!?\n\u0964]", text[m.end():m.end() + _LOOK], maxsplit=1)[0]
    return bool(_DOUBT_H.search(sentence) or _WISH_H.search(sentence) or _WISH_H.search(tail) or _UNSURE_H.search(sentence) or _UNSURE_H.search(tail)
                or _DOUBT_H.search(tail[:24]))


def _relation_for(poss: str, rel: str) -> tuple[str, str]:
    """(group, spoken) for a relation word. A Hinglish "mera mama" is the mother's brother; English "my mama" and Hinglish "meri mama" are a mum."""
    rel = rel.lower()
    if rel in ("mama", "मामा") and poss.lower() in ("mera", "mere", "मेरा", "मेरे"):
        return ("uncle", "uncle")
    return _RELATIONS[rel]


def _drop_lead(raw: str) -> str:
    """"Hey Ashmit" -> "Ashmit": little words and greetings in front of a name that came first in the sentence."""
    words = raw.split()
    while len(words) > 1 and _key(words[0]) in _NOT_NAMES_H:
        words.pop(0)
    return " ".join(words)


def extract_people_facts(text: str, hedged: Callable[[str, re.Match], bool]) -> list[dict[str, Any]]:
    """Facts about people and pets in ``text``, at most four. ``hedged(text, match)`` says whether the match is negated, hypothetical,
    quoted or a question (memory_manager passes its own check, so there is one rule for what counts as a plain statement). English matches get
    that check and the English reported-speech words, exactly as before; Hinglish matches also get the Hinglish hedges and stop lists."""
    text = (text or "").replace("’", "'")
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    def take(m: re.Match, group: str, spoken: str, name: str | None, hinglish: bool, correction: bool = False) -> None:
        # The name is looked at first, so a repeat of someone already saved costs nothing; the hedge checks are the slow part.
        if not name or (group, name.lower()) in seen:
            return
        if hedged(text, m) or _reported(text, m, hinglish=hinglish):
            return
        if hinglish and (_doubtful_correction(text, m) if correction else _doubtful(text, m)):
            return
        if not hinglish and _wished(text, m):
            return
        seen.add((group, name.lower()))
        out.append(_fact(group, spoken, name))

    for patterns, hinglish in ((_PATTERNS, False), (_PATTERNS_H, True)):
        for kind, pattern in patterns:
            for m in pattern.finditer(text):
                if len(out) >= 4:
                    return out
                if kind == "dating":
                    take(m, "partner", "partner", _tidy_name(m.group(1), need_capital=True), False)
                    continue
                names = m.groupdict()
                group, spoken = _relation_for(names.get("poss") or "", m.group("rel"))
                stop = (_NEVER_NAMES_H if kind == "named" else _NOT_NAMES_H) if hinglish else _NOT_NAMES_EN   # "ka naam Happy hai" may be a pet called Happy
                take(m, group, spoken, _tidy_name(names.get("n") or m.group(m.lastindex), need_capital=(kind == "capital"), stop=stop), hinglish, kind == "correct")
    for pattern, hinglish in ((_NAME_FIRST, False), (_FIRST_H, True)):
        for m in pattern.finditer(text):
            if len(out) >= 4:
                return out
            group, spoken = _relation_for(m.groupdict().get("poss") or "", m.group("rel"))
            raw = _drop_lead(m.group("n")) if hinglish else m.group("n")
            take(m, group, spoken, _tidy_name(raw, need_capital=True, stop=_NOT_NAMES_H if hinglish else _NOT_NAMES_EN), hinglish)
    return out


# ---------------------------------------------------------------------------------------------------------- recall questions

_ASK = r"(?:what(?:'s|s| is| was)|tell me|remind me|do you (?:still )?(?:remember|know)|can you (?:still )?(?:remember|tell me|recall)|remember)"
_RECALL = (
    re.compile(rf"\b{_ASK}\s+(?:again\s+)?(?:the\s+name\s+of\s+)?my\s+(?P<rel>{_REL}){_POSS}(?:\s+name)?(?:\s+(?:again|please|now))?\s*[?.!]*\s*$", re.I),
    re.compile(rf"\bwho(?:'s|s| is)\s+my\s+(?P<rel>{_REL})(?:\s+(?:again|please|now))?\s*[?.!]*\s*$", re.I),
    re.compile(rf"\b(?:do|can)\s+you\s+(?:still\s+)?(?:remember|know)\s+(?:who\s+)?my\s+(?P<rel>{_REL})(?:\s+is)?\s*[?.!]*\s*$", re.I),
)
_NAME_ASK = (
    re.compile(rf"\b{_ASK}\s+(?:again\s+)?my\s+name(?:\s+(?:again|please|now))?\s*[?.!]*\s*$", re.I),
    re.compile(r"\bwhat\s+(?:do\s+you|should\s+you)\s+call\s+me(?:\s+(?:again|please|now))?\s*[?.!]*\s*$", re.I),
    re.compile(r"\bwho\s+am\s+i(?:\s+(?:again|please|now))?\s*[?.!]*\s*$", re.I),
)


def recall_target(text: str) -> str | None:
    """'name' when the message asks for the person's own name, a relation group ('partner', 'dog', ...) when it asks for the name of someone
    in their life, else None. Short questions only: a long message is something else with the same words in it."""
    t = (text or "").replace("’", "'").strip()
    if not t or len(t.split()) > 12:
        return None
    for pattern in _NAME_ASK:
        if pattern.search(t):
            return "name"
    for pattern in _RECALL:
        m = pattern.search(t)
        if m:
            return _RELATIONS[m.group("rel").lower()][0]
    return None


def _pick(options: tuple[str, ...], seed: str) -> str:
    return options[int(hashlib.sha256(seed.encode("utf-8")).hexdigest(), 16) % len(options)]


def remembered_reply(facts: list[dict[str, Any]], *, seed: str) -> str:
    """A warm one-liner for a message that only told Bubbles something: it confirms what it will remember, then hands the chat back."""
    bits: list[str] = []
    first_name = None
    for f in facts:
        key, value = f["key"], f["value"]
        if key == "name":
            first_name = value
        elif key == "location":
            bits.append(f"you're in {value}")
        elif key == "occupation":
            bits.append(f"you work as {_article(value)}")
        elif key == "study":
            bits.append(f"you're studying {value}")
        elif f.get("relation"):
            rel = f["relation"]
            bits.append(f"{value} is your {rel}" if rel not in _PETS else f"you have a {rel} called {value}")
    if first_name and not bits:
        return _pick((f"Lovely to meet you, {first_name}! I'll remember that. How are you feeling today?",
                      f"Nice to meet you, {first_name}. That's saved, so I'll always know it's you. How's your day going?"), seed)
    if first_name:
        bits.insert(0, f"I'll call you {first_name}")
    if not bits:
        return "Got it, I'll remember that."
    said = bits[0] if len(bits) == 1 else ", ".join(bits[:-1]) + " and " + bits[-1]
    tail = _pick(("How are you feeling today?", "How's your day been?", "Anything on your mind today?"), seed + "tail")
    opener = _pick(("Got it", "Noted", "Thanks for telling me"), seed)
    return f"{opener}: {said}. I'll remember that. {tail}"


def _article(value: str) -> str:
    return f"{'an' if value[:1].lower() in 'aeiou' else 'a'} {value}"


def recall_reply(target: str, facts: list[dict[str, Any]], *, account_name: str | None) -> str:
    """The answer to a recall question, from saved facts only. Nothing saved is said plainly, and the person is invited to tell Bubbles."""
    if target == "name":
        saved = next((f["value"] for f in facts if f.get("key") == "name"), None) or account_name
        return (f"Of course: you're {saved}." if saved else "I don't have your name yet. Tell me what to call you and I'll remember it.")
    rows = [f for f in facts if f.get("relation") and _RELATIONS.get(str(f["relation"]).lower(), ("",))[0] == target]
    spoken = rows[0]["relation"] if rows else None
    if not rows:
        word = {"partner": "partner", "mother": "mum", "father": "dad"}.get(target, target)
        return f"I don't have your {word}'s name yet. Tell me and I'll remember it."
    names = [r["value"] for r in rows]
    listed = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]
    if spoken in _PETS:
        return f"Of course I remember: your {spoken} is {listed}."
    return f"Of course I remember: your {spoken} is {listed}." if len(names) == 1 else f"Of course: you've told me about {listed} as your {spoken}s."
