"""Orbit: relationship support for one person, and a few small rituals for two (plan 7.3 and 7.7).

``app.include_router(orbit.build_router(get_user, db))``. Solo by default; pairing reuses the partner connection in ``partner_sharing`` and adds nothing of its
own. Everything is a signed ``doc_store`` document owned by one person (no schema change, deleted with their data).

The promise this module keeps (the tests hold it):

* **Nothing one person tells Bubbles is shown to the other.** The only things that cross are the two that the sharer switched on and agreed to in Privacy
  choices: an answer to the shared daily question and the weekly check-in (shown to *both* only once *both* have answered), and one fixed, generic weather
  line (``orbit_weather.py``). A reply-helper paste, a repair note, a love-map note, a chat message never leave the owner.
* **Safety first.** Every free-text input is read by the safety engine and by Safe Harbor *before* anything else; a crisis or a disclosure of harm at home
  gets the fixed answer, is not stored, and never reaches a model. A person with a Safe Harbor flag in the last 90 days is silently left out of weather.
* **No manipulation.** Requests to check, track, test or make someone jealous get a warm decline, and drafts that contain a verdict or a stereotype lose that
  sentence.
"""
from __future__ import annotations

import hashlib
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable

from fastapi import APIRouter, Body, Header, HTTPException
from starlette.concurrency import run_in_threadpool

import ai_json
import chat_cache
import consent
import doc_store
import locale_support
import name_privacy
import orbit_weather
import partner_sharing
import person_model
import response_quality
import safe_harbor
from calc_core import local_today
from chat_pipeline import RateLimiter
from safety_engine import assess_safety, emergency_response

STATUSES = ("single", "dating", "situationship", "committed", "married", "separated", "complicated", "prefer_not")
CARED_FOR = ("words", "time", "help", "touch", "gifts")
CONFLICT = ("pursues", "withdraws", "balanced")
NOTE_KINDS = ("repair", "gratitude", "love_map")
MAX_NOTES = 60
CHECKIN_KEYS = ("appreciate", "wish", "weighing")
CHECKIN_PROMPTS = {"appreciate": "One thing I appreciated this week", "wish": "One wish for the week ahead", "weighing": "One thing that is weighing on me"}

#: one small question a day, the same for both people when paired. Warm, answerable in a line, nothing that interrogates.
QUESTIONS: tuple[tuple[str, str], ...] = (
    ("q01", "What made you smile today?"), ("q02", "What is one small thing that would make tomorrow easier?"), ("q03", "What is a memory of us that you like going back to?"),
    ("q04", "What is something you are looking forward to this week?"), ("q05", "What did you need more of today: rest, company, quiet or fun?"),
    ("q06", "What is something kind someone did for you recently?"), ("q07", "Which meal would feel like a hug right now?"), ("q08", "What is one thing you are proud of lately?"),
    ("q09", "What song fits your mood today?"), ("q10", "What is a small thing I do that you like?"), ("q11", "Where would you go for a quiet hour if you could?"),
    ("q12", "What is something you have been wanting to try?"), ("q13", "What was the best part of your day, and the hardest?"), ("q14", "What is one thing you would like us to do more often?"),
    ("q15", "What helps you feel calm when things are busy?"), ("q16", "Who is someone you are grateful for today, and why?"), ("q17", "What is a tiny habit you would like to start?"),
    ("q18", "What is something you admire about the way the other person handles hard days?"), ("q19", "What would a perfect lazy Sunday look like?"),
    ("q20", "What is something you learned about yourself this month?"), ("q21", "What is a dream you have not said out loud in a while?"), ("q22", "What did you laugh at recently?"),
    ("q23", "What do you wish more people understood about you?"), ("q24", "What is one thing you want to say thank you for?"), ("q25", "What is a place that makes you feel safe?"),
    ("q26", "What is a small way I could show up for you this week?"), ("q27", "What is something you miss from when you were younger?"), ("q28", "What would you like to celebrate, however small?"),
    ("q29", "What is a feeling you have had a lot of lately?"), ("q30", "What is one thing you would tell your younger self about love?"),
)
QUESTION_TEXT = dict(QUESTIONS)

LOVE_MAP_QUESTIONS: tuple[tuple[str, str], ...] = (
    ("m01", "What is stressing them most these days, at work, study or at home?"), ("m02", "What is something they are looking forward to?"),
    ("m03", "What is a dream they have not told many people?"), ("m04", "Who are the two or three people they feel closest to?"),
    ("m05", "What helps them feel calm after a hard day?"), ("m06", "What is a small thing that always makes them smile?"),
    ("m07", "What do they worry about that they rarely mention?"), ("m08", "What is their favourite way to spend a free evening?"),
    ("m09", "What is something they are proud of that few people know?"), ("m10", "What makes them feel most cared for?"),
    ("m11", "What was the best part of their childhood?"), ("m12", "What would they change about their week if they could?"),
)
LOVE_MAP_TEXT = dict(LOVE_MAP_QUESTIONS)

_limiter = RateLimiter(limit=20, window=60.0)

REPLY_SYSTEM = """You help a person write a reply to someone close to them. You only know the person's side, so never judge the other person or the relationship.
Return ONLY valid JSON: {"feelings": ["...", "...", "..."], "replies": [{"tone": "gentle", "text": "...", "why": "..."}, {"tone": "light", "text": "...", "why": "..."}, {"tone": "clear", "text": "...", "why": "..."}]}
- feelings: up to three feelings that MAY be under the message the person received, phrased as possibilities ("they may be feeling overlooked"), never as facts.
- replies: exactly three, in the first person, as the person would send them, in the same language and script as the person's own words (Hinglish stays Roman Hinglish). One to three short sentences each.
  gentle = warm and reassuring; light = easy and a little playful, never sarcastic; clear = calm, direct, says what the person needs.
- why: one short line on why this may land well.
- Never insult, guilt, threaten, bait, test or make the other person jealous. No verdicts, no labels, no stereotypes, no advice to stay or leave, no medical or legal advice.
- Keep any bracketed labels such as [PARTNER] exactly as written. Never add names."""

REPAIR_SYSTEM = """You help a person write a short message to repair things after a fight with someone close to them. Return ONLY valid JSON: {"draft": "..."}.
- Write in the first person, in the same language and script as the person's words (Hinglish stays Roman Hinglish), two to four sentences.
- Own the person's part without grovelling, say what they felt and what they need, and invite the other person back to talk. No blame, no verdicts, no labels, no stereotypes, no demands, no guilt.
- Keep any bracketed labels such as [PARTNER] exactly as written. Never add names."""

COOLDOWN_SYSTEM = """You help a person say something hard more gently. Return ONLY valid JSON: {"rewrite": "..."}.
- Rewrite the draft as a soft start: "I feel ... about ... and I need ...", in the first person, in the same language and script as the draft, one to three sentences.
- Keep the person's point. Remove insults, labels, threats, sarcasm and absolutes ("always", "never"). Do not add apologies they did not mean.
- Keep any bracketed labels such as [PARTNER] exactly as written. Never add names."""

_ANGER_WORDS = re.compile(
    r"\b(?:hate|furious|sick of|fed up|shut up|stupid|idiot|useless|pathetic|screw you|damn you|leave me alone|never talk|can'?t stand|disgusting|worthless|"
    r"nafrat|bakwas|bewakoof|pagal|chup kar|chup raho|dafa ho|tang aa gaya|tang aa gayi|bekaar|nikamma|nikammi|jaa yahan se)\b", re.I)
_REWRITES = {
    "en": "I'm really upset right now and I don't want to say something I'll regret. I need a little time, and then I'd like to talk about this properly. Can we come back to it in a bit?",
    "hinglish": "Main abhi bahut upset hoon aur kuch aisa nahi bolna chahta jo baad mein pachtaaun. Mujhe thoda time chahiye, phir hum is baare mein theek se baat karenge. Kya hum thodi der baad baat kar sakte hain?",
}
_TEMPLATE_REPLIES = {
    "en": (("gentle", "I can tell this matters to you, and it matters to me too. I'd like to understand how you're feeling. Can we talk when you're ready?", "It shows care and leaves the door open."),
           ("light", "Hey, I'm thinking of you. Want to talk about it a little later today?", "Easy and kind, no pressure."),
           ("clear", "I want to talk about this, but I need a bit of time first. Can we come back to it this evening?", "It says what you need without blaming.")),
    "hinglish": (("gentle", "Mujhe pata hai ye tumhare liye important hai, aur mere liye bhi hai. Main samajhna chahta hoon tum kya feel kar rahe ho. Jab tum ready ho tab baat karein?", "Isme fikar dikhti hai aur baat ka darwaza khula rehta hai."),
                 ("light", "Hey, main tumhare baare mein soch raha hoon. Thodi der baad is baare mein baat karein?", "Halka aur pyaara, koi pressure nahi."),
                 ("clear", "Main is baare mein baat karna chahta hoon, par pehle mujhe thoda time chahiye. Kya hum shaam ko wapas baat kar sakte hain?", "Bina blame kiye batata hai ki tumhe kya chahiye.")),
}
_REPAIR_TEMPLATE = {
    "en": "I've been thinking about what happened. {own} I felt {felt}, and what I needed was {needed}. I care about us and I'd like to talk when you're ready.",
    "hinglish": "Main soch raha hoon ki kya hua. {own} Mujhe {felt} laga, aur mujhe {needed} chahiye tha. Mujhe hum dono ki parwah hai, aur jab tum ready ho tab baat karna chahta hoon.",
}


# ---- helpers ---------------------------------------------------------------------------------------------------------------------------

def _bad(msg: str, code: int = 422) -> HTTPException:
    return HTTPException(status_code=code, detail=msg)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_week(day: date) -> str:
    y, w, _ = day.isocalendar()
    return f"{y}-W{w:02d}"


def _text(raw: Any, label: str, limit: int, *, required: bool = False) -> str:
    if raw is None or raw == "":
        if required:
            raise _bad(f"{label} is needed.")
        return ""
    if not isinstance(raw, str):
        raise _bad(f"{label} must be text.")
    clean = re.sub(r"\s+", " ", re.sub(r"[\x00-\x08\x0b-\x1f\x7f<>]", "", raw)).strip()
    if len(clean) > limit:
        raise _bad(f"{label} can be up to {limit} characters.")
    if required and not clean:
        raise _bad(f"{label} is needed.")
    return clean


def _lang(text: str) -> str:
    hinglish = safe_harbor.detect_language(text) in ("hi", "hi-latn") or len(re.findall(r"\b(?:main|mujhe|tum|hai|nahi|kya|aap|woh|uska|uski|hum|kar|karo|chahta|chahti)\b", text or "", re.I)) >= 2
    return "hinglish" if hinglish else "en"


def _pair_key(a: str, b: str) -> str:
    return hashlib.sha256("|".join(sorted((str(a), str(b)))).encode("utf-8")).hexdigest()[:24]


def screen(db: Any, uid: str, *texts: str) -> dict | None:
    """Read free text for safety before anything else. A crisis or harm at home returns the fixed answer (and the caller stores and sends nothing); otherwise None."""
    joined = " ".join(t for t in texts if t).strip()
    if not joined:
        return None
    ident = chat_cache.identity(db, uid)
    country, gender = ident.get("country"), ident.get("gender")
    assessment = assess_safety(joined)
    if assessment.state == "EMERGENCY" or assessment.crisis:
        return {"status": "safety", "kind": "emergency", "message": emergency_response(assessment, country)}
    harbor = safe_harbor.assess(joined, [], safe_harbor.HarborContext(country=country, gender=gender, now=_now()))
    if harbor.deterministic:
        return {"status": "safety", "kind": "safe_harbor", "message": safe_harbor.reply(harbor, seed=joined), "harbor": safe_harbor.payload(harbor)}
    if harbor.tier >= 1:
        return {"status": "safety", "kind": "safe_harbor", "message": safe_harbor.lite_fixed_reply(harbor) or "That sounds hard. I'm here, and there are people who can help if you want to talk to someone.",
                "harbor": safe_harbor.payload(harbor)}
    return None


def _need_ai_consent(db: Any, uid: str) -> None:
    if not consent.has_ai_consent(db, uid):
        ask = consent.chat_prompt(db, uid, None)
        raise HTTPException(status_code=403, detail={"code": "consent_required", "purpose": "ai_chat_processing", "ask": bool(ask["ask"]), "message": ask["reply"]})


def _throttle(uid: str) -> None:
    if not _limiter.allow(uid):
        raise _bad("You're going quickly. Please wait a moment and try again.", 429)


def _clean_model_text(text: str, user_message: str = "") -> str:
    """A model draft with verdict, stereotype and astrology sentences removed; '' if nothing usable is left or it tries to manipulate."""
    cleaned, removed = response_quality.enforce_orbit(text, user_message)
    if removed and cleaned == response_quality.NEUTRAL_LINE:
        return ""
    if response_quality.manipulation_request(cleaned) or re.search(r"\b(?:jealous|guilt[- ]?trip|make you pay|you'?ll regret)\b", cleaned, re.I):
        return ""
    return cleaned.strip()


def _string_field(key: str, limit: int) -> Callable[[Any], str]:
    def check(data: Any) -> str:
        if not isinstance(data, dict) or not isinstance(data.get(key), str) or not data[key].strip():
            raise ValueError(f"no {key}")
        return data[key].strip()[:limit]
    return check


def _valid_replies(data: Any) -> dict:
    if not isinstance(data, dict):
        raise ValueError("not an object")
    feelings = [str(f).strip()[:120] for f in (data.get("feelings") or []) if isinstance(f, str) and f.strip()][:3]
    replies = []
    for r in data.get("replies") or []:
        if isinstance(r, dict) and r.get("tone") in ("gentle", "light", "clear") and isinstance(r.get("text"), str) and r["text"].strip():
            replies.append({"tone": r["tone"], "text": r["text"].strip()[:500], "why": str(r.get("why") or "").strip()[:160]})
    if len(replies) < 2:
        raise ValueError("too few replies")
    return {"feelings": feelings, "replies": replies}


def _people(db: Any, uid: str) -> dict[str, str]:
    return name_privacy.people_map(db, uid)


# ---- profile ----------------------------------------------------------------------------------------------------------------------------

def get_profile(db: Any, uid: str) -> dict:
    p = doc_store.get(db, uid, "orbit_profile", "v1") or {}
    return {"status": p.get("status") if p.get("status") in STATUSES else None, "partner_word": str(p.get("partner_word") or ""),
            "cared_for_by": [c for c in p.get("cared_for_by") or [] if c in CARED_FOR], "conflict_style": p.get("conflict_style") if p.get("conflict_style") in CONFLICT else None}


def save_profile(db: Any, uid: str, body: dict) -> dict:
    status = body.get("status")
    if status is not None and status not in STATUSES:
        raise _bad("Choose one of the relationship options shown.")
    cared = body.get("cared_for_by", [])
    if not isinstance(cared, list) or any(c not in CARED_FOR for c in cared) or len(cared) > len(CARED_FOR):
        raise _bad("Choose from the ways of feeling cared for that are shown.")
    conflict = body.get("conflict_style")
    if conflict is not None and conflict not in CONFLICT:
        raise _bad("Choose one of the options shown for how you handle a disagreement.")
    word = _text(body.get("partner_word"), "The word you use for them", 20)
    blocked = screen(db, uid, word) if word else None
    if blocked:
        return blocked
    doc = {"status": status, "partner_word": word, "cared_for_by": list(dict.fromkeys(cared)), "conflict_style": conflict, "updated_at": _now().isoformat()}
    doc_store.put(db, uid, "orbit_profile", "v1", doc)
    items = [("cared_for_by", c, "orbit", "orbit_checkin", 3.0) for c in doc["cared_for_by"]] + ([("conflict_style", conflict, "orbit", "orbit_checkin", 3.0)] if conflict else [])
    if items:
        person_model.observe_evidence(db, uid, items)   # what they tell Orbit about themselves joins "How Bubbles understands you" (visible and deletable there)
    return {"status": "success", "profile": get_profile(db, uid)}


# ---- the home screen ----------------------------------------------------------------------------------------------------------------

def _weather_paused(db: Any, uid: str, now: datetime) -> bool:
    flag = doc_store.get(db, uid, "harbor_flag", "v1") or {}
    when = flag.get("last_at")
    try:
        last = datetime.fromisoformat(str(when).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return False
    last = last if last.tzinfo else last.replace(tzinfo=timezone.utc)
    return bool(flag.get("pause_partner_signals")) and now - last <= timedelta(days=safe_harbor.FLAG_DAYS)


def _question_for(uid: str, partner: dict | None, day: date) -> tuple[str, str]:
    key = _pair_key(uid, partner["uid"]) if partner else hashlib.sha256(str(uid).encode("utf-8")).hexdigest()[:24]
    index = int(hashlib.sha256(f"{key}|{day.isoformat()}".encode("utf-8")).hexdigest(), 16) % len(QUESTIONS)
    return QUESTIONS[index]


def _reveal_allowed(db: Any, uid: str, partner: dict | None) -> bool:
    """Both people have switched shared rituals on, and are still connected."""
    return bool(partner) and partner_sharing.shares(db, uid, "orbit_rituals") and partner_sharing.shares(db, partner["uid"], "orbit_rituals")


def question_state(db: Any, uid: str, day: date | None = None) -> dict:
    day = day or local_today()
    partner = partner_sharing.paired_with(db, uid)
    qid, qtext = _question_for(uid, partner, day)
    mine = doc_store.get(db, uid, "orbit_question", day.isoformat()) or {}
    answered = bool(mine.get("my_answer"))
    out = {"id": qid, "text": qtext, "date": day.isoformat(), "paired": bool(partner), "my_answer": mine.get("my_answer") or None, "answered": answered,
           "partner_answer": None, "state": "solo" if not partner else "waiting"}
    if partner and answered and _reveal_allowed(db, uid, partner):
        theirs = doc_store.get(db, partner["uid"], "orbit_question", day.isoformat()) or {}
        if theirs.get("my_answer") and theirs.get("question_id") == qid:
            out["partner_answer"], out["state"] = theirs["my_answer"], "revealed"
    elif partner and not answered:
        out["state"] = "waiting"          # the same word whether or not the other person has answered
    return out


def answer_question(db: Any, uid: str, body: dict) -> dict:
    answer = _text(body.get("answer"), "Your answer", 500, required=True)
    blocked = screen(db, uid, answer)
    if blocked:
        return blocked
    day = local_today()
    partner = partner_sharing.paired_with(db, uid)
    qid, _ = _question_for(uid, partner, day)
    doc_store.put(db, uid, "orbit_question", day.isoformat(), {"question_id": qid, "my_answer": answer, "answered_at": _now().isoformat()})
    return {"status": "success", **question_state(db, uid, day)}


def checkin_state(db: Any, uid: str, day: date | None = None) -> dict:
    day = day or local_today()
    week = _iso_week(day)
    partner = partner_sharing.paired_with(db, uid)
    mine = doc_store.get(db, uid, "orbit_checkin", week) or {}
    answered = bool(mine.get("answers"))
    out = {"week": week, "prompts": CHECKIN_PROMPTS, "paired": bool(partner), "answered": answered, "my_answers": mine.get("answers") or {}, "partner_answers": None,
           "state": "solo" if not partner else "waiting"}
    if partner and answered and _reveal_allowed(db, uid, partner):
        theirs = doc_store.get(db, partner["uid"], "orbit_checkin", week) or {}
        if theirs.get("answers"):
            out["partner_answers"], out["state"] = theirs["answers"], "revealed"
    return out


def answer_checkin(db: Any, uid: str, body: dict) -> dict:
    raw = body.get("answers")
    if not isinstance(raw, dict) or not raw or set(raw) - set(CHECKIN_KEYS):
        raise _bad("Answer at least one of the three questions.")
    answers = {k: _text(raw[k], CHECKIN_PROMPTS[k], 300) for k in CHECKIN_KEYS if k in raw}
    answers = {k: v for k, v in answers.items() if v}                  # any question may be skipped
    if not answers:
        raise _bad("Answer at least one of the three questions.")
    blocked = screen(db, uid, *answers.values())
    if blocked:
        return blocked
    day = local_today()
    doc_store.put(db, uid, "orbit_checkin", _iso_week(day), {"answers": answers, "answered_at": _now().isoformat()})
    return {"status": "success", **checkin_state(db, uid, day)}


# ---- weather ------------------------------------------------------------------------------------------------------------------------

def _signals(db: Any, uid: str) -> tuple[bool | None, datetime | None]:
    """(heavy week?, newest log time) for the sharer. The numbers stay in this function; only a yes/no and a time leave it."""
    import health_logs
    mood, stress, sleep, newest = [], [], [], None
    for slug in ("mood", "sleep"):
        try:
            entries = health_logs.list_domain(db, slug, health_logs.DOMAINS[slug], uid, 7).get("entries", [])
        except Exception:  # noqa: BLE001
            entries = []
        for e in entries:
            raw = e.get("date")
            try:
                when = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
                when = when if when.tzinfo else when.replace(tzinfo=timezone.utc)
                newest = when if newest is None or when > newest else newest
            except (TypeError, ValueError):
                pass
            if slug == "mood":
                if isinstance(e.get("mood"), (int, float)) and not isinstance(e.get("mood"), bool):
                    mood.append(float(e["mood"]))
                m = re.search(r"Stress\s+(\d+(?:\.\d+)?)/10", str(e.get("notes") or ""))
                if m:
                    stress.append(float(m.group(1)))
            elif isinstance(e.get("duration"), (int, float)) and not isinstance(e.get("duration"), bool) and 0 < e["duration"] <= 16:
                sleep.append(float(e["duration"]))
    return orbit_weather.heavy_week(mood, stress, sleep), newest


def weather_for(db: Any, reader: str, now: datetime | None = None) -> dict:
    """The line the reader's partner may show them: at most one in three days, from what the partner allowed, otherwise nothing. The answer has the same
    shape whatever the reason for "nothing", so a missing line says nothing about the partner."""
    now = now or _now()
    none = {"status": "success", "line": None}
    partner = partner_sharing.paired_with(db, reader)
    if not partner or not partner_sharing.shares(db, partner["uid"], "orbit_weather") or _weather_paused(db, partner["uid"], now):
        return none
    window = orbit_weather.window_index(now)
    state = doc_store.get(db, partner["uid"], "orbit_weather", "main") or {}
    if state.get("window") != window:
        heavy, newest = _signals(db, partner["uid"])
        if not orbit_weather.ready(newest, now):
            return none                       # try again later; nothing is saved, so the line is first chosen at a quiet moment
        state = {"window": window, "line": orbit_weather.pick(bool(heavy), _pair_key(reader, partner["uid"]), window), "chosen_at": now.isoformat()}
        doc_store.put(db, partner["uid"], "orbit_weather", "main", state)
    line = orbit_weather.LINE_TEXT.get(state.get("line") or "")
    return {"status": "success", "line": line}


# ---- home ---------------------------------------------------------------------------------------------------------------------------

def home(db: Any, uid: str) -> dict:
    now = _now()
    partner = partner_sharing.paired_with(db, uid)
    profile = get_profile(db, uid)
    q = question_state(db, uid)
    c = checkin_state(db, uid)
    return {
        "status": "success", "profile": profile, "paired": bool(partner), "partner_name": partner["name"] if partner else None,
        "question": {k: q[k] for k in ("id", "text", "answered", "state")}, "checkin": {k: c[k] for k in ("week", "answered", "state")},
        "weather": weather_for(db, uid, now)["line"], "weather_paused": _weather_paused(db, uid, now),
        "sharing": {"rituals": partner_sharing.shares(db, uid, "orbit_rituals"), "weather": partner_sharing.shares(db, uid, "orbit_weather")},
        "harbor_title": "Feeling unsafe at home?",
    }


# ---- tools --------------------------------------------------------------------------------------------------------------------------

def reply_helper(db: Any, uid: str, body: dict) -> dict:
    theirs = _text(body.get("their_message"), "What they said", 1500, required=True)
    context = _text(body.get("context"), "Context", 600)
    blocked = screen(db, uid, theirs, context)
    if blocked:
        return blocked
    if response_quality.manipulation_request(theirs + " " + context):
        return {"status": "declined", "message": "I'd rather help you say what you need directly. Tell me what you are hoping to say or feel, and I can help you put it into an honest message."}
    _need_ai_consent(db, uid)
    language = _lang(theirs + " " + context)
    people = _people(db, uid)
    prompt = name_privacy.mask(f"WHAT THEY SENT OR SAID:\n{theirs}" + (f"\n\nCONTEXT FROM THE PERSON:\n{context}" if context else ""), people)
    data = ai_json.ask_json(REPLY_SYSTEM, prompt, _valid_replies)
    replies, feelings, source = [], [], "template"
    if data:
        feelings = [name_privacy.unmask(f, people) for f in data["feelings"]]
        for r in data["replies"]:
            text = _clean_model_text(name_privacy.unmask(r["text"], people), theirs)
            if text:
                replies.append({"tone": r["tone"], "text": text, "why": name_privacy.unmask(r["why"], people)})
        source = "ai" if len(replies) >= 2 else "template"
    if source == "template":
        replies = [{"tone": t, "text": x, "why": w} for t, x, w in _TEMPLATE_REPLIES[language]]
        feelings = []
    return {"status": "success", "feelings": feelings, "replies": replies, "source": source}


def heated(draft: str) -> bool:
    letters = [c for c in draft if c.isalpha()]
    caps = len(letters) >= 8 and sum(1 for c in letters if c.isupper()) / len(letters) > 0.6
    return bool(caps or draft.count("!") >= 3 or "?!" in draft or _ANGER_WORDS.search(draft))


def cooldown(db: Any, uid: str, body: dict) -> dict:
    draft = _text(body.get("draft"), "Your draft", 1500, required=True)
    blocked = screen(db, uid, draft)
    if blocked:
        return blocked
    if not heated(draft):
        return {"status": "success", "heated": False, "rewrite": None, "pause_minutes": 0}
    rewrite, source = _REWRITES[_lang(draft)], "template"
    if consent.has_ai_consent(db, uid):
        people = _people(db, uid)
        data = ai_json.ask_json(COOLDOWN_SYSTEM, name_privacy.mask(draft, people), _string_field("rewrite", 600))
        cleaned = _clean_model_text(name_privacy.unmask(data, people), draft) if data else ""
        if cleaned:
            rewrite, source = cleaned, "ai"
    return {"status": "success", "heated": True, "rewrite": rewrite, "pause_minutes": 20, "source": source}


def love_map(db: Any, uid: str) -> dict:
    people = _people(db, uid)
    known = [{"id": "name", "text": f"Their name: {name}"} for name, label in people.items() if label == "[PARTNER]"][:1]
    notes = [n for n in _notes(db, uid) if n.get("kind") == "love_map"]
    answered = {n.get("question_id") for n in notes}
    known += [{"id": n["id"], "text": n["text"]} for n in notes]
    ask = [{"id": i, "text": t} for i, t in LOVE_MAP_QUESTIONS if i not in answered][:3]
    return {"status": "success", "known": known, "ask": ask}


def repair(db: Any, uid: str, body: dict) -> dict:
    parts = {k: _text(body.get(k), k.capitalize(), 400, required=True) for k in ("happened", "felt", "needed", "own")}
    blocked = screen(db, uid, *parts.values())
    if blocked:
        return blocked
    language = _lang(" ".join(parts.values()))
    template = _REPAIR_TEMPLATE[language].format(own=parts["own"].rstrip(".") + ".", felt=parts["felt"].rstrip("."), needed=parts["needed"].rstrip("."))
    draft, source = template, "template"
    if consent.has_ai_consent(db, uid):
        people = _people(db, uid)
        prompt = name_privacy.mask("WHAT HAPPENED: {happened}\nWHAT I FELT: {felt}\nWHAT I NEEDED: {needed}\nWHAT I CAN OWN: {own}".format(**parts), people)
        data = ai_json.ask_json(REPAIR_SYSTEM, prompt, _string_field("draft", 700))
        cleaned = _clean_model_text(name_privacy.unmask(data, people)) if data else ""
        if cleaned:
            draft, source = cleaned, "ai"
    return {"status": "success", "draft": draft, "source": source}


# ---- notes (private; a gratitude note may be shared) -------------------------------------------------------------------------------------

def _notes(db: Any, uid: str) -> list[dict]:
    return [{**d["payload"], "id": d["key"]} for d in doc_store.list_docs(db, uid, "orbit_note", MAX_NOTES)]


def add_note(db: Any, uid: str, body: dict) -> dict:
    kind = body.get("kind")
    if kind not in NOTE_KINDS:
        raise _bad("Choose what kind of note this is.")
    text = _text(body.get("text"), "Your note", 600, required=True)
    share = bool(body.get("share")) and kind == "gratitude"
    question_id = body.get("question_id") if body.get("question_id") in LOVE_MAP_TEXT else None
    blocked = screen(db, uid, text)
    if blocked:
        return blocked
    if len(_notes(db, uid)) >= MAX_NOTES:
        raise _bad("You have a lot of notes saved. Delete one to add another.")
    note_id = uuid.uuid4().hex[:16]
    doc_store.put(db, uid, "orbit_note", note_id, {"kind": kind, "text": text, "share": share, "question_id": question_id, "created_at": _now().isoformat()})
    return {"status": "success", "notes": _notes(db, uid)}


def delete_note(db: Any, uid: str, note_id: str) -> dict:
    if not re.fullmatch(r"[a-f0-9]{16}", note_id):
        raise _bad("That note does not exist.", 404)
    doc_store.delete(db, uid, "orbit_note", note_id)
    return {"status": "success", "notes": _notes(db, uid)}


def received_notes(db: Any, uid: str) -> dict:
    """Gratitude notes the connected person chose to share, newest first. Only while both are connected and the sender has shared rituals switched on."""
    partner = partner_sharing.paired_with(db, uid)
    if not partner or not partner_sharing.shares(db, partner["uid"], "orbit_rituals"):
        return {"status": "success", "notes": []}
    shared = [n for n in _notes(db, partner["uid"]) if n.get("kind") == "gratitude" and n.get("share")]
    return {"status": "success", "notes": [{"id": n["id"], "text": n["text"], "created_at": n.get("created_at")} for n in shared[:5]]}


def harbor_resources(db: Any, uid: str) -> dict:
    ident = chat_cache.identity(db, uid)
    return {"status": "success", "title": "Feeling unsafe at home?", "resources": locale_support.resources_for(ident.get("country"), ident.get("gender")),
            "note": "These lines are free and private. If you are in danger right now, call your local emergency number."}


# ---- HTTP -------------------------------------------------------------------------------------------------------------------------

def build_router(get_user: Callable[[str | None], Any], db: Any) -> APIRouter:
    router = APIRouter()

    async def who(authorization: str | None, *, limited: bool = False) -> str:
        uid = str((await run_in_threadpool(get_user, authorization)).id)       # authenticate first, before reading anything
        if limited:
            _throttle(uid)
        return uid

    def body_of(payload: Any) -> dict:
        if not isinstance(payload, dict):
            raise _bad("Send a JSON object.")
        return payload

    @router.get("/orbit")
    async def orbit_home(authorization: str | None = Header(default=None)):
        return await run_in_threadpool(home, db, await who(authorization))

    @router.put("/orbit/profile")
    async def orbit_profile(payload: Any = Body(...), authorization: str | None = Header(default=None)):
        return await run_in_threadpool(save_profile, db, await who(authorization, limited=True), body_of(payload))

    @router.post("/orbit/reply-helper")
    async def orbit_reply_helper(payload: Any = Body(...), authorization: str | None = Header(default=None)):
        return await run_in_threadpool(reply_helper, db, await who(authorization, limited=True), body_of(payload))

    @router.post("/orbit/cooldown")
    async def orbit_cooldown(payload: Any = Body(...), authorization: str | None = Header(default=None)):
        return await run_in_threadpool(cooldown, db, await who(authorization, limited=True), body_of(payload))

    @router.get("/orbit/love-map")
    async def orbit_love_map(authorization: str | None = Header(default=None)):
        return await run_in_threadpool(love_map, db, await who(authorization))

    @router.post("/orbit/repair")
    async def orbit_repair(payload: Any = Body(...), authorization: str | None = Header(default=None)):
        return await run_in_threadpool(repair, db, await who(authorization, limited=True), body_of(payload))

    @router.get("/orbit/question")
    async def orbit_question_get(authorization: str | None = Header(default=None)):
        return {"status": "success", **await run_in_threadpool(question_state, db, await who(authorization))}

    @router.post("/orbit/question")
    async def orbit_question_post(payload: Any = Body(...), authorization: str | None = Header(default=None)):
        return await run_in_threadpool(answer_question, db, await who(authorization, limited=True), body_of(payload))

    @router.get("/orbit/checkin")
    async def orbit_checkin_get(authorization: str | None = Header(default=None)):
        return {"status": "success", **await run_in_threadpool(checkin_state, db, await who(authorization))}

    @router.post("/orbit/checkin")
    async def orbit_checkin_post(payload: Any = Body(...), authorization: str | None = Header(default=None)):
        return await run_in_threadpool(answer_checkin, db, await who(authorization, limited=True), body_of(payload))

    @router.get("/orbit/weather")
    async def orbit_weather_get(authorization: str | None = Header(default=None)):
        return await run_in_threadpool(weather_for, db, await who(authorization))

    @router.get("/orbit/weather/preview")
    async def orbit_weather_preview(authorization: str | None = Header(default=None)):
        uid = await who(authorization)
        return {"status": "success", "on": await run_in_threadpool(partner_sharing.shares, db, uid, "orbit_weather"), "possible_lines": orbit_weather.describe_possible(),
                "how": "At most one line every three days. A heavier week makes a gentle line more likely, but gentle lines also appear in calm weeks, so a line never tells them how you are."}

    @router.get("/orbit/notes")
    async def orbit_notes_get(authorization: str | None = Header(default=None)):
        return {"status": "success", "notes": await run_in_threadpool(_notes, db, await who(authorization))}

    @router.post("/orbit/notes")
    async def orbit_notes_post(payload: Any = Body(...), authorization: str | None = Header(default=None)):
        return await run_in_threadpool(add_note, db, await who(authorization, limited=True), body_of(payload))

    @router.delete("/orbit/notes/{note_id}")
    async def orbit_notes_delete(note_id: str, authorization: str | None = Header(default=None)):
        return await run_in_threadpool(delete_note, db, await who(authorization), note_id)

    @router.get("/orbit/notes/received")
    async def orbit_notes_received(authorization: str | None = Header(default=None)):
        return await run_in_threadpool(received_notes, db, await who(authorization))

    @router.get("/orbit/harbor")
    async def orbit_harbor(authorization: str | None = Header(default=None)):
        return await run_in_threadpool(harbor_resources, db, await who(authorization))

    return router
