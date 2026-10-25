"""Integrity checks for public acquisition, not biological reference values."""
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("public_group_comparison", ROOT / "scripts/public_group_comparison.py")
assert spec and spec.loader
public = importlib.util.module_from_spec(spec)
spec.loader.exec_module(public)


def test_frozen_manifest_and_metadata_receipt():
    manifest = public.validate_manifest(json.loads(public.MANIFEST.read_text(encoding="utf-8")))
    assert len(manifest["files"]) == 18
    assert sum(f["metadata_sample"] for f in manifest["files"]) == 2
    receipt = json.loads((public.MANIFEST.parent / "ds6a-metadata-samples.json").read_text())
    assert receipt["manifest_sha256"] == hashlib.sha256(public.MANIFEST.read_bytes()).hexdigest()
    for row in receipt["files"]:
        item = next(f for f in manifest["files"] if f["name"] == row["name"])
        assert row["sha256"] == item["sha256"]
        assert row["metadata"]["series_shape"] == [4, 2304, 2304]
    assert not manifest["inference_allowed"]
    assert all(f["independent_experiment"] is None for f in manifest["files"])
    inventory = json.loads((public.MANIFEST.parent / "ds6a-source-inventory.json").read_text())
    assert len(inventory["files"]) == 180
    for rep in (1, 2, 3):
        for condition in ("Untreated", "ActD1"):
            candidates = sorted(f["name"] for f in inventory["files"] if f"_Rep{rep}_{condition}_" in f["name"])
            chosen = sorted(f["name"] for f in manifest["files"] if f"_Rep{rep}_{condition}_" in f["name"])
            assert chosen == candidates[:3]


@pytest.mark.parametrize("change", [{"name": "../bad.tif"}, {"url": "https://example.com/file"},
                                    {"md5": "invalid"}, {"bytes": -1}, {"sha256": "bad"}])
def test_reject_invalid_manifest(change):
    manifest = json.loads(public.MANIFEST.read_text(encoding="utf-8"))
    manifest["files"][0].update(change)
    with pytest.raises(ValueError):
        public.validate_manifest(manifest)


def test_hash_mismatch_never_overwrites_existing(tmp_path):
    item = {"name": "existing.tif", "bytes": 4, "md5": hashlib.md5(b"good", usedforsecurity=False).hexdigest()}
    target = tmp_path / item["name"]
    target.write_bytes(b"evil")
    with pytest.raises(ValueError, match="hash_mismatch"):
        public.acquire_one(tmp_path, item, download=True)
    assert target.read_bytes() == b"evil"


def test_download_truncation_does_not_publish(tmp_path, monkeypatch):
    import io
    item = {"name": "short.tif", "bytes": 4, "md5": hashlib.md5(b"good", usedforsecurity=False).hexdigest(), "url": "unused"}
    monkeypatch.setattr(public.urllib.request, "urlopen", lambda *a, **k: io.BytesIO(b"go"))
    with pytest.raises(ValueError, match="size_mismatch"):
        public.acquire_one(tmp_path, item, download=True)
    assert list(tmp_path.iterdir()) == []


def test_download_then_offline_verify(tmp_path, monkeypatch):
    import io
    item = {"name": "sample.tif", "bytes": 4, "md5": hashlib.md5(b"good", usedforsecurity=False).hexdigest(), "url": "unused"}
    monkeypatch.setattr(public.urllib.request, "urlopen", lambda *a, **k: io.BytesIO(b"good"))
    expected = hashlib.sha256(b"good").hexdigest()
    assert public.acquire_one(tmp_path, item, True) == expected
    assert public.acquire_one(tmp_path, item, False) == expected
