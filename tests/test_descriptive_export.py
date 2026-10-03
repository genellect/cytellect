"""Legacy measurement exports retain descriptive-only results and verify replay."""
import json
import zipfile

import pytest
from cytellect_analysis.descriptive import describe_legacy
from cytellect_analysis.descriptive_contracts import DescriptiveRequest
from cytellect_analysis.exports import build_export_bundle
from cytellect_analysis.images import sha256
from cytellect_analysis.replay import replay
from test_export import example


def package_inputs(tmp_path):
    report, config, masks, files = example(tmp_path)
    report["engine_provenance"] = {"field": {"engine": "supplied-masks"}}
    request = DescriptiveRequest.model_validate({"mode": "descriptive", "selection": {
        "source": "legacy-cell", "metric": "ncl_nucleus_mean_corrected"}})
    description = describe_legacy(report, config["field_snapshot"], request)
    description["revision_id"] = report["revision_id"]
    return report, config, masks, files, description


def test_single_nucleus_description_export_and_original_pixel_replay(tmp_path):
    report, config, masks, files, description = package_inputs(tmp_path)
    archive = build_export_bundle(tmp_path / "export", report=report, config=config, provenance={},
                                  field_masks=masks, raw_files=files, statistics_results=[description])
    with zipfile.ZipFile(archive) as opened:
        saved = json.loads(opened.read("statistics/0/result.json"))
        assert saved["plot_data"] == description["plot_data"]
        assert saved["counts"]["experimental_units"] is None
        assert "statistics/0/figure.svg" in opened.namelist()
        assert "statistics/0/comparisons.csv" not in opened.namelist()
        methods = opened.read("methods.md").decode()
        assert "No hypothesis test" in methods
        assert "All tests were two-sided" not in methods
    replay(tmp_path / "export/bundle", tmp_path / "originals", tmp_path / "replay")
    fresh = json.loads((tmp_path / "replay/statistics/0/result.json").read_text())
    assert fresh["plot_data"] == description["plot_data"]
    # 42 nuclear pixels: 38 at 30 and 4 at 90, minus background 10.
    assert fresh["plot_data"][0]["value"] == pytest.approx((38 * 30 + 4 * 90) / 42 - 10)
    assert fresh["field_summary"][0]["selected_rows"] == 1
    assert not (tmp_path / "replay/statistics/0/comparisons.csv").exists()


@pytest.mark.parametrize(("mutate", "error"), [
    (lambda r, c, d: d["plot_data"][0].update(value=999), "saved_result_mismatch"),
    (lambda r, c, d: d.update(revision_id="other"), "revision_mismatch"),
    (lambda r, c, d: d.update(comparisons=[]), "saved_result_mismatch"),
    (lambda r, c, d: c.update(review_record={}), "review_required"),
    (lambda r, c, d: c["review_record"].update(confirmed_at=True), "review_required"),
    (lambda r, c, d: c["review_record"].update(confirmed_at=float("nan")), "review_required"),
    (lambda r, c, d: r.update(invalidated_nucleoli=["field"]), "review_required"),
    (lambda r, c, d: c["field_ids"].append("unrecorded"), "revision_mismatch"),
])
def test_export_rejects_wrong_scientific_source_or_unreviewed_description(tmp_path, mutate, error):
    report, config, masks, files, description = package_inputs(tmp_path)
    mutate(report, config, description)
    with pytest.raises(ValueError, match=error):
        build_export_bundle(tmp_path / "export", report=report, config=config, provenance={},
                            field_masks=masks, raw_files=files, statistics_results=[description])


def test_replay_rejects_changed_description_even_when_package_hash_is_recomputed(tmp_path):
    report, config, masks, files, description = package_inputs(tmp_path)
    build_export_bundle(tmp_path / "export", report=report, config=config, provenance={},
                        field_masks=masks, raw_files=files, statistics_results=[description])
    bundle = tmp_path / "export/bundle"
    recorded = bundle / "statistics/0/result.json"
    modified = json.loads(recorded.read_text())
    modified["plot_data"][0]["value"] += 10
    recorded.write_text(json.dumps(modified), encoding="utf-8")
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["files"]["statistics/0/result.json"] = sha256(recorded)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="descriptive_saved_result_mismatch"):
        replay(bundle, tmp_path / "originals", tmp_path / "replay")
