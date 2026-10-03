"""Receipts require full collection, exact execution counts, and the same XML."""

import copy
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("scientific_review", REPO / "scripts/scientific_review.py")
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
PLAN = {"version": "1.0.0", "scope": "numerical only", "references": {"r": "https://example.org/reference"}, "checks": [{"id": "math", "question": "matches independent reference", "tests": ["tests/test_example.py"], "references": ["r"], "limit": "not biological acceptance"}], "separate_gates": ["human review"]}


def junit(payload):
    root = ET.fromstring(f"<testsuite>{payload}</testsuite>")
    root.set("tests", str(len(root.findall("testcase"))))
    for name, tag in (("failures", "failure"), ("errors", "error"), ("skipped", "skipped")):
        root.set(name, str(len(root.findall(f"testcase/{tag}"))))
    return ET.tostring(root)


def collection(xml, expected=None, **extra):
    expected = expected or {"tests/test_example.py": 1}
    return {"format": "cytellect-test-collection", "version": "1.0.0", "full_collection": True,
            "selection_issues": [], "marker_selection": "", "collection_errors": 0, "exit_status": 0,
            "collected": sum(expected.values()), "selected": sum(expected.values()), "deselected": 0,
            "selected_modules": expected, "deselected_modules": {},
            "junit_sha256": hashlib.sha256(xml).hexdigest(), **extra}


@pytest.mark.parametrize("payload", ["", '<testcase classname="tests.test_other" name="ok"/>', '<testcase classname="tests.test_example" name="absent"><skipped/></testcase>', '<testcase classname="tests.test_example" name="bad"><failure>PRIVATE_RAW_DIAGNOSTIC</failure></testcase>'])
def test_absent_skipped_failed_cannot_pass_or_leak(payload):
    xml = junit(payload)
    report = MODULE.summarize(PLAN, xml, collection(xml), "a" * 40, False)
    assert report["status"] == "incomplete_or_failed"
    assert "PRIVATE_RAW_DIAGNOSTIC" not in json.dumps(report)


def test_passing_math_does_not_certify_other_gates():
    xml = junit('<testcase classname="tests.test_example" name="works"/>')
    report = MODULE.summarize(PLAN, xml, collection(xml), "a" * 40, True)
    assert report["status"] == "passed"
    assert report["source_dirty"] is True
    assert report["collection"]["full_run_verified"] is True
    assert report["checks"][0]["modules"][0]["expected_selected"] == 1
    assert report["separate_gates"] == [{"gate": "human review", "status": "not_assessed_by_this_run"}]


def test_unrelated_failure_prevents_green_receipt():
    xml = junit('<testcase classname="tests.test_example" name="works"/><testcase classname="tests.test_other" name="bad"><error/></testcase>')
    selected = {"tests/test_example.py": 1, "tests/test_other.py": 1}
    assert MODULE.summarize(PLAN, xml, collection(xml, selected), "a" * 40, False)["status"] == "incomplete_or_failed"


def test_unregistered_reference_is_not_evidence():
    plan = copy.deepcopy(PLAN)
    plan["checks"][0]["references"] = ["unreviewed"]
    xml = junit("")
    with pytest.raises(ValueError, match="unregistered_scientific_reference"):
        MODULE.summarize(plan, xml, collection(xml), "a" * 40, False)


def test_missing_one_test_inside_present_module_does_not_pass():
    xml = junit('<testcase classname="tests.test_example" name="only_one"/>')
    receipt = collection(xml, {"tests/test_example.py": 2})
    assert MODULE.summarize(PLAN, xml, receipt, "a" * 40, False)["status"] == "incomplete_or_failed"


def test_collection_cannot_be_reused_for_different_xml():
    old = junit('<testcase classname="tests.test_example" name="old"/>')
    fresh = junit('<testcase classname="tests.test_example" name="new"/>')
    with pytest.raises(ValueError, match="collection_junit_hash_mismatch"):
        MODULE.summarize(PLAN, fresh, collection(old), "a" * 40, False)


@pytest.mark.parametrize("attribute", ["tests", "failures", "errors", "skipped"])
def test_suite_counters_cannot_hide_missing_or_error_cases(attribute):
    root = ET.fromstring(junit('<testcase classname="tests.test_example" name="works"/>'))
    root.set(attribute, str(int(root.get(attribute)) + 1))
    xml = ET.tostring(root)
    with pytest.raises(ValueError, match="junit_suite_counts_mismatch"):
        MODULE.summarize(PLAN, xml, collection(xml), "a" * 40, False)


def test_suite_level_error_and_duplicate_cases_are_rejected():
    for payload, reason in [('<error>PRIVATE_RAW_DIAGNOSTIC</error>', "unsupported_junit_suite_structure"),
                            ('<testcase classname="tests.test_example" name="same"/>' * 2, "duplicate_junit_testcase")]:
        xml = junit(payload)
        with pytest.raises(ValueError, match=reason):
            MODULE.summarize(PLAN, xml, collection(xml), "a" * 40, False)


def run_fixture(tmp_path, options=(), targets=("tests",), collection_error=False):
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "conftest.py").write_text((REPO / "tests/conftest.py").read_text(encoding="utf-8"), encoding="utf-8")
    (tests / "test_example.py").write_text(
        "import pytest\ndef test_first(): pass\ndef test_second(): pass\n"
        "@pytest.mark.fiji\ndef test_engine(): pass\n", encoding="utf-8")
    (tests / "test_other.py").write_text("def test_first(): pass\n", encoding="utf-8")
    if collection_error:
        (tests / "test_bad.py").write_text('raise RuntimeError("PRIVATE_RAW_DIAGNOSTIC")\n', encoding="utf-8")
    (tmp_path / "pytest.ini").write_text("[pytest]\nmarkers = fiji: separate runtime gate\n", encoding="utf-8")
    xml_path, receipt_path = tmp_path / "run.xml", tmp_path / "collection.json"
    env = {key: value for key, value in os.environ.items() if key not in {"PYTEST_ADDOPTS", "PYTEST_PLUGINS"}}
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    run = subprocess.run([sys.executable, "-m", "pytest", *targets, *options, "-q",
                          f"--junitxml={xml_path}", f"--scientific-collection={receipt_path}"],
                         cwd=tmp_path, env=env, capture_output=True, timeout=30)
    assert receipt_path.is_file(), "collection receipt must be written for this executed run"
    return run.returncode, xml_path.read_bytes(), json.loads(receipt_path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("options", [(), ("-m", "not fiji")])
def test_actual_full_pytest_collection_is_bound_and_counted(tmp_path, options):
    exit_code, xml, receipt = run_fixture(tmp_path, options=options)
    assert exit_code == 0
    assert receipt["full_collection"] is True
    assert receipt["selected_modules"]["tests/test_example.py"] == (2 if options else 3)
    assert receipt["deselected"] == (1 if options else 0)
    assert MODULE.summarize(PLAN, xml, receipt, "a" * 40, False)["status"] == "passed"


@pytest.mark.parametrize("options,targets", [
    (("-k", "first"), ("tests",)),
    ((), ("tests/test_example.py",)),
    (("--ignore=tests/test_other.py",), ("tests",)),
    (("--deselect=tests/test_example.py::test_second",), ("tests",)),
    (("--lf",), ("tests",)),
    (("-m", "fiji"), ("tests",)),
    (("-o", "python_functions=test_first"), ("tests",)),
])
def test_actual_partial_pytest_runs_cannot_claim_full_review(tmp_path, options, targets):
    exit_code, xml, receipt = run_fixture(tmp_path, options=options, targets=targets)
    assert exit_code == 0
    assert receipt["full_collection"] is False
    assert MODULE.summarize(PLAN, xml, receipt, "a" * 40, False)["status"] == "incomplete_or_failed"


def test_actual_collection_error_has_no_raw_diagnostics_in_receipt(tmp_path):
    exit_code, xml, receipt = run_fixture(tmp_path, collection_error=True)
    assert exit_code != 0
    assert receipt["collection_errors"] == 1
    report = MODULE.summarize(PLAN, xml, receipt, "a" * 40, False)
    assert report["status"] == "incomplete_or_failed"
    assert "PRIVATE_RAW_DIAGNOSTIC" not in json.dumps(receipt) + json.dumps(report)
