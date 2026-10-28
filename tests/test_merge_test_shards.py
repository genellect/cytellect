"""Sharded runs rebuild the full-run receipt only when every shard of one collection is present."""

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


def _load(name):
    spec = importlib.util.spec_from_file_location(name, REPO / f"scripts/{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MERGE, REVIEW = _load("merge_test_shards"), _load("scientific_review")
_spec = importlib.util.spec_from_file_location("cytellect_conftest", REPO / "tests/conftest.py")
assert _spec and _spec.loader
CONFTEST = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(CONFTEST)
PLAN = {"version": "1.0.0", "scope": "numerical only", "references": {"r": "https://example.org/reference"},
        "checks": [{"id": "math", "question": "matches independent reference", "tests": ["tests/test_example.py"],
                    "references": ["r"], "limit": "not biological acceptance"}], "separate_gates": ["human review"]}


def run_shards(tmp_path, count, failing=False):
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "conftest.py").write_text((REPO / "tests/conftest.py").read_text(encoding="utf-8"), encoding="utf-8")
    (tests / "test_example.py").write_text(
        "import pytest\ndef test_first(): pass\ndef test_second(): pass\n"
        "@pytest.mark.fiji\ndef test_engine(): pass\n", encoding="utf-8")
    body = 'def test_first(): assert False, "PRIVATE_RAW_DIAGNOSTIC"\n' if failing else "def test_first(): pass\n"
    (tests / "test_other.py").write_text(body, encoding="utf-8")
    (tests / "test_third.py").write_text("def test_a(): pass\ndef test_b(): pass\ndef test_c(): pass\n", encoding="utf-8")
    (tmp_path / "pytest.ini").write_text("[pytest]\nmarkers = fiji: separate runtime gate\n", encoding="utf-8")
    env = {key: value for key, value in os.environ.items() if key not in {"PYTEST_ADDOPTS", "PYTEST_PLUGINS"}}
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    shards = []
    for index in range(count):
        xml, receipt = tmp_path / f"run-{index}.xml", tmp_path / f"collection-{index}.json"
        subprocess.run([sys.executable, "-m", "pytest", "tests", "-m", "not fiji", "-q", f"--shard={index}/{count}",
                        f"--junitxml={xml}", f"--scientific-collection={receipt}"],
                       cwd=tmp_path, env=env, capture_output=True, timeout=30)
        shards.append(MERGE.strip(xml.read_bytes(), json.loads(receipt.read_text(encoding="utf-8"))))
    return shards


def test_all_shards_rebuild_a_full_run(tmp_path):
    shards = run_shards(tmp_path, 2)
    assert sorted(module for _, receipt in shards for module in receipt["selected_modules"]) == [
        "tests/test_example.py", "tests/test_other.py", "tests/test_third.py"]
    xml, receipt = MERGE.merge(shards)
    assert receipt["full_collection"] is True and "shard" not in receipt
    assert (receipt["collected"], receipt["selected"], receipt["deselected"]) == (7, 6, 1)
    report = REVIEW.summarize(PLAN, xml, receipt, "a" * 40, False)
    assert report["status"] == "passed" and report["collection"]["full_run_verified"] is True


def test_one_shard_is_never_a_full_run(tmp_path):
    xml, receipt = run_shards(tmp_path, 2)[0]
    assert REVIEW.summarize(PLAN, xml, receipt, "a" * 40, False)["collection"]["full_run_verified"] is False


@pytest.mark.parametrize("change", ["missing", "duplicate", "foreign"])
def test_incomplete_or_mixed_shards_are_rejected(tmp_path, change):
    shards = run_shards(tmp_path, 3)
    if change == "missing":
        shards = shards[:2]
    elif change == "duplicate":
        shards = [shards[0], shards[0], shards[2]]
    else:
        xml, receipt = shards[1]
        shards[1] = (xml, {**receipt, "shard": {**receipt["shard"], "collected_sha256": "0" * 64}})
    with pytest.raises(ValueError):
        MERGE.merge(shards)


def test_a_failure_in_any_shard_fails_without_leaking_its_text(tmp_path):
    shards = run_shards(tmp_path, 2, failing=True)
    assert all(b"PRIVATE_RAW_DIAGNOSTIC" not in xml for xml, _ in shards)
    xml, receipt = MERGE.merge(shards)
    assert receipt["exit_status"] != 0
    assert REVIEW.summarize(PLAN, xml, receipt, "a" * 40, False)["status"] == "incomplete_or_failed"


def test_modules_split_deterministically_onto_the_lightest_shard():
    counts = {"tests/test_a.py": 5, "tests/test_b.py": 4, "tests/test_c.py": 3, "tests/test_d.py": 2}
    assert CONFTEST.assign_modules(counts, 2) == {"tests/test_a.py": 0, "tests/test_b.py": 1, "tests/test_c.py": 1, "tests/test_d.py": 0}
    assert CONFTEST.assign_modules(counts, 2) == CONFTEST.assign_modules(dict(reversed(list(counts.items()))), 2)

