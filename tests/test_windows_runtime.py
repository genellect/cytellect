"""Exercise actual PowerShell extraction without downloads or interpreter execution."""
import hashlib
import json
import os
import subprocess
import zipfile
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows runtime bootstrap")
ROOT = Path(__file__).resolve().parents[1]


def test_non_ascii_windows_setup_scripts_declare_utf8_for_legacy_powershell():
    # PS5.1 otherwise decodes UTF-8 bytes with the workstation ANSI code page.
    # A Japanese developer PC can parse a file that fails on a US CI runner.
    for name in ("local_setup.ps1", "windows_runtime.ps1", "prepare_windows_runtime_data.ps1"):
        raw = (ROOT / "scripts" / name).read_bytes()
        raw.decode("utf-8-sig")
        assert raw.isascii() or raw.startswith(b"\xef\xbb\xbf"), name


def extract(archive, destination, count, maximum=4096, required=None, data_only=True):
    specification = archive.with_suffix(".spec.json")
    specification.write_text(json.dumps({"files": required or [], "count": count,
                                         "maximum": maximum, "data_only": data_only}))
    shell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    command = r'''
$ErrorActionPreference='Stop'
$env:PSModulePath=(Join-Path $PSHOME 'Modules')+[IO.Path]::PathSeparator+$env:PSModulePath
foreach($source in @('scripts/local_setup.ps1','scripts/windows_runtime.ps1')) {
    $tokens=$null; $errors=$null
    $ast=[Management.Automation.Language.Parser]::ParseFile((Join-Path $env:CYTELLECT_TEST_SOURCE $source),[ref]$tokens,[ref]$errors)
    if($errors.Count) { throw 'parse_failed' }
    foreach($function in $ast.FindAll({param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst]},$true)) {
        Invoke-Expression $function.Extent.Text
    }
}
function Update-SetupStatus([string]$Phase,[string]$Text) {}
$spec=Get-Content -LiteralPath $env:CYTELLECT_TEST_SPEC -Raw | ConvertFrom-Json
$required=@{}
foreach($file in $spec.files) { $required[$file.path]=$file }
try {
    $result=Read-PinnedRuntimeZip $env:CYTELLECT_TEST_ARCHIVE $env:CYTELLECT_TEST_DESTINATION $spec.maximum $spec.count $required -DataOnly:([bool]$spec.data_only)
    @{passed=$true;files=@($result)} | ConvertTo-Json -Depth 6 -Compress
} catch {
    @{passed=$false;code=$_.Exception.Message} | ConvertTo-Json -Compress
    exit 1
}
'''
    environment = {**os.environ, "CYTELLECT_TEST_SOURCE": str(ROOT), "CYTELLECT_TEST_SPEC": str(specification),
                   "CYTELLECT_TEST_ARCHIVE": str(archive), "CYTELLECT_TEST_DESTINATION": str(destination)}
    result = subprocess.run([str(shell), "-NoProfile", "-Command", command], env=environment,
                            capture_output=True, text=True, check=False, timeout=30)
    assert result.stdout.strip(), result.stderr
    return result.returncode, json.loads(result.stdout)


def make_archive(path, entries):
    with zipfile.ZipFile(path, "x") as archive:
        for name, value in entries:
            archive.writestr(name, value)


def test_exact_extraction_repeat_preserves_bytes_and_rejects_modified_install(tmp_path):
    archive = tmp_path / "data with spaces.zip"
    destination = tmp_path / "runtime with spaces"
    name, value = "Lib/tcl9.0/init.tcl", b"# public extraction fixture\n"
    make_archive(archive, [(name, value)])
    records = [{"path": name, "bytes": len(value), "sha256": hashlib.sha256(value).hexdigest()}]
    for _ in range(2):
        status, receipt = extract(archive, destination, 1, required=records)
        assert status == 0, receipt
        assert receipt["files"] == records
        assert (destination / name).read_bytes() == value
    (destination / name).write_bytes(b"modified accepted file")
    status, receipt = extract(archive, destination, 1, required=records)
    assert status == 1 and receipt["code"] == "installed_python_modified"
    assert (destination / name).read_bytes() == b"modified accepted file"


@pytest.mark.parametrize("fault", ["traversal", "absolute", "backslash", "ads", "case_collision", "symlink",
                                    "directory", "executable", "mz_content", "too_large", "wrong_count",
                                    "wrong_member", "wrong_hash", "reserved_device", "trailing_dot", "wildcard"])
def test_rejects_unsafe_or_inconsistent_runtime_member(tmp_path, fault):
    archive, destination = tmp_path / "bad.zip", tmp_path / "destination"
    name, value = "Lib/tk9.0/init.tcl", b"# fixture"
    entries = [(name, value)]
    count, maximum, records = 1, 4096, None
    if fault == "traversal":
        entries = [("../outside.tcl", value)]
    elif fault == "absolute":
        entries = [("/outside.tcl", value)]
    elif fault == "backslash":
        info = zipfile.ZipInfo("placeholder")
        # ZipInfo's Windows constructor normalizes backslashes. Preserve the
        # hostile raw archive name so the PowerShell boundary sees it.
        info.filename = "Lib\\escape.tcl"
        entries = [(info, value)]
    elif fault == "ads":
        entries = [("init.tcl:stream", value)]
    elif fault == "reserved_device":
        entries = [("Lib/CON.tcl", value)]
    elif fault == "trailing_dot":
        entries = [("Lib/alias./init.tcl", value)]
    elif fault == "wildcard":
        entries = [("Lib/name?.tcl", value)]
    elif fault == "case_collision":
        entries += [(name.upper(), value)]
        count = 2
    elif fault == "symlink":
        info = zipfile.ZipInfo(name)
        info.create_system, info.external_attr = 3, 0o120777 << 16
        entries = [(info, b"outside")]
    elif fault == "directory":
        entries = [("Lib/", b"")]
    elif fault == "executable":
        entries = [("Lib/tk9.0/loader.exe", value)]
    elif fault == "mz_content":
        entries = [(name, b"MZ" + value)]
    elif fault == "too_large":
        maximum = 2
    elif fault == "wrong_count":
        count = 2
    else:
        records = [{"path": "other.tcl" if fault == "wrong_member" else name,
                    "bytes": len(value), "sha256": "0" * 64}]
    make_archive(archive, entries)
    status, receipt = extract(archive, destination, count, maximum, records)
    assert status == 1 and receipt["passed"] is False
    assert not destination.exists(), "Invalid archive must not produce a usable partial runtime"
    assert not (tmp_path / "outside.tcl").exists()


def test_interrupted_member_can_retry_without_changing_other_files(tmp_path):
    archive, destination = tmp_path / "resume.zip", tmp_path / "runtime"
    name, value = "Lib/tcl9.0/init.tcl", b"# complete member"
    make_archive(archive, [(name, value)])
    partial = destination / (name + ".cytellect-partial")
    partial.parent.mkdir(parents=True)
    partial.write_bytes(b"interrupted")
    unrelated = destination / "preserved.txt"
    unrelated.write_bytes(b"preserved")
    status, receipt = extract(archive, destination, 1)
    assert status == 0, receipt
    assert (destination / name).read_bytes() == value
    assert not partial.exists()
    assert unrelated.read_bytes() == b"preserved"


def inspect_inventory(runtime, records, junction_target=None):
    specification = runtime.parent / "inventory.json"
    specification.write_text(json.dumps(records), encoding="utf-8")
    shell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    command = r'''
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
$env:PSModulePath=(Join-Path $PSHOME 'Modules')+[IO.Path]::PathSeparator+$env:PSModulePath
foreach($source in @('scripts/local_setup.ps1','scripts/windows_runtime.ps1')) {
    $tokens=$null; $errors=$null
    $ast=[Management.Automation.Language.Parser]::ParseFile((Join-Path $env:CYTELLECT_TEST_SOURCE $source),[ref]$tokens,[ref]$errors)
    if($errors.Count) { throw 'parse_failed' }
    foreach($function in $ast.FindAll({param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst]},$true)) {
        Invoke-Expression $function.Extent.Text
    }
}
if ($env:CYTELLECT_TEST_JUNCTION) {
    # Both locations are dedicated test-owned sibling directories. No runtime
    # process, privilege/policy change, or existing installation is involved.
    New-Item -ItemType Junction -Path (Join-Path $env:CYTELLECT_TEST_RUNTIME 'unexpected-link') -Target $env:CYTELLECT_TEST_JUNCTION | Out-Null
}
$records=Get-Content -LiteralPath $env:CYTELLECT_TEST_INVENTORY -Raw | ConvertFrom-Json
if ($null -eq $records) { $records=@() }
try {
    Assert-PythonRuntimeInventory $env:CYTELLECT_TEST_RUNTIME $records
    @{passed=$true} | ConvertTo-Json -Compress
} catch {
    $code=$_.Exception.Message
    # Tests expose only fixed errors, never platform exception/path contents.
    if ($code -notmatch '^(invalid_python_runtime_inventory|redirected_install_path|installed_python_(unexpected|missing)_entry|installed_python_modified)$') {
        $code='unexpected_inventory_failure'
    }
    @{passed=$false;code=$code} | ConvertTo-Json -Compress
    exit 1
}
'''
    environment = {**os.environ, "CYTELLECT_TEST_SOURCE": str(ROOT), "CYTELLECT_TEST_RUNTIME": str(runtime),
                   "CYTELLECT_TEST_INVENTORY": str(specification),
                   "CYTELLECT_TEST_JUNCTION": str(junction_target) if junction_target else ""}
    process = subprocess.run([str(shell), "-NoProfile", "-NonInteractive", "-Command", command],
                             env=environment, capture_output=True, text=True, check=False, timeout=30)
    assert process.stdout.strip(), process.stderr
    assert str(runtime) not in process.stdout
    return process.returncode, json.loads(process.stdout)


@pytest.fixture
def inventory_tree(tmp_path):
    runtime = tmp_path / "runtime"
    values = {"python.exe": b"synthetic content; never executed",
              "Lib/site-packages/known.py": b"# known original\n",
              "Lib/tcl9.0/init.tcl": b"# known data\n"}
    records = []
    for name, value in values.items():
        target = runtime / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(value)
        records.append({"path": name, "bytes": len(value), "sha256": hashlib.sha256(value).hexdigest()})
    return runtime, records, values


def test_final_inventory_accepts_only_exact_composition_on_repeat(inventory_tree):
    runtime, records, values = inventory_tree
    for _ in range(2):
        status, receipt = inspect_inventory(runtime, records)
        assert status == 0 and receipt == {"passed": True}
        assert {name: (runtime / name).read_bytes() for name in values} == values


@pytest.mark.parametrize("name", ["Lib/site-packages/sitecustomize.py", "Lib/site-packages/extra.pth",
                                  "Lib/site-packages/__pycache__/known.cpython-314.pyc", "unrecorded.txt"])
def test_final_inventory_rejects_extra_code_cache_and_other_files_without_deleting(inventory_tree, name):
    runtime, records, values = inventory_tree
    extra = runtime / name
    extra.parent.mkdir(parents=True, exist_ok=True)
    extra.write_bytes(b"unrecorded; must remain untouched")
    status, receipt = inspect_inventory(runtime, records)
    assert status == 1 and receipt["code"] == "installed_python_unexpected_entry"
    assert extra.read_bytes() == b"unrecorded; must remain untouched"
    assert {name: (runtime / name).read_bytes() for name in values} == values


@pytest.mark.parametrize("change", ["missing", "modified", "duplicate_record", "empty_records"])
def test_final_inventory_rejects_missing_changed_or_ambiguous_expected_values(inventory_tree, change):
    runtime, records, values = inventory_tree
    if change == "missing":
        (runtime / "python.exe").unlink()
        expected = "installed_python_missing_entry"
    elif change == "modified":
        (runtime / "python.exe").write_bytes(b"changed bytes are not repaired")
        expected = "installed_python_modified"
    elif change == "duplicate_record":
        records.append(records[0])
        expected = "invalid_python_runtime_inventory"
    else:
        records = []
        expected = "invalid_python_runtime_inventory"
    before = {str(p.relative_to(runtime)): p.read_bytes() for p in runtime.rglob("*") if p.is_file()}
    status, receipt = inspect_inventory(runtime, records)
    assert status == 1 and receipt["code"] == expected
    assert {str(p.relative_to(runtime)): p.read_bytes() for p in runtime.rglob("*") if p.is_file()} == before


def test_final_inventory_refuses_junction_without_following_or_modifying_target(inventory_tree):
    runtime, records, values = inventory_tree
    target = runtime.parent / "separate-owned-directory"
    target.mkdir()
    marker = target / "preserve.txt"
    marker.write_bytes(b"unrelated owned fixture")
    status, receipt = inspect_inventory(runtime, records, junction_target=target)
    assert status == 1 and receipt["code"] == "redirected_install_path"
    assert marker.read_bytes() == b"unrelated owned fixture"
    assert {name: (runtime / name).read_bytes() for name in values} == values


def test_archive_file_parent_collision_is_rejected_before_any_write(tmp_path):
    archive, destination = tmp_path / "collision.zip", tmp_path / "runtime"
    make_archive(archive, [("Lib/parent", b"first"), ("Lib/parent/child.tcl", b"second")])
    status, receipt = extract(archive, destination, 2)
    assert status == 1 and receipt["code"] == "python_archive_file_directory_collision"
    assert not destination.exists()


def inspect_venv(app, runtime, *, if_present=False, signature=None, junction=None):
    """Use real path/hash validation; only the OS signature result is synthetic."""
    specification = app.parent / "venv-case.json"
    specification.write_text(json.dumps({
        "runtime": runtime, "if_present": if_present,
        "signature": signature or {"status": "Valid", "subject": "CN=Python, O=Python Software Foundation, C=US"},
        "junction": junction,
    }), encoding="utf-8")
    shell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    command = r'''
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
$env:PSModulePath=(Join-Path $PSHOME 'Modules')+[IO.Path]::PathSeparator+$env:PSModulePath
foreach($source in @('scripts/local_setup.ps1','scripts/windows_runtime.ps1')) {
    $tokens=$null; $errors=$null
    $ast=[Management.Automation.Language.Parser]::ParseFile((Join-Path $env:CYTELLECT_TEST_SOURCE $source),[ref]$tokens,[ref]$errors)
    if($errors.Count) { throw 'parse_failed' }
    foreach($function in $ast.FindAll({param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst]},$true)) {
        Invoke-Expression $function.Extent.Text
    }
}
$case=Get-Content -LiteralPath $env:CYTELLECT_TEST_CASE -Raw | ConvertFrom-Json
$script:SignatureChecks=[Collections.Generic.List[string]]::new()
function Get-AuthenticodeSignature([string]$LiteralPath) {
    $script:SignatureChecks.Add([IO.Path]::GetFileName($LiteralPath))
    return [pscustomobject]@{Status=$case.signature.status;SignerCertificate=[pscustomobject]@{Subject=$case.signature.subject}}
}
if ($null -ne $case.junction) {
    New-Item -ItemType Junction -Path (Join-Path $env:CYTELLECT_TEST_APP $case.junction.relative) -Target $case.junction.target | Out-Null
}
try {
    Assert-SignedPythonVenv $env:CYTELLECT_TEST_APP $case.runtime -IfPresent:([bool]$case.if_present)
    @{passed=$true;signature_checks=@($script:SignatureChecks.ToArray())} | ConvertTo-Json -Compress
} catch {
    $code=$_.Exception.Message
    if ($code -notmatch '^(python_venv_(base_mismatch|configuration_missing)|python_launcher_(hash_mismatch|signature_invalid)|invalid_python_runtime_lock|redirected_install_path)$') {
        $code='unexpected_venv_failure'
    }
    @{passed=$false;code=$code;signature_checks=@($script:SignatureChecks.ToArray())} | ConvertTo-Json -Compress
    exit 1
}
'''
    result = subprocess.run([str(shell), "-NoProfile", "-NonInteractive", "-Command", command],
                            env={**os.environ, "CYTELLECT_TEST_SOURCE": str(ROOT),
                                 "CYTELLECT_TEST_CASE": str(specification), "CYTELLECT_TEST_APP": str(app)},
                            capture_output=True, text=True, check=False, timeout=30)
    assert result.stdout.strip(), result.stderr
    assert str(app) not in result.stdout
    return result.returncode, json.loads(result.stdout)


@pytest.fixture
def venv_tree(tmp_path):
    app, base = tmp_path / "app with spaces", tmp_path / "base with spaces"
    app.mkdir()
    base.mkdir()
    scripts = app / ".venv/Scripts"
    scripts.mkdir(parents=True)
    values = {"python.exe": b"synthetic console launcher; never executed",
              "pythonw.exe": b"synthetic GUI launcher; never executed"}
    records = []
    for name, value in values.items():
        (scripts / name).write_bytes(value)
        original = "venvlauncher.exe" if name == "python.exe" else "venvwlauncher.exe"
        records.append({"path": f"Lib/venv/scripts/nt/{original}",
                        "sha256": hashlib.sha256(value).hexdigest()})
    configuration = app / ".venv/pyvenv.cfg"
    configuration.write_text(f"home = {base}\ninclude-system-site-packages = false\n", encoding="utf-8")
    runtime = {"path": str(base), "specification": {"python": {"launchers": records}}}
    return app, runtime, values


def test_signed_venv_checks_both_exact_launchers_without_modifying_them(venv_tree):
    app, runtime, values = venv_tree
    for if_present in (False, True):
        status, receipt = inspect_venv(app, runtime, if_present=if_present)
        assert status == 0 and receipt == {"passed": True, "signature_checks": ["python.exe", "pythonw.exe"]}
        assert {name: (app / ".venv/Scripts" / name).read_bytes() for name in values} == values


@pytest.mark.parametrize("fault", ["other_base", "no_home", "duplicate_home", "missing_configuration",
                                  "relative_home", "drive_relative_home", "unc_home"])
def test_signed_venv_requires_one_recorded_matching_base(venv_tree, fault):
    app, runtime, _ = venv_tree
    configuration = app / ".venv/pyvenv.cfg"
    if fault == "other_base":
        configuration.write_text(f"home = {app.parent / 'different base'}\n", encoding="utf-8")
    elif fault == "no_home":
        configuration.write_text("include-system-site-packages = false\n", encoding="utf-8")
    elif fault == "duplicate_home":
        configuration.write_text(f"home = {runtime['path']}\nHOME = {runtime['path']}\n", encoding="utf-8")
    elif fault in {"relative_home", "drive_relative_home", "unc_home"}:
        invalid = {"relative_home": ".", "drive_relative_home": "C:base", "unc_home": "//synthetic-host/base"}
        configuration.write_text(f"home = {invalid[fault]}\n", encoding="utf-8")
    else:
        configuration.unlink()
    before = configuration.read_bytes() if configuration.exists() else None
    status, receipt = inspect_venv(app, runtime)
    expected = "python_venv_configuration_missing" if fault == "missing_configuration" else "python_venv_base_mismatch"
    assert status == 1 and receipt["code"] == expected and receipt["signature_checks"] == []
    assert (configuration.read_bytes() if configuration.exists() else None) == before


@pytest.mark.parametrize("name", ["python.exe", "pythonw.exe"])
def test_signed_venv_rejects_changed_launcher_before_trusting_signature(venv_tree, name):
    app, runtime, _ = venv_tree
    target = app / ".venv/Scripts" / name
    target.write_bytes(b"replaced bytes; must not be executed or repaired")
    status, receipt = inspect_venv(app, runtime)
    assert status == 1 and receipt["code"] == "python_launcher_hash_mismatch"
    assert name not in receipt["signature_checks"]
    assert target.read_bytes() == b"replaced bytes; must not be executed or repaired"


@pytest.mark.parametrize("status,subject", [
    ("NotSigned", ""), ("HashMismatch", "O=Python Software Foundation"),
    ("Valid", "CN=Python, O=Different Publisher"),
    ("Valid", "O=Python Software Foundation Unrelated"),
])
def test_signed_venv_rejects_untrusted_signature_even_when_bytes_match(venv_tree, status, subject):
    app, runtime, _ = venv_tree
    result, receipt = inspect_venv(app, runtime, signature={"status": status, "subject": subject})
    assert result == 1 and receipt["code"] == "python_launcher_signature_invalid"
    assert receipt["signature_checks"] == ["python.exe"]


@pytest.mark.parametrize("fault", ["missing", "duplicate"])
def test_signed_venv_rejects_ambiguous_or_missing_original_launcher_identity(venv_tree, fault):
    app, runtime, _ = venv_tree
    records = runtime["specification"]["python"]["launchers"]
    if fault == "missing":
        records.pop(0)
    else:
        records.append(dict(records[0]))
    status, receipt = inspect_venv(app, runtime)
    assert status == 1 and receipt["code"] == "invalid_python_runtime_lock"
    assert receipt["signature_checks"] == []


def test_signed_venv_if_present_allows_absent_environment_without_creating_it(tmp_path):
    app = tmp_path / "new app"
    app.mkdir()
    runtime = {"path": str(tmp_path / "base"), "specification": {"python": {"launchers": []}}}
    status, receipt = inspect_venv(app, runtime, if_present=True)
    assert status == 0 and receipt == {"passed": True, "signature_checks": []}
    assert not (app / ".venv").exists()


def test_signed_venv_if_present_checks_partial_launchers_before_resume(venv_tree):
    app, runtime, _ = venv_tree
    (app / ".venv/pyvenv.cfg").unlink()
    (app / ".venv/Scripts/pythonw.exe").unlink()
    status, receipt = inspect_venv(app, runtime, if_present=True)
    assert status == 0 and receipt == {"passed": True, "signature_checks": ["python.exe"]}
    (app / ".venv/Scripts/python.exe").write_bytes(b"modified partial launcher")
    status, receipt = inspect_venv(app, runtime, if_present=True)
    assert status == 1 and receipt["code"] == "python_launcher_hash_mismatch"


def test_signed_venv_final_gate_requires_gui_launcher_in_addition_to_console(venv_tree):
    app, runtime, _ = venv_tree
    (app / ".venv/Scripts/pythonw.exe").unlink()
    status, receipt = inspect_venv(app, runtime)
    assert status == 1 and receipt["code"] == "python_launcher_hash_mismatch"
    assert receipt["signature_checks"] == ["python.exe"]


def test_signed_venv_if_present_does_not_ignore_wrong_existing_configuration(venv_tree):
    app, runtime, _ = venv_tree
    (app / ".venv/pyvenv.cfg").write_text("home = C:/synthetic-other-base\n", encoding="utf-8")
    status, receipt = inspect_venv(app, runtime, if_present=True)
    assert status == 1 and receipt["code"] == "python_venv_base_mismatch"


@pytest.mark.parametrize("relative", [".venv", ".venv/Scripts"])
def test_signed_venv_rejects_directory_junctions_before_following_them(tmp_path, relative):
    app, target = tmp_path / "app", tmp_path / "separate-owned-target"
    (app / relative).parent.mkdir(parents=True, exist_ok=True)
    target.mkdir()
    marker = target / "preserve.txt"
    marker.write_bytes(b"outside environment fixture")
    runtime = {"path": str(tmp_path / "base"), "specification": {"python": {"launchers": []}}}
    status, receipt = inspect_venv(app, runtime, if_present=True,
                                   junction={"relative": relative, "target": str(target)})
    assert status == 1 and receipt["code"] == "redirected_install_path"
    assert receipt["signature_checks"] == []
    assert marker.read_bytes() == b"outside environment fixture"
