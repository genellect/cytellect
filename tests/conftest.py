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


def pytest_configure(config):
    if config.getoption("scientific_collection"):
        config._cytellect_collection = {"collected": [], "deselected": [], "collection_errors": 0}


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_collection_modifyitems(config, items):
    state = getattr(config, "_cytellect_collection", None)
    if state is not None:
        state["collected"] = list(items)
    yield


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
    if (len(collected_ids) != len(collected) or len(selected_ids) != len(selected)
            or len(deselected_ids) != len(deselected) or selected_ids & deselected_ids
            or collected_ids != selected_ids | deselected_ids):
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
    output = Path(destination)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n", encoding="utf-8")
