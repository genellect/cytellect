"""Rebind measurement revisions only when their adopted detection masks are identical."""
from copy import deepcopy

from .db import revisions
from .storage import read_json


def _inputs(info):
    value = deepcopy(info)
    for channel in value.get("channels", []):
        # Confirming an existing background/channel association does not change pixels.
        channel.pop("identity_confirmed", None)
        channel.pop("identity_source", None)
    return value


def same_mask_dependency(store, before_id, after_id, workspace_id, field_ids, expected_target):
    """Fail closed on changed inputs, detector settings, edits, exclusions or missing outputs."""
    before = store.one(revisions, id=before_id)
    after = store.one(revisions, id=after_id)
    if any(not row or row["workspace_id"] != workspace_id or row["state"] != "succeeded"
           or not row["result_dir"] for row in (before, after)):
        return False
    old_recipe, new_recipe = before["config"]["recipe"], after["config"]["recipe"]
    expected_source = "stardist_nuclear" if expected_target == "nuclei" else "fiji_nuclear_compartment"
    if any(recipe.get("source") != expected_source or recipe.get("region_set_id") != expected_target
           for recipe in (old_recipe, new_recipe)):
        return False
    if old_recipe != new_recipe and not can_rebind_compartment(
        store, old_recipe, new_recipe, workspace_id, field_ids
    ):
        return False
    try:
        reports = [read_json(store.safe_path(row["result_dir"], "measurements.json")) for row in (before, after)]
        for fid in field_ids:
            snapshots = [row["config"].get("field_snapshot", {}).get(fid) for row in (before, after)]
            if any(snapshot is None for snapshot in snapshots):
                return False
            if _inputs(snapshots[0]["image_info"]) != _inputs(snapshots[1]["image_info"]):
                return False
            masks = [report.get("field_masks", {}).get(fid) for report in reports]
            if any(not mask or fid not in report.get("field_tables", {}) for mask, report in zip(masks, reports)):
                return False
            keys = ("mask_revision_id", "mask_sha256", "shape", "region_set_id", "source", "file")
            if any(masks[0].get(key) is None or masks[0].get(key) != masks[1].get(key) for key in keys):
                return False
            exclusions = [[item for item in report["exclusions"] if item["field_id"] == fid] for report in reports]
            if exclusions[0] != exclusions[1]:
                return False
        return True
    except (OSError, ValueError, KeyError, TypeError):
        return False


def can_rebind_compartment(store, previous, requested, workspace_id, field_ids):
    """A changed parent measurement is not a changed segmentation.

    This is not recipe equivalence: callers must still create a new measurement
    with current parent references and independently verify the saved label files.
    """
    if previous.get("source") != "fiji_nuclear_compartment" or requested.get("source") != previous.get("source"):
        return False
    references = ("nuclear_revision_id", "nucleolar_revision_id")
    if ({key: value for key, value in previous.items() if key not in references}
            != {key: value for key, value in requested.items() if key not in references}):
        return False
    for key, target in (("nuclear_revision_id", "nuclei"), ("nucleolar_revision_id", "nucleoli")):
        old, new = previous.get(key), requested.get(key)
        if old == new:
            continue
        if not old or not new or not same_mask_dependency(store, old, new, workspace_id, field_ids, target):
            return False
    return True
