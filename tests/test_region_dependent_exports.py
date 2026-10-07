"""Original-pixel replay includes automatic background and adopted parent masks."""
import numpy as np
import pytest
from cytellect_analysis.region_contracts import RegionCompartmentRecipe
from cytellect_analysis.region_exports import replay_region_bundle
from cytellect_api.db import jobs, revisions
from cytellect_api.storage import read_json, write_json
from cytellect_worker import regions
from sqlalchemy import update
from test_region_area_worker import execute_versioned
from test_region_compartment_worker import compartment_config
from test_region_nuclear_worker import install_detector, nuclear_fields
from test_region_worker import execute


@pytest.mark.parametrize("compartment", [False, True])
def test_automatic_background_bundle_replays_original_pixels_and_parent_masks(tmp_path, monkeypatch, compartment):
    store, settings, config = nuclear_fields(tmp_path)
    install_detector(monkeypatch)
    if compartment:
        execute(store, settings, config, "nuclear")
        def detect(**kwargs):
            nuclei = kwargs["nuclei"]
            children = np.zeros_like(nuclei)
            children[2, 2] = 1
            return {"nucleoli": children, "nucleoplasm": np.where(children, 0, nuclei)}, {"nucleolar_states": {"7": "candidate", "19": "candidate"}}
        monkeypatch.setattr(regions, "detect_compartments", detect)
        execute(store, settings, compartment_config(config), "nucleoli")
        config = {**config, "recipe": RegionCompartmentRecipe(region_set_id="nucleoplasm", label="Nucleoplasm", compartment="nucleoplasm", nuclear_revision_id="nuclear", nuclear_channel_id="dna", defining_channel_id="actin", nucleolar_revision_id="nucleoli").model_dump(mode="json")}
    config = {**config, "backgrounds": {}, "measurement": {"version": "1.2.0", "mode": "automatic_background"}}
    report = execute_versioned(store, settings, config, "measured")
    assert not report["field_failures"]
    if compartment:
        from cytellect_analysis.compartment_observations import describe_compartment_summary
        from cytellect_analysis.descriptive_contracts import parse_descriptive_request
        from cytellect_analysis.descriptive_figures import render_descriptive
        summary = read_json(store.safe_path("results", "measured", "f1", "compartment-summary.json"))
        spec = parse_descriptive_request({"mode": "descriptive", "selection": {
            "source": "compartment-summary", "version": "1.0.0", "region_set_id": "nucleoplasm",
            "metric": "nucleolar_count", "channel_id": None}})
        described = describe_compartment_summary(report, config["field_snapshot"], spec, {"f1": summary})
        described["revision_id"] = "measured"
        stat_root = store.safe_path("statistics")
        described["figure"] = render_descriptive(described, stat_root)
        write_json(stat_root / "result.json", described)
        with store.transaction() as conn:
            conn.execute(update(revisions).where(revisions.c.id == "measured").values(reviewed=True, review_record={"confirmed_at": 1.0}))
            conn.execute(jobs.insert().values(id="summary-stats", workspace_id="w", revision_id="measured",
                kind="statistics", state="succeeded", payload=spec.model_dump(mode="json"), created=1.0,
                result_dir=store.relative_path(stat_root)))
    output = store.safe_path("export")
    regions.run_region_export(store, {"revision_id": "measured", "workspace_id": "w", "payload": {"include_raw": True}}, output)
    bundle = output / "bundle"
    assert read_json(bundle / "manifest.json")["format"] == "cytellect-region-reproducibility/4"
    verified = replay_region_bundle(bundle, bundle / "raw", tmp_path / "replay")
    assert verified["matched_saved_measurements"]
    if compartment:
        assert verified["matched_saved_descriptions"]
        assert (bundle / "statistics" / "0" / "result.json").is_file()
        assert (bundle / "dependencies" / "f1" / "nuclear.npy").is_file()
        assert (bundle / "dependencies" / "f1" / "nucleolar.npy").is_file()
        with (bundle / "dependencies" / "f1" / "nuclear.npy").open("ab") as file:
            file.write(b"corrupt")
        with pytest.raises(ValueError, match="region_bundle_file_hash_mismatch"):
            replay_region_bundle(bundle, bundle / "raw", tmp_path / "replay-corrupt")
