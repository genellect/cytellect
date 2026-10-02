"""Distribution notices must include actual texts and bundled vendor notices."""
import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("web_licenses", Path(__file__).parents[1] / "scripts/web_licenses.py")
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def fixture(tmp_path):
    web = tmp_path / "apps/web"
    web.mkdir(parents=True)
    (web / "package.json").write_text(json.dumps({"dependencies": {"react": "1", "next": "1"}}))
    packages = {}
    for name in ("react", "react-dom", "next", "dev-tool"):
        package = tmp_path / f"node_modules/.pnpm/{name}@1/node_modules/{name}"
        package.mkdir(parents=True)
        (package / "package.json").write_text(json.dumps({"name": name, "version": "1", "license": "MIT"}))
        (package / "LICENSE").write_text("Copyright 著作者\nPermission granted.", encoding="utf-8")
        packages[name] = package
    return packages


def test_notices_include_vendor_and_dev_text_without_machine_paths(tmp_path):
    packages = fixture(tmp_path)
    vendor = packages["next"] / "dist/compiled/vendor"
    vendor.mkdir(parents=True)
    (vendor / "NOTICE.txt").write_text("Vendor attribution", encoding="utf-8")
    text, report = module.collect_notices(tmp_path)
    assert "overinclusive" in text and "dev-tool@1" in text
    assert "著作者" in text and "Vendor attribution" in text
    assert "dist/compiled/vendor/NOTICE.txt" in text
    assert str(tmp_path) not in text and str(tmp_path) not in json.dumps(report)
    assert report["notice_count"] == 5


def test_direct_dependency_license_must_have_actual_text(tmp_path):
    packages = fixture(tmp_path)
    (packages["react"] / "LICENSE").unlink()
    with pytest.raises(ValueError, match="required_license_text_missing: react"):
        module.collect_notices(tmp_path)


def test_utf8_bom_and_legacy_copyright_bytes_are_preserved(tmp_path):
    packages = fixture(tmp_path)
    (packages["react"] / "LICENSE").write_bytes(b"\xef\xbb\xbfMIT")
    (packages["next"] / "COPYING").write_bytes(b"Copyright \xa9 Owner")
    text, _ = module.collect_notices(tmp_path)
    assert "Copyright © Owner" in text and "Latin-1 byte-preserving" in text
    assert "\ufffd" not in text and "\ufeff" not in text
