"""Actual generic EN/JA publication exports, independently tied to source values."""
import csv
import hashlib
import json
import xml.etree.ElementTree as ET

import pytest
from cytellect_analysis.region_comparison import compare_regions
from cytellect_analysis.region_comparison_figures import region_comparison_methods, render_region_comparison
from PIL import Image
from test_region_comparison import comparison_fixture, comparison_request


@pytest.mark.parametrize("language", ["en", "ja"])
@pytest.mark.parametrize("paired", [False, True])
def test_actual_vectors_keep_source_identity_unit_n_and_comparison_family(tmp_path, language, paired):
    report, config = comparison_fixture((('A', [3, 8, 2]), ('B', [4, 10, 5])))
    request = comparison_request(paired=paired, plot={"preset": "nature-single", "language": language,
                                                     "kind": "paired" if paired else "distribution"})
    result = compare_regions(report, config, request)
    manifest = render_region_comparison(result, tmp_path)
    svg = ET.parse(tmp_path / "figure.svg").getroot()
    assert float(svg.attrib["width"].removesuffix("pt")) / 72 * 25.4 == pytest.approx(89, abs=1e-5)
    assert svg.findall(".//{http://www.w3.org/2000/svg}text")
    assert not svg.findall(".//{http://www.w3.org/2000/svg}image")
    text = (tmp_path / "figure.svg").read_text(encoding="utf-8")
    assert "Actin" in text and "GFP" not in text and "NCL" not in text
    assert "n = 3" in text and "n = 6" not in text
    pdf = (tmp_path / "figure.pdf").read_bytes()
    assert b"/FontFile2" in pdf and b"/CIDFontType2" in pdf
    with Image.open(tmp_path / "figure.png") as png:
        assert png.width == pytest.approx(89 / 25.4 * 300, abs=1)
    with (tmp_path / "comparisons.csv").open(encoding="utf-8-sig", newline="") as stream:
        contrast = list(csv.DictReader(stream))[0]
    assert float(contrast["estimate"]) == pytest.approx(-2)
    assert int(contrast["n_a"]) == 3
    with (tmp_path / "sample-summary.csv").open(encoding="utf-8-sig", newline="") as stream:
        summaries = list(csv.DictReader(stream))
    assert [float(row["value"]) for row in summaries] == [3, 8, 2, 4, 10, 5]
    source = json.loads((tmp_path / "figure-data.json").read_text(encoding="utf-8"))
    assert source["spec"] == result["spec"]
    assert source["source_fingerprint"] == result["source_fingerprint"]
    assert source["plot_data"] == result["plot_data"]
    assert source["unit_summary"] == result["unit_summary"]
    assert source["channel"]["stain"] == "phalloidin"
    for name, digest in source["source_hashes"].items():
        assert hashlib.sha256((tmp_path / name).read_bytes()).hexdigest() == digest
    assert set(manifest["source_files"]) == {file.name for file in tmp_path.iterdir()}
    caption = (tmp_path / "figure-caption.md").read_text(encoding="utf-8")
    assert "phalloidin" in caption and "actin" in caption and "Cell interiors" in caption
    assert ("同時信頼区間ではない" if language == "ja" else "not simultaneous") in caption
    assert "independent units=3/3" in caption and "regions=6" in caption
    assert "Holm" in region_comparison_methods(result)


def test_reordered_groups_keep_saved_source_spec_and_literal_labels(tmp_path):
    report, config = comparison_fixture()
    result = compare_regions(report, config, comparison_request(plot={"group_order": ["B", "A"], "preset": "nature-double"}))
    render_region_comparison(result, tmp_path)
    source = json.loads((tmp_path / "figure-data.json").read_text(encoding="utf-8"))
    assert source["spec"]["plot"]["group_order"] == ["B", "A"]
    assert source["comparisons"][0]["estimate"] == -3


def test_no_figure_is_saved_for_unrenderable_literal_label(tmp_path):
    report, config = comparison_fixture()
    result = compare_regions(report, config, comparison_request(plot={"y_label": "W" * 120}))
    with pytest.raises(ValueError, match="figure_text_outside_canvas"):
        render_region_comparison(result, tmp_path)
    assert not list(tmp_path.glob("figure.*"))


@pytest.mark.parametrize(("language", "label"), [("en", "検証信号"), ("ja", "Verified marker")])
@pytest.mark.filterwarnings("error:Glyph .* missing from font")
def test_actual_comparison_mixed_script_labels_preserve_literal_source_and_numbers(tmp_path, language, label):
    report, config = comparison_fixture()
    report["recipe"]["label"] = config["recipe"]["label"] = "測定領域"
    for fid, table in report["field_tables"].items():
        table["region_set"]["label"] = "測定領域"
        for entry in table["channel_provenance"]:
            if entry["channel"]["channel_id"] == "actin":
                entry["channel"]["label"] = label
        for channel in config["field_snapshot"][fid]["image_info"]["channels"]:
            if channel["channel_id"] == "actin":
                channel["label"] = label
    result = compare_regions(report, config, comparison_request(plot={"language": language}))
    manifest = render_region_comparison(result, tmp_path)
    assert result["comparisons"][0]["estimate"] == -3
    assert manifest["figure_version"] == "1.1.3"
    text = (tmp_path / "figure.svg").read_text(encoding="utf-8")
    assert label in text and "GFP" not in text
    assert "測定領域" in (tmp_path / "figure-caption.md").read_text(encoding="utf-8")
    assert b"/FontFile2" in (tmp_path / "figure.pdf").read_bytes()
    source = json.loads((tmp_path / "figure-data.json").read_text(encoding="utf-8"))
    assert source["plot_data"] == result["plot_data"] and source["spec"] == result["spec"]
    assert source["font_metadata"]["sha256"] == manifest["font_metadata"]["sha256"]
