"""Nucleus table 1.0.0: one row per adopted nucleus, every channel and the nucleus's nucleoli.

The table joins values the shared implementation has already measured; it never
re-reads pixels for intensity. Nucleus area, raw/corrected intensities and
saturation come from the nuclear revision's saved measurement rows. Nucleolar
count, union area, area fraction, largest-object fraction and eccentricity come
from the adopted original-coordinate label images (definitions in docs/methods.md,
"Nucleus table 1.0.0").

A nucleus without an adopted nucleolus is missing with the detector's reason,
never zero (the same rule as compartment-summary 1.1.0). Excluded nuclei stay in
the table with their reason. Rows are bound by nucleus label, never by order or
position.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Annotated, Final, Literal

import numpy as np
from pydantic import Field, FiniteFloat

from .masks import validate_label_array, validate_labels
from .nucleolar_shape import nucleolar_eccentricity, nucleolar_objects
from .regions import Calibration2D, Id, RegionModel

PROTOCOL: Final = "nucleus-table/1.0.0"
Digest64 = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
Fraction01 = Annotated[FiniteFloat, Field(ge=0, le=1)]
RegionId = Annotated[int, Field(ge=1, le=4294967295)]
Reason = Annotated[str, Field(pattern=r"^[a-z0-9_]+$", max_length=80)]


class NucleusChannelValues(RegionModel):
    channel_id: Id
    role: Literal["nuclear_stain", "measure"]
    mean: FiniteFloat | None
    integrated: FiniteFloat | None
    mean_corrected: FiniteFloat | None
    integrated_corrected: FiniteFloat | None
    intensity_missing_reason: Reason | None
    correction_missing_reason: Reason | None
    storage_limit_fraction: Fraction01 | None
    acquisition_saturation_fraction: Fraction01 | None
    acquisition_saturation_missing_reason: Reason | None


class NucleolarMorphology(RegionModel):
    status: Literal["measured", "missing", "not_measured"]
    reason: Reason | None
    count: Annotated[int, Field(ge=1)] | None
    union_area_px: Annotated[int, Field(ge=1)] | None
    union_area_um2: Annotated[FiniteFloat, Field(gt=0)] | None
    area_fraction: Fraction01 | None
    largest_object_area_px: Annotated[int, Field(ge=1)] | None
    largest_object_fraction: Fraction01 | None
    eccentricity: Fraction01 | None
    eccentricity_missing_reason: Reason | None


class NucleusRow(RegionModel):
    nucleus_id: RegionId
    excluded: bool
    exclusion_reason: Annotated[str, Field(min_length=1, max_length=200)] | None
    touches_border: bool
    nucleus_area_px: Annotated[int, Field(gt=0)]
    nucleus_area_um2: Annotated[FiniteFloat, Field(gt=0)] | None
    area_missing_reason: Literal["calibration_unknown"] | None
    channels: tuple[NucleusChannelValues, ...]
    nucleoli: NucleolarMorphology


class NucleolarSource(RegionModel):
    revision_id: Id
    mask_revision_id: Id
    mask_sha256: Digest64


class NucleusTable(RegionModel):
    protocol: Literal["nucleus-table/1.0.0"] = PROTOCOL
    field_id: Id
    nuclear_revision_id: Id
    nuclear_mask_revision_id: Id
    nuclear_mask_sha256: Digest64
    measurement_protocol_version: Literal["1.0.0", "2.0.0", "3.0.0", "4.0.0"]
    nuclear_channel_id: Id | None
    nucleolar_source: NucleolarSource | None
    calibration: Calibration2D | None
    field_excluded: bool
    rows: tuple[NucleusRow, ...]


def _channel_values(row, role: Literal["nuclear_stain", "measure"]) -> NucleusChannelValues:
    def value(name):
        return getattr(row, name, None)
    return NucleusChannelValues(
        channel_id=row.channel_id, role=role, mean=value("mean"), integrated=value("integrated"),
        mean_corrected=value("mean_corrected"), integrated_corrected=value("integrated_corrected"),
        intensity_missing_reason=value("intensity_missing_reason"),
        correction_missing_reason=value("correction_missing_reason"),
        storage_limit_fraction=value("storage_limit_fraction"),
        acquisition_saturation_fraction=value("acquisition_saturation_fraction"),
        acquisition_saturation_missing_reason=value("acquisition_saturation_missing_reason"))


def _not_measured(reason: str) -> NucleolarMorphology:
    return NucleolarMorphology(status="not_measured", reason=reason, count=None, union_area_px=None,
                               union_area_um2=None, area_fraction=None, largest_object_area_px=None,
                               largest_object_fraction=None, eccentricity=None,
                               eccentricity_missing_reason=None)


def nucleolar_morphology(nuclei: np.ndarray, nucleoli: np.ndarray, states: Mapping[int, str],
                         pixel_area_um2: float | None) -> dict[int, NucleolarMorphology]:
    """Per parent nucleus label: the adopted nucleoli inside it, from labels only.

    `nucleoli` must already have excluded objects set to 0. Each object belongs to
    exactly one nucleus (validated). The largest-object fraction is the largest
    object's area over the union area of the nucleus's nucleoli.
    """
    validate_labels(nuclei, nucleoli)
    parents, parent_area = np.unique(nuclei, return_counts=True)
    nuclear_area = {int(label): int(area) for label, area in zip(parents, parent_area, strict=True) if label}
    labels, label_area = np.unique(nucleoli[nucleoli > 0], return_counts=True)
    child_area = {int(label): int(area) for label, area in zip(labels, label_area, strict=True)}
    objects = {parent: [child_area[child] for child in children]
               for parent, children in nucleolar_objects(nuclei, nucleoli).items()}
    shapes = nucleolar_eccentricity(nuclei, nucleoli)
    result = {}
    for parent in nuclear_area:
        areas = objects.get(parent)
        if not areas:
            state = states.get(parent)
            reason = state if state and state != "candidate" else "no_adopted_nucleolus"
            result[parent] = NucleolarMorphology(
                status="missing", reason=reason, count=None, union_area_px=None, union_area_um2=None,
                area_fraction=None, largest_object_area_px=None, largest_object_fraction=None,
                eccentricity=None, eccentricity_missing_reason=None)
            continue
        union, largest = sum(areas), max(areas)
        shape = shapes[parent]
        result[parent] = NucleolarMorphology(
            status="measured", reason=None, count=len(areas), union_area_px=union,
            union_area_um2=None if pixel_area_um2 is None else union * pixel_area_um2,
            area_fraction=union / nuclear_area[parent], largest_object_area_px=largest,
            largest_object_fraction=largest / union, eccentricity=shape["nucleolar_eccentricity"],
            eccentricity_missing_reason=shape["missing_reason"])
    return result


def nucleus_table(*, field_id: str, nuclear_revision_id: str, nuclear_mask: Mapping, nuclear_table,
                  nuclear_labels: np.ndarray, exclusions: Sequence[Mapping], nuclear_channel_id: str | None,
                  nucleoli: np.ndarray | None = None, nucleolar_states: Mapping | None = None,
                  nucleolar_source: Mapping | None = None) -> NucleusTable:
    """Join the nuclear revision's saved rows with the adopted nucleoli of one field.

    `nuclear_table` is the field's saved measurement table (any region protocol);
    `nuclear_labels` the saved nuclear labels whose hash matches `nuclear_mask`.
    `exclusions` are the nuclear revision's exclusions for this field.
    """
    validate_label_array(nuclear_labels)
    if tuple(nuclear_labels.shape) != tuple(nuclear_table.shape_yx):
        raise ValueError("nucleus_table_shape_mismatch")
    if nuclear_mask["mask_sha256"] != nuclear_table.mask_sha256:
        raise ValueError("nucleus_table_mask_mismatch")
    if (nucleoli is None) != (nucleolar_source is None):
        raise ValueError("nucleus_table_nucleolar_source_invalid")
    field_excluded = any(item.get("region_id") is None for item in exclusions)
    excluded = {int(item["region_id"]): item["reason"] for item in exclusions if item.get("region_id") is not None}
    calibration = nuclear_table.calibration
    pixel_area = (calibration.pixel_size_x_um * calibration.pixel_size_y_um) if calibration is not None else None
    morphology = ({} if nucleoli is None else nucleolar_morphology(
        nuclear_labels, nucleoli, {int(key): value for key, value in (nucleolar_states or {}).items()}, pixel_area))
    present = {int(value) for value in np.unique(nuclear_labels) if value}
    grouped: dict[int, list] = {}
    for row in nuclear_table.rows:
        grouped.setdefault(row.region_id, []).append(row)
    if set(grouped) != present:
        raise ValueError("nucleus_table_region_mismatch")
    order = [item.channel.channel_id for item in nuclear_table.channel_provenance]
    rows = []
    for nucleus_id in sorted(grouped):
        by_channel = {row.channel_id: row for row in grouped[nucleus_id]}
        first = by_channel[order[0]]
        if nucleus_id in excluded:
            nucleolar = _not_measured("nucleus_excluded")
        elif nucleoli is None:
            nucleolar = _not_measured("nucleolar_revision_not_selected")
        else:
            nucleolar = morphology[nucleus_id]
        rows.append(NucleusRow(
            nucleus_id=nucleus_id, excluded=field_excluded or nucleus_id in excluded,
            exclusion_reason=excluded.get(nucleus_id), touches_border=first.touches_border,
            nucleus_area_px=first.area_px, nucleus_area_um2=first.area_um2,
            area_missing_reason=first.area_missing_reason,
            channels=tuple(_channel_values(by_channel[cid], "nuclear_stain" if cid == nuclear_channel_id else "measure")
                           for cid in order),
            nucleoli=nucleolar))
    return NucleusTable(
        field_id=field_id, nuclear_revision_id=nuclear_revision_id,
        nuclear_mask_revision_id=nuclear_mask["mask_revision_id"], nuclear_mask_sha256=nuclear_mask["mask_sha256"],
        measurement_protocol_version=nuclear_table.protocol_version,
        nuclear_channel_id=nuclear_channel_id if nuclear_channel_id in order else None,
        nucleolar_source=None if nucleolar_source is None else NucleolarSource(**nucleolar_source),
        calibration=calibration, field_excluded=field_excluded, rows=tuple(rows))
