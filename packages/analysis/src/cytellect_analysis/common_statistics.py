"""Source-bound, explicitly adopted common statistics; v1 dispatch is untouched."""
from types import SimpleNamespace

import pandas as pd

from .common_statistics_contracts import (
    RegionAssociationRequest,
    RegionAssociationResult,
    RegionComparisonRequestV2,
    RegionComparisonResultV2,
)
from .common_unit_inference import (
    VERSION,
    compare_common_units,
    correlate_common_units,
    omnibus_common_units,
)
from .comparison_estimates import comparison_estimates
from .compartment_observations import LOG2, acquisition_proxy, compartment_comparison_source
from .compartment_observations import SAFE_ERROR_CODES as COMPARTMENT_ERRORS
from .compartment_review import compartment_missing_summary, confirmed_policy
from .descriptive_contracts import CompartmentMissingSummary, RegionSelection
from .field_summary_source import prepare_field_summary_observations
from .gfp_selection import SAFE_ERROR_CODES as GFP_GATE_ERRORS
from .gfp_selection import gate_of, gate_source_observations, gate_warnings
from .region_comparison import SAFE_ERROR_CODES as COMPARISON_ERRORS
from .region_comparison import _acquisition, _design_ledger, _source, source_fingerprint
from .statistics import finite_records
from .unit_inference import aggregate_unit_observations, apply_holm

SAFE_ERROR_CODES = COMPARISON_ERRORS | COMPARTMENT_ERRORS | GFP_GATE_ERRORS | frozenset({
    "common_statistics_finite_units_required", "common_statistics_insufficient_units",
    "common_statistics_constant_units", "common_statistics_not_estimable",
    "common_statistics_insufficient_nonzero_pairs", "common_statistics_unknown_method",
    "common_statistics_three_groups_required", "common_statistics_unmatched_units",
    "common_statistics_test_design_mismatch", "common_statistics_omnibus_design_mismatch",
    "common_statistics_omnibus_required", "common_statistics_omnibus_contrast_mismatch",
    "common_statistics_independent_association_required", "common_statistics_distinct_metrics_required",
    "common_statistics_matched_region_set_required", "common_statistics_pooling_confirmation_required",
    "common_statistics_result_required",
    "common_statistics_matched_gfp_selection_required", "common_statistics_matched_intensity_policy_required",
    "common_statistics_matched_observations_required",
    "comparison_estimates_single_contrast_required", "comparison_estimates_unknown_metric",
    "field_summary_positivity_not_connected", "field_summary_nuclear_source_required", "field_summary_status_mismatch", "field_summary_region_identity",
    "field_summary_invalid_calibration",
    "compartment_missing_association_unsupported", "compartment_missing_policy_unknown",
    "compartment_missing_ledger_changed", "compartment_state_not_missing", "compartment_ledger_invalid",
})


def _prepared(report, config, request, summaries=None, nuclear=None, shapes=None):
    compartment = request.selection.source == "compartment-summary"
    per_field = request.selection.source == "field-summary"
    if compartment:
        snapshot, observations, sources, unit, failed = compartment_comparison_source(
            report, config, request.selection, summaries, shapes)
    elif per_field:
        area = RegionSelection(source="region", region_set_id=request.selection.region_set_id, channel_id=None,
                               metric="area_px")
        snapshot, *_ = _source(report, config, SimpleNamespace(selection=area))
        observations, sources, unit, failed = prepare_field_summary_observations(report, snapshot, request.selection)
    else:
        snapshot, observations, sources, unit, failed = _source(report, config, request)
    gate_record = None
    if gate_of(request.selection) is not None:
        observations, gate_record = gate_source_observations(
            report, config.get("recipe"), snapshot, request.selection, observations, failed, summaries, nuclear)
    ledger, unit_ledger, pairs, selected, observation_ledger, missing, counts = _design_ledger(
        snapshot, observations, report, request,
        control_fields=None if gate_record is None else gate_record["control_field_ids"])
    acquisition, warnings = _acquisition(sources, snapshot, selected, ledger,
                                         acquisition_proxy(request) if compartment or per_field else request)
    if not request.selection.metric.startswith("area_") and not per_field:
        selected_ids = {(row["field_id"], row["region_id"]) for row in selected}
        for fid, table in report["field_tables"].items():
            for row in table["rows"]:
                if ((fid, row["region_id"]) in selected_ids and row["channel_id"] == request.selection.channel_id
                        and (row["storage_limit_fraction"] > 0 or (row["acquisition_saturation_fraction"] or 0) > 0)):
                    raise ValueError("region_comparison_saturated_signal")
    fields, samples, units = aggregate_unit_observations(pd.DataFrame(selected), "value")
    channel = (next(p["channel"] for p in sources[0]["channel_provenance"]
                    if p["channel"]["channel_id"] == request.selection.channel_id)
               if getattr(request.selection, "channel_id", None) is not None else None)
    if missing:
        warnings.append("missing_outcomes_excluded_not_assumed_missing_at_random")
    if failed:
        warnings.append("explicitly_excluded_failed_fields_have_unknown_observation_counts")
    warnings.append("acquisition_comparability_user_confirmed_not_machine_verified")
    if compartment and request.selection.metric == LOG2:
        warnings.append("nucleolar_union_saturation_not_assessed")
    selection = {"input_rows": len(observations), **counts}
    if gate_record is not None:
        selection["gfp_gate"] = gate_record
        warnings.extend(gate_warnings(gate_record))
    return {"metric": request.selection.metric, "unit": unit, "region": sources[0]["region_set"],
            "channel": channel, "source_fields": sources, "source_field_ledger": ledger,
            "observation_ledger": observation_ledger, "plot_data": selected,
            "field_summary": finite_records(fields), "sample_summary": finite_records(samples),
            "unit_summary": finite_records(units), "unit_ledger": unit_ledger, "pair_ledger": pairs,
            "selection": selection, "missingness": missing,
            "excluded_failed_fields": failed, "acquisition": acquisition, "warnings": warnings}


def _counts(prepared, conditions, paired=False):
    counts = []
    for condition in conditions:
        values = [r for r in prepared["unit_summary"] if r["condition"] == condition]
        unit_ledger = [r for r in prepared["unit_ledger"] if r["condition"] == condition]
        rows = [r for r in prepared["plot_data"] if r["condition"] == condition]
        fields = [r for r in prepared["source_field_ledger"] if r["condition"] == condition]
        counts.append({"condition": condition, "observations": len(rows), "input_fields": len(fields),
                       "selected_fields": len({r["field_id"] for r in rows}),
                       "samples": len({r["sample"] for r in rows}), "input_units": len(unit_ledger),
                       "experimental_units": len(values),
                       "explicitly_excluded_units": sum(r["status"] == "excluded" for r in unit_ledger),
                       "complete_pairs": len(values) if paired else None})
    return counts


def analyze_region_comparison(report, config, request, summaries=None, nuclear=None, shapes=None):
    """``summaries`` (field -> compartment-summary.json) is required only for a
    compartment-summary selection; region selections ignore it. ``shapes`` (field ->
    nucleus -> nucleolar shape) is required only for nucleolar eccentricity. ``nuclear`` is the
    bound adopted nuclear source for a GFP nucleus filter on a nucleoplasm revision
    (a nuclear revision is its own source)."""
    request = RegionComparisonRequestV2.model_validate(request)
    data = _prepared(report, config, request, summaries, nuclear, shapes)
    units = pd.DataFrame(data["unit_summary"])
    paired = request.design.kind == "paired"
    comparisons = []
    estimates = None
    for a, b in request.comparison_family.contrasts:
        aa, bb = units[units.condition == a], units[units.condition == b]
        if paired:
            joined = aa.set_index("pair")[["value"]].join(bb.set_index("pair")[["value"]],
                                                         how="outer", lsuffix="_a", rsuffix="_b")
            if joined.isna().any().any():
                raise ValueError("incomplete_pairs")
            va, vb = joined.value_a.to_numpy(), joined.value_b.to_numpy()
        else:
            va, vb = aa.value.to_numpy(), bb.value.to_numpy()
        if request.test != "none":
            comparisons.append({"group_a": a, "group_b": b, **compare_common_units(va, vb, request.test)})
        if request.estimates is not None:
            # The declared contrast [a, b] reports a − b: a is the treatment, b the control.
            estimates = comparison_estimates(
                vb, va, control_label=b, treatment_label=a, design=request.design.kind, test=request.test,
                metric=request.selection.metric, pairs=[str(pair) for pair in joined.index] if paired else None)
    apply_holm(comparisons, request.comparison_family.family_id)
    omnibus = (omnibus_common_units([units[units.condition == c].value.to_numpy() for c in request.conditions],
                                    request.omnibus) if request.omnibus else None)
    if omnibus:
        omnibus["conditions"] = list(request.conditions)
    counts = _counts(data, request.conditions, paired)
    # Unresolved nucleoli kept as missing (Q-05): the confirmed ledger and its warning travel with the result.
    missing = compartment_missing_summary(config, request.conditions)
    if missing is not None and missing["warnings"]:
        data["warnings"].append("compartment_missing_rate_differs")
    if request.test == "none":
        data["warnings"].append("descriptive_comparison_no_test_or_interval")
    elif any(row["experimental_units"] < 5 for row in counts):
        data["warnings"].append("few_independent_units_model_assumptions_and_power_require_review")
    # No invented mean CI for rank tests or omnibus. Raw unit values define plots.
    means = [{"condition": c, "mean": float(units[units.condition == c].value.mean()),
              "ci_low": None, "ci_high": None, "interval": "not requested"} for c in request.conditions]
    return RegionComparisonResultV2(
        inference_version=VERSION, revision_id=report["revision_id"], source_fingerprint=source_fingerprint(report, config),
        spec=request, comparisons=comparisons, means=means, counts=counts, omnibus=omnibus, estimates=estimates,
        compartment_missing=None if missing is None else CompartmentMissingSummary.model_validate(missing),
        method_settings={"test": request.test, "omnibus": request.omnibus, "correction": "Holm",
                         "family_id": request.comparison_family.family_id,
                         "family_size": len(comparisons), "contrast_policy": "all declared contrasts regardless of omnibus p",
                         "posthoc_label": "planned pairwise tests; neither Dunn nor Games–Howell",
                         "aggregation": request.aggregation}, **data).model_dump(mode="json")


def analyze_region_association(report, config, request, *, nuclear=None):
    request = RegionAssociationRequest.model_validate(request)
    if confirmed_policy(config) is not None:
        # Its result has no place for the missing-nucleoli ledger; the policy is for comparisons and descriptions.
        raise ValueError("compartment_missing_association_unsupported")
    # Reuse the exact source/design/acquisition review without fabricating tests.
    # All condition pairs are acquisition checks only; they do not produce p-values.
    contrasts = ([[a, b] for i, a in enumerate(request.conditions) for b in request.conditions[i + 1:]]
                 if request.scope == "pooled" else [])
    common = dict(design=request.design, conditions=request.conditions, acquisition_review=request.acquisition_review,
                  comparison_family=SimpleNamespace(contrasts=contrasts))
    x = _prepared(report, config, SimpleNamespace(selection=request.x_selection, **common), nuclear=nuclear)
    y = _prepared(report, config, SimpleNamespace(selection=request.y_selection, **common), nuclear=nuclear)
    if request.version == "1.1.0":
        def identity(source):
            return {(r["field_id"], r["region_id"]) for r in source["plot_data"]}
        if identity(x) != identity(y):
            raise ValueError("common_statistics_matched_observations_required")
    def by_unit(source):
        return {(r["condition"], r["experimental_unit"]): r for r in source["unit_summary"]}
    xx, yy = by_unit(x), by_unit(y)
    if set(xx) != set(yy):
        raise ValueError("common_statistics_unmatched_units")
    matched = [{"condition": c, "experimental_unit": uid, "x": xx[c, uid]["value"],
                "y": yy[c, uid]["value"]} for c, uid in sorted(xx)]
    ledger = []
    for row in x["unit_ledger"]:
        key = row["condition"], row["experimental_unit"]
        yrow = next(r for r in y["unit_ledger"] if (r["condition"], r["experimental_unit"]) == key)
        if row["status"] != yrow["status"]:
            raise ValueError("common_statistics_unmatched_units")
        ledger.append({"condition": key[0], "experimental_unit": key[1], "status": row["status"],
                       "x_selected_observations": row["selected_observations"],
                       "y_selected_observations": yrow["selected_observations"],
                       "field_ids": row["field_ids"], "excluded_fields": row["excluded_fields"]})
    scopes = request.conditions if request.scope == "per-condition" else ["pooled"]
    associations = []
    for scope in scopes:
        rows = [row for row in matched if request.scope == "pooled" or row["condition"] == scope]
        associations.append({"scope": scope, **correlate_common_units([r["x"] for r in rows],
                                                                      [r["y"] for r in rows], request.method)})
    apply_holm(associations, "declared-association-scopes")
    warnings = sorted(set(x["warnings"] + y["warnings"]))
    warnings.append("association_does_not_establish_causation_no_regression_or_batch_adjustment")
    if request.scope == "pooled":
        warnings.append("pooled_association_may_reflect_condition_or_acquisition_batch_confounding")
    missingness = [{"axis": axis, **row} for axis, source in (("x", x), ("y", y)) for row in source["missingness"]]
    return RegionAssociationResult(
        region_association_version=request.version,
        inference_version=VERSION, revision_id=report["revision_id"], source_fingerprint=source_fingerprint(report, config),
        spec=request, x_source=x, y_source=y, unit_summary=matched, unit_ledger=ledger, associations=associations,
        counts=[{"condition": c, "matched_units": sum(r["condition"] == c for r in matched),
                 "unmatched_units": 0, "excluded_units": sum(r["condition"] == c and r["status"] == "excluded" for r in ledger)}
                for c in request.conditions], missingness=missingness, warnings=warnings).model_dump(mode="json")
