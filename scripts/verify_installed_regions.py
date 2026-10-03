"""Installed-copy acceptance with generated pixels and independent closed-form references.

Run with the installed interpreter against its already running loopback server.
This development/release tool is deliberately excluded from the user installer.
No private research input, invitation, password or external service is needed.
"""
from __future__ import annotations

import argparse
import hashlib
import http.cookiejar
import importlib
import io
import json
import math
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

MODULES = (
    "cytellect_analysis.regions", "cytellect_analysis.region_contracts", "cytellect_analysis.engine",
    "cytellect_analysis.region_comparison", "cytellect_analysis.unit_inference",
    "cytellect_analysis.region_comparison_figures", "cytellect_analysis.region_exports",
    "cytellect_analysis.planning", "cytellect_analysis.plan_adoption",
    "cytellect_api.regions", "cytellect_api.region_comparisons", "cytellect_api.local",
    "cytellect_api.planning",
    "cytellect_worker.regions", "cytellect_worker.region_comparisons",
    "numpy", "scipy", "pandas", "statsmodels", "matplotlib", "tifffile", "pydantic",
)
VALUES = (-3, -1, 2, 0)


def require(condition, code):
    if not condition:
        raise ValueError(code)


def source_identity(app: Path, expected: str):
    require(bool(re.fullmatch(r"[0-9a-f]{40}", expected)), "expected_source_required")
    app = app.resolve()
    require(Path(sys.executable).resolve().is_relative_to(app) and Path(sys.prefix).resolve().is_relative_to(app),
            "installed_interpreter_required")
    for name in MODULES:
        importlib.import_module(name)
    from cytellect_api.local import installed_source_revision

    require(installed_source_revision(app) == expected, "installed_manifest_mismatch")
    files = {}
    for name, module in tuple(sys.modules.items()):
        if name.startswith(("cytellect_analysis", "cytellect_api", "cytellect_worker")) or name in MODULES:
            filename = getattr(module, "__file__", None)
            require(filename is not None, "installed_module_source_missing")
            file = Path(filename).resolve()
            require(file.is_relative_to(app), "source_checkout_import_forbidden")
            files[file.relative_to(app).as_posix()] = hashlib.sha256(file.read_bytes()).hexdigest()
    return {"source_commit": expected, "python": sys.version.split()[0], "module_sha256": files}


def verify_reference(result, *, paired):
    """A=[-3,-1], B=[2,0]: translate [2,4],[7,5] by -5; pair by index."""
    require(result["analysis_kind"] == "region-comparison", "comparison_kind_mismatch")
    require(result["spec"]["design"]["kind"] == ("paired" if paired else "independent"), "design_mismatch")
    require(len(result["comparisons"]) == 1, "comparison_family_mismatch")
    expected = ({"estimate": -3.0, "standard_error": 2.0, "statistic": -1.5,
                 "degrees_of_freedom": 1.0, "p_value": 1 - 2 * math.atan(1.5) / math.pi}
                if paired else {"estimate": -3.0, "standard_error": math.sqrt(2),
                                "statistic": -3 / math.sqrt(2), "degrees_of_freedom": 2.0,
                                "p_value": 1 - 3 / math.sqrt(13)})
    # Exact inverse-CDF identities for df=1 (Cauchy) and df=2; no SciPy t routine.
    half = 2 / math.tan(math.pi * .025) if paired else 2 * .95 / math.sqrt(1 - .95**2)
    expected.update(ci_low=-3 - half, ci_high=-3 + half, p_holm=expected["p_value"])
    observed = result["comparisons"][0]
    for key, reference in expected.items():
        require(math.isclose(observed[key], reference, rel_tol=1e-10, abs_tol=1e-11), "independent_reference_mismatch")
    require(observed["n_a"] == observed["n_b"] == 2, "independent_n_mismatch")
    require({row["condition"]: row["experimental_units"] for row in result["counts"]} == {"A": 2, "B": 2},
            "unit_count_mismatch")
    require(len(result["plot_data"]) == 4 and len(result["unit_summary"]) == 4, "observation_count_mismatch")
    if paired:
        require(observed["complete_pairs"] == 2 and len(result["pair_ledger"]) == 2, "pair_count_mismatch")
    return {"design": "paired" if paired else "independent", "expected": expected,
            "units_per_condition": 2, "observations": 4}


class LocalSession:
    def __init__(self, origin):
        url = urllib.parse.urlsplit(origin)
        require(url.scheme == "http" and url.hostname == "127.0.0.1" and url.port is not None
                and not url.username and not url.password and not url.query and not url.fragment
                and url.path in ("", "/"), "literal_loopback_origin_required")
        self.origin = origin.rstrip("/")
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                raise ValueError("local_acceptance_redirect_forbidden")

        self.opener = urllib.request.build_opener(NoRedirect(),
                        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def request(self, path, *, body=None, content_type="application/json", method=None):
        require(path.startswith("/v1/") and ".." not in path and not path.startswith("//"), "api_path_invalid")
        headers = {"Origin": self.origin, "X-Cytellect-Request": "1"}
        if body is not None:
            headers["Content-Type"] = content_type
        request = urllib.request.Request(self.origin + path, data=body, headers=headers, method=method)
        try:
            with self.opener.open(request, timeout=120) as response:
                require(response.headers.get("Cache-Control") == "no-store", "private_response_cache_required")
                return response.read()
        except urllib.error.HTTPError:
            raise ValueError("installed_acceptance_http_failure") from None

    def json(self, path, body=None):
        return json.loads(self.request(path, body=json.dumps(body).encode() if body is not None else None))

    def wait(self, job_id):
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            job = self.json(f"/v1/jobs/{job_id}")
            if job["state"] == "succeeded":
                return
            require(job["state"] not in ("failed", "cancelled"), "installed_acceptance_job_failed")
            time.sleep(.25)
        raise ValueError("installed_acceptance_job_timeout")


def multipart(specification, image, labels):
    boundary = "cytellect-generated-acceptance-boundary"
    parts = [f'--{boundary}\r\nContent-Disposition: form-data; name="specification"\r\n\r\n'.encode()
             + json.dumps(specification).encode() + b"\r\n"]
    for name, content in (("ch0", image), ("labels", labels)):
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; filename="fixture.tif"\r\n'
                     'Content-Type: image/tiff\r\n\r\n'.encode() + content + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def extract_verified_bundle(content: bytes, destination: Path):
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        names = archive.namelist()
        require(len(names) == len(set(names)) and sum(i.file_size for i in archive.infolist()) < 50 * 1024**2,
                "archive_size_or_duplicates_invalid")
        for name in names:
            relative = PurePosixPath(name)
            require(bool(relative.parts) and relative.as_posix() == name and not relative.is_absolute()
                    and all(re.fullmatch(r"[A-Za-z0-9_.-]+", part)
                    and part not in (".", "..") for part in relative.parts) and "\\" not in name,
                    "archive_path_invalid")
        manifest = json.loads(archive.read("manifest.json"))
        require(manifest["format"] == "cytellect-region-reproducibility/1" and manifest["raw_included"] is True,
                "raw_replay_package_required")
        require(set(manifest["files"]) | {"manifest.json"} == set(names), "archive_manifest_incomplete")
        for name, digest in manifest["files"].items():
            require(hashlib.sha256(archive.read(name)).hexdigest() == digest, "archive_hash_mismatch")
        destination.mkdir(parents=True, exist_ok=False)
        for name in names:
            target = destination.joinpath(*PurePosixPath(name).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(name))
    return len(manifest["files"])


def verify_workflow(session, output: Path, expected_source: str):
    import numpy as np
    import tifffile
    from cytellect_analysis.region_exports import replay_region_bundle
    from cytellect_worker.provenance import software_identity

    setup = session.json("/v1/local/setup")
    require(setup.get("mode") == "local" and setup.get("ready") is True, "local_service_required")
    session.json("/v1/local/session", {})
    wid = session.json("/v1/workspaces", {"title": "Generated numerical acceptance"})["id"]
    fids = []
    labels = np.zeros((12, 12), np.uint32)
    labels[4:6, 4:6] = 17

    def tiff(array):
        buffer = io.BytesIO()
        tifffile.imwrite(buffer, array, photometric="minisblack")
        return buffer.getvalue()

    for index, value in enumerate(VALUES):
        image = np.full((12, 12), 10, np.uint16)
        image[labels == 17] = 10 + value
        spec = {"channels": [{"channel_id": "signal", "label": "Known signal", "identity_confirmed": True}],
                "metadata": {"condition": "A" if index < 2 else "B", "sample": f"sample-{index}",
                             "experimental_unit": f"unit-{index}", "pair": f"pair-{index % 2}",
                             "acquisition_date": "generated-fixture"}}
        body, kind = multipart(spec, tiff(image), tiff(labels))
        field = json.loads(session.request(f"/v1/workspaces/{wid}/region-fields", body=body, content_type=kind))
        fids.append(field["id"])
    started = session.json(f"/v1/workspaces/{wid}/region-analyses", {
        "recipe": {"region_set_id": "objects", "label": "Known regions", "source": "imported"},
        "field_ids": fids, "backgrounds": {fid: {"signal": {"confirmed": True,
        "polygon": [[0, 0], [2, 0], [2, 2], [0, 2]]}} for fid in fids}})
    session.wait(started["job_id"])
    rid = started["revision_id"]
    report = session.json(f"/v1/revisions/{rid}/region-measurements")
    require(not report["field_failures"], "generated_measurement_failed")
    for fid, value in zip(fids, VALUES, strict=True):
        row, = report["field_tables"][fid]["rows"]
        require(row["area_px"] == 4 and row["mean_corrected"] == value
                and row["integrated_corrected"] == 4 * value and row["area_um2"] is None,
                "known_pixels_measurement_mismatch")
    session.json(f"/v1/revisions/{rid}/review", {})
    checks = []
    for paired in (False, True):
        design = {"kind": "paired" if paired else "independent", "confirmed": True,
                  "unit_definition": "Four generated software units; no biological replication claim"}
        if paired:
            design["pairing_basis"] = "Declared index pairing in generated software fixture"
        spec = {"mode": "region-experimental-unit", "selection": {"source": "region", "region_set_id": "objects",
                "channel_id": "signal", "metric": "mean_corrected"}, "design": design, "conditions": ["A", "B"],
                "comparison_family": {"family_id": "acceptance", "kind": "control", "control": "A", "contrasts": [["A", "B"]]},
                "acquisition_review": {"confirmed": True, "basis": "same-settings"}, "missingness_confirmed": True,
                "plot": {"kind": "paired" if paired else "distribution", "language": "en", "preset": "nature-single"}}
        job = session.json(f"/v1/revisions/{rid}/region-comparisons", spec)["job_id"]
        session.wait(job)
        result = session.json(f"/v1/jobs/{job}/region-comparison")
        checks.append(verify_reference(result, paired=paired))
        for name in result["figure"]["source_files"]:
            session.request(f"/v1/jobs/{job}/files/{name}")
    # Reconfirmation must not invalidate successful comparison fingerprints.
    session.json(f"/v1/revisions/{rid}/review", {})
    exported = session.json(f"/v1/revisions/{rid}/export?include_raw=true", {})["job_id"]
    session.wait(exported)
    content = session.request(f"/v1/jobs/{exported}/files/analysis.zip")
    (output / "generated-acceptance.zip").write_bytes(content)
    bundle = output / "bundle"
    verified = extract_verified_bundle(content, bundle)
    software = json.loads((bundle / "provenance.json").read_text(encoding="utf-8"))["software"]
    require(software["git_commit"] == expected_source
            and software["source_sha256"] == software_identity()["source_sha256"], "running_server_source_mismatch")
    replay = replay_region_bundle(bundle, bundle / "raw", output / "replayed")
    require(replay["matched_saved_measurements"] and replay["matched_saved_comparisons"], "installed_replay_mismatch")
    session.request(f"/v1/workspaces/{wid}", method="DELETE")
    return {"closed_form_checks": checks, "verified_bundle_files": verified, "replay": replay,
            "generated_workspace_deleted": True, "repeat_review_export": True,
            "running_source_sha256": software["source_sha256"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", type=Path, required=True)
    parser.add_argument("--expected-source", required=True)
    parser.add_argument("--origin", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    session = LocalSession(args.origin)  # Validate destination before generating any data.
    identity = source_identity(args.app, args.expected_source)
    output = args.output.resolve()
    require(not output.is_relative_to(args.app.resolve())
            and not output.is_relative_to(Path(__file__).resolve().parents[1]), "acceptance_output_must_be_separate")
    output.mkdir(parents=True, exist_ok=False)
    receipt = {"schema": "cytellect-installed-regions-acceptance/1", "identity": identity,
               "harness_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               "scope": "Generated pixel arithmetic, independent closed-form inference and installed replay; not biological validity"}
    try:
        receipt["checks"] = verify_workflow(session, output, args.expected_source)
        receipt["passed"] = True
    except Exception:
        receipt["passed"] = False
        (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        raise SystemExit("installed_region_acceptance_failed") from None
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": True, "source_commit": args.expected_source, "scope": receipt["scope"]}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit("installed_region_acceptance_setup_failed") from None
