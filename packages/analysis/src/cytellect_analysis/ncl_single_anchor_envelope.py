"""Experimental NCL envelope 1.0.0; immutable source pixels and original labels."""

from __future__ import annotations

import itertools

import numpy as np
from scipy import ndimage as ndi
from skimage.filters import threshold_multiotsu
from skimage.morphology import disk

from .masks import validate_label_array, validate_labels
from .measurement import normalize_nucleolar_states

MODE = "single-anchor-envelope-v1"


def _require(ok, code):
    if not ok:
        raise ValueError("cellpose_envelope_" + code)


def refine_ncl_single_anchor_envelope(
    image, anchors, nuclei, original_final, original_objects, nucleolar_states, eligible_parent_ids
):
    """Accept only source geometry/old detector provenance, never references or field IDs."""
    for labels in (anchors, nuclei, original_final):
        validate_label_array(labels)
        _require(int(labels.max()) < 2**24, "label_range_invalid")
    _require(
        isinstance(image, np.ndarray)
        and image.ndim == 2
        and image.size
        and image.dtype in (np.uint8, np.uint16)
        and max(image.shape) <= 4096,
        "input_invalid",
    )
    _require(image.shape == anchors.shape == nuclei.shape == original_final.shape, "shape_invalid")
    validate_labels(nuclei, anchors)
    validate_labels(nuclei, original_final)
    _require(isinstance(nucleolar_states, dict), "states_missing")
    states = normalize_nucleolar_states({"nucleolar_states": nucleolar_states})
    _require(set(states) == {int(v) for v in np.unique(nuclei) if v}, "states_incomplete")
    eligible = {pid for pid, state in states.items() if state == "candidate"}
    _require(set(eligible_parent_ids) == eligible, "eligibility_mismatch")
    original_objects = {int(k): v for k, v in original_objects.items()}
    for fid in (int(v) for v in np.unique(original_final) if v):
        _require(fid in original_objects, "object_provenance_missing")
        obj = original_objects[fid]
        _require(
            np.all(nuclei[original_final == fid] == obj["parent_id"])
            and obj["area"] == int(np.count_nonzero(original_final == fid)),
            "object_provenance_mismatch",
        )
    smooth = ndi.gaussian_filter(image.astype(np.float32), 0.9)
    structure8 = np.ones((3, 3), bool)
    boxes = ndi.find_objects(nuclei)
    records = []
    tentative = {}
    member_labels = np.zeros(anchors.shape, np.uint32)
    next_member = 1
    for parent in (int(v) for v in np.unique(nuclei) if v):
        box = boxes[parent - 1]
        _require(box is not None, "parent_box_missing")
        y0, y1 = max(0, box[0].start - 24), min(image.shape[0], box[0].stop + 24)
        x0, x1 = max(0, box[1].start - 24), min(image.shape[1], box[1].stop + 24)
        scope = nuclei[y0:y1, x0:x1] == parent
        source = anchors[y0:y1, x0:x1].copy()
        source[~scope] = 0
        ids = [int(v) for v in np.unique(source) if v]
        if not ids:
            records.append({"parent_id": parent, "status": "no_anchor"})
            continue
        for aid in ids:
            _require(np.count_nonzero(source == aid) == np.count_nonzero(anchors == aid), "geometry_invalid")
            _require(np.all(nuclei[anchors == aid] == parent), "geometry_invalid")
        values = smooth[y0:y1, x0:x1]
        original = image[y0:y1, x0:x1]
        try:
            threshold = float(threshold_multiotsu(values[scope], classes=3)[-1])
        except ValueError:
            records.append({"parent_id": parent, "status": "insufficient_signal_classes_unchanged"})
            continue
        support = (values >= threshold) & scope
        support = ndi.binary_closing(support, structure=disk(2)) & scope
        support = ndi.binary_fill_holes(support) & scope
        components, count = ndi.label(support, structure8)
        associations = {aid: [] for aid in ids}
        members = []
        for c in range(1, count + 1):
            member = components == c
            overlap = [int(v) for v in np.unique(source[member]) if v]
            gid = next_member
            next_member += 1
            member_labels[y0:y1, x0:x1][member] = gid
            for aid in overlap:
                associations[aid].append(gid)
            members.append((gid, member, overlap))
        for gid, member, overlap in members:
            rec = {
                "parent_id": parent,
                "member_id": gid,
                "crop_yxyx": [y0, y1, x0, x1],
                "upper_threshold": threshold,
                "complete_member_area": int(member.sum()),
                "positive_overlap_anchor_ids": overlap,
                "status": "pending_unchanged",
                "reasons": [],
            }
            records.append(rec)
            if len(overlap) != 1:
                rec["reasons"].append("no_anchor" if not overlap else "multiple_positive_overlap_anchors")
                continue
            aid = overlap[0]
            area = int(np.count_nonzero(source == aid))
            intersection = int(np.count_nonzero(member & (source == aid)))
            rec.update(
                anchor_id=aid,
                full_anchor_area=area,
                actual_crop_denominator=area,
                anchor_intersection=intersection,
                fraction=intersection / area,
                all_member_associations=associations[aid],
            )
            if len(associations[aid]) != 1:
                rec["reasons"].append("multiple_member_associations")
            if 2 * intersection < area:
                rec["reasons"].append("below_existing_half_anchor_rule")
            boundary = bool((member & ~ndi.binary_erosion(scope)).any())
            coverage = float(member.sum() / scope.sum())
            ring = ndi.binary_dilation(member, iterations=8) & ~support & scope
            enriched = bool(ring.any() and original[member].mean() > original[ring].mean())
            rec.update(
                nuclear_boundary=boundary,
                parent_coverage=coverage,
                enriched=enriched,
                ring_pixels=int(ring.sum()),
            )
            if boundary:
                rec["reasons"].append("parent_boundary")
            if coverage > 0.5:
                rec["reasons"].append("parent_coverage")
            if not enriched:
                rec["reasons"].append("not_enriched")
            owning = [(int(fid), o) for fid, o in original_objects.items() if aid in o["source_anchor_ids"]]
            if len(owning) != 1 or owning[0][1]["source_anchor_ids"] != [aid]:
                rec["reasons"].append("old_group_not_single_anchor_single_final")
            if rec["reasons"]:
                continue
            fid, obj = owning[0]
            old = original_final == fid
            if not old.any() or obj["parent_id"] != parent or not np.all(nuclei[old] == parent):
                rec["reasons"].append("old_final_not_visible_in_adopted_parent")
                continue
            whole = np.zeros(anchors.shape, bool)
            whole[y0:y1, x0:x1] = member
            candidate = whole | old
            rec.update(
                final_id=fid,
                old_final_area=int(old.sum()),
                proposal_area=int(candidate.sum()),
                added_pixels=int(np.count_nonzero(candidate & ~old)),
            )
            if not rec["added_pixels"]:
                rec.update(status="unchanged_no_new_pixels")
                continue
            if not np.all(nuclei[candidate] == parent) or ndi.label(candidate, structure8)[1] != 1:
                rec["reasons"].append("invalid_parent_or_connectivity")
                continue
            other = (original_final != 0) & (original_final != fid)
            if (ndi.binary_dilation(candidate, structure=structure8) & other).any():
                rec["reasons"].append("touches_or_overlaps_other_old_final")
                continue
            _require(fid not in tentative, "geometry_invalid")
            tentative[fid] = (candidate, rec)
    # Simultaneous proposals: conflicts reject BOTH, without sequential acceptance bias.
    conflicts = []
    bad = set()
    for a, b in itertools.combinations(sorted(tentative), 2):
        ma, ra = tentative[a]
        mb, rb = tentative[b]
        if (ndi.binary_dilation(ma, structure=structure8) & mb).any():
            bad.update((a, b))
            conflicts.append([a, b])
            ra["reasons"].append("mutual_proposal_overlap_or_8_adjacency")
            rb["reasons"].append("mutual_proposal_overlap_or_8_adjacency")
    result = original_final.copy()
    withheld = np.zeros_like(original_final, dtype=np.uint32)
    for fid, (candidate, rec) in tentative.items():
        if fid in bad:
            continue
        _require(not ((result > 0) & (result != fid) & candidate).any(), "geometry_invalid")
        parent = rec["parent_id"]
        rec["existing_parent_state"] = states[parent]
        rec["original_area_px"] = int(np.count_nonzero(original_final == fid))
        if states[parent] != "candidate":
            withheld[candidate & (original_final == 0)] = fid
            rec["status"] = "withheld_parent_state"
            rec["reasons"].append("existing_parent_state_" + states[parent])
            rec["final_area_px"] = rec["original_area_px"]
            continue
        result[candidate] = fid
        rec["status"] = "research_proposal_applied"
        rec["final_area_px"] = int(np.count_nonzero(result == fid))
    _require(
        np.array_equal(result[original_final > 0], original_final[original_final > 0]), "geometry_invalid"
    )
    _require(set(np.unique(result)) == set(np.unique(original_final)), "geometry_invalid")
    for fid, (candidate, rec) in tentative.items():
        if rec["status"] == "research_proposal_applied":
            _require(
                not (
                    ndi.binary_dilation(result == fid, structure=structure8)
                    & ((result != 0) & (result != fid))
                ).any(),
                "geometry_invalid",
            )
            _require(ndi.label(result == fid, structure8)[1] == 1, "geometry_invalid")
    return (
        result,
        member_labels,
        withheld,
        {
            "mode": MODE,
            "protocol_version": "1.0.0",
            "parent_state_policy": "additional_growth_only_for_exact_candidate",
            "original_objects": original_objects,
            "eligible_parent_ids": sorted(eligible),
            "parent_states": states,
            "records": records,
            "mutual_conflicts": conflicts,
            "applied_ids": [
                fid for fid, (_, r) in tentative.items() if r["status"] == "research_proposal_applied"
            ],
            "original_pixels_and_ids_preserved": True,
            "candidate_generation_reference_blind": True,
            "withheld_ids": sorted(int(v) for v in np.unique(withheld) if v),
            "biological_ownership_or_merge_safety_established": False,
        },
    )
