"""License evidence gates retain metadata without inventing license identities."""
import hashlib
import importlib.util
import json
import sys
from email.message import Message
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).parents[1] / "scripts"
spec = importlib.util.spec_from_file_location("sbom", SCRIPTS / "sbom.py")
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
sys.path.insert(0, str(SCRIPTS))
try:
    spec.loader.exec_module(module)
finally:
    sys.path.pop(0)


class Distribution:
    def __init__(self, base, *, name="example", expression=None, text=None, classifiers=(), files=()):
        self.base, self.version, self.files = base, "1.0", files
        self.metadata = Message()
        self.metadata["Name"] = name
        if expression is not None:
            self.metadata["License-Expression"] = expression
        if text is not None:
            self.metadata["License"] = text
        for item in classifiers:
            self.metadata["Classifier"] = item

    def locate_file(self, entry):
        return self.base / str(entry)


@pytest.mark.parametrize("name,license_label", [
    ("colorama", "BSD License"), ("markdown-it-py", "MIT License"), ("mdurl", "MIT License"),
    ("pathspec", "Mozilla Public License 2.0 (MPL 2.0)"),
    ("pip_audit", "Apache Software License"), ("tomli_w", "MIT License"),
])
def test_classifier_only_metadata_does_not_invent_spdx(tmp_path, name, license_label):
    classifier = f"License :: OSI Approved :: {license_label}"
    result = module.python_component(Distribution(tmp_path, name=name, classifiers=[classifier]))
    assert result["license_evidence"]["classifiers"] == [classifier]
    assert result["license_evidence"]["expression"] is None
    assert "REVIEW_REQUIRED" not in json.dumps(result)


def test_notice_hashes_relative_and_license_text_preserved(tmp_path):
    relative = "example-1.0.dist-info/licenses/LICENSE.txt"
    notice = tmp_path / relative
    notice.parent.mkdir(parents=True)
    raw = b"Copyright example\nPermission granted.\n"
    notice.write_bytes(raw)
    result = module.python_component(Distribution(tmp_path, expression="MIT", text="Declared license text",
                                                files=[relative]))
    assert result["license_evidence"]["files"] == [
        {"path": relative, "sha256": hashlib.sha256(raw).hexdigest(), "size_bytes": len(raw)}]
    assert result["license_evidence"]["text"] == "Declared license text"
    assert str(tmp_path) not in json.dumps(result)
    assert module.python_component(Distribution(tmp_path, files=[relative]))["license_evidence"]["files"]


@pytest.mark.parametrize("text", [None, "UNKNOWN", "", "REVIEW_REQUIRED"])
def test_no_declared_evidence_fails_closed(tmp_path, text):
    with pytest.raises(ValueError, match="dependency_license_evidence_missing"):
        module.python_component(Distribution(tmp_path, text=text))


@pytest.mark.parametrize("name", ["../LICENSE", "/LICENSE", "C:/private/LICENSE", "..\\LICENSE"])
def test_external_notice_paths_rejected(tmp_path, name):
    with pytest.raises(ValueError, match="dependency_notice_path_invalid"):
        module.python_component(Distribution(tmp_path, expression="MIT", files=[name]))


def test_private_metadata_path_rejected_without_copying_value(tmp_path):
    with pytest.raises(ValueError, match="^dependency_metadata_contains_private_path$"):
        module.python_component(Distribution(tmp_path, text="License at C:\\Users\\example\\LICENSE"))


def test_empty_notice_is_recorded_but_does_not_satisfy_license_evidence(tmp_path):
    (tmp_path / "LICENSE").write_bytes(b"")
    with pytest.raises(ValueError, match="dependency_license_evidence_missing"):
        module.python_component(Distribution(tmp_path, files=["LICENSE"]))
    result = module.python_component(Distribution(tmp_path, expression="MIT", files=["LICENSE"]))
    assert result["license_evidence"]["files"][0]["size_bytes"] == 0


def web_fixture(root):
    (root / "apps/web").mkdir(parents=True)
    (root / "apps/web/package.json").write_text(json.dumps({"dependencies": {"react": "1", "next": "1"}}))
    for name in ("react", "react-dom", "next"):
        package = root / f"node_modules/.pnpm/{name}@1/node_modules/{name}"
        package.mkdir(parents=True)
        (package / "package.json").write_text(json.dumps({"name": name, "version": "1", "license": "MIT"}))
        (package / "LICENSE").write_text("Copyright example\nMIT notice")
    (root / "engines/fiji").mkdir(parents=True)
    (root / "engines/fiji/runtime.lock.json").write_text(json.dumps({"model": {"sha256": "a" * 64}}))
    for name in ("uv.lock", "pnpm-lock.yaml"):
        (root / name).write_text("locked dependencies")


def test_combined_inventory_uses_actual_web_notice_gate_and_fiji_lock(tmp_path):
    web_fixture(tmp_path)
    dist = Distribution(tmp_path, expression="Apache-2.0")
    result, notices = module.inventory(tmp_path, [dist])
    assert result["schema"] == "cytellect-dependency-inventory/2"
    assert {p["name"] for p in result["web"]["packages"]} == {"react", "react-dom", "next"}
    assert result["web"]["notice_count"] == 3 and "MIT notice" in notices
    assert result["fiji"]["model"]["sha256"] == "a" * 64
    assert set(result["lockfiles"]) == {"uv.lock", "pnpm-lock.yaml"}
    assert str(tmp_path) not in json.dumps(result) + notices
    (tmp_path / "node_modules/.pnpm/react@1/node_modules/react/LICENSE").unlink()
    with pytest.raises(ValueError, match="web_licenses_required_license_text_missing"):
        module.inventory(tmp_path, [dist])
