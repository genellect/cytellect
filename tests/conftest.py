"""Optional full-suite collection receipt; no diagnostics or parameter values."""

import hashlib
import json
import re
from collections import Counter
from pathlib import Path

import pytest


def pytest_addoption(parser):
    parser.addoption("--scientific-collection", metavar="PATH", default=None,
                     help="Write a collection receipt bound to this run's JUnit XML")
    parser.addoption("--shard", metavar="INDEX/COUNT", default=None,
                     help="Run one of COUNT deterministic shards of whole test modules "
                          "(CI; scripts/merge_test_shards.py rebuilds the full receipt)")


def _shard(value):
    match = re.fullmatch(r"([0-9]+)/([1-9][0-9]*)", value or "")
    if not match or int(match.group(1)) >= int(match.group(2)):
        raise pytest.UsageError("--shard must be INDEX/COUNT with 0 <= INDEX < COUNT")
    return int(match.group(1)), int(match.group(2))


def _module(item):
    return item.nodeid.split("::", 1)[0].replace("\\", "/")


WEIGHTS = Path(__file__).with_name("shard_weights.json")


def module_weights(counts):
    """Recorded seconds per module (scripts/merge_test_shards.py weights); new modules get the average per test."""
    try:
        recorded = json.loads(WEIGHTS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        recorded = {}
    known = [module for module in counts if isinstance(recorded.get(module), (int, float))]
    per_test = sum(recorded[m] for m in known) / sum(counts[m] for m in known) if known else 1.0
    return {module: float(recorded[module]) if module in known else per_test * count for module, count in counts.items()}


def assign_modules(weights, shards):
    """Whole modules to shards, heaviest first onto the lightest shard; the same collection always splits the same way."""
    loads, assignment = [0.0] * shards, {}
    for module, weight in sorted(weights.items(), key=lambda entry: (-entry[1], entry[0])):
        target = min(range(shards), key=lambda index: (loads[index], index))
        assignment[module] = target
        loads[target] += weight
    return assignment


def pytest_configure(config):
    if config.getoption("shard"):
        _shard(config.getoption("shard"))
    if config.getoption("scientific_collection"):
        config._cytellect_collection = {"collected": [], "deselected": [], "other_shards": [],
                                        "collection_errors": 0}


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_collection_modifyitems(config, items):
    state = getattr(config, "_cytellect_collection", None)
    if state is not None:
        state["collected"] = list(items)
    yield
    # After marker deselection, keep this shard's modules. Items of other shards are not
    # "deselected": the receipt records them separately so one shard never reads as a full run.
    if config.getoption("shard"):
        index, count = _shard(config.getoption("shard"))
        assignment = assign_modules(module_weights(Counter(_module(item) for item in items)), count)
        others = [item for item in items if assignment[_module(item)] != index]
        items[:] = [item for item in items if assignment[_module(item)] == index]
        if state is not None:
            state["other_shards"] = others


def pytest_deselected(items):
    if items:
        state = getattr(items[0].config, "_cytellect_collection", None)
        if state is not None:
            state["deselected"].extend(items)


def pytest_collection_finish(session):
    state = getattr(session.config, "_cytellect_collection", None)
    if state is not None:
        # Before tests execute, testsfailed counts collection errors only.
        state["collection_errors"] = session.testsfailed


def _modules(items):
    result: Counter[str] = Counter()
    invalid = False
    for item in items:
        module = item.nodeid.split("::", 1)[0].replace("\\", "/")
        if not re.fullmatch(r"tests/test_[a-z0-9_]+\.py", module):
            invalid = True
            continue
        result[module] += 1
    return dict(sorted(result.items())), invalid


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_sessionfinish(session, exitstatus):
    # The outer wrapper resumes after pytest's JUnit plugin has written XML.
    yield
    config = session.config
    destination = config.getoption("scientific_collection")
    if not destination:
        return
    state = config._cytellect_collection
    collected, deselected, selected = state["collected"], state["deselected"], session.items
    others = state["other_shards"]
    reasons = []
    if list(config.args) != ["tests"]:
        reasons.append("full_tests_tree_required")
    if config.option.keyword:
        reasons.append("keyword_selection_not_allowed")
    mark = config.option.markexpr.strip()
    if mark not in {"", "not fiji"}:
        reasons.append("marker_selection_not_allowed")
    for option in ("ignore", "ignore_glob", "deselect", "lf", "ff", "nf", "stepwise",
                   "stepwise_skip", "stepwise_reset", "pyargs", "collectonly", "keepduplicates",
                   "override_ini", "inifilename"):
        if getattr(config.option, option, None):
            reasons.append("partial_selection_option_not_allowed")
            break
    if deselected and (mark != "not fiji" or any(item.get_closest_marker("fiji") is None for item in deselected)):
        reasons.append("only_fiji_deselection_allowed")
    collected_ids = {item.nodeid for item in collected}
    selected_ids = {item.nodeid for item in selected}
    deselected_ids = {item.nodeid for item in deselected}
    other_ids = {item.nodeid for item in others}
    if (len(collected_ids) != len(collected) or len(selected_ids) != len(selected)
            or len(deselected_ids) != len(deselected) or selected_ids & deselected_ids
            or (selected_ids | deselected_ids) & other_ids
            or collected_ids != selected_ids | deselected_ids | other_ids):
        reasons.append("collection_selection_mismatch")
    selected_modules, selected_invalid = _modules(selected)
    deselected_modules, deselected_invalid = _modules(deselected)
    if selected_invalid or deselected_invalid:
        reasons.append("unrecognized_test_module")
    if state["collection_errors"]:
        reasons.append("collection_errors")
    if not selected:
        reasons.append("no_selected_tests")
    junit_path = getattr(config.option, "xmlpath", None)
    try:
        junit_sha = hashlib.sha256(Path(junit_path).read_bytes()).hexdigest() if junit_path else None
    except OSError:
        junit_sha = None
    if junit_sha is None:
        reasons.append("junit_not_written")
    receipt = {"format": "cytellect-test-collection", "version": "1.0.0",
               "full_collection": not reasons, "selection_issues": sorted(set(reasons)),
               "marker_selection": mark if mark in {"", "not fiji"} else "unsupported",
               "collection_errors": int(state["collection_errors"]), "exit_status": int(exitstatus),
               "collected": len(collected), "selected": len(selected), "deselected": len(deselected),
               "selected_modules": selected_modules, "deselected_modules": deselected_modules,
               "junit_sha256": junit_sha}
    if config.getoption("shard"):
        index, count = _shard(config.getoption("shard"))
        identities = "\n".join(sorted(item.nodeid.replace("\\", "/") for item in collected)).encode()
        receipt["shard"] = {"index": index, "count": count, "other_shards": len(others),
                            "collected_sha256": hashlib.sha256(identities).hexdigest()}
    output = Path(destination)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n", encoding="utf-8")
