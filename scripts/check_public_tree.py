"""Reject accidental research/binary/secret publication; allow only registered public fixtures.

Also keeps the published demo files (apps/web/public/showcase) at or below SHOWCASE_LIMIT_BYTES (DM-10).
"""

import hashlib
import json
import re
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[1]
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
SHOWCASE_DIR = "apps/web/public/showcase/"
# DM-10: 700 MB. The requirement does not define MB, so the limit is read as 700 MiB (700 × 1024 × 1024 bytes).
SHOWCASE_LIMIT_BYTES = 700 * 1024 * 1024


def tracked_files(base: Path) -> list[str]:
    output = subprocess.check_output(["git", "-c", f"safe.directory={base.as_posix()}", "ls-files", "-z"], cwd=base)
    return list(filter(None, output.decode().split("\0")))


def showcase_size(base: Path, names: list[str]) -> int:
    """Total bytes of the tracked files under the published demo directory.

    A tracked symlink counts as the file it points to, because the site build publishes that file's bytes.
    """
    return sum(
        (base / name).stat().st_size
        for name in names
        if name.startswith(SHOWCASE_DIR) and (base / name).is_file()
    )


def showcase_size_error(total: int, limit: int) -> str | None:
    if total <= limit:
        return None
    return (
        f"Public tree rejected: published demo files ({SHOWCASE_DIR}) total {total:,} bytes "
        f"({total / 1024 / 1024:.2f} MiB), above the {limit:,}-byte ({limit / 1024 / 1024:.2f} MiB) limit (DM-10); "
        "review the recorded scenes before adding more."
    )


def content_failures(base: Path, names: list[str]) -> int:
    allowed = {}
    registry = base / "fixtures/public/allowlist.json"
    if registry.exists():
        allowed = json.loads(registry.read_text(encoding="utf-8"))
    failures = 0
    for name in names:
        path = base / name
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
    return failures


def main(base: Path = root) -> None:
    names = tracked_files(base)
    errors = []
    failures = content_failures(base, names)
    if failures:
        errors.append(
            f"Public tree rejected: {failures} unregistered data or sensitive-content findings; inspect locally."
        )
    size_error = showcase_size_error(showcase_size(base, names), SHOWCASE_LIMIT_BYTES)
    if size_error:
        errors.append(size_error)
    if errors:
        raise SystemExit("\n".join(errors))
    print("Public tree check passed.")


if __name__ == "__main__":
    main()
