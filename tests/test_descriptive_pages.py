"""Full-field coverage, real vector pages and recoverable presentation failures."""
import csv
import hashlib
import json
import xml.etree.ElementTree as ET

import pytest
from cytellect_analysis.descriptive import describe_regions
from cytellect_analysis.descriptive_contracts import DescriptiveRequest, parse_descriptive_request
from cytellect_analysis.descriptive_output import (
    copy_descriptive_output,
    render_descriptive_output,
    validate_descriptive_output,
)
from cytellect_analysis.descriptive_pages import page_layout
from cytellect_analysis.exports_csv import csv_sha256, write_csv
from cytellect_analysis.images import sha256
from matplotlib.figure import Figure
from pydantic import ValidationError
from test_descriptive import region_fixture, request


def description(count=1, *, preset="nature-double", language="en", empty_fields=(), **plot):
    report, snapshots = region_fixture(field_id="f001")
    for index in range(2, count + 1):
        fid = f"f{index:03d}"
        other, snapshot = region_fixture(field_id=fid, empty=index in empty_fields)
        report["field_tables"].update(other["field_tables"])
        snapshots.update(snapshot)
    spec = request(plot={"preset": preset, "language": language, **plot}).model_dump(mode="json")
    spec["figure_policy"] = {"version": "2.0.0", "layout": "field-pages"}
    result = describe_regions(report, snapshots, parse_descriptive_request(spec))
    result["revision_id"] = "revision"
    return result, report, snapshots


def test_old_contract_dump_and_all_numerical_fields_are_unchanged():
    paged, report, snapshots = description()
    legacy_spec = {key: value for key, value in paged["spec"].items() if key != "figure_policy"}
    old = DescriptiveRequest.model_validate(legacy_spec)
    assert parse_descriptive_request(legacy_spec).model_dump(mode="json") == old.model_dump(mode="json")
    legacy = describe_regions(report, snapshots, old)
    assert paged["descriptive_version"] == legacy["descriptive_version"] == "1.0.0"
    assert {key: value for key, value in paged.items() if key not in ("spec", "revision_id")} == {
        key: value for key, value in legacy.items() if key != "spec"}
    assert "figure_policy" not in legacy["spec"]
    assert [row["value"] for row in paged["plot_data"]] == [-5, 9]


@pytest.mark.parametrize("policy", [None, {"version": "3.0.0", "layout": "field-pages"},
                                    {"version": "2.0.0", "layout": "selected-fields"},
                                    {"version": "2.0.0", "layout": "field-pages", "fields": ["f001"]}])
def test_unknown_or_null_policy_cannot_reinterpret_old_request(policy):
    spec = request().model_dump(mode="json")
    spec["figure_policy"] = policy
    with pytest.raises(ValidationError):
        parse_descriptive_request(spec)


@pytest.mark.parametrize(("count", "preset", "lengths"), [
    (1, "nature-single", [1]), (4, "nature-single", [4]), (5, "nature-single", [4, 1]),
    (8, "nature-double", [8]), (9, "nature-double", [8, 1]), (100, "nature-double", [8] * 12 + [4]),
])
def test_page_boundaries_keep_global_order_without_dropping_fields(count, preset, lengths):
    result, _, _ = description(count, preset=preset)
    layout = page_layout(result)
    assert [len(page["field_ids"]) for page in layout["page_plan"]] == lengths
    assert [fid for page in layout["page_plan"] for fid in page["field_ids"]] == [f"f{i:03d}" for i in range(1, count + 1)]
    assert [n for page in layout["page_plan"] for n in page["field_numbers"]] == list(range(1, count + 1))
    assert result["counts"]["experimental_units"] is None


@pytest.mark.parametrize(("language", "preset"), [("en", "nature-double"), ("ja", "nature-single")])
def test_actual_pages_share_axes_and_preserve_empty_fields_and_source_tables(tmp_path, monkeypatch, language, preset):
    result, _, _ = description(9, language=language, preset=preset, empty_fields=(5, 6, 7, 8, 9))
    scales = []
    original = Figure.savefig

    def record(figure, *args, **kwargs):
        scales.append((list(figure.axes[0].get_ylim()), list(figure.axes[0].get_yticks())))
        return original(figure, *args, **kwargs)

    monkeypatch.setattr(Figure, "savefig", record)
    result["figure"] = render_descriptive_output(result, tmp_path)
    figure = result["figure"]
    assert figure["status"] == "ready"
    assert all(scale == (figure["y_limits"], figure["y_ticks"]) for scale in scales)
    assert len(scales) == 3 * len(figure["pages"])
    assert figure["page_plan"][-1]["field_numbers"][-1] == 9
    last_svg = tmp_path / figure["pages"][-1]["files"]["svg"]
    svg = ET.parse(last_svg).getroot()
    assert svg.findall(".//{http://www.w3.org/2000/svg}text")
    assert not svg.findall(".//{http://www.w3.org/2000/svg}image")
    text = last_svg.read_text(encoding="utf-8")
    assert ("視野 9" if language == "ja" else "Field 9") in text
    assert ("0 観測" if language == "ja" else "0 obs.") in text
    assert b"/FontFile2" in (tmp_path / figure["pages"][0]["files"]["pdf"]).read_bytes()
    with (tmp_path / "plot-data.csv").open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 8 and [float(row["value"]) for row in rows] == [-5, 9] * 4
    assert result["field_summary"][-1]["status"] == "no_regions"
    validate_descriptive_output(result, tmp_path)


def test_actual_hundred_field_output_has_thirteen_complete_pages(tmp_path):
    result, _, _ = description(100)
    result["figure"] = render_descriptive_output(result, tmp_path)
    assert result["figure"]["status"] == "ready"
    assert len(result["figure"]["pages"]) == 13
    assert len(list(tmp_path.glob("figure-*.svg"))) == 13
    with (tmp_path / "plot-data.csv").open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 200
    assert [float(row["value"]) for row in rows] == [-5, 9] * 100
    assert len({row["observation_id"] for row in rows}) == 200
    assert "Field 100" in (tmp_path / "figure-013.svg").read_text(encoding="utf-8")
    assert result["counts"]["experimental_units"] is None
    assert not (tmp_path / "comparisons.csv").exists()
    validate_descriptive_output(result, tmp_path)


def test_actual_layout_failure_retains_all_tables_and_wider_new_output_recovers(tmp_path):
    result, _, _ = description(9, preset="nature-single", x_label="W" * 60)
    first = tmp_path / "first"
    result["figure"] = render_descriptive_output(result, first)
    assert result["figure"]["status"] == "tables_only"
    assert result["figure"]["error"]["code"] == "figure_text_outside_canvas"
    assert not result["figure"]["pages"] and not list(first.glob("figure-*.svg"))
    assert (first / "plot-data.csv").is_file()
    assert "No figure was produced" in (first / "figure-caption.md").read_text(encoding="utf-8")
    copy_descriptive_output(result, first, tmp_path / "copy")
    original_hashes = {path.name: sha256(path) for path in first.iterdir()}
    fresh = {key: value for key, value in result.items() if key != "figure"}
    fresh["spec"] = {**fresh["spec"], "plot": {**fresh["spec"]["plot"], "preset": "nature-double"}}
    fresh["figure"] = render_descriptive_output(fresh, tmp_path / "wide")
    assert fresh["figure"]["status"] == "ready"
    assert fresh["plot_data"] == result["plot_data"]
    assert original_hashes == {path.name: sha256(path) for path in first.iterdir()}


def test_font_failure_recovers_but_source_mismatch_and_io_errors_do_not(tmp_path, monkeypatch):
    result, _, _ = description(y_label="Unsupported \u0378")
    result["figure"] = render_descriptive_output(result, tmp_path / "font")
    assert result["figure"]["status"] == "tables_only"
    assert result["figure"]["error"] == {"code": "figure_font_glyphs_unavailable", "page_index": None}
    valid, _, _ = description()
    valid["counts"]["observations"] += 1
    with pytest.raises(ValueError, match="source_mismatch"):
        render_descriptive_output(valid, tmp_path / "source")
    assert not (tmp_path / "source").exists()
    valid["counts"]["observations"] -= 1

    def write_failed(*args, **kwargs):
        raise OSError("fixture_write_failed")

    monkeypatch.setattr(Figure, "savefig", write_failed)
    with pytest.raises(OSError, match="fixture_write_failed"):
        render_descriptive_output(valid, tmp_path / "io")
    assert not list((tmp_path / "io").glob("figure-*.svg"))


def test_rehashed_page_mapping_or_csv_cannot_change_the_saved_source(tmp_path):
    result, _, _ = description(9)
    result["figure"] = render_descriptive_output(result, tmp_path)
    altered = json.loads(json.dumps(result))
    altered["figure"]["page_plan"][1]["field_ids"] = ["f001"]
    with pytest.raises(ValueError, match="manifest_mismatch"):
        validate_descriptive_output(altered, tmp_path)
    source_path = tmp_path / "plot-data.csv"
    source_path.write_bytes(source_path.read_bytes().replace(b"-5.0", b"99.0"))
    altered = json.loads(json.dumps(result))
    altered["figure"]["files"]["plot-data.csv"] = {"sha256": sha256(source_path), "bytes": source_path.stat().st_size}
    doc_path = tmp_path / "figure-data.json"
    doc = json.loads(doc_path.read_text(encoding="utf-8"))
    doc["source_hashes"]["plot-data.csv"] = sha256(source_path)
    doc_path.write_text(json.dumps(doc), encoding="utf-8")
    altered["figure"]["files"]["figure-data.json"] = {"sha256": sha256(doc_path), "bytes": doc_path.stat().st_size}
    (tmp_path / "descriptive-output.json").write_text(json.dumps(altered["figure"]), encoding="utf-8")
    with pytest.raises(ValueError, match="source_mismatch"):
        validate_descriptive_output(altered, tmp_path)


def test_canonical_csv_hash_retains_exact_bytes_without_temporary_research_files(tmp_path, monkeypatch):
    rows = [{"value": -5.25, "note": "=formula", "label": "検証", "absent": None},
            {"value": 0, "note": "line\nwith,comma", "label": "@literal", "other": True}]
    expected = ("\ufeffvalue,note,label,absent,other\n"
                "-5.25,'=formula,検証,,\n"
                "0,\"line\nwith,comma\",'@literal,,True\n").encode("utf-8")
    path = tmp_path / "reference.csv"
    write_csv(path, rows)
    assert path.read_bytes() == expected
    assert csv_sha256(rows) == hashlib.sha256(expected).hexdigest()
    result, _, _ = description()
    saved = tmp_path / "saved"
    result["figure"] = render_descriptive_output(result, saved)

    def forbidden(*args, **kwargs):
        raise AssertionError("verification_must_not_write_a_temporary_file")

    monkeypatch.setattr("cytellect_analysis.descriptive_output.TemporaryDirectory", forbidden)
    validate_descriptive_output(result, saved)


def test_later_page_failure_never_publishes_an_incomplete_figure_set(tmp_path, monkeypatch):
    import cytellect_analysis.descriptive_pages as pages

    result, _, _ = description(9)
    real_check, calls = pages._validate_text_layout, 0

    def fail_second(figure, axes):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise ValueError("figure_labels_overlap")
        real_check(figure, axes)

    monkeypatch.setattr(pages, "_validate_text_layout", fail_second)
    result["figure"] = render_descriptive_output(result, tmp_path)
    assert calls == 2
    assert result["figure"]["status"] == "tables_only"
    assert result["figure"]["error"] == {"code": "figure_labels_overlap", "page_index": 2}
    assert not result["figure"]["pages"] and not list(tmp_path.glob("figure-*.svg"))
    assert not list(tmp_path.glob(".descriptive-pages-*"))
    assert result["counts"]["observations"] == 18
    validate_descriptive_output(result, tmp_path)
