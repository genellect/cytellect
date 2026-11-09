"""Owned preview of saved nuclear channel means; formal statistics retain their review gate."""
import json
from types import SimpleNamespace
from typing import Annotated

from cytellect_analysis.channel_gate_contracts import ChannelGateRequest, ChannelGateResult
from cytellect_analysis.channel_selection import apply_channel_gate, channel_filter
from cytellect_analysis.gfp_selection import binding_kind
from cytellect_analysis.images import sha256
from cytellect_analysis.region_contracts import region_report_from_json, validate_region_report_policy
from fastapi import Depends, HTTPException

from .storage import read_json


def require_gate_source(rev, selection):
    """Immediate request guards; workers also bind masks, snapshot, exclusions and saved rows."""
    from .regions import require_gfp_gate_source

    gate = channel_filter(selection)
    if gate is None:
        positivity = getattr(selection, "positivity", None)
        require_gfp_gate_source(rev, SimpleNamespace(gfp_gate=positivity) if positivity is not None else selection)
        return
    recipe = rev["config"].get("recipe", {})
    if gate.reference_sha256 is None:
        raise HTTPException(422, "channel_gate_record_required")
    try:
        binding_kind(recipe, error_prefix="channel_gate")
        if recipe.get("source") in ("manual", "cellpose_cell"):
            raise ValueError("channel_gate_nuclear_source_invalid")
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    snapshot = rev["config"].get("field_snapshot", {})
    if set(gate.control_field_ids) - set(snapshot):
        raise HTTPException(422, "channel_gate_unknown_control_field")
    if any(all(channel.get("channel_id") != gate.channel_id for channel in field["image_info"].get("channels", []))
           for field in snapshot.values()):
        raise HTTPException(422, "channel_gate_channel_unknown")


def register_channel_gate_routes(api, store, owner, workspace, revision, result_root):
    Owner = Annotated[str, Depends(owner)]

    @api.post("/v1/workspaces/{wid}/channel-gate", response_model=ChannelGateResult)
    def classify(wid: str, body: ChannelGateRequest, who: Owner):
        workspace(wid, who)
        snapshot, sources, observations, failed, exclusions = {}, {}, [], [], set()
        target_exclusions, loaded = [], {}
        for item in body.fields:
            rev = revision(item.revision_id, who)
            config = rev["config"]
            if (rev["workspace_id"] != wid or config.get("analysis_kind") != "region-2d"
                    or not (config.get("recipe", {}).get("source") == "stardist_nuclear"
                            or (config.get("recipe", {}).get("source") == "fiji_nuclear_compartment"
                                and config["recipe"].get("compartment") == "nucleoplasm"))
                    or item.field_id not in config.get("field_ids", [])):
                raise HTTPException(409, "channel_gate_requires_nuclear_revision")
            if rev["id"] not in loaded:
                path = result_root(rev) / "measurements.json"
                report = region_report_from_json(json.dumps(read_json(path)))
                validate_region_report_policy(report, config)
                from cytellect_worker.gfp_sources import load_gate_nuclear_source
                parent = load_gate_nuclear_source(store, rev, report.model_dump(mode="json"),
                                                  SimpleNamespace(channel_gate=body.filter))
                loaded[rev["id"]] = report, sha256(path), parent
            report, report_hash, parent = loaded[rev["id"]]
            field = config.get("field_snapshot", {}).get(item.field_id)
            if (field is None or report.revision_id != rev["id"]
                    or report.recipe.model_dump(mode="json") != config.get("recipe")):
                raise HTTPException(409, "channel_gate_source_invalid")
            snapshot[item.field_id] = field
            saved_exclusions = [value.model_dump(mode="json") for value in report.exclusions if value.field_id == item.field_id]
            target_exclusions.extend(saved_exclusions)
            if any(value["region_id"] is None for value in saved_exclusions):
                exclusions.add(item.field_id)
            table, mask = report.field_tables.get(item.field_id), report.field_masks.get(item.field_id)
            if table is None:
                failed.append(item.field_id)
                continue
            if mask is None or list(table.shape_yx) != field["image_info"]["shape"]:
                raise HTTPException(409, "channel_gate_source_invalid")
            sources[item.field_id] = parent["fields"][item.field_id] if parent is not None else {
                "revision_id": rev["id"], "report_sha256": report_hash, "table": table.model_dump(mode="json"),
                "mask_revision_id": mask.mask_revision_id, "mask_sha256": mask.mask_sha256,
                "exclusions": saved_exclusions, "image_info": field["image_info"]}
            excluded_ids = {value["region_id"] for value in sources[item.field_id]["exclusions"]}
            for region_id in sorted({row["region_id"] for row in sources[item.field_id]["table"]["rows"]}):
                observations.append({"field_id": item.field_id, "region_id": region_id,
                                     "excluded": None in excluded_ids or region_id in excluded_ids})
        try:
            _, record = apply_channel_gate(observations, snapshot, body.filter,
                                           {"binding": "parent_nucleus" if any(value[2] is not None for value in loaded.values()) else "same_revision", "fields": sources},
                                           failed_fields=failed, field_exclusions=exclusions,
                                           target_exclusions=target_exclusions)
        except ValueError as exc:
            raise HTTPException(422, str(exc) if str(exc).startswith("channel_gate_") else "channel_gate_source_invalid") from None
        return ChannelGateResult(filter=body.filter, channel=record["channel"], dates=record["dates"],
                                 nuclei=record["nuclei"], field_counts=record["field_counts"], record=record)
