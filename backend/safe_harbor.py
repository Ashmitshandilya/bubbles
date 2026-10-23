"""Safe Harbor: a person who says someone close to them hurts, frightens or controls them is answered by Bubbles itself, with fixed,
reviewed copy, and the message never goes to an outside model (plan section 7.6). Pure text rules, no model, no network.

What lives here:
- ``assess``      the message -> a ``Harbor`` (tier 0 to 3, a person who says they hurt someone, someone else's story), in English, Hinglish
                  (Roman script) and Hindi (Devanagari). Independent from ``health_semantics`` so the health engine is not disturbed.
- the copy bank   tier 2, tier 3, the accountability copy, the follow-ups and the resource lines, three wordings each chosen by a stable
                  hash (like ``small_talk_reply``), so a retried message gets the same words.
- the state       a small state machine per conversation (``harbor_state`` signed document) that keeps the Safe Harbor voice on the next
                  messages, and a ``harbor_flag`` signed document (tier 1 and above) that pauses partner signals later (plan 7.5).

Tiers: 0 no signal. 1 control, fear or verbal abuse alone (a model may answer, with a SAFE HARBOR LITE block). 2 one act of physical
violence without a danger marker (fixed copy, gentle). 3 a danger marker (choking, a threat to kill, a weapon, sexual violence, a child
hurt, pregnancy, getting worse, fear, or a second tier 2 within 30 days): fixed copy, calm but explicit, with the right numbers.

Hedging follows the same idea as ``memory_manager._is_hedged``: a negated, hypothetical, quoted, playful or past-and-over mention is not
a live disclosure. The rules lean towards answering: a missed disclosure costs far more than a gentle reply to a look-alike.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from itertools import islice
from typing import Any

import locale_support

TIER_NONE, TIER_LITE, TIER_GENTLE, TIER_EXPLICIT = 0, 1, 2, 3
STATE_HOURS = 24            # a Safe Harbor voice held for a conversation fades after a day
REPEAT_DAYS = 30            # a second tier 2 inside this window is tier 3
FLAG_DAYS = 90              # how long events stay in the harbor_flag document
MAX_EVENTS = 30

# --------------------------------------------------------------------------
# Reading the message
# --------------------------------------------------------------------------

_PUNCT = str.maketrans({"’": "'", "‘": "'", "ʼ": "'", "“": '"', "”": '"', "–": "-", "—": "-", " ": " "})


def _dev(pattern: str) -> str:
    """Devanagari patterns are written in any form and compared in the same (NFKC) form as the text."""
    return unicodedata.normalize("NFKC", pattern)


def _c(pattern: str, flags: int = 0) -> "re.Pattern[str]":
    return re.compile(_dev(pattern), flags)


# Common typing slips for the words that carry a disclosure ("huband hitt me", "he chocked me"). Fixed before any rule runs, so every rule
# keeps one clean spelling. Only words that are almost never meant any other way are listed.
_TYPOS = {
    "huband": "husband", "husbnd": "husband", "husnd": "husband", "hubsand": "husband", "husbend": "husband", "husbond": "husband",
    "hasband": "husband", "husban": "husband", "hsuband": "husband", "huzband": "husband", "husbandd": "husband",
    "huzbund": "husband", "husbund": "husband", "hasbund": "husband", "husbunt": "husband", "huzbend": "husband", "hubsband": "husband",
    "boyfrnd": "boyfriend", "boyfreind": "boyfriend", "boyfirend": "boyfriend", "boy friend": "boyfriend",
    "girlfrnd": "girlfriend", "girlfreind": "girlfriend", "girl friend": "girlfriend",
    "hitt": "hit", "hitted": "hit", "slaped": "slapped", "slapd": "slapped", "slpped": "slapped", "slapt": "slapped", "slaaped": "slapped",
    "punchd": "punched", "punhced": "punched", "punshed": "punched", "punsched": "punched", "puched": "punched", "punhed": "punched", "punchedd": "punched",
    "kickd": "kicked", "kiked": "kicked", "kikked": "kicked", "slappd": "slapped", "slapedd": "slapped", "beeten": "beaten", "beatn": "beaten",
    "strangeled": "strangled", "strangaled": "strangled", "strangld": "strangled", "strangeld": "strangled", "stranglled": "strangled", "strangel": "strangle",
    "chocked": "choked", "chokd": "choked", "choaked": "choked", "chockd": "choked", "chock": "choke", "choak": "choke", "chocking": "choking",
    "kiled": "killed", "killd": "killed", "kil": "kill", "knfe": "knife", "nife": "knife",
    "violnt": "violent", "voilent": "violent", "violant": "violent", "mar peet": "marpeet", "mar pet": "marpeet",
    # the core Hinglish verb typed with a space ("peet ta hai", "maar ti hai")
    "peet ta": "peetta", "peet ti": "peetti", "peet te": "peette", "maar ta": "maarta", "maar ti": "maarti", "maar te": "maarte",
    "pit ta": "pitta", "pit ti": "pitti", "pit te": "pitte",
}
_TYPO_RX = re.compile(r"\b(?:" + "|".join(re.escape(k) for k in sorted(_TYPOS, key=len, reverse=True)) + r")\b")


def _norm(text: Any) -> str:
    t = unicodedata.normalize("NFKC", str(text or "")).translate(_PUNCT).lower()
    t = re.sub(r"(.)\1{2,}", r"\1\1", t)                   # "maaarta" -> "maarta"
    t = _TYPO_RX.sub(lambda m: _TYPOS[m.group()], t)
    return re.sub(r"[ \t\r\f\v]+", " ", t).strip()


_SENT = _c(r"(?<=[.!?।])\s+|[\n;]+")


def _split(text: str) -> list[str]:
    return [s.strip() for s in _SENT.split(text) if s and s.strip()]


_DEVANAGARI = _c(r"[ऀ-ॿ]")
_HI_WORDS = frozenset(
    "mujhe mujhko muje mera meri mere hai hain nahi nahin nhi kya roz rozana pati patni biwi maarta maarti maara peetta peeta thappad gussa "
    "darr dar bahut bohot bhi lekin aur toh tum tumhe aap unhe usne unhone woh wo kar karta karti karte raha rahi rahe hoon hu hun tha thi "
    "the yaar ghar bachon bachchon saas sasur sasural dahej jaan khud mereko meko isliye kyunki abhi kal aaj raat mat chahiye sakta sakti "
    "sakte kaise kyun mein se ko ka ki ke ne par pe haath uthaya uthata dhamki dhamkata chhodo".split())
_HI_STRONG = frozenset("mujhe mujhko muje mera meri mere maarta maarti maara thappad nahi nahin kya roz pati biwi patni usne unhone hoon hun tha thi ghar bachon dahej".split())


def detect_language(text: Any) -> str:
    """'hi' (Devanagari), 'hi-latn' (Roman-script Hindi) or 'en'."""
    t = _norm(text)
    letters = sum(1 for ch in t if ch.isalpha())
    if letters and len(_DEVANAGARI.findall(t)) / letters >= 0.3:
        return "hi"
    words = re.findall(r"[a-z]+", t)
    hits = [w for w in words if w in _HI_WORDS]
    return "hi-latn" if len(hits) >= 2 and any(w in _HI_STRONG for w in hits) else "en"


# ---- who: the person doing it (a partner, a spouse, an in-law, a family member, or he / she / they)

_PARTNER = r"(?:husband|hubby|hubs|wife|wifey|boyfriend|girlfriend|bf|gf|partner|fianc[eé]e?|spouse|ex|ex-husband|ex-wife|ex-boyfriend|ex-girlfriend|lover)"
_INLAW = r"(?:in[ -]?laws?|mil|fil|(?:mother|father|brother|sister)[ -]in[ -]law|saas|sasur\w*)"
_FAMILY = (r"(?:mother|father|mom|mum|dad|parents?|brother|sister|bro|sis|uncle|aunt|aunty|cousin|grandma|grandpa|grandmother|grandfather|"
           r"family|relatives?|step-?(?:mother|father|dad|mom))")
_ACTOR_RX = _c(rf"\b(?:he|she|they|{_PARTNER}|{_INLAW}|{_FAMILY})\b")
_CLOSE_RX = _c(rf"\b(?:he|she|they|{_PARTNER}|{_INLAW})\b")    # for control and verbal abuse: not a parent's ordinary strictness
_PARTNER_RX = _c(rf"\b(?:{_PARTNER}|{_INLAW})\b")
_PRONOUN_RX = _c(r"\b(?:he|she|they)\b")
_BOUND = _c(r"\b(?:when|because|while|as|after|before|since|if|that|though|although|which|where|whereas|but|so)\b")
_ELIDED = _c(r"(?:\s|and|then|also|just|again|even|once|often|always|sometimes|already|suddenly|yesterday|today|tonight|last night|"
                     r"he|she|they)*$")
_HIST_ACTOR = _c(rf"\b(?:{_PARTNER}|{_INLAW}|pati|patni|biwi|saas|sasur|sasural|husband|wife)\b|पति|पत्नी|बीवी|ससुराल|सास|ससुर")

_BODY = (r"(?:face|head|arms?|hands?|legs?|back|stomach|belly|body|chest|ribs?|cheeks?|mouth|lips?|nose|eyes?|ears?|neck|throat|hair|"
         r"shoulders?|wrists?|jaw|thighs?|side|fingers?)")
_ME = rf"(?:me|my\s+{_BODY})"

# ---- Hinglish and Hindi building blocks
_ME_HI = r"(?:mujhe|mujhko|muje|mjhe|mereko|mereku|meko|mujh\s*(?:pe|par|per)|mujhpe|mujhpar|mere\s+(?:upar|oopar|upr|saath|sath|sath))"
_REL_HI = (r"(?:pati|husband|hubby|biwi|wife|patni|bf|boyfriend|gf|girlfriend|saas|sasur|sasural|sasuralwale|devar|jeth|jethani|nanad|bhai|papa|"
           r"pitaji|pita\s+ji|baap|maa|mummy|mother|father|mama|chacha|taau|fufa|jija|jiju|ghar\s*wale|ghar\s*walon|ghar\s*walo|family)")
_HI_HIT = (r"(?:maar(?:ta|ti|te)|mar(?:ta|ti|te)|peett(?:a|i)|peet-?t(?:a|i|e)|pitt(?:a|i)|pit(?:ta|ti|te)|pitai|peetai|marpeet|maarpeet|maar[- ]peet|"
           r"maar\s+(?:de|diya|di|deta|deti|dete)\b(?!\s+dal)|maara|maari|mara|mari|maarne\s+lag\w*)")
_ESC_HI_VERB = r"(?:maar(?:ta|ti|te)|mar(?:ta|ti|te)|pitt(?:a|i)|pit(?:ta|ti|te)|pitai|peetai|peet-?t(?:a|i|e)|haath\s+uth\w*|hath\s+uth\w*)"

_ME_DV = r"(?:मुझे|मुझको|मुझ\s*(?:पर|पे)|मेरे\s+(?:ऊपर|साथ))"
_REL_DV = (r"(?:पति|पत्नी|बीवी|ससुर|सास|ननद|देवर|जेठ|जेठानी|ससुराल(?:\s*वाले)?|भाई|पापा|पिताजी|पिता|माँ|मां|मम्मी|बॉयफ्रेंड|गर्लफ्रेंड|"
           r"बीएफ|जीएफ|घर\s*वाले|घरवाले|चाचा|मामा|फूफा|जीजा|परिवार)")
_DV_HIT = r"(?:मार(?:ता|ती|ते)|मारा|मारी|पीट(?:ता|ती|ते)|पीट\s+(?:दिया|दी|देता|देती|देते)|पीटा|पीटी|पिटाई|थप्पड़|थप्पड|तमाचा|झापड़|लात|घूंसा|घूँसा|मुक्का|धक्का|हाथ\s*(?:भी\s*)?(?:उठा|चला)\w*)"


# --------------------------------------------------------------------------
# Hedges: is this mention live, or negated / hypothetical / past and over / play / quoted
# --------------------------------------------------------------------------

_NEG_BEFORE = _c(
    r"\b(?:never|not|(?:do|does|did|would|will|can|could|has|have|had|is|are|was|were)n'?t|wont|nobody|no\s+one|nahi|nahin|nhi)\b"
    r"(?:\s+\w+)?\s*$|(?:नहीं|कभी\s+नहीं)(?:\s+\S+)?\s*$")
_NEG_EXC = _c(r"\b(?:not\s+only|not\s+just|never\s+stop\w*|(?:doesn'?t|don'?t|won'?t)\s+stop|no\s+matter)\b")
_NEG_AFTER = _c(r"^\s*(?:nahi|nahin|nhi)\b|^\s*नहीं")
_NEG_BUT = _c(r"\bbut\b[^.!?]*\b(?:did|does|do|has|have|started|now|today|last|yesterday)\b|\blekin\b[^.!?]*\b(?:kiya|karta|ab|kal|aaj)\b")

_PLAIN_HYPO = _c(
    r"\bwhat\s+if\b|\bsuppose\b|\bimagine\b|\bpretend\b|\bhypothetically\b|\bin\s+case\b|\bwould\s+you\b"
    r"|\bif\b(?=[^.!?]{0,60}\b(?:ever|were|had|would)\b)"
    r"|\bif\b(?=.{0,80}\b(?:i\s+would|i'?d|i'?ll|i\s+will|i\s+can|i\s+could|i\s+should|i\s+might|i\s+shall|we\s+would|we'?ll)\b)"
    r"|\b(?:agar|agr|maan\s+lo|man\s+lo|socho|kya\s+hoga\s+agar)\b|अगर|यदि|मान\s*लो|सोचो")
_ASK_HYPO = _c(
    r"\b(?:what|how)\s+(?:should|do|can|could|would|to|will)\b[^.!?]{0,40}\bif\b|\bwhat\s+to\s+do\s+if\b"
    r"|\bkya\s+(?:karun|karu|karein|karoon)\s+agar\b|\bagar\b.{0,60}\bkya\s+(?:karun|karu|karein|karoon)\b")
_AGAIN = _c(r"\b(?:again|already|before|once\s+more|dobara|dubara|phir\s+se|fir\s+se|pehle\s+bhi)\b|दोबारा|फिर\s+से|पहले\s+भी")
_INDICATIVE_AFTER = _c(r"^\s*(?:hai|h|he|hain|tha|thi|the)\b|^\s*(?:है|हैं|था|थी|थे)")
_SAY_THREAT = _c(
    r"\b(?:said|says|saying|told|tells|threaten\w*|warn\w*|swore|keeps?\s+saying|bola|bolta|kaha|kehta|dhamki|dhamka\w*|chillata)\b|कहा|बोला|धमकी")

_PAST = _c(
    r"\b(?:used\s+to|use\s+to|stopped\s+(?:hitting|beating|slapping|abusing|hurting|that|doing\s+that)|(?:he|she|they)\s+has\s+stopped|has\s+stopped\s+(?:now|since)|"
    r"not\s+anymore|not\s+any\s+more|no\s+longer|years?\s+ago|long\s+ago|a\s+long\s+time\s+ago"
    r"|in\s+the\s+past|back\s+then|when\s+(?:i|we)\s+(?:were|was)\s+(?:a\s+)?(?:kids?|child|children|little|young|small|teen\w*|in\s+(?:school|class))|as\s+a\s+(?:kid|child)|childhood|growing\s+up"
    r"|we(?:'re|\s+are)\s+(?:good|fine|okay|ok|better|happy)\s+now|(?:all|everything\s+is)\s+(?:good|fine|okay|sorted)\s+now|it'?s\s+over|that'?s\s+over"
    r"|thing\s+of\s+the\s+past|ab\s+nahi|ab\s+nahin|ab\s+nhi|ab\s+bilkul\s+nahi|bachpan|saalon\s+pehle"
    r"|purani\s+baat|(?:maar|peet|pit|mar)(?:ta|ti|te)\s+(?:tha|thi|the))\b"
    r"|अब\s+नहीं|बचपन|साल\s+पहले|(?:मारता|मारती|मारते|पीटता|पीटती|पीटते)\s+(?:था|थी|थे)")
_PAST_NEXT = _c(r"^(?:but\s+)?(?:now\s+)?(?:(?:he|she|they|it)\s+)?(?:has\s+)?(?:stopped|doesn'?t\s+anymore|no\s+longer|not\s+anymore|never\s+again)\b|^ab\s+nahi")
_RECENT = _c(
    r"\b(?:yesterday|last\s+night|last\s+week|today|tonight|this\s+morning|this\s+week|just\s+now|days?\s+ago|hours?\s+ago|recently|right\s+now|"
    r"currently|kal|aaj|abhi|raat\s+ko|still|even\s+now|again|continues?|keeps?|every\s+day|daily|abhi\s+bhi|ab\s+bhi)\b|कल|आज|अभी|रात|अब\s+भी|फिर\s+भी")

# A video game, sparring or training, and a push that "we laughed" about are play. Game names are listed so "he beat me in Mortal Kombat" is not a beating.
_VIDEO_GAMES = (r"mortal\s+kombat|tekken|street\s+fighter|call\s+of\s+duty|fortnite|minecraft|valorant|overwatch|dota|league\s+of\s+legends|smash\s+bros|"
                r"mario\s*kart|counter[- ]?strike|free\s*fire|bgmi|pubg|roblox|among\s+us|gta|wwe|ufc|combos?|boss\s+fights?|controller|respawn\w*|noobs?|"
                r"gaming|gamer|play\s*station|ps[45]|xbox|fifa|nba\s*2k|apex\s+legends")
_SPARRING = (r"spar|spars|sparred|sparring|training\s+(?:today|session|class|partner|camp|ring|round)|(?:in|at|during|after|before)\s+training|"
             r"boxing\s+(?:class|practice|session)|martial\s+arts|dojo|bjj|jiu[- ]?jitsu|kick\s*boxing|self[- ]defen[cs]e\s+class|judo|karate|taekwondo|aikido|on\s+the\s+mat|"
             r"(?:gym|dance|yoga|judo|karate|wrestling)\s+(?:class|practice|session|lesson)")
_PLAY = _c(
    r"\b(?:playful(?:ly)?|jokingly|joking|as\s+a\s+joke|just\s+kidding|kidding|mazaak\s+mein|mazak\s+mein|masti\s+mein|pillows?|lol|haha+|lmao|tickl\w+|"
    r"pranks?|teasing(?:ly)?|cutely|cute\s+(?:slap|hit)|love\s+tap|fun\s+fight|pillow\s+fight|play\s+fight|playing|funny|jk|"
    r"(?:we|both\s+of\s+us|everyone|all\s+of\s+us)\s+(?:both\s+)?(?:laughed|laughing|giggled|cracked\s+up)|we\s+were\s+(?:all\s+)?laughing|(?:screamed|squealed|shrieked)\s+with\s+laughter|wrestl(?:ed|ing)\s+(?:for|over)|"
    r"race\s+kar\w*|hum\s+hans|hans\s+(?:pade|padi|diye)|hasne\s+lage|khelte\s+(?:hue|waqt)|khel\s+rah[eia]|i\s+teased\s+(?:her|him|them)|when\s+i\s+teased|in\s+play|(?:and|then)\s+giggled|"
    + _VIDEO_GAMES + "|" + _SPARRING + r")\b|मज़ाक\s+में|मजाक\s+में|मस्ती\s+में|हम\s+(?:दोनों\s+)?(?:हँस|हंस)\w*|(?:हँसने|हंसने)\s+लगे|खेल\s+रहे")
_PLAY_BLOCK = _c(
    r"\b(?:hurt\w*|pain\w*|bleed\w*|bruis\w*|swoll\w*|swell\w*|injur\w*|cr(?:y|ied|ying)|scared|afraid|fear\w*|angry|anger|furious|rage|gussa|gusse|dard|chot|khoon|"
    r"dar|darr|dara|nila|blood|broke|broken|fracture\w*|stitch\w*|doctor|hospital)\b|सूज|चोट|दर्द|डर|गुस्स|खून")
_ACCIDENT = _c(r"\b(?:accident\w*|by\s+mistake|unintentionally|didn'?t\s+mean\s+to|galti\s+se|ghalti\s+se|anjaane\s+mein)\b|गलती\s+से|अनजाने")

_ESC_WORDS = _c(
    r"\b(?:every\s+(?:(?:single|other|damn|blessed|bloody)\s+)?(?:day|night|week|weekend|month|morning|evening|time|other\s+day)|each\s+and\s+every\s+(?:single\s+)?(?:day|night|time)|"
    r"(?:day|night|week)\s+after\s+(?:day|night|week)|everyday|each\s+day|daily|all\s+the\s+time|most\s+days|again\s+and\s+again|over\s+and\s+over|"
    r"keeps?\s+(?:on\s+)?(?:hitting|beating|slapping|hurting|doing|choking|kicking)|again|once\s+more|another\s+time|multiple\s+times|several\s+times|many\s+times|"
    r"a\s+lot\s+of\s+times|repeatedly|regularly|often|always|constantly|frequently|sometimes|from\s+time\s+to\s+time|once\s+in\s+a\s+while|at\s+times|twice|thrice|"
    r"whenever\s+(?:he|she|they)|when\s+(?:he|she)\s+(?:drinks|is\s+drunk|gets\s+angry)|gets?\s+drunk\s+and|when\s+drunk|"
    r"for\s+(?:\d+\s+|several\s+|many\s+|a\s+few\s+)?(?:days|weeks|months|years)|(?:been|has\s+been|have\s+been)\s+(?:hitting|beating|slapping|abusing|hurting)|started\s+(?:hitting|beating|slapping|abusing)|"
    r"mahino\s+se|saalon\s+se|kab\s+se|nashe\s+mein|"
    r"(?:phir|fir)\s+(?:\w+\s+)?(?:maar|mara|maara|peet|pit|thapp?ad|dhakka|laat)\w*|roz|rozana|roj|har\s+(?:roz|din|raat|baar|hafte)|hamesha|aksar|kabhi\s*-?\s*kabhi|baar\s*-?\s*baar|bar\s+bar|lagataar|lagatar|phir\s+se|fir\s+se|dobara|dubara|"
    r"aaye\s+din|aye\s+din|kai\s+baar|do\s+baar|teen\s+baar|bahut\s+baar|pehle\s+bhi)\b"
    r"|फिर\s+\S*(?:मार|पीट|थप्पड़|लात|धक्का)|रोज़|रोज|हर\s+(?:दिन|रात|बार|हफ्ते)|हमेशा|अक्सर|कभी\s*-?\s*कभी|बार\s*-?\s*बार|लगातार|फिर\s+से|दोबारा|कई\s+बार|दो\s+बार")
_ESC_STRONG = _c(
    r"\b(?:getting\s+worse|gets\s+worse|got\s+worse|worse\s+and\s+worse|worse\s+every|worsening|more\s+and\s+more|more\s+often|more\s+frequent\w*|escalat\w+|"
    r"badh\s+raha|badhta\s+ja\w*|zyada\s+ho\s+(?:gaya|raha)|zyada\s+hone\s+laga|badtar)\b|बढ़\s+(?:रहा|गया)|बढ़ता\s+जा")
_PREGNANT = _c(
    r"\b(?:i\s*(?:am|'m|was)\s+(?:\w+\s+)?(?:pregnant|expecting)|i\s+(?:think\s+)?(?:might|may|could|must)\s+be\s+(?:\w+\s+)?pregnant|i\s+think\s+(?:i\s*am|i'?m)\s+pregnant|"
    r"missed\s+my\s+period|my\s+period\s+is\s+late|pregnant\s+(?:and|with)|my\s+pregnancy|while\s+i'?m\s+pregnant|while\s+pregnant|"
    r"main\s+pregnant|mai\s+pregnant|mujhe\s+pregnancy|pregnancy\s+mein|pregnant\s+hoon|pregnant\s+hu|garbhvati|garbh\s+mein)\b|गर्भवती|प्रेग्नेंट|गर्भ\s+में")
_FEAR_CUE = _c(
    r"\b(?:i\s*(?:am|'m|im)\s+(?:so\s+|very\s+|really\s+|too\s+)?(?:scared|afraid|terrified|frightened)|(?:i\s+)?feel\s+(?:so\s+)?(?:unsafe|scared|afraid)|"
    r"(?:mujhe\s+)?(?:bahut\s+)?(?:darr|dar)\s+(?:lag|hua|hui|raha|rahi)\w*|main\s+(?:bahut\s+)?(?:dari|dara)\s+(?:hui|hua|hoon|hu)|(?:darr?|dar)\s+(?:gayi|gaya|gai|gaye|hai)|dar(?:r\s*)?(?:ta|ti)\s+(?:hoon|hu|hun)|safe\s+nahi)\b|डर\s+(?:लग|गया|गई)|डरी|डरा")
_INJURY = _c(r"\b(?:hurt\w*|pain\w*|bleed\w*|bruis\w*|swoll\w*|injur\w*|black\s+and\s+blue|up)\b")
_GAME = _c(
    r"\b(?:chess|ludo|carrom|cricket|football|game|games|match|race|quiz|tournament|competition|contest|exam|marks|score|monopoly|poker|cards|pubg|bgmi|fifa|"
    r"badminton|tennis|sudoku|video\s+game|playstation|xbox|bet|election|argument|debate|ranking|rank)\b")


@dataclass
class _Rule:
    family: str
    rx: re.Pattern[str]
    mode: str = "any"                 # any | actor | elide | weak | close | close_or_family | speaker | partner | pronoun (he / she / they right before)
    tail: re.Pattern[str] | None = None        # text right AFTER the match that makes it something else ("hit me up")
    need: re.Pattern[str] | None = None        # the sentence must also contain this
    block: re.Pattern[str] | None = None       # ...and must not contain this
    notpre: re.Pattern[str] | None = None      # the words right BEFORE the match that make the subject a thing or an animal ("the news hit me")
    play_ok: bool = False                       # play, an accident or a quote can excuse it (a slap in a game), never a threat or a weapon


_R: list[_Rule] = []


def _add(family: str, pattern: str, mode: str = "any", *, tail: str | None = None, need: str | None = None, block: str | None = None,
         play_ok: bool = False, notpre: str | None = None) -> None:
    _R.append(_Rule(family, _c(pattern), mode, _c(tail) if tail else None, _c(need) if need else None, _c(block) if block else None,
                    _c(notpre) if notpre else None, play_ok))


# ===== English: physical =====
# "the news hit me hard", "it hit me really hard", "his dog bit me": a thing or an animal is the subject, not a person. Used by the physical rules that
# take their actor from the words before them (mode elide / weak).
_NOT_A_PERSON = (r"\b(?:it|that|this|which|news|loss|death|passing|thought|thoughts|reality|truth|grief|realisation|realization|silence|story|words?|message|"
                 r"feeling|feelings|memories|memory|sadness|wave|fact|announcement|diagnosis|results?|email|text|call|moment|sight|smell|song|scene|"
                 r"dog|dogs|puppy|cat|kitten|snake|monkey|horse|bee|wasp|mosquito|spider|bull|cow|goat|parrot|rat|pet|animal|ball|wind|storm|wave|waves|crowd)"
                 r"(?:'s)?\s+(?:(?:also|really|just|suddenly|then|finally|so|even|always|still|actually|both)\s+)*$")
# A push, a drag or a grab that is plainly kind or ordinary ("grabbed my arm to stop me from falling", "pushed me out of my comfort zone", "dragged me along to the wedding").
# "grabbed my arm to stop me from leaving" is NOT in this list: that is someone holding a person back.
_KIND_PUSH = r"\b(?:comfort\s+zone|swing|towards?\s+(?:my\s+)?(?:goals?|dreams?|success))\b"
_KIND_TAIL = (r"^\s+(?:and\s+(?:pulled|moved|dragged|pushed)\s+me\s+(?:out\s+of\s+(?:the\s+)?way|away\s+from\s+(?:the\s+)?(?:road|traffic|car|bike|scooter|fire|edge|dog)|to\s+safety)\b|"
              r"to\s+(?:help|steady|guide|support|save|catch|cross|warn|wake)\b|to\s+stop\s+me\s+from\s+(?:falling|slipping|tripping|fainting|getting\s+hit|getting\s+run\s+over|being\s+hit|stepping\s+(?:onto|into|off|out)|"
              r"walking\s+(?:onto|into|off)|running\s+(?:onto|into|across)|crossing|touching\s+(?:the|a|that)\s+(?:stove|fire|flame|plug|wire|socket|heater))\b|"
              r"(?:along\s+|around\s+)?(?:to|for)\s+(?:the\s+|a\s+)?(?:wedding|party|mall|shopping|market|temple|picnic|concert|movie|festival|function|gym|hike|dance)\b)")
# a friendly slap on the back ("slapped my back and congratulated me")
_FRIENDLY_SLAP = (r"^(?=.*\b(?:slap\w*|pat\w*)\s+(?:my|me\s+on\s+the)\s+(?:back|shoulders?)\b)"
                  r"(?=.*\b(?:congratulat\w*|well\s+done|proud|good\s+job|cheer\w*|celebrat\w*|won|win|encourag\w*|laugh\w*|bro|buddy|friends?|happy|"
                  r"got\s+the\s+(?:job|promotion|offer|rank)|promotion|passed|selected|choked\s+on|coughing|cough\w*|hiccup\w*|burp\w*)\b)")
# a slap on the hand over food ("slapped my hand away when I tried to steal his fries")
_FOOD_HAND = (r"^(?=.*\b(?:slap\w*|smack\w*|whack\w*|swat\w*)\s+my\s+(?:hands?|fingers?)\s+(?:away|off)\b)"
              r"(?=.*\b(?:fries|fry|plate|snack|snacks|biscuits?|chips|samosas?|cake|dessert|pizza|burger|cookies?|chocolate|momos|popcorn|steal|stole|stealing|sneak\w*|snatch\w*)\b)")
_add("physical", rf"\b(?:slap|slaps|slapped|slapping|punch|punches|punched|punching|thrash|thrashes|thrashed|thrashing|batter|batters|battered|battering|"
                 rf"whack|whacks|whacked|smack|smacks|smacked|spank|spanks|spanked|bash|bashes|bashed|cuff|cuffs|cuffed|clout|clouts|clouted|thwack|thwacked|wallop|walloped|"
                 rf"bop|bopped)\s+{_ME}\b", "elide", play_ok=True, block=_FOOD_HAND + "|" + _FRIENDLY_SLAP + r"|\b(?:handcuff\w*|police|cop|cops|officer)\b", notpre=_NOT_A_PERSON,
     tail=r"^\s+(?:an?|the|one|another)\s+(?:\w+\s+)?(?:ticket|tickets|card|pass|stamp|receipt|bill|slip|token|number)\b")
_add("physical", rf"\b(?:kick|kicks|kicked|kicking|shove|shoves|shoved|shoving|bit|bites|biting|bitten)\s+{_ME}\b", "weak",
     tail=r"^\s+(?:out\b|(?:an?|another|some|the|his|her|my)\s+(?:\w+\s+)?(?:plate|bowl|glass|cup|drink|snack|menu|note|letter|pen|phone|book|paper|bag|box|gift|towel|spoon|fork|bottle|dish|"
          r"sandwich|slice|piece|text|message|look|smile|wink|hug|kiss|glance|pass|ball|cross|corner|penalty|ticket|card|stamp)\b)", play_ok=True,
     notpre=_NOT_A_PERSON)
_add("physical", rf"\bhit(?:s|ting)?\s+{_ME}\b", "elide", play_ok=True,
     tail=r"^\s+(?:up\b|back\b|baby\b|different\b|(?:really\s+|so\s+|very\s+|pretty\s+)?hard\s+(?:emotionally|mentally|deeply|inside|in\s+the\s+(?:heart|gut|feels)|with\s+(?:grief|sadness|emotion))\b|with\s+(?:a|an|the|some|such|your|his|her)\s+(?:\w+\s+){0,2}?(?:joke|pun|puns|pop\s+quiz|quiz|test|exam|assignment|homework|deadline|plot\s+twist|twist|drive|six|four|shot|serve|smash|pass|goal|boundary|yorker|bouncer|idea|question|text|message|line|truth|reality|news|song|vibe|"
          r"thought|realization|realisation|memory|wave|feeling|nostalgia|lyrics|surprise|compliment|offer|price|bill|fee|pickup|pick-up|rejection|answer|comeback|reply|fact)\b"
          r"|like\s+(?:a|an|the)\s+(?:truck|ton|brick|wave|train|bus|freight|bolt|lightning)|hard\s+when\s+i\s+)", notpre=_NOT_A_PERSON)
_add("physical", rf"\b(?:beat|beats|beating|beaten)\s+{_ME}\b", "elide", play_ok=True,
     tail=r"^\s+(?:at\b|to\s+(?!death)|by\s+(?:\w+\s+){0,2}(?:points?|runs?|goals?|wickets?|seconds?|minutes?|marks?|inches|lengths?)\b|by\s+\d|for\s+(?:the|a|first|top)\b|on\s+(?:points|time|score)\b|in\s+(?:the\s+)?(?:race|game|games|match|finals?|election|contest|"
          r"competition|exam|test|chess|ludo|carrom|cricket|football|quiz|debate|bet|marks|score|ranking|class|rank|points|sudoku|monopoly|poker|cards|pubg|fifa|badminton|"
          r"tennis|rankings|final|semis?|round|league|tournament)\b)",
     block=r"^(?!.*\b(?:hurt|bruis\w*|bleed\w*|blood|cry|cried|scared|afraid|injur\w*|black and blue|up|stick|belt|cane|rod|chappal|slipper|ladle|pipe|hose|wire|hanger)\b).*\b"
           r"(?:chess|ludo|carrom|cricket|football|game|games|match|race|"
           r"quiz|tournament|competition|contest|exam|marks|score|monopoly|poker|cards|pubg|fifa|badminton|tennis|sudoku|video game|playstation|xbox|bet|election|debate|"
           + _VIDEO_GAMES + r")\b", notpre=_NOT_A_PERSON)
_add("physical", r"\b(?:push|pushes|pushed|pushing)\s+me\s+(?:down|away|against|around|aside|over|onto|off|out|hard|roughly|into\s+the\s+(?:wall|door|table|floor|stairs|bed|"
                 r"ground|cupboard|almirah|car|corner)|to\s+the\s+(?:floor|ground|wall)|in\s+front|and\b|when\b|because\b|again\b|last\b|yesterday\b|today\b|twice\b|so\b|[,.!?]|$)",
     "weak", play_ok=True, block=_KIND_PUSH, tail=_KIND_TAIL, notpre=_NOT_A_PERSON)
_add("physical", rf"\b(?:push\w*|shov\w*|slam\w*|bang\w*|knock\w*|smash\w*)\s+my\s+(?:head|face|body|back)\s+(?:against|into|on)\b", "weak")
_add("physical", r"\b(?:drag|drags|dragged|dragging)\s+me\s+(?:by|across|down|along|around|out\s+of|on\s+the\s+(?:floor|ground|road)|to\s+the\s+(?:floor|ground|bedroom|bathroom|"
                 r"kitchen|bed|corner)|into\s+(?:the|a)\s+(?:bedroom|bathroom|kitchen|corner|store\s*room)|outside|inside|away)", "weak", block=_KIND_PUSH, tail=_KIND_TAIL)
_add("physical", rf"\b(?:pull|pulls|pulled|pulling|yank|yanks|yanked|grab|grabs|grabbed|grabbing|twist|twists|twisted|squeeze|squeezes|squeezed)\s+(?:me\s+by\s+(?:the|my)\s+|my\s+)"
                 rf"(?:hair|arms?|wrists?|ears?|face|jaw|shoulders?|collar|dupatta|clothes|sleeves?)\b", "weak", play_ok=True, block=_KIND_PUSH, tail=_KIND_TAIL)
_add("physical", r"\b(?:threw|throws|throw|thrown|throwing|hurled|flung|chucked)\s+(?:(?:a|an|the|his|her|their|some)\s+)?(?:\w+\s+){0,2}?(?:at|towards|toward)\s+me\b", "weak",
     block=r"\b(?:party|surprise|bone|curveball|look|glance|smile|wink|kiss)\b", play_ok=True)
_add("physical", r"\b(?:threw|throws|throwing|thrown|flung)\s+me\s+(?:down|against|across|onto|on\s+the\s+(?:floor|bed|ground)|to\s+the\s+(?:floor|ground)|off\s+the|into\s+the\s+wall)", "weak")
# "she burned me a CD", "burned me some toast", "work burned me out": something made for me or a tired person, not a burn
_BURN_TAIL = (r"^\s+(?:out\b|(?:an?|the|some|another|one|two|three|a\s+few|his|her|their|my)\s+(?:\w+\s+){0,2}?(?:cds?|dvds?|discs?|disks?|playlists?|copy|copies|"
              r"mixtapes?|mix|albums?|songs?|files?|movies?|films?|usb|pen\s*drives?|toast|bread|rotis?|chapatis?|parathas?|pizzas?|cookies?|cakes?|food|rice|dinner|lunch|"
              r"breakfast|coffee|tea|eggs?|omelettes?|sandwich\w*)\b)")
_add("physical", rf"\b(?:burn|burns|burned|burnt|burning|scald|scalds|scalded)\s+(?:me|my\s+(?:hands?|arms?|skin|back|face|legs?|body|chest|foot|feet))\b", "weak",
     tail=_BURN_TAIL, block=r"\b(?:cds?|dvds?|playlist|mixtape|usb)\b")
_add("physical", r"\b(?:cigarette|iron|hot\s+(?:water|oil|tea|milk))\s+(?:on|onto)\s+(?:me|my\s+\w+)\b", "weak")
_add("physical", r"\b(?:held|holds|holding|pinned|pins|pinning|pressed|presses)\s+me\s+(?:down|against|to\s+the\s+(?:wall|floor|bed)|by\s+(?:the|my))\b", "weak", play_ok=True)
_add("physical", r"\b(?:spat|spit|spits|spitting)\s+(?:on|at|in)\s+(?:me|my\s+face)\b", "weak")
_add("physical", r"\b(?:raised|raises|raising|lifted|lifts|lifting)\s+(?:his|her|their|a)\s+(?:hands?|fist|fists)\s+(?:at|on|against|to)\s+me\b", "weak")
_add("physical", r"\b(?:attack|attacks|attacked|attacking|assault|assaults|assaulted|jumped|jumps)\s+me\b", "weak",
     tail=r"^\s+(?:with\s+(?:\w+\s+)?(?:questions?|criticism|accusations?|advice|compliments?|memes?|jokes?|kisses|hugs?|love|affection|tickles|gifts?|words)\b|"
          r"at\s+the\s+(?:door|gate|station|airport|entrance)\s+with\s+(?:a\s+)?(?:hug|kiss|surprise)\b)",
     block=r"\b(?:hug\w*|cuddl\w*|tickl\w*|surprise\w*|excited|excitement|joy\w*|puppy|questions?|criticism|compliments?|memes?|jokes?)\b")
_add("physical", r"\bphysical(?:ly)?\s+(?:abus\w+|violen\w+|assault\w*|attack\w*|hurt\w*|harm\w*)", "any", need=r"\b(?:my|me|i|i'm|mine)\b")
_add("physical", r"\b(?:hurt|hurts|hurting|harm|harms|harmed|abuse|abuses|abused|assault|assaults|assaulted)\s+me\s+physically\b", "weak")
# "he hurts me when he is angry", "my husband hurt me yesterday": a person doing the hurting, with nothing that says it is about feelings
_add("physical", r"\b(?:hurt|hurts|hurting)\s+me\b", "weak", play_ok=True,
     block=r"\b(?:emotional\w*|feelings?|deeply|so\s+much|by\s+(?:saying|lying|cheating|ignoring|forgetting|leaving|not|being|making|telling|breaking|doing|talking)|words|lies|cheat\w*|betray\w*|"
           r"ignor\w*|forgot|forget\w*|ghost\w*|breakup|broke\s+up|sorry|apolog\w*|truth|honest\w*|trust|(?:it|that|which|this)\s+(?:hurt|hurts)|"
           r"(?:doesn'?t|don'?t|didn'?t|never|not|won'?t|wouldn'?t|can'?t|afraid\s+to|scared\s+to|tries\s+not\s+to|careful\s+not\s+to|want\s+to|wants\s+to)\s+(?:\w+\s+){0,3}hurt)\b")
_add("physical", r"\b(?:is|are|was|gets|got|became|becomes)\s+(?:very\s+|so\s+|extremely\s+|really\s+|too\s+)?violent\b", "any",
     need=rf"\bmy\s+(?:{_PARTNER}|{_INLAW}|{_FAMILY})\b")
_add("physical", r"\b(?:left|leaves|leaving|gave|gives|giving|caused|causes)\s+(?:me\s+)?(?:with\s+)?(?:a\s+|some\s+|many\s+|several\s+)?(?:bruises?|black\s+eyes?|"
                 r"cuts?|marks|injur\w+|scars?|burns?|swelling|welts?)\b", "weak")
_add("physical", r"\b(?:bruises?|black\s+eye|swollen|swelling|cuts?|bleeding|marks|injur\w+|broken\s+(?:arm|nose|rib|ribs|jaw|tooth|teeth|finger|wrist|leg))\b[^.!?]{0,40}"
                 rf"\b(?:from|because\s+of|caused\s+by|after)\s+(?:him|her|them|my\s+(?:{_PARTNER}|{_INLAW}|{_FAMILY}))\b", "any", play_ok=True)
# "I have bruises on my arms and my husband did it", "my husband did this to me, look at the bruises": the injury and who did it, no verb of hitting
_WHO_DID = rf"(?:my\s+(?:{_PARTNER}|{_INLAW}|{_FAMILY})|he|she|they)"
_INJ_WORDS = r"\b(?:bruis\w*|black\s+and\s+blue|black\s+eyes?|swollen|swelling|bleeding|injur\w+|welts?|burn\s+marks|(?:marks|cuts|burns|scars)\s+on\s+my)\b"
_NOT_AN_ATTACK = (r"\b(?:accident\w*|by\s+mistake|unintentionally|didn'?t\s+mean\s+to|fell|fall|gym|bike|sports?|football|cricket|trip\w*|slipp\w*|"
                  r"my\s+(?:cat|dog|puppy|kitten)|jersey|colou?r|favou?rite)\b")
_add("physical", rf"{_INJ_WORDS}[^.!?]{{0,60}}\b{_WHO_DID}\s+(?:did|caused)\s+(?:it|this|that|them|these)\b", "any", play_ok=True,
     tail=r"^\s+up\b", block=_NOT_AN_ATTACK)
_add("physical", rf"\b{_WHO_DID}\s+(?:did|caused)\s+(?:it|this|that|them|these)\s+to\s+me\b", "any", play_ok=True, need=_INJ_WORDS, block=_NOT_AN_ATTACK)
# "he punched the wall next to my face": a blow aimed past a person is a threat to hit, tier 2 like a hit
_add("physical", r"\b(?:punch\w*|hit|kick\w*|slam\w*|smash\w*|bang\w*)\s+(?:the\s+|a\s+)?(?:wall|door|table|glass|plate|cupboard|mirror)\s+"
                 r"(?:right\s+)?(?:next\s+to|near|beside|by|past|inches\s+from)\s+my\s+(?:face|head|ear)\b", "weak")
_add("physical", r"\b(?:threaten\w*|tries|tried|trying|wants|wanted)\s+to\s+(?:hit|beat|slap|punch|kick|hurt|harm)\s+me\b", "any")        # a threat to hit: tier 2 like a hit
_add("physical", r"\b(?:said|says|told\s+me|tells\s+me|warned\s+me|swore|promised)\b[^.!?]{0,25}?\b(?:he|she|they)(?:'ll|\s+will|\s+would|'d)\s+(?:hit|beat|slap|punch|kick|hurt|harm|break)\b",
     "speaker")
# --- no body part named: "gave me a slap", "put his hands on me", "whipped me with a belt", "got violent with me"
_add("physical", r"\b(?:gave|gives|giving|give|landed|lands|delivered|dealt)\s+me\s+(?:a|an|one|two|three|four|a\s+couple\s+of|a\s+few|several|some|many|a\s+lot\s+of)\s+"
                 r"(?:\w+\s+){0,2}?(?:slaps?|slapping|punch(?:es)?(?!\s*line)|smacks?|thrashing|beating|beatings|hiding|whipping|flogging|clouts?|blows?)\b", "elide", play_ok=True,
     tail=r"^\s+(?:on\s+the\s+(?:back|shoulder)|for\s+(?:winning|passing|scoring)|at\s+(?:the\s+)?(?:game|chess|ludo|carrom|cricket|quiz|match))\b")
_add("physical", r"\b(?:put|puts|putting|laid|lays|laying|lay|placed)\s+(?:(?:his|her|their|a|my)\s+)?(?:hands?|fingers?)\s+(?:on|upon)\s+me\b", "elide", play_ok=True)
_add("physical", r"\b(?:whip|whips|whipped|whipping|flog|flogs|flogged|flogging|lash|lashed|lashing|cane|caned|caning|belt|belted|belting)\s+me\b", "elide", play_ok=True,
     tail=r"^\s+(?:up\b|a\b|an\b|some\b|something\b|out\b)")
_add("physical", r"\b(?:got|gets|get|became|becomes|become|turned|turns|turn|getting|becoming|was|were|is|are)\s+(?:very\s+|so\s+|really\s+|extremely\s+|too\s+)?"
                 r"(?:violent|physical|rough|aggressive)\s+(?:with|towards?|to)\s+me\b", "elide", play_ok=True)
# --- everyday words for a beating: "beat the hell out of me", "roughed me up", "handles me roughly", "used a belt on me", "things get physical at home"
_add("physical", r"\b(?:beat|beats|beating|beaten|knock\w*|kick\w*|punch\w*|thrash\w*|pound\w*|smack\w*|whack\w*|slap\w*)\s+(?:the\s+)?(?:hell|crap|shit|daylights|living\s+daylights|"
                 r"stuffing|snot|life|bejesus|heck)\s+out\s+of\s+me\b", "elide", play_ok=True,
     tail=r"^\s+(?:at|in)\s+(?:the\s+)?(?:chess|ludo|carrom|cricket|football|game|games|match|quiz|race|exam|badminton|tennis|poker|cards|pubg|fifa)\b")
_add("physical", r"\b(?:roughed|roughs|roughing|manhandled|manhandles|manhandling)\s+me\b|\bhandl(?:e|es|ed|ing)\s+me\s+(?:roughly|rough|harshly|violently)\b", "elide", play_ok=True)
_add("physical", r"\b(?:used|uses|using)\s+(?:a|an|the|his|her|their|some)\s+(?:belt|stick|cane|rod|wire|cable|chappal|slipper|shoe|hanger|pipe|bat|ladle|belan|"
                 r"rolling\s+pin|lathi|danda|hose|whip|cord|broom)\s+(?:on|against)\s+me\b", "weak", play_ok=True)
_add("physical", r"\bthings\s+(?:get|gets|got|become|became|turn|turned|go)\s+(?:very\s+|really\s+|quite\s+)?physical\b", "any",
     need=rf"\b(?:{_PARTNER}|{_INLAW}|home|house|he|she|drunk|drinks|drinking|angry)\b",
     block=r"\b(?:game|match|gym|sports?|training|football|cricket|hockey|boxing|rugby|kabaddi|debate|date|dating|chemistry|bed|bedroom|romantic|kiss\w*|flirt\w*|party|club|dance|dancing|movie|film)\b")

# ===== English: strangulation, threat to kill, weapon, sexual, child =====
# A choke in a video game, a film or a judo / jiu-jitsu / wrestling bout is not an attack, unless the words also carry pain, fear, a threat or a partner.
_CHOKE_DANGER = (r"hurt|bruis\w*|bleed\w*|blood|cry|cried|crying|scared|afraid|terrified|injur\w*|black and blue|(?:can'?t|cannot|couldn'?t|could\s+not|unable\s+to)\s+breathe|breathing|gasp\w*|dizzy|faint\w*|kill\w*|threat\w*|drunk|angry|"
                 r"blacked\s+out|passed\s+out|unconscious")
_CHOKE_SPECIFIC = r"judo|bjj|jiu[- ]?jitsu|wrestling|wrestl\w+|mma|sparring|spar|dojo|tapped|tap\s+out|combo|" + _VIDEO_GAMES
# a named game or martial art blocks even beside a partner ("I played Tekken with my husband and he choked me out"); a vague word (game, match, film) does not
_SPORT_CHOKE = (rf"^(?!.*\b(?:{_CHOKE_DANGER}|husband|wife|boyfriend|girlfriend)\b).*\b(?:game|games|gaming|match|tournament|movie|film|{_CHOKE_SPECIFIC})\b|"
                rf"^(?!.*\b(?:{_CHOKE_DANGER})\b).*\b(?:{_CHOKE_SPECIFIC})\b")
_add("strangulation", r"\b(?:choke|chokes|choked|choking|strangle|strangles|strangled|strangling|throttle|throttles|throttled)\s+me\b", "elide", tail=r"^\s+up\b", block=_SPORT_CHOKE)
_add("strangulation", r"\b(?:his|her|their)\s+(?:hands?|fingers?|arms?|forearm|knee|foot|elbow)\s+(?:(?:were|was|are|is|had\s+been|have\s+been)\s+)?(?:around|on|at|round|across)\s+my\s+(?:neck|throat)\b", "any")
_add("strangulation", r"\b(?:grab|grabs|grabbed|grabbing|hold|holds|held|holding|squeeze|squeezes|squeezed|squeezing|press|presses|pressed|pressing|clamp|clamps|clamped)\s+"
                      r"(?:me\s+by\s+the|my)\s+(?:neck|throat)\b", "weak")
_add("strangulation", r"\b(?:cut|cuts|cutting)\s+(?:off\s+)?my\s+(?:air|breath|breathing|air\s+supply|oxygen)\b", "elide")
# "tried to suffocate me with a pillow" (not "this room is suffocating me", not "smothered me with love")
_add("strangulation", r"\b(?:suffocat\w+|smother\w*)\s+me\s+with\s+(?:a|an|the|his|her|their)\s+(?:pillow|cushion|hand|hands|cloth|bag|towel|plastic|blanket)\b", "elide")
_add("strangulation", r"\b(?:suffocate|suffocated|suffocates|smother|smothered|smothers)\s+me\b", "elide",
     tail=r"^\s+with\s+(?:love|kisses|hugs|attention|affection|care|gifts|questions|rules)\b")
_add("strangulation", r"\b(?:can'?t|couldn'?t|cannot|could\s+not|unable\s+to|struggled\s+to)\s+breathe\s+(?:because|when|as|while|since)\s+(?:he|she|they|my\s+\w+)\b", "any")
_add("strangulation", r"\b(?:pillow|hand|cloth|bag|plastic|towel)\s+over\s+my\s+(?:face|mouth|nose)\b", "weak")
# "he presses a pillow on my face", "he sits on my chest": a weight or a cover on the breathing
_add("strangulation", r"\b(?:press\w*|hold\w*|held|put|puts|placed?|places|push\w*|shov\w*)\s+(?:a|an|the|his|her|their)\s+(?:pillow|cushion|hand|cloth|bag|plastic|towel|blanket)\s+"
                      r"(?:over|on|against|onto|across)\s+my\s+(?:face|mouth|nose)\b|\b(?:sits?|sat|sitting|kneels?|knelt|kneeling)\s+on\s+my\s+(?:chest|neck|throat)\b", "weak")
_kill_obj = r"(?:me|us|you|the\s+kids|my\s+(?:family|parents|mother|father|mom|dad|child|children|kids|baby|life))"
_add("threat_kill", rf"\b(?:said|says|saying|told\s+me|tells\s+me|telling\s+me|threaten\w*(?:\s+me)?|warn\w*(?:\s+me)?|swore|swears|promised|promises|keeps?\s+saying|kept\s+saying|"
                    rf"keeps?\s+telling\s+me|kept\s+telling\s+me|screamed|yelled|shouted|texted|messaged|wrote|vowed)\b[^.!?]{{0,40}}?\b(?:kill|murder|finish|end|get\s+rid\s+of)\s+{_kill_obj}\b",
     "speaker")
_add("threat_kill", r"\bthreaten\w*\s+to\s+(?:kill|murder)\b", "any")
_add("threat_kill", r"\b(?:death\s+threats?|threaten\w*\s+my\s+life|threats?\s+to\s+(?:my|our)\s+life)\b", "any")
_add("threat_kill", r"\b(?:wants?|wanted|trying|tries|tried|attempt\w*|plans|planning|planned)\s+to\s+(?:kill|murder)\s+me\b", "actor")
_add("threat_kill", r"\b(?:threaten\w*|said|says|told\s+me|warn\w*)\b[^.!?]{0,30}?\b(?:burn\s+me|set\s+me\s+on\s+fire|throw\s+acid|burn\s+me\s+alive)\b", "speaker")
# "he nearly killed me": an act that almost ended in death. Idioms about food, work, a scare or a joke are not it.
_add("threat_kill", r"\b(?:nearly|almost|very\s+nearly|just\s+about)\s+(?:killed|murdered|strangled|choked)\s+me\b", "elide", play_ok=True,
     block=r"\b(?:lol|haha+|lmao|jokes?|laugh\w*|cook\w*|food|spicy|spice|chill?i|scar\w+|prank\w*|workout|gym|exam|homework|marks|surprise\w*|driving|drove|speed|car|bike|"
           r"ride|rode|funny|danc\w+|song|movie|story|stories|heart\s+attack|tickl\w+|fright\w*|presentation|deadline|work|job|boss|meeting|traffic|stairs|run|running)\b")
_add("threat_kill", r"\b(?:poured|pours|pouring)\s+(?:kerosene|petrol|diesel|acid)\s+(?:on|over)\s+me\b|\bset\s+me\s+on\s+fire\b|\bthrew\s+acid\b", "any")
_add("kill_maybe", r"\b(?:will|would|'ll|is\s+going\s+to|'s\s+going\s+to|gonna|am\s+going\s+to|are\s+going\s+to)\s+kill\s+me\b", "partner",
     block=r"\b(?:lol|haha+|lmao|jk|literally|omg|dead|lool|late|forget|forgot|forgets|miss|missed|break|broke|lose|lost|spend|spent|buy|bought|eat|ate|skip|skipped|"
           r"anniversary|birthday|dinner|cook|burn|burnt)\b")
# "he is going to kill me tonight", "he is coming to kill me", "I'm afraid he will kill me": a plain he / she / they is enough when the words say it is
# about to happen. "my mom will kill me" and "he will kill me for being late" stay what they are (a figure of speech), same word list as above.
_IDIOM_KILL = (r"\b(?:lol|haha+|lmao|jk|literally|omg|dead|lool|late|forget|forgot|forgets|miss|missed|break|broke|lose|lost|spend|spent|buy|bought|eat|ate|skip|skipped|"
               r"anniversary|birthday|dinner|cook|burn|burnt|bill|exam|marks|result|grades?|phone|screen|vase|plate|glass|dish|dishes|crash|dent|scratch|find\w*\s+out|"
               r"found\s+out|knew|knows|sees|saw|for\s+(?:losing|forgetting|breaking|burning|missing|spending|buying|eating|skipping|wasting|ruining|spilling|using|wearing|"
               r"borrowing|failing|being\s+late|coming\s+late|getting\s+late)|spill\w*|ruin\w*|wreck\w*|damage\w*|workload|deadline\w*|work|job|boss|meeting|presentation|homework|assignment|project|"
               r"schedule|traffic|heat|spicy|jokes?|laugh\w*|hilarious|funny|cringe|embarrass\w*|movie|film|song|story|stories|show|series|game|match|fight\s+scene)\b")
_add("threat_kill", r"\b(?:is|are|was|'s)\s+(?:going\s+to|gonna|about\s+to|coming\s+to|come\s+to|trying\s+to|planning\s+to|out\s+to|here\s+to)\s+(?:kill|murder|finish)\s+(?:me|us)\b|"
                    r"\b(?:will|'ll|shall)\s+(?:kill|murder)\s+me\b|\bgonna\s+(?:kill|murder)\s+me\b|\b(?:came|comes|coming|come)\s+to\s+kill\s+me\b|"
     r"\bon\s+(?:his|her|their)\s+way\s+to\s+(?:kill|murder|hurt)\s+me\b",
     "pronoun", block=_IDIOM_KILL)
# a threat to hurt: gentle tier 2 like a hit, and tier 3 with fear ("I am scared he will hurt me tonight")
_GAMEY_WORDS = (r"\b(?:lol|haha+|lmao|jk|jokes?|chess|ludo|carrom|cricket|football|game|games|match|race|quiz|exam|marks|score|poker|cards|pubg|badminton|tennis|debate|"
                r"truth|honesty|feelings|pride|ego|reputation|career|heart|emotionally|financially|socially)\b")
_add("physical", r"\b(?:is|are|'s)\s+(?:going\s+to|gonna|about\s+to|planning\s+to)\s+(?:hit|beat|slap|punch|kick|hurt|harm|strangle|choke)\s+me\b|"
                 r"\b(?:will|'ll)\s+(?:hit|beat|slap|punch|kick|hurt|harm|strangle|choke)\s+me\b", "pronoun", play_ok=True, block=_GAMEY_WORDS)
_add("threat_kill", r"\bwants?\s+me\s+dead\b", "pronoun")
# the same words about a named partner stay a figure of speech (tier 1) unless the sentence also says it is happening or frightening
_add("threat_kill", r"\b(?:will|would|'ll|is\s+going\s+to|'s\s+going\s+to|gonna|am\s+going\s+to|are\s+going\s+to)\s+kill\s+me\b", "partner",
     need=r"\b(?:tonight|right\s+now|today|this\s+(?:evening|night)|now|drunk|knife|coming|door|outside|really|means?\s+it|meant\s+it|threat\w*|scared|afraid|terrified|serious\w*)\b",
     block=_IDIOM_KILL)
_add("threat_kill", r"\bkill\w*\s+(?:himself|herself|themselves)\s+(?:and|&|n|along\s+with|as\s+well\s+as|plus|then)\s+(?:me|us|the\s+kids|my\s+kids)\b|\bmurder[\s-]*suicide\b", "any")
_weapon = (r"(?:knife|knives|gun|pistol|revolver|rod|iron\s+rod|axe|hatchet|machete|cleaver|blade|razor|acid|sword|hammer|rifle|chaku|chakku|bandook|danda|"
           r"talwar|kulhadi|sariya|lathi|hockey\s+stick|cricket\s+bat|baseball\s+bat|crowbar|iron\s+pipe)(?!-(?:shaped|like|type|print|themed|toy|cake))")
# A weapon in a hand is a danger only with danger beside it ("pulled a knife on me", "grabbed a knife and chased me"); "picked up a knife and cut the cake" is not.
_DANGER_NEAR = (r"\b(?:(?:at|on|towards?|against|after)\s+(?:me|my|us)|threat\w*|kill\w*|scared|afraid|terrified|frightened|help|attack\w*|chas\w+|hid(?:e|ing)|"
                r"drunk|furious|angry|locked|hurt|stab\w*|came\s+at|comes\s+at|darr\w*|dara\w*)\b")
_WEAPON_BENIGN = (r"\b(?:cook\w*|chef|kitchen|vegetables?|onions?|fruits?|cake|bread|toy|movie|film|game|shop|store|collection|museum|display|sharpen\w*|repair\w*|fix\w*|"
                  r"plumber|carpenter|slice|slices|tomato\w*|apple|mango|birthday|party|prank|joke|lol|haha+)\b")
# "stabbed me in the back by telling my boss", "shot me a text": a figure of speech, not a weapon
_FIGURATIVE_STAB = (r"\b(?:in\s+the\s+back\s+(?:by|when|with|while|after|because|for)|behind\s+my\s+back|dirty\s+look|lol|haha+|jk|text|message|email|dm|whatsapp|photo|video)\b")
# "he is at the door with a knife, please help me", "he has locked me in and has a knife": a weapon in his hand while the words say danger is close
_add("weapon", rf"\b(?:with|has|have|had|holding|got|carrying|grabbed|took|taking)\s+(?:a|an|the|his|her|their|my)\s+(?:\w+\s+){{0,2}}?{_weapon}\b", "close",
     need=r"\b(?:door|outside|inside|locked|help|scared|afraid|terrified|coming|threat\w*|drunk|angry|furious|attack\w*|kill\w*|hide|hiding|room|following|chasing|window|gate|"
          r"shout\w*|scream\w*|yell\w*|rag\w*)\b",
     block=r"\b(?:cook\w*|chef|kitchen|vegetable\w*|onion\w*|fruit\w*|cake|bread|toy|movie|film|game|shop|store|collection|museum|display|sharpen\w*|repair\w*|fix\w*|plumber|carpenter)\b")
# a person breaking in: he / she / they (or a partner or in-law) is forcing the door, window or lock
_add("imminent", r"\b(?:breaking|breaks|smashing|smashes|kicking|kicks|banging|bangs|pounding|pounds|forcing|forces|hammering|hammers)\s+(?:down\s+|in\s+|open\s+|on\s+|at\s+)?(?:the\s+|my\s+|our\s+)?"
                 r"(?:door|gate|window|lock)\b|\bbreaking\s+in(?:to\s+(?:my|the|our)\s+(?:room|house|home|flat))?\b|\bbroke\s+into\s+(?:my|the|our)\s+(?:room|house|home|flat)\b|"
                 r"\btrying\s+to\s+(?:break|force)\s+(?:in|into|down|open|through)\b|\btrying\s+to\s+(?:break|force)\s+(?:the|my|our)\s+(?:door|lock|window|gate)\b", "close",
     block=r"\b(?:plumber|carpenter|workers?|movers?|landlord|repair\w*|renovat\w*|construction|neighbou?rs?|kid|kids|baby|toddler|dog|cat|wind|storm|movie|film|game|video|scene|show|"
           r"police|firefighters?|fire\s*brigade|ambulance|paramedics?|new\s+shoes|these\s+shoes)\b")
# "someone is trying to break down my door and I am alone": a stranger at the door counts when the words also say the person is alone, afraid or asking for help
_add("imminent", r"\b(?:someone|somebody|a\s+man|men|people|strangers?|intruders?|burglars?|robbers?|unknown\s+(?:man|men|people))\s+(?:is\s+|are\s+|was\s+|keeps?\s+)?(?:trying\s+to\s+)?"
                 r"(?:break\w*|forc\w*|smash\w*|kick\w*|bang\w*|pound\w*)\s+(?:down\s+|in\s+|open\s+|on\s+|at\s+)?(?:the\s+|my\s+|our\s+)?(?:door|gate|window|lock)\b", "any",
     need=r"\b(?:alone|scared|afraid|help|hiding|police|please|terrified|frightened|nobody|no\s+one)\b",
     block=r"\b(?:plumber|carpenter|workers?|movers?|landlord|repair\w*|renovat\w*|construction|neighbou?rs?|kid|kids|baby|toddler|dog|cat|wind|storm|movie|film|game|video|scene|show|"
           r"police\s+(?:are|is)|firefighters?|fire\s*brigade|ambulance|paramedics?|delivery|courier)\b")
_add("imminent", r"\b(?:darwaz[ae]|darwaja|gate|khidki)\s+(?:ko\s+)?(?:\w+\s+){0,2}?(?:tod|toda|todta|todti|todte|todne|peet|peeta|pit|pitta|thok|thokta|pakad|khatkhata)\w*",
     "any", need=r"\b(?:wo|woh|vo|pati|husband|usne|bf|boyfriend|saas|sasur|sasural|jeth|devar|bhai|papa|log)\b",
     block=r"\b(?:plumber|carpenter|mistri|kaam|marammat|repair|renovat\w*|police|pulis|kutta|kutte|bacha|bachche)\b")
# "wo bahar khada hai chaku ke saath": a weapon with him while he is at the door, outside or angry (not "chaku ke saath sabzi kaat rahi hoon")
_add("weapon", r"\b(?:chaku|chakku|chaaku|bandook|bandhook|danda|lathi|talwar|kulhadi|pistol|revolver|gun|knife|rod|sariya|hathoda|hammer)\s+ke\s+(?:saath|sath)\b", "any",
     need=r"\b(?:wo|woh|vo|pati|husband|usne|unhone|bf|boyfriend|saas|sasur|devar|jeth|bhai)\b",
     block=r"\b(?:sabzi|sabji|khana|pyaz|phal|kaat\w*|banat\w*|pakat\w*|rasoi|kitchen|dukaan|cake)\b")
_add("weapon", r"(?:चाकू|बंदूक|डंडा|डंडे|तलवार|कुल्हाड़ी|छुरी|लाठी|पिस्तौल|हथौड़ा|हथौड़े|सरिया|सरिये)\s+के\s+साथ", "any", need=r"वो|वह|पति|उसने|उन्होंने|भाई|पापा|ससुर|देवर|जेठ|बॉयफ्रेंड",
     block=r"सब्ज़ी|सब्जी|फल|काट|केक|प्याज|पकाने|खाना|रसोई")
_add("imminent", r"(?:दरवाज़ा|दरवाजा|दरवाज़े|दरवाजे|गेट|खिड़की)\s+(?:को\s+)?(?:\S+\s+){0,2}?(?:तोड़|पीट|ठोक|धक्का)\S*", "any",
     need=r"वो|वह|पति|उसने|उन्होंने|भाई|पापा|ससुर|देवर|जेठ|बॉयफ्रेंड|मेरा", block=r"प्लंबर|कारपेंटर|मिस्त्री|मरम्मत|पुलिस|कुत्ता|बच्चा")
_add("weapon", rf"\b(?:pull|pulls|pulled|point|points|pointed|hold|holds|held|wave|waves|waved|show|shows|showed|brandish\w*|took\s+out|takes\s+out|grabbed|grabs|"
               rf"picked\s+up|picks\s+up|came\s+at|comes\s+at|chased|chases|threatened|threatens|threatening|attack\w*|stab\w*|cut|cuts|shot|shoots|brought|fetched)\b[^.!?]{{0,30}}?"
               rf"\b(?:a|an|the|his|her|their)\s+{_weapon}\b", "actor", need=_DANGER_NEAR, block=_WEAPON_BENIGN)
_add("weapon", rf"\b{_weapon}\s+(?:at|to|on|against)\s+(?:me|my\s+(?:throat|neck|head|face|back|stomach|chest))\b", "any")
_add("weapon", rf"\b(?:threatened|threatens|threatening|attacked|attacks|attacking|hit|hits|hurt|cut|cuts|stabbed|stabs|shot|shoots|slashed|slashes|sliced|struck|clubbed|jabbed|beat|beaten)\s+(?:me\s+)?with\s+(?:a|an|the|his|her)\s+{_weapon}\b", "actor")
_add("weapon", r"\b(?:stab|stabs|stabbed|stabbing|shoot|shoots|shot|shooting)\s+(?:at\s+)?me\b", "actor",
     tail=r"^\s+(?:an?|another|one|some|his|her|their|my|your|that|this|down\b|off\b|up\b|over\b|out\b|back\b|\w+\s+(?:look|glare|glance|smile|grin|text|message|email|mail|dm|"
          r"video|photo|pic|picture|question|reply|wink|kiss|signal|note|call|invite|quote|joke|comment|line|ping)\b)",
     block=_FIGURATIVE_STAB)
_add("sexual", r"\b(?:forc(?:e|es|ed|ing)|made|makes|making)\s+me\s+(?:to\s+)?(?:have\s+sex|have\s+sexual|sleep\s+with|get\s+naked|undress|strip|perform\s+(?:oral|sex)|"
               r"do\s+sexual|watch\s+porn|touch\s+(?:him|her|them)|kiss\s+(?:him|her|them))", "any")
_add("sexual", r"\bforc(?:e|es|ed|ing)\s+(?:himself|herself|themselves)\s+on\s+me\b|\bforced\s+sex\b", "any")
_add("sexual", r"\b(?:rap(?:e|es|ed|ing)|molest(?:s|ed|ing)?|sexually\s+(?:assault|abus|harass)\w*)\s+me\b", "any")
_add("sexual", r"\bi\s+(?:was|am|got|have\s+been|had\s+been|keep\s+getting|am\s+being)\s+(?:raped|molested|sexually\s+(?:assaulted|abused|harassed)|abused\s+sexually)\b", "any")
_add("sexual", r"\bmarital\s+rape\b", "any", need=r"\b(?:my|me|i)\b")
_add("sexual", r"\b(?:sex|sexual|intercourse)\b[^.!?]{0,40}\bwithout\s+my\s+(?:consent|permission|will|agreement)\b", "any")
_add("sexual", r"\b(?:touch\w*|grop\w*|kiss\w*)\s+me\s+without\s+(?:my\s+)?(?:consent|permission)\b", "any")
_add("sexual", r"\b(?:doesn'?t|does\s+not|didn'?t|did\s+not|won'?t|never)\s+(?:take|accept|listen\s+to|respect|hear)\s+(?:my\s+)?(?:no|a\s+no)\b", "any",
     need=r"\b(?:sex|sexual|bed|intimate|intimacy|touch\w*|body)\b")
_add("sexual", r"\beven\s+(?:when|though|if|after)\s+i\s+(?:say|said|tell|told|beg|begged|cry|cried|refuse|refused)\s+(?:no|stop)\b", "any",
     need=r"\b(?:sex|sexual|bed|touch\w*|kiss\w*|grab\w*|hug\w*|undress\w*|forc\w*|pin\w*)\b", block=r"\b(?:doctor|dr|nurse|exam\w*|massage|physio\w*|lol|haha+)\b")
_add("sexual", r"\bagainst\s+my\s+will\b", "any", need=r"\b(?:sex|sexual|touch\w*|rape\w*)\b")
_add("sexual", r"\bsex\s+when\s+i\s+(?:don'?t|do\s+not)\s+want\b", "any")
# "my uncle touched me inappropriately": touching of a private kind by a relative or a close person (a child may be the speaker, so tier 3)
_add("sexual", r"\b(?:touch\w*|fondl\w*|grop\w*|molest\w*|feel\w*\s+up|rubb\w*|pinch\w*)\s+me\s+(?:inappropriately|improperly|wrongly|sexually|in\s+(?:a\s+)?(?:bad|wrong|dirty|"
               r"inappropriate|creepy|weird|funny|uncomfortable)\s+(?:way|places?|manner)|in\s+my\s+private|down\s+there|where\s+i\s+(?:didn'?t|did\s+not)\s+want)|"
               r"\b(?:touch\w*|grop\w*|fondl\w*)\s+my\s+(?:private\s+parts?|privates?|breasts?|vagina|genitals?|butt|bum)\b", "any",
     block=r"\b(?:doctor|dr|nurse|exam\w*|check\w*|scan|ultrasound|surgery|massage|physio\w*)\b")
_add("sexual", r"\binappropriate(?:ly)?\s+touch\w*|\b(?:bad|wrong)\s+touch\b", "any", need=r"\b(?:me|my|i)\b")
# "my uncle keeps touching me", "he touches me when nobody is around and I don't like it" (a child may be the one speaking)
_add("sexual", r"\b(?:keeps?|kept|started|starts|has\s+been|have\s+been|had\s+been|been)\s+touching\s+me\b|\b(?:touch\w*|grop\w*)\s+me\b[^.!?]{0,45}\b(?:don'?t|do\s+not|didn'?t|did\s+not|never)\s+(?:like|want)\b|"
               r"\b(?:touch\w*|grop\w*)\s+me\s+(?:when|while)\s+(?:no\s*one|nobody|we\s+are\s+alone|we'?re\s+alone|i'?m\s+alone|i\s+am\s+alone|everyone\s+(?:is\s+)?(?:asleep|out|gone))\b", "weak",
     block=r"\b(?:doctor|dr|nurse|exam\w*|massage|physio\w*|gently|kindly|deeply|emotionally|heart|story|song|movie)\b")
# "my uncle touched me and forced me", "touched me and made me do things", "touched me and told me not to tell anyone": no sex word is needed when a touch is followed by force or a secret
_add("sexual", r"\b(?:touch\w*|grop\w*|fondl\w*|molest\w*)\s+me\b[^.!?]{0,30}?\b(?:and|then|but|so)\s+(?:he\s+|she\s+)?(?:forc\w+|pressur\w+|blackmail\w+|threaten\w+)\s+me\b|"
               r"\b(?:touch\w*|grop\w*|fondl\w*)\s+me\b[^.!?]{0,30}?\b(?:made|makes|forced|forces)\s+me\s+(?:to\s+)?(?:do|to\s+do)\s+(?:things|stuff|something|that|it|bad|dirty|wrong)\b|"
               r"\b(?:touch\w*|grop\w*|fondl\w*)\s+me\b[^.!?]{0,40}\b(?:(?:told\s+me|said|says|tells\s+me)\s+(?:not\s+to\s+tell|to\s+keep|to\s+stay\s+quiet)|(?:our|a)\s+secret|don'?t\s+tell)", "any",
     block=r"\b(?:doctor|dr|nurse|exam\w*|massage|physio\w*|gently|kindly|deeply|emotionally|heart|story|song|movie|film|speech|poem|lol|haha+)\b")
_add("sexual", r"\bmujhe\s+(?:galat|ganda|gandi)\s+(?:tarah|tareeke|jagah)\s+(?:se\s+|pe\s+|par\s+)?(?:chhu|chu|haath\s+laga)\w*|\b(?:galat|ganda|gandi)\s+(?:tarah|tareeke)\s+se\s+(?:mujhe\s+)?(?:chhu|chu)\w*", "any")
_add("sexual", r"मुझे\s+गलत\s+(?:तरह|तरीके|जगह)\s+(?:से\s+|पर\s+)?(?:छ[ूु]|हाथ\s+लगा)\w*", "any")
_child = r"(?:the\s+|our\s+|my\s+|his\s+|her\s+)?(?:kids?|children|child|baby|babies|son|sons|daughter|daughters|boy|girl|toddler|infant|little\s+ones?|(?:\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)[ -]?(?:years?|yrs?|months?)[ -]?old(?:\s+(?:son|daughter|boy|girl|child|baby))?)"
_add("child", rf"\b(?:hit|hits|hitting|beat|beats|beating|slap|slaps|slapped|kick|kicks|kicked|punch|punches|punched|burn|burns|burned|burnt|abuse|abuses|abused|abusing|"
              rf"hurts|hurting|molest\w*|shake|shakes|shook|lock|locks|locked|starve|starves)\s+{_child}\b", "actor", need=r"\b(?:my|our|the\s+(?:kids?|children|baby))\b")
# "my husband beats me and the kids": the verb comes before "me", the child after "and"
_add("child", r"\b(?:hit|hits|hitting|beat|beats|beating|slap|slaps|slapped|kick|kicks|kicked|punch|punches|punched|abuse|abuses|abused|abusing|hurts|hurting|"
              r"thrash\w*|batter\w*)\s+me\s+(?:and|&|n|as\s+well\s+as|along\s+with|plus)\s+(?:the\s+|our\s+|my\s+|his\s+|her\s+)?(?:kids?|children|child|baby|babies|sons?|daughters?|"
              r"toddler|infant|little\s+ones?)\b", "actor")
_add("child", rf"\b(?:kids?|children|child|baby|son|daughter)\s+(?:is|are|gets?|got|being)\s+(?:being\s+)?(?:beaten|hit|slapped|abused)\s+by\b", "any", need=r"\b(?:my|our)\b")

# ===== English: control, fear, verbal abuse, dowry =====
_add("control", r"\b(?:checks?|checking|goes?\s+through|going\s+through|monitors?|monitoring|reads?|reading|snoops?\s+(?:through|on)|tracks?|tracking|spies\s+on|spying\s+on|stalks?|"
                r"stalking)\s+(?:all\s+)?(?:my\s+)?(?:phone|messages?|chats?|texts?|calls?|call\s+log|location|whatsapp|emails?|social\s+media|accounts?|passwords?|movements?)\b", "close",
     tail=r"^\s+(?:battery|charge|charging|storage|update|updates|settings|brightness|volume)\b",
     block=r"\bto\s+(?:see|check|know|find|look\s+up|read)\s+(?:the\s+)?(?:cricket|score|scores|match|weather|time|news|traffic|train|flight|map|menu|recipe|temperature)\b|"
           r"\b(?:cricket|weather|recipe|alarm|timer|out\s+loud|aloud|with\s+my\s+(?:permission|consent)|after\s+asking|asks\s+first)\b")
_add("control", r"\b(?:takes?|took|taking|snatch(?:es|ed)?|confiscat(?:es|ed)|grabs?|controls?|controlling|keeps?|holds?|withholds?)\s+(?:all\s+)?(?:of\s+)?my\s+"
                r"(?:money|salary|pay|paycheck|income|earnings|atm|cards?|bank|phone|passport|documents?|id)\b", "close_or_family",
     block=r"\b(?:charger|cable|case|cover|keys?|earphones?|headphones?|plug|accountant|tax|taxes|filing|itr|renew\w*|consulate|submit\w*|reimburse\w*|insurance|"
           r"to\s+(?:take|click|snap|call|play|charge|google|search|set|film|record)\b)",
     tail=r"^\s+(?:slips?|certificates?|statements?|receipts?|proofs?|letters?|forms?|details|reports?)\b")
_add("control", r"\b(?:doesn'?t|does\s+not|won'?t|will\s+not|never|not)\s+(?:let|allow|permit)\s+me\s+(?:to\s+)?(?:meet|see|talk|speak|go|leave|work|study|call|visit|have|use|"
                r"step|get\s+out|stay\s+in\s+touch|contact|join|spend|keep|text|message|make|wear|travel|sleep|be)\b", "close")
_add("control", r"\b(?:i'?m|i\s+am|am)\s+not\s+allowed\s+to\s+(?:meet|see|talk|speak|go|leave|work|study|call|visit|have|use|step|get\s+out|contact|wear|travel|text|message)\b", "close")
_add("control", r"\b(?:forbids?|forbade|stops?|stopped|prevents?|prevented|bans?|banned)\s+me\s+from\s+(?:meeting|seeing|talking|speaking|going|working|studying|leaving|calling|"
                r"visiting|using|contacting|texting|wearing|travelling|traveling)\b", "close")
_add("control", r"\b(?:locks?|locked|locking|keeps?\s+me\s+locked|shuts?|trapped|traps)\s+me\s+(?:in|inside)\b", "close_or_family",
     block=r"\b(?:accident\w*|by\s+mistake|lol|haha+|laughed|laughing|car|lift|elevator|joke|prank)\b")
_add("control", r"\b(?:locked|locks|locking|bolted|bolts)\s+(?:the\s+)?(?:door|gate|house|room)\b[^.!?]{0,30}\b(?:won'?t|will\s+not|doesn'?t|does\s+not|not)\s+(?:let|allow)\s+me\s+(?:out|leave|go)\b", "close_or_family")
_add("control", r"\b(?:cut|cuts|cutting)\s+me\s+off\s+from\s+(?:my\s+)?(?:family|friends|everyone|everybody|parents)\b", "close_or_family")
_add("control", r"\bisolat(?:es|ed|ing)\s+me\b", "close")
_add("control", r"\b(?:threw|throws|kicked|kicks|throwing)\s+me\s+out\s+of\s+(?:the|our|his|her)\s+(?:house|home|flat|apartment|room)\b", "close")
_add("control", r"\b(?:makes?|made|forces?|forced)\s+me\s+(?:to\s+)?(?:quit|leave|give\s+up|stop)\s+(?:my\s+)?(?:job|work|studies|college|school|career)\b", "close_or_family")
_add("control", r"\bcontrols?\s+(?:everything|my\s+life|what\s+i\s+wear|who\s+i\s+(?:talk|meet|see))\b", "close")
_fear_t = rf"(?:him|her|them|my\s+(?:{_PARTNER}|{_INLAW}|{_FAMILY})|his\s+(?:temper|anger|moods?|reaction)|her\s+(?:temper|anger|moods?|reaction)|going\s+home|being\s+(?:alone|home)\s+with)"
_add("fear", rf"\b(?:scared|afraid|terrified|frightened|petrified|fearful)\s+of\s+{_fear_t}\b", "any")
_add("fear", r"\b(?:scared|afraid|terrified|frightened|petrified|fearful)\s+to\s+(?:go\s+(?:home|back)|come\s+home|be\s+(?:home|alone\s+with|around|with)\s+(?:him|her|them|my)|"
             r"tell\s+(?:him|her)|talk\s+to\s+(?:him|her)|speak\s+to\s+(?:him|her)|say\s+no|disagree|upset\s+(?:him|her)|leave\s+(?:him|her))", "any")
_add("fear", r"\b(?:don'?t|do\s+not|doesn'?t|no\s+longer)\s+feel\s+safe\s+(?:at\s+home|with\s+(?:him|her|them|my\s+\w+)|around\s+(?:him|her|them|my\s+\w+)|in\s+my\s+(?:own\s+)?(?:home|house|marriage|relationship))", "any")
_add("fear", r"\b(?:feel|feeling|am|i'?m)\s+unsafe\s+(?:at\s+home|with|around|in)\b|\bunsafe\s+at\s+home\b|\bnot\s+safe\s+at\s+home\b|\b(?:afraid|fear)\s+for\s+my\s+(?:life|safety)\b|"
             r"\bin\s+danger\s+at\s+home\b", "any")
_add("fear", r"\bwalking\s+on\s+eggshells\b|\b(?:afraid|scared|fear)\s+(?:that\s+)?(?:he|she|they)'?(?:ll|\s+will|\s+would|\s+might)\s+(?:hurt|hit|kill|harm|beat)\b", "any")
_add("fear", r"\b(?:scares|terrifies|frightens|intimidates)\s+me\b", "close")
_add("verbal", r"\b(?:abuses|abused|abusing|insults?|insulted|humiliat(?:es|ed|ing)|degrad(?:es|ed|ing)|belittl(?:es|ed|ing)|demean(?:s|ed|ing)|swears?\s+at|cursed?\s+at|curses|"
               r"bullies|bullied|gaslights?|mocks?)\s+me\b", "close",
     tail=r"^\s+into\s+(?:trying|going|watching|eating|buying|joining|coming|taking)\b", block=r"\b(?:lol|haha+|lmao|jk|jokingly|playfully)\b")
_add("verbal", r"\b(?:calls?|called|calling)\s+me\s+(?:names|stupid|useless|worthless|ugly|fat|dumb|idiot|a\s+(?:slut|bitch|whore|loser|failure|burden|waste)|bad\s+names)\b", "close")
_add("verbal", r"\b(?:yells?|shouts?|screams?|screamed|yelled|shouted|rages?)\s+at\s+me\b[^.!?]{0,30}\b(?:every|all|daily|always|constantly|each|for\s+hours|roz)\b", "close")
_add("verbal", r"\b(?:verbal(?:ly)?|emotional(?:ly)?|mental(?:ly)?|psychological(?:ly)?)\s+(?:abus\w+|violen\w+|tortur\w+|harass\w+)", "any", need=r"\b(?:my|me|i|i'm)\b")
_add("verbal", r"\b(?:tortur(?:es|ed|ing)|harass(?:es|ed|ing))\s+me\b", "close",
     block=r"\b(?:singing|sings?|jokes?|puns?|stories|music|playlist|cooking|snoring|snores|trivia|karaoke|memes?|lol|haha+|lmao|jk|spoilers?|recipes?|selfies?|puzzles?|riddles?|quiz)\b")
_add("verbal", r"\b(?:makes?|made)\s+me\s+feel\s+(?:worthless|useless|small|stupid|like\s+nothing|like\s+a\s+burden)\b", "close")
_add("verbal", r"\b(?:is|are|was|been|being|gets|got|becomes)\s+(?:very\s+|so\s+|really\s+|extremely\s+)?abusive\b", "any", need=rf"\bmy\s+(?:{_PARTNER}|{_INLAW})\b")
_add("verbal", r"\b(?:is|are|was|gets|got|becomes|became|turns|turned)\s+(?:very\s+|so\s+|really\s+|extremely\s+|quite\s+|too\s+)?violent\b", "close",
     block=r"\b(?:movie|film|character|show|series|game|villain|dog|puppy|cat|horse|bull|kid|toddler|baby|customer|fans?|crowd|protest\w*|book|novel|scene|video|song|lyrics|sports?|games)\b")
_add("verbal", rf"\b(?:my|i\s+am\s+in\s+an?|i'?m\s+in\s+an?|in\s+an?|stuck\s+in\s+an?|trapped\s+in\s+an?)\s+(?:very\s+|so\s+)?(?:abusive|violent)\s+"
               rf"(?:relationship|marriage|husband|wife|boyfriend|girlfriend|partner|home|household)\b", "any")
_add("verbal", r"\bdomestic\s+(?:violence|abuse)\b", "any", need=r"\b(?:i|i'm|im|my|me|we)\b",
     block=r"\b(?:law|act|case|section|statistics|stats|report|news|article|research|awareness|what\s+is|define|meaning|helpline\s+for\s+others|topic|class|classes|syllabus|"
           r"chapter|lesson|civics|essay|project|school|college|assignment|lecture|course|documentary|book)\b")
_add("verbal", r"\b(?:victim|survivor)\s+of\s+(?:domestic|physical|verbal|emotional|sexual)?\s*(?:violence|abuse)\b", "any", need=r"\b(?:i|i'm|im|am)\b")
_add("dowry", r"\b(?:demand(?:s|ed|ing)?|harass(?:es|ed|ing)?|torture[sd]?|torturing|pressur(?:e|es|ed|ing)|forc(?:e|es|ed|ing)|asks?|asking|asked)\b[^.!?]{0,40}\bdowry\b|"
              r"\bdowry\b[^.!?]{0,40}\b(?:demand\w*|harass\w*|torture\w*|pressure|harassment)\b", "any", need=r"\b(?:my|me|i|we)\b")

# A father or elder beating the mother, sister or wife in the house the person lives in ("my dad beats my mom"). The person is part of that home, so it gets the
# same gentle fixed reply as their own story (tier 2; a danger marker such as "every night" or "I am scared" moves it to tier 3). A friend's family stays someone else's story.
_MALE_REL = r"(?:dad|father|papa|stepfather|stepdad|step-father|step-dad|uncle|brother|bro|grandfather|grandpa|husband|dada|nana)"
_FEMALE_REL = r"(?:mom|mum|mother|sister|sis|grandma|grandmother|aunt|aunty|stepmother|stepmom|step-mother|step-mom|wife|bhabhi|bhabi)"
_BEAT_V = (r"(?:beats|hits|slaps|punches|kicks|chokes|strangles|batters|thrashes|abuses|assaults|beat|hit|slapped|punched|kicked|choked|strangled|battered|thrashed|assaulted|abused|"
           r"hitting|beating|slapping|punching|kicking|choking|strangling|battering|thrashing|assaulting|abusing)")
_GAMEY = (r"^(?!.*\b(?:hurt|bruis\w*|bleed\w*|blood|cry|cried|scared|afraid|injur\w*|black and blue|up)\b).*\b(?:chess|ludo|carrom|cricket|football|game|games|match|race|quiz|"
          r"tournament|competition|contest|exam|marks|score|monopoly|poker|cards|pubg|fifa|badminton|tennis|sudoku|video game|playstation|xbox|bet|election|debate|ball|six)\b")
_add("physical", rf"\bmy\s+{_MALE_REL}\s+(?:\w+\s+){{0,2}}?{_BEAT_V}\s+(?:up\s+)?(?:my\s+{_FEMALE_REL}|her|{_FEMALE_REL})\b(?!'s\b)", "any", play_ok=True, block=_GAMEY)
_add("physical", rf"\bmy\s+{_FEMALE_REL}\s+(?:gets|got|is|was|is\s+being|keeps\s+getting|has\s+been|was\s+being)\s+(?:\w+\s+)?(?:beaten|hit|slapped|punched|kicked|choked|strangled|"
                 rf"battered|abused|thrashed|assaulted)\s+(?:up\s+)?by\s+my\s+{_MALE_REL}\b", "any", play_ok=True, block=_GAMEY)

# ===== Hinglish (Roman script) =====
# A drink word blocks a match only where it is what is being drunk ("mujhe chai peeti hai") or the idiom "chai ke liye marta" (dying for a tea).
# A drunk husband who beats his wife ("pati sharab pikar mujhe maarta hai") is the most common disclosure, so a drink word elsewhere never blocks.
_DRINK = r"(?:chai|paani|pani|daaru|daru|sharab|coffee|doodh|juice|cigarette|beer|drink|tea)"
_hi_block_idiom = r"\b(?:chai|coffee|paani|pani|doodh|juice|tea)\s+(?:ke\s+)?(?:liye|bina)\s+(?:\w+\s+){0,2}?mar(?:ta|ti|te)\b"
_hi_block_drink = rf"\b{_DRINK}\s+(?:\w+\s+){{0,2}}?pee(?:ta|ti|te)\b|" + _hi_block_idiom
_hi_verb = (r"(?P<v>maar(?:ta|ti|te)|mar(?:ta|ti|te)|pitt(?:a|i)|pit-?(?:ta|ti|te)|pitai|peetai|peet-?t(?:a|i|e)|marpeet|maarpeet|maar[- ]peet|"
            r"(?:maar|peet|pit)\s+(?:raha|rahi|rahe)|maar\s+(?:diya|di)(?!\s+dal)|(?:peet|pit)\s+(?:diya|di|deta|deti|dete)|"
            r"maar\s+maar|peet\s+peet)")
# A video game "kills" or "beats" a person every day ("mere pati ne mujhe PUBG mein maar diya"); unless an injury or fear word is also there.
_hi_media = (r"\b(?:film|movie|gaana|gaane|song|series|serial|scene)\b|"
             # a friend, a coach or a classmate who pushes "me" is not a partner or a family member (the gym "dhakka" for motivation)
             r"\b(?:dost|dosto|friend|friends|yaar|classmate|colleague|coach|trainer|teacher|padosi|padosan|stranger)\s+(?:(?:ne|bhi|toh|to|hi)\s+)?(?:mujhe|mujhko|muje|mereko|meko)\b|"
             r"^(?!.*\b(?:chot|khoon|dard|hospital|darr|dar|rona|roya|royi)\b).*\b(?:pubg|bgmi|valorant|fortnite|minecraft|free\s*fire|noob|gaming|"
             r"(?:game|match|ludo|carrom|chess|round|level)\s+(?:mein|me|ke\s+dauran))\b")
# food, the sun or hot tea as the thing that burned ("teekhe khane ne mujhe jala diya"): a thing, not a person
_hi_thing_burns = (r"\b(?:khana|khane|khaana|khaane|mirchi|teekh\w*|masala|dhoop|suraj|garmi|chai|coffee|doodh|tel|paani|pani|sunscreen)\s+ne\b|"
                   r"\b(?:khane|mirchi|teekh\w*|masala|dhoop|suraj)\s+se\b")
# "sar dard mujhe maar raha hai", "garmi ne mujhe maar diya", "thakaan maar rahi hai": a symptom, the weather or tiredness "kills" me, and a thing is
# never the person who hit. Blocked when the complaint word is the subject (a few filler words before the verb, no person in between) or in the
# "<verb> ... <complaint> ne" order. A real disclosure next to a complaint ("mujhe bukhar hai aur pati maarta hai") has a person in between.
_hi_complaint = (r"(?:\w*dard\w*|bukh?aa?r|garmi|garmee|garam[ie]?|sardi|sardee|thand|thandi|thaka+n|thakawat|thakaavat|bhookh|bhook|bhukh|neend|nind|pyaas|pyas|"
                 r"khaa?nsi|cramps?|ulti|chakkar|kamzori|migraine|allergy|infection|tension|stress|bimaari|bimari|dhoop|baarish|barish|humidity|pollution|"
                 r"bojh|bojhh|yaad|acidity|gas|zukh?aa?m|jalan|kabz|dast|sujan|jakdan|udaasi|udasi|akelapan|tanhai|chinta|fikar|pareshani|boredom|"
                 r"exam|paper|result|interview|presentation|homework|assignment|syllabus|deadline|traffic|padhai)")
# up to three words between the complaint and the verb, as long as none of them is a person or ends the clause ("bukhar hai aur pati maarta hai" is not blocked)
_hi_stop = (r"(?:hai|hain|hota|hoti|hote|aur|lekin|par|magar|kyunki|jab|tha|thi|the|and|but|woh|wo|vo|usne|unhone|dost|friend|koi|log|sab|ghar|family|"
            + _REL_HI[3:-1] + ")")
_hi_filler = rf"(?:(?!{_hi_stop}\b)\w+\s+)"
_hi_kill = r"(?:maar(?:ta|ti|te)|mar(?:ta|ti|te)|maar\s+(?:raha|rahi|rahe|diya|di|dala|dali)|maara|maari)"
_hi_not_a_person = rf"\b{_hi_complaint}\s+{_hi_filler}{{0,3}}{_hi_kill}\b|\b{_hi_kill}\s+{_hi_filler}{{0,3}}{_hi_complaint}\s+ne\b"
_add("physical", rf"{_ME_HI}\b[^.!?]{{0,30}}?\b{_hi_verb}\b", "any", play_ok=True, block=_hi_block_idiom + "|" + _hi_media + "|" + _hi_not_a_person)
_add("physical", rf"\b{_hi_verb}\b[^.!?]{{0,15}}?{_ME_HI}\b", "any", play_ok=True, block=_hi_block_idiom + "|" + _hi_media + "|" + _hi_not_a_person)
# "mujhe ghar mein roz maara jaata hai": the passive
_add("physical", rf"{_ME_HI}\b[^.!?]{{0,35}}?\b(?:maara|mara|peeta|pita|pitta)\s+(?:jaata|jata|jaati|jati|ja\s+raha|jaa\s+raha|ja\s+rahi|jaa\s+rahi)\b", "any", play_ok=True,
     block=_hi_block_idiom + "|" + _hi_media + "|" + _hi_not_a_person)
# "sasural mein roz maar padti hai", "maar khaa rahi hu roz pati se": taking a beating
_add("physical", r"\bmaar\s+(?:padt[ia]|padte|padi|pad\s+(?:rahi|rahe|gayi|gai)|milt[ia]|mil\s+rahi|khaat[ai]|khat[ai]|khaa?\s+rah[ie]|khaa?\s+rah[ae]|khaya|khayi|khai|khan[ei])\b", "any",
     play_ok=True, need=r"\b(?:mujhe|mujh|main|mai|hoon|hu|hun|rahi|meri|mera|mere|hum|pati|husband|sasural|ghar)\b", block=_hi_media)
_add("physical", rf"{_ME_HI}\b[^.!?]{{0,45}}?\b(?P<v>maara|maari|mara|mari|peeta|peeti)\s*(?:hai|h|he)?\b", "any", play_ok=True,
     need=r"\bne\b|\busne\b|\bunhone\b|\bwoh\b|\bwo\b|\bvo\b|\bpati\b|\bhusband\b",
     block=_hi_block_drink + "|" + _hi_media + "|" + _hi_not_a_person + r"|\b(?:mar\s+gaya|mar\s+gayi)\b", tail=r"^\s+(?:gaya|gayi|jaana|jana|jaunga|jaungi)\b")
_add("physical", rf"\b(?:mera|meri|mere)\s+{_REL_HI}\s+(?:\w+\s+){{0,3}}?{_hi_verb}\b", "any", play_ok=True,
     block=_hi_block_idiom + "|" + _hi_not_a_person + rf"|\b(?:mera|meri|mere)\s+{_REL_HI}\s+ko\b")      # "mere bhai ko maar diya": my relative was hit, not me
_add("physical", r"\b(?:mera|meri|mere)\s+(?:sar|sir|haath|hath|baal|muh|munh|gaal|pet|peeth|kamar|chehra|aankh|aankhen|naak|kaan|ungli|pair|taang|seena)\b[^.!?]{0,25}?"
                 r"\b(?P<v>maara|mara|pakda|pakad|khincha|khinch|marora|maroda|toda|tod\s+diya|dabaya|jalaya|jala\s+diya|kuchla)\b", "any", play_ok=True,
     need=r"\bne\b|\busne\b|\bunhone\b|\bwoh\b|\bwo\b|\bvo\b|\bpati\b|\bhusband\b", block=r"\b(?:khud|apne\s+aap|galti\s+se)\b")
_add("physical", r"\b(?:meri|mere)\s+(?:pitai|peetai|maar-?peet|marpeet)\b|\b(?:maar-?peet|marpeet|maarpeet)\s+(?:karta|karti|karte|hota|hoti|hoti\s+hai|karne)\b", "any",
     need=r"\b(?:mera|meri|mere|mujhe|mujh|ghar|pati|husband|wife|saas|sasur)\b", play_ok=True)
_add("physical", r"\b(?:thapp?ad(?:on)?|thapar|tamacha|tamache|chaanta|jhaapad|laat|laaten|lat|ghoonsa|ghunsa|mukka|mukke|dhakka|dhakke|kohni)\s+(?:\w+\s+)?(?P<v>mar(?:a|i|ta|ti|te)|maar(?:a|i|ta|ti|te)|jad(?:a|diya|ta|ti|te)?|"
                 r"lagaya|lagaye|lagaaye|lagayi|lagai|lagae|lagata|lagati|lagate|de\s+(?:diya|di|diye)|diya|diye|di\b|deta|deti|dete|dena|maar\s+di|mar\s+di|maare|mare)\b", "any", play_ok=True,
     need=rf"{_ME_HI}|\bmere\s+(?:gaal|muh|munh|chehre|pet|peeth)\b|\bmeri\s+(?:peeth|kamar)\b", block=_hi_media)
_add("physical", r"\bhaath\s+(?:bhi\s+)?(?:uthat|uthay|uth\s+jata|chalat|chalay|utha\s+(?:diya|di|liya))\w*|\bhath\s+(?:bhi\s+)?(?:uthat|uthay|chalat|utha\s+(?:diya|di))\w*", "any", play_ok=True, need=rf"{_ME_HI}|\bmujh|\bmere\b|\bmeri\b", block=_hi_media)
_add("physical", r"\b(?:baal|bal|baalon|balon)\s+(?:se\s+)?(?:pakad|kheench|khinch|nooch|noch)\w*|\bnoch(?:ta|ti|te|a|i)\b|\bjala\s+(?:diya|dete|deta)\b", "any", need=rf"{_ME_HI}|\bmere\b|\bmeri\b", block=_hi_thing_burns)
_add("physical", r"\bmujhe\s+maarne\s+(?:ki\s+(?:dhamki|koshish)|aaya|aaye|lagta|lage|laga|dauda|daude)\b|\bmaarne\s+ki\s+dhamki\b", "any")
# "pati maarta hai", "sasural wale dahej maangte hain aur maarte hain": the husband or an in-law as the subject, no "me" in the sentence. Not when someone
# else's husband is meant ("meri saheli ka pati"), someone else is hit ("pati bachon ko maarta hai" is the child family), or an animal / a friend is.
_hi_other_target = r"\b(?:usse|use|usko|unhe|unko|bachon|bachchon|bachche|bete|beti|kutte|kutta|gai|janwar|dost|friend|saheli|padosi|padosan|naukar|naukrani)\s+(?:ko\s+)?(?:\w+\s+){0,3}?(?:maar|mar|peet|pit)"
_add("physical", rf"(?:^|\s)(?:pati|husband|hubby|bf|boyfriend|saas|sasur|sasural(?:\s*(?:wale|walon|walo|walein))?|sasuralwale|devar|jeth|nanad|jethani|in-?laws?)\s+(?:\w+\s+){{0,5}}?{_hi_verb}\b",
     "any", play_ok=True,
     block=_hi_media + "|" + _hi_block_drink + "|" + _hi_not_a_person + r"|\b(?:ka|ki|ke|uska|uski|uske|unka|unki|unke|iska|iski|iske)\s+(?:pati|husband|saas|sasur|devar|jeth|nanad)\b|"
           + _hi_other_target + r"|^(?!.*\b(?:mujhe|mujhko|muje|mereko|meko|mujh)\b).*\bko\b")      # someone ELSE is hit ("pati ne mere bhai ko maara")
# "pati ne dhakka de diya", "husband ne thappad maara": the person hit is "me" without being said
_hi_ko_other = (r"^(?!.*\b(?:mujhe|mujhko|muje|mereko|meko|mujh)\b).*\bko\b|"      # "papa ne bhai ko maara": someone ELSE is hit
                r"\b(?:maine|mainey|mene|maene|mai\s*ne|main\s*ne|hamne|humne)\b")        # "maine apni wife par haath uthaya": the speaker is the doer (perpetrator rules)
_add("physical", rf"\b{_REL_HI}\s+ne\s+(?:\w+\s+){{0,2}}?(?:thapp?ad|thapar|tamacha|laat|ghoonsa|ghunsa|mukka|dhakka|jhaapad|chaanta)\s+"
                 r"(?:\w+\s+)?(?P<v>(?:de|diya|diye|di\b|mar|maar|jad|laga)\w*)", "any", play_ok=True, block=_hi_media + "|" + _hi_other_target + "|" + _hi_ko_other)
# "pati ne maara", "husband ne belan se mara", "papa ne peeta": a close person as the doer, nobody else named, so it is the speaker who was hit
_add("physical", rf"\b{_REL_HI}\s+ne\s+(?:\w+\s+){{0,2}}?(?P<v>maara|maari|mara|mari|peeta|peeti|pitaai|peetai)\b(?!\s+(?:hua|hui|hue)\b)", "any", play_ok=True,
     block=_hi_media + "|" + _hi_other_target + "|" + _hi_ko_other + "|" + _hi_block_drink +
           r"|\b(?:six|chhakka|chauka|four|goal|gol|catch|shot|ball|century|wicket|boundary|cricket|match|game|ludo|chess|carrom|bet|paise|paisa|dhoka|gappa|bahana|taana|joke|mazak|mazaak|nishana)\b")
# "pati kabhi kabhi haath uthata hai", "papa ne haath uthaya": raising a hand, the doer a close person (not a prayer, a vote or a question in class)
_add("physical", rf"\b{_REL_HI}\s+(?:ne\s+)?(?:\w+\s+){{0,7}}?(?:haath|hath)\s+(?:bhi\s+)?(?:uthat|uthay|uth\s+jata|chalat|chalay|utha\s+(?:diya|di|liya))\w*", "any", play_ok=True,
     block=_hi_media + "|" + _hi_other_target + "|" + _hi_ko_other + r"|\b(?:dua|duaa|ashirwad|aashirwad|puja|prarthana|namaste|class|sawal|question|vote|bid|auction|ishara|bye|salaam|salam)\b")
# "mere husband ne mujhe slap kiya", "pati ne slap kiya": an English hitting word with "kiya"; never when the speaker is the doer
_add("physical", r"\b(?:slap|punch|kick|thrash|choke|strangle|beat|hit)\s+(?:kiya|kia|kiye|kari|kar\s+diya|karta|karti|karte)\b", "any", play_ok=True,
     need=rf"{_ME_HI}|\b{_REL_HI}\s+ne\b",
     block=_hi_media + "|" + _hi_other_target + "|" + _hi_ko_other + r"|\b(?:maine|mainey|mene|maene|mai\s*ne|main\s*ne|hamne|humne|main|mai)\b")
# the verb first, "belan se mara mujhe": the doer is named with "ne", the speaker comes last
_add("physical", rf"\b(?P<v>maara|maari|mara|mari|peeta|peeti)\b[^.!?]{{0,15}}?{_ME_HI}\b", "any", play_ok=True,
     need=r"\bne\b|\busne\b|\bunhone\b", block=_hi_block_drink + "|" + _hi_media + "|" + _hi_not_a_person + r"|\b(?:mar\s+gaya|mar\s+gayi)\b|\b(?:maine|mainey|mene|main\s*ne)\b",
     tail=r"^\s+(?:gaya|gayi|jaana|jana|jaunga|jaungi)\b")
# "usne mujhe pita aaj phir": "pita" as the verb (not the father: "pita ji", "pita ne", "pita ka")
_add("physical", rf"{_ME_HI}\b[^.!?]{{0,20}}?\b(?P<v>pita|piti)\b(?!\s+(?:ji|jee|ne|ka|ki|ke|se|ko|pe|par|hain|the|tha|thi|hai|bhi\s+hai))", "any", play_ok=True,
     need=r"\b(?:usne|unhone|pati|husband|bf|boyfriend)\b", block=_hi_media + "|" + _hi_other_target)
# "meri saas ne mujhe jalaya garam tel se", "husband ne mujhe jalti cigarette se dagha": burned or branded. A heat word must be there ("dhoop ne mujhe jalaya" is the sun).
_hi_hot = r"\b(?:garam|tel|cigarette|sigret|aag|chulh\w+|tawa|tava|pateel\w*|chai|kerosene|mitti|petrol|diesel|maachis|matchbox|iron|press|stove|lighter|beedi|bidi|jalti|jalta)\b"
_hi_burn = r"(?:jalay\w*|jala\s+(?:diya|di|dala|dali|dete|deta|deti)|dagh\w*|daagh\w*|dagn\w*|dag\s+(?:diya|di))"
_add("physical", rf"{_ME_HI}\b[^.!?]{{0,40}}?\b{_hi_burn}\b", "any", play_ok=True, need=_hi_hot, block=_hi_media + "|" + _hi_thing_burns)
_add("physical", rf"\b{_REL_HI}\s+ne\s+(?:\w+\s+){{0,3}}?{_hi_burn}\b", "any", play_ok=True, need=_hi_hot, block=_hi_media + "|" + _hi_other_target + "|" + _hi_ko_other)
# "sasural wale mujhe garam pani se jalate hain": the present tense, with a relative as the subject
_add("physical", r"(?:^|\s)(?:pati|husband|saas|sasur|sasural(?:\s*(?:wale|walon|walo))?|sasuralwale|devar|jeth|jethani|nanad|in-?laws?)\s+(?:\w+\s+){0,5}?jala(?:te|ta|ti)\b", "any",
     play_ok=True, need=_hi_hot, block=_hi_media + "|" + _hi_other_target + "|" + _hi_ko_other)
# a household where a father or elder beats the mother, sister or sister-in-law ("papa mummy ko roz maarte hain"): the person lives in it, so the same care
_MALE_HI = r"(?:papa|pitaji|pita\s+ji|baap|bhai|chacha|taau|fufa|jija|jiju|dada|nana|sasur|devar|jeth)"
_FEMALE_HI = r"(?:mummy|maa|mother|didi|behen|behan|bhabhi|dadi|nani|chachi|bua|bhua|saas|jethani|nanad)"
_HH_VERB = (r"(?P<v>maar\w*|peet\w*|pit-?(?:t|ta|ti|te|ai)\w*|(?:haath|hath)\s+(?:uth|chala)\w*|thapp?ad\s+\w+|dhakka\s+\w+|laat\s+\w+)")
_HH_BLOCK = _hi_media + r"|\b(?:rok\w*|bach\w*\s+ke|dhoond\w*|dekh\w*|bula\w*)\b"
_add("physical", rf"\b(?:mere\s+|meri\s+)?{_MALE_HI}\s+(?:ne\s+)?(?:\w+\s+)?{_FEMALE_HI}\s+(?:ko|pe|par)\s+(?:\w+\s+){{0,2}}?{_HH_VERB}\b", "any", play_ok=True, block=_HH_BLOCK)
_add("physical", rf"\b{_FEMALE_HI}\s+(?:ko|pe|par)\s+(?:\w+\s+){{0,2}}?{_MALE_HI}\s+(?:ne\s+)?(?:\w+\s+){{0,2}}?{_HH_VERB}\b", "any", play_ok=True, block=_HH_BLOCK)
_add("strangulation", r"\bgal[ae]\s+(?:dab|ghont|pakad)\w*|\bgala\s+(?:dabaya|dabata|dabati|dabate|ghonta|ghonte|ghontne|pakda|pakadta)\b|\bsaans\s+(?:band|rok)\w*|"
                      r"\bgardan\s+(?:dab|pakad|mar|todn)\w*|\b(?:gardan|gale|gala)\s+(?:pe|par)\s+haath\b", "any", block=r"\b(?:kharab|dard|sukh|bhar\s+aaya|baith)\b")
# "dam ghut raha hai" is a person who cannot breathe (a symptom): it is a hold only when someone is named doing it ("usne mera dam ghont diya")
_add("strangulation", r"\bdam\s+(?:ghont|ghot|ghut)\w*", "any", need=r"\b(?:usne|unhone|pati|husband|bf|gf|boyfriend|girlfriend|saas|sasur|devar|jeth|wo|woh|vo)\b",
     block=r"\b(?:dil|dhak|seena|chest|atka|atki|khansi|allergy|asthma|dawai|doctor|hospital|bukhar|phool)\b")
_add("strangulation", r"\bgal[ae]\s+(?:se|ko)\s+(?:pakad|dab|ghont)\w*|\b(?:choke|strangle)\s+(?:kiya|kar|karta|karti|karte|kar\s+diya|kar\s+raha)\b", "any",
     need=r"\b(?:mujhe|mera|meri|mere|ne|usne|pati|husband|bf|gf)\b")
_add("threat_kill", r"\bjaan\s+(?:se\s+)?(?:maar|khatam|le\s+l)\w*|\bjaan\s+se\s+marwa\w*|\bmarwa\s+(?:dunga|dega|denge|dungi)\b|\bzind?a\s+(?:nahi|nhi)\s+chh?o\w*|\bjinda\s+(?:nahi|nhi)\s+chh?o\w*|"
                    r"\bkhatam\s+kar\s+(?:dunga|dega|denge|dungi)\b|\bkaat\s+(?:dunga|dega|denge|dalunga|dalega)\b", "any")
_add("threat_kill", rf"\bmaar\s+(?:dalunga|dalungi|dunga|dungi|dalne\s+ki)\b", "any", need=rf"{_ME_HI}|\b(?:bol|kah|dhamk|chilla)\w*\b|\bhume\b|\bhumein\b|\bbachon\b",
     block=r"\bmain\s+(?:use|usse|usko|unhe|unko)\b|^(?!.*\b(?:kaha|bola|bolta|kehta|keh|dhamk\w*|chilla\w*)\b).*\bmain\s+(?:tujhe|tumhe)\b|" + _hi_media)    # "usne kaha main tujhe maar dalunga" is HIS threat
# "he will kill me" in the third person is a threat only when someone says it ("wo bolta hai mujhe maar dalega"); "ye gaana / teacher / mummy mujhe maar dalega" is an idiom
_add("threat_kill", r"\bmaar\s+(?:dalega|dalegi|dalenge|dega|degi|denge)\b", "any", need=r"\b(?:bol|kah|dhamk|chilla)\w*\b|\bhume\b|\bhumein\b|\bbachon\b",
     block=_hi_media + r"|\b(?:teacher|sir|madam|mummy|mom|maa|papa|boss|exam|paper|result|marks|lol|haha+)\b")
_add("kill_maybe", r"\bmujhe\s+maar\s+dal(?:ega|egi|enge)\b", "any",
     need=r"\b(?:pati|husband|bf|boyfriend|gf|girlfriend|biwi|patni|wo|woh)\b", block=_hi_media + r"|\b(?:mummy|papa|mom|dad|maa|boss|teacher|lol|haha+|exam|paper|result|marks|fail)\b")
# the same words with "tonight / now / at the door / a knife" are about to happen: tier 3 ("wo mujhe maar dalega aaj raat")
_add("threat_kill", r"\bmujhe\s+maar\s+dal(?:ega|egi|enge)\b", "any",
     need=r"^(?=.*\b(?:pati|husband|bf|boyfriend|gf|girlfriend|biwi|patni|wo|woh|vo|usne)\b)(?=.*\b(?:aaj|abhi|raat|tonight|darwaza|bahar|chaku|darr|sach\s+mein|pakka)\b)",
     block=_hi_media + r"|\b(?:mummy|papa|mom|dad|maa|boss|teacher|lol|haha+|exam|paper|marks)\b")
_add("threat_kill", r"मुझे\s+मार\s+डाल(?:ेगा|ेगी|ेंगे)", "any",
     need=r"^(?=.*(?:पति|वो|वह|उसने|उन्होंने|बॉयफ्रेंड))(?=.*(?:आज|अभी|रात|दरवाज़|दरवाज|बाहर|चाकू|डर|सच\s+में))", block=r"गाना|गाने|फिल्म|मूवी|सीरीज|सीन|टीचर|मम्मी|पापा|बॉस|एग्जाम|परीक्षा")
_add("kill_maybe", r"मुझे\s+मार\s+डाल(?:ेगा|ेगी|ेंगे)", "any", need=r"पति|वो|वह|उसने|उन्होंने|बॉयफ्रेंड",
     block=r"गाना|गाने|फिल्म|मूवी|सीरीज|सीन|टीचर|मम्मी|पापा|बॉस|एग्जाम|परीक्षा")
# "pati ne kaha aaj tujhe nahi chhodunga": a threat said to the person, reported
_add("threat_kill", r"\b(?:tujhe|tumhe|tujhko|tumko)\s+(?:aaj\s+)?(?:nahi|nhi)\s+chho(?:dunga|dungi|dega|denge)\b", "any", need=r"\b(?:kaha|bola|bolta|kehta|keh|dhamk\w*|chilla\w*)\b")
_add("threat_kill", r"\bjala\s+(?:dunga|dega|denge|dungi|dalunga|dalega|dalenge)\b|\bjala(?:ne|na)\s+ki\s+(?:dhamki|koshish)\b|\bmitti\s+ka\s+tel\b[^.!?]{0,25}\b(?:daal|dala|dalkar|chhida)\w*", "any",
     need=rf"{_ME_HI}|\b(?:pati|husband|sasur|saas|sasural|bf|boyfriend|usne|unhone)\b")
_add("weapon", r"\b(?:chaku|chakku|chaaku|bandook|bandhook|danda|dande|lathi|talwar|kulhadi|pistol|revolver|gun|knife|rod|sariya|hathoda|hammer)\b[^.!?]{0,30}?\b(?:dikha(?:ya|yi|i|ai|ye)|dikha\s+(?:ke|kar)|"
                r"dikhaat[ae]|dikhat[ae]|dikha\s+rah[ae]|tant[aie]|tan\s+(?:deta|deti|dete)|nikalt[ae]|dhamkaat[ae]|dhamkat[ae]|daraat[ae]|"
                r"tan\s+di|taan\s+di|tana|se\s+maara|se\s+mara|se\s+maarta|se\s+maarti|se\s+dhamkaya|se\s+darata|nikala|nikal\s+(?:ke|kar)|uthaya|utha\s+(?:ke|kar)|le\s+(?:ke|kar)|leke|lekar|"
                r"se\s+hamla|se\s+waar|mujh\s*(?:par|pe)|mere\s+upar|gale\s+(?:pe|par))\b", "any")
_add("weapon", r"\b(?:chaku|chakku|chaaku|bandook|bandhook|danda|dande|lathi|talwar|kulhadi|pistol|revolver|gun|knife|rod|sariya|hathoda|hammer)\s+se\s+(?:mujhe|mujhpe|mujh\s*par|meri|mere)\b",
     "any")
_add("sexual", r"\b(?:zabardasti|jabardasti|zabardast[iy])\s+(?:ki|kiya|karta|karte|karna|kar\b|karne|sex|sambandh|se\s+sambandh|relation|physical|chhua|chhoo|touch|kiss|sulaya)\b|"
               r"\b(?:mere\s+saath|mujhse|mujhe)\s+(?:zabardasti|jabardasti)\b|\b(?:balatkar|rape)\s+(?:kiya|karta|kar|ki)\b|\bmere\s+saath\s+(?:balatkar|rape)\b|\bmera\s+balatkar\b|\bmeri\s+marzi\s+(?:ke\s+)?(?:bina|ke\s+khilaf)\b",
     "any", block=r"\b(?:party|shaadi|shadi|hansaya|khilaya|le\s+gaya|le\s+gayi|bulaya|paise)\b")
_add("sexual", r"\bmarzi\s+ke\s+bina\b", "any", need=r"\b(?:sex|sambandh|physical|relation|chhua|touch|pati|husband)\b")
_add("child", r"\b(?:bach(?:ch)?on|bachcho|bacchon|bachche|bachchi|baccho|bete|beti|baby|bachha|bachhi|baccha|kids?)\s+(?:ko|pe|par)\s+(?:\w+\s+){0,2}?"
              r"(?:maar(?:ta|ti|te)|mar(?:ta|ti|te)|pitt(?:a|i)|pit(?:ta|ti|te)|peet-?t(?:a|i|e)|thapp?ad|laat|dhakka|jala\w*|haath\s+uth\w*|haath\s+chala\w*|maar[ae]|maari|maar\s+(?:diya|di|dala|dali)|peet(?:a|i)\b|peet\s+(?:diya|di))\b", "any",
     block=r"\b(?:maine|mainey|mene|main)\s+(?:apne\s+|apni\s+)?(?:bach(?:ch)?on|bachcho|bacchon|bachche|bachchi|bete|beti|baby|bachha|bachhi|baccha)\b")
_add("child", r"\b(?:mujhe|mujhko|muje)\s+(?:aur|or|ya|and|n|&)\s+(?:apne\s+|meri\s+|mere\s+|hamare\s+|humare\s+)?(?:bach(?:ch)?on|bachcho|bacchon|bachche|bachchi|baccho|bete|beti|baby|bachha|bachhi|baccha)\s+(?:ko\s+)?(?:\w+\s+){0,2}?"
              r"(?:maar(?:ta|ti|te)|mar(?:ta|ti|te)|pitt(?:a|i)|pit(?:ta|ti|te)|peet-?t(?:a|i|e)|thapp?ad|laat|dhakka|jala\w*|haath\s+uth\w*|haath\s+chala\w*|maar[ae]|maari|maar\s+(?:diya|di|dala|dali)|peet(?:a|i)\b|peet\s+(?:diya|di))\b", "any")
_add("control", r"\b(?:mera\s+)?phone\s+(?:check|dekh|chhin|chheen|le\s+leta|le\s+leti|le\s+lete|todta|tod\s+diya)\w*|\bmessages?\s+(?:check|padhta|padhti|padhte|dekhta)\b|"
                r"\blocation\s+(?:track|dekhta|pata\s+karta)\w*|\bmeri\s+salary\s+(?:\w+\s+)?(?:le\s+leta|le\s+leti|le\s+lete|chheen|rakh\s+leta)\w*|\bpaise\s+(?:chheen|chhin|le\s+leta|le\s+lete|rakh\s+leta|nahi\s+deta|nahi\s+dete)\w*|"
                r"\bghar\s+se\s+(?:nikalne|bahar\s+nikalne|jaane|jane)\s+(?:nahi|nhi)\s+(?:deta|deti|dete)\b|\bbahar\s+(?:nahi|nhi)\s+jaane\s+(?:deta|deti|dete)\b|"
                r"\b(?:milne|baat\s+karne|jaane|jane|naukri\s+karne|padhne|padhai\s+karne)\s+(?:nahi|nhi)\s+(?:deta|deti|dete)\b|\bkamre\s+(?:mein|me)\s+band\b|\bghar\s+(?:mein|me)\s+band\b|"
                r"\bband\s+kar\s+(?:ke\s+)?rakhta\b|\bnaukri\s+(?:chhodne|chhod\s+dene|chhudwa)\w*|\bpabandi\b|\bjasoosi\b|\bghar\s+se\s+nikaal\s+(?:diya|dega|dunga)\b|"
                r"\bmayke\s+(?:nahi|nhi)\s+jaane\s+(?:deta|deti|dete)\b", "any", need=r"\b(?:mera|meri|mere|mujhe|mujh|pati|husband|wife|biwi|patni|saas|sasur|woh|wo|usne|vo)\b",
     tail=r"^\s+(?:kar(?:na|ne)\s+(?:hai|hain|hein|h|he|padta|padegi|padega|padti|tha|thi|hoga|chahiye|zaroori|ke\s+liye|ko\s+(?:kaha|bola|bolo|kaho))|karun|karu|karoon)\b")
_add("fear", r"\b(?:unse|usse|us\s+se|uss\s+se|pati\s+se|husband\s+se|sasur\s+se|saas\s+se|bf\s+se|boyfriend\s+se|gf\s+se|uske\s+gusse\s+se|unke\s+gusse\s+se)\s+(?:bahut\s+|bohot\s+|kaafi\s+)?"
              r"(?:darr?|dar)\b|\b(?:darr?|dar)\s+(?:lagta|lagti|lagte|raha|rahi|rehta|rahti)\s*(?:hai|h|he)?\s+(?:unse|usse|us\s+se|uss\s+se|pati\s+se|husband\s+se|ghar\s+jaane\s+se)|"
              r"\bghar\s+(?:jaane|jane|wapas\s+jaane|aane)\s+se\s+(?:darr?|dar)\b|\bsafe\s+nahi\s+(?:feel|hoon|hu|lagta|lagti)\b|\bkhatre\s+mein\s+(?:hoon|hu)\b|"
              r"\b(?:daraata|darata|darati|darate)\b|\bdara\s+(?:ke|kar)\s+rakhta\b", "any", need=r"\b(?:mujhe|main|mai|mera|meri|mere|pati|husband|ghar|unse|usse)\b")
_add("verbal", r"\bgaali(?:yan|an)?\s+(?:deta|deti|dete|nikalta|nikalti)\b|\bgali\s+deta\b|\bbeizzat\w*|\bbezzati\b|\bzal[ie]+l\b|\bapmaan\b|\btane\s+(?:deta|deti|marta)\b|"
               r"\bchillata\b|\bchillati\b|\bbadtameezi\b|\bgande\s+naam\b", "any", need=rf"{_ME_HI}|\b(?:mera|meri|mere)\b")
_add("dowry", r"\b(?:dahej|dowry)\b[^.!?]{0,40}\b(?:maang\w*|pareshan\w*|tang\w*|taan\w*|ke\s+liye|torture|pressure|harass\w*)\b|\b(?:maang\w*|pareshan\w*)\b[^.!?]{0,40}\b(?:dahej|dowry)\b",
     "any", need=r"\b(?:mujhe|mera|meri|mere|main|mai|humse|hum)\b")

# ===== Hindi (Devanagari) =====
# "सिर दर्द मुझे मार रहा है", "गर्मी मुझे मारती है": a symptom, the weather or tiredness is not the person who hit (same idea as ``_hi_not_a_person``)
_dv_complaint = r"(?:\S*दर्द\S*|बुखार|गर्मी|सर्दी|ठंड|थकान|थकावट|भूख|नींद|प्यास|खांसी|खाँसी|क्रैम्प्स?|उल्टी|चक्कर|कमज़ोरी|कमजोरी|तनाव|धूप|बारिश|बीमारी|बोझ|याद|एसिडिटी|गैस|जुकाम|जलन|कब्ज़|कब्ज|सूजन|उदासी|अकेलापन|चिंता|फिक्र|परेशानी|परीक्षा|एग्जाम|पेपर|रिज़ल्ट|इंटरव्यू|प्रेजेंटेशन|होमवर्क|असाइनमेंट|ट्रैफिक|पढ़ाई)"
# kitchen and laundry work that is "beaten" (आटा पीटा, कपड़े पीटे, गद्दा पीटा): a thing, not a person
_dv_kitchen = r"आटा|आटे|कपड़े|कपड़ा|कपड़ों|गद्दा|गद्दे|कालीन|दाल|मसाला|मसाले|चटनी|रोटी|रोटियां|पराठा|ढोल|नगाड़ा|तबला|चावल|मक्खन|दही|पनीर|चने|बेसन|धूल|तकिया|तकिये|कढ़ाई|धोना|धोया"
_dv_stop = rf"(?:है|हैं|होता|होती|होते|और|लेकिन|पर|मगर|क्योंकि|जब|था|थी|थे|वह|वो|उसने|उन्होंने|दोस्त|कोई|लोग|सब|घर|{_REL_DV[3:-1]})"
_dv_filler = rf"(?:(?!{_dv_stop}(?:\s|$))[^\s,.!?।]+\s+)"
_dv_kill = r"(?:मार(?:ता|ती|ते)|मार\s+(?:रहा|रही|रहे|दिया|दी|डाला|डाली)|मारा|मारी)"
_dv_not_a_person = (rf"{_dv_complaint}\s+{_dv_filler}{{0,3}}{_dv_kill}|{_dv_kill}\s+{_dv_filler}{{0,3}}{_dv_complaint}\s+ने|"
                    rf"{_dv_kitchen}|"
                    r"गाना|गाने|फिल्म|मूवी|सीरीज|सीन|पबजी|बीजीएमआई|गेमिंग|वीडियो\s+गेम|गोल|छक्का|चौका|कैच|शॉट|गेंद|मैच|क्रिकेट|सेंचुरी|विकेट|बाज़ी|बाजी")
_add("physical", rf"{_ME_DV}[^.!?]{{0,30}}?(?P<v>{_DV_HIT})", "any", play_ok=True, block=_dv_not_a_person)
_add("physical", rf"(?P<v>{_DV_HIT})[^.!?]{{0,15}}?{_ME_DV}", "any", play_ok=True, block=_dv_not_a_person)
# "वो अभी मुझे मार रहा है": happening now. A person must be in the sentence ("माइग्रेन मुझे मार रहा है" is a headache, not a person).
_add("physical", rf"{_ME_DV}[^.!?]{{0,30}}?(?P<v>(?:मार|पीट)\s+(?:रहा|रही|रहे))", "any", play_ok=True, block=_dv_not_a_person,
     need=r"वो|वह|उसने|उन्होंने|पति|पत्नी|बीवी|ससुर|सास|ननद|देवर|जेठ|भाई|पापा|पिता|बॉयफ्रेंड|गर्लफ्रेंड|बीएफ|जीएफ|घर\s*वाले|चाचा|मामा|फूफा|जीजा")
_add("physical", rf"(?:मेरा|मेरी|मेरे)\s+{_REL_DV}\s+(?:\S+\s+){{0,3}}?(?P<v>{_DV_HIT})", "any", play_ok=True)
# "मेरी सास ने मुझे गर्म तेल से जला दिया": burned or branded; a heat word must be there (धूप ने मुझे जला दिया is the sun)
_dv_hot = r"गर्म|गरम|तेल|सिगरेट|बीड़ी|आग|चूल्हा|तवा|केरोसिन|मिट्टी\s+का\s+तेल|पेट्रोल|इस्त्री|प्रेस|चाय|पानी|जलती|जलता"
_add("physical", rf"{_ME_DV}[^.!?]{{0,40}}?(?P<v>जला(?:या|ते|ता|ती)|जला\s+(?:दिया|दी|डाला|डाली)|दाग(?:ा|ते|ता|ती)|दाग\s+दिया)", "any", play_ok=True, need=_dv_hot,
     block=_dv_not_a_person + r"|धूप|सूरज|मिर्च|जलेबी")
# "पति शराब पीकर मारता है": a relation as the subject, no "me" in the sentence (not when it is someone else's relation or someone else is hit)
_add("physical", rf"(?:^|\s){_REL_DV}\s+(?:\S+\s+){{0,4}}?(?P<v>{_DV_HIT})", "any", play_ok=True,
     block=rf"(?:का|की|के|उसका|उसकी|उसके)\s+{_REL_DV}|{_REL_DV}\s+(?:को|पर|पे)\s+(?:\S+\s+){{0,3}}?{_DV_HIT}|(?:उसे|उसको|उन्हें|उनको|बच्चों|बच्चे|बेटे|बेटी|बच्चा|बच्ची|कुत्ते)\s+(?:को\s+)?(?:\S+\s+){{0,3}}?{_DV_HIT}|{_dv_not_a_person}")
_add("physical", r"मारपीट|मार-पीट|मेरी\s+पिटाई|धमकी.{0,20}मारने|मुझे\s+मारने\s+(?:की|आया|आए)", "any", need=r"मुझे|मेरा|मेरी|मेरे|घर|पति")
_add("strangulation", r"गला\s+(?:दबा|घोंट|घोट|पकड़)\w*|गर्दन\s+(?:दबा|पकड़)\w*|(?:गले|गर्दन)\s+(?:पर|पे)\s+हाथ|सांस\s+(?:बंद|रोक)\w*", "any", block=r"खराब|दर्द|सूख")
_add("threat_kill", r"जान\s*से\s*(?:मार|खत्म)\w*|जान\s+ले\s+(?:लूंगा|लूँगा|लेगा|लेंगे)|खत्म\s+कर\s+(?:दूंगा|दूँगा|देगा|देंगे)|ज़िंदा\s+नहीं\s+छोड़|जिंदा\s+नहीं\s+छोड़|काट\s+(?:दूंगा|दूँगा|देगा)", "any")
_add("threat_kill", r"जला\s+(?:दूंगा|दूँगा|देगा|देंगे|डालूंगा|डालेगा)|जलाने\s+की\s+(?:धमकी|कोशिश)|मिट्टी\s+का\s+तेल", "any", need=r"मुझे|मेरी|मेरे|पति|ससुराल|उसने")
_add("threat_kill", r"मार\s+(?:डालूंगा|डालूँगा|दूंगा|दूँगा)", "any", need=r"मुझे|कहा|बोला|धमकी|हमें|बच्चों", block=r"गाना|गाने|फिल्म|मूवी|सीरीज|सीन")
_add("threat_kill", r"मार\s+(?:डालेगा|डालेगी|डालेंगे|देगा|देगी|देंगे)", "any", need=r"कहा|बोला|धमकी|हमें|बच्चों",
     block=r"गाना|गाने|फिल्म|मूवी|सीरीज|सीन|टीचर|मम्मी|पापा|बॉस|एग्जाम|परीक्षा")
_add("weapon", r"(?:चाकू|बंदूक|डंडा|डंडे|तलवार|कुल्हाड़ी|छुरी|लाठी|पिस्तौल|हथौड़ा|हथौड़े|सरिया|सरिये)\s+(?:से|दिखाया|दिखाकर|दिखाता|दिखाती|दिखाते|दिखा\s+रहा|तान|निकाला|निकालता|निकालती|उठाया|लेकर)", "any", need=r"मुझे|मुझ|मेरे|मेरी|पति|उसने|वो|वह|उन्होंने|भाई|पापा|पिता|ससुर|सास|देवर|जेठ|बॉयफ्रेंड",
     block=r"सब्ज़ी|सब्जी|फल|काट\s+रहा|काट\s+रही|केक|प्याज|पकाने|खाना|कुत्ते|कुत्ता|गाय|भैंस|बकरी|साँप|सांप|चूहे|बंदर|जानवर|भगाया|भगाने")
_MALE_DV = r"(?:पापा|पिताजी|पिता|बाप|भाई|चाचा|ताऊ|फूफा|जीजा|दादा|नाना|ससुर|देवर|जेठ)"
_FEMALE_DV = r"(?:मम्मी|माँ|मां|माता|दीदी|बहन|भाभी|दादी|नानी|चाची|बुआ|सास|जेठानी|ननद)"
# "पापा मम्मी को रोज़ मारते हैं": a father or elder beating the mother in the house the person lives in
_add("physical", rf"(?:^|\s){_MALE_DV}\s+(?:ने\s+)?(?:\S+\s+)?{_FEMALE_DV}\s+(?:को|पर|पे)\s+(?:\S+\s+){{0,2}}?(?P<v>{_DV_HIT})", "any", play_ok=True, block=_dv_not_a_person)
_add("sexual", r"मेरी\s+मर्ज़ी\s+के\s+(?:बिना|खिलाफ)|मर्ज़ी\s+के\s+बिना|ज़बरदस्ती|जबरदस्ती|बलात्कार", "any",
     need=r"सेक्स|संबंध|सम्बन्ध|रिश्ता|छुआ|छूना|पति|बलात्कार|मेरे\s+साथ|मुझसे", block=r"पार्टी|शादी|हँसाया|खिलाया|ले\s+गया|ले\s+गई|बुलाया|पैसे")
_add("child", r"(?:बच्चों|बच्चे|बेटे|बेटी|बच्चा|बच्ची)\s+(?:को|पर|पे)\s+(?:\S+\s+){0,2}?(?:मार(?:ता|ती|ते)|पीट(?:ता|ती|ते)|थप्पड़|लात|धक्का|जला\w*|हाथ\s+(?:उठा|चला)\w*)", "any",
     block=r"(?:मैंने|मैं)\s+(?:अपने\s+|अपनी\s+)?(?:बच्चों|बेटे|बेटी|बच्चा|बच्ची|बच्चे)")
_add("control", r"फोन\s+(?:चेक|देख|छीन|ले\s+लेता|ले\s+लेती|तोड़)\w*|मैसेज\s+(?:चेक|पढ़ता|पढ़ती|देखता)|लोकेशन\s+(?:ट्रैक|देखता)\w*|मेरी\s+(?:सैलरी|तनख्वाह)\s+(?:ले\s+लेता|ले\s+लेती|छीन)\w*|"
                r"पैसे\s+(?:छीन|ले\s+लेता|ले\s+लेते|रख\s+लेता)\w*|घर\s+से\s+(?:निकलने|बाहर\s+निकलने|जाने)\s+नहीं\s+(?:देता|देती|देते)|बाहर\s+नहीं\s+(?:निकलने|जाने)\s+(?:देता|देती|देते)|"
                r"(?:मिलने|बात\s+करने|जाने|नौकरी\s+करने|पढ़ने)\s+नहीं\s+(?:देता|देती|देते)|कमरे\s+में\s+बंद|नौकरी\s+(?:छुड़वा|छोड़ने)\w*|पाबंदी|जासूसी", "any",
     need=r"मेरा|मेरी|मेरे|मुझे|पति|पत्नी|बीवी|सास|ससुर|वह|वो|उसने")
_add("fear", r"(?:उनसे|उससे|पति\s+से|ससुर\s+से|सास\s+से|उसके\s+गुस्से\s+से|उनके\s+गुस्से\s+से)\s+(?:बहुत\s+|काफ़ी\s+|काफी\s+)?डर|डर\s+(?:लगता|लगती|लगते)\s+है\s+(?:उनसे|उससे|पति\s+से|घर\s+जाने\s+से)|"
              r"घर\s+(?:जाने|वापस\s+जाने|आने)\s+से\s+डर|सुरक्षित\s+नहीं\s+(?:हूँ|हूं|लगता|लगती)|खतरे\s+में\s+(?:हूँ|हूं)|डराता|डराती", "any", need=r"मुझे|मैं|मेरा|मेरी|मेरे|पति|घर|उनसे|उससे")
_add("verbal", r"गाली(?:याँ|यां)?\s+(?:देता|देती|देते|निकालता|निकालती)|बेइज़्ज़ती|बेइज्जती|अपमान|ताने\s+(?:देता|देती|मारता)|चिल्लाता|चिल्लाती|बदतमीज़ी|गंदे\s+नाम", "any",
     need=r"मुझे|मेरा|मेरी|मेरे")
_add("dowry", r"दहेज[^.!?]{0,40}(?:मांग\w*|परेशान\w*|तंग\w*|ताने|प्रताड़\w*|दबाव)|(?:मांग\w*|परेशान\w*)[^.!?]{0,40}दहेज", "any", need=r"मुझे|मेरा|मेरी|मेरे|मैं|हमसे")


# ===== More everyday wordings (found by a red team): threats, ordinary objects as weapons, restraint, coercion, burning, a swing that missed =====
_add("threat_kill", r"\b(?:nobody|no\s+one)\s+(?:will\s+|would\s+|could\s+)?(?:ever\s+)?(?:find|finds|found)\s+(?:my|our)\s+(?:body|bodies|corpse|remains)\b", "speaker")
# thrown from a height: a balcony, a roof, a window, a bridge ("he said he would throw me off the balcony")
_add("threat_kill", r"\b(?:throw|throws|threw|thrown|throwing|push|pushes|pushed|pushing|toss\w*|fling|flung|hurl\w*|drop|drops|dropped|dropping)\s+me\s+"
                    r"(?:off|from|out\s+of|over|down)\s+(?:the\s+|a\s+|his\s+|her\s+|their\s+|our\s+)?(?:\w+\s+)?(?:balcony|terrace|roof|rooftop|window|bridge|cliff|ledge|building|moving\s+(?:train|car))\b",
     "actor", play_ok=True)
# "he would cut me up", "he said he will chop you into pieces"
_add("threat_kill", r"\b(?:cut|chop|slice|carve|hack|tear)\s+(?:me|you)\s+(?:up|apart|into\s+(?:small\s+)?pieces|to\s+pieces)\b", "actor",
     tail=r"^\s+(?:a|an|some|the|one|two|three|few|another|my|his|her)\b",
     block=r"\b(?:lol|haha+|lmao|jk|joke|jokes|movie|film|game|recipe|cook\w*|vegetables?|onions?|cake|bread)\b")
_add("threat_kill", r"\b(?:kaatne|katne|kaatna|katna|maar\s+dalne|jaan\s+se\s+marne|khatam\s+karne|tukde\s+tukde\s+karne)\s+ki\s+(?:dhamki|baat|koshish)\b", "any")
# a gun pointed: "points it at me" with a weapon named earlier in the sentence
_add("weapon", r"\b(?:point|points|pointed|pointing|aim|aims|aimed|aiming)\s+(?:it|them|that|this|the\s+\w+|a\s+\w+|his\s+\w+|her\s+\w+)\s+(?:right\s+)?at\s+"
               r"(?:me|my\s+(?:head|face|chest|forehead|throat|stomach|back))\b", "actor", need=r"\b" + _weapon + r"\b", block=_WEAPON_BENIGN)
# an ordinary object used or held up against a person: threatened with a stick, a bottle, a chain
_add("weapon", r"\b(?:threaten\w*|waved|waves|waving|brandish\w*|swung|swings|swinging)\s+(?:at\s+)?(?:me\s+)?(?:with\s+)?(?:a|an|the|his|her|their)\s+(?:\w+\s+)?"
               r"(?:stick|bat|belt|rod|pipe|bottle|chain|iron|poker|brick|stone|scissors|shears|hammer|chappal|slipper|shoe|hanger|wire|cable|rope|broom|spanner|wrench|"
               r"screwdriver|axe|ladle|belan|rolling\s+pin|frying\s+pan|cleaver)\b", "actor", block=_WEAPON_BENIGN + r"|\b(?:cricket|football|game|match|baseball|practice)\b")
# "he wrapped his belt around my neck", "she tied a dupatta round my throat" (not a scarf put on for the cold)
_add("strangulation", r"\b(?:wrap\w*|tie|ties|tied|tying|loop\w*|put|puts|tighten\w*|pull\w*|twist\w*)\s+(?:a|an|the|his|her|their)\s+(?:\w+\s+)?"
                      r"(?:belt|rope|cord|dupatta|scarf|cable|wire|chain|towel|sari|saree|string|stole|tie|chunni|chunri)\s+(?:tight(?:ly)?\s+)?(?:a?round|on|over|across)\s+my\s+(?:neck|throat)\b", "close",
     block=r"\b(?:cold|winter|warm|fashion|cute|gift|style|photo|nice|garland|helped\s+me\s+(?:wear|put))\b")
# "he pinned me against the wall by my neck"
_add("strangulation", r"\b(?:pin\w*|hold\w*|held|press\w*|slam\w*|push\w*|shov\w*|lift\w*|grab\w*|drag\w*|pull\w*|lock\w*)\s+me\s+(?:\w+\s+){0,5}?by\s+(?:the|my)\s+(?:neck|throat)\b", "weak")
# face pressed into a pillow, water or the floor
_add("strangulation", r"\b(?:press\w*|push\w*|shov\w*|forc\w*|hold\w*|held|bury|buried|stuff\w*|smash\w*)\s+my\s+(?:face|head)\s+(?:in|into|against|down\s+(?:in|into|on))\s+(?:a\s+|the\s+|his\s+|her\s+)?"
                      r"(?:pillow|pillows|cushion|mattress|bed|blanket|water|bucket|sink|toilet|bathtub|tub|floor|ground)\b", "actor",
     block=r"\b(?:i|we)\s+(?:also\s+|just\s+|then\s+)?(?:press|pressed|push|pushed|bury|buried|hold|held|hid|hide)\b")
# a knee or a foot on the back, ribs or head
_add("physical", r"\b(?:his|her|their)\s+(?:knee|knees|foot|boot|elbow|full\s+weight)\s+(?:on|in|into|against)\s+my\s+(?:back|head|ribs?|stomach|spine|arm)\b", "weak", play_ok=True)
# blows with other names: backhanded, headbutted, elbowed, clobbered, pummelled
_add("physical", r"\b(?:backhand\w*|headbutt\w*|head-butt\w*|elbow(?:s|ed|ing)?|clobber\w*|kneed|kneeing|pummel\w*|bludgeon\w*|pistol-whip\w*)\s+me\b", "elide", play_ok=True,
     tail=r"^\s+(?:a\b|an\b|some\b|the\b)", notpre=_NOT_A_PERSON)
# knocked or slammed to the ground
_add("physical", r"\b(?:knock\w*|slam\w*)\s+me\s+(?:to\s+the\s+(?:ground|floor)|down|over|onto|against|into|on\s+the\s+(?:ground|floor))\b", "weak", play_ok=True,
     block=r"\b(?:dog|puppy|cat|wave|waves|crowd|ball|wind|bike|car|bus|truck|fell|trip\w*|slipp\w*)\b", notpre=_NOT_A_PERSON)
_add("physical", r"\b(?:stomp\w*|stamp\w*|trampl\w*)\s+(?:on|upon)\s+(?:me|my\s+(?:hand|hands|fingers?|foot|feet|arm|back|stomach|chest|head|face|leg|legs))\b", "weak", play_ok=True,
     block=r"\b(?:ants?|insects?|bugs?|cockroach\w*|spider\w*|grapes|wine|snow|puddle|dance|dancing|accidentally)\b", notpre=_NOT_A_PERSON)
# a blow tried, even if it missed ("took a swing at me but missed", "lunged at me")
_add("physical", r"\b(?:took|takes|taking|take)\s+(?:a|an)\s+(?:swing|swipe|punch|slap|kick|lunge|jab|stab)\s+at\s+(?:me|my\s+\w+)\b|"
                 r"\b(?:swung|swings|swinging|lunged|lunges|lunging|swiped|swipes|swiping|lashed\s+out|lashes\s+out)\s+(?:a\s+\w+\s+)?(?:at|towards?)\s+me\b|"
                 r"\bswung\s+(?:his|her|their)\s+(?:fist|hand|arm|belt|stick)\s+at\s+me\b", "weak", play_ok=True,
     block=r"\b(?:dog|puppy|cat|bull|snake|bee|wasp|bird|monkey)\b", notpre=_NOT_A_PERSON)
# "kicks our dog and then me": a person who hurts the pet and then the speaker
_add("physical", r"\b(?:kick|kicks|kicked|hit|hits|beat|beats|slap\w*|punch\w*|throw\w*|threw)\s+(?:the\s+|our\s+|my\s+|his\s+|her\s+)?(?:dog|cat|puppy|kitten|pets?)\s+"
                 r"(?:and|&)\s+(?:then\s+|also\s+|even\s+|later\s+)?(?:me|us|the\s+kids?)\b", "actor", play_ok=True)
# tied, bound or chained to something
_add("physical", r"\b(?:tie|ties|tied|tying|bound|bind|binds|binding|handcuff\w*|chain\w*|strap\w*)\s+me\s+(?:up\s+)?(?:to|on|onto|with|in)\s+(?:the\s+|a\s+|his\s+|her\s+)?"
                 r"(?:bed|chair|pole|pillar|wall|rope|ropes|chains?|cuffs|handcuffs|radiator|window|bars|post|tree|cot|table|bedpost|bedframe)\b|"
                 r"\b(?:tied|ties|tie|tying)\s+(?:my\s+(?:hands|wrists|legs|ankles|feet)|me\s+up\s+with\s+(?:a\s+)?(?:rope|cloth|dupatta|belt|wire|tape|cable|chain))\b", "weak", play_ok=True,
     block=r"\b(?:police|cops?|officers?|rescue|hostage|movie|film|game|scene|series|yoga|sailing|boat|ship|dock)\b")
# burning: a cigarette put out on the skin (the older rule lists the cigarette beside "on me"), a hot ladle, a hot pan
_add("physical", r"\b(?:stub\w*|put|puts|press\w*|extinguish\w*|snuff\w*|grind\w*|ground)\s+(?:out\s+)?(?:a\s+|an\s+|the\s+|his\s+|her\s+|their\s+)?(?:lit\s+)?(?:cigarette|cigar|beedi|bidi|joint|match|lighter|iron|incense)\s+"
                 r"(?:butt\s+|end\s+)?(?:out\s+)?(?:on|onto|against|into)\s+(?:me|my\s+\w+)\b", "weak")
_add("physical", r"\b(?:burn|burns|burned|burnt|burning|scald\w*|brand\w*)\s+(?:me|my\s+(?:hands?|arms?|skin|back|face|legs?|body|chest|foot|feet))\s+with\s+(?:a\s+|an\s+|the\s+|his\s+|her\s+)?"
                 r"(?:hot|heated|boiling|burning|red-hot)\s+(?:ladle|spoon|pan|tawa|iron|rod|knife|oil|water|tea|milk|utensil|tongs|chimta|poker)\b", "weak")
_add("physical", r"\b(?:mera|meri|mere)\s+(?:haath|hath|pair|ungli|ungliyan|chehra|peeth|baah|gaal|pet|haathon|hathon)\b[^.!?]{0,25}?\b(?:garam|tave|tawa|chulh\w+|aag|pateel\w*|jalti|jalte)\b[^.!?]{0,20}?"
                 r"\b(?:rakh|dab|laga|daal|dal|sek|chhu|ghus|dhak)\w*", "any", play_ok=True,
     need=r"\bne\b|\busne\b|\bunhone\b|\bwoh\b|\bwo\b|\bvo\b|\bpati\b|\bhusband\b|\bsaas\b|\bsasur\w*|\bnanad\b|\bjethani\b", block=r"\b(?:khud|apne\s+aap|galti\s+se)\b")
# hair pulled and the person dragged ("baalon se pakad ke ghaseeta")
_add("physical", rf"{_ME_HI}\b[^.!?]{{0,40}}?\bghas[ie]+t\w*", "any", play_ok=True,
     need=r"\bne\b|\busne\b|\bunhone\b|\bwoh\b|\bwo\b|\bvo\b|\bpati\b|\bhusband\b|\bbf\b|\bboyfriend\b|\bsaas\b|\bsasur\w*", block=_hi_media)
_add("physical", r"(?:मेरे\s+)?बाल(?:ों)?\s+(?:से\s+|को\s+)?(?:पकड़|खींच|नोच)\w*|(?:मुझे|मुझको|मेरे)[^.!?]{0,25}?घसीट\w*", "any", play_ok=True,
     need=r"मुझे|मुझको|मेरे|मेरी|मेरा", block=r"मैंने|मैने|खुद|गलती\s+से")
# sexual coercion: "a wife can't refuse", "does things to me that I don't want", "insists on sex and doesn't care that I'm sick"
_add("sexual", r"\b(?:wife|woman|girlfriend|bahu)\s+(?:i\s+|she\s+)?(?:can'?t|cannot|can\s+not|has\s+no\s+right\s+to|isn'?t\s+allowed\s+to|is\s+not\s+allowed\s+to|must\s+not|should\s+not|doesn'?t\s+get\s+to)\s+(?:refuse|say\s+no|deny)\b",
     "any", need=r"\b(?:says?|said|tells?|told|insists?|keeps\s+saying)\b[^.!?]{0,60}\b(?:wife|woman|girlfriend|bahu)\b",
     tail=r"^\s+(?:a|an|the|any|her|his|my|to\s+(?:a|an|the|any|food|sweets|cake|dessert|chai|tea|shopping|ice))\b", block=r"\b(?:lol|haha+|joke|jokes|jokingly|gift|invitation|offer|dessert)\b")
_add("sexual", r"\b(?:do|does|did|doing)\s+(?:things|stuff|something|what\s+he\s+wants|what\s+she\s+wants)\s+(?:to|with)\s+me\b[^.!?]{0,40}\b(?:don'?t|do\s+not|didn'?t|did\s+not|never)\s+(?:want|like|agree|consent)\b",
     "any", block=r"\b(?:doctor|dr|nurse|exam\w*|massage|physio\w*|lol|haha+)\b")
_add("sexual", r"\b(?:insist\w*|pressur\w+|push\w*|demand\w*|expect\w*|nag\w*|badger\w*|guilt\w*|coerc\w+)\s+(?:me\s+)?(?:on|for|into|to\s+have|about)?\s*(?:having\s+)?(?:sex|intercourse|sexual\s+\w+|intimacy)\b",
     "close", need=r"\b(?:doesn'?t\s+care|does\s+not\s+care|even\s+when|even\s+if|although|though|i'?m\s+(?:sick|tired|ill|unwell|exhausted|in\s+pain|bleeding)|i\s+(?:am|feel)\s+(?:sick|tired|ill|unwell|exhausted|in\s+pain)|"
                       r"not\s+in\s+the\s+mood|no\s+mood|don'?t\s+want|do\s+not\s+want|say\s+no|said\s+no|refuse\w*|can'?t\s+say\s+no|painful|every\s+(?:night|day)|nightly|against\s+my)\b",
     block=r"\b(?:doctor|dr|nurse|therapist|counsel\w*|article|blog|podcast|book|lol|haha+)\b")
# intimate images used to threaten: recorded naked, "will post it if I leave" (a control of the worst kind: the reply is the soft Safe Harbor voice)
_add("control", r"\b(?:record\w*|film\w*|photograph\w*|took\s+(?:photos?|pictures?|pics?|videos?)\s+of|secretly\s+(?:record|film))\s+me\s+(?:naked|nude|undressed|without\s+(?:clothes|my\s+knowledge|my\s+permission|my\s+consent)|"
                r"in\s+the\s+(?:bath|shower|bathroom)|having\s+sex)\b", "close_or_family")
_add("control", r"\b(?:will|would|'ll|is\s+going\s+to|gonna|threatens?\s+to|threatened\s+to)\s+(?:post|share|leak|upload|send|spread|put)\s+(?:it|them|those|my\s+(?:nudes?|photos?|pictures?|pics?|videos?)|"
                r"the\s+(?:nudes?|photos?|pictures?|pics?|videos?|clips?))\b[^.!?]{0,40}\b(?:if\s+i|unless\s+i|online|everywhere|to\s+everyone|to\s+my\s+(?:family|parents|friends))", "close_or_family")
# locked in with the keys taken
_add("control", r"\b(?:lock\w*|bolt\w*|latch\w*)\s+(?:the\s+|our\s+|my\s+)?(?:main\s+|front\s+|back\s+|house\s+)?(?:door|gate|house|room|flat|home)\b[^.!?]{0,40}?\b"
                r"(?:took|takes|take|taken|hid|hides|hidden|keeps?|kept|has|snatched|confiscated|hold|holds|held)\s+(?:my|the|all)\s+(?:house\s+|door\s+|home\s+|car\s+)?(?:keys?|phone|chaabi|chabi)\b", "close_or_family",
     block=r"\b(?:when|before|while|as|after)\s+(?:he|she|they)\s+(?:left|leaves|leaving|went|goes|going|was\s+leaving)\b|\bfor\s+work\b|\bto\s+(?:go\s+to|drive|drop|pick|fetch|buy|get)\b")
_add("control", r"\b(?:took|takes|hid|hides|snatched|confiscated|hidden)\s+(?:my|the|our)\s+(?:house\s+|door\s+|home\s+)?keys\b", "close_or_family",
     need=r"\b(?:lock\w*|trapped|stuck\s+(?:at|in)\s+(?:the\s+)?(?:house|home)|(?:can'?t|cannot|couldn'?t|unable\s+to|not\s+allowed\s+to)\s+(?:\w+\s+)?(?:leave|go\s+out|get\s+out|step\s+out|exit))\b",
     block=r"\b(?:when|before|while|as|after)\s+(?:he|she|they)\s+(?:left|leaves|leaving|went|goes|going|was\s+leaving)\b|\bfor\s+work\b|\bto\s+(?:go\s+to|drive|drop|pick|fetch|buy|get)\b")

# ===== Passive voice, "my husband beats" with no object, someone else's story, and a person who says they hurt someone =====
_STRONG_PASSIVE = {"beaten": "physical", "beat": "physical", "slapped": "physical", "punched": "physical", "kicked": "physical", "thrashed": "physical",
                   "battered": "physical", "spanked": "physical", "whacked": "physical", "smacked": "physical", "assaulted": "physical",
                   "choked": "strangulation", "strangled": "strangulation"}
_WEAK_PASSIVE = {"hit": "physical", "pushed": "physical", "shoved": "physical", "dragged": "physical", "attacked": "physical", "burned": "physical",
                 "burnt": "physical", "abused": "verbal"}
_PASSIVE = _c(r"\bi\s*(?:'m|am)?\s*(?:was|am|got|get|gets|been|have\s+been|had\s+been|keep\s+getting|kept\s+getting|am\s+getting|was\s+getting|am\s+being|was\s+being|being)\s+"
              r"(?:\w+\s+)?(?P<v>beaten|beat|slapped|punched|kicked|choked|strangled|thrashed|battered|assaulted|hit|pushed|shoved|dragged|attacked|spanked|whacked|smacked|abused|burned|burnt)\b"
              r"(?:\s+up)?(?:\s+by\s+(?P<by>[^.,!?]{1,40}))?")
_FIGURATIVE_BY = _c(r"\bby\s+(?:the|a|an|that|this|how|what|such)\s+(?:\w+\s+){0,2}?(?:news|sight|thought|realisation|realization|fact|feeling|grief|loss|reality|announcement|email|text|message|"
                    r"results?|prices?|bill|amount|cost|sound|smell|beauty|speech|performance|ending|plot|twist|film|movie|song|story|layoffs?|jokes?|surprise|compliments?)\b")
# who did it, named right after "by": him, her, them, he, my husband, his mother in law, my drunk father ... (a car or a stranger is not it)
_BY_ACTOR = _c(rf"(?:my\s+|his\s+|her\s+|their\s+|our\s+|the\s+)?(?:\w+\s+)?(?:he|him|she|her|they|them|{_PARTNER}|{_INLAW}|{_FAMILY})\b")
_FAIR_GAME = _c(r"\b(?:chess|ludo|carrom|monopoly|poker|cards|sudoku|quiz|tournament|competition|contest|race|bet|election|exam|marks|score|ranking|rank)\b")
_OUT_OF = _c(r"^\s+(?:out|off|from)\s+(?:of\s+)?(?:the\s+|a\s+|my\s+)?(?:group|chat|whatsapp|team|club|class|school|college|server|channel|game|party|office|job|league|app|forum|community|discord|event|flight|bus|train|cafe|restaurant|mall|theatre|theater|bar)\b")
_SPORTY = _c(r"\b(?:football|cricket|match|game|games|sports?|gym|practice|training|tournament|playing|played|hockey|kabaddi|badminton|tennis|basketball|rugby|volleyball|"
             r"accident|crash|bike|car|bus|truck|scooter|dog|horse|bull|cow)\b")
_HURT_NOW = _c(r"\b(?:bleed\w*|bruis\w*|swoll\w*|swell\w*|injur\w*|black\s+and\s+blue|in\s+pain|blood)\b")
_NOT_AN_ASSAULT = _c(r"\b(?:car|bike|bus|truck|train|auto|scooter|ball|cricket|football|game|match|sports?|gym|fell|fall|fallen|accident\w*|crash\w*|stone|branch|door|wall|floor|stairs?|"
                     r"tripped|slipped|ceiling|fan|bat|puck|bee|wasp|dog|bull|cow|lightning)\b")
_NOOBJ = _c(rf"\bmy\s+(?:{_PARTNER}|{_INLAW}|{_FAMILY})\s+(?:\w+\s+){{0,2}}?(?:beats|hits|slaps|punches|kicks|chokes|strangles|batters|thrashes)\b"
            r"(?=\s*(?:$|[,.!?]|every|daily|a\s+lot|often|regularly|always|when|if|badly|up\b|because|whenever|again|so\b))")
_OTHER = (
    _c(rf"\b(?:her|his|their|my\s+\w+'s|\w+'s)\s+(?:{_PARTNER}|{_INLAW}|dad|father|mom|mother)\s+(?:\w+\s+){{0,2}}?(?:hits|beats|slaps|punches|kicks|abuses|chokes|strangles|hurts|batters|burns|assaults)\b"),
    _c(rf"\b(?:is|are|being|gets|got)\s+(?:being\s+)?(?:beaten|hit|abused|battered|slapped)\s+by\s+(?:her|his|their)\s+(?:{_PARTNER}|{_INLAW}|dad|father|mom|mother)\b"),
    _c(rf"\b(?:uska|uski|uske|unka|unki|unke)\s+{_REL_HI}\s+(?:\w+\s+){{0,2}}?(?:usse|use|usko|unhe|unko)\s+(?:\w+\s+){{0,2}}?(?:maar(?:ta|ti|te)|mar(?:ta|ti|te)|pitt(?:a|i)|pit(?:ta|ti|te)|pitai)\b"),
    _c(r"(?:उसका|उसकी|उसके|उनका|उनकी|उनके)\s+\S+\s+(?:उसे|उसको|उन्हें|उनको)\s+(?:\S+\s+){0,2}?(?:मारता|मारती|मारते|पीटता|पीटती|पीटते)"),
)

_I_ADV = (r"(?:(?:have|had|just|also|again|even|actually|really|literally|accidentally|only|once|recently|sometimes|always|often|did|do|keep|kept|started|finally|then)\s+|"
          r"(?:lost\s+(?:control|my\s+temper|my\s+cool)|got\s+(?:so\s+)?angry|snapped)\s+(?:and\s+)?)*")
_OBJ_PARTNER = (rf"(?:her|him|them|my\s+(?:{_PARTNER}|kids?|children|child|son|daughter|baby)|our\s+(?:kids?|children|child|son|daughter|baby)|the\s+(?:kids?|children|child))")
_PERP = (
    _c(rf"\bi\s+{_I_ADV}(?:hit|slapped|slap|punched|punch|kicked|kick|beat|choked|strangled|thrashed|spanked|hits|beats|slaps|punches|kicks|burned|burnt)\s+{_OBJ_PARTNER}\b"
       r"(?!\s+(?:up\b|back\b|at\b|out\b|off\b|in\s+(?:the\s+)?(?:race|game|chess|ludo|carrom|cricket|quiz|match|exam)|to\s+(?:it|the)\b|with\s+(?:a\s+)?(?:joke|pillow)))"),
    _c(rf"\bi\s+{_I_ADV}(?:pushed|shoved|dragged|grabbed|threw)\s+{_OBJ_PARTNER}\s+(?:down|away|against|around|aside|over|onto|off|out\s+of|by\s+the\s+(?:hair|arm|neck))"),
    # "I get so angry that I raise my hand on my girlfriend": a few words may sit between, none of them a negation or a wish
    _c(rf"\bi\s+(?:(?!(?:never|not|no|didn|don|won|can|couldn|wouldn|if|wish|hope|would|should|could|promise\w*|try|tried|trying|afraid|scared|worried|fear\w*|stop\w*)\b)\w+\s+){{0,7}}?"
       rf"(?:raise|raised|raises|lift|lifted|lifts)\s+my\s+(?:hand|hands|fist|fists)\s+(?:at|on|against|to)\s+{_OBJ_PARTNER}\b"),
    _c(rf"\bi\s+(?:get|got|become|became|turn|turned|am|was)\s+(?:so\s+|very\s+)?(?:violent|physical|abusive)\s+(?:with|towards?|to)\s+{_OBJ_PARTNER}\b"),
    _c(r"\b(?:maine|mainey|mene|maene|mai\s*ne|main\s*ne)\s+(?:\w+\s+){0,3}?(?:usse|use|usko|usey|unhe|unko|apni\s+\w+|apne\s+\w+|biwi|patni|wife|gf|girlfriend|pati|husband|bf|boyfriend|bachon|bachchon|bete|beti|bachche)\s+"
       r"(?:\w+\s+){0,2}?(?:ko\s+)?(?:maara|mara|maar\s+diya|peeta|pita|peet\s+diya|thappad|thapad|laat|dhakka|haath\s+uthaya|gala\s+dabaya|mukka|ghoonsa)\b"),
    _c(r"\b(?:maine|mainey|mene|maene|mai\s*ne|main\s*ne)\s+(?:usse|use|usko|usey|unhe|unko|biwi\s+ko|patni\s+ko|wife\s+ko|pati\s+ko|husband\s+ko|gf\s+ko|bf\s+ko)?\s*"
       r"(?:thappad|thapad|laat|dhakka|mukka|ghoonsa)\s+(?:mara|maara|mari|maari|diya|jad\s+diya|lagaya)\b"),
    _c(r"\bmaine\s+(?:\w+\s+){0,3}?haath\s+uthaya\b"),
    _c(r"\bmain\s+(?:apni\s+|apne\s+)?(?:biwi|patni|wife|gf|girlfriend|pati|husband|bf|boyfriend|bachon|bachchon|bete|beti|use|usse|usko)\s+(?:ko\s+)?(?:\w+\s+){0,2}?"
       r"(?:(?:maarta|marta|peetta|pitta|maarti|marti)\s*(?:hoon|hu|hun|hai)|(?:peet|pit|maar|mar)\s+(?:deta|deti|dunga|dungi|diya|di)\s*(?:hoon|hu|hun)?)\b"),
    # saying they WANT to hurt their partner or child ("I want to hurt my wife, I am so angry at her"): the same accountability copy, before anything happens
    _c(rf"\b(?:i\s+(?:really\s+|just\s+|so\s+)?(?:want|wanna|will)|i'?m\s+(?:going\s+to|gonna)|i\s+am\s+going\s+to|i'll)\s+(?:to\s+)?(?:hurt|hit|beat|slap|punch|kick|harm|strangle|choke|kill)\s+"
       rf"my\s+(?:{_PARTNER}|kids?|children|child|son|daughter|baby)\b"),
    _c(rf"\bi\s+feel\s+like\s+(?:hurting|hitting|beating|slapping|punching|kicking|strangling|choking|killing)\s+my\s+(?:{_PARTNER}|kids?|children|child|son|daughter|baby)\b"),
    _c(r"(?:मैंने|मैने)\s+(?:\S+\s+){0,3}?(?:उसे|उसको|उन्हें|उनको|अपनी\s+\S+|अपने\s+\S+|पत्नी|बीवी|पति|बच्चों|बेटे|बेटी)\s+(?:\S+\s+){0,2}?(?:को\s+)?(?:मारा|पीटा|मार\s+(?:दिया|दी|डाला)|पीट\s+(?:दिया|दी)|थप्पड़\s+(?:मारा|मार\s+दिया|लगाया|लगा\s+दिया|जड़\s+दिया)|लात\s+(?:मारी|मार\s+दी)|धक्का\s+(?:दिया|दे\s+दिया)|हाथ\s+उठाया|गला\s+दबाया)"),
    # "mujhse gusse mein pati par haath uth gaya": a hand raised against a partner, said as something that happened through the speaker
    _c(r"\b(?:mujhse|mujhse|mere\s+se)\b[^.!?]{0,40}?\b(?:biwi|patni|wife|gf|girlfriend|pati|husband|bf|boyfriend|bachon|bachchon|bete|beti|bachche|use|usse|usko)\s+"
       r"(?:par|pe|per|ke\s+upar|ko)\s+(?:\w+\s+){0,2}?(?:haath|hath)\s+(?:bhi\s+)?(?:uth|utha|chal)\w*"),
    _c(r"मैं\s+(?:अपनी\s+|अपने\s+)?(?:पत्नी|बीवी|पति|बच्चों|बेटे|बेटी|उसे|उसको)\s+(?:को\s+)?(?:\S+\s+){0,2}?(?:मारता|मारती|पीटता|पीटती)\s+(?:हूँ|हूं)"),
)


# --------------------------------------------------------------------------
# What a message holds
# --------------------------------------------------------------------------

@dataclass
class _Hit:
    family: str
    sent: int
    status: str        # live | hypo | hypo_ask | past | ignore


_I_BEFORE = _c(r"\b(?:i|we)\s+(?:also\s+|just\s+|then\s+|even\s+)*$")


def _segment(sent: str, start: int) -> str:
    """The words before the match in the same clause (cut at when / because / that / but ...)."""
    pre = sent[:start]
    cut = 0
    for m in _BOUND.finditer(pre):
        cut = m.end()
    return pre[cut:]


def _actor_ok(rule: _Rule, sent: str, start: int, hist_actor: bool) -> bool:
    mode = rule.mode
    if mode == "any":
        return True
    seg = _segment(sent, start)
    if mode == "speaker":
        return not _I_BEFORE.search(seg)
    if mode == "partner":
        return bool(_PARTNER_RX.search(seg[-80:]))
    if mode == "pronoun":
        return bool(_PRONOUN_RX.search(seg[-40:]))
    if mode == "close":
        return bool(_CLOSE_RX.search(seg[-80:]))
    if _ACTOR_RX.search(seg[-80:]):
        return True
    if mode == "close_or_family":
        return False
    if mode == "actor":
        return hist_actor and not seg.strip()
    elided = bool(_ELIDED.fullmatch(seg.strip()) or not seg.strip())
    return elided and (mode == "elide" or hist_actor)


def _in_quote(pre: str) -> bool:
    """Inside "double" or 'single' quotes: someone else's words, a title or a lyric."""
    if pre.count('"') % 2 == 1:
        return True
    return len(re.findall(r"(?<!\w)'(?=\w)", pre)) > len(re.findall(r"(?<=\w)'(?!\w)", pre))


class _Sent:
    """One sentence and what every mention in it shares, worked out once: a message made of repeats must stay fast (8000 characters is the limit)."""

    def __init__(self, text: str, nxt: str):
        self.text = text
        self.played = bool((_PLAY.search(text) or _ACCIDENT.search(text)) and not _PLAY_BLOCK.search(text))   # play or an accident, with no injury or fear
        say = _SAY_THREAT.search(text)
        cues = sorted((m.start(), m.group()) for rx in (_PLAIN_HYPO, _ASK_HYPO) for m in rx.finditer(text))
        self.cues = [(pos, word) for pos, word in cues if say is None or say.start() >= pos]     # after "he said ..." an "if" is part of what was said
        self.asking = bool(_ASK_HYPO.search(text) or _AGAIN.search(text))
        self.past = bool((_PAST.search(text) and not _RECENT.search(text)) or _PAST_NEXT.match(nxt))


_MAX_PER_RULE = 6      # a sentence needs one live mention to count; more only costs time


def _status(rule: _Rule, sc: _Sent, start: int, end: int) -> str:
    """Is the mention at ``start``..``end`` (the verb) a live disclosure? ignore | hypo | hypo_ask | past | live."""
    sent = sc.text
    pre, post = sent[:start], sent[end:]
    neg = _NEG_BEFORE.search(pre[-40:])
    if neg and not _NEG_EXC.search(neg.group() + " " + sent[start:end]) and not _NEG_BUT.search(post[:200]):
        return "ignore"
    if _NEG_AFTER.match(post):
        return "ignore"
    if rule.play_ok and (sc.played or _in_quote(pre)):
        return "ignore"                                      # play, an accident, or someone else's words in quotes
    for pos, word in sc.cues:
        if pos >= start:
            break
        if word in {"agar", "agr", "अगर", "यदि"} and _INDICATIVE_AFTER.match(post):
            continue                                         # "agar main bolun toh woh mujhe maarta hai": a habit, not a what-if
        return "hypo_ask" if sc.asking else "hypo"
    return "past" if sc.past else "live"


def _scan(sents: list[str], hist_actor: bool) -> list[_Hit]:
    hits: list[_Hit] = []
    for i, sent in enumerate(sents):
        sc = _Sent(sent, sents[i + 1] if i + 1 < len(sents) else "")
        for rule in _R:
            if rule.need and not rule.need.search(sent):
                continue
            if rule.block and rule.block.search(sent):
                continue
            for m in islice(rule.rx.finditer(sent), _MAX_PER_RULE):
                if rule.tail and rule.tail.match(sent[m.end():m.end() + 80]):
                    continue
                if rule.notpre and rule.notpre.search(sent[max(0, m.start() - 40):m.start()]):
                    continue
                if not _actor_ok(rule, sent, m.start(), hist_actor):
                    continue
                vs, ve = (m.start("v"), m.end("v")) if "v" in rule.rx.groupindex else (m.start(), m.end())   # the verb decides negation and tense
                hits.append(_Hit(rule.family, i, _status(rule, sc, vs, ve)))
        for m in islice(_PASSIVE.finditer(sent), _MAX_PER_RULE):
            verb, by = m.group("v"), (m.group("by") or "").strip()
            if _FIGURATIVE_BY.search(sent[m.end():m.end() + 70]):
                continue                                     # "punched in the gut by the news"
            family = _STRONG_PASSIVE.get(verb) or _WEAK_PASSIVE[verb]
            if by:
                if not _BY_ACTOR.match(by):
                    continue                                 # "hit by a car", "slapped by a stranger", "hit by a car ... and my wife came" (the doer comes first)
            elif verb in _STRONG_PASSIVE and (_SPORTY.search(sent) or _FAIR_GAME.search(sent) or _OUT_OF.match(sent[m.end():m.end() + 40])) and not _ACTOR_RX.search(sent):
                continue                                     # "I got kicked in the shin during football practice", "I was beaten at chess", "kicked out of the group"
            elif verb in _WEAK_PASSIVE:
                if _HURT_NOW.search(sent) and not _NOT_AN_ASSAULT.search(sent):
                    hits.append(_Hit("unclear", i, _status(_PLAYFUL, sc, m.start(), m.end())))     # "I was hit and I am bleeding": nobody named, but hurt: a safety check
                continue
            hits.append(_Hit(family, i, _status(_PLAYFUL, sc, m.start(), m.end())))
        for m in islice(_NOOBJ.finditer(sent), _MAX_PER_RULE):
            hits.append(_Hit("physical", i, _status(_PLAYFUL, sc, m.start(), m.end())))
    return hits


_PLAYFUL = _Rule("physical", _ACTOR_RX, "any", play_ok=True)      # stands for "a hit that play, an accident or a quote can excuse"


def _about_other(sents: list[str]) -> bool:
    return any(rx.search(s) for s in sents for rx in _OTHER)


_SPORT = _c(r"\b(?:boxing|sparring|karate|judo|taekwondo|wrestling|mma|gym|training|tournament|ring|rugby|football|cricket|hockey|kabaddi|game|match)\b")


_CHILD_WORD = _c(r"\b(?:kids?|children|child|son|daughter|baby|bete|beti|bachch?\w*|bacch\w*)\b|बच्च|बेटे|बेटी")


def _perpetrator(sents: list[str]) -> tuple[bool, bool]:
    """(the person says they hurt someone close, and the one hurt is a child). A parent who hits a child is offered Childline beside Tele-MANAS."""
    for i, sent in enumerate(sents):
        if _SPORT.search(sent):
            continue
        sc = _Sent(sent, sents[i + 1] if i + 1 < len(sents) else "")
        for rx in _PERP:
            for m in islice(rx.finditer(sent), _MAX_PER_RULE):
                if _status(_PLAYFUL, sc, m.start(), m.end()) == "live":
                    return True, bool(_CHILD_WORD.search(m.group()))
    return False, False


@dataclass
class Detection:
    """What the words of one message say, before any state about the conversation is taken into account."""
    tier: int = 0
    perpetrator: bool = False
    about_other: bool = False
    past_only: bool = False          # an act is described but it is over: a gentle check, not an emergency
    child_at_risk: bool = False
    families: tuple[str, ...] = ()
    lang: str = "en"


def _history_actor(history: list[dict[str, Any]] | None) -> bool:
    rows = [r for r in (history or []) if isinstance(r, dict) and r.get("role") == "user"][-3:]
    return any(_HIST_ACTOR.search(_norm(r.get("content"))) for r in rows)


def detect(text: Any, history: list[dict[str, Any]] | None = None) -> Detection:
    """Read one message. Pure; no state. ``history`` (recent rows of the conversation) only helps to tell who "kicked me" means."""
    original = str(text or "")[:8000]
    norm = _norm(original)
    if not norm:
        return Detection()
    sents = _split(norm)
    lang = detect_language(norm)
    hits = _scan(sents, _history_actor(history))
    live = [h for h in hits if h.status == "live"]
    families = {h.family for h in live}
    physical = bool(families & {"physical"})
    high = families & {"strangulation", "threat_kill", "weapon", "sexual", "child", "imminent"}
    soft = families & {"control", "fear", "verbal", "dowry", "kill_maybe", "unclear"}
    soft_hypo = any(h.status == "hypo_ask" for h in hits)
    past_acts = any(h.status == "past" and h.family in {"physical", "strangulation", "threat_kill", "weapon", "sexual", "child"} for h in hits)
    escalation = bool(_ESC_STRONG.search(norm)) or any(_ESC_WORDS.search(sents[h.sent]) for h in live if h.family in {"physical", "strangulation"})
    pregnant = bool(_PREGNANT.search(norm))
    fearful = "fear" in families or bool(_FEAR_CUE.search(norm))
    act = physical or bool(high)
    other = _about_other(sents)
    if high:
        tier = TIER_EXPLICIT
    elif physical:
        tier = TIER_EXPLICIT if (pregnant or escalation or fearful) else TIER_GENTLE
    elif soft or soft_hypo or past_acts:
        tier = TIER_LITE
    else:
        tier = TIER_NONE
    perpetrator, child_hurt = _perpetrator(sents) if tier < TIER_GENTLE else (False, False)
    return Detection(
        tier=tier, perpetrator=perpetrator, about_other=other and not act and not perpetrator,
        past_only=past_acts and not act, child_at_risk="child" in families or child_hurt, families=tuple(sorted(families)), lang=lang,
    )


# --------------------------------------------------------------------------
# The result: tier, voice, and what to store
# --------------------------------------------------------------------------

OPTIONS = ("talk_more", "safety_plan", "show_help", "okay_for_now")             # what a person who was hurt is offered
OPTIONS_SELF = ("talk_more", "cool_down", "show_help", "okay_for_now")          # what a person who hurt someone is offered
_STEP_OF = {"listen": "options", "talk_more": "talking", "safety_plan": "plan", "show_help": "help", "okay_for_now": "closed", "cool_down": "calm", "urgent": "options"}
_OPTION_RX = {
    "okay_for_now": _c(r"\b(?:i'?m|i\s+am)\s+(?:okay|ok|fine|alright)\s+for\s+now\b|\bokay\s+for\s+now\b|\b(?:abhi|filhal)\s+(?:ke\s+liye\s+)?(?:main\s+)?(?:theek|thik|sahi|okay|ok)\b|"
                       r"\bmain\s+(?:abhi\s+)?(?:theek|thik)\s+(?:hoon|hu|hun)\b|अभी\s+(?:के\s+लिए\s+)?(?:मैं\s+)?ठीक|मैं\s+ठीक\s+हूँ|मैं\s+ठीक\s+हूं"),
    "safety_plan": _c(r"safety\s+plan|make\s+a\s+plan|plan\s+bana|suraksha\s+yojana|सुरक्षा\s+योजना|सेफ्टी\s+प्लान|प्लान\s+बना"),
    "show_help": _c(r"who\s+can\s+help|show\s+me\s+who|help\s*lines?|kaun\s+(?:madad|help)|kisse\s+madad|madad\s+kaun|कौन\s+मदद|मदद\s+कौन|हेल्पलाइन"),
    "talk_more": _c(r"talk\s+more|want\s+to\s+talk|baat\s+karni|baat\s+karna|aur\s+baat|और\s+बात|बात\s+करन"),
    "cool_down": _c(r"cool\s+down|calm\s+down|shaant|शांत"),
}


# Inside a live Safe Harbor conversation, a message is a follow-up unless it plainly asks about something else. "What cream can I use for the bruise" and "what
# should I eat for dinner" are answered as usual; "what should I do" and "should I tell my mom" stay in the Safe Harbor voice. A topic word alone never ends the voice:
# it must be a question and have no word about the person, the home, fear, harm or help in it.
_TOPIC = _c(r"\b(?:eat|eating|ate|food|hungry|hunger|dinner|lunch|breakfast|snack|snacks|recipe|diet|calories?|protein|khana|khaun|khaane|nashta|bhookh|cream|ointment|lotion|"
            r"medicine|medication|tablets?|pills?|painkillers?|paracetamol|dawai|dawa|sleep|slept|water|steps|walk|walking|workout|exercise|gym|weight|vitamins?|supplements?|"
            r"period|periods|cycle|ovulation|headache|fever|cold|cough|bruise|bruises|swelling|swollen|compress|wound|scar|rash|"
            r"joke|weather|news|movie|song|music|cricket|football|score|price|study|homework|salary|travel|flight|shopping|laptop|app|code|python|maths?|history|capital|translate)\b|"
            r"खाना|क्रीम|दवाई|दवा|नींद|पानी|मौसम|गाना|फिल्म")
_ASKING = _c(r"\?|\b(?:what|which|how\s+(?:much|many|long|do|can|to)|should\s+i|can\s+i|could\s+i|kya|kaise|kitna|konsa|kaunsa|kab|kahan)\b|क्या|कैसे|कौन")
_ABOUT_THE_PERSON = _c(r"\b(?:he|him|his|she|her|they|them|husband|wife|partner|boyfriend|girlfriend|in-?laws?|pati|patni|biwi|saas|sasur|sasural|ghar|home|house|scared|afraid|fear|"
                       r"unsafe|danger\w*|hit|hits|hurt|hurts|beat|beats|slap\w*|punch\w*|kick\w*|threat\w*|kill|abus\w*|violen\w*|helpline|police|escape|darr|dar|madad|help)\b|"
                       r"पति|पत्नी|बीवी|ससुराल|घर|डर|मदद")
# Someone is badly hurt right now (said inside a Safe Harbor conversation: "she is bleeding badly"). The number comes first, in the same voice.
_URGENT_NOW = _c(r"\b(?:bleeding\s+(?:badly|heavily|a\s+lot|alot|profusely)|not\s+breathing|can'?t\s+breathe|unconscious|passed\s+out|not\s+(?:moving|waking|responding)|won'?t\s+wake|"
                 r"collapsed|unresponsive|badly\s+(?:hurt|injured)|seriously\s+(?:hurt|injured)|khoon\s+beh|behosh|saans\s+nahi|hosh\s+nahi)\b|बेहोश|खून\s+बह|सांस\s+नहीं|होश\s+नहीं")


def _off_topic(t: str) -> bool:
    return bool(_TOPIC.search(t) and _ASKING.search(t) and not _ABOUT_THE_PERSON.search(t))


def pick_option(text: Any, mode: str = "victim") -> str:
    """Which of the offered choices the message is (a tapped chip arrives as its label), else "listen"."""
    t = _norm(text)
    for option in ("okay_for_now", "safety_plan", "cool_down", "show_help", "talk_more"):
        if option == "safety_plan" and mode == "perpetrator":
            continue
        if option == "cool_down" and mode != "perpetrator":
            continue
        if _OPTION_RX[option].search(t):
            return option
    return "listen"


@dataclass
class HarborContext:
    """What is known before the message is read. Everything is optional; the empty context means a new conversation, India, gender unknown."""
    state: dict[str, Any] | None = None     # the harbor_state document of this conversation
    flag: dict[str, Any] | None = None      # the harbor_flag document of this person
    country: Any = None                     # not asked yet (setup v2): None means India
    gender: Any = None
    message_id: str | None = None
    now: datetime | None = None
    flag_read: bool = False                 # the flag was looked up (even if there is none yet), so ``record`` need not read it again


@dataclass
class Harbor:
    """One message, understood. ``tier`` is what THIS message says; ``level`` is how serious the conversation now is (a follow-up keeps it)."""
    tier: int = 0
    perpetrator: bool = False
    about_other: bool = False
    past_only: bool = False
    child_at_risk: bool = False
    families: tuple[str, ...] = ()
    lang: str = "en"
    level: int = 0
    mode: str = "victim"                  # victim | perpetrator: whose voice the follow-ups use
    followup: str | None = None           # None | listen | talk_more | safety_plan | show_help | okay_for_now | cool_down
    step: str | None = None               # what the conversation state becomes after this reply
    repeat: bool = False                  # raised to tier 3 because a second tier 2 came within 30 days
    pause_partner_signals: bool = False   # tier 1 and above: partner weather from this person stops (plan 7.5); stored as the harbor_flag
    country: Any = None
    gender: Any = None

    @property
    def deterministic(self) -> bool:
        """True when the reply is fixed copy and no outside model may see the message."""
        return self.tier >= TIER_GENTLE or self.perpetrator or self.followup is not None

    def without_followup(self) -> "Harbor":
        return replace(self, followup=None, step=None, level=self.tier)


def _parse_time(value: Any) -> datetime | None:
    try:
        when = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)


def _live_state(state: dict[str, Any] | None, now: datetime) -> dict[str, Any] | None:
    if not isinstance(state, dict) or state.get("step") in (None, "closed"):
        return None
    when = _parse_time(state.get("updated_at"))
    return state if when is None or now - when <= timedelta(hours=STATE_HOURS) else None


def _prior_events(flag: dict[str, Any] | None, now: datetime, message_id: str | None) -> int:
    count = 0
    for event in (flag or {}).get("events") or []:
        when = _parse_time(event.get("at")) if isinstance(event, dict) else None
        if when and now - when <= timedelta(days=REPEAT_DAYS) and event.get("m") != message_id and int(event.get("t") or 0) >= TIER_GENTLE:
            count += 1
    return count


def assess(text: Any, history: list[dict[str, Any]] | None = None, ctx: HarborContext | None = None, *, now: datetime | None = None) -> Harbor:
    """The whole decision for one message: its tier, whether it is a follow-up inside a Safe Harbor conversation, and what to store.
    Never raises on text; ``ctx`` carries the stored documents (see ``load_context``)."""
    ctx = ctx or HarborContext()
    now = now or ctx.now or datetime.now(timezone.utc)
    d = detect(text, history)
    state = _live_state(ctx.state, now)
    lang = d.lang if d.lang != "en" or not state else str(state.get("lang") or "en")
    norm = _norm(text)[:8000]
    tier, repeat = d.tier, False
    if tier == TIER_GENTLE and _prior_events(ctx.flag, now, ctx.message_id) >= 1:
        tier, repeat = TIER_EXPLICIT, True
    if state and tier < TIER_EXPLICIT and not d.perpetrator and _PREGNANT.search(norm):
        tier = TIER_EXPLICIT       # "I think I am pregnant" after telling Bubbles they were hurt: a danger marker (plan 7.6), not a question to wave on
    h = Harbor(tier=tier, perpetrator=d.perpetrator, about_other=d.about_other, past_only=d.past_only, child_at_risk=d.child_at_risk,
               families=d.families, lang=lang, repeat=repeat, pause_partner_signals=tier >= TIER_LITE, country=ctx.country, gender=ctx.gender)
    h.level = TIER_GENTLE if d.perpetrator and tier < TIER_GENTLE else tier
    if tier >= TIER_GENTLE or d.perpetrator:
        h.mode = "perpetrator" if d.perpetrator and tier < TIER_GENTLE else "victim"
        h.step = "heard"
        if state and tier >= TIER_GENTLE:
            h.level = max(tier, int(state.get("tier") or 0))
        return h
    if state:
        h.mode = "perpetrator" if state.get("mode") == "perpetrator" else "victim"
        if _URGENT_NOW.search(norm):
            h.followup = "urgent"                      # someone is badly hurt now: the number first, still in this voice
        elif _off_topic(norm):
            return h                                   # a plain question about something else is answered as usual; the voice stays for the next message
        else:
            h.followup = pick_option(text, h.mode)
        h.step = _STEP_OF[h.followup]
        h.level = max(tier, int(state.get("tier") or TIER_GENTLE))
        h.child_at_risk = h.child_at_risk or bool(state.get("child"))
    return h


def fail_safe(text: Any) -> Harbor:
    """If the rules themselves ever fail, a plain keyword look decides: better a gentle fixed reply than the message going to a model."""
    try:
        if _c(r"\b(?:hit|hits|beat|beats|slap|slapped|punch|punched|choke|choked|strangle|strangled|kick|kicked|rape|raped)\s+me\b|\bkill\s+me\b|"
              r"\bmaar\w*|\bpeet\w*|\bpitai\b|\bthapp?ad\b|\bjaan\s+se\b|\bgala\s+dab\w*|\bzabardasti\b|मार|पीट|थप्पड़|गला\s+दब|जान\s*से").search(_norm(text)):
            return Harbor(tier=TIER_GENTLE, level=TIER_GENTLE, lang=detect_language(text), families=("fail_safe",), step="heard", pause_partner_signals=True)
    except Exception:  # noqa: BLE001
        pass
    return Harbor()


# --------------------------------------------------------------------------
# The copy bank (fixed text, reviewed; no model ever writes it)
# --------------------------------------------------------------------------
# Rules for every line: calm, plain, no diagnosis, no verdict about the other person, no "leave them", no em-dashes. Hinglish and Hindi use
# forms that do not change with the speaker's or listener's gender ("tum important ho", "aap"), as Appendix A of the plan asks.
# Three wordings per kind and language; the hash of the message picks one, so a retried message gets the same words.
# The Hindi (Devanagari) wording carries needs_review=True: the owner, or a native speaker the owner trusts, checks it before release
# (plan Section 17, D7). Until then it is the same meaning as the English and Hinglish, written carefully, not verified.


@dataclass(frozen=True)
class Copy:
    texts: tuple[str, ...]
    needs_review: bool = False


def _copy(en: tuple[str, ...], hl: tuple[str, ...], hi: tuple[str, ...]) -> dict[str, Copy]:
    return {"en": Copy(en), "hi-latn": Copy(hl), "hi": Copy(hi, needs_review=True)}


# Tier 2: one act of violence, no danger marker. The owner's tone: it is a little hard for me to hear; talk to someone mature you trust, who
# will not take advantage; for now maybe do not bring it up with them while they are angry. No numbers, no alarm, no "leave them".
TIER2 = _copy(
    en=(
        "I'm really glad you told me. Honestly, this is a little hard for me to hear, because you matter and you shouldn't be hurt by someone close to you. "
        "Would it help to talk to someone mature you trust, someone who won't use this against you? For now, it may be safer not to bring this up with them "
        "while they're angry. I'm here, and you can tell me as much or as little as you want.",
        "Thank you for trusting me with this. I'll be honest, it's a little hard for me to hear, because you deserve to feel safe with the people close to you. "
        "Is there someone mature you trust, who wouldn't take advantage of what you share? Talking to them could really help. For now, it may be wiser not to "
        "raise it with them while they're angry. I'm right here, and you can tell me as much or as little as you like.",
        "I'm glad you said it out loud. This is a little hard for me to hear, because being hurt by someone close is not okay, and you matter. If you can, tell "
        "someone mature you trust, someone who will not use it against you or take advantage of it. And for now, maybe don't bring it up with them while they're "
        "angry. You can tell me as much or as little as you want, and I'll be here.",
    ),
    hl=(
        "Mujhe batane ke liye thank you. Sach kahun toh ye sunna mere liye thoda mushkil hai, kyunki tum important ho aur kisi apne se hurt hona theek nahi hai. "
        "Kisi aise mature insaan se baat karna madad kar sakta hai jis pe tumhe bharosa ho, jo is baat ka galat fayda na uthaye. Abhi ke liye, jab woh gusse mein "
        "ho tab ye baat na chhedna shayad zyada safe rahega. Main yahin hoon, jitna chaho utna batao.",
        "Tumne mujh pe bharosa kiya, uske liye shukriya. Sach batau toh ye sunna mere liye thoda mushkil hai, kyunki tumhe apno ke saath safe feel karna chahiye. "
        "Kya koi aisa samajhdaar insaan hai jis pe tumhe bharosa ho aur jo is baat ka galat fayda na uthaye? Unse baat karne se madad mil sakti hai. Abhi ke liye, "
        "woh gusse mein ho toh ye baat unse na karna shayad behtar hoga. Main yahin hoon, jitna chaho utna batao.",
        "Achha kiya jo tumne ye bol diya. Mere liye ye sunna thoda mushkil hai, kyunki kisi apne se chot pahunchna theek nahi hai aur tum important ho. Agar ho sake toh "
        "kisi mature insaan ko batao jis pe bharosa ho aur jo iska galat fayda na uthaye. Aur abhi ke liye, jab woh gusse mein ho, unse ye baat na chhedna shayad theek "
        "rahega. Jitna chaho utna mujhse share karo, main yahin hoon.",
    ),
    hi=(
        "आपने मुझे बताया, इसके लिए शुक्रिया। सच कहूँ तो यह सुनना मेरे लिए थोड़ा मुश्किल है, क्योंकि आप मायने रखते हैं और किसी अपने से चोट पहुँचना ठीक नहीं है। "
        "क्या किसी ऐसे समझदार इंसान से बात करना मदद करेगा जिस पर आपको भरोसा हो और जो इस बात का गलत फायदा न उठाए? अभी के लिए, जब वे गुस्से में हों तब यह बात न छेड़ना "
        "शायद ज़्यादा सुरक्षित रहेगा। मैं यहीं हूँ, जितना चाहें उतना बताइए।",
        "मुझ पर भरोसा करने के लिए शुक्रिया। सच बताऊँ तो यह सुनना मेरे लिए थोड़ा मुश्किल है, क्योंकि अपनों के साथ आपको सुरक्षित महसूस करना चाहिए। क्या कोई समझदार इंसान है "
        "जिस पर आपको भरोसा हो और जो इस बात का गलत फायदा न उठाए? उनसे बात करने से मदद मिल सकती है। अभी के लिए, वे गुस्से में हों तो यह बात उनसे न करना शायद बेहतर होगा। "
        "मैं यहीं हूँ, जितना चाहें उतना साझा कीजिए।",
        "आपने यह कह दिया, यह अच्छा किया। मेरे लिए यह सुनना थोड़ा मुश्किल है, क्योंकि किसी अपने से चोट पहुँचना ठीक नहीं है और आप मायने रखते हैं। हो सके तो किसी समझदार "
        "इंसान को बताइए जिस पर आपको भरोसा हो और जो इसका गलत फायदा न उठाए। और अभी के लिए, जब वे गुस्से में हों, तब उनसे यह बात न छेड़ना शायद ठीक रहेगा। जितना चाहें उतना "
        "मुझसे साझा कीजिए, मैं यहीं हूँ।",
    ),
)

# Tier 3: a danger marker. Calm but explicit. {help} is the resource sentence for this person (see HELP).
TIER3 = _copy(
    en=(
        "What you're describing sounds dangerous, and your safety matters most right now. {help} If you can, keep your phone charged and stay close to someone "
        "you trust. Please don't confront them about this right now. I'm here, and we can take this one small step at a time.",
        "I'm taking what you've told me seriously, because it sounds dangerous, and your safety comes first. {help} If you can, keep your phone charged and stay near "
        "someone you trust. It's best not to bring this up with them right now. I'm here with you, and we can go one small step at a time.",
        "Thank you for telling me. This sounds unsafe, and I want you to be safe above everything else. {help} Try to keep your phone charged, stay close to someone "
        "you trust, and please don't confront them about this now. I'm here, and we'll take it slowly, one step at a time.",
    ),
    hl=(
        "Jo tumne abhi bataya woh khatarnaak lag raha hai, aur abhi sabse zaroori tumhari safety hai. {help} Ho sake toh phone charged rakho aur kisi bharose wale ke "
        "paas raho. Abhi unse is baare mein baat mat chhedna. Main yahin hoon, hum ek-ek chhota kadam lenge.",
        "Jo tumne bataya, mujhe woh seriously lag raha hai, kyunki woh khatarnaak sunai deta hai. Sabse pehle tumhari safety. {help} Ho sake toh phone charged rakho aur "
        "kisi bharose wale ke paas raho. Abhi unse ye baat na karna hi behtar hai. Main tumhare saath hoon, hum ek-ek chhota kadam lenge.",
        "Batane ke liye shukriya. Ye baat unsafe sunai deti hai, aur sabse zaroori hai ki tum safe raho. {help} Phone charged rakhne ki koshish karo, kisi bharose wale ke "
        "paas raho, aur abhi unse is baare mein baat mat karna. Main yahin hoon, hum dheere-dheere, ek-ek kadam lenge.",
    ),
    hi=(
        "जो आपने बताया वह ख़तरनाक लग रहा है, और अभी सबसे ज़रूरी आपकी सुरक्षा है। {help} हो सके तो फ़ोन चार्ज रखिए और किसी भरोसेमंद व्यक्ति के पास रहिए। अभी उनसे इस बारे में "
        "बात मत छेड़िए। मैं यहीं हूँ, हम एक-एक छोटा कदम लेंगे।",
        "मुझे यह बात गंभीर लग रही है, क्योंकि यह ख़तरनाक सुनाई देती है। सबसे पहले आपकी सुरक्षा। {help} हो सके तो फ़ोन चार्ज रखिए और किसी भरोसेमंद व्यक्ति के पास रहिए। "
        "अभी उनसे यह बात न करना ही बेहतर है। मैं आपके साथ हूँ, हम एक-एक छोटा कदम लेंगे।",
        "बताने के लिए शुक्रिया। यह बात असुरक्षित लगती है, और सबसे ज़रूरी है कि आप सुरक्षित रहें। {help} फ़ोन चार्ज रखने की कोशिश कीजिए, किसी भरोसेमंद व्यक्ति के पास रहिए, "
        "और अभी उनसे इस बारे में बात मत कीजिए। मैं यहीं हूँ, हम धीरे-धीरे, एक-एक कदम लेंगे।",
    ),
)

# The resource sentence inside tier 3, and on its own after a crisis reply. Chosen by who can help this person (see locale_support).
HELP: dict[str, dict[str, str]] = {
    "en": {
        "women": "If you're in danger at this moment, please call 112. The Women Helpline 181 and the NCW helpline 14490 are free, open all day and night, and help "
                 "with exactly this, quietly.",
        "other": "If you're in danger at this moment, please call 112. Tele-MANAS on 14416 is free and open all day and night, and it can also help to tell a person "
                 "you trust what is happening.",
        "local": "If you're in danger at this moment, please call your local emergency number. A local helpline that deals with this can also help, quietly.",
        "child": " If a child is in danger, Childline 1098 is free and open all day and night.",
    },
    "hi-latn": {
        "women": "Agar abhi is waqt khatra hai, toh please 112 pe call karo. Women Helpline 181 aur NCW helpline 14490 free hain, din-raat khule hain, aur chupchaap isi "
                 "cheez mein madad karte hain.",
        "other": "Agar abhi is waqt khatra hai, toh please 112 pe call karo. Tele-MANAS 14416 free hai aur din-raat khula hai, aur kisi bharose wale insaan ko batana bhi "
                 "madad kar sakta hai.",
        "local": "Agar abhi is waqt khatra hai, toh please apne local emergency number pe call karo. Isi cheez ke liye local helpline bhi chupchaap madad kar sakti hai.",
        "child": " Agar kisi bachche ko khatra hai, toh Childline 1098 free hai aur din-raat khula hai.",
    },
    "hi": {
        "women": "अगर अभी इसी समय ख़तरा है, तो कृपया 112 पर कॉल कीजिए। महिला हेल्पलाइन 181 और NCW हेल्पलाइन 14490 मुफ़्त हैं, दिन-रात खुली रहती हैं, और ठीक ऐसी ही बात में "
                 "चुपचाप मदद करती हैं।",
        "other": "अगर अभी इसी समय ख़तरा है, तो कृपया 112 पर कॉल कीजिए। Tele-MANAS 14416 मुफ़्त है और दिन-रात खुला रहता है, और किसी भरोसेमंद व्यक्ति को बताना भी मदद कर सकता है।",
        "local": "अगर अभी इसी समय ख़तरा है, तो कृपया अपने स्थानीय आपातकालीन नंबर पर कॉल कीजिए। ऐसी ही बात के लिए स्थानीय हेल्पलाइन भी चुपचाप मदद कर सकती है।",
        "child": " अगर किसी बच्चे को ख़तरा है, तो Childline 1098 मुफ़्त है और दिन-रात खुली रहती है।",
    },
}

# A person who says they hurt someone: not shaming, clear that hurting is not okay, steps (step away, cool down, a counsellor), Tele-MANAS for anger and
# stress, 112 if anyone is in danger now. {help} is the one sentence with the numbers (see HELP_SELF).
PERPETRATOR = _copy(
    en=(
        "Thank you for being honest with me. Hurting someone is not okay, and I won't pretend otherwise, but telling me suggests you may want to do something "
        "different, and that matters. When you feel anger rising, step away from the situation, take a few slow breaths, and give yourself time to cool down before "
        "you speak. Talking to a counsellor can help with anger and stress. {help}",
        "I'm glad you told me, even though it isn't easy to say. Hurting someone you care about is not okay, and it can seriously harm them. It also doesn't have to "
        "happen again. When things get heated, leave the room, breathe slowly, and wait before you talk. A counsellor can help you work on anger and stress. {help}",
        "Thank you for saying this plainly. That takes some courage. Hurting someone is not okay, and I'd like to help you make sure it doesn't happen again. Step away "
        "when you feel yourself boiling over, cool down before you talk, and think about speaking with a counsellor about anger and stress. {help}",
    ),
    hl=(
        "Sach batane ke liye shukriya. Kisi ko chot pahunchana theek nahi hai, ye baat saaf hai. Par tumne ye khul ke bataya, isse lagta hai ki kuch alag karne ka mann hai, "
        "aur wahi sabse zaroori hai. Gussa badhe toh pehle us jagah se hat jao, dheere-dheere saans lo aur baat karne se pehle thoda waqt do. Gusse aur tanav ke liye kisi "
        "counsellor se baat karna madad kar sakta hai. {help}",
        "Tumne bataya, achha laga, chahe ye kehna aasaan nahi tha. Jo tumhare apne hain, unhe chot pahunchana theek nahi hai, aur isse unhe gehra nuksan ho sakta hai. Par ye "
        "dobara hona zaroori nahi hai. Jab baat garam ho, kamre se bahar chale jao, dheere saans lo aur bolne se pehle ruko. Gusse aur tanav par counsellor madad kar sakta hai. {help}",
        "Seedhe bolne ke liye shukriya, isme himmat lagti hai. Kisi ko chot pahunchana theek nahi hai, aur koshish yahi honi chahiye ki ye dobara na ho. Jab lage ki gussa ubal "
        "raha hai, wahan se hat jao, bolne se pehle thanda ho jao, aur gusse aur tanav ke baare mein kisi counsellor se baat karne ka socho. {help}",
    ),
    hi=(
        "सच बताने के लिए शुक्रिया। किसी को चोट पहुँचाना ठीक नहीं है, यह बात साफ़ है। पर आपने यह खुलकर बताया, इससे लगता है कि कुछ अलग करने का मन है, और वही सबसे ज़रूरी है। "
        "गुस्सा बढ़े तो पहले उस जगह से हट जाइए, धीरे-धीरे साँस लीजिए और बोलने से पहले थोड़ा समय दीजिए। गुस्से और तनाव के लिए किसी काउंसलर से बात करना मदद कर सकता है। {help}",
        "आपने बताया, यह अच्छा किया, भले ही यह कहना आसान नहीं था। जिसे आप चाहते हैं, उसे चोट पहुँचाना ठीक नहीं है, और इससे उसे गहरा नुकसान हो सकता है। पर यह दोबारा होना ज़रूरी नहीं है। "
        "जब बात गरम हो, कमरे से बाहर चले जाइए, धीरे साँस लीजिए और बोलने से पहले रुकिए। गुस्से और तनाव पर काउंसलर मदद कर सकता है। {help}",
        "सीधे बोलने के लिए शुक्रिया, इसमें हिम्मत लगती है। किसी को चोट पहुँचाना ठीक नहीं है, और कोशिश यही होनी चाहिए कि यह दोबारा न हो। जब लगे कि गुस्सा उबल रहा है, वहाँ से हट जाइए, "
        "बोलने से पहले ठंडे हो जाइए, और गुस्से और तनाव के बारे में किसी काउंसलर से बात करने का सोचिए। {help}",
    ),
)
HELP_SELF: dict[str, dict[str, str]] = {
    "en": {"in": "Tele-MANAS on 14416 is free and open all day and night. If anyone is in danger right now, please call 112.",
           "local": "If anyone is in danger right now, please call your local emergency number."},
    "hi-latn": {"in": "Tele-MANAS 14416 free hai aur din-raat khula hai. Agar abhi kisi ko khatra hai, toh please 112 pe call karo.",
                "local": "Agar abhi kisi ko khatra hai, toh please apne local emergency number pe call karo."},
    "hi": {"in": "Tele-MANAS 14416 मुफ़्त है और दिन-रात खुला रहता है। अगर अभी किसी को ख़तरा है, तो कृपया 112 पर कॉल कीजिए।",
           "local": "अगर अभी किसी को ख़तरा है, तो कृपया अपने स्थानीय आपातकालीन नंबर पर कॉल कीजिए।"},
}

# Follow-ups: the next messages keep the Safe Harbor voice. Listen, ask what they need, offer the four choices; never cheerful small talk.
LISTEN = _copy(
    en=("I'm here, and I'm listening. What would help you most right now? You can pick one of these, or just tell me in your own words.",
        "Thank you for telling me more. I'm still here. Would you like to keep talking, make a small safety plan, or see who can help? Or tell me what you need.",
        "I hear you. There's no hurry. Tell me what you need right now, or choose one of these."),
    hl=("Main yahin hoon, tumhari baat dhyaan se sunne ke liye. Abhi tumhe sabse zyada kya madad karega? In mein se chun lo, ya apne shabdon mein batao.",
        "Aur batane ke liye shukriya. Main abhi bhi yahin hoon. Aur baat karni hai, chhota sa safety plan banana hai, ya dekhna hai ki kaun madad kar sakta hai? Ya seedha batao ki kya chahiye.",
        "Koi jaldi nahi hai. Abhi tumhe kya chahiye, ye batao, ya in mein se koi chun lo."),
    hi=("मैं यहीं हूँ, आपकी बात ध्यान से सुनने के लिए। अभी आपको सबसे ज़्यादा क्या मदद करेगा? इनमें से चुन लीजिए, या अपने शब्दों में बताइए।",
        "और बताने के लिए शुक्रिया। मैं अभी भी यहीं हूँ। क्या और बात करनी है, छोटी-सी सुरक्षा योजना बनानी है, या देखना है कि कौन मदद कर सकता है? या सीधे बताइए कि क्या चाहिए।",
        "कोई जल्दी नहीं है। अभी आपको क्या चाहिए, यह बताइए, या इनमें से कोई चुन लीजिए।"),
)
LISTEN_SELF = _copy(
    en=("I'm listening, and I'm not here to judge. Tell me what's going on, or choose one of these.",
        "Thank you for telling me more. I'm still here. We can keep talking, look at ways to cool down, or see who can help.",
        "There's no hurry. Tell me what you need right now, or pick one of these."),
    hl=("Main yahin hoon, bina judge kiye sunne ke liye. Batao kya chal raha hai, ya in mein se koi chun lo.",
        "Aur batane ke liye shukriya. Main abhi bhi yahin hoon. Hum baat kar sakte hain, shaant hone ke tareeke dekh sakte hain, ya dekh sakte hain ki kaun madad kar sakta hai.",
        "Koi jaldi nahi hai. Abhi tumhe kya chahiye, ye batao, ya in mein se koi chun lo."),
    hi=("मैं यहीं हूँ, बिना जज किए सुनने के लिए। बताइए क्या चल रहा है, या इनमें से कोई चुन लीजिए।",
        "और बताने के लिए शुक्रिया। मैं अभी भी यहीं हूँ। हम बात कर सकते हैं, शांत होने के तरीके देख सकते हैं, या देख सकते हैं कि कौन मदद कर सकता है।",
        "कोई जल्दी नहीं है। अभी आपको क्या चाहिए, यह बताइए, या इनमें से कोई चुन लीजिए।"),
)
TALK_MORE = {"en": "I'm listening. Take your time, and tell me as much or as little as you want.",
             "hi-latn": "Main yahin hoon, apna waqt lo, aur jitna chaho utna batao.",
             "hi": "मैं यहीं हूँ। अपना समय लीजिए, और जितना चाहें उतना बताइए।"}
SAFETY_PLAN = {
    "en": "A safety plan is a short checklist you can prepare quietly, one small thing at a time: copies of important documents, some cash, a small bag with essentials, "
          "a code word with a friend you trust, important numbers saved under a neutral name, and the nearest place where you would feel safe. You don't have to do it all "
          "today, and you don't need to write your answers here. Which one would you like to start with?",
    "hi-latn": "Safety plan ek chhoti checklist hai jo tum chupchaap, ek-ek chhoti cheez karke taiyaar kar sakte ho: zaroori kaagzaat ki copy, thoda cash, zaroori saamaan ka chhota bag, "
               "kisi bharose wale dost ke saath ek code word, zaroori numbers kisi neutral naam se save, aur sabse paas ki jagah jahan tum safe mehsoos karo. Sab aaj hi karna zaroori nahi, "
               "aur apne jawab yahan likhne ki zaroorat nahi. Kahan se shuru karna chahoge?",
    "hi": "सुरक्षा योजना एक छोटी चेकलिस्ट है जिसे आप चुपचाप, एक-एक छोटी चीज़ करके तैयार कर सकते हैं: ज़रूरी कागज़ों की कॉपी, थोड़ा नकद, ज़रूरी सामान का छोटा बैग, किसी भरोसेमंद दोस्त के "
          "साथ एक कोड शब्द, ज़रूरी नंबर किसी सामान्य नाम से सेव, और सबसे पास की वह जगह जहाँ आप सुरक्षित महसूस करें। सब कुछ आज ही करना ज़रूरी नहीं, और अपने जवाब यहाँ लिखने की "
          "ज़रूरत नहीं। आप कहाँ से शुरू करना चाहेंगे?",
}
SHOW_HELP = {"en": "Here are people who can help, all free:", "hi-latn": "Ye log madad kar sakte hain, sab free hain:", "hi": "ये लोग मदद कर सकते हैं, सब मुफ़्त हैं:"}
SHOW_HELP_END = {"en": "If you're in danger right now, call 112 first. I'm still here.", "hi-latn": "Agar abhi khatra hai, toh sabse pehle 112 pe call karo. Main yahin hoon.",
                 "hi": "अगर अभी ख़तरा है, तो सबसे पहले 112 पर कॉल कीजिए। मैं यहीं हूँ।"}
SHOW_HELP_END_LOCAL = {"en": "If you're in danger right now, call your local emergency number first. I'm still here.",
                       "hi-latn": "Agar abhi khatra hai, toh sabse pehle apne local emergency number pe call karo. Main yahin hoon.",
                       "hi": "अगर अभी ख़तरा है, तो सबसे पहले अपने स्थानीय आपातकालीन नंबर पर कॉल कीजिए। मैं यहीं हूँ।"}
OKAY_FOR_NOW = {"en": "I'm glad you're okay for now. I'm here whenever you want to talk. If things change, {emergency} is always there, and you can come back to this chat any time.",
                "hi-latn": "Achha laga ki abhi tum theek ho. Jab bhi baat karni ho, main yahin hoon. Agar halaat badlein, toh {emergency} hamesha hai, aur tum is chat mein kabhi bhi wapas aa sakte ho.",
                "hi": "अच्छा लगा कि अभी आप ठीक हैं। जब भी बात करनी हो, मैं यहीं हूँ। अगर हालात बदलें, तो {emergency} हमेशा है, और आप इस चैट में कभी भी लौट सकते हैं।"}
OKAY_LOCAL = {"en": "your local emergency number", "hi-latn": "apna local emergency number", "hi": "आपका स्थानीय आपातकालीन नंबर"}
# Someone is badly hurt right now, said inside a Safe Harbor conversation: the number first, in the same calm voice. {emergency} is "112" or the local words.
URGENT_NOW = {"en": "If anyone is badly hurt right now, please call {emergency} now and ask someone nearby to help. If it is safe, stay with them until help arrives. I'm still here.",
              "hi-latn": "Agar abhi kisi ko gehri chot lagi hai, toh please abhi {emergency} pe call karo aur paas ke kisi insaan se madad maango. Ho sake toh madad aane tak unke paas raho. Main yahin hoon.",
              "hi": "अगर अभी किसी को गहरी चोट लगी है, तो कृपया अभी {emergency} पर कॉल कीजिए और पास के किसी व्यक्ति से मदद माँगिए। हो सके तो मदद आने तक उनके पास रहिए। मैं यहीं हूँ।"}
URGENT_LOCAL = {"en": "your local emergency number", "hi-latn": "apne local emergency number", "hi": "अपने स्थानीय आपातकालीन नंबर"}
COOL_DOWN = {
    "en": "When anger rises, it helps to step away first. Leave the room if you can, breathe slowly with the breath out longer than the breath in, and give yourself time "
          "before you speak. Talking to a counsellor can help with anger and stress. {help}",
    "hi-latn": "Gussa badhe toh pehle wahan se hat jaana madad karta hai. Ho sake toh kamre se bahar chale jao, dheere saans lo aur saans bahar zyada der tak chhodo, aur bolne se pehle "
               "thoda waqt do. Gusse aur tanav par counsellor se baat karna madad kar sakta hai. {help}",
    "hi": "गुस्सा बढ़े तो पहले वहाँ से हट जाना मदद करता है। हो सके तो कमरे से बाहर चले जाइए, धीरे साँस लीजिए और साँस बाहर ज़्यादा देर तक छोड़िए, और बोलने से पहले थोड़ा समय दीजिए। "
          "गुस्से और तनाव पर काउंसलर से बात करना मदद कर सकता है। {help}",
}
MEDICAL_NOTE = {"en": "If you're hurt, please get checked by a clinician or an urgent-care service today. You can tell them how it happened only if you feel able to.",
                "hi-latn": "Agar chot lagi hai, toh aaj hi kisi clinician ya urgent-care se jaanch karwa lo. Kaise hua, ye tabhi batana jab tum bata paao.",
                "hi": "अगर चोट लगी है, तो आज ही किसी क्लिनिशियन या अर्जेंट-केयर सेवा से जाँच करवाइए। यह कैसे हुआ, यह तभी बताइए जब आप बता सकें।"}
# Tier 1 with no yes to the outside model: a short fixed reply (the consent question follows it, like the loneliness reply).
TIER1_FIXED = {
    "en": "That sounds really hard, and I'm glad you told me. You deserve to feel safe and respected with the people close to you. I'm here to listen, and if you ever feel "
          "unsafe, 112 is always there.",
    "hi-latn": "Ye bahut mushkil lag raha hai, aur achha laga ki tumne bataya. Tumhe apno ke saath safe aur izzat se rehne ka poora haq hai. Main sunne ke liye yahin hoon, aur agar kabhi "
               "unsafe lage, toh 112 hamesha hai.",
    "hi": "यह बहुत मुश्किल लग रहा है, और अच्छा लगा कि आपने बताया। अपनों के साथ सुरक्षित और इज़्ज़त से रहने का आपको पूरा हक़ है। मैं सुनने के लिए यहीं हूँ, और अगर कभी असुरक्षित लगे, "
          "तो 112 हमेशा है।",
}
LABELS = {
    "talk_more": {"en": "I want to talk more", "hi-latn": "Aur baat karni hai", "hi": "मुझे और बात करनी है"},
    "safety_plan": {"en": "Help me make a safety plan", "hi-latn": "Safety plan banane mein madad karo", "hi": "सुरक्षा योजना बनाने में मदद कीजिए"},
    "show_help": {"en": "Show me who can help", "hi-latn": "Mujhe batao kaun madad kar sakta hai", "hi": "बताइए कौन मदद कर सकता है"},
    "okay_for_now": {"en": "I'm okay for now", "hi-latn": "Abhi main theek hoon", "hi": "अभी मैं ठीक हूँ"},
    "cool_down": {"en": "Help me cool down", "hi-latn": "Shaant hone mein madad karo", "hi": "शांत होने में मदद कीजिए"},
}


# needs_review=True for every Hindi (Devanagari) line that is not a ``Copy`` entry: the owner, or a native speaker the owner trusts, checks them before release.
HINDI_UNREVIEWED = ("help", "help_self", "talk_more", "safety_plan", "show_help", "show_help_end", "show_help_end_local", "okay_for_now", "okay_local",
                    "urgent_now", "urgent_local", "cool_down", "medical_note", "tier1_fixed", "labels")


def needs_review() -> list[tuple[str, str]]:
    """Every copy entry still waiting for a native-speaker check: ``(kind, language)``. The owner clears this list before release."""
    named = {"tier2": TIER2, "tier3": TIER3, "perpetrator": PERPETRATOR, "listen": LISTEN, "listen_self": LISTEN_SELF}
    out = [(kind, lang) for kind, bank in named.items() for lang, copy in bank.items() if copy.needs_review]
    # The plain one-line banks have no per-entry flag: every Devanagari line in them is user-facing Hindi that nobody who speaks it has checked yet,
    # so each bank that carries a "hi" line is listed here (a test fails if a new bank with Hindi is added and not listed).
    out += [(kind, "hi") for kind in HINDI_UNREVIEWED]
    return out


# --------------------------------------------------------------------------
# Building the reply, the client payload and the model blocks
# --------------------------------------------------------------------------

def _pick(texts: tuple[str, ...], seed: str) -> str:
    return texts[int(hashlib.sha256(seed.encode("utf-8")).hexdigest(), 16) % len(texts)]   # stable, so a retried message gets the same words


def _seed(text: Any) -> str:
    return " ".join(re.findall(r"\w+", _norm(text)))


def _lang(h: Harbor) -> str:
    return h.lang if h.lang in HELP else "en"


def _is_india(h: Harbor) -> bool:
    return locale_support.normalize_country(h.country) == "IN"


def resources(h: Harbor) -> list[dict[str, str]]:
    """The people to point to for this person: who was hurt (112 and the helpline that fits), or who hurt someone (112 and Tele-MANAS)."""
    if h.mode == "perpetrator":
        return locale_support.self_help_resources(h.country, h.child_at_risk)
    return locale_support.resources_for(h.country, h.gender, h.child_at_risk)


def help_sentence(h: Harbor) -> str:
    """The tier 3 resource line: what to do if in danger now, and who answers day and night. Also used on its own after a crisis reply."""
    bank, found = HELP[_lang(h)], locale_support.resources_for(h.country, h.gender, h.child_at_risk)
    numbers = {r["number"] for r in found}
    text = bank["women"] if "181" in numbers else bank["other"] if "14416" in numbers else bank["local"]
    return text + (bank["child"] if "1098" in numbers else "")


def resource_line(h: Harbor) -> str:
    return help_sentence(h)


def _help_self(h: Harbor) -> str:
    child = HELP[_lang(h)]["child"] if h.child_at_risk and _is_india(h) else ""      # a parent who hurt a child: Childline 1098 as well
    return HELP_SELF[_lang(h)]["in" if _is_india(h) else "local"] + child


def _followup_text(h: Harbor, seed: str) -> str:
    lang, option, self_voice = _lang(h), h.followup, h.mode == "perpetrator"
    if option == "talk_more":
        return TALK_MORE[lang]
    if option == "safety_plan":
        return SAFETY_PLAN[lang]
    if option == "cool_down":
        return COOL_DOWN[lang].format(help=_help_self(h))
    if option == "show_help":
        found = resources(h)
        lines = "\n".join(f"- {r['name']}: {r['number']}" if r["number"] else f"- {r['name']}" for r in found)
        end = SHOW_HELP_END if _is_india(h) else SHOW_HELP_END_LOCAL
        return f"{SHOW_HELP[lang]}\n{lines}\n\n{end[lang]}"
    if option == "okay_for_now":
        return OKAY_FOR_NOW[lang].format(emergency="112" if _is_india(h) else OKAY_LOCAL[lang])
    if option == "urgent":
        return URGENT_NOW[lang].format(emergency="112" if _is_india(h) else URGENT_LOCAL[lang])
    return _pick((LISTEN_SELF if self_voice else LISTEN)[lang].texts, seed)


def reply(h: Harbor, *, seed: Any = "", medical: bool = False) -> str:
    """The fixed reply for a deterministic Harbor (tier 2 or 3, a person who hurt someone, or a follow-up). ``medical`` adds one line when the
    person also reported symptoms that need prompt care."""
    lang, picker = _lang(h), _seed(seed)
    if h.followup:
        return _followup_text(h, picker)
    if h.mode == "perpetrator":
        text = _pick(PERPETRATOR[lang].texts, picker).format(help=_help_self(h))
    elif h.level >= TIER_EXPLICIT:
        text = _pick(TIER3[lang].texts, picker).format(help=help_sentence(h))
    else:
        text = _pick(TIER2[lang].texts, picker)
    return text + ("\n\n" + MEDICAL_NOTE[lang] if medical else "")


def lite_fixed_reply(h: Harbor) -> str | None:
    """Tier 1 when no outside model may be asked (no yes to AI processing): a short fixed reply, followed by the usual consent question."""
    return TIER1_FIXED[_lang(h)] if h.tier == TIER_LITE and not h.deterministic else None


def payload(h: Harbor, *, explicit: bool = False) -> dict[str, Any]:
    """What the screen gets next to the reply: ``{tier, mode, step, resources: [{name, number, note}], actions: [{id, label}]}``.
    ``explicit`` says the reply carried the tier 3 resource line (a crisis reply followed by it)."""
    lang, self_voice = _lang(h), h.mode == "perpetrator"
    options = OPTIONS_SELF if self_voice else OPTIONS
    return {
        "tier": TIER_EXPLICIT if explicit else max(h.level, TIER_GENTLE),
        "mode": "followup" if h.followup else "perpetrator" if h.mode == "perpetrator" else "disclosure",
        "step": h.step,
        "resources": resources(h),
        "actions": [] if h.step == "closed" else [{"id": o, "label": LABELS[o][lang]} for o in options],
    }


def _resource_lines(h: Harbor) -> str:
    return "\n".join(f"  {r['name']}: {r['number']}" if r["number"] else f"  {r['name']}" for r in resources(h))


def model_block(h: Harbor) -> str:
    """Extra instructions for the model on a turn the model IS allowed to answer: tier 1 (SAFE HARBOR LITE) and someone else's story.
    Empty for everything else (tier 2 and above never reach a model)."""
    if h.deterministic:
        return ""
    if h.tier == TIER_LITE:
        return (
            "SAFE HARBOR LITE (the person may be describing control, fear or hurtful treatment from someone close; treat it as a disclosure, not a coaching topic):\n"
            "- Reply like a calm, warm friend, in the person's own language. Validate how they feel first. Do not diagnose, and do not label anyone.\n"
            "- You may gently say that what they describe sounds controlling or hurtful, and that they deserve to feel safe and respected. "
            "Never tell them to leave, to stay, to confront or to forgive. Never call the other person toxic, abusive or a narcissist.\n"
            "- Do not ask for names, addresses or details that could identify anyone. At most one question.\n"
            "- Offer once, quietly, that you can show them people who help with exactly this, whenever they want. Give no phone numbers unless they ask. "
            "If they ask, use exactly these and no others:\n" + _resource_lines(h) + "\n"
            "- Do not help them check, track, test or control the other person.")
    if h.about_other:
        return (
            "SAFE HARBOR (SOMEONE ELSE): the person described violence or fear affecting someone they know, not themselves.\n"
            "- Be kind and listen. Do not ask for names or identifying details, and do not tell them to confront the other person.\n"
            "- You may gently mention that the person being hurt can call 112 if in danger, and that the Women Helpline 181 and the NCW helpline 14490 are free, open day and night. "
            "Offer these as something to share, not as an order.\n"
            "- Suggest they listen without judging and keep what they were told private. Never give a verdict about the other person.")
    return ""


# --------------------------------------------------------------------------
# Storing state (signed documents through doc_store; best effort, never blocks a reply)
# --------------------------------------------------------------------------

def _log(operation: str, error: Exception) -> None:
    try:
        from logging_util import logger
        logger.error(component="SAFE_HARBOR", operation=operation, error=error, fallback_action="continuing")   # no message text, no user id
    except Exception:  # noqa: BLE001
        pass


def _harbor_meta(row: Any) -> dict[str, Any] | None:
    meta = row.get("metadata") if isinstance(row, dict) and row.get("role") == "bubbles" else None
    return meta if isinstance(meta, dict) and isinstance(meta.get("harbor"), dict) else None


def _last_harbor_reply(history: list[dict[str, Any]] | None) -> dict[str, Any] | None:
    """The newest Safe Harbor reply (kind safe_harbor) anywhere in the recent history, even when ordinary replies came after it: a health question
    in the middle of the conversation does not end the Safe Harbor voice, only a day, or "I'm okay for now", does."""
    return next((r for r in reversed(history or []) if (m := _harbor_meta(r)) is not None and m.get("kind") == "safe_harbor"), None)


def _may_have_state(history: list[dict[str, Any]] | None) -> bool:
    """Worth reading the conversation's harbor_state document: a Safe Harbor or crisis-with-numbers reply is in the recent history. Chats with none cost nothing.
    ponytail: the chat reads only the last 10 messages, so a Safe Harbor reply that scrolled out of them (10 messages of other talk within a day) is not seen;
    reading the document on every message of a long chat would add a query to each one. Widen if that ever matters."""
    return any(_harbor_meta(r) is not None for r in history or [])


def _state_from_reply(row: dict[str, Any]) -> dict[str, Any]:
    """The state as the reply itself recorded it: used only if the signed document cannot be read."""
    shown = row["metadata"]["harbor"]
    return {"tier": shown.get("tier") or TIER_GENTLE, "step": shown.get("step") or "heard", "mode": "perpetrator" if shown.get("mode") == "perpetrator" else "victim",
            "lang": shown.get("lang"), "child": bool(shown.get("child")), "updated_at": row.get("created_at")}


def load_context(db: Any, user_id: str, conversation_id: str | None, text: Any, history: list[dict[str, Any]] | None, *, message_id: str | None = None,
                 country: Any = None, gender: Any = None, now: datetime | None = None) -> HarborContext:
    """Reads the stored documents this message needs, and only those, in ONE read: the conversation's harbor_state when the recent history holds a
    Safe Harbor reply anywhere (not only as the newest reply), and the person's harbor_flag when the message itself carries a signal (tier 1 and up:
    tier 2 needs it for the 30-day repeat count, and ``record`` reuses it). Almost every message needs neither, so costs nothing."""
    ctx = HarborContext(country=country, gender=gender, message_id=message_id, now=now)
    try:
        last = _last_harbor_reply(history)
        wants_state = _may_have_state(history)
        wants_flag = detect(text, history).tier >= TIER_LITE
        if not wants_state and not wants_flag:
            return ctx
        if db is None:
            ctx.state = _state_from_reply(last) if last is not None else None
            return ctx
        import doc_store
        wanted = ([("harbor_state", str(conversation_id))] if wants_state and conversation_id else []) + ([("harbor_flag", "v1")] if wants_flag else [])
        docs = doc_store.get_pairs(db, user_id, wanted) if wanted else {}
        ctx.flag, ctx.flag_read = docs.get(("harbor_flag", "v1")), wants_flag
        ctx.state = docs.get(("harbor_state", str(conversation_id))) if wants_state else None
        if last is not None and ctx.state is None:
            ctx.state = _state_from_reply(last)
    except Exception as error:  # noqa: BLE001 - a read problem must not stop a reply; the history alone still carries the voice
        _log("load_context", error)
        last = _last_harbor_reply(history)
        if last is not None and ctx.state is None:
            ctx.state = _state_from_reply(last)
    return ctx


def record(db: Any, user_id: str, conversation_id: str | None, message_id: str | None, h: Harbor, *, keep_voice: bool = True,
           ctx: HarborContext | None = None, now: datetime | None = None) -> None:
    """After the reply is saved: the conversation's state (so the next messages keep the Safe Harbor voice) and, from tier 1 up, the person's
    flag with a timestamp (partner signals pause later, plan 7.5; and tier 2 events are counted for the 30-day repeat rule). The two writes run
    side by side. Safe to repeat: events are keyed by the message id. ``keep_voice=False`` is used when the reply was a crisis reply, which has
    its own follow-up (safety_followup)."""
    now = now or datetime.now(timezone.utc)
    iso = now.isoformat()
    jobs = []

    def write_state() -> None:
        try:
            import doc_store
            doc_store.put(db, user_id, "harbor_state", str(conversation_id),
                          {"tier": h.level, "step": h.step, "mode": h.mode, "lang": h.lang, "child": h.child_at_risk, "updated_at": iso})
        except Exception as error:  # noqa: BLE001 - the reply is already saved; a missed note only means the next message is read afresh
            _log("record_state", error)

    def write_flag() -> None:
        try:
            import doc_store
            flag = (ctx.flag if ctx is not None and ctx.flag_read else doc_store.get(db, user_id, "harbor_flag", "v1")) or {}
            events = [e for e in flag.get("events") or []
                      if isinstance(e, dict) and (when := _parse_time(e.get("at"))) is not None and now - when <= timedelta(days=FLAG_DAYS)]
            if h.tier >= TIER_GENTLE and message_id and not any(e.get("m") == str(message_id) for e in events):
                events.append({"m": str(message_id), "at": iso, "t": h.tier})
            doc_store.put(db, user_id, "harbor_flag", "v1",
                          {"last_tier": h.tier, "last_at": iso, "pause_partner_signals": True, "events": events[-MAX_EVENTS:]})
        except Exception as error:  # noqa: BLE001
            _log("record_flag", error)

    if keep_voice and h.step and conversation_id:
        jobs.append(write_state)
    if h.pause_partner_signals and not h.about_other:
        jobs.append(write_flag)
    if jobs:
        from parallel import together
        together(*jobs)


def hidden_message_ids(history: list[dict[str, Any]] | None) -> set[str]:
    """Ids of Safe Harbor replies and of the messages they answered: these never go into the text sent to an outside model."""
    hidden: set[str] = set()
    for row in history or []:
        meta = row.get("metadata") if isinstance(row, dict) and isinstance(row.get("metadata"), dict) else {}
        if row.get("role") == "bubbles" and meta.get("harbor"):
            hidden.update(str(i) for i in (row.get("id"), meta.get("user_message_id")) if i)
    return hidden
