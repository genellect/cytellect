"""Public JUMP source-table checks; no cell-like synthetic images or tuning.

Protocol error cases use minimal synthetic scalar byte offsets only: they cannot
be induced reliably with the immutable public server and have no biological role.
Extraction and missing/duplicate-row tests use the registered public table rows.
"""
from __future__ import annotations

import csv
import gzip
import importlib.util
import io
import json
import math
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("public_jump_cellprofiler", ROOT / "scripts/public_jump_cellprofiler.py")
assert SPEC and SPEC.loader
PUBLIC = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PUBLIC)
REFERENCE = json.loads((ROOT / "fixtures/public/jump-plk1/cellprofiler-reference.json").read_text())


def test_registered_public_selection_and_filename_site():
    assert REFERENCE["status"] == "verified_extraction"
    assert REFERENCE["license"] == "CC0-1.0"
    image_files = json.loads((ROOT / "fixtures/public/jump-plk1/files.json").read_text())["files"]
    registered = {f["name"] for f in image_files}
    assert [p["plate"] for p in REFERENCE["plates"]] == [p for _, p in PUBLIC.RUNS]
    for plate in REFERENCE["plates"]:
        fields = plate["selected_fields"]
        assert len(fields) == 6
        assert {(r["values"]["Metadata_Well"], int(r["values"]["Metadata_Site"])) for r in fields} == {
            (w, s) for w in ("A02", "A23") for s in (3, 4, 5)}
        for entry in fields:
            row = entry["values"]
            assert row["FileName_OrigDNA"] in registered
            assert int(re.search(r"F(\d{3})L", row["FileName_OrigDNA"])[1]) == int(row["Metadata_Site"]) + 1
            assert float(row["Count_NucleiIncludingEdges"]) >= float(row["Count_Nuclei"])


def test_public_objects_complete_and_finite():
    assert REFERENCE["object_columns"] == PUBLIC.OBJECT_COLUMNS
    for plate in REFERENCE["plates"]:
        targets = {int(f["values"]["Image_ImageNumber"]): int(float(f["values"]["Count_Nuclei"]))
                   for f in plate["selected_fields"]}
        PUBLIC.validate_objects(plate["objects"], targets)
        assert len(plate["objects"]) == sum(targets.values())
        offsets = []
        for obj in plate["objects"]:
            values = [float(v) for v in obj["values"]]
            assert all(math.isfinite(v) for v in values)
            assert values[4] <= values[2] < values[6]
            assert values[5] <= values[3] < values[7]
            assert values[8] > 0
            assert 0 <= values[9] <= 1 and 0 <= values[10] <= 1
            assert re.fullmatch(r"[a-f0-9]{64}", obj["raw_row_sha256"])
            offsets.append(obj["byte_offset"])
        assert len(set(offsets)) == len(offsets)


@pytest.mark.parametrize("duplicate", [False, True])
def test_public_object_missing_or_duplicate_is_not_complete(duplicate):
    plate = REFERENCE["plates"][0]
    field = plate["selected_fields"][0]["values"]
    image_id = int(field["Image_ImageNumber"])
    rows = [r for r in plate["objects"] if int(r["values"][0]) == image_id]
    invalid = rows + rows[:1] if duplicate else rows[1:]
    with pytest.raises(ValueError, match="incomplete/duplicate"):
        PUBLIC.validate_objects(invalid, {image_id: int(float(field["Count_Nuclei"]))})


def test_public_all_well_summary_uses_every_metadata_assigned_field():
    well_rows = next(m for m in REFERENCE["metadata"] if m["url"].endswith("well.csv.gz"))["selected_rows"]
    for plate in REFERENCE["plates"]:
        assigned = {r["values"]["Metadata_Well"]: PUBLIC.GROUPS[r["values"]["Metadata_JCP2022"]]
                    for r in well_rows if r["values"]["Metadata_Plate"] == plate["plate"]}
        rows = plate["all_control_fields"]
        assert len(rows) == len(assigned) * 9
        expected_means = {}
        for group in PUBLIC.GROUPS.values():
            group_wells = sorted(w for w, g in assigned.items() if g == group)
            summary = plate["all_well_summary"]["groups"][group]
            assert summary["wells"] == group_wells
            for well in group_wells:
                assert sorted(int(r["values"]["Metadata_Site"]) for r in rows
                              if r["values"]["Metadata_Well"] == well) == list(range(9))
            for column in ("Count_Nuclei", "Count_NucleiIncludingEdges"):
                counts = [int(float(r["values"][column])) for r in rows if r["group"] == group]
                mean = math.fsum(counts) / len(counts)
                assert summary[column] == {"sum": sum(counts), "mean_per_field": mean}
                expected_means[(group, column)] = mean
        for column in ("Count_Nuclei", "Count_NucleiIncludingEdges"):
            assert plate["all_well_summary"]["PLK1_divided_by_non_targeting"][column] == pytest.approx(
                expected_means[("PLK1", column)] / expected_means[("Non-targeting", column)], abs=1e-15)


def test_public_ranges_are_bounded_and_cover_every_extracted_row():
    for plate in REFERENCE["plates"]:
        source = plate["nuclei_source"]
        assert source["version_id"] and source["etag"]
        assert source["downloaded_bytes"] == sum(r["bytes"] for r in source["ranges"])
        assert source["downloaded_bytes"] < source["bytes"] / 10
        assert source["downloaded_bytes"] <= 512 * 1024 * 1024
        for request in source["ranges"]:
            assert request["bytes"] == request["end"] - request["start"] + 1
            assert request["bytes"] <= PUBLIC.BLOCK + PUBLIC.PROBE
        for row in plate["objects"]:
            assert any(r["start"] <= row["byte_offset"]
                       and row["byte_offset"] + row["bytes"] - 1 <= r["end"] for r in source["ranges"])


@pytest.mark.parametrize("status,header", [(200, "bytes 0-9/100"), (206, "bytes 0-99/100"),
                                           (206, "bytes 1-10/100"), (206, "bytes 0-9/101")])
def test_synthetic_scalar_range_protocol_rejects_unbounded_or_changed_source(status, header):
    with pytest.raises(ValueError, match="refusing body"):
        PUBLIC.validate_range(status, header, 0, 9, 100)


def test_synthetic_scalar_range_protocol_accepts_exact_response():
    PUBLIC.validate_range(206, "bytes 0-9/100", 0, 9, 100)


def test_public_row_projection_verifier_detects_value_and_hash_changes(tmp_path):
    # A projection of a registered public row, not a generated image or invented measurement.
    obj = REFERENCE["plates"][0]["objects"][0]
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\r\n")
    writer.writerow(PUBLIC.OBJECT_COLUMNS)
    writer.writerow(obj["values"])
    header, raw = stream.getvalue().encode().splitlines(keepends=True)
    path = tmp_path / "public-projection.csv.gz"
    with gzip.open(path, "wb") as out:
        out.write(header + raw)
    record = {"values": obj["values"], "raw_row_sha256": PUBLIC.digest(raw), "bytes": len(raw)}
    PUBLIC.verify_raw(path, PUBLIC.digest(header), [record], PUBLIC.OBJECT_COLUMNS)
    with pytest.raises(ValueError, match="unexpected"):
        PUBLIC.verify_raw(path, PUBLIC.digest(header), [{**record, "raw_row_sha256": "0" * 64}], PUBLIC.OBJECT_COLUMNS)
    changed = list(obj["values"])
    changed[-1] = "0"
    with pytest.raises(ValueError, match="values differ"):
        PUBLIC.verify_raw(path, PUBLIC.digest(header), [{**record, "values": changed}], PUBLIC.OBJECT_COLUMNS)


def test_public_partial_line_does_not_create_an_object():
    row = REFERENCE["plates"][0]["objects"][0]
    raw = (",".join(row["values"]) + "\n").encode()
    fragment = raw[3:] + raw + raw[:7]
    assert list(PUBLIC.complete_lines(fragment, 3)) == [(len(raw), raw)]


def test_public_row_projection_extracts_unsorted_images_and_reuses_probes(tmp_path):
    """Reorder public CSV rows for a parser check; no measurements are invented."""
    plate = REFERENCE["plates"][0]
    rows = plate["objects"]
    targets = {int(f["values"]["Image_ImageNumber"]): int(float(f["values"]["Count_Nuclei"]))
               for f in plate["selected_fields"]}
    text = io.StringIO(newline="")
    writer = csv.writer(text, lineterminator="\n")
    writer.writerow(PUBLIC.OBJECT_COLUMNS)
    # Reverse the published image sequence and interleave even/odd objects.
    reordered = list(reversed(rows[::2])) + rows[1::2]
    writer.writerows(r["values"] for r in reordered)
    data = text.getvalue().encode()

    class PublicProjection:
        header = PUBLIC.OBJECT_COLUMNS
        header_raw = data.splitlines(keepends=True)[0]
        size = len(data)

        def get(self, start, end):
            return data[start:min(end + 1, len(data))]

    objects, _ = PUBLIC.extract_objects(PublicProjection(), targets, tmp_path / "public-unsorted.csv.gz")
    assert [r["values"] for r in objects] == [r["values"] for r in rows]
