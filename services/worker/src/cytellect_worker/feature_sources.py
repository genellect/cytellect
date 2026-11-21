"""Region shape and pixel-signal values (region-features/1.0.0) for one reviewed region revision.

Each field's values are recomputed from its adopted label image (bound to the report's mask identity) and, for
pixel-signal metrics, the field's original channel array (bound to the snapshot's file record). Nothing is stored:
the analysis package binds the values to the measured regions by identity and pixel area.
"""
import numpy as np
from cytellect_analysis.masks import validate_label_array
from cytellect_analysis.region_contracts import RegionImageInfo
from cytellect_analysis.region_features import compute_features, selections_of
from cytellect_analysis.regions import _array_hash
from cytellect_api.db import revisions

from .regions import _load_array


def load_region_features(store, rev, report, specs):
    """(metric, channel ID) -> field -> record for every shape or pixel-signal selection in ``specs``."""
    keys = set().union(*(selections_of(spec) for spec in specs)) if specs else set()
    if not keys:
        return None
    snapshot = rev["config"].get("field_snapshot", {})

    def labels_of(fid):
        mask = report.get("field_masks", {}).get(fid)
        origin = store.one(revisions, id=mask["mask_revision_id"]) if mask else None
        if (origin is None or origin["workspace_id"] != rev["workspace_id"] or origin["state"] != "succeeded"
                or not origin["result_dir"]):
            raise ValueError("region_features_unavailable")
        path = store.safe_path(origin["result_dir"], fid, "labels.npy")
        if path.is_symlink() or not path.is_file():
            raise ValueError("region_features_unavailable")
        labels = np.load(path, allow_pickle=False)
        validate_label_array(labels)
        if list(labels.shape) != mask["shape"] or _array_hash(labels, "<u4") != mask["mask_sha256"]:
            raise ValueError("region_features_mismatch")
        return labels

    def channel_of(fid, channel_id):
        if fid not in snapshot:
            raise ValueError("region_features_unavailable")
        record = RegionImageInfo.model_validate(snapshot[fid]["image_info"]).channel_arrays.get(channel_id)
        if record is None:
            raise ValueError("region_features_unavailable")
        folder = store.safe_path("workspaces", rev["workspace_id"], "fields", fid)
        return _load_array(folder / f"channel-{channel_id}.npy", record)

    return compute_features(keys, report, labels_of, channel_of)
