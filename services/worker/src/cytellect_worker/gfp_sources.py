"""Bind a GFP nucleus filter (1.0.0) to the adopted nuclear revision rows of the same fields.

A nuclear (``stardist_nuclear``) revision is its own GFP source and needs nothing
here. A nucleoplasm revision records, per field, the nuclear revision, mask
revision and canonical mask hash it was derived from (``nuclear_source`` in its
provenance); the nuclear report must still hold exactly that mask and the same
nucleus exclusions, so nucleoplasm region / parent-nucleus IDs denote the same
nuclei. Any other source, or any disagreement, is refused with a safe code.
"""
from cytellect_analysis.gfp_selection import binding_kind
from cytellect_analysis.images import sha256
from cytellect_api.db import revisions
from cytellect_api.storage import read_json


def load_gfp_nuclear_source(store, rev, report):
    if binding_kind(rev["config"].get("recipe")) == "same_revision":
        return None
    provenance = read_json(store.safe_path(rev["result_dir"], "provenance.json"))
    loaded: dict = {}
    fields = {}
    for fid in sorted(report["field_tables"]):
        source = (provenance.get("fields", {}).get(fid) or {}).get("nuclear_source")
        if not isinstance(source, dict) or not isinstance(source.get("revision_id"), str):
            raise ValueError("gfp_gate_nuclear_source_unbound")
        rid = source["revision_id"]
        if rid not in loaded:
            nuclear = store.one(revisions, id=rid)
            if (nuclear is None or nuclear["workspace_id"] != rev["workspace_id"] or nuclear["state"] != "succeeded"
                    or not nuclear["result_dir"] or nuclear["config"].get("analysis_kind") != "region-2d"
                    or nuclear["config"].get("recipe", {}).get("source") != "stardist_nuclear"):
                raise ValueError("gfp_gate_nuclear_source_unbound")
            path = store.safe_path(nuclear["result_dir"], "measurements.json")
            if path.is_symlink() or not path.is_file():
                raise ValueError("gfp_gate_nuclear_source_unbound")
            loaded[rid] = (nuclear, read_json(path), sha256(path))
        nuclear, nuclear_report, digest = loaded[rid]
        mask = nuclear_report.get("field_masks", {}).get(fid)
        table = nuclear_report.get("field_tables", {}).get(fid)
        original = nuclear["config"].get("field_snapshot", {}).get(fid)
        exclusions = [item for item in nuclear_report.get("exclusions", []) if item.get("field_id") == fid]
        if (not mask or table is None or original is None
                or mask.get("mask_revision_id") != source.get("mask_revision_id")
                or mask.get("mask_sha256") != source.get("mask_sha256")
                or exclusions != source.get("exclusions")):
            raise ValueError("gfp_gate_nuclear_identity_mismatch")
        fields[fid] = {"revision_id": rid, "report_sha256": digest, "table": table,
                       "mask_revision_id": mask["mask_revision_id"], "mask_sha256": mask["mask_sha256"],
                       "exclusions": exclusions, "image_info": original.get("image_info")}
    return {"binding": "parent_nucleus", "fields": fields}
