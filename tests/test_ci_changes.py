import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from ci_changes import code_changed, is_documentation  # noqa: E402


def test_documentation_paths_are_docs_and_root_markdown_only():
    for path in ["docs/methods.md", "docs/sub/a.png", "README.md", "README.en.md", "AGENTS.md", "LICENSE", "NOTICE"]:
        assert is_documentation(path), path
    for path in ["apps/web/public/marketing/a.md", "fixtures/public/bbbc007/README.md", "scripts/x.py",
                 ".github/workflows/ci.yml", "pyproject.toml", "services/api/README.md"]:
        assert not is_documentation(path), path


def test_any_code_or_an_empty_diff_runs_everything():
    assert not code_changed(["README.md", "docs/a.md"])
    assert code_changed(["README.md", "scripts/build_local_bundle.py"])
    assert code_changed([])
