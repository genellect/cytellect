"""Nucleus table 1.0.0: every channel and the adopted nucleoli of each nucleus, read-only.

The API joins what the worker already measured and saved (rows and label images);
the browser never computes these values.
"""
import json
from typing import Annotated

import numpy as np
from cytellect_analysis.nucleus_table import NucleusTable, nucleus_table
from cytellect_analysis.region_contracts import region_report_from_json, validate_region_report_policy
from cytellect_analysis.regions import _array_hash
from fastapi import Depends, HTTPException, Query

from .regions import is_region
from .storage import read_json


def _saved_field(root, rev, field_id):
    """The strictly parsed saved table, mask record and hash-checked labels of one field."""
    report = region_report_from_json(json.dumps(read_json(root / "measurements.json")))
    validate_region_report_policy(report, rev["config"])
    table, mask = report.field_tables.get(field_id), report.field_masks.get(field_id)
    path = root / field_id / "labels.npy"
    if table is None or mask is None or not path.is_file():
        raise HTTPException(409, "field_not_measured")
    labels = np.load(path, allow_pickle=False)
    if not isinstance(labels, np.ndarray) or labels.ndim != 2 or _array_hash(labels, "<u4") != mask.mask_sha256:
        raise HTTPException(409, "nucleus_table_mask_mismatch")
    exclusions = [item.model_dump(mode="json") for item in report.exclusions if item.field_id == field_id]
    return table, mask, labels, exclusions


def register_nucleus_table_routes(api, owner, revision, result_root):
    Owner = Annotated[str, Depends(owner)]

    def measured(rid, who):
        rev = revision(rid, who)
        if not is_region(rev):
            raise HTTPException(409, "region_analysis_required")
        if rev["state"] != "succeeded" or not rev["result_dir"]:
            raise HTTPException(409, "revision_not_succeeded")
        return rev

    @api.get("/v1/revisions/{rid}/nucleus-table", response_model=NucleusTable)
    def get_nucleus_table(rid: str, field_id: str, who: Owner,
                          nucleolar_revision_id: Annotated[str | None, Query()] = None):
        """One row per nucleus of a nuclear revision; with `nucleolar_revision_id`, the
        nucleolar revision built on it adds each nucleus's adopted nucleoli."""
        rev = measured(rid, who)
        if field_id not in rev["config"].get("field_ids", []):
            raise HTTPException(404, "field_not_found")
        table, mask, labels, exclusions = _saved_field(result_root(rev), rev, field_id)
        nucleoli = states = source = None
        if nucleolar_revision_id is not None:
            child = measured(nucleolar_revision_id, who)
            recipe = child["config"].get("recipe", {})
            if (child["workspace_id"] != rev["workspace_id"] or recipe.get("compartment") != "nucleoli"
                    or recipe.get("nuclear_revision_id") != rid):
                raise HTTPException(422, "nucleus_table_nucleolar_source_invalid")
            root = result_root(child)
            _, child_mask, nucleoli, child_exclusions = _saved_field(root, child, field_id)
            nucleoli = nucleoli.copy()
            nucleoli[np.isin(nucleoli, [item["region_id"] for item in child_exclusions
                                        if item["region_id"] is not None])] = 0
            engine = read_json(root / "provenance.json").get("fields", {}).get(field_id, {}).get("detector", {}).get("engine", {})
            states = engine.get("nucleolar_states") or {}
            source = {"revision_id": child["id"], "mask_revision_id": child_mask.mask_revision_id,
                      "mask_sha256": child_mask.mask_sha256}
        try:
            return nucleus_table(
                field_id=field_id, nuclear_revision_id=rid, nuclear_mask=mask.model_dump(mode="json"),
                nuclear_table=table, nuclear_labels=labels, exclusions=exclusions,
                nuclear_channel_id=rev["config"].get("recipe", {}).get("defining_channel_id"),
                nucleoli=nucleoli, nucleolar_states=states, nucleolar_source=source)
        except ValueError as exc:
            raise HTTPException(409, str(exc) if str(exc).startswith(("nucleus_table_", "nucleolus_")) else "nucleus_table_invalid") from None
