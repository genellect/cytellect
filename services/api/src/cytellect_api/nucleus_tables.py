"""Nucleus table 1.0.0: every channel and the confirmed nucleoli of each nucleus, read-only.

The API joins what the worker already measured and saved (rows and label images);
the browser never computes these values. The CSV download is the same table.
"""
import io
import json
import zipfile
from typing import Annotated

import numpy as np
from cytellect_analysis.nucleus_table import NucleusTable, nucleus_table, nucleus_table_files
from cytellect_analysis.region_contracts import region_report_from_json, validate_region_report_policy
from cytellect_analysis.regions import _array_hash
from fastapi import Depends, HTTPException, Query, Response

from .regions import is_region
from .storage import read_json
from .workspace_runs import adopted_for
from .workspace_selection import selection_at


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


def register_nucleus_table_routes(api, store, owner, revision, result_root):
    Owner = Annotated[str, Depends(owner)]

    def measured(rid, who):
        rev = revision(rid, who)
        if not is_region(rev):
            raise HTTPException(409, "region_analysis_required")
        if rev["state"] != "succeeded" or not rev["result_dir"]:
            raise HTTPException(409, "revision_not_succeeded")
        return rev

    def build(rid, field_id, who, nucleolar_revision_id):
        rev = measured(rid, who)
        recipe = rev["config"].get("recipe", {})
        # Only detected nuclei with a confirmed nuclear stain are nuclei; another region set
        # (cells, positive regions, compartments, drawn regions) is never read as nuclei here.
        if recipe.get("source") != "stardist_nuclear" or not recipe.get("defining_channel_id"):
            raise HTTPException(422, "nucleus_table_nuclear_source_required")
        if field_id not in rev["config"].get("field_ids", []):
            raise HTTPException(404, "field_not_found")
        table, mask, labels, exclusions = _saved_field(result_root(rev), rev, field_id)
        with store.transaction() as conn:
            adopted = adopted_for(conn, rev["workspace_id"], field_id, selection_at(conn, rev["workspace_id"]))
        nucleoli = states = source = None
        child_exclusions: list = []
        if nucleolar_revision_id is not None:
            child = measured(nucleolar_revision_id, who)
            child_recipe = child["config"].get("recipe", {})
            if (child["workspace_id"] != rev["workspace_id"] or child_recipe.get("source") != "fiji_nuclear_compartment"
                    or child_recipe.get("compartment") != "nucleoli" or child_recipe.get("nuclear_revision_id") != rid
                    or field_id not in child["config"].get("field_ids", [])):
                raise HTTPException(422, "nucleus_table_nucleolar_source_invalid")
            root = result_root(child)
            _, child_mask, nucleoli, child_exclusions = _saved_field(root, child, field_id)
            record = read_json(root / "provenance.json").get("fields", {}).get(field_id, {})
            pinned = record.get("nuclear_source") or {}
            # The nucleoli must have been derived from exactly these saved nuclei.
            if pinned.get("revision_id") != rid or pinned.get("mask_sha256") != mask.mask_sha256:
                raise HTTPException(409, "nucleus_table_nucleolar_source_mismatch")
            states = (record.get("detector") or {}).get("engine", {}).get("nucleolar_states") or {}
            source = {"revision_id": child["id"], "mask_revision_id": child_mask.mask_revision_id,
                      "mask_sha256": child_mask.mask_sha256,
                      "adopted": adopted.get("nucleoli", {}).get("id") == child["id"]}
        try:
            return nucleus_table(
                field_id=field_id, nuclear_revision_id=rid, nuclear_mask=mask.model_dump(mode="json"),
                nuclear_table=table, nuclear_labels=labels, exclusions=exclusions,
                nuclear_channel_id=recipe["defining_channel_id"],
                nuclear_adopted=adopted.get("nuclei", {}).get("id") == rid,
                nucleoli=nucleoli, nucleolar_states=states, nucleolar_exclusions=child_exclusions,
                nucleolar_source=source)
        except ValueError as exc:
            code = str(exc)
            raise HTTPException(409, code if code.startswith(("nucleus_table_", "nucleolus_", "nucleolar_"))
                                else "nucleus_table_invalid") from None

    @api.get("/v1/revisions/{rid}/nucleus-table", response_model=NucleusTable)
    def get_nucleus_table(rid: str, field_id: str, who: Owner,
                          nucleolar_revision_id: Annotated[str | None, Query()] = None):
        """One row per nucleus of a nuclear revision; with `nucleolar_revision_id`, the
        nucleolar revision built on it adds each nucleus's confirmed nucleoli."""
        return build(rid, field_id, who, nucleolar_revision_id)

    @api.get("/v1/revisions/{rid}/nucleus-table.zip", response_class=Response,
             responses={200: {"content": {"application/zip": {}}}})
    def download_nucleus_table(rid: str, field_id: str, who: Owner,
                               nucleolar_revision_id: Annotated[str | None, Query()] = None):
        """The same table as `nucleus-table.csv`, `columns.csv` (units and definitions) and JSON."""
        table = build(rid, field_id, who, nucleolar_revision_id)
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, data in nucleus_table_files(table).items():
                archive.writestr(zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0)), data)
        filename = f"nucleus-table-{field_id}.zip"
        return Response(buffer.getvalue(), media_type="application/zip",
                        headers={"Content-Disposition": f'attachment; filename="{filename}"'})
