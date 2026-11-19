"""Publication figures (common-statistics figure 2.0.0, docs/drafts/publication-figures/plan.md).

The rendering checks use a comparison saved by the public demo (Zenodo 6643470, CC BY 4.0,
`apps/web/public/showcase/snapshot`). The rule checks (forms, annotations, point layout) use
the existing small numeric fixture of the comparison tests; those values are synthetic and
only exercise the rules, never a biological claim.
"""
import copy
import json
from pathlib import Path

import numpy as np
import pytest
from cytellect_analysis.common_statistics import analyze_region_comparison
from cytellect_analysis.common_statistics_figures import FIGURE_VERSION, render_common_statistics
from cytellect_analysis.figure_annotations import comparison_annotations
from cytellect_analysis.figure_forms import DENSE_OBSERVATIONS, figure_forms
from cytellect_analysis.figure_layout import beeswarm
from cytellect_analysis.figure_style import FONT_FILES, p_stars, p_text
from test_common_statistics import request_v2
from test_region_comparison import comparison_fixture

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "apps/web/public/showcase/snapshot"


def demo_comparison():
    """The demo's saved NPM1 nuclear mean comparison (all nuclei, 3 runs, descriptive)."""
    journal = json.loads((SNAPSHOT / "journal.json").read_text(encoding="utf-8"))["entries"]
    for entry in journal:
        if entry["method"] != "GET" or not entry["path"].endswith("/common-statistics"):
            continue
        result = json.loads((SNAPSHOT / entry["file"]).read_text(encoding="utf-8"))
        if (result.get("metric") == "mean" and (result.get("channel") or {}).get("channel_id") == "npm1"
                and result["region"]["region_set_id"] == "nuclei" and result.get("estimates")
                and not (result.get("selection") or {}).get("channel_gate")):
            result.pop("figure", None)
            result.pop("source_job_id", None)
            return result
    pytest.skip("demo comparison not recorded")


def test_bundled_font_is_present():
    assert all(path.is_file() for path in FONT_FILES.values())


def test_publication_figure_from_a_saved_demo_comparison(tmp_path):
    result = demo_comparison()
    result["spec"]["plot"]["kind"] = "superplot"
    manifest = render_common_statistics(result, tmp_path)
    assert manifest["common_statistics_figure_version"] == FIGURE_VERSION == "2.0.0"
    assert manifest["font"] == "Liberation Sans"
    # A two-group panel is drawn at its printed size, not two columns wide.
    assert 36 <= manifest["style"]["width_mm"] <= 60
    svg = (tmp_path / "figure.svg").read_text(encoding="utf-8")
    assert "Liberation Sans', Arial, Helvetica" in svg and "<text" in svg
    assert "Higher in 2 of 3 runs" in svg and "n = 3 runs" in svg
    assert "Nuclear NPM1 mean" in svg
    observations = [r for r in result["plot_data"] if r["selection_status"] == "selected"]
    assert svg.count("data-cytellect-source") == len(observations) + len(result["unit_summary"])
    legend = (tmp_path / "figure-legend.md").read_text(encoding="utf-8")
    assert "[Cell line]" in legend and "n = 3 runs per condition" in legend
    assert "no hypothesis test" in legend
    source = json.loads((tmp_path / "figure-data.json").read_text(encoding="utf-8"))
    assert source["presentation"]["observations"] == "points"
    assert [form["id"] for form in manifest["forms"]][:3] == ["points", "density", "box"]


def test_same_result_gives_the_same_figure(tmp_path):
    result = demo_comparison()
    result["spec"]["plot"]["kind"] = "superplot"
    first = render_common_statistics(copy.deepcopy(result), tmp_path / "a")
    second = render_common_statistics(copy.deepcopy(result), tmp_path / "b")
    assert first == second
    assert (tmp_path / "a/figure.svg").read_bytes() == (tmp_path / "b/figure.svg").read_bytes()


@pytest.mark.parametrize("presentation", [
    {"observations": "violin"}, {"observations": "box"}, {"annotation": "stars"}, {"annotation": "none"},
    {"size": "single-column"}, {"size": "double-column"}, {"color_by": "group"}])
def test_presentation_choices_render(tmp_path, presentation):
    result = demo_comparison()
    result["spec"]["plot"].update(kind="superplot", presentation={"version": "1.0.0", **presentation})
    manifest = render_common_statistics(result, tmp_path)
    for key, value in presentation.items():
        assert manifest["presentation"][key] == value


def test_historical_versions_still_replay(tmp_path):
    result = demo_comparison()
    for version in ("1.0.0", "1.0.1"):
        manifest = render_common_statistics(copy.deepcopy(result), tmp_path / version, figure_version=version)
        assert manifest["common_statistics_figure_version"] == version
        assert "figure-legend.md" not in manifest["source_files"]


def test_beeswarm_is_deterministic_and_bounded():
    values = np.array([1.0, 1.0, 1.0, 1.02, 2.0, 2.0, 3.0])
    first = beeswarm(values, dx=.05, dy=.1, half_width=.3)
    assert np.array_equal(first, beeswarm(values, dx=.05, dy=.1, half_width=.3))
    assert np.max(np.abs(first)) <= .3 + 1e-12
    crowded = beeswarm(np.ones(200), dx=.05, dy=.1, half_width=.3)
    assert np.isclose(np.max(np.abs(crowded)), .3)


def test_forms_follow_the_experiment():
    report, config = comparison_fixture((("A", [1, 3, 6]), ("B", [2, 5, 10])))
    result = analyze_region_comparison(report, config, request_v2(test="welch-t"))
    forms = figure_forms(result)
    ids = [form["id"] for form in forms["forms"]]
    assert ids[0] == "points" and forms["default"]["kind"] == "superplot"
    # Three runs and few observations: no run-value box, violin or histogram and no density.
    assert not {"density", "run-box", "run-violin", "run-histogram"} & set(ids)
    assert DENSE_OBSERVATIONS == 30


def test_annotations_use_the_saved_values():
    report, config = comparison_fixture((("A", [1, 3, 6]), ("B", [2, 5, 10])))
    result = analyze_region_comparison(report, config, request_v2(
        test="welch-t", estimates="comparison-estimates/1.0.0",
        comparison_family={"family_id": "f", "kind": "planned", "contrasts": [["B", "A"]]}))
    notes = comparison_annotations(result, ["A", "B"])
    (bracket,) = notes.brackets
    p = result["comparisons"][0]["p_value"]
    assert bracket.lines[-1] == p_text(p)
    assert bracket.lines[0].startswith("Δ = ")
    assert comparison_annotations(result, ["A", "B"], "stars").brackets[0].lines == [p_stars(p)]


def test_descriptive_annotation_counts_runs():
    result = demo_comparison()
    notes = comparison_annotations(result, result["spec"]["conditions"])
    assert notes.brackets[0].lines == ["Higher in 2 of 3 runs"]
    runs = copy.deepcopy(result)
    for run in runs["estimates"]["runs"]:
        run["ratio"] = 0.5
        run["difference"] = -1.0
    assert comparison_annotations(runs, runs["spec"]["conditions"]).brackets[0].lines == ["−50 to −50% (3/3 runs)"]


def test_p_value_text():
    assert p_text(0.0004) == "P < 0.001"
    assert p_text(0.0123) == "P = 0.012"
    assert p_text(0.213) == "P = 0.21"
    assert p_stars(0.2) == "n.s." and p_stars(0.004) == "**"


def demo_images(result):
    """The original channels and saved labels of the representative fields, from the public seed."""
    import hashlib
    import io
    import zipfile

    import tifffile
    from cytellect_analysis.figure_images import representative_fields

    seed = zipfile.ZipFile(ROOT / "apps/web/public/showcase/seed.zip")
    names = seed.namelist()
    loaded = {}
    order = result["spec"]["conditions"]
    sources = {s["field_id"]: s for s in result["source_fields"]}
    for field_id, _ in representative_fields(result, order).values():
        source = sources[field_id]
        wanted = {source["image_info"]["inputs"][f"ch{i}"]["sha256"]: c["channel_id"]
                  for i, c in enumerate(source["image_info"]["channels"])}
        channels = {}
        for name in names:
            if name.endswith(".tif"):
                data = seed.read(name)
                digest = hashlib.sha256(data).hexdigest()
                if digest in wanted:
                    channels[wanted[digest]] = tifffile.imread(io.BytesIO(data))
        labels = [np.load(io.BytesIO(seed.read(n))) for n in names if field_id in n and n.endswith("labels.npy")]
        labels = [array for array in labels if array.shape == next(iter(channels.values())).shape] if channels else []
        if len(channels) == len(wanted) and labels:
            loaded[field_id] = {"channels": channels, "labels": labels[0]}
    return loaded


def test_representative_images_share_one_display_range(tmp_path):
    result = demo_comparison()
    images = demo_images(result)
    if len(images) < 2:
        pytest.skip("seed images not found by field")
    result["spec"]["plot"].update(kind="superplot", presentation={"version": "1.0.0", "composition": "images-quantification"})
    manifest = render_common_statistics(result, tmp_path, images=images)
    record = manifest["images"]
    assert record["measured_channel"] == "npm1" and record["counterstain_channel"] == "hoechst"
    assert {item["condition"] for item in record["fields"]} == set(result["spec"]["conditions"])
    assert record["scale_bar_um"] and len(record["display_range"]) == 2
    svg = (tmp_path / "figure.svg").read_text(encoding="utf-8")
    assert "<image" in svg and "data:image/png;base64," in svg
    assert "figure-images.npz" in manifest["source_files"]
    legend = (tmp_path / "figure-legend.md").read_text(encoding="utf-8")
    assert "same linear display range" in legend and "Scale bar" in legend
    # The pixels shown are the original values (the crop of the field), unchanged.
    saved = np.load(tmp_path / "figure-images.npz")
    first = record["fields"][0]
    y0, y1, x0, x1 = first["crop_yx"]
    assert np.array_equal(saved["0-npm1"], images[first["field_id"]]["channels"]["npm1"][y0:y1, x0:x1])
