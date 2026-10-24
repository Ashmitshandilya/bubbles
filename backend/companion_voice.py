"""The friend voice: warm, varied replies to feelings and good news, written by Bubbles itself (no outside model).

Pure. For a message that is only about a feeling (stress, worry, loneliness, a low day, missing someone, tiredness) or good news, Bubbles answers like a caring
friend: it says it heard you, normalises the feeling without brushing it off, offers one small step and one caring question. It adapts to the person's own
tone and reply length (Person Model) and to English or Hinglish. Anything that sounds like hopelessness, self-harm, severity, a long-lasting problem or a
health symptom beyond tiredness is NOT answered here: that goes the safety route or to the model, as before.
"""
from __future__ import annotations

import hashlib
import re
from typing import Iterable

# what the message must NOT contain for the friend voice to answer it on its own
_NOT_FOR_THIS = re.compile(
    r"\b(?:hopeless|worthless|no\s+point|give\s+up|giving\s+up|can'?t\s+go\s+on|don'?t\s+want\s+to\s+(?:live|be\s+here|exist)|end\s+it|kill|die|dying|suicid\w+|self[- ]?harm|"
    r"hurt\s+myself|cut\s+myself|do\s+something\s+(?:stupid|drastic|crazy|rash|silly)|might\s+do\s+something|trapped|controls?\s+my|disappear\w*|abuse\w*|hits?\s+me|beat\w*|assault\w*|rape\w*|unsafe|threat\w*|"
    r"for\s+(?:weeks|months|years)|since\s+(?:weeks|months|years)|every\s+day|all\s+the\s+time|always|never\s+(?:feel|happy)|"
    r"pregnan\w+|medicine|medication|tablets?|doctor|hospital|diagnos\w+|"
    r"disorder|disease|illness|syndrome|condition|depress\w*|bipolar|ocd|ptsd|schizo\w*|adhd|autis\w*|do\s+i\s+have|am\s+i\s+(?:sick|ill|mad|crazy)|"
    r"har\s+din|roz|hamesha|lagatar|kai\s+(?:hafte|mahine)|hafto|mahino|"
    r"mar\s+jana|jeena\s+nahi|jaan\s+de)\b", re.I)
# a feeling someone else has is not the person's own: "my mother feels very sad" goes to the model, "I miss my mom" stays
_THIRD_PERSON = re.compile(r"\b(?:my\s+(?:mother|mom|mum|father|dad|friend|brother|sister|husband|wife|boyfriend|girlfriend|partner|son|daughter|boss|colleague|neighbou?r)|he|she|they|his|her|their)\b", re.I)
_FIRST_PERSON = re.compile(r"\b(?:i|i'm|im|i've|ive|i'd|me|myself|main|mujhe|mera|meri|mere|maine)\b", re.I)
# stress and overwhelm are not health-semantics concepts; these words carry them
_STRESS = re.compile(r"\b(?:stress(?:ed|ful)?|overwhelm\w*|burn(?:ed|t)\s*out|swamped|too\s+much\s+(?:work|on\s+my\s+plate)|tension|tensed|pressure\s+(?:at|of)\s+(?:work|college|exams?))\b|\bstressed\s+out\b", re.I)
_JOY = re.compile(
    r"\b(?:got\s+(?:the|a)\s+(?:job|promotion|offer|internship|raise)|promoted|i\s+passed|passed\s+my|cleared\s+(?:my|the)|so\s+happy|really\s+happy|feeling\s+(?:great|amazing|fantastic|wonderful|"
    r"so\s+good|really\s+good)|great\s+day|good\s+news|excited|proud\s+of\s+myself|nailed\s+it|did\s+it|best\s+day|khush|bahut\s+khush|maza\s+aa\s+raha|grateful|thankful|nice\s+day|good\s+mood|great\s+workout|feel\s+amazing)\b", re.I)
_TIRED = re.compile(r"\b(?:so\s+tired|very\s+tired|really\s+tired|exhausted|drained|wiped\s+out|worn\s+out|thak\s+gaya|thak\s+gayi|bahut\s+thak|thaka\s+hua|thaki\s+hui|energy\s+nahi)\b", re.I)
# softer everyday feelings that carry no symptom: nerves, missing home or family, an ordinary hard day (each needs a first-person cue, checked above)
_NERVOUS = re.compile(r"\b(?:nervous|worried\s+about|anxious\s+about|jittery|on\s+edge)\b", re.I)
_MISSING = re.compile(r"\bmiss(?:ing)?\s+(?:my\s+)?(?:family|home|hometown|parents|friends|college|school|ghar)\b|\bghar\s+ki\s+yaad\b", re.I)
_LOWISH = re.compile(
    r"\b(?:feel(?:ing)?\s+like\s+crying|want\s+to\s+cry|(?:such\s+a\s+)?(?:hard|tough|rough|bad)\s+day|feel(?:ing)?\s+(?:kind\s+of\s+)?empty|bored\s+and\s+(?:a\s+bit\s+)?down|need\s+a\s+hug|"
    r"udaas\w*|man\s+nahi\s+lag\s+raha)\b", re.I)
_QUESTION_FOR_INFO = re.compile(r"\b(?:how\s+(?:to|can|do|much|many)|what\s+(?:is|are|should)|why|tips?|advice|suggest|which|kaise|kya\s+karu)\b", re.I)

MIND_CONCEPTS = ("panic_attack", "separation_anxiety", "loneliness", "anxiety", "low_mood")
FEEL_CONCEPTS = ("panic_attack", "separation_anxiety", "loneliness", "anxiety", "low_mood", "stress", "tired", "joy")

# concept -> (validations, small steps, caring questions), English
EN: dict[str, tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]] = {
    "loneliness": (
        ("That sounds really lonely, and I'm glad you told me.", "Feeling lonely is heavy, and it doesn't mean anything is wrong with you.", "I'm right here with you. Lonely moments can feel so big."),
        ("One low-pressure reach-out can help: a short message to someone you like, even just a hello.", "Sometimes a small, easy plan helps, like a short call or a walk where there are other people around."),
        ("Is there someone you'd feel okay sending a small hello to?", "Do you want to tell me what's making today feel lonely?")),
    "anxiety": (
        ("That sounds stressful. Worry can get really loud.", "I'm sorry your mind is racing. That's exhausting.", "It makes sense that you feel on edge, and you don't have to hold it alone."),
        ("A few slow breaths can help: in for about 4, out for about 6.", "Try pressing your feet into the floor and naming five things you can see. It brings you back to the room."),
        ("What's the main thing on your mind right now?", "Do you want to tell me what's got you worried?")),
    "panic_attack": (
        ("I'm here. This feeling is awful, and it does pass.", "You're not alone in this. Let's slow it down together."),
        ("Breathe in through your nose for about 4, then out slowly for about 6 to 8. Press your feet into the floor and look around the room for five things you can see.", "Try a slow breath in for 4 and a longer breath out for 6, a few times. Let your shoulders drop as you breathe out."),
        ("Is it easing a little, or shall we keep breathing together?", "Are you somewhere safe right now?")),
    "separation_anxiety": (
        ("Missing someone you love is hard. That ache means you care.", "Being apart from someone important can really weigh on you, and that's okay."),
        ("A small ritual can help: a voice note, a set time to talk, or something that reminds you of them.", "Sharing a small moment from your day with them, even a photo, can make the distance feel smaller."),
        ("Who are you missing?", "Do you want to tell me about them?")),
    "low_mood": (
        ("I'm sorry it's a low day. You don't have to push through it alone.", "That sounds heavy. Low days happen, and being kind to yourself matters.", "Thank you for telling me. I'm here."),
        ("One small kind thing can help: a glass of water, a few minutes of daylight, a short walk.", "Go easy today. One small thing for yourself is enough: something warm to drink, a shower, a little fresh air."),
        ("Do you want to tell me what's been weighing on you?", "What would feel like even a tiny bit of relief right now?")),
    "stress": (
        ("That sounds like a lot. No wonder you're stretched.", "I'm sorry things feel so heavy right now. Feeling overwhelmed is really draining.", "It makes sense that you're stressed with all that on your plate."),
        ("Try picking just the next smallest thing, and let the rest wait for a moment.", "A short break can help: stand up, stretch, a few slow breaths, a sip of water."),
        ("What feels like the heaviest part?", "Do you want to untangle it together and pick the one thing that matters most today?")),
    "tired": (
        ("Ugh, that sounds draining. Being tired all day is really hard.", "I'm sorry you're so worn out. Rest is allowed.", "That sounds like an exhausting day."),
        ("Water, a little daylight and a short walk can help a bit, and an earlier night if you can.", "If you can, try a slow, easy evening and an earlier night. Even a short rest helps."),
        ("How did you sleep last night?", "Did anything make today especially tiring?")),
    "joy": (
        ("That's wonderful. Congratulations!", "Yay! I love hearing that.", "That made my day. I'm so happy for you!"),
        ("You deserve to enjoy this one.", "Take a moment to let it sink in."),
        ("What made it so good?", "I'd love to hear how it went. Will you tell me more?")),
}
# the same, in Roman Hindi (Hinglish)
HI: dict[str, tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]] = {
    "loneliness": (("Ye sunke accha nahi laga, akelapan bhaari lagta hai. Batane ke liye thank you.", "Main yahin hoon. Akela mehsoos karna kamzori nahi hai."),
                   ("Kisi ek insaan ko chhota sa 'hi' bhej do, bas itna kaafi hai.",), ("Koi hai jise tum message karna chahoge?", "Aaj kya cheez akela mehsoos kara rahi hai?")),
    "anxiety": (("Ye tension wala feel bahut thakane wala hota hai.", "Samajh sakta hoon, dimaag daud raha hoga."),
                ("Do-teen dheere saans lo: andar 4 tak, bahar 6 tak.",), ("Abhi sabse zyada kya cheez dimaag mein chal rahi hai?",)),
    "panic_attack": (("Main yahin hoon. Ye feeling bahut buri hoti hai par guzar jaati hai.",),
                     ("Naak se andar 4 tak, phir dheere bahar 6-8 tak saans lo. Pair zameen pe tikao.",), ("Thoda kam ho raha hai, ya saath mein saans lete rahein?",)),
    "separation_anxiety": (("Kisi apne ko miss karna mushkil hota hai, ye pyaar dikhata hai.",),
                           ("Ek voice note ya baat karne ka fixed time chhota sa sahara ban sakta hai.",), ("Kise miss kar rahe ho?",)),
    "low_mood": (("Aaj ka din bhaari hai, sorry. Akele sab sambhalna zaroori nahi.", "Batane ke liye thank you. Main yahin hoon."),
                 ("Ek chhoti si acchi cheez: paani, thodi dhoop, ya chhota sa walk.",), ("Kya cheez tumhe pareshan kar rahi hai?",)),
    "stress": (("Bahut kuch ek saath hai, thak jaana natural hai.", "Itna pressure ho to overwhelmed lagna samajh aata hai."),
               ("Bas agla sabse chhota kaam uthao, baaki thodi der ke liye rehne do.",), ("Sabse bhaari cheez kaunsi lag rahi hai?",)),
    "tired": (("Aaj ka din thakane wala raha lagta hai.", "Thakaan sach mein bhaari hoti hai."),
              ("Paani, thodi dhoop aur aaj jaldi so jaana madad karega.",), ("Kal raat neend kaisi rahi?",)),
    "joy": (("Wah, bahut badhiya! Congratulations!", "Ye sunke maza aa gaya!"),
            ("Is pal ko enjoy karo.",), ("Kya hua, thoda aur batao?",)),
}

PANIC_NOTE = "If it feels like more than panic (chest pain, trouble breathing, or you feel unsafe), please get medical help or call your local emergency number."
LOW_MOOD_NOTE = "If this low feeling has been sticking around, talking to someone you trust or a professional can really help."
MIND_TOOL = {"loneliness": "Mind > Loneliness check-in", "anxiety": "Mind > Anxiety check-in", "panic_attack": "Mind > Breathe and ground",
             "separation_anxiety": "Mind > Missing someone", "low_mood": "Mind > Check in", "stress": "Mind > Breathe and ground"}


def _pick(seed: str, salt: str, options: tuple[str, ...]) -> str:
    return options[int(hashlib.sha256(f"{seed}|{salt}".encode("utf-8")).hexdigest(), 16) % len(options)]


def concept_of(text: str, active_concepts: Iterable[str] = ()) -> str | None:
    """The feeling this message is about, or None. Only a message that is about the feeling (not asking for information, not a symptom report) qualifies."""
    t = str(text or "")
    if not t.strip() or len(t) > 280 or re.search(r"\d", t) or _NOT_FOR_THIS.search(t) or _QUESTION_FOR_INFO.search(t):
        return None   # a number means a log is in the message (it has its own route); a question for information is for a card or the model
    if _THIRD_PERSON.search(t) and not _FIRST_PERSON.search(t):
        return None   # about someone else
    concepts = set(active_concepts)
    mind = next((c for c in MIND_CONCEPTS if c in concepts), None)
    others = concepts - set(MIND_CONCEPTS) - {"fatigue"}
    if others:
        return None
    if mind:
        return mind
    if "fatigue" in concepts or _TIRED.search(t):
        return "tired" if not _STRESS.search(t) else "stress"
    if _STRESS.search(t):
        return "stress"
    if _JOY.search(t):
        return "joy"
    if _NERVOUS.search(t):
        return "anxiety"
    if _MISSING.search(t):
        return "separation_anxiety"
    if _LOWISH.search(t):
        return "low_mood"
    return None


def reply(concept: str, *, name: str | None = None, language: str = "en", tone: str = "gentle_warm", length: str = "balanced", seed: str = "") -> str:
    """The friend's reply. ``tone`` and ``length`` come from the person's own Person Model (defaults when unknown)."""
    hinglish = language == "hi-latn"
    bank = (HI if hinglish else EN)[concept]
    validate = _pick(seed, "v", bank[0])
    step = _pick(seed, "s", bank[1])
    question = _pick(seed, "q", bank[2])
    if name and not hinglish and concept != "joy":
        validate = f"{name}, {validate[0].lower()}{validate[1:]}" if validate[0].isupper() and not validate.startswith("I") else f"{name}, {validate}"
    elif name and concept == "joy":
        validate = f"{validate[:-1]}, {name}!" if validate.endswith("!") else f"{validate} {name}!"
    if tone == "calm_direct" and concept != "joy":
        validate = validate.split(". ")[0].rstrip(".") + "."
    if tone == "cheerful_playful" and concept in ("stress", "tired"):
        validate = validate.replace("Ugh, ", "").replace("Ugh ", "")
    parts = [validate]
    if length != "short" or concept == "panic_attack":
        parts.append(step)
    if concept == "panic_attack" and not hinglish:
        parts.append(PANIC_NOTE)
    if concept == "low_mood" and not hinglish and length != "short":
        parts.append(LOW_MOOD_NOTE)
    parts.append(question)
    text = " ".join(parts[:-1]) + ("\n\n" if len(parts) > 1 else "") + parts[-1]
    tool = MIND_TOOL.get(concept)
    if tool and length == "detailed" and not hinglish:
        text += f"\n\nIf it helps, there's {tool} in the app."
    return text
