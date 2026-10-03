"""Build pinned Tcl/Tk data only; never execute/extract MSI or alter Python binaries."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import stat
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "engines/python/windows-runtime.lock.json"
MAX_ARCHIVE_BYTES = 64 * 1024**2
MAX_SCRIPT_BYTES = 32 * 1024**2
NOTICE_PATH = "THIRD_PARTY_TCLTK_NOTICES.txt"
MANIFEST_PATH = "runtime-data.json"
RESERVED = re.compile(r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)", re.I)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def safe_name(name: str) -> str:
    if not isinstance(name, str) or not name or any(c in name for c in '\\:<>"|?*'):
        raise ValueError("runtime_unsafe_path")
    if any(ord(c) < 32 for c in name):
        raise ValueError("runtime_unsafe_path")
    for part in name.split("/"):
        if part in {"", ".", ".."} or part.endswith((".", " ")) or RESERVED.match(part):
            raise ValueError("runtime_unsafe_path")
    return name


def safe_filesystem_path(path: Path) -> None:
    for entry in (path, *path.parents):
        if entry.is_symlink() or entry.is_junction():
            raise ValueError("runtime_redirected_path")


def verified_bytes(path: Path, record: dict) -> bytes:
    safe_filesystem_path(path)
    if (not path.is_file() or not 0 < record["bytes"] <= MAX_ARCHIVE_BYTES
            or path.stat().st_size != record["bytes"]):
        raise ValueError("runtime_input_size_mismatch")
    raw = path.read_bytes()
    if len(raw) != record["bytes"] or digest(raw) != record["sha256"]:
        raise ValueError("runtime_input_hash_mismatch")
    return raw


def archive_entries(archive: zipfile.ZipFile) -> dict[str, zipfile.ZipInfo]:
    entries: dict[str, zipfile.ZipInfo] = {}
    folded: set[str] = set()
    for entry in archive.infolist():
        name = safe_name(entry.filename)
        kind = stat.S_IFMT(entry.external_attr >> 16)
        if (entry.is_dir() or kind not in {0, stat.S_IFREG}
                or entry.external_attr & 0x400 or entry.flag_bits & 1):
            raise ValueError("runtime_nonregular_archive_entry")
        if name.casefold() in folded:
            raise ValueError("runtime_case_collision")
        folded.add(name.casefold())
        entries[name] = entry
    for name in folded:
        if any("/".join(name.split("/")[:i]) in folded for i in range(1, len(name.split("/")))):
            raise ValueError("runtime_file_directory_collision")
    return entries


def _members(lock: dict, manifest_path: Path) -> list[dict]:
    safe_filesystem_path(manifest_path)
    raw = manifest_path.read_bytes()
    if len(raw) > 1024**2 or digest(raw) != lock["members_manifest"]["sha256"]:
        raise ValueError("runtime_members_manifest_mismatch")
    document = json.loads(raw)
    files = document["files"]
    if (document["schema"] != "cytellect-windows-runtime-members/1"
            or document["composition_version"] != lock["composition_version"]
            or len(files) != 929 or lock["members_manifest"]["member_count"] != 929):
        raise ValueError("runtime_members_manifest_invalid")
    seen: set[str] = set()
    for item in files:
        name = safe_name(item["path"])
        safe_name(item["member"])
        if (name.casefold() in seen or item["archive"] not in {"tcl", "tk"}
                or type(item["bytes"]) is not int or not 0 <= item["bytes"] <= 8 * 1024**2
                or not re.fullmatch(r"[a-f0-9]{64}", item["sha256"])):
            raise ValueError("runtime_members_manifest_invalid")
        seen.add(name.casefold())
    if sum(item["bytes"] for item in files) > MAX_SCRIPT_BYTES:
        raise ValueError("runtime_scripts_too_large")
    return files


def _base_names(base_raw: bytes, lock: dict) -> set[str]:
    with zipfile.ZipFile(io.BytesIO(base_raw)) as archive:
        entries = archive_entries(archive)
        spec = lock["python"]
        if (len(entries) != spec["file_count"] or len(entries) != spec["member_count"]
                or sum(e.file_size for e in entries.values()) != spec["expanded_bytes"]):
            raise ValueError("runtime_base_inventory_mismatch")
        for notice in [*spec["launchers"], *(n for n in lock["notices"] if n["scope"] == "base")]:
            name = safe_name(notice["path"])
            if name not in entries or digest(archive.read(entries[name])) != notice["sha256"]:
                raise ValueError("runtime_base_identity_mismatch")
        return {name.casefold() for name in entries}


def _scripts(raw: bytes, spec: dict, members: list[dict], base_names: set[str]) -> dict[str, bytes]:
    expected = {item["member"]: item for item in members if item["archive"] == spec["id"]}
    if len(expected) != spec["member_count"] or len(expected) != {"tcl": 839, "tk": 90}[spec["id"]]:
        raise ValueError("runtime_script_count_mismatch")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        entries = archive_entries(archive)
        if entries.keys() != expected.keys():
            raise ValueError("runtime_script_members_mismatch")
        output = {}
        for name, entry in entries.items():
            item = expected[name]
            path = item["path"]
            if (not name.startswith(spec["prefix"])
                    or path != spec["target_prefix"] + name[len(spec["prefix"]):]):
                raise ValueError("runtime_script_mapping_invalid")
            folded = path.casefold()
            if (folded in base_names or any(base.startswith(folded + "/") for base in base_names)
                    or any("/".join(folded.split("/")[:i]) in base_names
                           for i in range(1, len(folded.split("/"))))):
                raise ValueError("runtime_base_collision")
            if entry.file_size != item["bytes"]:
                raise ValueError("runtime_script_size_mismatch")
            data = archive.read(entry)
            if path.lower().endswith((".exe", ".dll", ".pyd", ".com", ".scr")) or data.startswith(b"MZ"):
                raise ValueError("runtime_script_executable")
            if len(data) != item["bytes"] or digest(data) != item["sha256"]:
                raise ValueError("runtime_script_hash_mismatch")
            output[path] = data
        return output


def _notices(files: dict[str, bytes], lock: dict) -> bytes:
    for notice in (n for n in lock["notices"] if n["scope"] == "scripts"):
        data = files[notice["path"]]
        if len(data) != notice["bytes"] or digest(data) != notice["sha256"]:
            raise ValueError("runtime_notice_mismatch")
    icons = files["Lib/tk9.0/icons.tcl"].split(b"namespace eval", 1)[0]
    if b"https://creativecommons.org/licenses/by-sa/4.0/" not in icons:
        raise ValueError("runtime_icon_attribution_missing")
    return (b"Cytellect Tcl/Tk data assembly: original script bytes and notices retained.\n"
            b"Only library installation paths were mapped to Lib/tcl9.0 and Lib/tk9.0.\n"
            b"Source: https://www.python.org/ftp/python/3.14.8/amd64/tcltk.msi\n"
            b"This data asset contains no Python/Tcl/Tk runtime binaries.\n"
            b"Python base runtime notices remain in its original LICENSE.txt and documentation.\n\n"
            b"Tcl license.terms (verbatim)\n\n" + files["Lib/tcl9.0/license.terms"]
            + b"\n\nTk license.terms (verbatim)\n\n" + files["Lib/tk9.0/license.terms"]
            + b"\n\nTk icons: original complete attribution header (verbatim)\n\n" + icons
            + b"\nThe icons originate from https://github.com/vinceliuice/vimix-icon-theme\n"
            b"CC BY-SA 4.0: https://creativecommons.org/licenses/by-sa/4.0/\n"
            b"Legal code: https://creativecommons.org/licenses/by-sa/4.0/legalcode\n"
            b"Cytellect has not modified these icon bytes. These notices are not a legal certification.\n")


def build_data(parent_msi: Path, base_zip: Path, tcl_zip: Path, tk_zip: Path, output: Path,
               *, lock_path: Path = LOCK, members_path: Path | None = None) -> dict:
    safe_filesystem_path(lock_path)
    lock = json.loads(lock_path.read_bytes())
    if lock["schema"] != "cytellect-windows-runtime/1" or lock["platform"] != "windows-x64":
        raise ValueError("runtime_lock_invalid")
    members_path = members_path or ROOT / safe_name(lock["members_manifest"]["path"])
    members = _members(lock, members_path)
    # Independently verifies supplied parent and children. Does not assert that
    # this process extracted, executed, or inspected the parent MSI's contents.
    verified_bytes(parent_msi, lock["parent_msi"])
    base_names = _base_names(verified_bytes(base_zip, lock["python"]), lock)
    files: dict[str, bytes] = {}
    if [s["id"] for s in lock["script_archives"]] != ["tcl", "tk"]:
        raise ValueError("runtime_script_archives_invalid")
    for source, spec in zip((tcl_zip, tk_zip), lock["script_archives"], strict=True):
        files.update(_scripts(verified_bytes(source, spec), spec, members, base_names))
    files[NOTICE_PATH] = _notices(files, lock)
    manifest = {
        "schema": "cytellect-windows-runtime-data/1", "composition_version": lock["composition_version"],
        "python_version": lock["python"]["version"], "parent_msi": lock["parent_msi"],
        "script_archives": lock["script_archives"],
        "members_manifest_sha256": lock["members_manifest"]["sha256"],
        "provenance": {"inputs": "caller-supplied pre-extracted archives",
                       "extraction_performed_by_builder": False,
                       "verification": "independently pinned parent and child bytes; no extraction replay"},
        "files": [{"path": path, "bytes": len(data), "sha256": digest(data)}
                  for path, data in sorted(files.items())],
    }
    files[MANIFEST_PATH] = json_bytes(manifest)
    if any(path.casefold() in base_names for path in files):
        raise ValueError("runtime_base_collision")
    archive_bytes = io.BytesIO()
    with zipfile.ZipFile(archive_bytes, "w", zipfile.ZIP_STORED) as archive:
        for path, data in sorted(files.items()):
            entry = zipfile.ZipInfo(path, (2026, 1, 1, 0, 0, 0))
            entry.create_system = 3
            entry.external_attr = 0o100644 << 16
            entry.compress_type = zipfile.ZIP_STORED
            archive.writestr(entry, data)
    raw = archive_bytes.getvalue()
    result = {"path": "engines/python/windows-tcltk-9.0.4-data.zip", "sha256": digest(raw),
              "bytes": len(raw), "member_count": len(files), "manifest_path": MANIFEST_PATH,
              "manifest_sha256": digest(files[MANIFEST_PATH]),
              "notice_sha256": digest(files[NOTICE_PATH]), "script_count": len(members),
              "expanded_bytes": sum(map(len, files.values()))}
    if lock.get("data_asset") and lock["data_asset"] != result:
        raise ValueError("runtime_derived_identity_mismatch")
    safe_filesystem_path(output)
    checksum = output.with_suffix(output.suffix + ".sha256")
    safe_filesystem_path(checksum)
    if output.exists() or checksum.exists():
        raise FileExistsError("runtime_output_exists")
    if output.resolve().is_relative_to(ROOT):
        raise ValueError("runtime_output_must_be_outside_checkout")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as stream:
        stream.write(raw)
    with checksum.open("x", encoding="ascii", newline="\n") as stream:
        stream.write(f"{result['sha256']}  {output.name}\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("parent-msi", "base-zip", "tcl-zip", "tk-zip", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = build_data(args.parent_msi, args.base_zip, args.tcl_zip, args.tk_zip, args.output)
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile):
        raise SystemExit("Pinned Windows runtime data build rejected; inspect inputs privately.") from None
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
