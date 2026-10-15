# Hinglish / Hindi safety terms: review request

**Status:** pending review by (1) a clinician (emergency or general medicine) and (2) at least two native Hindi/Hinglish speakers.
**Code:** `backend/hinglish_terms.py` (vocabulary), `backend/health_semantics.py` (how it is applied).
**Tests:** `backend/tests/test_health_language_corpus.py` (`HINGLISH_CASES`), `backend/tests/eval/safety_cases.jsonl` (S38-S74).

## Why this exists

The RED safety gate (deterministic emergency guidance, no AI call) only understood English. Hinglish and Devanagari
emergencies such as "saans nahi aa rahi" or "मेरे सीने में बहुत तेज दर्द हो रहा है" were classed GREEN and sent to the
generative AI path. The terms below were chosen by an engineer from common usage. They are a first version, not a
clinically validated list.

## How it works (one paragraph)

Devanagari is transliterated to the romanized spelling people type (`सीने में दर्द` → `sine mein dard`), so one
vocabulary covers both scripts. Hinglish phrases map onto the **same concepts and labels** as the English red flags,
so the safety copy and escalation rules are identical. Hindi puts the negator after the symptom
("seene mein dard **nahi hai**"), so Hindi sentences also get Hindi cues for negation, "if" (agar/yadi), someone else
("papa ko ..."), educational questions, history ("pichhle saal", "bachpan mein") and "it went away" ("ab theek hoon").
English sentences are untouched: 1,039 English test texts give byte-identical results before and after.

Design rule: when unsure, escalate. A Hindi phrase is only read as "not a current symptom" when the cue is
unambiguous; everything else stays a current report.

## Terms per red flag (please mark: keep / remove / add)

| Red flag | Hinglish / Hindi wordings recognised | Reviewer notes |
|---|---|---|
| Chest pain or pressure | seene/chhati mein dard, dabav, jakdan, bhaaripan, bojh, **jalan**, chubhan, takleef; seena dukh raha / bhaari lag raha; "seene pe kuch baitha hai"; **dil mein dard** | |
| Breathing difficulty | saans nahi aa rahi / nahi le pa raha; saans lene mein takleef/dikkat; saans phool rahi; saans ruk/atak/ukhad/chadh rahi; saans ruk ruk ke; dam ghut raha; hoth/naakhun neele | |
| Loss of consciousness | behosh, hosh kho diya, chakkar aa ke gir gaya, gash aana | |
| Seizure | mirgi (ka daura), daura pad/aa raha, jhatke aa rahe, fit aa gaya | |
| Heavy bleeding | bahut (zyada) khoon beh/nikal raha, khoon ruk nahi raha, har ghante pad badalna, bade thakke | |
| Suicidal thoughts / crisis | khudkushi, aatmahatya, marna chahta/chahti, marne ka mann/khayal, jeene ka mann nahi karta, jeene ki wajah nahi, nahi jeena, zindagi khatam karna, apni jaan lena, kaash mar jaun / paida na hota, mere bina sab khush rahenge, khud ko maar dun, **zindagi se haar gaya** | |
| Self-harm | khud ko nuksan/chot/hurt karna, nas/kalai kaatna, ek saath saari goliyan kha lena | |
| Stroke signs | munh tedha, chehra ek taraf latak gaya / sunn, zubaan ladkhada rahi, bolne mein atak, achanak bolne mein dikkat, ek taraf ka haath-pair sunn/kamzor, left haath sunn ho gaya, haath hil nahi raha, haath mein jaan nahi, lakwa/falij, achanak dikhna band | |
| Severe allergic reaction | gala band ho raha / sooj gaya / kas raha, hoth/jeebh/chehra sooj gaya, bahut tez allergy | |
| Heart attack | dil ka daura, heart attack (any spelling) | |
| Sudden severe headache | zindagi ka sabse bura sar dard, achanak bahut tez sar dard | |
| Blood in vomit (urgent) | khoon ki ulti, ulti mein khoon | |

## Choices that need a decision

1. **"seene mein jalan"** is usually acidity, but it is escalated because English "burning in my chest" is. Keep it RED, move it to AMBER, or keep RED only with other signs?
2. **"dil mein dard"** is sometimes emotional ("my heart aches"). It is treated as chest pain.
3. **"saas"**: people type it for breath (saans), but it also means mother-in-law. "saas nahi aa rahi" escalates.
4. **"zindagi se haar gaya"** (given up on life) triggers the crisis reply. Frustrated speech may trigger it too.
5. **"left haath sunn ho gaya"** (arm went numb) is EMERGENCY. English "my arm went numb" is URGENT, because the English past tense reads as an event that already happened. Hindi "ho gaya" describes a current state.
6. **Mild wording is not downgraded yet.** English "a little chest tightness" becomes URGENT, but "halka sa dard" in Hindi stays EMERGENCY.
7. **Hedges are not modelled.** "shayad seene mein dard hai" is EMERGENCY; English "maybe chest pain" asks a clarifying question.

## Known gaps (tracked as `known_gap` in the eval set)

- "na seene mein dard hai na saans ki dikkat" (neither/nor) is not read as a denial, so it escalates.
- "mujhe darr hai ki kahin heart attack na ho jaye" (fear of a future event) escalates.
- English, found while doing this work: "I did not have chest pain before but now I do" is classed GREEN. The
  Hinglish version is handled. The English rule was deliberately left unchanged for this release.

- Found in the 2026-10-12 acceptance review, same gap in English, tracked as known_gap: a family-history cue hides the
  user's own report ("family mein history hai aur mujhe seene mein dard hai"); "me and my mother" is read as someone
  else only. ("kal ... tha aur aaj bhi hai", yesterday and today too, is handled in Hinglish; English still misses it.)
- Crisis wording added after review: "mujhe marna hai", "ab aur nahi jee sakta", "main mar jaunga", "khud ko khatam
  kar lunga", "neend ki goliyan kha lunga", "sab khatam kar dunga". Some are also everyday exaggeration ("main mar
  jaunga"); they get the gentle crisis reply, which invites correction. Please confirm.

## Also recommended (not changed)

- Emergency and crisis replies are English-only. Hindi/Hinglish versions of the replies are still needed.
- Done 2026-10-14 (branch `safety-india-crisis-lines`, pending a clinician glance): the crisis replies no longer name
  US 988. They now name **112** (emergency) and **Tele-MANAS 14416 / 1-800-891-4416** (national mental-health line),
  then the local emergency number or findahelpline.com outside India. One shared text: `CRISIS_LINES` in
  `backend/safety_engine.py`.
