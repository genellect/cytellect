import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from ci_changes import (  # noqa: E402
    ALL,
    areas_for,
    documentation_registry_change,
    normalize,
    select,
    select_changes,
)


def test_documentation_selects_no_heavy_area():
    for path in ["docs/methods.md", "docs/sub/a.png", "README.md", "README.en.md", "AGENTS.md", "LICENSE", "NOTICE",
                 ".github/pull_request_template.md"]:
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


def test_landing_page_changes_select_only_the_landing_page_checks():
    for path in ["apps/web/src/components/PublicLanding.tsx", "apps/web/src/components/LandingFeatures.tsx",
                 "apps/web/src/components/HeroFilm.tsx", "apps/web/src/components/optical-landing.module.css",
                 "apps/web/public/lp-metrics.js", "apps/web/tests/marketing.spec.ts", "apps/web/tests/lp-analytics.spec.ts"]:
        assert areas_for(path) == {"lp"}, path
    assert areas_for("apps/web/public/marketing/hero-film.webm") == {"python", "lp"}
    assert areas_for("fixtures/public/allowlist.json") == {"python", "lp"}
    assert select(["apps/web/src/components/PublicLanding.tsx", "docs/lp-art-direction.md"]) == {"lp"}
    assert areas_for("scripts/lp_film/build_film.py") == frozenset()
    # Other web components still run the real-API browser workflow.
    assert areas_for("apps/web/src/components/WorkspaceApp.tsx") == {"web", "fiji"}


def test_unlisted_paths_and_shared_configuration_select_everything():
    for path in [".github/workflows/ci.yml", "pyproject.toml", "uv.lock", "pnpm-lock.yaml", "package.json",
                 "fixtures/public/bbbc007/README.md", "apps-new/x.ts"]:
        assert areas_for(path) == ALL, path
    assert select([]) == ALL
    assert select(["README.md", "services/proposal-worker/src/a.ts"]) == {"web"}


def test_the_full_web_job_replaces_the_landing_page_job():
    # The web job runs the landing-page tests too, so lp never runs beside it (every main push included).
    assert "lp" not in ALL and normalize(ALL) == ALL
    assert select(["apps/web/src/components/PublicLanding.tsx", "apps/web/src/app/page.tsx"]) == {"web", "fiji"}
    assert select(["apps/web/src/components/PublicLanding.tsx", "services/proposal-worker/src/a.ts"]) == {"web"}


def test_registering_a_documentation_image_is_a_documentation_change():
    old = {"docs/images/a.webp": {"sha256": "1"}, "apps/web/public/marketing/b.webp": {"sha256": "2"}}
    assert documentation_registry_change(old, {**old, "docs/images/c.webp": {"sha256": "3"}})
    assert documentation_registry_change(old, {**old, "docs/images/a.webp": {"sha256": "9"}})
    assert not documentation_registry_change(old, {**old, "apps/web/public/marketing/b.webp": {"sha256": "9"}})
    assert not documentation_registry_change(old, {**old, "docs/images/c.webp": {}, "fixtures/public/x.tif": {}})
    assert not documentation_registry_change(old, dict(old))


def test_a_documentation_registry_change_alone_selects_nothing():
    registry = "fixtures/public/allowlist.json"
    assert select_changes([registry], documentation_registry=True) == frozenset()
    assert select_changes([registry, "README.md", "docs/images/a.webp"], documentation_registry=True) == frozenset()
    assert select_changes([registry, "services/proposal-worker/src/a.ts"], documentation_registry=True) == {"web"}
    assert select_changes([registry], documentation_registry=False) == {"python", "lp"}
