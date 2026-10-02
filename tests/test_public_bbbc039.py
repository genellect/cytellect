"""Fixed, publicly licensed real fluorescence images: no user research data."""
import importlib.util
import os
from pathlib import Path

import numpy as np
import pytest
import tifffile

source = Path(__file__).resolve().parents[1] / "scripts/public_bbbc039.py"
spec = importlib.util.spec_from_file_location("public_bbbc039", source)
benchmark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmark)


def test_public_source_hashes_split_and_dimensions():
    manifest = benchmark.verify()
    assert manifest["license"] == "CC0-1.0"
    assert len(manifest["images"]) == 5
    for item in manifest["images"]:
        raw = tifffile.imread(benchmark.FIXTURE / item["image"]["path"])
        truth = benchmark.decode_ground_truth(benchmark.FIXTURE / item["mask"]["path"])
        assert raw.shape == truth.shape == (520, 696)
        assert raw.dtype == np.uint16
        assert np.unique(truth).size > 2
        score = benchmark.match_instances(truth, truth)
        assert score["f1"] == 1 and score["fp"] == score["fn"] == 0


def test_missing_predictions_report_false_negatives_on_real_annotations():
    item = benchmark.verify()["images"][0]
    truth = benchmark.decode_ground_truth(benchmark.FIXTURE / item["mask"]["path"])
    score = benchmark.match_instances(truth, np.zeros_like(truth))
    assert score["f1"] == 0
    assert score["fn"] == score["true_instances"] > 0


@pytest.mark.fiji
def test_real_fiji_on_fixed_public_dna_image(tmp_path):
    from cytellect_analysis.contracts import Recipe
    from cytellect_analysis.engine import detect
    executable = os.environ.get("CYTELLECT_FIJI_EXECUTABLE")
    if not executable:
        pytest.skip("Real Fiji not configured: public-image inference has not passed")
    item = benchmark.verify()["images"][0]
    original = tifffile.imread(benchmark.FIXTURE / item["image"]["path"])
    truth = benchmark.decode_ground_truth(benchmark.FIXTURE / item["mask"]["path"])
    nuclei, _, info = detect({"dapi": original, "ncl": np.zeros_like(original)}, Recipe(), tmp_path, executable)
    result = benchmark.match_instances(truth, nuclei)
    assert result["true_instances"] == 156
    assert result["f1"] >= 0.90  # Fixed-image regression, not a generalization claim.
    assert info["headless"] is True
