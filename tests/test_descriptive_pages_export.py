"""Saved paged artifacts survive export; replay records a separate rendering outcome."""
import json

import pytest
from cytellect_analysis.descriptive import describe_legacy, describe_regions
from cytellect_analysis.descriptive_contracts import parse_descriptive_request
from cytellect_analysis.descriptive_output import render_descriptive_output
from cytellect_analysis.exports import build_export_bundle
from cytellect_analysis.images import sha256
from cytellect_analysis.region_exports import build_region_bundle, replay_region_bundle
from cytellect_analysis.replay import replay
from test_descriptive_export import package_inputs
from test_region_area_exports import descriptive, sources
from test_region_export import bundle_inputs

POLICY = {"version": "2.0.0", "layout": "field-pages"}


@pytest.mark.parametrize("tables_only", [False, True])
def test_area_bundle_preserves_saved_artifact_bytes_and_replay_separates_figure_status(tmp_path, tables_only):
    store, config, report = sources(tmp_path)
    spec = descriptive().model_dump(mode="json")
    spec.update(figure_policy=POLICY)
    spec["plot"].update(preset="nature-double", y_label="Unavailable \u0378" if tables_only else "")
    result = describe_regions(report, config["field_snapshot"], parse_descriptive_request(spec))
    result["revision_id"] = report["revision_id"]
    saved = tmp_path / "saved"
    result["figure"] = render_descriptive_output(result, saved)
    assert result["figure"]["status"] == ("tables_only" if tables_only else "ready")
    original_hashes = {path.name: sha256(path) for path in saved.iterdir()}
    output = tmp_path / "export"
    build_region_bundle(output, **bundle_inputs(store, config, report), statistics_results=[result],
                        statistics_roots=[(0, saved)], include_raw=True)
    bundle = output / "bundle"
    recorded = json.loads((bundle / "statistics/0/result.json").read_text(encoding="utf-8"))
    assert recorded == result
    for filename in result["figure"]["source_files"]:
        assert (bundle / "statistics/0" / filename).read_bytes() == (saved / filename).read_bytes()
    verification = replay_region_bundle(bundle, bundle / "raw", tmp_path / "replayed")
    assert verification["matched_saved_measurements"] and verification["matched_saved_descriptions"]
    assert verification["descriptive_figures_ready"] is not tables_only
    assert original_hashes == {path.name: sha256(path) for path in saved.iterdir()}
    rendered = tmp_path / "replayed/statistics/0"
    receipt = json.loads((rendered / "descriptive-output-verification.json").read_text(encoding="utf-8"))
    assert receipt["matched_saved_description"] and receipt["matched_page_mapping"]
    assert receipt["saved_figure_status"] == receipt["replayed_figure_status"] == result["figure"]["status"]
    source = json.loads((rendered / "figure-data.json").read_text(encoding="utf-8"))
    assert [row["value"] for row in source["plot_data"]] == [2, 4, 7, 5]
    assert all(row["channel_id"] is None for row in source["plot_data"])
    assert source["counts"]["experimental_units"] is None
    assert "Background estimation and correction were not performed" in (rendered / "methods.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("tables_only", [False, True])
def test_legacy_bundle_preserves_policy_and_reports_unavailable_replay_after_writing_tables(tmp_path, tables_only):
    report, config, masks, files, legacy = package_inputs(tmp_path)
    spec = {**legacy["spec"], "figure_policy": POLICY}
    spec["plot"] = {**spec["plot"], "preset": "nature-double", "y_label": "Unavailable \u0378" if tables_only else ""}
    result = describe_legacy(report, config["field_snapshot"], parse_descriptive_request(spec))
    result["revision_id"] = report["revision_id"]
    saved = tmp_path / "saved"
    result["figure"] = render_descriptive_output(result, saved)
    build_export_bundle(tmp_path / "export", report=report, config=config, provenance={}, field_masks=masks,
                        raw_files=files, statistics_results=[result], statistics_roots=[(0, saved)])
    bundle = tmp_path / "export/bundle"
    assert json.loads((bundle / "statistics/0/result.json").read_text(encoding="utf-8")) == result
    if tables_only:
        with pytest.raises(ValueError, match="descriptive_replay_figure_unavailable"):
            replay(bundle, tmp_path / "originals", tmp_path / "replayed")
    else:
        replay(bundle, tmp_path / "originals", tmp_path / "replayed")
    data = json.loads((tmp_path / "replayed/statistics/0/result.json").read_text(encoding="utf-8"))
    assert data["plot_data"] == result["plot_data"]
    assert data["plot_data"][0]["value"] == pytest.approx((38 * 30 + 4 * 90) / 42 - 10)
    assert data["counts"]["experimental_units"] is None
    assert (tmp_path / "replayed/statistics/0/plot-data.csv").is_file()


def test_new_export_refuses_missing_or_changed_private_artifact_index(tmp_path):
    store, config, report = sources(tmp_path)
    spec = descriptive().model_dump(mode="json")
    spec.update(figure_policy=POLICY)
    spec["plot"]["preset"] = "nature-double"
    result = describe_regions(report, config["field_snapshot"], spec)
    result["revision_id"] = report["revision_id"]
    saved = tmp_path / "saved"
    result["figure"] = render_descriptive_output(result, saved)
    with pytest.raises(ValueError, match="source_required"):
        build_region_bundle(tmp_path / "absent", **bundle_inputs(store, config, report), statistics_results=[result])
    index = saved / "descriptive-output.json"
    changed = json.loads(index.read_text(encoding="utf-8"))
    changed["style"]["font_size_pt"] = 6
    index.write_text(json.dumps(changed), encoding="utf-8")
    with pytest.raises(ValueError, match="manifest_mismatch"):
        build_region_bundle(tmp_path / "changed", **bundle_inputs(store, config, report), statistics_results=[result],
                            statistics_roots=[(0, saved)])
