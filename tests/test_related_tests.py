"""scripts/related_tests.py: the tests `dev.py check --related` runs for a change."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from related_tests import imported_names, module_name, related_tests, select  # noqa: E402

SOURCES = {
    "pkg/src/lib/__init__.py": "",
    "pkg/src/lib/stats.py": "from . import shapes\n",
    "pkg/src/lib/shapes.py": "import math\n",
    "scripts/tool.py": "import lib.stats\n",
    "tests/conftest.py": "",
    "tests/helper.py": "from lib import shapes\n",
    "tests/test_stats.py": "from lib.stats import mean\n",
    "tests/test_shapes.py": "from lib import shapes\n",
    "tests/test_tool.py": "import tool\n",
    "tests/test_workflow.py": "TEXT = open('.github/workflows/ci.yml').read()\nNAME = 'allowlist.json'\n",
    "tests/test_helper_user.py": "import helper\n",
}
FILES = frozenset(SOURCES)


def test_a_module_is_named_from_its_outermost_package():
    assert module_name("pkg/src/lib/stats.py", FILES) == "lib.stats"
    assert module_name("pkg/src/lib/__init__.py", FILES) == "lib"
    assert module_name("scripts/tool.py", FILES) == "tool"
    assert module_name("tests/test_tool.py", FILES) == "test_tool"


def test_imports_cover_plain_from_and_relative_forms():
    assert {"lib", "lib.shapes"} <= imported_names("pkg/src/lib/stats.py", SOURCES["pkg/src/lib/stats.py"], FILES)
    assert imported_names("tests/test_stats.py", "from lib.stats import mean\n", FILES) == {"lib.stats", "lib.stats.mean"}
    assert imported_names("tests/broken.py", "def (:\n", FILES) == set()


def test_a_changed_module_selects_the_tests_that_import_it_directly():
    assert select(SOURCES, ["pkg/src/lib/stats.py"]) == ["tests/test_stats.py"]
    assert select(SOURCES, ["pkg/src/lib/shapes.py"]) == ["tests/test_shapes.py"]  # not test_stats, which reaches it through stats
    assert select(SOURCES, ["scripts/tool.py"]) == ["tests/test_tool.py"]
    assert select(SOURCES, ["tests/helper.py"]) == ["tests/test_helper_user.py"]


def test_a_changed_test_selects_itself_and_a_named_file_selects_the_tests_that_read_it():
    assert select(SOURCES, ["tests/test_tool.py"]) == ["tests/test_tool.py"]
    assert select(SOURCES, [".github/workflows/ci.yml"]) == ["tests/test_workflow.py"]
    assert select(SOURCES, ["fixtures/public/allowlist.json"]) == ["tests/test_workflow.py"]
    assert select(SOURCES, ["apps/web/src/app/page.tsx"]) == []
    assert select(SOURCES, ["docs/README.md"]) == []  # a name shared by many files identifies none


def test_the_test_configuration_selects_everything():
    for path in ("tests/conftest.py", "pyproject.toml", "uv.lock"):
        assert select(SOURCES, [path, "pkg/src/lib/stats.py"]) is None


def test_this_repository_resolves_its_own_layout():
    assert "tests/test_related_tests.py" in related_tests(ROOT, ["scripts/related_tests.py"])
    statistics = related_tests(ROOT, ["packages/analysis/src/cytellect_analysis/statistics.py"])
    assert "tests/test_statistics.py" in statistics and len(statistics) < 40
    assert related_tests(ROOT, ["tests/conftest.py"]) is None
