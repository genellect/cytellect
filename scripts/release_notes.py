"""The researcher-facing text of a Windows release (docs/ci.md).

    python scripts/release_notes.py --release-dir release --version 0.1.0-local.22 --commit <sha> \
        --previous-tag v0.1.0-local.21 --out release-notes.md

The text is packaging/windows/release-notes.ja.md, written for researchers: what they can now do,
how to start and what to do when stuck. The version and the installer's size come from the
signed update manifest, which must name this version and commit. The changes of the version come from
packaging/windows/release-highlights/<version>.ja.md. When that file is missing, the text links
the commits since the previous release instead and the command says so, so the owner can write
the changes before publishing. Test results stay in the receipts and the workflow summary.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "packaging/windows/release-notes.ja.md"
HIGHLIGHTS = ROOT / "packaging/windows/release-highlights"
REPOSITORY = "https://github.com/genellect/cytellect"


def highlights(version: str, previous_tag: str, commit: str) -> tuple[str, bool]:
    """The changes of the version and whether they were written for it."""
    path = HIGHLIGHTS / f"{version}.ja.md"
    if path.is_file():
        return path.read_text(encoding="utf-8").strip(), True
    if previous_tag:
        return f"変更の一覧は [{previous_tag} からの変更]({REPOSITORY}/compare/{previous_tag}...{commit}) をご覧ください。", False
    return f"変更の一覧は [コミットの履歴]({REPOSITORY}/commits/{commit}) をご覧ください。", False


def render(release_dir: Path, version: str, commit: str, previous_tag: str = "") -> tuple[str, bool]:
    manifest = json.loads((release_dir / f"Cytellect-update-{version}.json").read_text(encoding="utf-8"))
    if manifest.get("version") != version or manifest.get("source_commit") != commit:
        raise ValueError("the update manifest names another version or commit")
    installer = manifest["installer"]
    changes, written = highlights(version, previous_tag, commit)
    values = {"version": version, "size_gb": f"{installer['bytes'] / 1e9:.2f}", "highlights": changes}
    text = TEMPLATE.read_text(encoding="utf-8")
    for name, value in values.items():
        text = text.replace("{" + name + "}", value)
    left = re.findall(r"\{[a-z_0-9]+\}", text)
    if left:
        raise ValueError(f"unfilled placeholders: {', '.join(sorted(set(left)))}")
    return text, written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--release-dir", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--previous-tag", default="")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        text, written = render(args.release_dir, args.version, args.commit, args.previous_tag)
    except (OSError, KeyError, ValueError) as error:
        print(f"release notes refused: {error}", file=sys.stderr)
        return 1
    args.out.write_text(text, encoding="utf-8")
    if not written:
        print(f"no packaging/windows/release-highlights/{args.version}.ja.md: "
              "the text links the commits; write the changes in the draft before publishing")
    return 0


if __name__ == "__main__":
    sys.exit(main())
