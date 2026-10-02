"""Resolve local Markdown links without making research-bearing network requests."""

import re
from pathlib import Path

root = Path(__file__).resolve().parents[1]
missing = []
for path in [*root.glob("*.md"), *root.glob("docs/*.md")]:
    for value in re.findall(r"\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
        value = value.split("#")[0]
        if not value or "://" in value or value.startswith("mailto:"):
            continue
        if not (path.parent / value).exists():
            missing.append(f"{path.relative_to(root)} -> {value}")
if missing:
    raise SystemExit("\n".join(missing))
print("Local documentation links passed.")
