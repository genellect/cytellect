"""Actual vector/PNG renders with source-data and non-inference acceptance checks."""
import csv
import hashlib
import json
import xml.etree.ElementTree as ET

import pytest
from cytellect_analysis.descriptive import describe_regions
from cytellect_analysis.descriptive_figures import descriptive_methods, render_descriptive
from PIL import Image
from test_descriptive import region_fixture, request


@pytest.mark.parametrize("language", ["en", "ja"])
@pytest.mark.parametrize(("preset", "width"), [("nature-single", 89), ("nature-double", 183)])
def test_actual_descriptive_vectors_preserve_values_without_inference(tmp_path, language, preset, width):
    report, snapshots = region_fixture()
    result = describe_regions(report, snapshots, request(plot={"language": language, "preset": preset}))
    manifest = render_descriptive(result, tmp_path)
    svg = ET.parse(tmp_path / "figure.svg").getroot()
    assert float(svg.attrib["width"].removesuffix("pt")) / 72 * 25.4 == pytest.approx(width, abs=1e-5)
    assert svg.findall(".//{http://www.w3.org/2000/svg}text")
    assert not svg.findall(".//{http://www.w3.org/2000/svg}image")
    pdf = (tmp_path / "figure.pdf").read_bytes()
    assert b"/FontFile2" in pdf and b"/CIDFontType2" in pdf
    with Image.open(tmp_path / "figure.png") as image:
        assert image.width == pytest.approx(width / 25.4 * 300, abs=1)
    with (tmp_path / "plot-data.csv").open(encoding="utf-8-sig", newline="") as stream:
        exported = list(csv.DictReader(stream))
    assert [float(row["value"]) for row in exported] == [-5, 9]
    assert [row["observation_id"] for row in exported] == [row["observation_id"] for row in result["plot_data"]]
    source = json.loads((tmp_path / "figure-data.json").read_text(encoding="utf-8"))
    assert source["counts"]["experimental_units"] is None
    assert source["plot_data"] == result["plot_data"]
    assert source["source_fields"][0]["channel_provenance"][0]["channel"]["stain"] == "phalloidin"
    for name, digest in source["source_hashes"].items():
        assert hashlib.sha256((tmp_path / name).read_bytes()).hexdigest() == digest
    assert set(manifest["source_files"]) == {item.name for item in tmp_path.iterdir()}
    assert not (tmp_path / "comparisons.csv").exists()
    assert not (tmp_path / "experimental-units.csv").exists()
    text = (tmp_path / "figure.svg").read_text(encoding="utf-8")
    assert "95%" not in text and "n =" not in text and "p =" not in text
    assert "Actin" in text
    caption = (tmp_path / "figure-caption.md").read_text(encoding="utf-8")
    assert ("独立性を判定していない" if language == "ja" else "not assessed") in caption
    assert "phalloidin" in caption and "field_id=f1" in caption
    assert "channel_id=actin; label=Actin; stain=phalloidin" in caption
    assert "No hypothesis test" in descriptive_methods(result)
    assert source["font_metadata"]["style"] == "normal"


def test_single_observation_is_plotted_and_empty_field_stays_visible(tmp_path):
    report, snapshots = region_fixture()
    report["exclusions"].append({"field_id": "f1", "region_id": 7, "reason": "edge review"})
    empty, empty_snapshot = region_fixture(empty=True, field_id="a_empty")
    report["field_tables"].update(empty["field_tables"])
    snapshots.update(empty_snapshot)
    result = describe_regions(report, snapshots, request())
    render_descriptive(result, tmp_path)
    svg = (tmp_path / "figure.svg").read_text(encoding="utf-8")
    assert "0 obs." in svg and "1 obs." in svg and "Field median" in svg
    source = json.loads((tmp_path / "figure-data.json").read_text(encoding="utf-8"))
    assert len(source["plot_data"]) == 1 and source["plot_data"][0]["value"] == 9
    assert source["field_summary"][0]["status"] == "no_regions"


def test_figure_rejects_source_mismatch_and_inferential_payload(tmp_path):
    report, snapshots = region_fixture()
    result = describe_regions(report, snapshots, request())
    result["comparisons"] = []
    with pytest.raises(ValueError, match="inference_not_allowed"):
        render_descriptive(result, tmp_path)
    result.pop("comparisons")
    result["counts"]["observations"] = 99
    with pytest.raises(ValueError, match="source_mismatch"):
        render_descriptive(result, tmp_path)


def test_long_literal_labels_fail_before_output(tmp_path):
    report, snapshots = region_fixture()
    result = describe_regions(report, snapshots, request(plot={"y_label": "W" * 120}))
    with pytest.raises(ValueError, match="figure_text_outside_canvas"):
        render_descriptive(result, tmp_path)
    assert not list(tmp_path.glob("figure.*"))
