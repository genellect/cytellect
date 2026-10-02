"""Physical export and source integrity gates, distinct from biological validity."""
import csv
import hashlib
import json
import re
import xml.etree.ElementTree as ET

import pytest
from cytellect_analysis.contracts import PlotSpec, StatisticsRequest
from cytellect_analysis.figures import figure_settings, render_figures
from cytellect_analysis.statistics import analyze
from PIL import Image


def result(kind="distribution", preset="nature-single", paired=False, mode="experimental-unit"):
    rows = []
    for group, effect in (("Control", 0), ("Treatment", 2)):
        for unit in range(4):
            for cell in range(3):
                rows.append({"condition": group, "experimental_unit": f"{group}{unit}",
                             "sample": f"{group}{unit}", "field_id": f"{group}{unit}",
                             "acquisition_date": "date", "ncl_nucleus_mean_corrected": effect + unit*.3 + cell*.2 + effect*unit*.05
                             + (-1)**(unit+cell)*.11, "pair": f"p{unit}", "gfp_mean_corrected": 2**(cell+unit*.17),
                             "excluded": False, "gfp_positive": True})
    request = StatisticsRequest(metric="ncl_nucleus_mean_corrected", baseline="Control",
                                comparisons=[("Control", "Treatment")], independent_units_confirmed=True,
                                mode=mode, paired=paired, plot=PlotSpec(kind=kind, preset=preset))
    return analyze(rows, request)


@pytest.mark.parametrize(("preset", "width"), [("nature-single", 89), ("nature-double", 183)])
def test_physical_dimensions_editable_text_and_embedded_font(tmp_path, preset, width):
    meta = render_figures(result(preset=preset), tmp_path)
    svg = ET.parse(tmp_path/"figure.svg").getroot()
    assert float(svg.attrib["width"].removesuffix("pt")) / 72 * 25.4 == pytest.approx(width, abs=1e-5)
    assert float(svg.attrib["height"].removesuffix("pt")) / 72 * 25.4 <= 170
    assert svg.findall(".//{http://www.w3.org/2000/svg}text")
    assert not svg.findall(".//{http://www.w3.org/2000/svg}image")  # vector scientific panel
    pdf = (tmp_path/"figure.pdf").read_bytes()
    assert b"/FontFile2" in pdf and b"/CIDFontType2" in pdf
    with Image.open(tmp_path/"figure.png") as im:
        assert im.width == pytest.approx(width / 25.4 * 300, abs=1)
        assert im.info["dpi"][0] == pytest.approx(300, abs=.01)
    assert meta["style"]["font_size_pt"] == 7
    text = (tmp_path/"figure.svg").read_text(encoding="utf-8")
    assert "Nuclear NCL" in text
    sizes = [float(s) for s in re.findall(r"font-size:\s*([\d.]+)px", text)]
    assert all(5 <= s <= 7 for s in sizes)


def test_sources_counts_pairing_and_exact_statistics_are_exported(tmp_path):
    data = result(kind="paired", paired=True)
    data["revision_id"] = "reviewed-revision"
    render_figures(data, tmp_path)
    svg = (tmp_path/"figure.svg").read_text(encoding="utf-8")
    assert "Paired comparison" in svg
    caption = (tmp_path/"figure-caption.md").read_text(encoding="utf-8")
    assert "independent units=4" in caption and "observations=12" in caption
    assert "Holm p=None" not in caption
    source = json.loads((tmp_path/"figure-data.json").read_text(encoding="utf-8"))
    assert source["revision_id"] == "reviewed-revision"
    assert source["means"] == data["means"] and source["counts"] == data["counts"]
    assert set(source["unit_glyphs"]) == {"p0", "p1", "p2", "p3"}
    for name, digest in source["source_hashes"].items():
        assert hashlib.sha256((tmp_path/name).read_bytes()).hexdigest() == digest
    with (tmp_path/"plot-data.csv").open(encoding="utf-8-sig", newline="") as stream:
        assert len(list(csv.DictReader(stream))) == 24


def test_scatter_uses_saved_cluster_predictions_or_no_inference(tmp_path):
    unit = render_figures(result(kind="scatter"), tmp_path/"unit")
    assert unit["scatter_band"] is None
    assert not (tmp_path/"unit/model-predictions.csv").exists()
    model = result(kind="scatter", mode="exploratory")
    meta = render_figures(model, tmp_path/"model")
    assert meta["scatter_band"] == "field-clustered CRV1 pointwise 95% mean CI"
    with (tmp_path/"model/model-predictions.csv").open(encoding="utf-8-sig", newline="") as stream:
        prediction = list(csv.DictReader(stream))
    assert len(prediction) == len(model["model"]["prediction_grid"])
    assert float(prediction[0]["ci_low"]) == model["model"]["prediction_grid"][0]["ci_low"]
    assert "clustered CRV1" in (tmp_path/"model/figure-caption.md").read_text(encoding="utf-8")


def test_nature_preset_rejects_noncompliant_dimensions_and_text():
    with pytest.raises(ValueError, match="170mm"):
        figure_settings(PlotSpec(height_inches=7).model_dump())
    with pytest.raises(ValueError, match="font"):
        figure_settings(PlotSpec(font_size=8).model_dump())
    custom = figure_settings(PlotSpec(preset="custom", width_inches=9, font_size=12).model_dump())
    assert custom["width_inches"] == 9 and custom["font_size_pt"] == 12


def test_plot_cannot_hide_missing_gfp_or_mislabel_paired_inference(tmp_path):
    with pytest.raises(ValueError, match="paired_inference"):
        render_figures(result(kind="paired", paired=False), tmp_path/"unpaired")
    data = result(kind="scatter")
    data["plot_data"][0]["gfp_mean_corrected"] = None
    with pytest.raises(ValueError, match="finite_gfp_for_all"):
        render_figures(data, tmp_path/"missing")


def test_legacy_gfp_axis_names_actual_transform(tmp_path):
    data = result(kind="scatter", mode="exploratory")
    data["spec"]["gfp_transform"] = "legacy-log2p1"
    render_figures(data, tmp_path)
    assert "max(GFP, 0) + 1" in (tmp_path/"figure.svg").read_text(encoding="utf-8")
