"""The web container copies every repository file the web build imports (scripts/check_web_container_context.py)."""
import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/check_web_container_context.py"
spec = importlib.util.spec_from_file_location("check_web_container_context", SCRIPT)
assert spec and spec.loader
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)

DOCKERFILE = """FROM node AS builder
COPY package.json pnpm-lock.yaml ./
COPY apps/web apps/web
COPY fixtures/planning fixtures/planning
COPY --from=builder /app/out /srv
"""


def write(root: Path, name: str, text: str) -> str:
    (root / name).parent.mkdir(parents=True, exist_ok=True)
    (root / name).write_text(text, encoding="utf-8")
    return name


def test_copy_sources_exclude_the_destination_and_other_stages():
    assert check.copied_sources(DOCKERFILE) == ["package.json", "pnpm-lock.yaml", "apps/web", "fixtures/planning"]


def test_an_import_outside_every_copied_path_is_reported(tmp_path):
    files = [
        write(tmp_path, "apps/web/src/lib/a.test.ts",
              'import cases from "../../../../fixtures/result-summary-cases.json";\n'
              'import plan from "../../../../fixtures/planning/decisions-v2.json";\n'
              'import {x} from "./b";\n'),
        write(tmp_path, "apps/web/src/lib/c.ts", 'const m = await import("../../../../packages/other/x");\n'),
        # Served assets are not compiled, so a path inside them is not a module import.
        write(tmp_path, "apps/web/public/app.js", 'import "../../../outside.js";\n'),
    ]
    assert check.missing_imports(tmp_path, DOCKERFILE, files) == [
        ("apps/web/src/lib/a.test.ts", "../../../../fixtures/result-summary-cases.json"),
        ("apps/web/src/lib/c.ts", "../../../../packages/other/x"),
    ]
    copied = DOCKERFILE + "COPY fixtures/result-summary-cases.json fixtures/result-summary-cases.json\n"
    assert check.missing_imports(tmp_path, copied, files) == [("apps/web/src/lib/c.ts", "../../../../packages/other/x")]


def test_the_committed_web_container_copies_every_imported_path():
    result = subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
