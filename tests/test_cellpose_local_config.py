"""Optional local setup cannot redirect execution outside the private install."""
import json

from cytellect_api.local import local_cellpose_environment


def receipt(tmp_path, *, outside=False):
    root = tmp_path / "install"
    data = root / "data"
    python = (tmp_path if outside else root) / "runtime" / "python.exe"
    models = root / "models"
    python.parent.mkdir(parents=True)
    python.write_bytes(b"not executed by the receipt reader")
    models.mkdir(parents=True)
    config = root / "settings" / "cellpose.json"
    config.parent.mkdir()
    config.write_text(json.dumps({"schema": "cytellect-cellpose-local/1", "python": str(python),
                                 "model_dir": str(models)}), encoding="utf-8-sig")
    return data, config


def test_local_setup_loads_shared_runtime_without_executing_it(tmp_path):
    data, _ = receipt(tmp_path)
    env = local_cellpose_environment(data)
    assert set(env) == {"CYTELLECT_CELLPOSE_PYTHON", "CYTELLECT_CELLPOSE_MODEL_DIR"}
    assert "install" in env["CYTELLECT_CELLPOSE_PYTHON"]


def test_local_setup_rejects_path_escape_and_bad_optional_config(tmp_path):
    data, config = receipt(tmp_path, outside=True)
    assert local_cellpose_environment(data) == {}
    config.write_text("invalid-json", encoding="utf-8")
    assert local_cellpose_environment(data) == {}
    config.write_text("x" * 16_385, encoding="utf-8")
    assert local_cellpose_environment(data) == {}
