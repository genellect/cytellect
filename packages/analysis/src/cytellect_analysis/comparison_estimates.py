"""Treatment − control estimates 1.0.0 for two-group comparisons (WP4, implementation pending).

Definitions are in docs/methods.md, "Comparison estimates 1.0.0". Inputs are the
independent-unit values already aggregated by the saved comparison
(field → sample → unit); this module never re-aggregates observations.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from .group_comparison_contracts import ComparisonEstimates


def comparison_estimates(control: Sequence[float], treatment: Sequence[float], *, control_label: str,
                         treatment_label: str, design: Literal["independent", "paired"],
                         test: Literal["welch-t", "paired-t", "mann-whitney-u", "wilcoxon"], metric: str,
                         pairs: Sequence[str] | None = None) -> ComparisonEstimates:
    """For a paired design, control[i] and treatment[i] are the two units of pairs[i]."""
    raise NotImplementedError("comparison_estimates_not_implemented")
