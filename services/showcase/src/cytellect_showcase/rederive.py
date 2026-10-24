"""Recompute the seed's saved statistics and figures inside the in-browser runtime (build time only).

A visitor's publication package recomputes every statistics result of the revision in the
browser and requires it to equal the saved one exactly. Results the builder computed with
CPython differ from Pyodide's in recorded library versions and in the last bits of some
floating-point values, so the build (``build.py``, ``publish``) runs this inside the Pyodide
harness on the exported seed and publishes the recomputed results.

Values may differ from the saved ones only within the cross-runtime tolerance that
``tests/test_showcase_runtime.py`` uses (relative 1e-9, absolute 1e-12); anything else stops the build.
"""
from __future__ import annotations

import json
import math
import shutil
from typing import Any

# Library versions a result records about itself.
VERSION_RECORDS = {"scipy_version"}
# How the figure was drawn (fonts, files); it is drawn again here and replaced with the rest.
RENDERING = "figure"
RELATIVE, ABSOLUTE = 1e-9, 1e-12


def difference(before: Any, after: Any, where: str = "") -> str | None:
    """The first place where two results differ beyond the tolerance, or None."""
    if isinstance(before, dict) and isinstance(after, dict):
        keys = set(before) - VERSION_RECORDS
        if keys != set(after) - VERSION_RECORDS:
            return f"{where} keys {sorted(keys ^ (set(after) - VERSION_RECORDS))}"
        return next((found for key in sorted(keys) if (found := difference(before[key], after[key], f"{where}.{key}"))), None)
    if isinstance(before, list) and isinstance(after, list):
        if len(before) != len(after):
            return f"{where} length {len(before)} != {len(after)}"
        return next((found for index, (a, b) in enumerate(zip(before, after)) if (found := difference(a, b, f"{where}[{index}]"))), None)
    numbers = (int, float)
    if isinstance(before, numbers) and isinstance(after, numbers) and not isinstance(before, bool) and not isinstance(after, bool):
        a, b = float(before), float(after)
        same = a == b or (math.isnan(a) and math.isnan(b)) or math.isclose(a, b, rel_tol=RELATIVE, abs_tol=ABSOLUTE)
        return None if same else f"{where}: {before!r} != {after!r}"
    return None if type(before) is type(after) and before == after else f"{where}: {str(before)[:120]!r} != {str(after)[:120]!r}"


def rederive_in_place() -> dict:
    """Run every succeeded statistics and figure-render job of the booted seed again, in place."""
    from cytellect_api.db import jobs
    from cytellect_worker.figure_render import run_figure_render
    from cytellect_worker.main import run_statistics

    from . import runtime

    current = runtime._require()
    store, data_dir = current.store, current.settings.data_dir
    handlers = {"statistics": run_statistics, "figure-render": run_figure_render}
    redone: list[str] = []
    counts = {kind: 0 for kind in handlers}
    for job in sorted(store.rows(jobs, state="succeeded"), key=lambda row: row["created"]):
        if job["kind"] not in handlers:
            continue
        target = store.safe_path(job["result_dir"])
        scratch = data_dir / "tmp" / f"rederive-{job['id']}"
        shutil.rmtree(scratch, ignore_errors=True)
        scratch.parent.mkdir(parents=True, exist_ok=True)
        handlers[job["kind"]](store, job, scratch)
        before = json.loads((target / "result.json").read_text())
        after = json.loads((scratch / "result.json").read_text())
        names = sorted(path.name for path in target.iterdir()), sorted(path.name for path in scratch.iterdir())
        found = difference({key: value for key, value in before.items() if key != RENDERING},
                           {key: value for key, value in after.items() if key != RENDERING}) or (f"files {sorted(set(names[0]) ^ set(names[1]))}" if names[0] != names[1] else None)
        if found:
            raise ValueError(f"rederive changed {job['kind']} {job['id']} beyond the cross-runtime tolerance: {found}")
        shutil.rmtree(target)
        shutil.move(scratch, target)
        redone.append(job["result_dir"])
        counts[job["kind"]] += 1
    return {"root": str(data_dir), "dirs": redone, "statistics": counts["statistics"], "figure_render": counts["figure-render"]}
