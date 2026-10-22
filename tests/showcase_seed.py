"""Test-only showcase seed built by the normal CPython API on public BBBC013 pixels.

Detection is a deterministic stand-in (Otsu threshold + connected components),
never shipped and never a scientific claim: it only lets the runtime tests
exercise recorded-detection replay without Fiji. The four fields are crops of
two published wells; crops of one well are not independent replicates and are
used here only to drive the statistics code paths.
"""

from __future__ import annotations

import contextlib
import io
import json
import zipfile
from pathlib import Path

import numpy as np
import tifffile
from cytellect_api.app import create_app
from cytellect_api.config import Settings
from fastapi.testclient import TestClient

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures/public/bbbc013"
ORIGIN = "https://showcase.test"
HEADERS = {"origin": ORIGIN, "x-cytellect-request": "1"}
CROP = 160
FIELDS = [("A01", 0, 0), ("A01", 320, 320), ("A12", 0, 0), ("A12", 320, 320)]
CHANNELS = [
    {"channel_id": "dna", "label": "DRAQ", "stain": "DRAQ (DNA)", "identity_confirmed": True},
    {"channel_id": "gfp", "label": "GFP", "stain": "FKHR-EGFP", "identity_confirmed": True},
]


def fake_labels(image: np.ndarray) -> np.ndarray:
    from skimage.filters import threshold_otsu
    from skimage.measure import label
    from skimage.morphology import remove_small_objects

    mask = remove_small_objects(image > threshold_otsu(image), max_size=19)
    return label(mask, connectivity=1).astype(np.uint32)


def fake_detect_nuclei(image, parameters, destination, executable, scratch_root=None, detection_max_side=None):
    return fake_labels(np.asarray(image)), {
        "nuclear_detector_protocol_version": "1.0.0", "model": parameters.model,
        "model_sha256": "0" * 64, "parameters": parameters.model_dump(mode="json"),
        "test_stand_in": "otsu-connected-components",
    }


def _tiff(array: np.ndarray) -> bytes:
    buffer = io.BytesIO()
    tifffile.imwrite(buffer, array, photometric="minisblack")
    return buffer.getvalue()


def _crop(well: str, role: str, top: int, left: int) -> np.ndarray:
    return tifffile.imread(FIXTURE / f"{well}-{role}.tif")[top:top + CROP, left:left + CROP]


RECORDED_MODEL = "recorded-test-model"
DRAFT = {
    "recipe": "nuclear-intensity",
    "channels": [{"token": "ch1", "stain": "DRAQ (DNA)", "role": "nuclear", "reason": "核の領域を決める"},
                 {"token": "ch2", "stain": "FKHR-EGFP", "role": "measure", "reason": "測定対象"}],
    "metrics": [{"metric": "area", "channel": None, "region": "nucleus"},
                {"metric": "mean_raw", "channel": "ch2", "region": "nucleus"}],
    "statistics": {"kind": "descriptive", "test": None, "omnibus": None, "association": None},
    "figures": [{"kind": "field-distribution", "metric": "mean_raw", "channel": "ch2", "region": "nucleus"}],
    "missing_information": [], "reference_ids": ["senft-2023"], "rationale": "視野ごとの分布を示す。",
}


def record_proposals(store, wid: str, goals: dict[str, dict]) -> dict:
    """Recorded service payloads keyed by the context the API will send for each goal."""
    from cytellect_analysis.proposal_contracts import PROPOSAL_PROMPT_VERSION
    from cytellect_analysis.proposal_validation import context_sha256, validate_draft
    from cytellect_api.proposals import ProposalDraftRequest, _continuation_context, build_context

    entries = {}
    for goal, draft in goals.items():
        context, links = build_context(store, wid, goal)
        context = _continuation_context(context, links, ProposalDraftRequest(goal=goal, transmission_confirmed=True))
        validate_draft(context, draft, model=RECORDED_MODEL, prompt_version=PROPOSAL_PROMPT_VERSION)
        entries[context_sha256(context)] = {"model": RECORDED_MODEL, "prompt_version": PROPOSAL_PROMPT_VERSION,
                                            "draft": draft}
    return {"version": 1, "entries": entries}


@contextlib.contextmanager
def fake_detection():
    import cytellect_worker.regions as regions

    original = regions.detect_nuclei
    regions.detect_nuclei = fake_detect_nuclei
    try:
        yield
    finally:
        regions.detect_nuclei = original


def large_field(well: str, role: str, index: int) -> np.ndarray:
    """A 1536x1536 uint16 field (3x nearest-neighbour upsampling, x200) for memory checks only."""
    offset = 64 * index
    tile = tifffile.imread(FIXTURE / f"{well}-{role}.tif")[offset:offset + 512, offset:offset + 512]
    return np.kron(tile, np.ones((3, 3), dtype=np.uint8)).astype(np.uint16) * 200


def build_seed(directory: Path, *, proposals: dict | None = None, large: bool = False) -> tuple[bytes, dict]:
    """Return (seed zip bytes, identifiers) after one adopted nuclear run.

    ``large`` uses six 1536x1536 uint16 fields (three per well), the size of the
    public demo dataset, to measure browser memory; pixels are not scientific data.
    """
    from cytellect_showcase._executor import drain

    data = directory / "seed-data"
    settings = Settings(data, app_origin=ORIGIN, secure_cookies=False)
    app = create_app(settings)
    store = app.state.store
    client = TestClient(app, base_url=ORIGIN)
    assert client.post("/v1/invitations/redeem", headers=HEADERS, json={"token": store.invite()}).status_code == 200
    wid = client.post("/v1/workspaces", headers=HEADERS, json={"title": "BBBC013 showcase test"}).json()["id"]
    field_ids = []
    layout = [(well, index, 0) for well in ("A01", "A12") for index in range(3)] if large else FIELDS
    for index, (well, top, left) in enumerate(layout):
        specification = {"channels": CHANNELS, "metadata": {
            "condition": well, "sample": f"{well}-crop-{index}", "experimental_unit": f"{well}-crop-{index}",
            "acquisition_date": "batch-1"}}
        dna, gfp = ((large_field(well, "dapi", top), large_field(well, "gfp", top)) if large
                    else (_crop(well, "dapi", top, left), _crop(well, "gfp", top, left)))
        files = {"ch0": ("dna.tif", _tiff(dna), "image/tiff"), "ch1": ("gfp.tif", _tiff(gfp), "image/tiff")}
        response = client.post(f"/v1/workspaces/{wid}/region-fields", headers=HEADERS,
                               data={"specification": json.dumps(specification)}, files=files)
        assert response.status_code == 201, response.text
        field_ids.append(response.json()["id"])
    response = client.put(f"/v1/workspaces/{wid}/channel-assignments", headers=HEADERS, json={
        "version": 0, "assignments": [
            {"channel_id": "dna", "stain": "DRAQ (DNA)", "role": "nuclear"},
            {"channel_id": "gfp", "stain": "FKHR-EGFP", "role": "measure"}]})
    assert response.status_code == 200, response.text
    response = client.put(f"/v1/workspaces/{wid}/analysis-spec", headers=HEADERS, json={"version": 0, "spec": {
        "channel_assignment_version": response.json()["version"], "target": "nuclei",
        "settings": {"background": "raw"}}})
    assert response.status_code == 200, response.text
    response = client.post(f"/v1/workspaces/{wid}/runs", headers=HEADERS, json={
        "request_id": "seed-nuclei", "spec_version": response.json()["version"], "target": "nuclei",
        "field_ids": field_ids})
    assert response.status_code == 202, response.text
    run_id = response.json()["id"]
    recordings = data / "recordings"
    recordings.mkdir()
    with fake_detection(), contextlib.ExitStack() as stack:
        try:
            from cytellect_showcase import detections  # type: ignore[attr-defined]
        except ImportError:
            detections = None
        if detections is not None:
            # Record the stand-in in the shared format when the recorder exists.
            result = detections.install_recorder(recordings)
            if hasattr(result, "__exit__"):
                stack.enter_context(result)
        drain(store, settings)
    run = client.get(f"/v1/workspaces/{wid}/runs/{run_id}").json()
    assert run["state"] == "succeeded", run
    assert client.post(f"/v1/workspaces/{wid}/runs/{run_id}/accept", headers=HEADERS).status_code == 200
    revision_id = run["steps"][0]["revision_id"]
    selection = client.get(f"/v1/workspaces/{wid}/selection").json()
    metadata = {f["id"]: f["metadata"] for f in client.get(f"/v1/workspaces/{wid}/region-fields").json()}
    if proposals is not None:
        (data / "proposals.json").write_text(json.dumps(record_proposals(store, wid, proposals)), encoding="utf-8")
    store.engine.dispose()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(data.rglob("*")):
            relative = path.relative_to(data)
            if relative.parts[0] == "tmp" or not path.is_file():
                continue
            archive.write(path, relative.as_posix())
    return buffer.getvalue(), {"workspace_id": wid, "field_ids": field_ids, "run_id": run_id,
                               "revision_id": revision_id, "selection": selection, "metadata": metadata}
