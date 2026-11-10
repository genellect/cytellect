"""Nucleus table 1.0.0: one row per nucleus, every channel and the nucleus's confirmed nucleoli.

The table joins values the shared implementation has already measured; it never
re-reads pixels for intensity. Nucleus area, raw/corrected intensities and
saturation come from the nuclear revision's saved measurement rows. Nucleolar
count, union area, area fraction, largest-object fraction and eccentricity come
from the nucleolar revision's original-coordinate label images (definitions in
docs/methods.md, "Nucleus table 1.0.0").

A nucleus's nucleoli are confirmed when the nucleolar revision is the adopted one and
the nucleus has at least one adopted nucleolus left after exclusions: the same rule as
comparisons and descriptions (`adopted_nucleolar_states`), so a nucleolus the researcher
added, kept or edited counts. Every other case is missing with its reason, never zero.
Excluded nuclei stay in the table with their reason. Rows are bound by nucleus label,
never by order or position.
"""
from __future__ import annotations

import io
import json
from collections.abc import Mapping, Sequence
from typing import Annotated, Final, Literal

import numpy as np
from pydantic import Field, FiniteFloat

from .compartment_engine import adopted_nucleolar_states
from .exports_csv import write_csv_stream
from .masks import validate_label_array, validate_labels
from .nucleolar_shape import nucleolar_eccentricity, nucleolar_objects
from .regions import FIELD_EXCLUSION_REASON_MAX, Calibration2D, Id, Label, RegionModel

PROTOCOL: Final = "nucleus-table/1.0.0"
Digest64 = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
Fraction01 = Annotated[FiniteFloat, Field(ge=0, le=1)]
RegionId = Annotated[int, Field(ge=1, le=4294967295)]
Reason = Annotated[str, Field(pattern=r"^[a-z0-9_]+$", max_length=80)]
Count = Annotated[int, Field(ge=0)]


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
    # Why µm² is absent while the nucleoli are confirmed: no calibration, or the nucleolar
    # revision's calibration differs from the nuclear one.
    union_area_um2_missing_reason: Literal["calibration_unknown", "calibration_mismatch"] | None
    area_fraction: Fraction01 | None
    largest_object_area_px: Annotated[int, Field(ge=1)] | None
    largest_object_fraction: Fraction01 | None
    eccentricity: Fraction01 | None
    eccentricity_missing_reason: Reason | None
    excluded_objects: Count


class NucleusRow(RegionModel):
    nucleus_id: RegionId
    excluded: bool
    exclusion_scope: Literal["field", "nucleus"] | None
    # A nucleus's own reason (at most 200 characters) or the reason of its excluded field, which the
    # workspace's selection screen saves at up to FIELD_EXCLUSION_REASON_MAX characters.
    exclusion_reason: Annotated[str, Field(min_length=1, max_length=FIELD_EXCLUSION_REASON_MAX)] | None
    touches_border: bool
    nucleus_area_px: Annotated[int, Field(gt=0)]
    nucleus_area_um2: Annotated[FiniteFloat, Field(gt=0)] | None
    area_missing_reason: Literal["calibration_unknown"] | None
    channels: tuple[NucleusChannelValues, ...]
    nucleoli: NucleolarMorphology


class TableChannel(RegionModel):
    """The recorded identity of one channel, so a saved table names the stain of every column."""
    channel_id: Id
    label: Label
    stain: Label | None
    role: Literal["nuclear_stain", "measure"]


class NucleolarSource(RegionModel):
    revision_id: Id
    mask_revision_id: Id
    mask_sha256: Digest64
    adopted: bool
    field_excluded: bool


class ChannelBackground(RegionModel):
    """Where a channel's corrected values come from: a confirmed ROI, an unconfirmed automatic
    candidate (protocol 4.0.0), or no background (raw or area-only protocols)."""
    channel_id: Id
    source: Literal["confirmed_roi", "automatic_candidate", "not_established"]
    confirmed_by_researcher: bool
    median: FiniteFloat | None


def _channel_background(provenance) -> ChannelBackground:
    channel_id = provenance.channel.channel_id
    record = getattr(provenance, "background", None)
    if record is None and getattr(provenance, "background_median", None) is not None:
        # Corrected protocol 1.0.0: a confirmed background ROI of a saved background revision.
        return ChannelBackground(channel_id=channel_id, source="confirmed_roi", confirmed_by_researcher=True,
                                 median=provenance.background_median)
    if record is not None and getattr(record, "background_source", None) == "automatic_candidate":
        return ChannelBackground(channel_id=channel_id, source="automatic_candidate", confirmed_by_researcher=False,
                                 median=record.background_median)
    return ChannelBackground(channel_id=channel_id, source="not_established", confirmed_by_researcher=False, median=None)


class NucleusTable(RegionModel):
    protocol: Literal["nucleus-table/1.0.0"] = PROTOCOL
    field_id: Id
    nuclear_revision_id: Id
    nuclear_mask_revision_id: Id
    nuclear_mask_sha256: Digest64
    nuclear_adopted: bool
    measurement_protocol_version: Literal["1.0.0", "2.0.0", "3.0.0", "4.0.0"]
    nuclear_channel_id: Id | None
    nucleolar_source: NucleolarSource | None
    calibration: Calibration2D | None
    field_excluded: bool
    channels: tuple[TableChannel, ...]
    backgrounds: tuple[ChannelBackground, ...]
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


def _unconfirmed(status: Literal["missing", "not_measured"], reason: str, excluded_objects: int = 0) -> NucleolarMorphology:
    return NucleolarMorphology(status=status, reason=reason, count=None, union_area_px=None, union_area_um2=None,
                               union_area_um2_missing_reason=None, area_fraction=None, largest_object_area_px=None, largest_object_fraction=None,
                               eccentricity=None, eccentricity_missing_reason=None, excluded_objects=excluded_objects)


def nucleolar_morphology(nuclei: np.ndarray, nucleoli: np.ndarray, states: Mapping[int, str],
                         pixel_area_um2: float | None,
                         excluded_objects: Mapping[int, int] | None = None,
                         area_missing_reason: Literal["calibration_unknown", "calibration_mismatch"] = "calibration_unknown",
                         ) -> dict[int, NucleolarMorphology]:
    """Per parent nucleus label: its confirmed nucleoli, from labels and the recorded detector state.

    `nucleoli` must already have excluded objects set to 0; `excluded_objects` counts
    them per parent. `states` is the state this function is to trust for each parent:
    a parent whose state is `candidate` and that has at least one remaining object is
    measured; any other state, or none, is missing with that reason. The table passes
    `adopted_nucleolar_states`, where a parent with an adopted nucleolus (also one
    awaiting review that the researcher kept, added or edited) is `candidate`. The
    largest-object fraction is the largest object's area over the union area of the
    nucleus's nucleoli. Without `pixel_area_um2` the µm² area is missing with
    `area_missing_reason`.
    """
    validate_labels(nuclei, nucleoli)
    excluded_objects = excluded_objects or {}
    parents, parent_area = np.unique(nuclei, return_counts=True)
    nuclear_area = {int(label): int(area) for label, area in zip(parents, parent_area, strict=True) if label}
    labels, label_area = np.unique(nucleoli[nucleoli > 0], return_counts=True)
    child_area = {int(label): int(area) for label, area in zip(labels, label_area, strict=True)}
    objects = {parent: [child_area[child] for child in children]
               for parent, children in nucleolar_objects(nuclei, nucleoli).items()}
    shapes = nucleolar_eccentricity(nuclei, nucleoli)
    result = {}
    for parent in nuclear_area:
        areas, state, dropped = objects.get(parent), states.get(parent), excluded_objects.get(parent, 0)
        if state is None:
            result[parent] = _unconfirmed("missing", "nucleolar_state_unknown", dropped)
        elif state != "candidate":
            result[parent] = _unconfirmed("missing", state, dropped)
        elif not areas:
            result[parent] = _unconfirmed("missing", "no_adopted_nucleolus", dropped)
        else:
            union, largest = sum(areas), max(areas)
            shape = shapes[parent]
            result[parent] = NucleolarMorphology(
                status="measured", reason=None, count=len(areas), union_area_px=union,
                union_area_um2=None if pixel_area_um2 is None else union * pixel_area_um2,
                union_area_um2_missing_reason=area_missing_reason if pixel_area_um2 is None else None,
                area_fraction=union / nuclear_area[parent], largest_object_area_px=largest,
                largest_object_fraction=largest / union, eccentricity=shape["nucleolar_eccentricity"],
                eccentricity_missing_reason=shape["missing_reason"], excluded_objects=dropped)
    return result


def _excluded(exclusions: Sequence[Mapping]) -> tuple[str | None, dict[int, str]]:
    """The whole-field exclusion reason (None when the field is kept) and the per-region reasons."""
    field = next((item["reason"] for item in exclusions if item.get("region_id") is None), None)
    return field, {int(item["region_id"]): item["reason"] for item in exclusions if item.get("region_id") is not None}


def nucleus_table(*, field_id: str, nuclear_revision_id: str, nuclear_mask: Mapping, nuclear_table,
                  nuclear_labels: np.ndarray, exclusions: Sequence[Mapping], nuclear_channel_id: str | None,
                  nuclear_adopted: bool, nucleoli: np.ndarray | None = None, nucleolar_states: Mapping | None = None,
                  nucleolar_exclusions: Sequence[Mapping] = (), nucleolar_source: Mapping | None = None,
                  nucleolar_calibration_matches: bool = True,
                  nucleolar_missing_reason: str = "nucleolar_revision_not_selected") -> NucleusTable:
    """Join the nuclear revision's saved rows with the nucleolar revision of one field.

    `nuclear_table` is the field's saved measurement table (any region protocol);
    `nuclear_labels` the saved nuclear labels whose hash matches `nuclear_mask`;
    `exclusions` the nuclear revision's exclusions for this field. `nucleoli` are the
    nucleolar revision's saved labels before its `nucleolar_exclusions` are applied;
    `nucleolar_source` records its identity and whether it is the adopted one. Nucleolar µm²
    needs the nucleolar revision's calibration to equal the nuclear one; without a nucleolar
    revision, `nucleolar_missing_reason` says why (not selected, or unavailable for this field).
    """
    validate_label_array(nuclear_labels)
    if tuple(nuclear_labels.shape) != tuple(nuclear_table.shape_yx):
        raise ValueError("nucleus_table_shape_mismatch")
    if nuclear_mask["mask_sha256"] != nuclear_table.mask_sha256:
        raise ValueError("nucleus_table_mask_mismatch")
    if (nucleoli is None) != (nucleolar_source is None):
        raise ValueError("nucleus_table_nucleolar_source_invalid")
    field_reason, excluded = _excluded(exclusions)
    field_excluded = field_reason is not None
    calibration = nuclear_table.calibration
    pixel_area = (calibration.pixel_size_x_um * calibration.pixel_size_y_um) if calibration is not None else None
    morphology: dict[int, NucleolarMorphology] = {}
    nucleolar_field_excluded = False
    if nucleoli is not None:
        assert nucleolar_source is not None
        validate_labels(nuclear_labels, nucleoli)
        nucleolar_field_reason, dropped_ids = _excluded(nucleolar_exclusions)
        nucleolar_field_excluded = nucleolar_field_reason is not None
        dropped = np.isin(nucleoli, sorted(dropped_ids))
        dropped_by_parent: dict[int, int] = {}
        for child, parent in {int(c): int(p) for c, p in zip(nucleoli[dropped], nuclear_labels[dropped], strict=True)}.items():
            dropped_by_parent[parent] = dropped_by_parent.get(parent, 0) + 1
        # The same rule as comparisons and descriptions: a nucleus with an adopted nucleolus (added,
        # kept or edited by the researcher) is confirmed; one whose nucleoli were all excluded keeps
        # that state, so its reason stays "no adopted nucleolus" with the excluded count.
        states = adopted_nucleolar_states(nuclear_labels, nucleoli, nucleolar_states)
        morphology = nucleolar_morphology(nuclear_labels, np.where(dropped, 0, nucleoli).astype(nucleoli.dtype),
                                          states, pixel_area if nucleolar_calibration_matches else None,
                                          dropped_by_parent,
                                          "calibration_unknown" if pixel_area is None else "calibration_mismatch")
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
        if not order or set(by_channel) != set(order):
            raise ValueError("nucleus_table_region_mismatch")  # every nucleus needs one row per channel
        first = by_channel[order[0]]
        # An exclusion (of this nucleus or of the whole field) comes before every nucleolar reason.
        scope: Literal["field", "nucleus"] | None = (
            "nucleus" if nucleus_id in excluded else "field" if field_excluded else None)
        nucleus_excluded = scope is not None
        if nucleus_excluded:
            nucleolar = _unconfirmed("not_measured", "nucleus_excluded")
        elif nucleoli is None:
            nucleolar = _unconfirmed("not_measured", nucleolar_missing_reason)
        elif nucleolar_field_excluded:
            nucleolar = _unconfirmed("missing", "nucleolar_field_excluded")
        elif not nucleolar_source["adopted"]:  # type: ignore[index]
            nucleolar = _unconfirmed("missing", "nucleolar_revision_not_adopted", morphology[nucleus_id].excluded_objects)
        else:
            nucleolar = morphology[nucleus_id]
        rows.append(NucleusRow(
            nucleus_id=nucleus_id, excluded=nucleus_excluded, exclusion_scope=scope,
            exclusion_reason=excluded.get(nucleus_id, field_reason),
            touches_border=first.touches_border, nucleus_area_px=first.area_px, nucleus_area_um2=first.area_um2,
            area_missing_reason=first.area_missing_reason,
            channels=tuple(_channel_values(by_channel[cid], "nuclear_stain" if cid == nuclear_channel_id else "measure")
                           for cid in order),
            nucleoli=nucleolar))
    return NucleusTable(
        field_id=field_id, nuclear_revision_id=nuclear_revision_id,
        nuclear_mask_revision_id=nuclear_mask["mask_revision_id"], nuclear_mask_sha256=nuclear_mask["mask_sha256"],
        nuclear_adopted=nuclear_adopted, measurement_protocol_version=nuclear_table.protocol_version,
        nuclear_channel_id=nuclear_channel_id if nuclear_channel_id in order else None,
        nucleolar_source=None if nucleolar_source is None else NucleolarSource(
            **nucleolar_source, field_excluded=nucleolar_field_excluded),
        calibration=calibration, field_excluded=field_excluded,
        channels=tuple(TableChannel(channel_id=item.channel.channel_id, label=item.channel.label,
                                    stain=item.channel.stain,
                                    role="nuclear_stain" if item.channel.channel_id == nuclear_channel_id else "measure")
                       for item in nuclear_table.channel_provenance),
        backgrounds=tuple(_channel_background(item) for item in nuclear_table.channel_provenance),
        rows=tuple(rows))


# --- CSV export: the same table, one row per nucleus, with units and definitions ---

_NUCLEOLAR_COLUMNS = (
    ("nucleolar_status", "", "measured: nucleoli confirmed; missing: not confirmed (reason given); not_measured: not analysed or nucleus excluded"),
    ("nucleolar_reason", "", "Why nucleolar values are absent: the detector state for this nucleus or the table rule"),
    ("nucleolar_count", "objects", "Number of confirmed nucleolar objects in the nucleus"),
    ("nucleolar_area_px", "px²", "Union area of the nucleus's confirmed nucleoli"),
    ("nucleolar_area_um2", "µm²", "Union area in µm² with a confirmed calibration"),
    ("nucleolar_area_um2_missing_reason", "", "Why µm² is absent while the nucleoli are confirmed: calibration_unknown, or calibration_mismatch (the nucleolar and nuclear revisions record different pixel sizes)"),
    ("nucleolar_area_fraction", "ratio", "Nucleolar union area / nucleus area"),
    ("largest_nucleolus_area_px", "px²", "Area of the largest confirmed nucleolus"),
    ("largest_nucleolus_fraction", "ratio", "Largest nucleolus area / nucleolar union area"),
    ("nucleolar_eccentricity", "0–1", "Area-weighted mean eccentricity of the nucleolar objects (compartment-summary 1.1.0)"),
    ("nucleolar_eccentricity_missing_reason", "", "Why eccentricity is absent while the nucleoli are confirmed"),
    ("excluded_nucleoli", "objects", "Nucleolar objects of this nucleus excluded by the researcher (not counted above)"),
)


def _columns(table: NucleusTable) -> list[tuple[str, str, str]]:
    channels = table.channels
    columns = [
        ("protocol", "", "Nucleus table version"),
        ("field_id", "", "Field"),
        ("nuclear_revision_id", "", "Analysis revision of the nuclei"),
        ("nuclear_mask_revision_id", "", "Revision that last changed the nuclear mask"),
        ("nuclear_mask_sha256", "", "Hash of the nuclear label image (cytellect-array-v1)"),
        ("nuclear_adopted", "", "Whether these nuclei are the field's adopted nuclei"),
        ("measurement_protocol_version", "", "Region measurement protocol of the saved values"),
        ("nucleolar_revision_id", "", "Analysis revision of the nucleoli (empty: not selected)"),
        ("nucleolar_mask_revision_id", "", "Revision that last changed the nucleolar mask"),
        ("nucleolar_mask_sha256", "", "Hash of the nucleolar label image"),
        ("nucleolar_adopted", "", "Whether these nucleoli are the field's adopted nucleoli"),
        ("pixel_size_x_um", "µm", "Confirmed pixel width (empty: uncalibrated)"),
        ("pixel_size_y_um", "µm", "Confirmed pixel height (empty: uncalibrated)"),
        ("nucleus_id", "", "Nucleus label in the nuclear mask"),
        ("excluded", "", "Excluded by the researcher (the whole field or this nucleus)"),
        ("exclusion_scope", "", "field: the whole field was excluded; nucleus: this nucleus was excluded"),
        ("exclusion_reason", "", "Researcher's reason (this nucleus's own reason, else the field's)"),
        ("touches_border", "", "The nucleus touches the image border"),
        ("nucleus_area_px", "px²", "Nucleus area"),
        ("nucleus_area_um2", "µm²", "Nucleus area with a confirmed calibration"),
        ("area_missing_reason", "", "Why µm² is absent"),
    ]
    for item in channels:
        cid = item.channel_id
        stain = "the nuclear stain (relative DNA signal; not a DNA amount)" if item.role == "nuclear_stain" else "this stain"
        columns += [
            (f"{cid}__label", "", "Recorded name of this channel"),
            (f"{cid}__stain", "", "Recorded stain of this channel (empty: not recorded)"),
            (f"{cid}__role", "", "nuclear_stain: the channel that defined the nuclei; measure: other stains"),
            (f"{cid}__mean", "intensity", f"Mean original pixel value of {stain} in the nucleus"),
            (f"{cid}__integrated", "intensity × px", f"Sum of original pixel values of {stain} in the nucleus"),
            (f"{cid}__background_source", "", "confirmed_roi: a researcher-confirmed background ROI; automatic_candidate: an unconfirmed automatic estimate; not_established: no background"),
            (f"{cid}__background_confirmed", "", "Whether a person confirmed the background used for the corrected values"),
            (f"{cid}__background_median", "intensity", "Background value subtracted for the corrected values"),
            (f"{cid}__mean_corrected", "intensity", "Mean minus the channel background (see background_source)"),
            (f"{cid}__integrated_corrected", "intensity × px", "Sum minus area × background"),
            (f"{cid}__intensity_missing_reason", "", "Why raw intensities are absent"),
            (f"{cid}__correction_missing_reason", "", "Why corrected intensities are absent"),
            (f"{cid}__storage_limit_fraction", "ratio", "Fraction of nucleus pixels at the file's maximum value"),
            (f"{cid}__acquisition_saturation_fraction", "ratio", "Fraction of nucleus pixels at or above the detector's saturation value"),
            (f"{cid}__acquisition_saturation_missing_reason", "", "Why the saturation fraction is absent"),
        ]
    return columns + list(_NUCLEOLAR_COLUMNS)


def nucleus_table_csv_rows(table: NucleusTable) -> tuple[list[str], list[dict], list[dict]]:
    """The table as CSV rows (one per nucleus) and the column definitions; values are copied, not recomputed."""
    columns = _columns(table)
    source = table.nucleolar_source
    calibration = table.calibration
    common = {
        "protocol": table.protocol, "field_id": table.field_id, "nuclear_revision_id": table.nuclear_revision_id,
        "nuclear_mask_revision_id": table.nuclear_mask_revision_id, "nuclear_mask_sha256": table.nuclear_mask_sha256,
        "nuclear_adopted": table.nuclear_adopted, "measurement_protocol_version": table.measurement_protocol_version,
        "nucleolar_revision_id": source.revision_id if source else None,
        "nucleolar_mask_revision_id": source.mask_revision_id if source else None,
        "nucleolar_mask_sha256": source.mask_sha256 if source else None,
        "nucleolar_adopted": source.adopted if source else None,
        "pixel_size_x_um": calibration.pixel_size_x_um if calibration else None,
        "pixel_size_y_um": calibration.pixel_size_y_um if calibration else None,
    }
    rows = []
    for row in table.rows:
        record = {**common, "nucleus_id": row.nucleus_id, "excluded": row.excluded, "exclusion_scope": row.exclusion_scope,
                  "exclusion_reason": row.exclusion_reason, "touches_border": row.touches_border,
                  "nucleus_area_px": row.nucleus_area_px, "nucleus_area_um2": row.nucleus_area_um2,
                  "area_missing_reason": row.area_missing_reason}
        for channel in table.channels:
            record[f"{channel.channel_id}__label"] = channel.label
            record[f"{channel.channel_id}__stain"] = channel.stain
        for background in table.backgrounds:
            record[f"{background.channel_id}__background_source"] = background.source
            record[f"{background.channel_id}__background_confirmed"] = background.confirmed_by_researcher
            record[f"{background.channel_id}__background_median"] = background.median
        for item in row.channels:
            for key in ("role", "mean", "integrated", "mean_corrected", "integrated_corrected", "intensity_missing_reason",
                        "correction_missing_reason", "storage_limit_fraction", "acquisition_saturation_fraction",
                        "acquisition_saturation_missing_reason"):
                record[f"{item.channel_id}__{key}"] = getattr(item, key)
        m = row.nucleoli
        record.update({"nucleolar_status": m.status, "nucleolar_reason": m.reason, "nucleolar_count": m.count,
                       "nucleolar_area_px": m.union_area_px, "nucleolar_area_um2": m.union_area_um2,
                       "nucleolar_area_um2_missing_reason": m.union_area_um2_missing_reason,
                       "nucleolar_area_fraction": m.area_fraction, "largest_nucleolus_area_px": m.largest_object_area_px,
                       "largest_nucleolus_fraction": m.largest_object_fraction, "nucleolar_eccentricity": m.eccentricity,
                       "nucleolar_eccentricity_missing_reason": m.eccentricity_missing_reason,
                       "excluded_nucleoli": m.excluded_objects})
        rows.append(record)
    names = [name for name, _, _ in columns]
    # A channel column is named by its channel ID; the definitions name that channel's label and stain.
    by_id = {channel.channel_id: channel for channel in table.channels}
    definitions = []
    for name, unit, text in columns:
        named = by_id.get(name.split("__", 1)[0]) if "__" in name else None
        definitions.append({"column": name, "unit": unit, "definition": text,
                            "channel_id": named.channel_id if named else None,
                            "channel_label": named.label if named else None,
                            "stain": named.stain if named else None})
    return names, rows, definitions


def nucleus_table_files(table: NucleusTable) -> dict[str, bytes]:
    """`nucleus-table.csv`, `columns.csv` and the authoritative `nucleus-table.json`."""
    names, rows, definitions = nucleus_table_csv_rows(table)
    files = {}
    for name, (data, columns) in {"nucleus-table.csv": (rows, names),
                                  "columns.csv": (definitions, ["column", "unit", "definition", "channel_id",
                                                                "channel_label", "stain"])}.items():
        stream = io.StringIO()
        write_csv_stream(stream, data, columns=columns)
        files[name] = b"\xef\xbb\xbf" + stream.getvalue().encode("utf-8")
    files["nucleus-table.json"] = json.dumps(table.model_dump(mode="json"), ensure_ascii=False, indent=1).encode("utf-8")
    return files
