"""Check that prepared public inputs are byte-identical to fixtures/public/uploads.json (CI fiji-browser)."""
import hashlib
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
registered = {entry["sha256"]: entry["file"] for entry in
              json.loads((root / "fixtures/public/uploads.json").read_text(encoding="utf-8"))["files"]}
prepared = [path for path in sorted(Path(sys.argv[1]).iterdir()) if path.suffix.lower() in {".tif", ".tiff"}]
unregistered = [path.name for path in prepared if hashlib.sha256(path.read_bytes()).hexdigest() not in registered]
if not prepared or unregistered:
    sys.exit(f"Prepared inputs missing from fixtures/public/uploads.json: {unregistered or 'none prepared'}")
print(f"{len(prepared)} prepared inputs match fixtures/public/uploads.json")
