"""Sanitized reference provenance and complete real-image comparison coverage."""
import hashlib
import json
from pathlib import Path


def test_public_ncl_reference_provenance_and_compartment_coverage():
    root = Path(__file__).resolve().parents[1]
    source = json.loads((root / "fixtures/public/nucleolar/manifest.json").read_text())
    report = json.loads((root / "fixtures/public/nucleolar/imagej-comparison.json").read_text())
    assert report["image_sha256"] == source["sha256"]
    assert report["channel_map"] == source["schema"]["channel_map"]
    assert report["channel_conflict"] == source["schema"]["channel_conflict"]
    bridge = (root / "engines/fiji/Bbbc013Reference.java").read_bytes().replace(b"\r\n", b"\n")
    assert report["reference_bridge_sha256"] == hashlib.sha256(bridge).hexdigest()
    assert {row["compartment"]: row["regions"] for row in report["compartments"]} == {"nucleus": 100, "nucleoli": 100, "nucleoplasm": 100, "object": 182}
    for row in report["compartments"]:
        assert len(row["rows"]) == row["regions"]
        errors = row["maximum_absolute_errors"]
        assert errors["raw_mean"] == errors["raw_median"] == errors["count"] == 0
        assert errors["corrected_integrated"] < 1e-6
    assert len(report["ratios"]) == 100
    assert sum(row["cytellect_ratio"] is None for row in report["ratios"]) == 2
    for row in report["ratios"]:
        if row["imagej_derived_ratio"] is None:
            assert row["cytellect_ratio"] is None and row["cytellect_log2_ratio"] is None
        else:
            assert abs(row["cytellect_ratio"] - row["imagej_derived_ratio"]) <= 1e-12
            assert abs(row["cytellect_log2_ratio"] - row["imagej_derived_log2_ratio"]) <= 1e-12
