## 15. Mind: loneliness, anxiety, separation anxiety (added 2026-10-16; awaiting sign-off)

Draft from lane L3, for the lead to fold in as the next numbered section. Nothing here diagnoses, labels or advises a medicine. Every item needs clinician sign-off; the Hinglish items also need a native-speaker check (add to HINGLISH_SAFETY_TERMS_REVIEW.md).

### 15.1 Passive-ideation wording (the safety path: crisis reply 112 / Tele-MANAS 14416, nothing stored)
Each pattern needs a first-person feeling or being cue. English (`health_semantics._LEX_SRC`, `suicidal_ideation`, second list):
- "I am / I'm / I feel / I feel like / I have become ... (such a / a / nothing but a) burden" ("I feel like a burden to everyone", "I've become a burden")
- "no one / nobody would (even) miss me"
- "no one / nobody would (even) notice / care / know (if / when) I was / am / died / disappeared / am gone"
- "I am / I feel / feeling (so, really, completely...) worthless"
Must stay quiet (tested): "I don't want to be a burden" (a wish), "he called me worthless", "I'm not worthless", "I used to feel worthless years ago", "my friend feels worthless", "this phone is worthless", "nobody would miss that show", "burden of proof", "What does it mean to feel worthless?".
Hinglish (`hinglish_terms.py`): "main sabke liye bojh hoon", "mere jaane se kisi ko farak nahi padega", "koi meri kami mehsoos nahi karega", "main kisi kaam ka nahi hoon", "meri koi value nahi hai", "main worthless / useless feel karta hoon", "main bilkul bekaar hoon". Near-misses kept quiet: "mujhe nahi lagta main bojh hoon", "kisi kaam ka nahi hai ye phone", "main bekaar hoon yaar cooking mein".
Open question for the reviewer: "main kisi kaam ka nahi hoon" and "main bilkul bekaar hoon" can be said in frustration; they are treated as crisis wording on purpose (the reply is caring and nothing is lost). Say if they should be softened to a clarification.

### 15.2 Ordinary concepts (never escalate alone; a self report that is current, recent or recurring)
- `loneliness`: lonely / lonesome, "I feel (so) alone", "nobody to talk to / nobody talks to me", "I have no friends", "feel isolated / left out / cut off / unwanted"; Hinglish: akela / akeli / akelapan / tanha / tanhai with lagta / lagti / feel, "koi dost nahi", "koi baat karne wala nahi".
- `panic_attack` (child of `anxiety`): panic / panic attack / panicky, "can't calm down".
- `separation_anxiety` (child of `anxiety`): "separation anxiety", homesick, "anxious / scared when I'm apart / away", "can't bear being apart", "miss my mom so much"; Hinglish: "mummy ki bahut yaad aa rahi hai", "door rehna nahi ho pata".
- `anxiety` (parent) gains the Hinglish ghabrahat / ghabra* / bechain* and "mujhe chinta / fikr / tension hai".
Quiet by test: "I live alone and I like it", "leave me alone", "I'm not lonely", "Lonely Planet", "don't panic", other people's panic or loneliness, "I miss the bus".
All four map to the brain area on the body map. No concept alone changes a safety state.

### 15.3 Quick scores (no sum, no label, no diagnosis; a score is stored, never free text)
- Loneliness: one question, "How often do you feel lonely?", answers 1 Never, 2 Rarely, 3 Sometimes, 4 Often, 5 Almost always. Offer-to-talk threshold: 4 or more.
- Anxiety right now: 0 to 10. Threshold for the "talk to someone you trust, a counsellor or your doctor" line and the breathing offer: 7 or more.
Both thresholds are Bubbles' own (not from a validated instrument) and are described to the user only as "a check-in, not a medical assessment". The PHQ-2 / GAD-2 rules are unchanged.

### 15.4 Brain map
An average anxiety score of 7 or more (`STRESS_HIGH_AVERAGE`) across at least `ORGAN_MIN_ENTRIES_FOR_AVERAGE` check-ins makes the brain "worth watching" with: "Your anxiety scores averaged N/10 across M check-ins. If it keeps feeling like a lot, talking to someone can help." The tracker's stress number now also reaches the existing stress rule. Nothing here sets "talk to a doctor".

### 15.5 Chat behaviour (`mind_chat.py`)
When the person reports their own current, recent or recurring panic, separation anxiety, loneliness, anxiety or low mood, the model gets: reply like a close friend; one warm line, one small step, at most one question; name the matching Mind tool; never name or label a condition; never say it is nothing or promise it will pass; no medicine or supplement advice; if they mention not coping or feeling unsafe, stay gentle and point to a person they trust. Safety routing is unchanged and runs first.
Without the AI yes, loneliness gets this fixed reply (then the frozen consent text): "I'm really glad you said that. Feeling lonely is more common than people admit, and it doesn't mean something is wrong with you. One small thing that often helps is a short message to one person you like. The Loneliness check-in in the Mind section is there whenever you want it."

### 15.6 Static supportive copy (Mind hub; friend voice, no labels)
- Loneliness: "Feeling lonely is more common than people say, and it doesn't mean something is wrong with you. A small reach-out often helps: a short message to one person, or a walk where other people are around." Steps: send one short message to someone you like; go somewhere with other people nearby for ten minutes; say it in chat.
- Panic: "You are safe right now. This feeling is strong, and it passes. Let's slow it down together." Steps: breathe in for 4; breathe out slowly for 6, longer than the breath in; press your feet into the floor and name 3 things you can see. (The "you are safe right now" and "it passes" sentences are reassurance about the feeling, not about health; reviewer to confirm they are acceptable.)
- Missing someone / apart: "Missing someone you love is a sign of how much they matter. Being apart can feel heavy, and small rituals make it easier." Steps: pick a regular time to talk; send a voice note or a photo of your day; keep one small thing of theirs close and do one kind thing for yourself.
- Result lines for a high loneliness or anxiety score end with the unchanged support line (reach out right away; 112; Tele-MANAS 14416).
- Brain row wording: nothing to read yet; nothing stands out in what you have logged; worth a gentle look; worth talking through with someone you trust or a doctor. None says healthy or fine.
