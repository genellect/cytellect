"""Physical export and source integrity gates, distinct from biological validity."""
import csv
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from types import SimpleNamespace

import pytest
from cytellect_analysis import figures
from cytellect_analysis.contracts import PlotSpec, StatisticsRequest
from cytellect_analysis.figures import figure_settings, render_figures, select_font
from cytellect_analysis.statistics import analyze
from matplotlib import font_manager
from matplotlib.figure import Figure
from matplotlib.text import Text
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


def font_fixture(monkeypatch, definitions):
    entries, loaded = [], {}
    for family, cached_weight, actual_weight, text in definitions:
        entry = SimpleNamespace(name=family, weight=cached_weight, style="normal", stretch="normal",
                                fname=f"{family}-{cached_weight}.ttf")
        entries.append(entry)
        characters = {ord(c): 1 for c in text + "0123456789.eE+-"}
        loaded[entry.fname] = SimpleNamespace(
            actual=SimpleNamespace(name=family, weight=actual_weight, style="normal"),
            get_charmap=lambda characters=characters: characters,
        )
    monkeypatch.setattr(font_manager.fontManager, "ttflist", entries)
    monkeypatch.setattr(font_manager, "get_font", lambda path: loaded[str(path)])
    monkeypatch.setattr(font_manager, "ttfFontProperty", lambda font: font.actual)


def test_thin_only_japanese_family_uses_actual_regular_alternative(monkeypatch):
    font_fixture(monkeypatch, [("Noto Sans JP", 100, 100, "測定値"),
                              ("Yu Gothic", 400, 400, "測定値")])
    selected = select_font("ja", "測定値")
    assert selected.family == "Yu Gothic" and selected.weight == 400
    assert selected.path.name == "Yu Gothic-400.ttf"


@pytest.mark.parametrize("actual_weight", [100, 300, 600, 700])
def test_stale_cache_does_not_hide_thin_light_or_bold_file(monkeypatch, actual_weight):
    font_fixture(monkeypatch, [("Noto Sans JP", 400, actual_weight, "測定値")])
    with pytest.raises(ValueError, match="japanese_font_not_installed"):
        select_font("ja", "測定値")


def test_glyph_coverage_uses_complete_regular_face_or_fails(monkeypatch):
    font_fixture(monkeypatch, [("Noto Sans JP", 400, 400, "ABC"),
                              ("Meiryo", 400, 400, "ABC測定値")])
    assert select_font("ja", "ABC測定値").family == "Meiryo"
    with pytest.raises(ValueError, match="figure_font_glyphs_unavailable"):
        select_font("ja", "\U0010ffff")


@pytest.mark.parametrize("language", ["en", "ja"])
@pytest.mark.parametrize("kind", ["distribution", "scatter"])
@pytest.mark.filterwarnings("error:Glyph .* missing from font")
def test_actual_font_file_weight_glyphs_and_private_metadata(tmp_path, monkeypatch, language, kind):
    data = result(kind=kind, mode="exploratory" if kind == "scatter" else "experimental-unit")
    data["spec"]["plot"]["language"] = language
    try:
        selected = select_font(language, "測定値" if language == "ja" else "Measured value")
    except ValueError as exc:
        if language == "ja" and str(exc) == "japanese_font_not_installed":
            pytest.skip("No installed regular Japanese font; no runtime font download")
        raise
    original_save = Figure.savefig
    recorded_paths = []
    selected_faces = []

    def inspect_bound_fonts(figure, *args, **kwargs):
        texts = figure.findobj(match=Text)
        selected = select_font(language, "".join(text.get_text() for text in texts))
        selected_faces.append(selected)
        for text in texts:
            if text.get_text():
                path = text.get_fontproperties().get_file()
                assert path is not None
                actual = font_manager.ttfFontProperty(font_manager.get_font(path))
                assert actual.style == "normal" and 350 <= actual.weight <= 500
                assert path == str(selected.path)
                recorded_paths.append(path)
        return original_save(figure, *args, **kwargs)

    monkeypatch.setattr(Figure, "savefig", inspect_bound_fonts)
    meta = render_figures(data, tmp_path)
    selected = selected_faces[0]
    assert all(face == selected for face in selected_faces)
    assert recorded_paths and meta["figure_version"] == "1.1.2"
    assert meta["font_metadata"] == selected.metadata()
    encoded = (tmp_path / "figure-data.json").read_text(encoding="utf-8")
    source = json.loads(encoded)
    assert source["font_metadata"] == meta["font_metadata"]
    assert str(selected.path) not in encoded and "path" not in source["font_metadata"]
    assert source["means"] == data["means"] and source["counts"] == data["counts"]
    pdf = (tmp_path / "figure.pdf").read_bytes()
    assert b"/FontFile2" in pdf and b"/CIDFontType2" in pdf and b"/ToUnicode" in pdf
    assert ET.parse(tmp_path / "figure.svg").findall(".//{http://www.w3.org/2000/svg}text")


def test_missing_glyph_fails_before_any_figure_is_published(tmp_path):
    data = result()
    data["spec"]["plot"]["y_label"] = "Undefined glyph \U0010ffff"
    with pytest.raises(ValueError, match="figure_font_glyphs_unavailable"):
        figures.render_figures(data, tmp_path)
    assert not list(tmp_path.glob("figure.*"))


@pytest.mark.parametrize("label_case", ["native-ratio", "legacy-ratio", "positive-log2", "legacy-log2p1"])
@pytest.mark.filterwarnings("error:Glyph .* missing from font")
def test_japanese_builtin_log_labels_use_portable_base_two_notation(tmp_path, label_case):
    # Noto Sans CJK regular lacks U+2082. Built-in labels use literal log2;
    # user labels still require exact font coverage and are never rewritten.
    data = result(kind="scatter" if "log2" in label_case else "distribution",
                  mode="exploratory" if "log2" in label_case else "experimental-unit")
    data["spec"]["plot"].update(language="ja", preset="nature-double")
    if label_case in {"native-ratio", "legacy-ratio"}:
        metric = "ncl_log2_nucleoplasm_over_nucleoli" if label_case == "native-ratio" else "ncl_legacy_release"
        old = data["spec"]["metric"]
        data["spec"]["metric"] = metric
        for name in ("plot_data", "field_summary", "unit_summary"):
            for row in data[name]:
                row[metric] = row.pop(old)
    else:
        data["spec"]["gfp_transform"] = label_case
    try:
        select_font("ja", "測定値")
    except ValueError as exc:
        if str(exc) == "japanese_font_not_installed":
            pytest.skip("No installed regular Japanese font; no runtime font download")
        raise
    render_figures(data, tmp_path)
    text = (tmp_path / "figure.svg").read_text(encoding="utf-8")
    assert "log2" in text and "log₂" not in text
    assert (tmp_path / "figure.pdf").is_file()


def crowded_result():
    names = [f"Condition {index:02d} measurement" for index in range(8)]
    rows = [{"condition": name, "experimental_unit": f"u{group}-{unit}",
             "sample": f"s{group}-{unit}", "field_id": f"f{group}-{unit}",
             "acquisition_date": "date", "value": group + unit * .3 + cell * .2}
            for group, name in enumerate(names) for unit in range(3) for cell in range(3)]
    return analyze(rows, StatisticsRequest(metric="value", baseline=names[0],
        comparisons=[(names[0], names[1])], independent_units_confirmed=True))


def test_crowded_tick_labels_fail_before_any_output_and_allow_wider_size(tmp_path):
    data = crowded_result()
    with pytest.raises(ValueError, match="figure_labels_overlap"):
        render_figures(data, tmp_path / "crowded")
    assert not list((tmp_path / "crowded").iterdir())
    data["spec"]["plot"].update(preset="nature-double")
    render_figures(data, tmp_path / "wider")
    assert (tmp_path / "wider" / "figure.pdf").exists()


def test_long_unwrapped_axis_label_is_not_silently_clipped(tmp_path):
    data = result()
    data["spec"]["plot"]["x_label"] = "A" * 120
    with pytest.raises(ValueError, match="figure_text_outside_canvas"):
        render_figures(data, tmp_path)
    assert not list(tmp_path.iterdir())
