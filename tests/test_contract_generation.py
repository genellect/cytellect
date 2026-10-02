import json
import sys

from cytellect_analysis.contracts import Recipe
from cytellect_api.cli import main


def test_generated_defaults_and_schema_have_the_authoritative_recipe(tmp_path, monkeypatch):
    monkeypatch.setenv("CYTELLECT_DATA_DIR", str(tmp_path / "private"))
    schema = tmp_path / "openapi.json"
    defaults = tmp_path / "web" / "recipe-defaults.json"
    monkeypatch.setattr(sys, "argv", [
        "cytellect", "openapi", "--output", str(schema), "--recipe-defaults", str(defaults),
    ])
    main()
    saved = json.loads(defaults.read_text(encoding="utf-8"))
    assert saved == Recipe().model_dump(mode="json")
    assert saved["native_signal_qc_minimum_ratio"] is None
    fields = json.loads(schema.read_text(encoding="utf-8"))["components"]["schemas"]["Recipe"]["properties"]
    assert set(saved) == set(fields)
