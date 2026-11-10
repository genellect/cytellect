"""Check nucleus/partition APIs and exports against registered public pixels and saved masks.

This checks calculation and source joins, not detector accuracy or biological
validity. It never runs a detector, changes review decisions, or uses private data.
The output directory must be new and outside the checkout.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import zipfile
from collections import Counter
from pathlib import Path

import numpy as np
from cytellect_api.app import create_app
from cytellect_api.config import Settings
from cytellect_api.db import fields, workspaces
from cytellect_api.workspace_runs import adopted_for
from cytellect_api.workspace_selection import selection_at
from cytellect_showcase.runtime import _create_session, _extract_seed, _refresh_expiry, _seed_owner
from cytellect_showcase.seed import restore
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
TITLE = "核小体と転写（ActD 処理）"


def check(condition: object, code: str = "public_check_failed") -> None:
    """An explicit check that `python -O` cannot remove (unlike assert)."""
    if not condition:
        raise AssertionError(code)


def close(actual: float | None, expected: float) -> None:
    if actual is None or not np.isclose(actual, expected, rtol=1e-12, atol=1e-12):
        raise AssertionError(f"public_value_mismatch: {actual!r} != {expected!r}")


def verify(output: Path) -> dict:
    output = output.expanduser().resolve()
    if output == ROOT or ROOT in output.parents or output.exists():
        raise ValueError("output_must_be_new_and_outside_checkout")
    seed = ROOT / "apps/web/public/showcase/seed.zip"
    manifest = json.loads((seed.parent / "manifest.json").read_text(encoding="utf-8"))
    record = manifest["files"]["seed.zip"]
    raw = seed.read_bytes()
    if len(raw) != record["bytes"] or hashlib.sha256(raw).hexdigest() != record["sha256"]:
        raise ValueError("registered_public_seed_mismatch")
    data = output / "data"
    data.mkdir(parents=True)
    _extract_seed(raw, data)
    regenerated = restore(data)  # verifies each regenerated file's recorded size and SHA-256
    settings = Settings(data_dir=data, app_origin="http://localhost:3000", secure_cookies=False)
    app = create_app(settings)
    store = app.state.store
    _refresh_expiry(store, settings)
    client = TestClient(app)
    client.cookies.set(settings.cookie_name, _create_session(store, _seed_owner(store)))
    headers = {"Origin": settings.app_origin}
    workspace = next(w for w in store.rows(workspaces) if w["title"] == TITLE and not w["deleted"])
    wid = workspace["id"]
    checked = []
    for field in store.rows(fields):
        if field["workspace_id"] != wid:
            continue
        fid = field["id"]
        with store.transaction() as conn:
            adopted = adopted_for(conn, wid, fid, selection_at(conn, wid))
        nuclear, child = adopted.get("nuclei"), adopted.get("nucleoli")
        if nuclear is None or child is None:
            checked.append({"field_id": fid, "status": "not_selected"})
            continue
        params = {"field_id": fid, "nucleolar_revision_id": child["id"]}
        path = f'/v1/revisions/{nuclear["id"]}/nucleus-table'
        response = client.get(path, params=params, headers=headers)
        if response.status_code != 200:
            checked.append({"field_id": fid, "status": "unavailable", "reason": response.json()["detail"]})
            continue
        table = response.json()
        labels = np.load(store.safe_path(nuclear["result_dir"]) / fid / "labels.npy", allow_pickle=False)
        child_root = store.safe_path(child["result_dir"])
        child_labels = np.load(child_root / fid / "labels.npy", allow_pickle=False)
        report = json.loads((child_root / "measurements.json").read_text(encoding="utf-8"))
        drop = [item["region_id"] for item in report["exclusions"]
                if item["field_id"] == fid and item["region_id"] is not None]
        child_labels = np.where(np.isin(child_labels, drop), 0, child_labels)
        for row in table["rows"]:
            mask = labels == row["nucleus_id"]
            check(row["nucleus_area_px"] == np.count_nonzero(mask), "public_check_failed")
            for channel in row["channels"]:
                original = np.load(data / "workspaces" / wid / "fields" / fid /
                                   f'channel-{channel["channel_id"]}.npy', allow_pickle=False)
                pixels = original[mask].astype(np.float64)
                close(channel["mean"], float(pixels.mean()))
                close(channel["integrated"], float(pixels.sum()))
            morph = row["nucleoli"]
            if morph["status"] == "measured":
                objects, sizes = np.unique(child_labels[mask & (child_labels > 0)], return_counts=True)
                area = int(sizes.sum())
                check(morph["count"] == len(objects) and morph["union_area_px"] == area, "public_check_failed")
                check(morph["largest_object_area_px"] == int(sizes.max()), "public_check_failed")
                close(morph["area_fraction"], area / int(mask.sum()))
                close(morph["largest_object_fraction"], int(sizes.max()) / area)
                if table["calibration"] is not None:
                    calibration = table["calibration"]
                    close(morph["union_area_um2"], area * calibration["pixel_size_x_um"] *
                          calibration["pixel_size_y_um"])
            else:
                check(morph["count"] is None and morph["union_area_px"] is None, "public_check_failed")
                # Both ways: a nucleus left without nucleoli has no adopted nucleolus in the saved mask
                # (unless the nucleoli are not adopted, the field is excluded or the nucleus is excluded).
                if not row["excluded"] and morph["reason"] not in ("nucleolar_revision_not_adopted", "nucleolar_field_excluded"):
                    check(not np.any(child_labels[mask] > 0), "nucleolus_present_but_missing")
        download = client.get(path + ".zip", params=params, headers=headers)
        check(download.status_code == 200, "public_check_failed")
        with zipfile.ZipFile(io.BytesIO(download.content)) as archive:
            check(json.loads(archive.read("nucleus-table.json")) == table, "public_check_failed")
            csv_rows = {int(row["nucleus_id"]): row for row in csv.DictReader(
                io.StringIO(archive.read("nucleus-table.csv").decode("utf-8-sig")))}
        for row in table["rows"]:
            saved = csv_rows[row["nucleus_id"]]
            check(saved["nucleolar_status"] == row["nucleoli"]["status"], "public_check_failed")
            check(saved["nucleolar_reason"] == (row["nucleoli"]["reason"] or ""), "public_check_failed")
            for column, value in (("nucleolar_count", row["nucleoli"]["count"]),
                                  ("nucleolar_area_px", row["nucleoli"]["union_area_px"])):
                check(saved[column] == (str(value) if value is not None else ""), "public_check_failed")
        reference = adopted.get("nucleoplasm")
        partition_status = "not_selected"
        if reference is not None:
            partition_params = {"field_id": fid, "target_revision_id": child["id"],
                                "reference_revision_id": reference["id"], "channel_id": "eu5"}
            partition_path = f'/v1/revisions/{nuclear["id"]}/region-partition'
            partition = client.get(partition_path, params=partition_params, headers=headers)
            if partition.status_code == 200:
                values = partition.json()
                check(values["nuclear_source"]["reviewed"] == bool(nuclear["reviewed"]), "public_check_failed")
                check(values["target_source"]["reviewed"] == bool(child["reviewed"]), "public_check_failed")
                check(values["reference_source"]["reviewed"] == bool(reference["reviewed"]), "public_check_failed")
                reference_labels = np.load(store.safe_path(reference["result_dir"]) / fid / "labels.npy", allow_pickle=False)
                pixels = np.load(data / "workspaces" / wid / "fields" / fid / "channel-eu5.npy", allow_pickle=False)
                for row in values["rows"]:
                    for name, membership in (("target", child_labels), ("reference", reference_labels)):
                        support = (labels == row["nucleus_id"]) & (membership > 0)
                        if row[name]["raw_mean"] is not None:
                            selected_pixels = pixels[support].astype(np.float64)
                            close(row[name]["raw_mean"], float(selected_pixels.mean()))
                            close(row[name]["raw_integrated"], float(selected_pixels.sum()))
                        else:
                            # Both ways: a value is missing only for an empty region, with its reason.
                            check(not support.any() and row[name]["raw_missing_reason"], "partition_value_missing")
                    if row["raw"]["k"] is not None:
                        close(row["raw"]["k"], row["target"]["raw_mean"] / row["reference"]["raw_mean"])
                        close(row["raw"]["log2_k"], float(np.log2(row["raw"]["k"])))
                    else:
                        check(row["raw"]["missing_reasons"], "public_check_failed")
                partition_csv = client.get(partition_path + ".csv", params=partition_params, headers=headers)
                check(partition_csv.status_code == 200, "public_check_failed")
                records = list(csv.DictReader(io.StringIO(partition_csv.content.decode("utf-8-sig"))))
                check(json.loads(records[0]["provenance_json"])["review_status"] == values["review_status"], "public_check_failed")
                partition_status = "checked"
            else:
                partition_status = partition.json()["detail"]
        checked.append({"field_id": fid, "nuclear_revision_id": nuclear["id"],
                        "nucleolar_revision_id": child["id"], "status": "checked",
                        "partition_status": partition_status,
                        "nuclei": len(table["rows"]),
                        "nucleolar_statuses": dict(Counter(row["nucleoli"]["status"] for row in table["rows"]))})
    result = {"source": "https://zenodo.org/records/6643470", "license": "CC-BY-4.0",
              "seed_sha256": record["sha256"], "regenerated_files_verified": regenerated,
              "scope": "API/source-join/arithmetic/export consistency; no detection or biological validity claim",
              "field_checks": checked}
    (output / "report.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    arguments = parser.parse_args()
    verification = verify(arguments.out)
    print(json.dumps({"fields": len(verification["field_checks"]),
                      "statuses": dict(Counter(row["status"] for row in verification["field_checks"])),
                      "partition_statuses": dict(Counter(row.get("partition_status", "not_checked")
                                                         for row in verification["field_checks"]))}))
    if any(row["status"] != "checked" or row.get("partition_status") != "checked"
           for row in verification["field_checks"]):
        raise SystemExit(1)
