"""The safety copy on the freeze list must stay byte-for-byte what it was before the voice work (origin/main d8d5add).

The expected values are SHA-256 hashes of the real outputs on d8d5add, for nine representative messages and every fixed text on the list:
safety_instruction, CRISIS_LINES, emergency / clarification / urgent_fallback responses, safety_followup_reply, ai_failed_reply,
correction_response, consent_needed_reply, DEGRADED_RESPONSE_TEXT, DOSE_NOTE and scrub_doses, and the two urgent organ-map sentences.
If this test fails, a shared safety text changed: that needs the clinical sign-off in the review packet, not a new hash."""
import hashlib
import json
import os
import sys

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)
os.environ.setdefault("SUPABASE_URL", "http://localhost")
os.environ.setdefault("SUPABASE_SECRET_KEY", "x")

EXPECTED = json.loads(r'''
{
 "CRISIS_LINES": "2d91cc0a15f462d979d42a076cba78776d5f626224df02e474aefacbf43f792d",
 "DEGRADED": "ad9ffc70b41d9df5c5fa3f440358feaa33e8dd868adb94098f6932a997b8e237",
 "DOSE_NOTE": "81683a486ae8f3e6147ba737dea83de82ef60c452209477ff45a2fb03ec71670",
 "ai_failed_plain": "6ab5ef2697ea03a1038f81f43176ed055164a76145e52cc908a50e4f5d637c0e",
 "ai_failed_urgent": "6ab5ef2697ea03a1038f81f43176ed055164a76145e52cc908a50e4f5d637c0e",
 "clarification_response_0": "025a2d09b066855f59be4e515f63af26560a9f2ee7b62f400d2469b7ffcb78d5",
 "clarification_response_1": "30723dc96c8be723142c934589c7cf7eef46de948ab54559ba8da1790a078cc0",
 "clarification_response_2": "0d904732da01c5c78744eda0294255be3cebb5a2f26d3bfc9ea9ace24349c4d9",
 "clarification_response_3": "d255dbd3c852a2f3499a480f17b68a67fd522ae46f095152c232aa5e5599a661",
 "clarification_response_4": "57f42ee1b6d8298c077396ffd3661ffc76fc558d4fe1bf8a2bf2c2b5bb2d1725",
 "clarification_response_5": "d255dbd3c852a2f3499a480f17b68a67fd522ae46f095152c232aa5e5599a661",
 "clarification_response_6": "f5b527ea2e510e3ed736bef94282e3c48132a0925ec1d5433ca807eee3b5a38f",
 "clarification_response_7": "0d904732da01c5c78744eda0294255be3cebb5a2f26d3bfc9ea9ace24349c4d9",
 "clarification_response_8": "7415692130c58ab9f4bce9ee8386f4c0717f2cf6dad0fba3e4c690ffe5d7b0e7",
 "consent_None": "799d42ae73d7ad2e1f67e6b7cec8f75e53e347695f7993af3ab32c76b3199978",
 "consent_Riya": "f2e83925eee1ae0c1f8eb594d7c254317f1707ce3e3af8c54bb1bb6708bfb138",
 "correction_misread_1": "b30ab9c7b5af9519d4c8c00492c6a9389b4e0343a3133344806b8023900bc461",
 "correction_misread_2": "bc26872c458ab814b1e3743b6b8bb796d6d47f4a66beccec8ed7c4a14a073962",
 "correction_unfounded_1": "7d3515608430baca8b56820e8be2c0d74f03256b91f2b8a887c35ec521a1d5cd",
 "correction_unfounded_2": "0a40e669fb265f937c5c6eefd412bfc96846d23ab6e2ecd0a2055a6aa64e3932",
 "correction_update_1": "9ed62ed7528dc953fe99e21220037b8bc5adb3134c3a15e459b1c77b077cd02f",
 "correction_update_2": "3a96235644194d8d042dcebd77a6f1ed7c62e0608c06bf9714a87475f3e45de2",
 "emergency_response_0": "e5d7a3eb2a762ef3e81b2a0758f46b20b8fd0ffccc44a68cf1348f3be199b47a",
 "emergency_response_1": "5a46c0fb30e174ef7f91c80e2f74e1b89bb7e0b772a16166c9c0be4a1972ea18",
 "emergency_response_2": "25d13f935233e2708bd6ae564b067fa59883691460dadd030bb5eb347552be27",
 "emergency_response_3": "b5dd26854c94880e8381cc900d073f46837146d24ed779e84dcb817e923c1ddb",
 "emergency_response_4": "d889c01bb8ef32acee8bf96fc673a932312e88f8cb406925bba2c85d5101c535",
 "emergency_response_5": "b5dd26854c94880e8381cc900d073f46837146d24ed779e84dcb817e923c1ddb",
 "emergency_response_6": "26f83ae9c9589598d7f06f07d529e59f28d734289cf962ea647c3758dc9cd9bb",
 "emergency_response_7": "25d13f935233e2708bd6ae564b067fa59883691460dadd030bb5eb347552be27",
 "emergency_response_8": "285626bb85ae7b7a338e0e82274f97d5dab5e35105b5524da5cae6c54ac82435",
 "followup_clarification_POTENTIAL_REDFLAG_NEEDS_CLARIFICATION__None": "f3c6a8d2c588474dd1c30e1038e9727e36ae662df17ae48e76d75c9c761095fb",
 "followup_clarification_POTENTIAL_REDFLAG_NEEDS_CLARIFICATION__Riya": "f3c6a8d2c588474dd1c30e1038e9727e36ae662df17ae48e76d75c9c761095fb",
 "followup_emergency_EMERGENCY__None": "d171e67f35cbf2f03ae38d1ceda653a15439e45803937cd835993cea40aee3d8",
 "followup_emergency_EMERGENCY__Riya": "3d986d4b147fd2a6657667a5f0cead831947f7353d64fb7f5e458b0a64aebd4f",
 "followup_emergency_EMERGENCY_self_harm_None": "3250134e91141c2da3987c476a6d932edaab5209c1dd0bafb0c135c66bba0bc0",
 "followup_emergency_EMERGENCY_self_harm_Riya": "a7d084bc9054bc88d0f5fdd1ca69026fa4965b31850a315a6bb95385cba3c38c",
 "followup_emergency_EMERGENCY_suicidal_ideation_None": "3250134e91141c2da3987c476a6d932edaab5209c1dd0bafb0c135c66bba0bc0",
 "followup_emergency_EMERGENCY_suicidal_ideation_Riya": "a7d084bc9054bc88d0f5fdd1ca69026fa4965b31850a315a6bb95385cba3c38c",
 "followup_reply_URGENT__None": "ae40a633f74829da136f01345edec13386285ee7441a43c1c9baf48af675b330",
 "followup_reply_URGENT__Riya": "7524d10f967fe79fd318181bc3c83f09a651383236085aea374bc92f342234b6",
 "organ_Please get medical a": "adefea26f54485c498827d1e480c94abbd7c77156da105025138d6d51280c846",
 "organ_This deserves prompt": "248694a8844e795aac1f85bebac3a224705e8539dc3673ffec316a0f3090bf5d",
 "safety_instruction_0": "09f964e11e709e130db86029dd1f3f10be57df5ae39d2d96471008cf17db97df",
 "safety_instruction_1": "c68a32b1989d0c3c4127bee31e9d499c420677c347e38152cd9e444cb04fb91b",
 "safety_instruction_2": "09f964e11e709e130db86029dd1f3f10be57df5ae39d2d96471008cf17db97df",
 "safety_instruction_3": "634c14c4ccfe27a8176bb723c309bbeaafa5f4537b7e1ca9b0db6b2a00c3fbe4",
 "safety_instruction_4": "09f964e11e709e130db86029dd1f3f10be57df5ae39d2d96471008cf17db97df",
 "safety_instruction_5": "634c14c4ccfe27a8176bb723c309bbeaafa5f4537b7e1ca9b0db6b2a00c3fbe4",
 "safety_instruction_6": "f290abc53648732788b4f4bae3ceba650652f41d6a864d983e5553daa32e0463",
 "safety_instruction_7": "09f964e11e709e130db86029dd1f3f10be57df5ae39d2d96471008cf17db97df",
 "safety_instruction_8": "09f964e11e709e130db86029dd1f3f10be57df5ae39d2d96471008cf17db97df",
 "scrub": "1f844bd816d09525880536a1598548850babe52099c4cbe1288bcc652f44fe3f",
 "state_0": "RED|EMERGENCY",
 "state_1": "AMBER|POTENTIAL_REDFLAG_NEEDS_CLARIFICATION",
 "state_2": "RED|EMERGENCY",
 "state_3": "GREEN|NO_REDFLAG",
 "state_4": "RED|EMERGENCY",
 "state_5": "GREEN|NO_REDFLAG",
 "state_6": "AMBER|URGENT",
 "state_7": "RED|EMERGENCY",
 "state_8": "RED|EMERGENCY",
 "urgent_fallback_response_0": "85df90b72022c50c637ee8ae1c583ce2a5587605b9bfb1525e12c91a821caebc",
 "urgent_fallback_response_1": "adc50fc77ed1ced7843941a1cdd04e92c0e69a37570cf5689a7d169fcecc839f",
 "urgent_fallback_response_2": "97e6ef1562f285eff4a274c2f9040d5ade8f2ac1519b9e7eca3075d4ad2fbb1a",
 "urgent_fallback_response_3": "bad28261d8d09dde8fafecd7ee2db765f50f6ff802a087adc933937fc5293226",
 "urgent_fallback_response_4": "7e617c2961c6d8f4b29c2d5b4632e65bcda69c5a32f68cb32b0b87a5cdcfa375",
 "urgent_fallback_response_5": "bad28261d8d09dde8fafecd7ee2db765f50f6ff802a087adc933937fc5293226",
 "urgent_fallback_response_6": "dc949e4452358f4dd4403a630ff1c2ec994797645d12da20c8a8e951bcf13300",
 "urgent_fallback_response_7": "97e6ef1562f285eff4a274c2f9040d5ade8f2ac1519b9e7eca3075d4ad2fbb1a",
 "urgent_fallback_response_8": "5fcb65bb1ca6fbb149cf0730fc1429fd0881bf98e21bc17beac03cbf1b3358b7"
}
''')


def h(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def snapshot():
    import safety_engine as se
    import chat_pipeline as cp
    import consent
    import conversation_correction as cc
    import bubbles_ai
    import response_quality as rq
    out = {}
    msgs = ["I have crushing chest pain and cannot breathe", "chest pain since morning, maybe", "I want to end my life", "my baby is not breathing",
            "heavy bleeding soaking a pad every hour", "I feel a bit tired", "severe headache worst of my life", "I am having thoughts of suicide",
            "face drooping and slurred speech"]
    for i, m in enumerate(msgs):
        a = se.assess_safety(m)
        out[f"state_{i}"] = f"{a.level}|{a.state}"
        for fn in ("safety_instruction", "emergency_response", "clarification_response", "urgent_fallback_response"):
            try:
                out[f"{fn}_{i}"] = h(getattr(se, fn)(a))
            except Exception as e:  # noqa: BLE001
                out[f"{fn}_{i}"] = "ERR:" + type(e).__name__
    out["CRISIS_LINES"] = h(repr(se.CRISIS_LINES))
    for kind, state, concepts in [("emergency", "EMERGENCY", []), ("clarification", "POTENTIAL_REDFLAG_NEEDS_CLARIFICATION", []),
                                  ("reply", "URGENT", []), ("emergency", "EMERGENCY", ["suicidal_ideation"]), ("emergency", "EMERGENCY", sorted(cp.CRISIS)[:1])]:
        for name in (None, "Riya"):
            reply = {"metadata": {"kind": kind, "safety": {"state": state, "concepts": concepts}}}
            out[f"followup_{kind}_{state}_{'-'.join(concepts)}_{name}"] = h(cp.safety_followup_reply(reply, name=name))
    for name in (None, "Riya"):
        out[f"consent_{name}"] = h(consent.consent_needed_reply(name))
    out["DEGRADED"] = h(bubbles_ai.DEGRADED_RESPONSE_TEXT)
    out["DOSE_NOTE"] = h(rq.DOSE_NOTE)
    out["scrub"] = h(repr(rq.scrub_doses("Take paracetamol 500 mg twice a day. Rest well.")))
    import types
    turn = types.SimpleNamespace(safety=se.assess_safety("I have crushing chest pain"), log=types.SimpleNamespace(metrics={}))
    out["ai_failed_urgent"] = h(cp.ai_failed_reply(turn, name="Riya", saved_events=0))
    turn2 = types.SimpleNamespace(safety=se.assess_safety("I feel tired"), log=types.SimpleNamespace(metrics={}))
    out["ai_failed_plain"] = h(cp.ai_failed_reply(turn2, name=None, saved_events=0))
    for kind in ("misread", "unfounded", "update"):
        for concepts in (("headache",), ("headache", "nausea")):
            c = cc.Correction(True, kind=kind, concepts=concepts, retract_message_id="m", reject_user_message_id="u")
            try:
                out[f"correction_{kind}_{len(concepts)}"] = h(cc.correction_response(c))
            except Exception as e:  # noqa: BLE001
                out[f"correction_{kind}_{len(concepts)}"] = "ERR:" + type(e).__name__
    src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "organ_map_engine.py"), encoding="utf-8").read()
    for marker in ("This deserves prompt attention: please speak to a doctor or an urgent-care",
                   "Please get medical advice promptly, and urgently if you are breathless."):
        out["organ_" + marker[:20]] = h(marker) if marker in src else "MISSING"
    return out


def test_every_freeze_list_text_is_unchanged():
    got = snapshot()
    assert set(got) == set(EXPECTED)
    changed = sorted(k for k in EXPECTED if got[k] != EXPECTED[k])
    assert not changed, f"freeze-list text changed: {changed}"
    assert not [k for k, v in got.items() if str(v).startswith("ERR") or v == "MISSING"]
