"""Community moderation: deterministic text rules, no database, no network, no AI.

``moderate(text)`` answers one of three things for a post or comment:

* ``allow``  - show it (contact details, if any, are already removed from ``Decision.text``)
* ``hold``   - not sure: only the author sees it ("waiting for review") until the owner decides
* ``remove`` - certain: not shown, with a plain reason code

Order: contact details are stripped; threats and hate aimed at a person are removed even inside a crisis post; crisis wording about
oneself is never removed (the API shows the author the safety banner and puts the post first in the owner's queue); then slurs,
explicit sexual content, abuse, selling and dose or "stop your medicine" advice are removed; then the unsure cases are held (strong
language, shouting, repeats, diagnosis claims stated as fact, cure claims, a dose with no clear context).

Word lists are data (``data/community_words.json``). The rules are Roman-script English and Hinglish (a short Devanagari list
is included). They are a first filter, not a judge: held items and user reports reach the owner's queue.
If the word list cannot be read the filter holds everything rather than letting unchecked text through.
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

DATA_FILE = Path(__file__).resolve().parent / "data" / "community_words.json"

ALLOW, HOLD, REMOVE = "allow", "hold", "remove"

#: What the author is told. Plain words, no authority names, no diagnosis.
REASON_TEXT = {
    "threat": "This sounded like a threat, so it was taken down.",
    "hate": "This had language that targets people, so it was taken down.",
    "sexual": "This had sexual content, which isn't allowed here, so it was taken down.",
    "abuse": "This was aimed at someone in a hurtful way, so it was taken down.",
    "selling": "Selling and promoting aren't allowed here, so this was taken down.",
    "dose_advice": "Advice on how much of a medicine to take isn't allowed here, so this was taken down.",
    "stop_medicine": "Telling someone to stop a medicine or skip a doctor isn't allowed here, so this was taken down.",
    "profanity": "This is waiting for a quick review because of strong language.",
    "sexual_review": "This is waiting for a quick review.",
    "selling_review": "This is waiting for a quick review because it looks like it may be promoting something.",
    "diagnosis_claim": "This is waiting for a quick review because it states a diagnosis as fact.",
    "cure_claim": "This is waiting for a quick review because it makes a cure claim.",
    "dose_review": "This is waiting for a quick review because it mentions an amount of medicine.",
    "spam": "This is waiting for a quick review because it looks like spam.",
    "shouting": "This is waiting for a quick review.",
    "reports": "Several people reported this, so it is waiting for a quick review.",
    "duplicate": "This looks the same as something you just posted.",
    "moderation_error": "This is waiting for a quick review.",
    "admin": "This was taken down by the Bubbles team.",
}


@dataclass(frozen=True)
class Decision:
    action: str                       # allow | hold | remove
    reason: str | None                # a code from REASON_TEXT, or None for a plain allow
    text: str                         # the text to store (contact details replaced by "[removed]")
    notes: tuple[str, ...] = ()       # e.g. ("contact_removed",)


# --- word lists ---------------------------------------------------------------------------------------------------------

_LEET = {"a": "[a@4*]", "e": "[e3*]", "i": "[i1!*]", "o": "[o0*]", "u": "[u*v]", "s": "[s$5]"}
_START = r"(?<![^\W\d_])"
_END = r"(?![^\W\d_])"
_SUFFIX = r"(?:s|es|ed|ing|in)?"


def _word(word: str) -> str:
    w = unicodedata.normalize("NFKC", word).casefold().strip()
    if not w.isascii():
        return re.escape(w)
    sep = r"[.\-_*\s]?" if len(w.replace(" ", "")) >= 5 else r"[.\-_*]?"
    out: list[str] = []
    for ch in w:
        if ch == " ":
            out.append(r"[\W_]+")
        elif ch.isalpha():
            out.append(_LEET.get(ch, re.escape(ch)) + "+" + sep)
        else:
            out.append(re.escape(ch))
    return "".join(out) + _SUFFIX


def _compile(words: Iterable[str]) -> re.Pattern | None:
    parts = [_word(w) for w in sorted({w for w in words if w}, key=len, reverse=True)]
    if not parts:
        return None
    return re.compile(_START + "(?:" + "|".join(parts) + ")" + _END, re.I)


class _Lists:
    def __init__(self) -> None:
        self.ready = False
        self.slurs = self.strong = self.sex_remove = self.sex_hold = self.selling = None
        try:
            data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
            self.slurs = _compile(data["slurs"])
            self.strong = _compile(data["profanity_strong"])
            self.sex_remove = _compile(data["sexual_remove"])
            self.sex_hold = _compile(data["sexual_hold"])
            self.selling = _compile(data["selling"])
            self.ready = all([self.slurs, self.strong, self.sex_remove, self.sex_hold, self.selling])
        except Exception:  # noqa: BLE001 - a missing or broken list must hold posts, never pass them
            self.ready = False


_LISTS: _Lists | None = None


def _lists() -> _Lists:
    global _LISTS
    if _LISTS is None:
        _LISTS = _Lists()
    return _LISTS


# --- contact details ----------------------------------------------------------------------------------------------------

_NUM_WORDS = r"(?:zero|oh|one|two|three|four|five|six|seven|eight|nine|ek|do|teen|char|paanch|chhe|saat|aath|nau)"
_PHONE_CANDIDATE = re.compile(r"(?<![\d])\+?\(?\d[\d\s().\-]{7,}\d(?!\d)")
_PHONE_WORDS = re.compile(rf"\b(?:{_NUM_WORDS}\b[\s,.\-]*){{8,}}", re.I)
_EMAIL = re.compile(r"[\w.+\-]+@[\w\-]+(?:\.[\w\-]+)+|\b[\w.]+\s*(?:\(at\)|\[at\])\s*[\w.]+", re.I)
_EMAIL_AT = re.compile(r"\b[\w.]{3,}\s+at\s+(?:gmail|yahoo|outlook|hotmail|icloud|proton)(?:\s+dot\s+\w+|\.\w+)", re.I)
_HANDLE = re.compile(r"(?<![\w@])@[a-z0-9_.]{3,30}\b", re.I)
_SOCIAL = re.compile(
    r"\b(?:insta(?:gram)?|ig|snap(?:chat)?|telegram|tg|fb|facebook|youtube|yt)\b\s*(?:id|handle|username)?\s*[:@]\s*[a-z0-9_.]{3,}"
    r"|\b(?:insta(?:gram)?|ig|snap(?:chat)?|telegram|tg)\b\s+(?:id|handle|username)\s*(?:is)?\s*[a-z0-9_.]{3,}", re.I)
_URL = re.compile(
    r"(?:https?://|www\.)\S+|\b[a-z0-9\-]+(?:\.[a-z0-9\-]+)*\.(?:com|in|org|net|co|io|me|ly|app|xyz|info|shop|store|club|online|site|link)\b(?:/\S*)?",
    re.I)
_REMOVED = "[removed]"


def strip_contact_details(text: str) -> tuple[str, dict[str, int]]:
    """Replace phone numbers, emails, handles and links with "[removed]". Returns the new text and a count of each kind."""
    counts = {"phone": 0, "email": 0, "handle": 0, "url": 0}

    def phone(m: re.Match) -> str:
        if sum(c.isdigit() for c in m.group(0)) >= 10:
            counts["phone"] += 1
            return _REMOVED
        return m.group(0)

    def bump(kind: str):
        def sub(_m: re.Match) -> str:
            counts[kind] += 1
            return _REMOVED
        return sub

    out = _EMAIL.sub(bump("email"), text)
    out = _EMAIL_AT.sub(bump("email"), out)
    out = _SOCIAL.sub(bump("handle"), out)
    out = _URL.sub(bump("url"), out)
    out = _HANDLE.sub(bump("handle"), out)
    out = _PHONE_CANDIDATE.sub(phone, out)
    out = _PHONE_WORDS.sub(bump("phone"), out)
    return out, counts


# --- rules --------------------------------------------------------------------------------------------------------------

_YOU = r"(?:you|u|ur|your|yourself|urself|tu|tum|tera|teri|tere|tujhe|tumhe|tumko|tujhko|aap|aapko|tumhari|tumhara)"
_THREAT = re.compile(
    r"\bkys\b|\b(?:kill|hang|burn)\s+(?:yourself|urself)\b"
    r"|\b(?:go|just|please)\s+(?:and\s+)?(?:die|kill\s+yourself|jump\s+off)\b"
    r"|\byou\s+(?:should|must|need\s+to|ought\s+to|deserve\s+to|better)\s+(?:just\s+)?(?:die|kill\s+yourself|be\s+killed|get\s+raped|rot)\b"
    r"|\bi(?:'ll|\s+will|\s+am\s+going\s+to|'m\s+going\s+to|'m\s+gonna|\s+would)\s+(?:kill|murder|beat|rape|find|hurt|stab|shoot|burn)\s+(?:you|u|him|her|them)\b"
    r"|\b(?:kill|murder|rape|stab|shoot|beat\s+up)\s+(?:you|u)\b"
    r"|\bi\s+know\s+where\s+(?:you|u|she|he)\s+(?:live|lives|stay|stays|work|works)\b"
    r"|\b(?:tujhe|tumhe|tereko|tujhko|usko|use)\s+(?:maar|mar|jaan\s+se|khatam)\b"
    r"|\b(?:maar|mar|jaan\s+se\s+maar)\s+(?:dunga|dungi|daalunga|daaloonga|denge|dalunga)\b"
    r"|\b(?:mar|maro)\s?ja+o\b|\bjaa\s+mar\b|\bmar\s+jaa\b",
    re.I)
_HATE = re.compile(
    r"\bkill\s+all\s+(?:the\s+)?(?:muslims?|hindus?|christians?|jews?|sikhs?|dalits?|gays?|trans|women|men|blacks?|whites?)\b"
    r"|\b(?:muslims?|hindus?|christians?|jews?|sikhs?|dalits?|gays?|women|blacks?)\s+(?:should|must|ought\s+to)\s+(?:die|be\s+killed|be\s+shot|burn|rot)\b",
    re.I)

_DOSE = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:mg|mcg|µg|iu|tablets?|tabs?|pills?|capsules?|caps|drops?|goli|goliyan)\b"
    r"|\b(?:a|an|one|two|three|four|half|1/2|ek|do|teen|aadhi|aadhe)\s+(?:tablets?|tabs?|pills?|capsules?|goli|goliyan|doses?)\b"
    r"|\b\d+(?:\.\d+)?\s*ml\b(?=.{0,40}\b(?:syrup|medicine|dawai|injection|suspension|cough)\b)"
    r"|\b\d+\s*units?\b(?=.{0,40}\binsulin\b)", re.I)
_MEDICINE_NAME = re.compile(
    r"\b(?:paracetamol|crocin|dolo|ibuprofen|brufen|combiflam|aspirin|metformin|insulin|levothyroxine|thyronorm|eltroxin|antibiotics?|amoxicillin|azithromycin|"
    r"cetirizine|pantoprazole|omez|ors|iron|calcium|vitamin|steroids?|prednisolone|sertraline|escitalopram|alprazolam|melatonin|ashwagandha|"
    r"contraceptive|ipill|i-pill|norethisterone|primolut|misoprostol)\b", re.I)
_VERB = (r"(?:take|taking|have|use|swallow|pop|eat|drink|start|consume|increase|double|apply|inject|get|go\s+for|"
         r"le\s+lo|le\s+lijiye|kha\s+lo|kha\s+lijiye|khao|lena|lete\s+raho|lena\s+shuru\s+karo)")
_ADVICE = re.compile(
    rf"^\W*(?:(?:just|also|maybe|please|so|then|and|always|try\s+to|try|better|you\s+(?:can|could|should|must|need\s+to|have\s+to|ought\s+to|better)(?:\s+just)?)\s+){{0,3}}{_VERB}\b"
    rf"|\byou\s+(?:can|could|should|must|need\s+to|have\s+to|ought\s+to|better|will\s+need\s+to)(?:\s+(?:just|also|simply))?\s+{_VERB}\b"
    r"|\b(?:tum|aap)\s+.{0,25}\b(?:le\s+lo|le\s+lijiye|kha\s+lo|kha\s+lijiye|lena)\b|\b(?:le\s+lo|kha\s+lo)\b", re.I)
_ASKING = re.compile(
    r"\?|\b(?:should\s+i|can\s+i|could\s+i|shall\s+i|do\s+i|is\s+it\s+(?:ok|okay|safe|fine)|how\s+much|what\s+dose|which\s+dose|kya\s+main|kya\s+mujhe|"
    r"kitni|kitna|kitne|is\s+it\s+normal|anyone\s+(?:tried|know|took|taking))\b", re.I)
_OWN = re.compile(
    r"\b(?:i|i'm|im|i've|ive|i'd|my|me|mine|myself|mera|meri|mere|mujhe|maine|mujhko|doctor\s+(?:said|told|gave|advised|prescribed)|"
    r"dr\.?\s+(?:said|told|gave)|prescribed|prescription\s+says)\b", re.I)

_STOP_VERB = (r"(?:stop|quit|skip|discontinue|avoid|never\s+take|don'?t\s+take|do\s+not\s+take|no\s+need\s+(?:to\s+take|for)|"
              r"throw\s+away|band\s+kar|band\s+karo|chhod\s+do|chhod\s+dena|chhodo|mat\s+lo|mat\s+lena|na\s+lo|nahi\s+leni|nahi\s+lena)")
_MED_NOUN = (r"(?:medicines?|medications?|meds|tablets?|pills?|insulin|antibiotics?|treatment|therapy|dawai|dawa|dawaiyan|goli|goliyan|"
             r"steroids?|antidepressants?|thyroid\s+(?:tablets?|medicine)|bp\s+(?:tablets?|medicine))")
_STOP = re.compile(
    rf"\b{_STOP_VERB}\b.{{0,30}}\b{_MED_NOUN}\b|\b{_MED_NOUN}\b.{{0,20}}\b(?:band\s+kar\s+do|band\s+karo|chhod\s+do|chhod\s+dena|mat\s+lo|na\s+lo|mat\s+lena)\b"
    r"|\byou\s+(?:don'?t|do\s+not)\s+need\s+(?:any\s+|a\s+)?(?:medicines?|medications?|tablets?|pills?|treatment)\b", re.I)
_NO_DOCTOR = re.compile(
    r"\b(?:no\s+need\s+(?:to|for)\s+(?:see|visit|consult|go\s+to)\s+(?:a\s+|the\s+|any\s+)?(?:doctor|hospital|gynae\w*)|"
    r"(?:don'?t|do\s+not|never)\s+(?:see|visit|consult|go\s+to)\s+(?:a\s+|the\s+|any\s+)?(?:doctor|hospital)|"
    r"you\s+(?:don'?t|do\s+not)\s+need\s+(?:a\s+|any\s+)?(?:doctor|hospital))\b", re.I)
_STOP_OWN_OR_ASKING = re.compile(
    r"\bshould\s+i\b|\bcan\s+i\b|\bcould\s+i\b|\bdo\s+i\b|\bshall\s+i\b|\bis\s+it\s+(?:ok|okay|safe|fine)\b|\bkya\s+main\b|\bkya\s+mujhe\b|\bi\s+(?:have\s+|'ve\s+|had\s+)?"
    r"(?:stopped|quit|skipped|left|stop|want\s+to\s+stop|wanna\s+stop|am\s+thinking|'m\s+thinking|am\s+planning|'m\s+planning|don'?t|do\s+not|never|forgot)\b|\bi'?ve\s+(?:stopped|quit|skipped)\b|"
    r"\bthinking\s+(?:of|about)\s+(?:stopping|quitting|skipping)\b|\bmy\s+doctor\b|\bdoctor\s+(?:said|told|asked|ne)\b|\bdr\.?\s+(?:said|told)\b|\bmaine\b|\bmujhe\b|"
    r"\bask\s+(?:your|a|the)\s+doctor\b|\bdoctor\s+se\s+pooch|\btalk\s+to\s+(?:your|a|the)\s+doctor\b|\bspeak\s+to\s+(?:your|a|the)\s+doctor\b", re.I)

_COND = (r"(?:pcos|pcod|thyroid|hypothyroid(?:ism)?|hyperthyroid(?:ism)?|diabet\w+|cancer|tumou?rs?|anaemi\w+|anemi\w+|endometriosis|fibroids?|"
         r"depression|bipolar|adhd|autis\w+|hiv|aids|tb|tuberculosis|hepatitis|ulcers?|epilepsy|asthma|arthritis|pregnan\w+|miscarriage|"
         r"infertil\w+|ocd|schizophren\w+|kidney\s+(?:stones?|failure|disease)|heart\s+(?:disease|attack|problem)|anxiety\s+disorder)")
_CERTAIN = r"(?:definitely|clearly|surely|obviously|certainly|100%|for\s+sure|without\s+doubt|pakka|zaroor|bilkul)"
_HEDGE = re.compile(
    r"\?|\b(?:if|may|might|could|maybe|perhaps|possibly|probably|wonder|wondering|suppose|seems?|looks?\s+like|sounds?\s+like|do\s+you|did\s+you|have\s+you|"
    r"when|since|because|whether|ask|check|test|tested|diagnosed|doctor|kya|shayad|ho\s+sakta)\b", re.I)
_DIAGNOSIS = re.compile(
    rf"\byou(?:'ve|\s+have|\s+got|'re|\s+are|\s+must\s+have|\s+must\s+be)?\s*(?:{_CERTAIN}\s+)?(?:have|got|has|are|must\s+have|must\s+be|suffer(?:ing)?\s+from)\s+(?:a\s+|an\s+|the\s+)?"
    rf"(?:{_COND}|anaemic|anemic|diabetic|depressed|pregnant|infertile)\b"
    rf"|\b(?:this|that|it|ye|yeh)(?:'s|\s+is|\s+hai)\s+{_CERTAIN}\s+(?:a\s+|an\s+|the\s+|your\s+)?{_COND}\b"
    rf"|\b(?:tumhe|tujhe|aapko|tumko)\s+(?:{_CERTAIN}\s+)?(?:{_COND}|sugar)\s+(?:hai|hoga|ho\s+gaya)\b"
    rf"|\b(?:ye|yeh|ye\s+to|ye\s+toh)\s+{_COND}\s+(?:hi\s+)?hai\b", re.I)
_CURE_WORD = re.compile(r"\b(?:cure|cures|cured|reverse|reverses|reversed|heal|heals|healed)\b", re.I)
_CURE_COND = re.compile(r"\b(?:cancer|diabetes|pcos|pcod|thyroid|hiv|tb|depression|infertility|fibroids?|anxiety|arthritis)\b", re.I)
_CURE_CLAIM = re.compile(r"100\s?%|guarantee\w*|permanent\w*|miracle|overnight|completely|totally|forever|\bin\s+\d+\s+(?:days|weeks|months)\b|pakka|bilkul", re.I)

_ADVICE_WINDOW = 18   # a first-person word in the first 18 characters means the advice is about the writer ("I take...")
_PRICE = re.compile(r"(?:₹|rs\.?|inr)\s?\d|\b\d+\s?(?:rs|rupees|rupee|/-)\b|\bonly\s+\d+\b|\bcod\b", re.I)
_PRODUCT = re.compile(r"\b(?:medicines?|medication|pills?|tablets?|capsules?|cure|product|products|course|treatment|supplements?|powder|oil|kit|dawai|goli)\b", re.I)

_SENTENCES = re.compile(r"(?<=[.!?\n])\s+|\n+")


def _sentences(text: str) -> list[str]:
    return [s for s in _SENTENCES.split(text) if s and s.strip()]


def _normalise(text: str) -> str:
    t = unicodedata.normalize("NFKC", text or "")
    t = re.sub(r"[​-‏⁠﻿]", "", t)
    return re.sub(r"[ \t]+", " ", t).strip()


def _directed(sentence: str) -> bool:
    """True when strong language sits in a sentence that also addresses a person ("you", "tu", "tera"...)."""
    return re.search(rf"\b{_YOU}\b", sentence, re.I) is not None


_NEGATED_STOP = re.compile(r"\b(?:don'?t|do\s+not|never|not|shouldn'?t|should\s+not|mustn'?t|please\s+don'?t)\s+(?:ever\s+|just\s+)?(?:stop|quit|skip|discontinue)\b", re.I)
_IMPERATIVE_STOP = re.compile(
    rf"^\W*(?:(?:just|also|please|so|then|and|you\s+(?:can|should|must)|better)\s+){{0,3}}{_STOP_VERB}\b", re.I)
_HINGLISH_STOP = re.compile(r"\b(?:band\s+kar\s+do|band\s+karo|chhod\s+do|chhod\s+dena|chhodo|mat\s+lo|mat\s+lena|na\s+lo|nahi\s+lena)\b", re.I)


def _stop_medicine(sentence: str) -> bool:
    """Telling someone else to stop a medicine or skip a doctor. A person's own story, a question, or "never stop" is not this."""
    s = _NEGATED_STOP.sub(" ", sentence)
    if _NO_DOCTOR.search(s) and not re.search(r"\b(?:i|i'm|my|me|we)\b", s, re.I):
        return True
    if not _STOP.search(s) or _STOP_OWN_OR_ASKING.search(s):
        return False
    return bool(_IMPERATIVE_STOP.search(s) or _HINGLISH_STOP.search(s) or re.search(rf"\b{_YOU}\b", s, re.I))


def _dose_advice(sentence: str) -> str | None:
    """'dose_advice' (certain), 'dose_review' (unsure) or None for one sentence."""
    if not _DOSE.search(sentence):
        return None
    if _ADVICE.search(sentence) and not _ASKING.search(sentence):
        if not re.search(r"\b(?:i|i'm|i've|my|me)\b", sentence[: _ADVICE_WINDOW], re.I):
            return "dose_advice"
    if _OWN.search(sentence) or _ASKING.search(sentence):
        return None
    if _MEDICINE_NAME.search(sentence) or re.search(r"\b(?:tablets?|pills?|capsules?)\b", sentence, re.I):
        return "dose_review"
    return None



def _diagnosis(sentence: str) -> bool:
    return bool(_DIAGNOSIS.search(sentence)) and not _HEDGE.search(sentence)


def _cure_claim(sentence: str) -> bool:
    return bool(_CURE_WORD.search(sentence) and _CURE_COND.search(sentence) and _CURE_CLAIM.search(sentence))


def _shouting(text: str) -> bool:
    letters = [c for c in text if c.isalpha()]
    return len(letters) >= 25 and sum(c.isupper() for c in letters) / len(letters) >= 0.75


def _repeats(text: str) -> bool:
    if re.search(r"(.)\1{9,}", text):
        return True
    words = re.findall(r"\w+", text.casefold())
    if len(words) >= 8:
        top = max(words.count(w) for w in set(words) if len(w) >= 3) if any(len(w) >= 3 for w in words) else 0
        if top / len(words) > 0.5:
            return True
    return False


def moderate(text: str, *, crisis: bool = False) -> Decision:
    """Decide one post or comment. ``crisis`` is True when the safety engine found crisis wording about the writer."""
    try:
        return _moderate(text, crisis)
    except Exception:  # noqa: BLE001 - a rule that breaks must hold the text, never show it unchecked
        return Decision(HOLD, "moderation_error", _normalise(text))


def _moderate(raw: str, crisis: bool) -> Decision:
    lists = _lists()
    text = _normalise(raw)
    clean, found = strip_contact_details(text)
    contact = sum(found.values())
    notes = ("contact_removed",) if contact else ()

    def out(action: str, reason: str | None) -> Decision:
        return Decision(action, reason, clean, notes)

    if not lists.ready:
        return out(HOLD, "moderation_error")
    if not re.search(r"[^\W_]", clean.replace(_REMOVED, "")):
        return out(HOLD, "spam")
    verdict = _judge(clean, crisis, lists, found)
    if verdict[0] == ALLOW:   # the same rules over a decoded copy: leetspeak (T@ke 5OO), dotted or spaced letters (k.i.l.l)
        alt = _decode(clean)
        if alt != clean:
            again = _judge(alt, crisis, lists, found)
            if again[0] != ALLOW:
                verdict = again
    return out(*verdict)


_SPACED = re.compile(r"(?<![^\W\d_])(?:[^\W\d_][.\-_*\s]){3,}[^\W\d_](?![^\W\d_])")
_INWORD = {"@": "a", "$": "s", "3": "e", "1": "i", "0": "o", "4": "a", "5": "s", "7": "t", "!": "i"}


def _decode(text: str) -> str:
    """A reading of the text with common disguises undone. Only used to look for rule hits; never stored or shown."""
    t = _SPACED.sub(lambda m: re.sub(r"[.\-_*\s]", "", m.group()), text)
    t = re.sub(r"(?<=[^\W\d_])([@$3140 57!])(?=[^\W\d_])", lambda m: _INWORD.get(m.group(1), m.group(1)), t)
    for _ in range(3):   # 5OO -> 500
        t = re.sub(r"(?<=\d)[oOlI](?=[\doOlI\s]|$)|(?<=[ ])[oO](?=\d)", lambda m: "0" if m.group() in "oO" else "1", t)
    return t


def _judge(clean: str, crisis: bool, lists, found: dict) -> tuple[str, str | None]:
    sentences = _sentences(clean)
    folded = clean.casefold()

    # threats and hate aimed at people are removed even when the writer is also in crisis
    if _THREAT.search(folded):
        return (REMOVE, "threat")
    if _HATE.search(folded):
        return (REMOVE, "hate")
    if crisis:
        return (ALLOW, None)

    if lists.slurs.search(folded):
        return (REMOVE, "hate")
    if lists.sex_remove.search(folded):
        return (REMOVE, "sexual")
    strong = [s for s in sentences if lists.strong.search(s.casefold())]
    if any(_directed(s) for s in strong):
        return (REMOVE, "abuse")
    selling_hit = bool(lists.selling.search(folded))
    if selling_hit and (sum(found.values()) or _PRICE.search(folded) or _PRODUCT.search(folded)):
        return (REMOVE, "selling")
    for s in sentences:
        if _stop_medicine(s):
            return (REMOVE, "stop_medicine")
    unsure: str | None = None
    for s in sentences:
        verdict = _dose_advice(s)
        if verdict == "dose_advice":
            return (REMOVE, "dose_advice")
        if verdict == "dose_review":
            unsure = unsure or "dose_review"

    if strong:
        return (HOLD, "profanity")
    if lists.sex_hold.search(folded):
        return (HOLD, "sexual_review")
    if selling_hit:
        return (HOLD, "selling_review")
    if found["url"] >= 2 or _repeats(clean):
        return (HOLD, "spam")
    if _shouting(clean):
        return (HOLD, "shouting")
    if any(_diagnosis(s) for s in sentences):
        return (HOLD, "diagnosis_claim")
    if any(_cure_claim(s) for s in sentences):
        return (HOLD, "cure_claim")
    if unsure:
        return (HOLD, unsure)
    return (ALLOW, None)


# --- crisis wording (the safety engine decides; nothing about the text is kept) -------------------------------------------

def safety_signal(text: str):
    """The safety engine's assessment of a post, or None when it finds nothing (a failure counts as a crisis signal). Deterministic, local, no model."""
    try:
        import safety_engine
        a = safety_engine.assess_safety(text)
    except Exception:  # noqa: BLE001 - fail closed: treat an unreadable post as a crisis one (held for review, support lines shown)
        from types import SimpleNamespace
        return SimpleNamespace(crisis=True, state="URGENT")
    return a if (a.crisis or a.state in ("URGENT", "EMERGENCY")) else None
