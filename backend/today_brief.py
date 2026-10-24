"""The one sentence at the top of Today. Pure: the caller passes what it found, this picks what leads.

Priority: safety state > an open thread > the strongest new association > a cycle-phase line > an Orbit ritual waiting > a warm line.
One sentence, at most 30 words, never "Welcome back".
"""
from __future__ import annotations

import hashlib

MAX_WORDS = 30

# Fixed bank; chosen by a stable hash of the person and the day, so the line does not change on every refresh.
WARM_LINES = (
    "Nothing is asking for you right now. A glass of water and a slow breath are plenty.",
    "A small log today makes the next pattern easier to see.",
    "However the day went, you are allowed to take it gently.",
    "No pressure to track everything. One honest entry is enough.",
    "If something felt off today, tell me and we will look at it together.",
    "Rest counts as progress too.",
    "You do not have to do anything with this screen. It is here when you want it.",
    "Notice one thing that went okay today. It does not have to be big.",
    "Your body keeps its own rhythm. We are just learning it.",
    "Eat something you enjoy today, and drink some water with it.",
    "A short walk can change the feel of a whole afternoon.",
    "If you are tired, say so. Tired is information, not failure.",
    "Whatever you log, I will not read gaps as bad news.",
    "Small kindnesses to yourself add up the way small logs do.",
    "Your last few days are quiet in the logs. That is fine.",
    "Take the next hour as it comes.",
    "Sleep, water, a little movement: any one of them helps.",
    "You can ask me anything, including the small things.",
    "Be as kind to yourself as you would be to a friend today.",
    "Some days the best plan is no plan.",
    "Check in with how your shoulders feel. Let them drop.",
    "A good day does not need a record. A hard day does not need a reason.",
    "Today is one page, not the whole book.",
    "If a worry keeps coming back, we can write it down and look at it.",
    "Breathe out a little longer than you breathe in. It helps.",
    "You are not behind. There is no schedule here.",
    "Light, water, company: pick whichever is easiest.",
    "I am here when you want to talk, and quiet when you do not.",
    "Your effort this week is more visible than you think.",
    "Look after the basics today and the rest can wait.",
)


def _short(text: str) -> str:
    words = text.split()
    return text.strip() if len(words) <= MAX_WORDS else " ".join(words[:MAX_WORDS]).rstrip(",;:") + "."


def tidy_association(line: str) -> str:
    """"On days after you slept longer, your logged mood tended to be higher (60 days logged). ..." as one friendly sentence for the top of Today:
    the finding, then where it comes from. The statistics and caveats stay on the Patterns page."""
    head = str(line or "").split(" (")[0].split(". ")[0].strip().rstrip(".")
    return f"{head}. That's from your own logs, not a cause." if head else ""


def warm_line(uid: str, day: str) -> str:
    digest = hashlib.sha256(f"{uid}:{day}".encode()).digest()
    return WARM_LINES[digest[0] % len(WARM_LINES)]


def pick(*, uid: str, day: str, safety: str | None = None, open_thread: str | None = None,
         association: str | None = None, cycle_line: str | None = None, orbit_waiting: bool = False) -> dict:
    """``{"kind", "text"}``. ``safety`` is the level word of a non-GREEN state (the banner carries the detail)."""
    if safety and safety.upper() not in ("GREEN", "NONE", ""):
        return {"kind": "safety", "text": "Your last message is the thing to look after first. The notice above has the steps."}
    if open_thread and open_thread.strip():
        return {"kind": "thread", "text": _short(open_thread)}
    if association and association.strip():
        return {"kind": "pattern", "text": _short(tidy_association(association))}
    if cycle_line and cycle_line.strip():
        return {"kind": "cycle", "text": _short(cycle_line)}
    if orbit_waiting:
        return {"kind": "orbit", "text": "Today's question for you two is waiting in Orbit, whenever you like."}
    return {"kind": "warm", "text": warm_line(uid, day)}
