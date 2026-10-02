"""Published GFP/DRAQ pixels and an independent, actual ImageJ reference."""
import importlib.util
import json
import os
from pathlib import Path

import numpy as np
import pytest
import tifffile

source = Path(__file__).resolve().parents[1] / "scripts/public_bbbc013.py"
spec = importlib.util.spec_from_file_location("public_bbbc013", source)
benchmark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmark)


def test_public_gfp_source_and_unchanged_samples():
    manifest = benchmark.verify()
    assert manifest["license"] == "CC-BY-3.0"
    assert [field["id"] for field in manifest["images"]] == ["A01", "A06", "A12"]
    for field in manifest["images"]:
        assert set(field["channels"]) == {"dapi", "gfp"}
        assert field["channels"]["dapi"]["stain"] == "DRAQ (DNA)"
        assert field["channels"]["gfp"]["stain"] == "FKHR-EGFP"


def test_published_reference_records_match_pinned_images_and_all_fields():
    manifest = benchmark.verify()
    report = json.loads((benchmark.FIXTURE / "benchmark.json").read_text())
    assert [row["id"] for row in report["fields"]] == [row["id"] for row in manifest["images"]]
    assert report["reference_bridge_sha256"] == benchmark.digest((source.parents[1] / "engines/fiji/Bbbc013Reference.java").read_bytes().replace(b"\r\n", b"\n"))
    for field, source_field in zip(report["fields"], manifest["images"], strict=True):
        assert field["source_channels"] == source_field["channels"]
        assert field["nuclei"] == len(field["rows"]) > 0
        assert field["maximum_absolute_errors"]["raw_mean"] <= 1e-10
        assert field["maximum_absolute_errors"]["raw_median"] == 0
        assert field["maximum_absolute_errors"]["corrected_integrated"] <= 1e-8
    assert any(row["gfp_corrected_mean"] < 0 for field in report["fields"] for row in field["rows"])


@pytest.mark.fiji
def test_actual_fiji_gfp_only_and_independent_imagej_measurement(tmp_path):
    from cytellect_analysis.contracts import Recipe
    from cytellect_analysis.engine import detect
    from cytellect_analysis.measurement import measure

    executable = os.environ.get("CYTELLECT_FIJI_EXECUTABLE")
    if not executable:
        pytest.skip("Actual Fiji not configured: independent public GFP reference NOT executed")
    field = benchmark.verify()["images"][1]  # Fixed A06 also exercises negative corrected signal.
    channels = {role: tifffile.imread(benchmark.FIXTURE / item["path"]) for role, item in field["channels"].items()}
    originals = {role: values.copy() for role, values in channels.items()}
    recipe = Recipe(id="gfp-nuclear-2d", gfp_gate="none")
    nuclei, nucleoli, _ = detect(channels, recipe, tmp_path / "engine", executable)
    assert not nucleoli.any() and not (tmp_path / "engine/ncl.tif").exists()
    assert all(np.array_equal(channels[role], original) for role, original in originals.items())
    offset, _ = benchmark.reference_offset(nuclei)
    cells, _, _ = measure(channels, nuclei, nucleoli, offset, recipe, {}, field["id"])
    labels = nuclei.copy()
    labels[offset] = 999999
    reference = benchmark.imagej_reference(benchmark.FIXTURE / field["channels"]["gfp"]["path"], labels, tmp_path / "reference", executable)
    lookup = {row["id"]: row for row in reference}
    background = lookup[999999]["median"]
    assert len(cells) > 100
    assert any(row["gfp_mean_corrected"] < 0 for row in cells)
    for row in cells:
        expected = lookup[row["nucleus_id"]]
        assert row["nucleus_area_px"] == expected["count"]
        assert row["gfp_mean"] == expected["mean"]
        assert row["gfp_median"] == expected["median_midpoint"]
        assert abs(row["gfp_integrated"] - expected["integrated"]) < 1e-8
        assert abs(row["gfp_mean_corrected"] - (expected["mean"] - background)) < 1e-10
        assert abs(row["gfp_integrated_corrected"] - (expected["integrated"] - expected["count"] * background)) < 1e-8
        assert row["ncl_nucleus_mean"] is None
        assert row["nucleolar_count"] is None
