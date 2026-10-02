"""Require like-for-like reviewed native region alternatives before comparison."""
import numpy as np

from cytellect_analysis.review import unresolved_nucleolar_failures

DEFINITION_KEYS = frozenset({"nucleolar_method", "smoothing_sigma_px", "minimum_area_px",
                             "split_touching", "dapi_low_percentile"})


def validate_region_configs(primary, alternative):
    """Pure compatibility contract, also usable by offline replay."""
    main_recipe, alt_recipe = primary["recipe"], alternative["recipe"]
    if main_recipe.get("id") != "ncl-native-2d" or alt_recipe.get("id") != "ncl-native-2d":
        raise ValueError("region_sensitivity_requires_native_ncl")
    if set(primary["field_ids"]) != set(alternative["field_ids"]):
        raise ValueError("region_sensitivity_fields_differ")
    if primary["field_snapshot"] != alternative["field_snapshot"]:
        raise ValueError("region_sensitivity_inputs_or_metadata_differ")
    if primary.get("backgrounds", {}) != alternative.get("backgrounds", {}):
        raise ValueError("region_sensitivity_backgrounds_differ")
    # Exclusion order has no scientific meaning, but reasons and target IDs do.
    def normalize(config):
        return sorted((entry["field_id"], entry.get("nucleus_id") or 0, entry["reason"])
                      for entry in config.get("exclusions", []))
    if normalize(primary) != normalize(alternative):
        raise ValueError("region_sensitivity_exclusions_differ")
    if ({key: value for key, value in main_recipe.items() if key not in DEFINITION_KEYS}
            != {key: value for key, value in alt_recipe.items() if key not in DEFINITION_KEYS}):
        raise ValueError("region_sensitivity_nonregion_parameters_differ")


def validate_region_reports(config, report):
    """No failed fields, unresolved mask reviews or unresolved candidate failures."""
    accepted = set(config.get("review_record", {}).get("accepted_invalidated_fields", []))
    if (report.get("field_failures") or report.get("excluded_failed_fields")
            or set(report.get("invalidated_nucleoli", [])) - accepted):
        raise ValueError("region_sensitivity_complete_reviewed_masks_required")
    if unresolved_nucleolar_failures(report, config):
        raise ValueError("nucleolar_processing_failed")


def validate_region_masks(primary_root, alternative_root, field_ids, *, filename="masks.npz"):
    """Original-coordinate nucleus/manual masks must be identical, not just counts."""
    for fid in field_ids:
        try:
            with np.load(primary_root / fid / filename, allow_pickle=False) as primary:
                with np.load(alternative_root / fid / filename, allow_pickle=False) as alternative:
                    for layer in ("nuclei", "manual"):
                        if not np.array_equal(primary[layer], alternative[layer]):
                            raise ValueError("region_sensitivity_nuclear_or_manual_masks_differ")
        except (OSError, KeyError):
            raise ValueError("region_sensitivity_complete_reviewed_masks_required") from None
