import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from ci_changes import ALL, areas_for, select  # noqa: E402


def test_documentation_selects_no_heavy_area():
    for path in ["docs/methods.md", "docs/sub/a.png", "README.md", "README.en.md", "AGENTS.md", "LICENSE", "NOTICE"]:
        assert areas_for(path) == frozenset(), path


def test_each_area_follows_what_its_jobs_build_or_run():
    assert areas_for("services/proposal-worker/src/index.ts") == {"web"}
    assert areas_for("apps/web/src/app/page.tsx") == {"web", "fiji"}
    assert areas_for("apps/web/scripts/finalize-local-export.mjs") == {"web", "fiji", "windows"}
    assert areas_for("packages/analysis/src/cytellect_analysis/statistics.py") == ALL
    assert areas_for("services/api/src/cytellect_api/app.py") == ALL
    assert areas_for("scripts/local_setup.ps1") == {"python", "windows"}
    assert areas_for("engines/fiji/runtime.lock.json") == {"python", "fiji", "windows"}
    assert areas_for("infra/Dockerfile.python") == {"python", "fiji"}
    assert areas_for("tests/test_statistics.py") == {"python", "fiji", "windows"}


def test_unlisted_paths_and_shared_configuration_select_everything():
    for path in [".github/workflows/ci.yml", "pyproject.toml", "uv.lock", "pnpm-lock.yaml", "package.json",
                 "fixtures/public/bbbc007/README.md", "apps-new/x.ts"]:
        assert areas_for(path) == ALL, path
    assert select([]) == ALL
    assert select(["README.md", "services/proposal-worker/src/a.ts"]) == {"web"}
