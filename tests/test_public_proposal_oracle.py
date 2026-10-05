"""Exercise the actual CLI with UTF-8 JSON and a non-UTF-8 process locale."""
import json
import os
import subprocess
import sys
from pathlib import Path


def test_oracle_preserves_japanese_from_pipe():
    root = Path(__file__).resolve().parents[1]
    context = {
        "protocol": "1.1.0", "goal": "核の面積を測定する。",
        "channels": [{"token": "ch1", "stain": "DAPI", "role": "nuclear"}],
        "field_count": 1,
    }
    payload = json.dumps({"context": context, "draft": {}}, ensure_ascii=False).encode("utf-8")
    env = {key: value for key, value in os.environ.items()
           if key in {"PATH", "Path", "SystemRoot", "WINDIR", "TEMP", "TMP", "HOME", "VIRTUAL_ENV"}}
    env["PYTHONIOENCODING"] = "ascii:surrogateescape"
    completed = subprocess.run(
        [sys.executable, str(root / "scripts/evaluate_sol_proposal.py")],
        input=payload, capture_output=True, cwd=root, env=env, timeout=15, check=False,
    )
    assert completed.returncode == 0
    assert json.loads(completed.stdout) == {"valid": False, "codes": ["proposal_shape_invalid"]}
