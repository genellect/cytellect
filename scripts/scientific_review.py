"""Summarize an actual pytest JUnit run without treating absent/skipped checks as passed.

No test is launched from the registry and no raw failure text, private path or
measurement is copied into the public receipt. The registry links scientific
questions to code checks; separate biological/runtime gates remain separate.
"""

import argparse
import hashlib
import json
import re
from pathlib import Path

from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException


def _cases_with_consistent_totals(root):
    suites = list(root.iter("testsuite"))
    if not suites:
        raise ValueError("junit_test_suite_required")
    cases = []
    totals = {key: 0 for key in ("tests", "failures", "errors", "skipped")}
    for suite in suites:
        if suite.find("testsuite") is not None or suite.find("error") is not None or suite.find("failure") is not None:
            raise ValueError("unsupported_junit_suite_structure")
        children = suite.findall("testcase")
        observed = {"tests": len(children), "failures": 0, "errors": 0, "skipped": 0}
        for case in children:
            outcomes = [(name, case.find(tag) is not None)
                        for name, tag in (("failures", "failure"), ("errors", "error"), ("skipped", "skipped"))]
            if sum(present for _, present in outcomes) > 1:
                raise ValueError("ambiguous_junit_test_outcome")
            for name, present in outcomes:
                observed[name] += int(present)
        for key, actual in observed.items():
            declared = suite.get(key, "")
            if not re.fullmatch(r"[0-9]+", declared) or int(declared) != actual:
                raise ValueError("junit_suite_counts_mismatch")
            totals[key] += actual
        cases.extend(children)
    if root.tag == "testsuites":
        for key, actual in totals.items():
            declared = root.get(key)
            if declared is not None and (not re.fullmatch(r"[0-9]+", declared) or int(declared) != actual):
                raise ValueError("junit_root_counts_mismatch")
    identities = [(case.get("classname", ""), case.get("name", "")) for case in cases]
    if len(cases) != len(list(root.iter("testcase"))):
        raise ValueError("unassigned_junit_testcase")
    if len(identities) != len(set(identities)):
        raise ValueError("duplicate_junit_testcase")
    return cases


def _collection_status(collection, junit, cases):
    if collection.get("format") != "cytellect-test-collection" or collection.get("version") != "1.0.0":
        raise ValueError("full_collection_receipt_required")
    if collection.get("junit_sha256") != hashlib.sha256(junit).hexdigest():
        raise ValueError("collection_junit_hash_mismatch")
    for key in ("collected", "selected", "deselected", "collection_errors", "exit_status"):
        if type(collection.get(key)) is not int or collection[key] < 0:
            raise ValueError("invalid_collection_count")
    for key in ("selected_modules", "deselected_modules"):
        if not isinstance(collection.get(key), dict):
            raise ValueError("invalid_collection_modules")
        for module, count in collection[key].items():
            if not re.fullmatch(r"tests/test_[a-z0-9_]+\.py", module) or type(count) is not int or count < 1:
                raise ValueError("invalid_collection_module")
    expected = collection["selected_modules"]
    consistent = (sum(expected.values()) == collection["selected"]
                  and sum(collection["deselected_modules"].values()) == collection["deselected"]
                  and collection["collected"] == collection["selected"] + collection["deselected"]
                  and len(cases) == collection["selected"])
    observed = {module: sum(case.get("classname", "") == module[:-3].replace("/", ".")
                           or case.get("classname", "").startswith(module[:-3].replace("/", ".") + ".")
                           for case in cases) for module in expected}
    consistent = consistent and observed == expected and sum(observed.values()) == len(cases)
    return (consistent and collection.get("full_collection") is True
            and collection.get("selection_issues") == [] and collection["collection_errors"] == 0
            and collection["exit_status"] == 0 and collection["selected"] > 0
            and collection.get("marker_selection") in {"", "not fiji"})


def summarize(plan: dict, junit: bytes, collection: dict, source_commit: str, source_dirty: bool) -> dict:
    if not re.fullmatch(r"[0-9a-f]{40}", source_commit):
        raise ValueError("full_source_commit_required")
    if plan.get("version") != "1.0.0" or not plan.get("checks"):
        raise ValueError("invalid_review_registry")
    try:
        root = ElementTree.fromstring(junit)
    except (ElementTree.ParseError, DefusedXmlException):
        raise ValueError("invalid_junit_xml") from None
    if root.tag not in {"testsuites", "testsuite"}:
        raise ValueError("invalid_junit_root")
    cases = _cases_with_consistent_totals(root)
    full_run = _collection_status(collection, junit, cases)
    results = []
    ids = set()
    for check in plan["checks"]:
        if check["id"] in ids or not check.get("tests") or not check.get("limit"):
            raise ValueError("invalid_review_check")
        ids.add(check["id"])
        if not check.get("references") or any(r not in plan["references"] for r in check["references"]):
            raise ValueError("unregistered_scientific_reference")
        modules = []
        for test in check["tests"]:
            if not re.fullmatch(r"tests/test_[a-z0-9_]+\.py", test):
                raise ValueError("invalid_test_module")
            module = test.removesuffix(".py").replace("/", ".")
            found = [case for case in cases if case.get("classname", "") == module
                     or case.get("classname", "").startswith(module + ".")]
            counts = {"passed": 0, "failed": 0, "errors": 0, "skipped": 0}
            for case in found:
                if case.find("error") is not None:
                    counts["errors"] += 1
                elif case.find("failure") is not None:
                    counts["failed"] += 1
                elif case.find("skipped") is not None:
                    counts["skipped"] += 1
                else:
                    counts["passed"] += 1
            expected = collection["selected_modules"].get(test, 0)
            passed = full_run and expected > 0 and len(found) == expected and not any(counts[key] for key in ("failed", "errors", "skipped"))
            modules.append({"test_module": test, "status": "passed" if passed else "incomplete_or_failed", "expected_selected": expected, "counts": counts})
        results.append({"id": check["id"], "question": check["question"], "status": "passed" if all(m["status"] == "passed" for m in modules) else "incomplete_or_failed", "modules": modules, "references": check["references"], "limit": check["limit"]})
    # A failed test elsewhere in the same run also prevents a misleading green receipt.
    run_failures = sum(case.find("error") is not None or case.find("failure") is not None for case in cases)
    return {
        "format": "cytellect-scientific-review", "version": "1.0.0",
        "source_commit": source_commit, "source_dirty": source_dirty,
        "registry_sha256": hashlib.sha256(json.dumps(plan, sort_keys=True).encode()).hexdigest(),
        "junit_sha256": hashlib.sha256(junit).hexdigest(),
        "collection_sha256": hashlib.sha256(json.dumps(collection, sort_keys=True).encode()).hexdigest(),
        "collection": {"full_run_verified": full_run, "selected": collection["selected"],
                       "deselected": collection["deselected"], "collection_errors": collection["collection_errors"],
                       "exit_status": collection["exit_status"]},
        "scope": plan["scope"], "status": "passed" if full_run and not run_failures and all(r["status"] == "passed" for r in results) else "incomplete_or_failed",
        "checks": results, "references": plan["references"],
        "separate_gates": [{"gate": gate, "status": "not_assessed_by_this_run"} for gate in plan["separate_gates"]],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=Path("validation/review-plan.json"))
    parser.add_argument("--junit", type=Path, required=True)
    parser.add_argument("--collection", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--source-dirty", action="store_true")
    args = parser.parse_args()
    report = summarize(json.loads(args.registry.read_text(encoding="utf-8")), args.junit.read_bytes(),
                       json.loads(args.collection.read_text(encoding="utf-8")), args.source_commit, args.source_dirty)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "checks": len(report["checks"]), "scope": report["scope"]}))
    if report["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
