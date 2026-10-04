"""Reject accidental research/binary/secret publication; allow only registered public fixtures."""

import hashlib
import json
import re
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[1]
files = (
    subprocess.check_output(["git", "-c", f"safe.directory={root.as_posix()}", "ls-files", "-z"], cwd=root)
    .decode()
    .split("\0")
)
allowed = {}
registry = root / "fixtures/public/allowlist.json"
if registry.exists():
    allowed = json.loads(registry.read_text(encoding="utf-8"))
sensitive = {
    ".tif",
    ".tiff",
    ".czi",
    ".nd2",
    ".lif",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".mp4",
    ".glb",
    ".blend",
    ".woff2",
    ".woff",
    ".ttf",
    ".pdf",
    ".zip",
    ".npy",
    ".npz",
    ".sqlite",
    ".db",
}
failures = 0
for name in filter(None, files):
    path = root / name
    if not path.is_file():
        continue
    data = path.read_bytes()
    if path.suffix.lower() in sensitive or name in allowed:
        entry = allowed.get(name)
        if (
            not entry
            or not entry.get("source")
            or not entry.get("license")
            or hashlib.sha256(data).hexdigest() != entry.get("sha256")
        ):
            failures += 1
    if path.suffix.lower() not in sensitive and len(data) < 2_000_000:
        text = data.decode("utf-8", errors="ignore")
        if re.search(r"(?:ghp_|gho_|sk_live_)[A-Za-z0-9]{20,}", text):
            failures += 1
        if re.search(r"C:[/\\]Users[/\\](?!<|example|user)[A-Za-z0-9_-]+", text, re.I):
            failures += 1
if failures:
    raise SystemExit(
        f"Public tree rejected: {failures} unregistered data or sensitive-content findings; inspect locally."
    )
print("Public tree check passed.")
