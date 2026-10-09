"""Immutable experimental metadata changes, separate from image/mask identity."""
from __future__ import annotations

from copy import deepcopy

from .region_contracts import RegionMetadataChange, RegionMetadataEdit

CHANNEL_ANNOTATIONS = frozenset({"label", "stain", "identity_source", "identity_confirmed"})


def channel_pixel_identity(channel: dict) -> dict:
    """Names/evidence can be corrected; channel IDs and acquisition facts cannot."""
    return {key: value for key, value in channel.items() if key not in CHANNEL_ANNOTATIONS}


def image_pixel_identity(info: dict) -> dict:
    value = deepcopy(info)
    value["channels"] = [channel_pixel_identity(channel) for channel in value.get("channels", [])]
    return value


def region_metadata_child_config(parent, edit: RegionMetadataEdit) -> dict:
    """Change only recorded metadata; the source revision and pixels stay intact."""
    config = deepcopy(parent["config"])
    snapshot = config["field_snapshot"]
    if not set(edit.fields).issubset(snapshot):
        raise ValueError("unknown_region_metadata_field")
    for key in ("region_edit", "region_metadata_edit", "channel_annotation_edit", "review_record"):
        config.pop(key, None)
    updates = edit.model_dump(mode="json")["fields"]
    for fid, metadata in updates.items():
        snapshot[fid]["metadata"] = metadata
    config["reuse_revision"] = parent["id"]
    config["region_metadata_edit"] = {
        "version": edit.version, "source_revision_id": parent["id"], "fields": updates,
    }
    return config


def validate_region_reuse(parent, config: dict, recipe: dict, *, verified_dependency_rebind=False) -> None:
    """A metadata child may change named metadata only, never source images."""
    previous = parent["config"]["field_snapshot"]
    current = config["field_snapshot"]
    if not set(previous).issubset(current):
        raise ValueError("region_parent_fields_must_be_retained")
    if parent["config"]["recipe"] != recipe and not verified_dependency_rebind:
        raise ValueError("region_parent_definition_changed")
    changes = config.get("region_metadata_edit")
    updates = {}
    if changes is not None:
        edit = RegionMetadataChange.model_validate(changes)
        if edit.source_revision_id != parent["id"] or not set(edit.fields).issubset(previous):
            raise ValueError("region_metadata_source_mismatch")
        updates = edit.model_dump(mode="json")["fields"]
    annotations = config.get("channel_annotation_edit")
    if annotations is not None:
        if (not isinstance(annotations, dict) or annotations.get("version") != "1.0.0"
                or annotations.get("source_revision_id") != parent["id"]
                or not isinstance(annotations.get("fields"), dict)
                or set(annotations["fields"]) - set(previous)
                or any(not isinstance(channels, list) or not all(isinstance(channel, dict) for channel in channels)
                       for channels in annotations["fields"].values())):
            raise ValueError("region_metadata_source_mismatch")
    for fid, source in previous.items():
        expected = {**source, "metadata": updates[fid]} if fid in updates else source
        if annotations is not None and fid in annotations["fields"]:
            expected = deepcopy(expected)
            revised = {**expected["image_info"], "channels": annotations["fields"][fid]}
            if image_pixel_identity(expected["image_info"]) != image_pixel_identity(revised):
                raise ValueError("region_parent_definition_changed")
            expected["image_info"] = revised
        if config.get("confirmed_channel_ids"):
            if config.get("measurement") is not None:
                raise ValueError("region_parent_definition_changed")
            expected = deepcopy(expected)
            confirmed = set(config["confirmed_channel_ids"])
            assignment_snapshot = config.get("channel_assignments", {})
            entries = assignment_snapshot.get("assignments", []) if "global_field_ids" not in assignment_snapshot or fid in assignment_snapshot["global_field_ids"] else []
            for group in assignment_snapshot.get("groups", []):
                if fid in group["field_ids"]:
                    entries = group["assignments"]
                    break
            assigned = {entry["channel_id"]: entry for entry in entries}
            for channel in expected["image_info"]["channels"]:
                if channel["channel_id"] in confirmed:
                    cid = channel["channel_id"]
                    roi = config.get("backgrounds", {}).get(fid, {}).get(cid)
                    if assigned.get(cid, {}).get("role") == "unused" or not roi or roi.get("confirmed") is not True:
                        raise ValueError("region_parent_definition_changed")
                    channel.pop("identity_source", None)
                    channel["identity_confirmed"] = True
        if expected != current[fid]:
            raise ValueError("region_parent_definition_changed")
