from pathlib import Path

import pytest
from cytellect_analysis import install_check


def test_failed_installation_check_removes_only_owned_attempt(tmp_path, monkeypatch):
    existing = tmp_path / "preserved.txt"
    existing.write_text("keep")

    def failure(channels, recipe, output, fiji, **kwargs):
        Path(output).mkdir(parents=True)
        (Path(output) / "partial.tif").write_bytes(b"generated incomplete output")
        raise RuntimeError("fiji_execution_failed")

    monkeypatch.setattr(install_check, "detect", failure)
    with pytest.raises(RuntimeError, match="fiji_execution_failed"):
        install_check.verify_installation("unused", tmp_path)
    assert list(tmp_path.iterdir()) == [existing]
    assert existing.read_text() == "keep"
