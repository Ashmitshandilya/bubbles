"""Legacy COCO_* environment names keep working after the rename (env_compat maps them to BUBBLES_*)."""
import os
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]


def run(env_extra):
    env = {k: v for k, v in os.environ.items() if not k.startswith(("COCO_", "BUBBLES_"))}
    env.update(env_extra)
    code = "import env_compat, os; print(os.environ.get('BUBBLES_DOC_SIGNING_KEY'), os.environ.get('BUBBLES_ENABLE_RXNAV'))"
    return subprocess.run([sys.executable, "-c", code], cwd=BACKEND, env=env, capture_output=True, text=True).stdout.split()


def test_legacy_names_are_mapped_and_new_names_win():
    assert run({"COCO_DOC_SIGNING_KEY": "old-key", "COCO_ENABLE_RXNAV": "1"}) == ["old-key", "1"]
    assert run({"COCO_DOC_SIGNING_KEY": "old-key", "BUBBLES_DOC_SIGNING_KEY": "new-key"})[0] == "new-key"
    assert run({}) == ["None", "None"]
