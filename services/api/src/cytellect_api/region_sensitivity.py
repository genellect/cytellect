"""Server-side revision state checks around the pure region comparison contract."""
from cytellect_analysis.region_sensitivity import (
    DEFINITION_KEYS as DEFINITION_KEYS,
)
from cytellect_analysis.region_sensitivity import (
    validate_region_configs,
    validate_region_masks,
    validate_region_reports,
)

from .storage import read_json


def validate_region_revision(store, primary, alternative, *, check_masks=False):
    if primary["id"] == alternative["id"]:
        raise ValueError("region_sensitivity_requires_alternate_revision")
    if primary["workspace_id"] != alternative["workspace_id"]:
        raise ValueError("region_sensitivity_workspace_mismatch")
    for revision in (primary, alternative):
        if revision["state"] != "succeeded" or not revision["reviewed"] or not revision["result_dir"]:
            raise ValueError("region_sensitivity_review_required")
    validate_region_configs(primary["config"], alternative["config"])
    reports = []
    for revision in (primary, alternative):
        report = read_json(store.safe_path(revision["result_dir"], "measurements.json"))
        validate_region_reports({**revision["config"], "review_record": revision["review_record"] or {}}, report)
        reports.append(report)
    versions = [{row.get("measurement_protocol_version") for row in report["cells"]} for report in reports]
    if versions[0] != versions[1]:
        raise ValueError("region_sensitivity_measurement_protocol_differs")
    if check_masks:
        validate_region_masks(store.safe_path(primary["result_dir"]), store.safe_path(alternative["result_dir"]),
                              primary["config"]["field_ids"])
    return reports[1]
