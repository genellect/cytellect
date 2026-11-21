"""Region features of one measured field for the image table (region-features/1.0.0, #257 A-4, RP-03).

Read-only: the values are computed by the analysis package from the field's hash-checked saved labels and, for a
channel, its hash-checked original channel array, exactly as statistics compute them. Nothing is stored.
"""
from typing import Annotated, Any

import numpy as np
from cytellect_analysis.images import sha256
from cytellect_analysis.region_contracts import RegionImageInfo
from cytellect_analysis.region_features import SHAPE_METRICS, SIGNAL_METRICS, compute_features
from cytellect_analysis.region_shape import MINIMUM_AREA_PX
from cytellect_analysis.regions import RegionModel
from fastapi import Depends, HTTPException, Query
from pydantic import Field

from .nucleus_tables import _saved_field
from .regions import is_region


class RegionFeatureValue(RegionModel):
    value: float | None
    missing_reason: str | None


class RegionFeatureRow(RegionModel):
    region_id: Annotated[int, Field(ge=1)]
    area_px: Annotated[int, Field(ge=1)]
    excluded: bool
    values: dict[str, RegionFeatureValue]


class RegionFeatureTable(RegionModel):
    protocol: str
    field_id: str
    region_set_id: str
    mask_revision_id: str
    channel_id: str | None
    minimum_area_px: int
    metrics: list[str]
    thresholds: dict[str, Any]
    rows: list[RegionFeatureRow]


def register_region_feature_routes(api, store, owner, revision, result_root):
    Owner = Annotated[str, Depends(owner)]

    @api.get("/v1/revisions/{rid}/region-features", response_model=RegionFeatureTable)
    def get_region_features(rid: str, field_id: str, who: Owner,
                            channel_id: Annotated[str | None, Query()] = None):
        """Solidity, axis ratio and eccentricity of every region of one measured field; with `channel_id`, also the
        pixel CV (raw and, with an established automatic background, corrected) and positive-area fraction."""
        rev = revision(rid, who)
        if not is_region(rev):
            raise HTTPException(409, "region_analysis_required")
        if rev["state"] != "succeeded" or not rev["result_dir"]:
            raise HTTPException(409, "revision_not_succeeded")
        if field_id not in rev["config"].get("field_ids", []):
            raise HTTPException(404, "field_not_found")
        root = result_root(rev)
        table, mask, labels, exclusions = _saved_field(root, rev, field_id)
        measurement = rev["config"].get("measurement") or {}
        metrics = list(SHAPE_METRICS)
        image = None
        if channel_id is not None:
            if measurement.get("mode") not in ("raw_intensity", "automatic_background"):
                raise HTTPException(422, "region_metric_not_measured")
            info = RegionImageInfo.model_validate(rev["config"]["field_snapshot"][field_id]["image_info"])
            record = info.channel_arrays.get(channel_id)
            if record is None:
                raise HTTPException(404, "channel_not_found")
            path = store.safe_path("workspaces", rev["workspace_id"], "fields", field_id, f"channel-{channel_id}.npy")
            if (not path.is_file() or path.stat().st_size != record.bytes
                    or sha256(path) != record.sha256):
                raise HTTPException(409, "region_input_file_hash_mismatch")
            image = np.load(path, allow_pickle=False)
            metrics += [metric for metric in SIGNAL_METRICS
                        if metric != "cv_corrected" or measurement.get("mode") == "automatic_background"]
        report = {"field_tables": {field_id: table.model_dump(mode="json")}, "exclusions": exclusions}
        try:
            features = compute_features({(metric, None if metric in SHAPE_METRICS else channel_id) for metric in metrics},
                                        report, lambda _: labels, lambda _fid, _channel: image)
        except ValueError as exc:
            raise HTTPException(409, str(exc) if str(exc).startswith("region_") else "region_features_invalid") from None
        assert features is not None
        excluded = {int(item["region_id"]) for item in exclusions if item.get("region_id") is not None}
        whole = any(item.get("region_id") is None for item in exclusions)
        shape = features["solidity", None][field_id]["values"]
        rows = []
        for region_id in sorted(shape):
            values = {metric: features[metric, None if metric in SHAPE_METRICS else channel_id][field_id]["values"][region_id]
                      for metric in metrics}
            rows.append({"region_id": region_id, "area_px": shape[region_id]["area_px"],
                         "excluded": whole or region_id in excluded,
                         "values": {metric: {"value": value["value"], "missing_reason": value["missing_reason"]}
                                    for metric, value in values.items()}})
        thresholds = {}
        if channel_id is not None:
            thresholds["positive_area_fraction"] = features["positive_area_fraction", channel_id][field_id]["threshold"]
        return {"protocol": "region-features/1.0.0", "field_id": field_id, "region_set_id": mask.region_set_id,
                "mask_revision_id": mask.mask_revision_id, "channel_id": channel_id, "minimum_area_px": MINIMUM_AREA_PX,
                "metrics": metrics, "thresholds": thresholds, "rows": rows}

