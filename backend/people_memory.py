"""The people and pets in a person's life, as they tell Bubbles about them ("my boyfriend's name is Ashmit", "my dog is called Bruno").

Pure text rules, no database and no model, so they are instant, free, and the same every time:
- ``extract_people_facts``: what the person said, as facts for memory_manager to save (same shape as its other facts);
- ``recall_target``: whether a message asks Bubbles to recall one of them ("what's my boyfriend's name?", "do you remember my name?");
- ``remembered_reply`` / ``recall_reply``: the warm one-line answers for those two cases.

Only first-person statements count. A negated, hypothetical, quoted or questioning phrasing is ignored (memory_manager._is_hedged), and a
sentence about someone else ("his boyfriend is...") never matches because every pattern needs "my" or "I".
"""
from __future__ import annotations

import hashlib
import re
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
}
_ONE_PERSON = frozenset({"partner", "mother", "father"})   # a new name for these is a correction of the old one
_PETS = frozenset({"dog", "cat", "pet"})
_REL = "|".join(sorted((re.escape(r) for r in _RELATIONS), key=len, reverse=True))
_WORD = r"[A-Za-z][A-Za-z'’-]*"
_NAME = rf"({_WORD}(?:[ \t]+{_WORD})?)"
_POSS = r"(?:['’]s|s)?"

# Words that follow "my boyfriend is ..." and are NOT a name; also what a sentence-start word could be in "X is my boyfriend".
_NOT_NAMES = frozenset("""a an the my your his her their our not no so very really quite too just also still always never now here there who what why how when where
he she it they we you i this that these those someone somebody anyone nobody something nothing everyone also doing fine ok okay good bad sad happy angry upset
tired sick ill unwell away home late early busy gone back coming leaving going getting being feeling mine yours his hers ours theirs one two three""".split())

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


def _tidy_name(raw: str, *, need_capital: bool) -> str | None:
    """One or two words from the capture: the second only when both are capitalised ("Mary Ann"); lower-case typing is title-cased."""
    words = [w for w in raw.replace("’", "'").split() if w]
    if not words:
        return None
    first = words[0]
    if first.lower() in _NOT_NAMES or (need_capital and not first[0].isupper()):
        return None
    keep = [first]
    if len(words) > 1 and first[0].isupper() and words[1][0].isupper() and words[1].lower() not in _NOT_NAMES:
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


def _reported(text: str, m: re.Match) -> bool:
    """True when the same sentence passes the statement on from someone else ("she said my boyfriend is Ashmit")."""
    start = m.start()
    boundary = max(text.rfind(c, 0, start) for c in ".!?\n") + 1
    return bool(_REPORTED.search(text[boundary:start]))


def extract_people_facts(text: str, hedged: Callable[[str, re.Match], bool]) -> list[dict[str, Any]]:
    """Facts about people and pets in ``text``, at most four. ``hedged(text, match)`` says whether the match is negated, hypothetical,
    quoted or a question (memory_manager passes its own check, so there is one rule for what counts as a plain statement)."""
    text = (text or "").replace("’", "'")
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    def add(group: str, spoken: str, name: str | None) -> None:
        if name and len(out) < 4 and (group, name.lower()) not in seen:
            seen.add((group, name.lower()))
            out.append(_fact(group, spoken, name))

    for kind, pattern in _PATTERNS:
        for m in pattern.finditer(text):
            if hedged(text, m) or _reported(text, m):
                continue
            if kind == "dating":
                add("partner", "partner", _tidy_name(m.group(1), need_capital=True))
                continue
            group, spoken = _RELATIONS[m.group("rel").lower()]
            add(group, spoken, _tidy_name(m.group(m.lastindex), need_capital=(kind == "capital")))
    for m in _NAME_FIRST.finditer(text):
        if hedged(text, m) or _reported(text, m):
            continue
        group, spoken = _RELATIONS[m.group("rel").lower()]
        add(group, spoken, _tidy_name(m.group("n"), need_capital=True))
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
