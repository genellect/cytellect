"""Immutable experimental metadata changes, separate from image/mask identity."""
from __future__ import annotations

from copy import deepcopy

from .region_contracts import RegionMetadataChange, RegionMetadataEdit


def region_metadata_child_config(parent, edit: RegionMetadataEdit) -> dict:
    """Change only recorded metadata; the source revision and pixels stay intact."""
    config = deepcopy(parent["config"])
    snapshot = config["field_snapshot"]
    if not set(edit.fields).issubset(snapshot):
        raise ValueError("unknown_region_metadata_field")
    for key in ("region_edit", "region_metadata_edit", "review_record"):
        config.pop(key, None)
    updates = edit.model_dump(mode="json")["fields"]
    for fid, metadata in updates.items():
        snapshot[fid]["metadata"] = metadata
    config["reuse_revision"] = parent["id"]
    config["region_metadata_edit"] = {
        "version": edit.version, "source_revision_id": parent["id"], "fields": updates,
    }
    return config


def validate_region_reuse(parent, config: dict, recipe: dict) -> None:
    """A metadata child may change named metadata only, never source images."""
    previous = parent["config"]["field_snapshot"]
    current = config["field_snapshot"]
    if not set(previous).issubset(current):
        raise ValueError("region_parent_fields_must_be_retained")
    if parent["config"]["recipe"] != recipe:
        raise ValueError("region_parent_definition_changed")
    changes = config.get("region_metadata_edit")
    updates = {}
    if changes is not None:
        edit = RegionMetadataChange.model_validate(changes)
        if edit.source_revision_id != parent["id"] or not set(edit.fields).issubset(previous):
            raise ValueError("region_metadata_source_mismatch")
        updates = edit.model_dump(mode="json")["fields"]
    for fid, source in previous.items():
        expected = {**source, "metadata": updates[fid]} if fid in updates else source
        if expected != current[fid]:
            raise ValueError("region_parent_definition_changed")
