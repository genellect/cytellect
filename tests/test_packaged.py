import json

import pytest
from cytellect_api.local import local_retention_mode
from cytellect_api.packaged import data_location


def test_store_reuses_installer_data_without_rewriting_its_ownership(tmp_path):
    root = tmp_path / "Cytellect"
    data = root / "data"
    data.mkdir(parents=True)
    marker = root / "setup-root.json"
    original = b'{"product":"cytellect-local","schema":1}'
    marker.write_bytes(original)
    assert data_location(tmp_path) == data
    assert marker.read_bytes() == original
    assert not (root / "settings").exists()  # the installer's retention choice is left as recorded


def test_store_owns_fresh_location_and_reopens_with_manual_retention(tmp_path):
    data = tmp_path / "Cytellect/data"
    assert data_location(tmp_path) == data
    assert data_location(tmp_path) == data
    # Released installers and their storage collection accept exactly this marker.
    assert json.loads((tmp_path / "Cytellect/setup-root.json").read_bytes()) == {"product": "cytellect-local", "schema": 1}
    assert local_retention_mode(data) == "manual"


def test_store_finishes_its_own_interrupted_first_start(tmp_path):
    (tmp_path / "Cytellect/settings").mkdir(parents=True)
    assert data_location(tmp_path) == tmp_path / "Cytellect/data"
    assert (tmp_path / "Cytellect/setup-root.json").is_file()


def test_store_rejects_unowned_data(tmp_path):
    root = tmp_path / "Cytellect"
    root.mkdir()
    unrelated = root / "existing.txt"
    unrelated.write_bytes(b"unowned")
    with pytest.raises(ValueError, match="install_directory_not_owned"):
        data_location(tmp_path)
    assert tuple(root.iterdir()) == (unrelated,)
    assert unrelated.read_bytes() == b"unowned"
