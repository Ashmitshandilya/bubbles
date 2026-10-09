"""Backward-compatible environment names after the Coco -> Bubbles rename.

Import this BEFORE anything reads configuration. It loads backend/.env, then copies every legacy ``COCO_*`` variable to its
``BUBBLES_*`` name when the new name is not set, so an existing .env keeps working (including COCO_DOC_SIGNING_KEY, which
must not change or stored documents would stop verifying). New deployments should use the BUBBLES_* names.
"""
import os

from dotenv import load_dotenv

load_dotenv()
for _k, _v in list(os.environ.items()):
    if _k.startswith("COCO_") and ("BUBBLES_" + _k[5:]) not in os.environ:
        os.environ["BUBBLES_" + _k[5:]] = _v
