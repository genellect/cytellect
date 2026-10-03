"""Builder isolation and exact-byte provenance, using invented non-research data."""
import copy
import hashlib
import importlib.util
import json
import stat
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("runtime_data", ROOT / "scripts/build_windows_runtime_data.py")
assert spec and spec.loader
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write_zip(path, entries):
    with zipfile.ZipFile(path, "w") as archive:
        for name, raw in entries.items():
            info = zipfile.ZipInfo(name)
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, raw)


def record(path):
    raw = path.read_bytes()
    return {"bytes": len(raw), "sha256": sha(raw)}


@pytest.fixture
def inputs(tmp_path):
    lock = json.loads(builder.LOCK.read_bytes())
    lock.pop("data_asset", None)
    root = tmp_path / "inputs"
    root.mkdir()
    parent = root / "parent.msi"
    parent.write_bytes(b"invented parent identity; not an MSI")
    lock["parent_msi"].update(record(parent))
    base_entries = {"python.exe": b"MZfake base", "LICENSE.txt": b"base license"}
    base = root / "base.zip"
    write_zip(base, base_entries)
    lock["python"].update(record(base))
    lock["python"].update(member_count=2, file_count=2,
                          expanded_bytes=sum(map(len, base_entries.values())),
                          launchers=[{"path": "python.exe", "sha256": sha(base_entries["python.exe"])}])
    contents = {}
    members = []
    for definition in lock["script_archives"]:
        kind = definition["id"]
        content = {f"{definition['prefix']}license.terms": f"{kind} original license\r\n".encode()}
        if kind == "tk":
            content["tk_library/icons.tcl"] = (
                b"# Original attribution https://creativecommons.org/licenses/by-sa/4.0/\n"
                b"# Author: synthetic fixture\nnamespace eval test {}\n")
        while len(content) < definition["member_count"]:
            number = len(content)
            content[f"{definition['prefix']}part{number:04}.tcl"] = f"# original script {number}\n".encode()
        contents[kind] = content
        path = root / f"{kind}.zip"
        write_zip(path, content)
        definition.update(record(path))
        for name, raw in content.items():
            members.append({"archive": kind, "member": name,
                            "path": definition["target_prefix"] + name[len(definition["prefix"]):],
                            "bytes": len(raw), "sha256": sha(raw)})
    for notice in lock["notices"]:
        if notice["scope"] == "base":
            raw = base_entries[notice["path"]]
        else:
            member = next(item for item in members if item["path"] == notice["path"])
            raw = contents[member["archive"]][member["member"]]
        notice.update(bytes=len(raw), sha256=sha(raw))
    manifest = {"schema": "cytellect-windows-runtime-members/1",
                "composition_version": lock["composition_version"], "files": members}
    manifest_path = root / "members.json"
    lock_path = root / "lock.json"
    state = {"root": root, "lock": lock, "manifest": manifest, "lock_path": lock_path,
             "manifest_path": manifest_path, "contents": contents}
    save(state)
    return state


def save(state):
    state["manifest_path"].write_bytes(builder.json_bytes(state["manifest"]))
    state["lock"]["members_manifest"]["sha256"] = sha(state["manifest_path"].read_bytes())
    state["lock_path"].write_bytes(builder.json_bytes(state["lock"]))


def refresh_archive(state, kind):
    path = state["root"] / f"{kind}.zip"
    write_zip(path, state["contents"][kind])
    next(a for a in state["lock"]["script_archives"] if a["id"] == kind).update(record(path))
    save(state)


def build(state, output=None):
    root = state["root"]
    return builder.build_data(root / "parent.msi", root / "base.zip", root / "tcl.zip", root / "tk.zip",
                              output or root.parent / "data.zip", lock_path=state["lock_path"],
                              members_path=state["manifest_path"])


def test_exact_roundtrip_notices_provenance_and_deterministic_bytes(inputs):
    before = {path.name: sha(path.read_bytes()) for path in inputs["root"].iterdir()}
    out = inputs["root"].parent / "data.zip"
    result = build(inputs, out)
    second = inputs["root"].parent / "second.zip"
    assert result == build(inputs, second)
    assert out.read_bytes() == second.read_bytes()
    assert result["script_count"] == 929
    assert result["member_count"] == 931
    with zipfile.ZipFile(out) as archive:
        assert len(archive.infolist()) == 931
        assert all(e.compress_type == zipfile.ZIP_STORED for e in archive.infolist())
        assert all(e.date_time == (2026, 1, 1, 0, 0, 0) for e in archive.infolist())
        manifest = json.loads(archive.read("runtime-data.json"))
        assert manifest["provenance"]["extraction_performed_by_builder"] is False
        assert "no extraction replay" in manifest["provenance"]["verification"]
        assert len(manifest["files"]) == 930
        for item in inputs["manifest"]["files"]:
            assert archive.read(item["path"]) == inputs["contents"][item["archive"]][item["member"]]
        for item in manifest["files"]:
            raw = archive.read(item["path"])
            assert len(raw) == item["bytes"] and sha(raw) == item["sha256"]
        notices = archive.read(builder.NOTICE_PATH)
        assert b"tcl original license\r\n" in notices and b"tk original license\r\n" in notices
        assert b"Author: synthetic fixture" in notices
        assert b"https://creativecommons.org/licenses/by-sa/4.0/legalcode" in notices
        assert not any(name.endswith((".exe", ".dll", ".msi")) for name in archive.namelist())
    assert out.with_suffix(".zip.sha256").read_text().strip() == f"{sha(out.read_bytes())}  data.zip"
    assert before == {path.name: sha(path.read_bytes()) for path in inputs["root"].iterdir()}


@pytest.mark.parametrize("name", ["parent.msi", "base.zip", "tcl.zip", "tk.zip"])
def test_pinned_input_tamper_rejected_before_output(inputs, name):
    path = inputs["root"] / name
    data = bytearray(path.read_bytes())
    data[-1] ^= 1
    path.write_bytes(data)
    with pytest.raises(ValueError, match="input_hash"):
        build(inputs)
    assert not (inputs["root"].parent / "data.zip").exists()


@pytest.mark.parametrize("name", ["/root", "../bad", "tcl_library/../bad", "C:/bad", "a\\b",
                                  "file:stream", "a//b", "a/./b", "NUL.txt", "a. ", "a\x00b"])
def test_unsafe_archive_paths(inputs, name):
    # ZIP writers truncate NUL names, so exercise the path contract directly.
    with pytest.raises(ValueError, match="unsafe_path"):
        builder.safe_name(name)


def test_duplicate_and_case_colliding_entries(inputs):
    content = inputs["contents"]["tcl"]
    content["tcl_library/LICENSE.terms"] = b"different name"
    refresh_archive(inputs, "tcl")
    with pytest.raises(ValueError, match="case_collision"):
        build(inputs)


@pytest.mark.parametrize("mode,attribute", [(stat.S_IFLNK | 0o777, 0), (stat.S_IFREG | 0o644, 0x400),
                                          (stat.S_IFDIR | 0o755, 0)])
def test_links_reparse_and_directory_entries_rejected(inputs, mode, attribute):
    path = inputs["root"] / "tcl.zip"
    with zipfile.ZipFile(path, "w") as archive:
        for number, (name, raw) in enumerate(inputs["contents"]["tcl"].items()):
            entry = zipfile.ZipInfo(name)
            entry.create_system = 3
            entry.external_attr = (mode << 16) | attribute if number == 0 else 0o100644 << 16
            archive.writestr(entry, raw)
    inputs["lock"]["script_archives"][0].update(record(path))
    save(inputs)
    with pytest.raises(ValueError, match="nonregular"):
        build(inputs)


@pytest.mark.parametrize("change", ["missing", "unexpected", "changed"])
def test_exact_members_and_member_hashes(inputs, change):
    content = inputs["contents"]["tcl"]
    name = next(n for n in content if "part" in n)
    if change == "missing":
        del content[name]
    elif change == "unexpected":
        content["tcl_library/unreviewed.tcl"] = b"unreviewed"
    else:
        content[name] = content[name].replace(b"original", b"changed!")
    refresh_archive(inputs, "tcl")
    with pytest.raises(ValueError, match="script_(members|hash)_mismatch"):
        build(inputs)


@pytest.mark.parametrize("kind", ["header", "extension"])
def test_executables_rejected_even_if_new_hashes_are_in_test_manifest(inputs, kind):
    item = next(m for m in inputs["manifest"]["files"] if "part" in m["member"])
    content = inputs["contents"]["tcl"]
    if kind == "header":
        content[item["member"]] = b"MZnot allowed in a script"
    else:
        old = item["member"]
        item["member"] = old + ".dll"
        item["path"] += ".dll"
        content[item["member"]] = content.pop(old)
    item.update(bytes=len(content[item["member"]]), sha256=sha(content[item["member"]]))
    refresh_archive(inputs, "tcl")
    with pytest.raises(ValueError, match="script_executable"):
        build(inputs)


def test_base_path_collision_even_with_consistent_modified_test_base(inputs):
    path = inputs["root"] / "base.zip"
    entries = {"python.exe": b"MZfake base", "LICENSE.txt": b"base license",
               "lib/TCL9.0/LICENSE.terms": b"existing"}
    write_zip(path, entries)
    inputs["lock"]["python"].update(record(path), member_count=3, file_count=3,
                                     expanded_bytes=sum(map(len, entries.values())))
    save(inputs)
    with pytest.raises(ValueError, match="base_collision"):
        build(inputs)


def test_manifest_tamper_and_excessive_member_size(inputs):
    inputs["manifest_path"].write_bytes(b"{}")
    with pytest.raises(ValueError, match="manifest_mismatch"):
        build(inputs)
    inputs["manifest"]["files"][0]["bytes"] = 8 * 1024**2 + 1
    save(inputs)
    with pytest.raises(ValueError, match="manifest_invalid"):
        build(inputs)


def test_existing_archive_or_checksum_never_overwritten(inputs):
    build(inputs)
    out = inputs["root"].parent / "data.zip"
    original = out.read_bytes()
    with pytest.raises(FileExistsError):
        build(inputs)
    assert out.read_bytes() == original
    other = out.with_name("other.zip")
    other.with_suffix(".zip.sha256").write_text("existing")
    with pytest.raises(FileExistsError):
        build(inputs, other)
    assert not other.exists()


def test_actual_derived_identity_can_be_pinned_and_mismatch_is_rejected(inputs):
    result = build(inputs)
    inputs["lock"]["data_asset"] = copy.deepcopy(result)
    save(inputs)
    assert result == build(inputs, inputs["root"].parent / "pinned.zip")
    inputs["lock"]["data_asset"]["sha256"] = "0" * 64
    save(inputs)
    with pytest.raises(ValueError, match="derived_identity"):
        build(inputs, inputs["root"].parent / "rejected.zip")


def test_notice_tamper_does_not_get_hidden_by_general_tcl_license(inputs):
    notice = next(n for n in inputs["lock"]["notices"] if n["path"].endswith("icons.tcl"))
    notice["sha256"] = "0" * 64
    save(inputs)
    with pytest.raises(ValueError, match="notice_mismatch"):
        build(inputs)


def test_repository_output_is_forbidden(inputs):
    with pytest.raises(ValueError, match="outside_checkout"):
        build(inputs, ROOT / "runtime-test-must-not-exist.zip")


def test_committed_exact_manifest_and_notice_coverage():
    lock = json.loads(builder.LOCK.read_bytes())
    members = builder._members(lock, ROOT / lock["members_manifest"]["path"])
    assert len(members) == 929
    assert {m["archive"] for m in members} == {"tcl", "tk"}
    assert sum(m["archive"] == "tcl" for m in members) == 839
    assert lock["python"]["member_count"] == lock["python"]["file_count"] == 2203
    scripts = {m["path"]: m for m in members}
    for notice in lock["notices"]:
        if notice["scope"] == "scripts":
            assert notice["sha256"] == scripts[notice["path"]]["sha256"]
            assert notice["bytes"] == scripts[notice["path"]]["bytes"]
    assert next(n for n in lock["notices"] if n["path"].endswith("icons.tcl"))["license"] == "CC-BY-SA-4.0"
