"""scripts/check_docs.py: documents and agent skills name only commands, skills and paths that exist."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from check_docs import check  # noqa: E402


def test_this_repository_passes():
    assert check(ROOT) == []


def test_missing_links_commands_options_skills_and_paths_are_reported(tmp_path):
    skill = tmp_path / ".claude/skills/cytellect-a/SKILL.md"
    skill.parent.mkdir(parents=True)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/ok.md").write_text("`python3 scripts/dev.py check --related` and `serve --skip-build`\n", encoding="utf-8")
    skill.write_text(
        "---\nname: cytellect-b\n---\n"
        "See `cytellect-zzz`, `cytellect-a`, `docs/none.md`, `docs/ok.md`, `origin/main` and [x](missing.md).\n\n"
        "```bash\npython3 scripts/dev.py check --nope   # a comment with --words\npython3 scripts/dev.py e2e\n```\n"
        "`check --fiji` and `serve --share`\n", encoding="utf-8")
    assert check(tmp_path) == [
        ".claude/skills/cytellect-a/SKILL.md -> missing.md",
        ".claude/skills/cytellect-a/SKILL.md -> dev.py check --nope (no such option)",
        ".claude/skills/cytellect-a/SKILL.md -> dev.py e2e (no such command)",
        ".claude/skills/cytellect-a/SKILL.md -> dev.py serve --share (no such option)",
        ".claude/skills/cytellect-a/SKILL.md -> name must be cytellect-a",
        ".claude/skills/cytellect-a/SKILL.md -> skill cytellect-zzz (not in .claude/skills)",
        ".claude/skills/cytellect-a/SKILL.md -> docs/none.md (no such path)",
    ]
