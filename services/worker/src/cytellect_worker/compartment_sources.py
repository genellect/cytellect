"""Locate each field's saved compartment-summary.json for a reviewed nucleoplasm revision.

The summary is written next to the nucleoplasm labels by the revision that derived
the mask from adopted nucleoli. A child revision (metadata, background, review)
reuses that mask, so the summary is read from the mask's origin revision and bound
to it by the canonical mask hash recorded in this revision's report.
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
        origin = rev if mask["mask_revision_id"] == rev["id"] else store.one(revisions, id=mask["mask_revision_id"])
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
