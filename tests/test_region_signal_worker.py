"""Signal candidates reuse image storage but retain separate immutable masks."""
import numpy as np
from cytellect_analysis.region_contracts import RegionSignalRecipe
from cytellect_analysis.region_exports import region_methods
from cytellect_api.storage import read_json
from cytellect_worker import regions
from test_region_nuclear_worker import detected_labels, install_detector, nuclear_fields
from test_region_worker import execute


def test_signal_revision_measures_selected_channel_and_preserves_nuclei(tmp_path, monkeypatch):
    store, settings, nuclear = nuclear_fields(tmp_path)
    install_detector(monkeypatch)
    execute(store, settings, nuclear, "nuclear")
    calls = []
    def detect(image, parameters, destination, executable, scratch_root=None):
        calls.append(image.copy())
        assert parameters.threshold_method == "otsu"
        return detected_labels(), {"operation": "signal-only", "status": "candidate", "parameters": parameters.model_dump(mode="json")}
    monkeypatch.setattr(regions, "detect_positive_regions", detect)
    config = {**nuclear, "recipe": RegionSignalRecipe(region_set_id="marker_positive", label="Marker-positive areas", defining_channel_id="actin").model_dump(mode="json")}
    report = execute(store, settings, config, "signal")
    assert report["field_failures"] == [] and len(calls) == 1
    assert report["field_masks"]["f1"]["source"] == "fiji_positive_regions"
    methods = region_methods(config, report, read_json(store.safe_path("results", "signal", "provenance.json")))
    assert "exploratory signal-positive areas" in methods
    assert "no automatic detector was executed" not in methods

    assert {row["mean"] for row in report["field_tables"]["f1"]["rows"] if row["channel_id"] == "actin"} == {26, 40}
    assert read_json(store.safe_path("results", "nuclear", "measurements.json"))["field_masks"]["f1"]["source"] == "stardist_nuclear"
    again = execute(store, settings, {**config, "reuse_revision": "signal"}, "remeasured")
    assert again["field_failures"] == [] and len(calls) == 1
    assert read_json(store.safe_path("results", "remeasured", "provenance.json"))["fields"]["f1"]["detector"]["executed_this_attempt"] is False
    np.testing.assert_array_equal(calls[0], np.load(store.safe_path("workspaces", "w", "fields", "f1", "channel-actin.npy")))


def test_uniform_otsu_is_indeterminate_not_negative_or_zero_measurement(tmp_path, monkeypatch):
    store, settings, config = nuclear_fields(tmp_path)
    config["recipe"] = RegionSignalRecipe(region_set_id="signal", label="Signal areas", defining_channel_id="actin").model_dump(mode="json")
    monkeypatch.setattr(regions, "detect_positive_regions", lambda *args, **kwargs: (np.zeros((8, 8), dtype=np.uint32), {"status": "indeterminate"}))
    report = execute(store, settings, config)
    assert report["field_tables"] == {}
    assert report["field_failures"] == [{"field_id": "f1", "reason": "signal_threshold_indeterminate"}]
    assert read_json(store.safe_path("results", "r1", "provenance.json"))["fields"]["f1"]["detector"]["engine"]["status"] == "indeterminate"
