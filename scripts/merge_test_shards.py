"""Combine sharded pytest runs into one JUnit XML and one full-collection receipt.

Each shard job runs ``pytest tests --shard I/N --junitxml=... --scientific-collection=...``
and then ``strip`` keeps only test identities, outcomes and timings, so no failure text, path or
measurement leaves the runner. ``merge`` accepts the shards only when they come from the same
collection, cover every index once and select disjoint modules that, with the marker
deselection, add up to everything collected. The result is checked by scientific_review.py
exactly like a single full run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree as ET

from defusedxml import ElementTree as SafeET

OUTCOMES = ("failure", "error", "skipped")
SHARED = ("collected", "deselected", "deselected_modules", "marker_selection")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def strip(junit: bytes, collection: dict) -> tuple[bytes, dict]:
    """Keep each test's identity, outcome and time; drop messages, output and properties."""
    if collection.get("junit_sha256") != _sha(junit) or "shard" not in collection:
        raise ValueError("shard_receipt_not_bound_to_junit")
    root = SafeET.fromstring(junit)
    out = ET.Element("testsuites")
    for suite in root.iter("testsuite"):
        clean = ET.SubElement(out, "testsuite", {"name": "pytest"})
        counts = dict.fromkeys(("tests", "failures", "errors", "skipped"), 0)
        for case in suite.findall("testcase"):
            item = ET.SubElement(clean, "testcase", {"classname": case.get("classname", ""), "name": case.get("name", ""),
                                                      "time": case.get("time", "0")})
            counts["tests"] += 1
            for tag, key in zip(OUTCOMES, ("failures", "errors", "skipped")):
                if case.find(tag) is not None:
                    ET.SubElement(item, tag)
                    counts[key] += 1
        for key, value in counts.items():
            clean.set(key, str(value))
    data = ET.tostring(out, encoding="utf-8")
    return data, {**collection, "junit_sha256": _sha(data)}


def merge(shards: list[tuple[bytes, dict]]) -> tuple[bytes, dict]:
    if not shards:
        raise ValueError("no_shards")
    receipts = [collection for _, collection in shards]
    count = receipts[0]["shard"]["count"]
    if sorted(r["shard"]["index"] for r in receipts) != list(range(count)) or any(r["shard"]["count"] != count for r in receipts):
        raise ValueError("every_shard_exactly_once_required")
    if len({r["shard"]["collected_sha256"] for r in receipts}) != 1 or any(
            json.dumps([r[key] for key in SHARED], sort_keys=True) != json.dumps([receipts[0][key] for key in SHARED], sort_keys=True)
            for r in receipts):
        raise ValueError("shards_from_different_collections")
    for junit, receipt in shards:
        if receipt.get("junit_sha256") != _sha(junit):
            raise ValueError("shard_junit_hash_mismatch")
    modules: dict[str, int] = {}
    for receipt in receipts:
        if set(modules) & set(receipt["selected_modules"]):
            raise ValueError("shards_overlap")
        modules.update(receipt["selected_modules"])
    selected = sum(r["selected"] for r in receipts)
    issues = sorted({issue for r in receipts for issue in r["selection_issues"]})
    if selected + receipts[0]["deselected"] != receipts[0]["collected"]:
        issues = sorted({*issues, "shards_do_not_cover_collection"})
    root = ET.Element("testsuites")
    totals = dict.fromkeys(("tests", "failures", "errors", "skipped"), 0)
    for junit, _ in shards:
        for suite in SafeET.fromstring(junit).iter("testsuite"):
            root.append(suite)
            for key in totals:
                totals[key] += int(suite.get(key, "0"))
    for key, value in totals.items():
        root.set(key, str(value))
    data = ET.tostring(root, encoding="utf-8")
    combined = {key: value for key, value in receipts[0].items() if key != "shard"}
    combined.update({
        "full_collection": not issues and all(r["full_collection"] for r in receipts),
        "selection_issues": issues,
        "collection_errors": max(r["collection_errors"] for r in receipts),
        "exit_status": max(r["exit_status"] for r in receipts),
        "selected": selected, "selected_modules": dict(sorted(modules.items())),
        "junit_sha256": _sha(data),
    })
    return data, combined


def weights(junits: list[bytes]) -> dict[str, float]:
    """Seconds per test module, for tests/shard_weights.json."""
    totals: dict[str, float] = {}
    for junit in junits:
        for case in SafeET.fromstring(junit).iter("testcase"):
            parts = case.get("classname", "").split(".")
            if len(parts) >= 2 and parts[0] == "tests":
                module = f"tests/{parts[1]}.py"
                totals[module] = totals.get(module, 0.0) + float(case.get("time") or 0)
    return {module: round(seconds, 1) for module, seconds in sorted(totals.items())}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    one = commands.add_parser("strip", help="Reduce one shard's JUnit XML to identities and outcomes")
    one.add_argument("--junit", type=Path, required=True)
    one.add_argument("--collection", type=Path, required=True)
    one.add_argument("--output-dir", type=Path, required=True)
    many = commands.add_parser("merge", help="Combine stripped shards into one run")
    many.add_argument("--shards", type=Path, required=True, help="Directory with one sub-directory per shard")
    many.add_argument("--output-junit", type=Path, required=True)
    many.add_argument("--output-collection", type=Path, required=True)
    record = commands.add_parser("weights", help="Write seconds per test module from JUnit files")
    record.add_argument("--junit", type=Path, nargs="+", required=True)
    record.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "weights":
        args.output.write_text(json.dumps(weights([path.read_bytes() for path in args.junit]), indent=1) + "\n", encoding="utf-8")
        return
    if args.command == "strip":
        data, receipt = strip(args.junit.read_bytes(), json.loads(args.collection.read_text(encoding="utf-8")))
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / "junit.xml").write_bytes(data)
        (args.output_dir / "collection.json").write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        return
    shards = [((directory / "junit.xml").read_bytes(), json.loads((directory / "collection.json").read_text(encoding="utf-8")))
              for directory in sorted(path for path in args.shards.iterdir() if path.is_dir())]
    data, receipt = merge(shards)
    args.output_junit.parent.mkdir(parents=True, exist_ok=True)
    args.output_junit.write_bytes(data)
    args.output_collection.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"shards": len(shards), "selected": receipt["selected"], "full_collection": receipt["full_collection"]}))


if __name__ == "__main__":
    main()
