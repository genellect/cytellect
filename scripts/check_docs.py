"""Check what documents and agent skills point at, without network requests.

- Local Markdown links resolve to a file.
- A `dev.py` command or option named in code exists (scripts/dev.py is the single source).
- In CLAUDE.md and the project skills (.claude/skills): a named project skill exists, a skill's
  name is its directory, and a repository path written as code exists.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from dev import command_options  # noqa: E402


def code(text: str) -> list[str]:
    """Fenced blocks line by line, then inline code spans."""
    fenced = re.findall(r"^```[^\n]*\n(.*?)^```", text, flags=re.M | re.S)
    spans = re.findall(r"`([^`\n]+)`", re.sub(r"^```.*?^```", "", text, flags=re.M | re.S))
    return [line for block in fenced for line in block.splitlines()] + spans


def check(root: Path) -> list[str]:
    skill_files = sorted(root.glob(".claude/skills/*/SKILL.md"))
    skills = {path.parent.name for path in skill_files}
    agent_documents = {root / "CLAUDE.md", *skill_files}
    commands = command_options()
    problems = []
    for path in [*sorted(root.glob("*.md")), *sorted(root.glob("docs/*.md")), *skill_files]:
        text = path.read_text(encoding="utf-8")
        name = path.relative_to(root)
        for value in re.findall(r"\]\(([^)]+)\)", text):
            value = value.split("#")[0]
            if not value or "://" in value or value.startswith("mailto:"):
                continue
            if not (path.parent / value).exists():
                problems.append(f"{name} -> {value}")
        for snippet in code(text):
            called = re.search(r"\bdev\.py ([a-z][a-z0-9-]*)((?: +\S+)*)", snippet)
            bare = re.match(r"([a-z][a-z0-9-]*)((?: +\S+)*)$", snippet.strip())
            match = called or (bare if bare and bare.group(1) in commands and "--" in bare.group(2) else None)
            if not match:
                continue
            command, rest = match.group(1), match.group(2).split("#")[0]
            if command not in commands:
                problems.append(f"{name} -> dev.py {command} (no such command)")
                continue
            problems += [f"{name} -> dev.py {command} {option} (no such option)"
                         for option in re.findall(r"(?<!\S)--[a-z][a-z-]*", rest) if option not in commands[command]]
        if path in skill_files:
            declared = re.search(r"^name: (.+)$", text, flags=re.M)
            if not declared or declared.group(1).strip() != path.parent.name:
                problems.append(f"{name} -> name must be {path.parent.name}")
        if path in agent_documents:
            for span in re.findall(r"`([^`\n]+)`", text):
                if re.fullmatch(r"cytellect-[a-z-]+", span) and span not in skills:
                    problems.append(f"{name} -> skill {span} (not in .claude/skills)")
                first = span.split("/")[0]
                looks_like_path = re.fullmatch(r"[\w.-]+(/[\w.-]+)+|[\w.-]+\.md", span) and (root / first).exists()
                if looks_like_path and not (root / span).exists():
                    problems.append(f"{name} -> {span} (no such path)")
    return problems


if __name__ == "__main__":
    found = check(ROOT)
    if found:
        raise SystemExit("\n".join(found))
    print("Local documentation links, dev.py commands and skill references passed.")
