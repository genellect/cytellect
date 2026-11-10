"""Declared strata (experiment design 1.1.0): one stratum per formal aggregation, never pooled.

The saved design is the only source of a field's stratum. A cohort of a stratified
design names exactly one declared stratum and holds only its fields; descriptions and
comparisons refuse a source that has no stratum, spans strata or was assembled under
another saved design. The selected stratum is recorded in the cohort, the result,
its Methods and its replay. See docs/methods.md, "Experiment design 1.1.0".
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from copy import deepcopy
from typing import Annotated, Final, Literal

from pydantic import Field

from .experiment_design import StratifiedExperimentDesign, field_metadata, parse_design
from .regions import Id, RegionModel

RECORD_VERSION: Final = "stratum-selection/1.0.0"
# Refusals a worker may report as they are (no research content).
SAFE_ERROR_CODES = frozenset({
    "comparison_stratum_required", "comparison_stratum_design_changed", "comparison_stratum_unassigned",
    "comparison_stratum_mixed", "comparison_stratum_metadata_mismatch", "comparison_stratum_legacy_unsupported",
})
Digest64 = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]


class CohortStratum(RegionModel):
    """The stratum a cohort request selects, bound to the saved design it was read from."""
    design_version: Literal["1.1.0"] = "1.1.0"
    design_sha256: Digest64
    stratum_id: Id


class StratumLevelRecord(RegionModel):
    factor_id: Id
    factor: str
    level_id: Id
    level: str


class ExcludedStratumField(RegionModel):
    field_id: Id
    reason: str | None


class StratumRecord(RegionModel):
    """What a cohort, its results and their Methods keep about the selected stratum.

    `field_ids` are every field the researcher assigned to the stratum; `analysed_field_ids`
    the fields the cohort holds; `excluded_fields` the assigned fields excluded before
    analysis, with the researcher's reason. Together they account for every assigned field.
    """
    version: Literal["stratum-selection/1.0.0"] = RECORD_VERSION
    design_version: Literal["1.1.0"] = "1.1.0"
    design_sha256: Digest64
    stratum_id: Id
    label: str
    levels: list[StratumLevelRecord]
    field_ids: list[Id]
    analysed_field_ids: list[Id]
    excluded_fields: list[ExcludedStratumField]


def design_sha256(design) -> str:
    """Canonical hash of the saved design (sorted keys, compact JSON of the validated model)."""
    value = parse_design(design).model_dump(mode="json") if not hasattr(design, "model_dump") else design.model_dump(mode="json")
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def stratified(design) -> StratifiedExperimentDesign | None:
    """The saved design when it declares strata (1.1.0), else None."""
    if design is None:
        return None
    parsed = parse_design(design)
    return parsed if isinstance(parsed, StratifiedExperimentDesign) else None


def stratum_record(design: StratifiedExperimentDesign, stratum_id: str, analysed: Iterable[str] | None = None,
                   excluded: Mapping[str, str | None] | None = None) -> dict:
    stratum = next((item for item in design.strata if item.id == stratum_id), None)
    if stratum is None:
        raise ValueError("stratum_unknown")
    factors = {factor.id: factor for factor in design.factors}
    levels = []
    for factor in design.factors:
        level = next(item for item in factor.levels if item.id == stratum.levels[factor.id])
        levels.append({"factor_id": factor.id, "factor": factor.label, "level_id": level.id, "level": level.label})
    assert set(factors) == set(stratum.levels)
    members = sorted(fid for fid, assignment in design.fields.items() if assignment.stratum_id == stratum.id)
    excluded = dict(excluded or {})
    return StratumRecord(design_sha256=design_sha256(design), stratum_id=stratum.id, label=stratum.label,
                         levels=[StratumLevelRecord(**item) for item in levels], field_ids=members,
                         analysed_field_ids=sorted(members if analysed is None else analysed),
                         excluded_fields=[ExcludedStratumField(field_id=fid, reason=excluded[fid]) for fid in sorted(excluded)],
                         ).model_dump(mode="json")


def check_cohort_stratum(design, requested: CohortStratum | None, source_ids: Iterable[str],
                         excluded_ids: Iterable[str], metadata: Mapping[str, Mapping],
                         exclusion_reasons: Mapping[str, str] | None = None) -> dict | None:
    """Validate a cohort request against the saved design; return the stratum record to keep.

    Without a stratified design the request must not name a stratum and nothing changes.
    With one, the request must name a declared stratum of exactly this saved design;
    the included and excluded fields must be exactly that stratum's fields, and each
    field's metadata must be the metadata the design derives (condition, unit, sample,
    pair, date), so the browser cannot relabel or mix fields.
    """
    plan = stratified(design)
    sources, excluded = set(source_ids), set(excluded_ids)
    if plan is None:
        if requested is not None:
            raise ValueError("cohort_stratum_without_design")
        return None
    if requested is None:
        raise ValueError("cohort_stratum_required")
    if requested.design_sha256 != design_sha256(plan):
        raise ValueError("cohort_stratum_design_changed")
    members = {fid for fid, assignment in plan.fields.items() if assignment.stratum_id == requested.stratum_id}
    if not members:
        raise ValueError("cohort_stratum_empty")
    if sources - members:
        raise ValueError("cohort_stratum_mixed")
    # Fields excluded elsewhere in the workspace belong to other strata and are not this cohort's.
    if (sources | (excluded & members)) != members or sources & excluded:
        raise ValueError("cohort_stratum_incomplete")
    derived = field_metadata(plan)
    for fid in sources:
        if dict(metadata[fid]) != derived[fid].model_dump(mode="json"):
            raise ValueError("cohort_stratum_metadata_mismatch")
    reasons = exclusion_reasons or {}
    return stratum_record(plan, requested.stratum_id, analysed=sources,
                          excluded={fid: reasons.get(fid) for fid in excluded & members})


def check_source_strata(design, config: Mapping) -> None:
    """Refuse a description or comparison whose source is not one declared stratum of the saved design.

    Every source of a stratified design must be a cohort of one declared stratum (one field
    included), assembled under the current saved design, so the stratum, the design hash and
    the exclusion ledger always reach the result. Sources of unstratified designs are unchanged.
    """
    plan = stratified(design)
    record = config.get("stratum")
    if plan is None:
        if record is not None:
            raise ValueError("comparison_stratum_design_changed")
        return
    fields = set(config.get("field_snapshot", {}) or config.get("field_ids", []))
    assigned = {fid: plan.fields[fid].stratum_id for fid in fields
                if fid in plan.fields and plan.fields[fid].stratum_id is not None}
    if set(assigned) != fields:
        raise ValueError("comparison_stratum_unassigned")
    if len(set(assigned.values())) > 1:
        raise ValueError("comparison_stratum_mixed")
    if record is None:
        raise ValueError("comparison_stratum_required")
    if record.get("design_sha256") != design_sha256(plan):
        raise ValueError("comparison_stratum_design_changed")
    if fields != set(record.get("analysed_field_ids", [])) or set(assigned.values()) != {record.get("stratum_id")}:
        raise ValueError("comparison_stratum_mixed")
    # Groups, units, samples, pairs and dates come from the saved design only: a metadata edit of
    # the cohort (or a child of it) cannot relabel fields under the same stratum and design hash.
    derived = field_metadata(plan)
    snapshot = config.get("field_snapshot", {})
    if any(fid not in snapshot or dict(snapshot[fid].get("metadata") or {}) != derived[fid].model_dump(mode="json")
           for fid in fields):
        raise ValueError("comparison_stratum_metadata_mismatch")


def check_preview_strata(design, config: Mapping) -> None:
    """An automatic preview describes one field, or fields of one declared stratum: never several strata
    or unassigned fields together. It records no stratum (a preview is not a formal result)."""
    plan = stratified(design)
    if plan is None:
        return
    fields = set(config.get("field_snapshot", {}) or config.get("field_ids", []))
    if len(fields) <= 1:
        return
    strata = {plan.fields[fid].stratum_id if fid in plan.fields else None for fid in fields}
    if None in strata:
        raise ValueError("comparison_stratum_unassigned")
    if len(strata) > 1:
        raise ValueError("comparison_stratum_mixed")


def refuse_legacy_comparison(design) -> None:
    """Region comparison 1.0.0 predates strata: a stratified design uses common statistics 2.0.0."""
    if stratified(design) is not None:
        raise ValueError("comparison_stratum_legacy_unsupported")


def with_stratum(result: dict, config: Mapping) -> dict:
    """Copy the cohort's stratum record into a result (absent for unstratified sources)."""
    if config.get("stratum") is not None:
        result["stratum"] = deepcopy(config["stratum"])
    return result


def stratum_methods_lines(record: Mapping | None) -> list[str]:
    if not record:
        return []
    levels = "; ".join(f"{item['factor']}: {item['level']}" for item in record["levels"])
    assigned, analysed, excluded = len(record["field_ids"]), len(record["analysed_field_ids"]), len(record["excluded_fields"])
    return [f"Stratum: {record['label']} ({levels}); experiment design {record['design_version']}, "
            f"design sha256 {record['design_sha256']}.",
            f"The researcher assigned {assigned} fields to this declared stratum; {analysed} were analysed and "
            f"{excluded} were excluded before analysis with recorded reasons. Only fields of this stratum were used. "
            "Other strata were neither pooled with it nor compared, and the stratum was not modelled as a factor."]
