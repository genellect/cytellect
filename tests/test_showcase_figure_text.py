"""Public recorded results: prose changes preserve drawings and reject changed inputs."""
import copy
import hashlib
import json
import math
import shutil
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from cytellect_showcase.figure_catalog import build
from cytellect_showcase.figure_text import package_root, reuse_item

SNAPSHOT = Path(__file__).resolve().parents[1] / "apps/web/public/showcase/snapshot"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def published():
    document = read(SNAPSHOT / "figures.json")
    results = {}
    from cytellect_showcase.journal_files import read_journal

    # The opening snapshot answers the seed's saved results; the tour, the results its changes made.
    snapshot = [{"method": key.split(" ", 1)[0], "path": key.split(" ", 1)[1], "file": value.get("file")}
                for key, value in read(SNAPSHOT / "index.json")["entries"].items()]
    for entry in [*read_journal(SNAPSHOT)["entries"], *snapshot]:
        parts = entry["path"].split("/")
        if entry["method"] == "GET" and len(parts) == 5 and parts[2] == "jobs" and parts[4] in ("result", "common-statistics"):
            source = document["sources"].get(parts[3])
            if source and entry["file"]:
                results.setdefault(source["group"], read(SNAPSHOT / entry["file"]))
    return document, results


@pytest.fixture
def comparison(tmp_path, published):
    document, results = published
    seed_groups = {source["group"] for source in document["sources"].values() if source.get("seed")}
    identity = next(identity for identity in results
                    if document["groups"][identity]["opening"]["figure"].get("common_statistics_figure_version") == "2.0.0"
                    and results[identity]["analysis_kind"] == "region-comparison" and identity in seed_groups)
    previous, target = tmp_path / "previous", tmp_path / "target"
    previous.mkdir()
    target.mkdir()
    group = document["groups"][identity]
    for item in [group["opening"], *group["figures"]]:
        for name in item["files"].values():
            shutil.copyfile(SNAPSHOT / name, previous / name)
    job = "aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa"
    (previous / "figures.json").write_text(json.dumps({"groups": {identity: group}, "saved": {},
                                                       "sources": {job: {"group": identity}}, "packages": []}))
    (previous / "source-result.json").write_text(json.dumps(results[identity]), encoding="utf-8")
    (previous / "index.json").write_text(json.dumps({"entries": {f"GET /v1/jobs/{job}/common-statistics":
                                                                {"file": "source-result.json"}}}))
    (previous / "journal.json").write_text('{"entries":[]}')
    (target / "index.json").write_text('{"entries":{}}')
    (target / "journal.json").write_text('{"entries":[]}')
    result = copy.deepcopy(results[identity])
    data = tmp_path / "data"
    data.mkdir()
    result_path = data / "result.json"
    result_path.write_text(json.dumps(result))
    row = {"id": "aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa", "workspace_id": "public", "result_dir": str(data)}
    store = SimpleNamespace(rows=lambda table, **filters: [row] if filters["kind"] == "statistics" else [],
                            safe_path=Path)
    api = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(store=store)), settings=SimpleNamespace(data_dir=data))
    return api, previous, target, tmp_path / "scratch", identity, result_path


def test_catalogue_keeps_every_published_drawing_byte(comparison):
    api, previous, target, scratch, identity, _ = comparison
    before = read(previous / "figures.json")["groups"][identity]
    report = build(api, target, scratch, drawings=previous)
    after = read(target / "figures.json")["groups"][identity]
    assert report["groups"] == 1
    for old, new in zip([before["opening"], *before["figures"]], [after["opening"], *after["figures"]], strict=True):
        assert old["plot"] == new["plot"]
        for name, file in old["files"].items():
            if name != "figure-legend.md":
                assert new["files"][name] == file
                assert (previous / file).read_bytes() == (target / file).read_bytes()
        text = (target / new["files"]["figure-legend.md"]).read_text(encoding="utf-8")
        assert "→" not in text and "Fields and fields" not in text
        assert "n = " in text


@pytest.mark.parametrize("change", ["values", "tiny-values", "settings", "checksum", "nondefault-presentation"])
def test_changed_values_settings_or_assets_are_rejected(comparison, change):
    api, previous, target, scratch, identity, result_path = comparison
    if change in ("values", "tiny-values", "nondefault-presentation"):
        result = read(result_path)
        if change == "nondefault-presentation":
            result["spec"]["plot"]["presentation"] = {"version": "1.0.0", "outlines": False}
        else:
            value = result["unit_summary"][0]["value"]
            result["unit_summary"][0]["value"] = value + 1 if change == "values" else math.nextafter(value, math.inf)
        result_path.write_text(json.dumps(result))
    else:
        document = read(previous / "figures.json")
        if change == "settings":
            document["groups"][identity]["opening"]["plot"]["font_size"] += 1
            (previous / "figures.json").write_text(json.dumps(document))
        else:
            name = document["groups"][identity]["opening"]["files"]["figure.svg"]
            (previous / name).write_bytes(b"changed")
    with pytest.raises(ValueError, match={"values": "no identical published result", "tiny-values": "no identical published result",
                                         "nondefault-presentation": "no identical published result", "settings": "settings changed",
                                         "checksum": "checksum mismatch"}[change]):
        build(api, target, scratch, drawings=previous)


def test_explicit_defaults_and_new_capture_fingerprint_keep_the_same_drawing(comparison):
    from cytellect_analysis.common_statistics_contracts import FigurePresentation

    api, previous, target, scratch, identity, result_path = comparison
    result = read(result_path)
    result["source_fingerprint"] = "f" * 64
    result["spec"]["plot"]["presentation"] = FigurePresentation(version="1.0.0").model_dump(mode="json")
    result_path.write_text(json.dumps(result))
    report = build(api, target, scratch, drawings=previous)
    after = read(target / "figures.json")
    assert report["groups"] == 1
    assert set(after["drawing_origins"].values()) == {identity}


def test_package_prose_preserves_all_graphics_and_source_files(tmp_path, published):
    document, results = published
    entry = next(entry for entry in document["packages"] if document["sources"][entry["source"]]["group"] in results)
    identity = document["sources"][entry["source"]]["group"]
    item = document["groups"][identity]["figures"][entry["figure"]]
    target = tmp_path / "target"
    target.mkdir()
    def save(body, suffix):
        name = hashlib.sha256(body).hexdigest()[:24] + suffix
        (target / name).write_bytes(body)
        return name
    updated = reuse_item(SimpleNamespace(save=save), SNAPSHOT, results[identity], item)
    root = package_root(SNAPSHOT, document, identity, updated, target, tmp_path / "package")
    with zipfile.ZipFile(SNAPSHOT / entry["files"]["publication.zip"]) as archive:
        for name in item["figure"]["source_files"]:
            if name not in ("figure-legend.md", "figure-caption.md"):
                assert (root / name).read_bytes() == archive.read(f"edited-figure/{name}")
    assert (root / "figure-legend.md").read_bytes() == (target / updated["files"]["figure-legend.md"]).read_bytes()
