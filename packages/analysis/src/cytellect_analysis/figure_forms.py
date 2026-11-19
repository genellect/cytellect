"""Which figure forms suit a saved comparison (presentation only).

The forms follow the structure of the experiment, not a list of chart types: the number of
runs per group, the number of observations, and the scale of the metric decide which forms a
researcher can choose and which one is drawn by default.
"""
from __future__ import annotations

from collections import Counter

from .group_comparison_contracts import metric_scale

DENSE_OBSERVATIONS = 30  # per group; fewer points make a density outline misleading
MANY_RUNS = 10  # per group; below this a box or violin of run values is not shown


def _scale(result) -> str:
    try:
        return metric_scale(result.get("metric", ""))
    except ValueError:
        return "difference"


def observation_counts(result) -> Counter:
    rows = [row for row in result.get("plot_data") or [] if row.get("selection_status", "selected") == "selected"]
    return Counter(row["condition"] for row in rows)


def figure_forms(result) -> dict:
    """The default form and the forms a researcher can choose, in display order.

    Each form is a ``kind`` (the saved plot kind) and, for the run hierarchy, the
    ``observations`` layer. Association results have one form.
    """
    if result.get("analysis_kind") == "region-association":
        return {"default": {"kind": "scatter"}, "forms": [{"id": "scatter", "kind": "scatter"}]}
    conditions = result["spec"]["conditions"]
    counts = observation_counts(result)
    runs = Counter(row["condition"] for row in result.get("unit_summary") or [])
    fewest_observations = min((counts.get(c, 0) for c in conditions), default=0)
    fewest_runs = min((runs.get(c, 0) for c in conditions), default=0)
    per_field = result["spec"].get("selection", {}).get("source") == "field-summary"
    scale = _scale(result)
    values = [row["value"] for row in result.get("unit_summary") or []]
    forms = [{"id": "points", "kind": "superplot", "observations": "points"}]
    dense = fewest_observations >= DENSE_OBSERVATIONS and not per_field
    if dense:
        forms.append({"id": "density", "kind": "superplot", "observations": "violin"})
        forms.append({"id": "box", "kind": "superplot", "observations": "box"})
    if scale in ("ratio", "fraction") and values and min(values) >= 0:
        forms.append({"id": "bar", "kind": "unit-mean-bar", "observations": "points"})
    if fewest_runs >= MANY_RUNS:
        forms += [{"id": "run-box", "kind": "box"}, {"id": "run-violin", "kind": "violin"},
                  {"id": "run-histogram", "kind": "histogram"}]
        if result["spec"]["design"]["kind"] == "paired":
            forms.append({"id": "run-paired", "kind": "paired"})
    # Every point coloured by run (a SuperPlot) reads best; outlines and boxes are options.
    default = forms[0]
    return {"default": {key: value for key, value in default.items() if key != "id"}, "forms": forms}
