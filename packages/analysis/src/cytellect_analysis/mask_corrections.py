"""Manual mask edits of the measured region set, counted from saved provenance only.

Every edit is an immutable child revision whose `RegionMaskEdit` is appended to the
field's provenance history (generic-regions.md). The label operations are fixed:
add and split create exactly one label, merge keeps the smallest of its labels,
delete removes its labels and replace redraws one label; empty polygons are
refused. The number of initial regions is therefore reconstructed exactly from
the measured mask and the recorded operations, without reading any other revision.
"""
from __future__ import annotations

from collections import Counter

from .region_contracts import RegionMaskEdit

VERSION = "1.0.0"
OPERATIONS = ("add", "replace", "delete", "merge", "split")
INITIAL_EN = {
    "stardist_nuclear": "StarDist nuclear candidates", "cellpose_cell": "Cellpose cell candidates",
    "fiji_positive_regions": "Fiji signal-threshold candidates",
    "fiji_nuclear_compartment": "Fiji nuclear-compartment candidates",
    "imported": "imported labels", "manual": "an empty manual label plane",
}


def _mismatch():
    return ValueError("descriptive_mask_history_mismatch")


def _field(fid, table, mask, history, region_set_id):
    final = len({row["region_id"] for row in table["rows"]})
    row = {"field_id": fid, "mask_revision_id": mask["mask_revision_id"], "final_regions": final}
    starts = [index for index, event in enumerate(history if isinstance(history, list) else [])
              if isinstance(event, dict) and event.get("operation") == "initialize"]
    if not starts:
        return {**row, "status": "not_recorded", "initial_source": None, "initial_revision_id": None,
                "edit_revision_ids": [], "operations": dict.fromkeys(OPERATIONS, 0), "initial_regions": None,
                "added_regions": 0, "redrawn_regions": 0, "deleted_regions": 0, "split_regions": 0,
                "merged_regions": 0}
    initial, *later = history[starts[-1]:]
    edits = []
    for event in later:
        if event.get("operation") != "edit":
            continue
        try:
            edit = RegionMaskEdit.model_validate(event.get("edit"))
        except ValueError:
            raise _mismatch() from None
        if (edit.field_id != fid or edit.region_set_id != region_set_id
                or not isinstance(event.get("revision_id"), str)):
            raise _mismatch()
        edits.append((event["revision_id"], edit))
    if (not isinstance(initial.get("revision_id"), str)
            or (edits[-1][0] if edits else initial["revision_id"]) != mask["mask_revision_id"]):
        raise _mismatch()
    operations: Counter[str] = Counter(edit.operation for _, edit in edits)
    deleted = sum(len(edit.ids) for _, edit in edits if edit.operation == "delete")
    merged = sum(len(edit.ids) for _, edit in edits if edit.operation == "merge")
    initial_regions = final - operations["add"] - operations["split"] + deleted + merged - operations["merge"]
    if initial_regions < 0:
        raise _mismatch()
    return {**row, "status": "recorded", "initial_source": initial.get("source"),
            "initial_revision_id": initial["revision_id"], "edit_revision_ids": [rid for rid, _ in edits],
            "operations": {name: operations[name] for name in OPERATIONS}, "initial_regions": initial_regions,
            "added_regions": operations["add"], "redrawn_regions": operations["replace"],
            "deleted_regions": deleted, "split_regions": operations["split"], "merged_regions": merged}


def mask_correction_summary(report, provenance):
    """Per measured field: initial regions, recorded hand edits and measured regions."""
    recipe = report.get("recipe") or {}
    if provenance.get("revision_id") != report.get("revision_id"):
        raise _mismatch()
    rows = [_field(fid, report["field_tables"][fid], report["field_masks"][fid],
                   provenance.get("fields", {}).get(fid, {}).get("history"), recipe.get("region_set_id"))
            for fid in sorted(report.get("field_tables", {}))]
    # Parent masks of derived sets (compartments, cells bound to nuclei) are named, not counted.
    parents = set()
    for fid in report.get("field_tables", {}):
        for key in ("nuclear_source", "nucleolar_source"):
            source = provenance.get("fields", {}).get(fid, {}).get(key)
            if isinstance(source, dict) and isinstance(source.get("revision_id"), str):
                parents.add(source["revision_id"])
    return {"version": VERSION, "region_set_id": recipe.get("region_set_id"), "source": recipe.get("source"),
            "source_revision_ids": sorted(parents), "fields": rows,
            "edited_fields": sum(bool(row["edit_revision_ids"]) for row in rows)}


def with_mask_corrections(result, report, provenance):
    """Adds the ledger to a region descriptive result; absent from results created before it."""
    from .descriptive_contracts import MaskCorrectionSummary

    summary = mask_correction_summary(report, provenance)
    try:
        result["mask_corrections"] = MaskCorrectionSummary.model_validate(summary).model_dump(mode="json")
    except ValueError:
        raise _mismatch() from None
    return result


def _n(count, noun):
    """``1 region``, ``2 regions``: the English Methods count their nouns."""
    return f"{count} {noun}{'' if count == 1 else 's'}"


def _changes(row, ja):
    merged, merges = row["merged_regions"], row["operations"]["merge"]
    if ja:
        parts = [(row["deleted_regions"], f"{row['deleted_regions']} 領域を削除"),
                 (row["added_regions"], f"{row['added_regions']} 領域を追加"),
                 (row["redrawn_regions"], f"{row['redrawn_regions']} 領域を描き直し"),
                 (row["split_regions"], f"{row['split_regions']} 領域を 2 つに分割"),
                 (merged, f"{merged} 領域を {merges} 領域に結合")]
        return "、".join(text for count, text in parts if count)
    parts = [(row["deleted_regions"], f"{row['deleted_regions']} deleted"),
             (row["added_regions"], f"{row['added_regions']} added"),
             (row["redrawn_regions"], f"{row['redrawn_regions']} redrawn"),
             (row["split_regions"], f"{row['split_regions']} split in two"),
             (merged, f"{merged} merged into {merges}")]
    return ", ".join(text for count, text in parts if count)


def mask_correction_methods_lines(result, identify):
    """English Methods sentences; ``identify(field_id)`` names a field."""
    summary = result.get("mask_corrections")
    if not summary:
        return []
    rows, edited = summary["fields"], [row for row in summary["fields"] if row["edit_revision_ids"]]
    initial = INITIAL_EN.get(summary["source"], f"initial regions ({summary['source']})")
    if edited:
        lines = [f"Manual mask edits: masks of {len(edited)} of {_n(len(rows), 'measured field')} were edited by hand "
                 f"after their initial regions ({initial}) were created."]
        lines += [f"{identify(row['field_id'])}: {_n(row['initial_regions'], 'initial region')}; {_changes(row, False)}; "
                  f"{_n(row['final_regions'], 'region')} measured." for row in edited]
        lines.append("Initial region counts are reconstructed from the measured masks and the recorded edit operations. "
                     "Deleted regions are absent from the measured masks and are not counted as explicitly excluded "
                     "observations. Each edit's revision, operation, region IDs and polygon are retained in "
                     "provenance.json; per-field counts are in figure-data.json (mask_corrections).")
    else:
        lines = [f"Manual mask edits: none are recorded for the {_n(len(rows), 'measured field')}; "
                 f"their measured masks are the initial regions ({initial})."]
    missing = sum(row["status"] == "not_recorded" for row in rows)
    if missing:
        lines.append(f"No mask edit history is recorded for {_n(missing, 'measured field')}.")
    if summary["source_revision_ids"]:
        lines.append("Edits to the pinned source masks (revisions " + ", ".join(summary["source_revision_ids"])
                     + ") are recorded in those revisions and are not counted here.")
    return lines


def mask_correction_caption_lines(result, labels, ja):
    summary = result.get("mask_corrections")
    if not summary:
        return []
    edited = [row for row in summary["fields"] if row["edit_revision_ids"]]
    missing = [labels.get(row["field_id"], row["field_id"]) for row in summary["fields"]
               if row["status"] == "not_recorded"]
    if ja:
        lines = (["手作業の輪郭修正（件数は figure-data.json の mask_corrections）："
                  + "；".join(f"{labels.get(row['field_id'], row['field_id'])} は{_changes(row, True)}"
                             f"（最初 {row['initial_regions']} 領域、測定 {row['final_regions']} 領域）" for row in edited) + "。"]
                 if edited else ["手作業の輪郭修正は記録されていない。輪郭は最初の領域のまま。"])
        if missing:
            lines.append("輪郭修正の記録がない視野：" + "、".join(missing) + "。")
        return lines
    lines = (["Manual mask edits (counts in figure-data.json, mask_corrections): "
              + "; ".join(f"{labels.get(row['field_id'], row['field_id'])}: {_changes(row, False)} "
                         f"({_n(row['initial_regions'], 'initial region')}, {row['final_regions']} measured)" for row in edited) + "."]
             if edited else ["No manual mask edits are recorded; masks are the initial regions."])
    if missing:
        lines.append("No mask edit history is recorded for: " + ", ".join(missing) + ".")
    return lines
