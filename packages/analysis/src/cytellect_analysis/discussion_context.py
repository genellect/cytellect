"""What a result discussion sends, derived from one saved two-group comparison (requirements AC-03).

Only the saved result's numbers and fixed identifiers leave the PC: the metric key, the region set
when it is one of the registered compartments, the recorded stain, the group names, the values,
intervals, n and the test. Run labels, channel IDs, file names, field IDs and paths stay local; runs
are sent as `run 1`, `run 2`… in their saved order.
"""
from __future__ import annotations

import re
from typing import Any

from .discussion_contracts import DiscussionContext, ExperimentNote

# Region sets the analysis itself defines; any other name may be the researcher's own and stays local.
_REGIONS = frozenset({"nucleus", "nuclei", "nucleoli", "nucleoplasm", "cell", "cytoplasm"})
_WARNING = r"^[a-z0-9_]{1,120}$"
# A positivity threshold set without a negative control (the summary's "探索的なしきい値").
_EXPLORATORY = frozenset({"channel_gate_exploratory_threshold_without_negative_control", "gfp_gate_exploratory"})


class DiscussionUnsupported(ValueError):
    """The saved result is not one comparison of two groups with saved estimates."""


def _interval(value: dict[str, Any] | None) -> dict[str, float] | None:
    if not value or value.get("estimate") is None:
        return None
    return {"estimate": value["estimate"], "ci_low": value["ci_low"], "ci_high": value["ci_high"]}


def discussion_context(result: dict[str, Any], experiment: ExperimentNote | None = None) -> DiscussionContext:
    """Build the context from a saved `region-comparison` 2.0.0 result (`result.json` as stored)."""
    estimates = result.get("estimates")
    if result.get("analysis_kind") != "region-comparison" or not estimates:
        raise DiscussionUnsupported("discussion_requires_saved_estimates")
    comparisons = result.get("comparisons") or []
    # A descriptive comparison saves no test (no p value); a tested one saves exactly one contrast.
    if len(comparisons) != (0 if estimates.get("test") == "none" else 1):
        raise DiscussionUnsupported("discussion_requires_one_comparison")
    comparison = comparisons[0] if comparisons else {}
    selection = (result.get("spec") or {}).get("selection") or {}
    region = selection.get("region_set_id")
    channel = result.get("channel") or {}
    stain = channel.get("stain") if isinstance(channel.get("stain"), str) and channel.get("stain") else None
    warnings = [code for code in result.get("warnings") or [] if isinstance(code, str) and re.match(_WARNING, code)]
    runs = [{"run": f"run {index + 1}", "control": run["control"], "treatment": run["treatment"],
             "difference": run["difference"], "ratio": run.get("ratio")}
            for index, run in enumerate(estimates.get("runs") or [])]
    p_value = comparison.get("p_value")
    effect = comparison.get("effect")
    return DiscussionContext.model_validate({
        "experiment": (experiment or ExperimentNote()).model_dump(),
        "result": {
            "metric": estimates["metric"],
            "region": region if region in _REGIONS else None,
            "stain": stain,
            "unit": result.get("unit") or "",
            "scale": estimates["scale"],
            "control": estimates["control"],
            "treatment": estimates["treatment"],
            "design": estimates["design"],
            "test": estimates["test"],
            "exploratory_threshold": any(code in _EXPLORATORY for code in warnings),
            "n_control": estimates["n_control"],
            "n_treatment": estimates["n_treatment"],
            "n_runs": estimates.get("n_pairs"),
            # A descriptive result carries no p value or effect even if a field happens to be present.
            "p_value": p_value if estimates["test"] != "none" and isinstance(p_value, (int, float)) else None,
            "effect": effect if estimates["test"] != "none" and isinstance(effect, (int, float)) else None,
            "groups": [{"condition": group["condition"], "mean": group.get("mean")} for group in estimates["groups"]],
            "difference": _interval(estimates.get("difference")),
            "ratio": _interval(estimates.get("ratio")),
            "runs": runs,
            "warnings": warnings,
        },
    })
