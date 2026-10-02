"""Strict import of measured numerical assays; no instrument-specific inference."""
import csv
import io
import math
from typing import Any

from .statistics import analyze

REQUIRED = {"condition", "experimental_unit", "sample", "field_id", "acquisition_date", "value"}
OPTIONAL = {"pair", "repeat_length", "unit", "assay"}


def parse_numeric_csv(content: bytes):
    if len(content) > 8 * 1024 * 1024:
        raise ValueError("numeric_csv_too_large")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("numeric_csv_requires_utf8") from exc
    reader = csv.DictReader(io.StringIO(text), strict=True)
    names = reader.fieldnames or []
    if len(names) != len(set(names)) or not REQUIRED.issubset(names) or set(names) - REQUIRED - OPTIONAL:
        raise ValueError("numeric_csv_columns_invalid")
    rows: list[dict[str, Any]] = []
    field_metadata: dict[str, tuple] = {}
    try:
        for raw in reader:
            if len(rows) >= 100000 or None in raw or any(value is None for value in raw.values()):
                raise ValueError("numeric_csv_rows_invalid")
            row = {key: value.strip() for key, value in raw.items()}
            for key in REQUIRED - {"value"}:
                if not row[key] or len(row[key]) > 80:
                    raise ValueError("numeric_csv_metadata_invalid")
            for key in OPTIONAL & set(row):
                if len(row[key]) > 120:
                    raise ValueError("numeric_csv_metadata_invalid")
            try:
                value = float(row["value"])
                length = float(row["repeat_length"]) if row.get("repeat_length") else None
            except ValueError as exc:
                raise ValueError("numeric_csv_nonfinite_value") from exc
            if not math.isfinite(value) or (length is not None and (not math.isfinite(length) or length < 0)):
                raise ValueError("numeric_csv_nonfinite_value")
            row.update(value=value, repeat_length=length, pair=row.get("pair") or None,
                       excluded=False, gfp_positive=True)
            metadata = tuple(row[key] for key in ("condition", "experimental_unit", "sample", "acquisition_date", "pair"))
            if row["field_id"] in field_metadata and field_metadata[row["field_id"]] != metadata:
                raise ValueError("inconsistent_field_metadata")
            field_metadata[row["field_id"]] = metadata
            rows.append(row)
    except csv.Error as exc:
        raise ValueError("numeric_csv_malformed") from exc
    if not rows:
        raise ValueError("numeric_csv_empty")
    units = {row.get("unit", "") for row in rows}
    assays = {row.get("assay", "") for row in rows}
    if len(units) != 1 or len(assays) != 1:
        raise ValueError("numeric_csv_single_assay_and_unit_required")
    return {"rows": rows, "metadata": {"unit": next(iter(units)), "assay": next(iter(assays)),
                                      "row_count": len(rows), "conditions": sorted({row["condition"] for row in rows}), "kind": "measured-numerical-assay"}}


def analyze_numeric(rows, request):
    if request.mode != "experimental-unit" or request.metric != "value":
        raise ValueError("numeric_assay_requires_experimental_unit_value")
    if request.plot.kind == "scatter":
        raise ValueError("numeric_assay_has_no_gfp_scatter")
    if (getattr(request, "sensitivity_gfp_thresholds", []) or getattr(request, "sensitivity_complete_dates", False)
            or getattr(request, "sensitivity_legacy_high_regions", [])):
        raise ValueError("numeric_assay_image_sensitivities_not_applicable")
    result = analyze(rows, request)
    result["source_kind"] = "measured-numerical-assay"
    result["unit"] = rows[0].get("unit", "")
    result["assay"] = rows[0].get("assay", "")
    for count in result["counts"]:
        count["observations"] = count.pop("cells")
    return result
