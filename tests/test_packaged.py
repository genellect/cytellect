import json

import pytest
from cytellect_api.packaged import data_location


def test_store_reuses_installer_data_without_rewriting_its_ownership(tmp_path):
    root = tmp_path / "Cytellect"
    data = root / "data"
    data.mkdir(parents=True)
    marker = root / "setup-root.json"
    original = b'{"product":"cytellect-local","schema":1}'
    marker.write_bytes(original)
    assert data_location(tmp_path) == (data, False)
    assert marker.read_bytes() == original


def test_store_owns_fresh_location_and_reopens_with_manual_retention(tmp_path):
    assert data_location(tmp_path) == (tmp_path / "Cytellect/data", True)
    assert data_location(tmp_path) == (tmp_path / "Cytellect/data", True)
    owner = json.loads((tmp_path / "Cytellect/setup-root.json").read_bytes())
    assert owner["product"] == "cytellect-local"


def test_store_rejects_unowned_data(tmp_path):
    root = tmp_path / "Cytellect"
    root.mkdir()
    unrelated = root / "existing.txt"
    unrelated.write_bytes(b"unowned")
    with pytest.raises(ValueError, match="install_directory_not_owned"):
        data_location(tmp_path)
    assert tuple(root.iterdir()) == (unrelated,)
    assert unrelated.read_bytes() == b"unowned"
