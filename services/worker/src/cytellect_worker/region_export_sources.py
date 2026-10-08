"""Collect owned, hash-bound dependency masks without including original images."""
import numpy as np
from cytellect_analysis.images import sha256
from cytellect_analysis.region_contracts import region_report_from_json, validate_region_report_policy
from cytellect_api.db import revisions
from cytellect_api.storage import read_json

from .compartment_sources import load_compartment_summaries


def collect_dependencies(store, revision, report, provenance):
    if revision["config"].get("recipe", {}).get("source") not in {"fiji_nuclear_compartment", "cellpose_cell"}:
        return {}
    recipe = revision["config"]["recipe"]
    summaries = (load_compartment_summaries(store, revision, report)
                 if recipe.get("compartment") == "nucleoplasm" and recipe.get("nucleolar_revision_id") else {})
    dependencies = {}
    for fid in report["field_tables"]:
        identities = provenance["fields"][fid]
        entry = {}
        for kind in ("nuclear", "nucleolar"):
            identity = identities.get(kind + "_source")
            if kind == "nucleolar" and fid in summaries:
                identity = summaries[fid]["nucleolar_revision"]
            if identity is None:
                continue
            source = store.one(revisions, id=identity["revision_id"])
            if (not source or source["workspace_id"] != revision["workspace_id"]
                    or source["state"] != "succeeded" or not source["result_dir"]):
                raise ValueError("region_bundle_parent_identity_mismatch")
            root = store.safe_path(source["result_dir"])
            path = root / "measurements.json"
            source_report = read_json(path)
            validate_region_report_policy(region_report_from_json(path.read_text(encoding="utf-8")), source["config"])
            mask = source_report["field_masks"][fid]
            labels_path = store.safe_path(root, fid, "labels.npy")
            if (labels_path.is_symlink() or mask["mask_sha256"] != identity["mask_sha256"]
                    or mask["mask_revision_id"] != identity["mask_revision_id"]
                    or sha256(labels_path) != mask["file"]["sha256"]
                    or labels_path.stat().st_size != mask["file"]["bytes"]
                    or [item for item in source_report["exclusions"] if item["field_id"] == fid] != identity["exclusions"]):
                raise ValueError("region_bundle_parent_identity_mismatch")
            entry[kind] = {"identity": identity}
            if kind == "nuclear":
                entry[kind].update(config=source["config"], report=source_report, report_sha256=sha256(path))
            entry[kind + "_labels"] = np.load(labels_path, allow_pickle=False)
        if fid in summaries:
            entry["summary"] = summaries[fid]
        dependencies[fid] = entry
    return dependencies
