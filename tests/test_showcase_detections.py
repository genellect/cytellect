"""Showcase detector recording and replay: exact outputs, stable keys, visible misses."""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "services" / "showcase" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "services" / "showcase" / "src"))

from cytellect_analysis.region_contracts import NuclearDetectorSpec  # noqa: E402
from cytellect_showcase import detections  # noqa: E402
from cytellect_showcase.detections import (  # noqa: E402
    NOT_RECORDED,
    DetectionNotRecorded,
    install_recorder,
    install_replay,
    record_key,
)
from cytellect_worker import regions  # noqa: E402
from test_api_worker import HEADERS, authenticated  # noqa: E402
from test_region_api import tiff_bytes  # noqa: E402
from test_region_cohorts import finish_analysis  # noqa: E402

DETECTOR = {"engine": "fiji-stardist-2d", "model": "Versatile (fluorescent nuclei)",
            "percentile_low": 1, "percentile_high": 99.8, "probability": 0.5, "nms": 0.3}


@pytest.fixture(autouse=True)
def restore_detectors():
    yield
    detections.uninstall()
    regions.REGION_FIELD_ERRORS.discard(NOT_RECORDED)


def image():
    return np.arange(144, dtype=np.uint16).reshape(12, 12)


def fake_labels():
    labels = np.zeros((12, 12), np.uint32)
    labels[3:7, 3:7] = 1
    labels[8:11, 1:4] = 2
    return labels


def test_record_key_is_documented_and_stable():
    pixels = image()
    key = record_key("detect_nuclei", {"image": pixels}, DETECTOR)
    assert key == record_key("detect_nuclei", {"image": pixels.copy()}, NuclearDetectorSpec.model_validate(DETECTOR))
    assert key == record_key("detect_nuclei", {"image": np.asfortranarray(pixels)}, DETECTOR)
    digest = detections.array_digest(pixels)
    document = {"fn": "detect_nuclei", "arrays": {"image": digest},
                "detector": NuclearDetectorSpec.model_validate(DETECTOR).model_dump(mode="json"),
                "options": {"detection_max_side": None}}
    import hashlib
    expected = hashlib.sha256(json.dumps(document, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    assert key == expected
    different = {
        record_key("detect_nuclei", {"image": pixels.astype(np.uint8)}, DETECTOR),
        record_key("detect_nuclei", {"image": pixels.reshape(9, 16)}, DETECTOR),
        record_key("detect_nuclei", {"image": pixels + 1}, DETECTOR),
        record_key("detect_nuclei", {"image": pixels}, {**DETECTOR, "probability": 0.55}),
        record_key("detect_nuclei", {"image": pixels}, DETECTOR, 256),
        record_key("detect_positive_regions", {"image": pixels}, None),
    }
    assert key not in different and len(different) == 6


def test_round_trip_restores_labels_info_and_engine_files(tmp_path, monkeypatch):
    calls = []

    def fake_detect(image, parameters, output_dir, executable, scratch_root=None, *, detection_max_side=None):
        calls.append(detection_max_side)
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "engine-result.json").write_text('{"count": 2}')
        (output_dir / "nested").mkdir()
        (output_dir / "nested" / "nuclei.tif").write_bytes(b"labels")
        return fake_labels(), {"engine": "fake", "parameters": NuclearDetectorSpec.model_validate(parameters).model_dump()}

    monkeypatch.setattr("cytellect_worker.regions.detect_nuclei", fake_detect)
    recorder = install_recorder(tmp_path / "recordings")
    labels, info = regions.detect_nuclei(image(), DETECTOR, tmp_path / "run1" / "engine", "/fiji",
                                         scratch_root=tmp_path, detection_max_side=96)
    assert calls == [96] and len(recorder.index["entries"]) == 1
    detections.uninstall()

    def forbidden(*args, **kwargs):
        raise AssertionError("replay must not run a detector")

    monkeypatch.setattr("cytellect_worker.regions.detect_nuclei", forbidden)
    install_replay(tmp_path / "recordings")
    output = tmp_path / "elsewhere" / "engine"
    replayed, replayed_info = regions.detect_nuclei(image(), NuclearDetectorSpec.model_validate(DETECTOR), output, "",
                                                    detection_max_side=96)
    assert np.array_equal(replayed, labels) and replayed.dtype == np.uint32
    assert replayed_info == info
    assert (output / "engine-result.json").read_text() == '{"count": 2}'
    assert (output / "nested" / "nuclei.tif").read_bytes() == b"labels"
    with pytest.raises(DetectionNotRecorded) as missing:
        regions.detect_nuclei(image(), DETECTOR, output, "", detection_max_side=None)
    assert str(missing.value) == NOT_RECORDED
    assert NOT_RECORDED in regions.REGION_FIELD_ERRORS


def test_compartments_record_all_masks_and_python_only_definitions_execute(tmp_path, monkeypatch):
    nuclei = fake_labels()
    channels = {"dapi": image(), "ncl": image()[::-1].copy()}
    executed = []

    def fake_compartments(channels, nuclei, parameters, output_dir, executable, scratch_root=None):
        executed.append(parameters if isinstance(parameters, dict) else parameters.model_dump())
        nucleoli = np.where(nuclei == 1, 5, 0).astype(np.uint32)
        return {"nucleoli": nucleoli, "nucleoplasm": np.where(nucleoli, 0, nuclei).astype(np.uint32)}, {"engine": "fake"}

    monkeypatch.setattr("cytellect_worker.regions.detect_compartments", fake_compartments)
    legacy = {"engine": "fiji-nucleolar-compartments", "protocol_version": "1.1.0", "threshold_method": "otsu",
              "threshold": None, "smoothing_sigma_px": 0, "minimum_area_px": 1, "maximum_area_px": None,
              "split_touching": False}
    install_recorder(tmp_path / "rec")
    recorded, _ = regions.detect_compartments(channels=channels, nuclei=nuclei, parameters=legacy,
                                              output_dir=tmp_path / "a", executable="")
    regions.detect_compartments(channels=channels, nuclei=nuclei, parameters=_ncl_objects(),
                                output_dir=tmp_path / "b", executable="")
    index = json.loads((tmp_path / "rec" / "index.json").read_text())
    assert [entry["fn"] for entry in index["entries"].values()] == ["detect_compartments"]
    assert sorted(next(iter(index["entries"].values()))["outputs"]) == ["nucleoli", "nucleoplasm"]
    detections.uninstall()
    executed.clear()
    install_replay(tmp_path / "rec")
    masks, info = regions.detect_compartments(channels=channels, nuclei=nuclei, parameters=legacy,
                                              output_dir=tmp_path / "c", executable="")
    assert executed == [] and info == {"engine": "fake"}
    assert all(np.array_equal(masks[name], recorded[name]) for name in recorded)
    regions.detect_compartments(channels=channels, nuclei=nuclei, parameters=_ncl_objects(),
                                output_dir=tmp_path / "d", executable="")
    assert len(executed) == 1
    with pytest.raises(DetectionNotRecorded):
        regions.detect_compartments(channels=channels, nuclei=nuclei, parameters={**legacy, "minimum_area_px": 2},
                                    output_dir=tmp_path / "e", executable="")


def _ncl_objects():
    from cytellect_analysis.ncl_objects import NclObjectDetector

    return NclObjectDetector()


def _nuclear_upload(client, wid):
    upload = client.post(f"/v1/workspaces/{wid}/region-fields", headers=HEADERS, data={"specification": json.dumps({
        "version": "1.1.0", "channels": [{"channel_id": "ch1", "label": "DNA", "stain": "DAPI",
                                          "identity_source": "filename"}]})},
        files={"ch0": ("fixture.tif", tiff_bytes(image()), "image/tiff")})
    assert upload.status_code == 201, upload.text
    return upload.json()["id"]


def _nuclear_request(fid, probability=0.5):
    return {"field_ids": [fid], "measurement": {"version": "1.1.0", "mode": "raw_intensity"}, "backgrounds": {},
            "recipe": {"version": "1.2.0", "region_set_id": "nuclei", "label": "Nuclei", "source": "stardist_nuclear",
                       "defining_channel_id": "ch1", "nuclear_role_source": "recorded_stain",
                       "detector": {**DETECTOR, "probability": probability}}}


def test_worker_replays_recorded_measurement_and_reports_missing_code(tmp_path, monkeypatch):
    monkeypatch.setattr("cytellect_worker.regions.detect_nuclei",
                        lambda *args, **kwargs: (fake_labels(), {"engine": "test-fixture"}))
    client, app, settings = authenticated(tmp_path / "build")
    wid = client.post("/v1/workspaces", json={"title": "record"}, headers=HEADERS).json()["id"]
    fid = _nuclear_upload(client, wid)
    install_recorder(tmp_path / "recordings")
    assert client.post(f"/v1/workspaces/{wid}/region-analyses", json=_nuclear_request(fid), headers=HEADERS).status_code == 202
    recorded = finish_analysis(app, settings)
    assert recorded["field_failures"] == []
    detections.uninstall()

    monkeypatch.setattr("cytellect_worker.regions.detect_nuclei",
                        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("no detector in replay")))
    install_replay(tmp_path / "recordings")
    client, app, settings = authenticated(tmp_path / "browser")
    wid = client.post("/v1/workspaces", json={"title": "replay"}, headers=HEADERS).json()["id"]
    fid = _nuclear_upload(client, wid)
    assert client.post(f"/v1/workspaces/{wid}/region-analyses", json=_nuclear_request(fid), headers=HEADERS).status_code == 202
    replayed = finish_analysis(app, settings)
    keys = ("region_id", "channel_id", "area_px", "mean", "median", "integrated")
    rows = [{key: row[key] for key in keys} for row in replayed["field_tables"][fid]["rows"]]
    expected = [{key: row[key] for key in keys} for row in next(iter(recorded["field_tables"].values()))["rows"]]
    assert rows == expected and len(rows) == 2
    assert client.post(f"/v1/workspaces/{wid}/region-analyses", json=_nuclear_request(fid, 0.7),
                       headers=HEADERS).status_code == 202
    missing = finish_analysis(app, settings)
    assert missing["field_tables"] == {}
    assert missing["field_failures"] == [{"field_id": fid, "reason": NOT_RECORDED}]
