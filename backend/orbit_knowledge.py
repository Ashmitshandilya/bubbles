"""Orbit pattern cards: curated general knowledge about relationships, offered to the model only when the person's own words match.

``data/orbit_knowledge.json`` holds about thirty cards. ``cards_for(text, history, limit=2)`` scores them by signals (English, Roman-script Hindi and
Devanagari) and returns the best one or two; ``prompt_block`` turns them into the block the Heart-to-heart prompt carries. A card is never a fact about
this person or their partner, never a diagnosis, and never a verdict: every card lists what must never be said, and the schema test refuses numbers and
percentages in what a card claims.

A signal is a short phrase. It matches when all of its content words appear close together in the message, in any order, after light stemming and with
near-synonyms folded together ("yelled" and "shouted", "partner" and "boyfriend", "ladai" and "fight"). Exact phrases would miss almost every real message.

Pure and cheap: the file is read once.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import hinglish_terms

PATH = Path(__file__).resolve().parent / "data" / "orbit_knowledge.json"
EVIDENCE_RANK = {"strong": 3, "moderate": 2, "practice": 1}
REQUIRED = ("id", "title", "signals", "what_it_is", "what_helps", "evidence", "cultures", "never_say", "source")
HISTORY_WEIGHT = 0.5

#: spellings people use for the same Hinglish word, folded to one form
_VARIANTS = {
    r"\b(?:nahin|nhi|nai|nahee)\b": "nahi", r"\bkrta\b": "karta", r"\bkrti\b": "karti", r"\bpyar\b": "pyaar", r"\b(?:jhuth|jhoot|jhut)\b": "jhooth",
    r"\b(?:gusa|gussaa)\b": "gussa", r"\bmujse\b": "mujhse", r"\bdimag\b": "dimaag", r"\bshadi\b": "shaadi", r"\bbharose\b": "bharosa",
    r"\bmafi\b": "maafi", r"\b(?:chod|chhod|chodd)\b": "chhod", r"\bchupchap\b": "chup chap", r"\bpariwar\b": "parivaar",
}
_VARIANT_RX = [(re.compile(p), r) for p, r in _VARIANTS.items()]

_STOP = frozenset((
    "a an the to of in on at and or but so it its is am are was were be been being do does did done have has had i me my mine we us our you your he him his she her "
    "hers they them their that this these those with for from by as not no nor very just really also too then than when while if because about into out up over "
    "again still always never ever even only each every one some any more much many get got gets getting make makes made let lets like want wants wanted need needs "
    "needed feel feels felt after how what why where who other ago since would could should can will cant wont dont doesnt didnt isnt arent wasnt im ive id ill thing things way lot bit "
    "hai hain ho hoon hu hun ka ki ke ko se me mein par pe ne tha thi the aur bhi to toh ya kya mera meri mere mujhe mujhse main hum ham tum aap woh wo usne usse "
    "uska uski uske yeh ye is us in koi kuch bahut bohot abhi phir fir jab tab raha rahi rahe lagta lagti lagte").split())

#: words that mean the same thing for matching (looked up after light stemming)
_SYN = {
    "speak": "talk", "chat": "talk", "discuss": "talk", "convers": "talk", "baat": "talk", "bol": "talk", "bolna": "talk",
    "messag": "text", "msg": "text", "dm": "text", "whatsapp": "text", "ping": "text",
    "answer": "reply", "respond": "reply", "respons": "reply", "jawab": "reply",
    "quiet": "silent", "mute": "silent", "ghost": "silent", "unrespons": "silent", "chup": "silent", "khamosh": "silent", "silenc": "silent",
    "yell": "shout", "scream": "shout", "chilla": "shout", "chillan": "shout", "bark": "shout",
    "furious": "angry", "mad": "angry", "rage": "angry", "livid": "angry", "gussa": "angry", "gusse": "angry",
    "argu": "fight", "argue": "fight", "fought": "fight", "argument": "fight", "quarrel": "fight", "ladai": "fight", "ladt": "fight", "lad": "fight", "jhagda": "fight", "jhagd": "fight", "jhagade": "fight",
    "row": "fight", "bicker": "fight", "arguing": "fight",
    "neglect": "ignor", "overlook": "ignor", "dismiss": "ignor", "ignore": "ignor",
    "laugh": "mock", "tease": "mock", "sneer": "mock", "belittl": "mock", "ridicul": "mock", "taan": "mock", "taane": "mock", "mazaak": "mock", "mocks": "mock",
    "accus": "blame", "fault": "blame", "galti": "blame", "excus": "blame",
    "hormon": "pms", "premenstru": "pms", "period": "pms",
    "mother": "inlaw", "law": "inlaw", "saas": "inlaw", "sasur": "inlaw", "sasural": "inlaw",
    "relative": "relativ", "rishtedaar": "relativ", "mehmaan": "relativ", "guest": "relativ",
    "affair": "cheat",
    "liar": "lie", "jhooth": "lie",
    "hide": "hid", "hidden": "hid", "chhupa": "hid", "secret": "hid",
    "read": "check", "snoop": "check", "spy": "check", "stalk": "check", "track": "check", "monitor": "check", "dekh": "check",
    "paise": "money", "paisa": "money", "salary": "money", "spend": "money", "saving": "money", "save": "money", "financ": "money", "afford": "money", "sending": "money",
    "newborn": "baby", "son": "baby", "daughter": "baby", "bachch": "baby", "bachcha": "baby", "delivery": "baby",
    "alone": "privat", "privacy": "privat",
    "akela": "lonely", "akeli": "lonely",
    "apolog": "sorry", "maafi": "sorry", "maaf": "sorry",
    "exboyfriend": "ex", "exgirlfriend": "ex",
    "abroad": "distanc", "zone": "distanc", "dooriyan": "distanc", "door": "distanc", "distance": "distanc",
    "caste": "religion", "community": "religion", "jaati": "religion", "dharm": "religion", "faith": "religion",
    "closeness": "intimat", "physical": "intimat", "sex": "intimat", "sexual": "intimat", "intimacy": "intimat",
    "depress": "low", "sad": "low", "down": "low", "udaas": "low", "struggl": "low",
    "boyfriend": "partner", "girlfriend": "partner", "husband": "partner", "wife": "partner", "bf": "partner", "gf": "partner", "fiance": "partner", "spouse": "partner",
    "pati": "partner", "patni": "partner", "biwi": "partner",
    "decision": "decid", "choic": "decid", "raay": "decid", "opinion": "decid", "wish": "decid", "view": "decid",
    "realis": "notic", "dhyan": "notic", "look": "notic",
    "sun": "listen", "hear": "listen",
}


#: stems distinctive enough to count as a signal on their own
_SINGLE_OK = frozenset({"unseen", "invisible", "stranger", "mock", "humiliat", "situationship", "stonewal", "ldr", "inlaw", "chidchidi", "jealous", "withdraw", "heartbroken", "taunt", "sasural", "reconcil"})


def normalize(text: Any) -> str:
    """Lower case, Devanagari to Roman, apostrophes dropped, punctuation to spaces, spelling variants folded."""
    t = hinglish_terms.transliterate(str(text or "")[:2000]).lower().replace("’", "'")
    t = t.replace("'", "")
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    for rx, repl in _VARIANT_RX:
        t = rx.sub(repl, t)
    return re.sub(r"\s+", " ", t).strip()


def _stem(word: str) -> str:
    w = word
    for suffix in ("ing", "ed", "es", "ly", "s"):
        if w.endswith(suffix) and len(w) - len(suffix) >= 3:
            w = w[: -len(suffix)]
            break
    if len(w) > 3 and w[-1] == w[-2] and w[-1] not in "sl":
        w = w[:-1]
    return _SYN.get(w, _SYN.get(word, w))


def stems(text: str) -> list[str]:
    """Content words of a normalized text, lightly stemmed, with stop words dropped and near-synonyms folded together."""
    return [_stem(w) for w in text.split() if w not in _STOP and len(w) > 1]


def _signal_matches(sig: tuple[str, ...], tokens: list[str]) -> bool:
    """All content words of the signal appear in the text within a short window, in any order."""
    if not sig:
        return False
    positions = {w: [i for i, t in enumerate(tokens) if t == w] for w in set(sig)}
    if any(not p for p in positions.values()):
        return False
    if len(positions) == 1:
        return True
    window = len(sig) + 4
    anchor = min(positions, key=lambda w: len(positions[w]))
    return any(all(any(abs(i - a) <= window for i in positions[w]) for w in positions if w != anchor) for a in positions[anchor])


@lru_cache(maxsize=1)
def cards() -> tuple[dict[str, Any], ...]:
    data = json.loads(PATH.read_text(encoding="utf-8"))
    out = []
    for card in data["cards"]:
        card = dict(card)
        sigs: list[tuple[str, ...]] = []
        for raw in card["signals"]:
            st = tuple(dict.fromkeys(stems(normalize(raw))))
            if len(st) < 2 and not (st and st[0] in _SINGLE_OK):
                continue          # one common word on its own matches too much ("love", "baby", "broke"); only distinctive words may stand alone
            if st not in sigs:
                sigs.append(st)
        card["_signals"] = tuple(sigs)
        card["_vocab"] = frozenset(w for sig in sigs for w in sig)
        out.append(card)
    # a word that appears in few cards' signals is distinctive; one that appears in many says almost nothing
    counts: dict[str, int] = {}
    for card in out:
        for w in card["_vocab"]:
            counts[w] = counts.get(w, 0) + 1
    weight = {w: 1.0 if n == 1 else 0.5 if n == 2 else 0.25 if n <= 4 else 0.0 for w, n in counts.items()}
    for card in out:
        card["_weights"] = {w: weight[w] for w in card["_vocab"] if weight[w] > 0}
    return tuple(out)


def by_id(card_id: str) -> dict[str, Any] | None:
    return next((c for c in cards() if c["id"] == card_id), None)


LOOSE_THRESHOLD = 1.5


def _hits(card: dict[str, Any], tokens: list[str], loose: bool = False) -> float:
    """Strict signal matches count one each. In ``loose`` mode (used only when the talk is already about a relationship, so a stray card does little
    harm), enough distinctive words of the card's own vocabulary count as one half: a word only this card uses is worth a full point, a word shared by
    a few cards less, a common word nothing."""
    strict = sum(1 for sig in card["_signals"] if _signal_matches(sig, tokens))
    if strict or not loose:
        return float(strict)
    weights = card["_weights"]
    return 0.5 if sum(weights[w] for w in set(tokens) if w in weights) >= LOOSE_THRESHOLD else 0.0


def _user_texts(history: list[dict[str, Any]] | None, n: int = 2) -> list[list[str]]:
    rows = [r for r in (history or []) if r.get("role") == "user" and r.get("content")]
    return [stems(normalize(r["content"])) for r in rows[-n:]]


def cards_for(text: Any, history: list[dict[str, Any]] | None = None, limit: int = 2, loose: bool = False) -> list[dict[str, Any]]:
    """The best cards for what the person just wrote, at most ``limit``. A card needs at least one signal in the new message itself; earlier messages
    in the conversation only add a little weight, so a card never comes from old talk alone. Ties go to stronger evidence, then to the card id."""
    current = stems(normalize(text))
    if not current:
        return []
    earlier = _user_texts(history)
    scored = []
    for card in cards():
        now = _hits(card, current, loose)
        if not now:
            continue
        score = now + HISTORY_WEIGHT * min(1, sum(_hits(card, e) for e in earlier))
        scored.append((-score, -EVIDENCE_RANK.get(card["evidence"], 0), card["id"], card))
    scored.sort(key=lambda row: row[:3])
    return [row[3] for row in scored[: max(0, limit)]]


def prompt_block(selected: list[dict[str, Any]], country: Any = None) -> str:
    """The PATTERN CARDS block for the prompt, or "". Culture notes are included only for India (and for a person who never said)."""
    if not selected:
        return ""
    from locale_support import normalize_country
    india = normalize_country(country) == "IN"
    lines = ["PATTERN CARDS (general knowledge, not facts about this person. Use one only if their own words match it, in your own words, "
             "and never name a pattern as a diagnosis or a verdict):"]
    for c in selected:
        line = f"- {c['title']}: {c['what_it_is']} What tends to help: " + "; ".join(c["what_helps"]) + "."
        note = (c.get("cultures") or {}).get("IN") if india else None
        if note:
            line += f" Note for India: {note}"
        lines.append(line)
    avoid = sorted({phrase for c in selected for phrase in c["never_say"]})
    lines.append("Never say: " + "; ".join(avoid) + ".")
    return "\n".join(lines)


def catalogue_block(country: Any = None) -> str:
    """When no card matches by words, the model gets every card as one short line and picks the one that fits (or none): word matching misses
    most fresh phrasing, the model does not. Used only for relationship talk, and dropped first when the prompt is full."""
    from locale_support import normalize_country
    lines = ["PATTERN CARDS (general knowledge, not facts about this person. If one of these clearly fits what they describe, use its idea in your own words; "
             "if none fits, ignore all of them. Never name a pattern as a diagnosis or a verdict):"]
    for c in cards():
        first = re.split(r"(?<=[.!?])\s", c["what_it_is"], maxsplit=1)[0]
        lines.append(f"- {c['title']}: {first[:90]}")
    return chr(10).join(lines)


def validate() -> list[str]:
    """Problems with the card file, as readable strings (empty = fine). The test runs this."""
    problems: list[str] = []
    seen: set[str] = set()
    for c in cards():
        cid = c.get("id", "?")
        for field in REQUIRED:
            if field not in c or (c[field] in (None, "", [], ()) and field != "cultures"):
                problems.append(f"{cid}: missing {field}")
        if cid in seen:
            problems.append(f"{cid}: duplicate id")
        seen.add(cid)
        if c.get("evidence") not in EVIDENCE_RANK:
            problems.append(f"{cid}: evidence must be one of {sorted(EVIDENCE_RANK)}")
        if len(c.get("signals") or []) < 6:
            problems.append(f"{cid}: needs at least six signals")
        if re.search(r"\d|%|percent", c.get("what_it_is", ""), re.I):
            problems.append(f"{cid}: what_it_is has a number or percentage")
        if any(re.search(r"\d|%|percent", h, re.I) for h in c.get("what_helps", [])):
            problems.append(f"{cid}: what_helps has a number or percentage")
        if not c.get("never_say"):
            problems.append(f"{cid}: never_say is empty")
        if not isinstance(c.get("cultures"), dict) or any(k not in ("IN",) for k in c["cultures"]):
            problems.append(f"{cid}: cultures must be an object with only known country codes")
    return problems
