"""What a result discussion sends, derived from one saved two-group comparison (requirements AC-03,
docs/drafts/llm-assistant/plan.md).

The model reads the result as the researcher sees it: the metric with its name and recorded definition,
the region set, the recorded stain and the channel's label, the researcher's group and run names, the
values, intervals, n and the test. Numbers come only from the saved result.
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


# The workspace's names for per-region metrics; compartment and field-summary metrics use their figure labels.
_REGION_METRICS = {
    "area_px": "面積（px²）", "area_um2": "面積", "mean": "平均輝度", "median": "輝度の中央値",
    "integrated": "積算輝度", "mean_corrected": "平均輝度（背景補正）", "median_corrected": "輝度の中央値（背景補正）",
    "integrated_corrected": "積算輝度（背景補正）",
}


def _metric_text(metric: str) -> tuple[str | None, str | None]:
    """The metric's Japanese name and, when the analysis records one, its definition."""
    from .common_statistics_figures import COMPARTMENT_LABELS, FIELD_SUMMARY_LABELS
    from .field_summary_source import DEFINITIONS
    label = _REGION_METRICS.get(metric) or (COMPARTMENT_LABELS.get(metric) or FIELD_SUMMARY_LABELS.get(metric) or (None, None))[1]
    definition = DEFINITIONS.get(metric)
    return label, definition[:500] if definition else None


def _short(value: Any) -> str | None:
    return value.strip()[:80] if isinstance(value, str) and value.strip() else None


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
    # The researcher's run names (the pairing key); `run N` only when a run has none.
    runs = [{"run": _short(run.get("pair")) or f"run {index + 1}", "control": run["control"], "treatment": run["treatment"],
             "difference": run["difference"], "ratio": run.get("ratio")}
            for index, run in enumerate(estimates.get("runs") or [])]
    p_value = comparison.get("p_value")
    effect = comparison.get("effect")
    metric_label, metric_definition = _metric_text(estimates["metric"])
    return DiscussionContext.model_validate({
        "experiment": (experiment or ExperimentNote()).model_dump(),
        "result": {
            "metric": estimates["metric"],
            "metric_label": metric_label,
            "metric_definition": metric_definition,
            "channel_label": _short(channel.get("label")),
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
