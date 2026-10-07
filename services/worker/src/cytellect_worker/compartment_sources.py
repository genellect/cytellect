"""Locate each field's saved compartment-summary.json for a reviewed nucleoplasm revision.

The current measurement's summary is preferred: background remeasurement keeps
the mask but changes corrected summaries and dependency references. Historical
raw-only children may fall back to the mask origin after verifying mask identity.
"""
import numpy as np
from cytellect_analysis.compartment_observations import require_compartment_source
from cytellect_analysis.masks import validate_label_array
from cytellect_analysis.regions import _array_hash
from cytellect_api.db import revisions
from cytellect_api.storage import read_json


def load_compartment_summaries(store, rev, report):
    recipe = rev["config"].get("recipe", {})
    require_compartment_source(recipe, recipe.get("region_set_id"))
    summaries = {}
    for fid in sorted(report["field_tables"]):
        mask = report.get("field_masks", {}).get(fid)
        if not mask:
            raise ValueError("compartment_summary_unavailable")
        current_summary = store.safe_path(rev["result_dir"], fid, "compartment-summary.json")
        origin = rev if current_summary.is_file() else store.one(revisions, id=mask["mask_revision_id"])
        if (not current_summary.is_file()
                and (rev["config"].get("measurement") or {}).get("mode") == "automatic_background"):
            raise ValueError("compartment_summary_unavailable")
        if (origin is None or origin["workspace_id"] != rev["workspace_id"] or origin["state"] != "succeeded"
                or not origin["result_dir"]):
            raise ValueError("compartment_summary_unavailable")
        # The origin must itself derive nucleoplasm from adopted nucleoli; its summary
        # records which nucleolar revision, and the mask hash binds it to this report.
        require_compartment_source(origin["config"].get("recipe"), recipe.get("region_set_id"))
        folder = store.safe_path(origin["result_dir"], fid)
        labels_path, summary_path = folder / "labels.npy", folder / "compartment-summary.json"
        if any(path.is_symlink() or not path.is_file() for path in (labels_path, summary_path)):
            raise ValueError("compartment_summary_unavailable")
        labels = np.load(labels_path, allow_pickle=False)
        validate_label_array(labels)
        if list(labels.shape) != mask["shape"] or _array_hash(labels, "<u4") != mask["mask_sha256"]:
            raise ValueError("compartment_summary_mask_mismatch")
        summaries[fid] = read_json(summary_path)
    return summaries
