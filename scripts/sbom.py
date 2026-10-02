"""Small dependency inventory. Never reads environment variables or research volumes."""

import argparse
import importlib.metadata
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
components = []
for dist in importlib.metadata.distributions():
    md = dist.metadata
    license_value = md.get("License-Expression") or md.get("License") or "REVIEW_REQUIRED"
    components.append(
        {
            "type": "library",
            "name": md["Name"],
            "version": dist.version,
            "license_declared": license_value[:2000],
            "source": md.get_all("Project-URL") or [],
        }
    )
repo = Path(__file__).resolve().parents[1]
payload = {
    "schema": "cytellect-dependency-inventory/1",
    "python": sorted(components, key=lambda x: x["name"].lower()),
    "node_lockfile": "pnpm-lock.yaml",
    "fiji": json.loads((repo / "engines/fiji/runtime.lock.json").read_text(encoding="utf-8")),
    "notice": "Inventory, not a legal determination. See docs/oss.md; third-party components retain their licenses.",
}
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
print("Dependency inventory written.")
