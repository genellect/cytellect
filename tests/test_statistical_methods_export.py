"""Actual document bytes, complete ledgers and recorded template dispatch across replay."""
import copy
import hashlib
import json

import pytest
from cytellect_analysis.descriptive import describe_legacy, describe_regions
from cytellect_analysis.descriptive_contracts import PagedDescriptiveOutput
from cytellect_analysis.descriptive_output import render_descriptive_output, validate_descriptive_output
from cytellect_analysis.exports import build_export_bundle
from cytellect_analysis.region_comparison import compare_regions
from cytellect_analysis.region_comparison_figures import render_region_comparison
from cytellect_analysis.region_exports import build_region_bundle, replay_region_bundle
from cytellect_analysis.replay import replay
from cytellect_analysis.statistical_methods import CURRENT_METHODS_TEMPLATE
from pydantic import ValidationError
from test_descriptive_export import package_inputs
from test_descriptive_pages import description
from test_region_area_exports import comparison, descriptive, sources
from test_region_export import bundle_inputs

POLICY = {"version": "2.0.0", "layout": "field-pages"}
CURRENT = CURRENT_METHODS_TEMPLATE


@pytest.mark.parametrize("current", [False, True])
@pytest.mark.parametrize("paged", [False, True])
def test_native_bundle_keeps_recorded_methods_in_child_parent_and_replay(tmp_path, current, paged):
    report, config, masks, files, described = package_inputs(tmp_path)
    spec = described["spec"]
    if paged:
        spec = {**spec, "figure_policy": POLICY}
    result = describe_legacy(report, config["field_snapshot"], spec)
    result["revision_id"] = report["revision_id"]
    folder = tmp_path / "saved"
    result["figure"] = render_descriptive_output(result, folder, methods_template=CURRENT if current else None)
    original = {path.name: path.read_bytes() for path in folder.iterdir()}
    build_export_bundle(tmp_path / "export", report=report, config=config, provenance={}, field_masks=masks,
                        raw_files=files, statistics_results=[result], statistics_roots=[(0, folder)])
    bundle = tmp_path / "export/bundle"
    replay(bundle, tmp_path / "originals", tmp_path / "replayed")
    for base in (bundle, tmp_path / "replayed"):
        output = base / "statistics/0"
        assert (output / "methods.md").read_bytes() == original["methods.md"]
        assert (output / "figure-caption.md").read_bytes() == original["figure-caption.md"]
        assert (output / "selection.csv").read_bytes() == original["selection.csv"]
        saved = json.loads((output / "result.json").read_text())
        assert ("methods_template" in saved["figure"]) is current
        assert saved["plot_data"] == result["plot_data"] and saved["selection"] == result["selection"]
    top = (bundle / "methods.md").read_text(encoding="utf-8")
    assert ("cytellect-statistical-methods 1.0.0" in top) is current
    assert ("Selection: {" in top) is not current
    assert original == {path.name: path.read_bytes() for path in folder.iterdir()}


@pytest.mark.parametrize("paired", [False, True])
@pytest.mark.parametrize("current", [False, True])
def test_area_bundle_retains_all_numbers_and_its_methods_version_without_background(tmp_path, paired, current):
    store, config, report = sources(tmp_path)
    described = describe_regions(report, config["field_snapshot"], descriptive())
    described["revision_id"] = report["revision_id"]
    compared = compare_regions(report, config, comparison(paired))
    template = CURRENT if current else None
    described["figure"] = render_descriptive_output(described, tmp_path / "description", methods_template=template)
    compared["figure"] = render_region_comparison(compared, tmp_path / "comparison", methods_template=template)
    build_region_bundle(tmp_path / "export", **bundle_inputs(store, config, report),
                        statistics_results=[described, compared], include_raw=True)
    bundle = tmp_path / "export/bundle"
    verified = replay_region_bundle(bundle, bundle / "raw", tmp_path / "replayed")
    assert verified["matched_saved_descriptions"] and verified["matched_saved_comparisons"]
    for index, name in enumerate(("description", "comparison")):
        original = (tmp_path / name / "methods.md").read_bytes()
        for base in (bundle, tmp_path / "replayed"):
            out = base / "statistics" / str(index)
            assert (out / "methods.md").read_bytes() == original
            assert (out / "figure-caption.md").read_bytes() == (tmp_path / name / "figure-caption.md").read_bytes()
            text = (out / "methods.md").read_text(encoding="utf-8")
            assert "Background estimation and correction were not performed" in text
            assert "Fluorescence intensity and signal-saturation fractions were not measured" in text
            assert "Native negative" not in text
            source = json.loads((out / "figure-data.json").read_text(encoding="utf-8"))
            assert ("methods_template" in source) is current
    if current:
        text = (tmp_path / "comparison/methods.md").read_text(encoding="utf-8")
        assert "n=2 independent experimental units" in text
        assert ("2 complete pairs" in text) is paired
        assert ("Welch" in text) is not paired
    assert compared["comparisons"][0]["estimate"] == -3


def test_new_manifest_rejects_explicit_null_unknown_and_rehashed_incorrect_methods(tmp_path):
    result, _, _ = description(1)
    historical = render_descriptive_output(result, tmp_path / "historical")
    parsed = PagedDescriptiveOutput.model_validate(historical)
    assert parsed.model_dump(mode="json") == historical and "methods_template" not in historical
    for invalid in (None, {"id": "other", "version": "1.0.0"}, {"id": CURRENT.id, "version": "99.0.0"}):
        with pytest.raises(ValidationError):
            PagedDescriptiveOutput.model_validate({**historical, "methods_template": invalid})
    root = tmp_path / "current"
    result["figure"] = render_descriptive_output(result, root, methods_template=CURRENT)
    validate_descriptive_output(result, root, require_index=True)
    source = json.loads((root / "figure-data.json").read_text(encoding="utf-8"))
    assert source["methods_template"] == result["figure"]["methods_template"] == CURRENT.model_dump()
    incorrect = b"Invented independence and significant p-values.\n"
    (root / "methods.md").write_bytes(incorrect)
    altered = copy.deepcopy(result)
    altered["figure"]["files"]["methods.md"] = {"bytes": len(incorrect), "sha256": hashlib.sha256(incorrect).hexdigest()}
    (root / "descriptive-output.json").write_text(json.dumps(altered["figure"]), encoding="utf-8")
    with pytest.raises(ValueError, match="source_mismatch"):
        validate_descriptive_output(altered, root, require_index=True)
