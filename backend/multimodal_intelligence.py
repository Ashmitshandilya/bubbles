"""Batch 31: multimodal/voice boundaries. No raw media is persisted by this module."""
from __future__ import annotations
from typing import Any

ALLOWED_MEDIA={"image","audio","document","food_photo","lab_report"}

def inspect_media_metadata(media_type:str, filename:str|None=None, size_bytes:int|None=None) -> dict[str,Any]:
    kind=str(media_type).lower()
    return {"accepted":kind in ALLOWED_MEDIA,"media_type":kind,"filename":filename,"size_bytes":size_bytes,"raw_media_persisted":False,"next_step":"extract structured facts only after user-authorized processing"}

def voice_session_policy() -> dict[str,Any]:
    return {"transcription":"ephemeral by default","storage":"off by default","tts":"optional","interruptions":True,"consent_required":True,"sensitive_audio_minimization":True}
