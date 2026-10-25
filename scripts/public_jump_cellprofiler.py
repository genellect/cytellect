"""Pin the published JUMP CellProfiler reference without downloading Nuclei.csv.

Acquire: python scripts/public_jump_cellprofiler.py --output ../jump-cp-reference
Verify local receipt: add --verify. Refresh the owned fixture: add --write-reference.

Only source table arithmetic (counts/means/ratios) is performed here, not Cytellect
image measurements or inferential statistics. No detection settings are changed.
Image.csv is streamed in full; Nuclei.csv only uses bounded HTTP Range requests.
Approximate ordering is a search hint, never a completeness proof. Every selected
image must have exactly ObjectNumber 1..Count_Nuclei or extraction fails closed.
Raw source rows, including their line terminator, are hashed before CSV parsing.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import math
import re
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "fixtures/public/jump-plk1/cellprofiler-reference.json"
BASE = "https://cellpainting-gallery.s3.amazonaws.com/cpg0016-jump/source_13"
METADATA_COMMIT = "016e865fa0691244e0860943e41c7d6a88ed2580"
METADATA_BASE = f"https://raw.githubusercontent.com/jump-cellpainting/datasets/{METADATA_COMMIT}/metadata"
METADATA_BLOBS = {"well.csv.gz": "b3f95059d32a0793731f2b250060f2f44454bc0d",
                  "crispr.csv.gz": "0e7b488948cf19ef05e94932688495ed866de0c4"}
RUNS = [("20220914_Run1", "CP-CC9-R1-01"), ("20221009_Run2", "CP-CC9-R2-01"),
        ("20221017_Run3", "CP-CC9-R3-01")]
GROUPS = {"JCP2022_800002": "Non-targeting", "JCP2022_805264": "PLK1"}
IMAGE_COLUMNS = ["Image_ImageNumber", "Metadata_Plate", "Metadata_Well", "Metadata_Site",
                 "FileName_OrigDNA", "Count_Nuclei", "Count_NucleiIncludingEdges"]
OBJECT_COLUMNS = ["ImageNumber", "ObjectNumber", "Nuclei_AreaShape_Center_X",
                  "Nuclei_AreaShape_Center_Y", "Nuclei_AreaShape_BoundingBoxMinimum_X",
                  "Nuclei_AreaShape_BoundingBoxMinimum_Y", "Nuclei_AreaShape_BoundingBoxMaximum_X",
                  "Nuclei_AreaShape_BoundingBoxMaximum_Y", "Nuclei_AreaShape_Area",
                  "Nuclei_AreaShape_Eccentricity", "Nuclei_AreaShape_Solidity",
                  "Nuclei_Intensity_MeanIntensity_DNA"]
BLOCK = 4 * 1024 * 1024
PROBE = 128 * 1024


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def reference_json(value, depth: int = 0) -> str:
    """Keep each published row on one line so the small fixture stays reviewable."""
    indent = " " * depth
    child = " " * (depth + 1)
    if isinstance(value, dict):
        if "raw_row_sha256" in value or not value:
            return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        return "{\n" + ",\n".join(child + json.dumps(k) + ": " + reference_json(v, depth + 1)
                                  for k, v in value.items()) + "\n" + indent + "}"
    if isinstance(value, list) and value and isinstance(value[0], (dict, list)):
        return "[\n" + ",\n".join(child + reference_json(v, depth + 1) for v in value) + "\n" + indent + "]"
    return json.dumps(value, ensure_ascii=False)


def parse_row(raw: bytes, header: list[str]) -> dict[str, str]:
    values = next(csv.reader([raw.decode("utf-8").rstrip("\r\n")]))
    if len(values) != len(header):
        raise ValueError("incomplete or multiline CSV row")
    return dict(zip(header, values, strict=True))


def complete_lines(data: bytes, start: int):
    """Return offsets of only complete rows; a nonzero start discards first line."""
    offset = start
    for index, raw in enumerate(data.splitlines(keepends=True)):
        if (start == 0 or index > 0) and raw.endswith(b"\n"):
            yield offset, raw
        offset += len(raw)


def validate_range(status: int, content_range: str, start: int, end: int, size: int):
    if status != 206 or content_range != f"bytes {start}-{end}/{size}":
        raise ValueError("server did not honor the exact bounded Range; refusing body")


class RangeCSV:
    """Keep each response bounded; pin S3 version and ETag before any range read."""
    def __init__(self, url: str, budget: int = 512 * 1024 * 1024):
        with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=90) as r:
            self.size = int(r.headers["Content-Length"])
            self.etag = r.headers["ETag"]
            self.version = r.headers.get("x-amz-version-id")
            self.modified = r.headers.get("Last-Modified")
        self.url = url
        self.pinned_url = url + "?" + urllib.parse.urlencode({"versionId": self.version}) if self.version else url
        self.budget = budget
        self.transferred = 0
        self.receipts: list[dict] = []
        self.cache: dict[tuple[int, int], bytes] = {}
        head = self.get(0, PROBE - 1)
        self.header_raw = head.splitlines(keepends=True)[0]
        self.header = next(csv.reader([self.header_raw.decode().rstrip("\r\n")]))

    def get(self, start: int, end: int) -> bytes:
        start, end = max(0, start), min(self.size - 1, end)
        key = (start, end)
        if key in self.cache:
            return self.cache[key]
        length = end - start + 1
        if length <= 0 or length > BLOCK + PROBE or self.transferred + length > self.budget:
            raise ValueError("range or total transfer budget exceeded; no full CSV fallback")
        req = urllib.request.Request(self.pinned_url, headers={
            "Range": f"bytes={start}-{end}", "If-Match": self.etag, "Accept-Encoding": "identity"})
        with urllib.request.urlopen(req, timeout=120) as r:
            validate_range(r.status, r.headers.get("Content-Range", ""), start, end, self.size)
            if r.headers.get("ETag") != self.etag:
                raise ValueError("source changed during extraction")
            data = r.read(length + 1)
        if len(data) != length:
            raise ValueError("truncated or oversized Range body")
        self.transferred += length
        self.receipts.append({"start": start, "end": end, "bytes": length, "sha256": digest(data)})
        # Cache probes, not multi-MB ranges; repeat receipt verification is cheap.
        if length <= PROBE:
            self.cache[key] = data
        return data

    def provenance(self):
        return {"url": self.url, "version_id": self.version, "etag": self.etag,
                "bytes": self.size, "last_modified": self.modified,
                "header_sha256": digest(self.header_raw), "header_bytes": len(self.header_raw),
                "downloaded_bytes": self.transferred, "ranges": self.receipts}


def metadata(output: Path):
    records, selected = [], {}
    for name in ("well.csv.gz", "crispr.csv.gz"):
        url = f"{METADATA_BASE}/{name}"
        target = output / name
        if not target.exists():
            with urllib.request.urlopen(url, timeout=120) as r:
                data = r.read(10 * 1024 * 1024 + 1)
            if len(data) > 10 * 1024 * 1024:
                raise ValueError("metadata exceeds bounded size")
            target.write_bytes(data)
        data = target.read_bytes()
        blob = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        if blob != METADATA_BLOBS[name]:
            raise ValueError("metadata differs from pinned public Git blob")
        picked = []
        with gzip.GzipFile(fileobj=io.BytesIO(data)) as r:
            header = next(csv.reader([r.readline().decode().rstrip("\r\n")]))
            for raw in r:
                row = parse_row(raw, header)
                if row.get("Metadata_JCP2022") not in GROUPS:
                    continue
                if name == "well.csv.gz" and (row.get("Metadata_Source") != "source_13"
                        or row.get("Metadata_Plate") not in {p for _, p in RUNS}):
                    continue
                picked.append({"values": row, "raw_row_sha256": digest(raw)})
                if name == "well.csv.gz":
                    selected[(row["Metadata_Plate"], row["Metadata_Well"])] = GROUPS[row["Metadata_JCP2022"]]
        records.append({"url": url, "git_blob": blob, "bytes": len(data), "sha256": digest(data), "selected_rows": picked})
    if not selected:
        raise ValueError("no control metadata found")
    return selected, records


def image_table(url: str, plate: str, wells: dict, output: Path):
    """Stream all Image.csv rows; store only small selected-column records."""
    receipt_path = output / f"{plate}-images.json"
    if receipt_path.exists():
        result = json.loads(receipt_path.read_text())
        if result["url"] != url:
            raise ValueError("cached Image.csv has another source URL")
        verify_raw(output / f"{plate}-Image-selected.csv.gz", result["header_sha256"], result["rows"], IMAGE_COLUMNS)
        return result
    total_hash = hashlib.sha256()
    size = 0
    rows = []
    raw_path = output / f"{plate}-Image-selected.csv.gz"
    with urllib.request.urlopen(url, timeout=120) as response, gzip.open(raw_path, "wb") as raw_out:
        expected = int(response.headers["Content-Length"])
        if expected > 128 * 1024 * 1024:
            raise ValueError("Image.csv exceeds safe streaming limit")
        header_raw = response.readline()
        header = next(csv.reader([header_raw.decode().rstrip("\r\n")]))
        total_hash.update(header_raw)
        size += len(header_raw)
        raw_out.write(header_raw)
        image_ids = set()
        for raw in response:
            offset = size
            size += len(raw)
            total_hash.update(raw)
            row = parse_row(raw, header)
            image_id = int(row["Image_ImageNumber"])
            if image_id in image_ids or row["Metadata_Plate"] != plate:
                raise ValueError("duplicate ImageNumber or incorrect plate")
            image_ids.add(image_id)
            if (plate, row["Metadata_Well"]) in wells:
                values = {key: row[key] for key in IMAGE_COLUMNS}
                filename_site = int(re.search(r"F(\d{3})L", values["FileName_OrigDNA"])[1])
                if filename_site != int(values["Metadata_Site"]) + 1:
                    raise ValueError("zero-based Metadata_Site does not match FileName_OrigDNA")
                rows.append({"values": values, "group": wells[(plate, row["Metadata_Well"])],
                             "raw_row_sha256": digest(raw), "byte_offset": offset, "bytes": len(raw)})
                raw_out.write(raw)
        if size != expected:
            raise ValueError("incomplete Image.csv")
        result = {"url": url, "bytes": size, "sha256": total_hash.hexdigest(),
                  "etag": response.headers.get("ETag"), "version_id": response.headers.get("x-amz-version-id"),
                  "header_sha256": digest(header_raw), "total_image_rows": len(image_ids), "rows": rows}
    receipt_path.write_text(json.dumps(result, indent=1) + "\n")
    return result


def summarize(rows: list[dict], plate: str, wells: dict):
    groups = {}
    for group in GROUPS.values():
        wanted = sorted(w for (p, w), g in wells.items() if p == plate and g == group)
        selected = [r for r in rows if r["group"] == group]
        for well in wanted:
            sites = [int(r["values"]["Metadata_Site"]) for r in selected if r["values"]["Metadata_Well"] == well]
            if sorted(sites) != list(range(9)):
                raise ValueError(f"missing/duplicate field: {plate} {well}")
        groups[group] = {"wells": wanted, "fields": len(selected)}
        for column in ("Count_Nuclei", "Count_NucleiIncludingEdges"):
            values = [float(r["values"][column]) for r in selected]
            if not values or any(not math.isfinite(v) or v < 0 or not v.is_integer() for v in values):
                raise ValueError("invalid published count")
            groups[group][column] = {"sum": int(sum(values)), "mean_per_field": sum(values) / len(values)}
    return {"groups": groups, "PLK1_divided_by_non_targeting": {
        c: groups["PLK1"][c]["mean_per_field"] / groups["Non-targeting"][c]["mean_per_field"]
        for c in ("Count_Nuclei", "Count_NucleiIncludingEdges")}}


def validate_objects(objects: list[dict], targets: dict[int, int]):
    for image_id, expected in targets.items():
        ids = [int(o["values"][1]) for o in objects if int(o["values"][0]) == image_id]
        if sorted(ids) != list(range(1, expected + 1)):
            raise ValueError(f"incomplete/duplicate objects for ImageNumber {image_id}: {len(ids)}/{expected}")


def extract_objects(source: RangeCSV, targets: dict[int, int], raw_output: Path):
    found: dict[tuple[int, int], dict] = {}
    seen_ranges: dict[tuple[int, int], list[int]] = {}
    search = []
    with gzip.open(raw_output, "wb") as raw_out:
        raw_out.write(source.header_raw)

        def collect(start: int, end: int):
            start, end = max(0, start), min(source.size - 1, end)
            if (start, end) in seen_ranges:
                return seen_ranges[(start, end)]
            data = source.get(start, end)
            image_numbers = []
            for offset, raw in complete_lines(data, start):
                if offset == 0:
                    continue
                # First two CSV columns are numeric; parse all columns only for targets.
                first = raw.split(b",", 2)
                image_id, object_id = int(first[0]), int(first[1])
                image_numbers.append(image_id)
                if image_id not in targets:
                    continue
                values = parse_row(raw, source.header)
                key = (image_id, object_id)
                entry = {"values": [values[c] for c in OBJECT_COLUMNS],
                         "raw_row_sha256": digest(raw), "byte_offset": offset, "bytes": len(raw)}
                if key in found:
                    if found[key] != entry:
                        raise ValueError("conflicting duplicate object or repeated source row")
                else:
                    found[key] = entry
                    raw_out.write(raw)
            seen_ranges[(start, end)] = image_numbers
            return image_numbers

        for target in sorted(targets):
            if sum(k[0] == target for k in found) == targets[target]:
                continue
            lo, hi = 0, source.size - 1
            center = 0
            for _ in range(24):
                center = (lo + hi) // 2
                numbers = collect(center, center + PROBE - 1)
                if not numbers:
                    raise ValueError("probe contains no complete CSV row")
                representative = sorted(numbers)[len(numbers) // 2]
                if target in numbers or hi - lo < BLOCK:
                    break
                if representative < target:
                    lo = center + 1
                else:
                    hi = center - 1
            search.append({"image_number": target, "approximate_center": center})
            # Out-of-order rows can lie beyond a sorted-search stopping point.
            # Expand symmetrically and check the published count after each block.
            for radius in range(64):
                starts = [center - BLOCK // 2] if radius == 0 else [center - BLOCK // 2 - radius * BLOCK,
                                                                  center - BLOCK // 2 + radius * BLOCK]
                for start in starts:
                    if start >= source.size or start + BLOCK <= 0:
                        continue
                    collect(max(0, start - PROBE), min(source.size - 1, start + BLOCK - 1))
                    if sum(k[0] == target for k in found) == targets[target]:
                        break
                if sum(k[0] == target for k in found) == targets[target]:
                    break
            else:
                raise ValueError(f"target {target} incomplete after bounded expansion")
        objects = sorted(found.values(), key=lambda o: (int(o["values"][0]), int(o["values"][1])))
        validate_objects(objects, targets)
    return objects, search


def verify_raw(path: Path, header_hash: str, records: list[dict], columns: list[str]):
    expected = {r["raw_row_sha256"]: r for r in records}
    observed = set()
    with gzip.open(path, "rb") as stream:
        raw_header = stream.readline()
        if digest(raw_header) != header_hash:
            raise ValueError("raw header hash mismatch")
        header = next(csv.reader([raw_header.decode().rstrip("\r\n")]))
        for raw in stream:
            sha = digest(raw)
            if sha not in expected or sha in observed:
                raise ValueError("unexpected or duplicate raw row")
            row = parse_row(raw, header)
            record = expected[sha]
            actual = [row[c] for c in columns]
            values = record["values"]
            if actual != ([values[c] for c in columns] if isinstance(values, dict) else values):
                raise ValueError("extracted values differ from raw row")
            if len(raw) != record["bytes"]:
                raise ValueError("raw row byte count mismatch")
            observed.add(sha)
    if observed != set(expected):
        raise ValueError("missing raw rows")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--write-reference", action="store_true")
    args = parser.parse_args()
    output = args.output.resolve()
    if output == ROOT or ROOT in output.parents:
        raise SystemExit("raw public CSV rows must remain outside the checkout")
    output.mkdir(parents=True, exist_ok=True)
    if args.verify:
        reference = json.loads(REFERENCE.read_text())
        for archive in reference["metadata"]:
            data = (output / archive["url"].rsplit("/", 1)[1]).read_bytes()
            if len(data) != archive["bytes"] or digest(data) != archive["sha256"]:
                raise ValueError("metadata archive checksum mismatch")
        for plate in reference["plates"]:
            name = plate["plate"]
            verify_raw(output / f"{name}-Image-selected.csv.gz", plate["image_source"]["header_sha256"],
                       plate["all_control_fields"], IMAGE_COLUMNS)
            verify_raw(output / f"{name}-Nuclei-selected.csv.gz", plate["nuclei_source"]["header_sha256"],
                       plate["objects"], OBJECT_COLUMNS)
            validate_objects(plate["objects"], {int(r["values"]["Image_ImageNumber"]): int(float(r["values"]["Count_Nuclei"]))
                                             for r in plate["selected_fields"]})
        print(json.dumps({"verified_plates": len(reference["plates"])}))
        return
    wells, meta = metadata(output)
    progress_path = output / "reference-progress.json"
    previous = json.loads(progress_path.read_text()) if progress_path.exists() else {}
    completed = {p["plate"]: p for p in previous.get("plates", [])}
    result = json.loads(REFERENCE.read_text())
    result.update({"status": "verified_extraction", "metadata": meta, "object_columns": OBJECT_COLUMNS,
                   "source_publication": "Chandrasekaran SN et al. Morphological map of under- and overexpression of genes in human cells. Nature Methods (2025). doi:10.1038/s41592-025-02753-9",
                   "reference_scope": "Published CellProfiler tables for the exact registered images. No segmentation settings or thresholds were tuned against them.",
                   "row_hash_definition": "SHA-256 of original UTF-8 CSV row bytes including original newline; offsets zero based",
                   "summary_definition": "Arithmetic mean of all nine fields of every metadata-assigned PLK1/non-targeting well on each plate; ratio is PLK1 mean / non-targeting mean; source-table summary, not Cytellect analysis or biological n.",
                   "completeness": "Approximate order only locates candidate ranges. Require exact unique ObjectNumber set 1..Count_Nuclei for every selected image. No full-download fallback.",
                   "license_source": "https://github.com/broadinstitute/cellpainting-gallery#citationlicense",
                   "license_readme_git_blob": "ae86e4e04d31b40dfaf913d1ea4df573e72e25d5",
                   "license_quoted": "All the data is released with CC0 1.0 Universal (CC0 1.0).",
                   "caveats": ["CellProfiler measurements are a published algorithmic reference, not manually annotated ground truth.",
                               "Nuclei.csv corresponds to Count_Nuclei, not Count_NucleiIncludingEdges; boundary filtering differs from Cytellect.",
                               "DNA mean intensity is the source pipeline DNA measurement, not necessarily raw TIFF intensity. No rescaling is inferred.",
                               "All-well counts are descriptive; fields and wells are not independent experimental replicates."],
                   "plates": []})
    for batch, plate in RUNS:
        prefix = f"{BASE}/workspace/analysis/{batch}/{plate}/analysis/{plate}"
        images = image_table(f"{prefix}/Image.csv", plate, wells, output)
        selected = [r for r in images["rows"] if r["values"]["Metadata_Well"] in ("A02", "A23")
                    and int(r["values"]["Metadata_Site"]) in (3, 4, 5)]
        if len(selected) != 6:
            raise ValueError("fixed selection must contain six images per plate")
        targets = {int(r["values"]["Image_ImageNumber"]): int(float(r["values"]["Count_Nuclei"])) for r in selected}
        if plate in completed:
            record = completed[plate]
            if record["selected_fields"] != selected or record["all_control_fields"] != images["rows"]:
                raise ValueError("cached extraction differs from the fixed image selection")
            if record["nuclei_source"]["url"] != f"{prefix}/Nuclei.csv":
                raise ValueError("cached extraction uses a different source")
            verify_raw(output / f"{plate}-Image-selected.csv.gz", images["header_sha256"], images["rows"], IMAGE_COLUMNS)
            verify_raw(output / f"{plate}-Nuclei-selected.csv.gz", record["nuclei_source"]["header_sha256"], record["objects"], OBJECT_COLUMNS)
            validate_objects(record["objects"], targets)
            if record["all_well_summary"] != summarize(images["rows"], plate, wells):
                raise ValueError("cached all-well summary mismatch")
            result["plates"].append(record)
            print(json.dumps({"plate": plate, "verified_cached_objects": len(record["objects"])}), flush=True)
            continue
        source = RangeCSV(f"{prefix}/Nuclei.csv")
        objects, search = extract_objects(source, targets, output / f"{plate}-Nuclei-selected.csv.gz")
        record = {"plate": plate, "batch": batch, "image_source": {k: v for k, v in images.items() if k != "rows"},
                  "nuclei_source": source.provenance(), "selected_fields": selected,
                  "all_control_fields": images["rows"], "all_well_summary": summarize(images["rows"], plate, wells),
                  "search": search, "objects": objects}
        result["plates"].append(record)
        (output / "reference-progress.json").write_text(json.dumps(result, indent=1) + "\n")
        print(json.dumps({"plate": plate, "objects": len(objects), "range_bytes": source.transferred,
                          "all_well_summary": record["all_well_summary"]}), flush=True)
    (output / "cellprofiler-reference.json").write_text(reference_json(result) + "\n", encoding="utf-8", newline="\n")
    if args.write_reference:
        REFERENCE.write_text(reference_json(result) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
