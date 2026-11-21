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
from cytellect_analysis.common_statistics import analyze_region_association, analyze_region_comparison
from cytellect_analysis.common_statistics_figures import FIGURE_VERSION, render_common_statistics
from cytellect_analysis.figure_annotations import comparison_annotations
from cytellect_analysis.figure_forms import DENSE_OBSERVATIONS, figure_forms
from cytellect_analysis.figure_layout import beeswarm
from cytellect_analysis.figure_style import FONT_FILES, p_stars, p_text
from test_common_statistics import association_request, request_v2
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


OPENING = {"version": "1.0.0", "annotation": "value", "size": "panel", "composition": "quantification", "outlines": True}


def test_publication_figure_from_a_saved_demo_comparison(tmp_path):
    result = demo_comparison()
    # As the 「グラフ」 view opens a saved comparison: the run hierarchy with the opening presentation.
    result["spec"]["plot"].update(kind="superplot", presentation=OPENING)
    manifest = render_common_statistics(result, tmp_path)
    assert manifest["common_statistics_figure_version"] == FIGURE_VERSION == "2.0.0"
    assert manifest["font"] == "Liberation Sans"
    # A two-group panel is drawn at its printed size (each group as wide as its longest word), not a column wide.
    assert 36 <= manifest["style"]["width_mm"] <= 70
    svg = (tmp_path / "figure.svg").read_text(encoding="utf-8")
    assert "Liberation Sans', Arial, Helvetica" in svg and "<text" in svg
    assert "Higher in 2 of 3 runs" in svg and "n = 3 runs" in svg
    assert "Nuclear NPM1 mean" in svg
    observations = [r for r in result["plot_data"] if r["selection_status"] == "selected"]
    assert svg.count("data-cytellect-source") == len(observations) + len(result["unit_summary"])
    legend = (tmp_path / "figure-legend.md").read_text(encoding="utf-8")
    assert "[Cell line]" in legend and "n = 3 runs per condition" in legend
    assert "No hypothesis test or confidence interval was calculated" in legend
    # The title states the result as the summary on the screen does (FL-03); the body reads as a paper's legend.
    assert legend.startswith("**Nuclear NPM1 mean intensity did not change consistently with Oxaliplatin 10 µM.**")
    assert "→" not in legend and "Excluded runs: 0" not in legend
    assert "the mean of its fields, each field summarised by the median of its nuclei" in legend
    source = json.loads((tmp_path / "figure-data.json").read_text(encoding="utf-8"))
    assert source["presentation"]["observations"] == "points"
    assert [form["id"] for form in manifest["forms"]][:3] == ["points", "density", "box"]


def test_a_request_naming_no_presentation_keeps_its_size(tmp_path):
    # An earlier client (the region workspace's figure settings) or a figure saved before the
    # publication figure: the width and height it asked for, not the panel.
    result = demo_comparison()
    result["spec"]["plot"].update(kind="superplot", preset="custom", width_inches=120 / 25.4, height_inches=70 / 25.4)
    manifest = render_common_statistics(result, tmp_path)
    assert manifest["style"]["width_mm"] == pytest.approx(120) and manifest["style"]["height_mm"] == pytest.approx(70)


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


def test_beeswarm_narrows_only_the_rows_that_do_not_fit():
    # A dense row at 0 and a few sparse values far above it (genellect/cytellect#257, owner decision 2026-11-21).
    values = np.concatenate([np.zeros(200), [5.0, 5.0, 5.0, 9.0]])
    natural = beeswarm(values, dx=.05, dy=.1, half_width=np.inf)
    placed = beeswarm(values, dx=.05, dy=.1, half_width=.3)
    assert np.max(np.abs(placed)) <= .3 + 1e-12
    # The dense row is narrowed into the group's width; the sparse values keep their natural spacing.
    assert np.isclose(np.max(np.abs(placed[:200])), .3)
    assert np.array_equal(placed[200:], natural[200:])
    assert len(set(np.round(placed[200:203], 9))) == 3


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


def test_value_axis_encloses_every_value_and_checks_the_chosen_range():
    from cytellect_analysis.publication_figure import _y_range

    values = [-2.52, -0.4, 0.15]
    bottom, top, ticks = _y_range(values, "log2", {})
    assert bottom <= min(values) and top >= max(values) and (bottom, top) == (ticks.min(), ticks.max())
    bottom, top, _ = _y_range([3.0, 7.0, 12.0], "difference", {"y_tick_step": 5})
    assert bottom <= 3 and top >= 12
    with pytest.raises(ValueError, match="figure_y_range_invalid"):
        _y_range([3.0, 12.0], "difference", {"y_min": 50})
    with pytest.raises(ValueError, match="figure_tick_count_exceeded"):
        _y_range([3.0, 30000.0], "difference", {"y_tick_step": 0.001})


def test_percent_ticks_keep_their_decimals():
    from cytellect_analysis.figure_style import value_formatter

    formatter, unit = value_formatter("fraction", [0, .025, .125])
    assert unit == "%"
    assert [formatter(value, 0) for value in (0, .025, .075, .125, 1)] == ["0", "2.5", "7.5", "12.5", "100"]


def test_association_applies_the_axis_controls(tmp_path):
    report, config = comparison_fixture((("A", [1, 2, 3]), ("B", [4, 5, 6])))
    plot = {"preset": "nature-double", "y_tick_step": 1e-9}
    result = analyze_region_association(report, config, association_request(plot=plot))
    with pytest.raises(ValueError, match="figure_tick_count_exceeded"):
        render_common_statistics(result, tmp_path)


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


def drawn(result, tmp_path, name, **plot):
    """Draw the saved demo comparison with one setting changed, as the 「グラフ」 view asks for it."""
    result = copy.deepcopy(result)
    presentation = {**OPENING, **plot.pop("presentation", {})}
    result["spec"]["plot"].update({"kind": "superplot", **plot, "presentation": presentation})
    out = tmp_path / name
    manifest = render_common_statistics(result, out)
    return manifest, (out / "figure.svg").read_text(encoding="utf-8"), (out / "figure-legend.md").read_text(encoding="utf-8")


def test_every_form_is_a_publication_figure_that_says_what_it_summarises(tmp_path):
    # Each form the view offers reads as its summary, and the legend names it (2026-11-19, owner: only the
    # default figure was a publication figure; the box hid under the points).
    result = demo_comparison()
    box, _, box_legend = drawn(result, tmp_path, "box", presentation={"observations": "box"})
    assert box["common_statistics_figure_version"] == "2.0.0"
    assert "boxes show the median and interquartile range" in box_legend
    _, _, density_legend = drawn(result, tmp_path, "density", presentation={"observations": "violin"})
    assert "grey outlines show the distribution" in density_legend
    _, _, bar_legend = drawn(result, tmp_path, "bar", kind="unit-mean-bar", presentation={"observations": "points"})
    assert "bars show the mean of runs" in bar_legend
    selected = [row["condition"] for row in result["plot_data"] if row["selection_status"] == "selected"]
    largest = max(selected.count(condition) for condition in set(selected))
    # A bar over more than 150 observations in a group leaves them out; the legend then does not mention them.
    assert ("small dots" in bar_legend.lower()) == (largest <= 150)


def test_a_column_width_is_used_by_the_groups_not_left_blank(tmp_path):
    import xml.etree.ElementTree as ET

    result = demo_comparison()
    manifest, svg, _ = drawn(result, tmp_path, "double", presentation={"size": "double-column"})
    assert manifest["style"]["width_mm"] == pytest.approx(183)
    root = ET.fromstring(svg)
    # The axes patch spans most of the width (it was a 40 mm panel centred in 183 mm).
    patch = next(element for element in root.iter() if element.get("id") == "patch_2")
    path = next(child for child in patch.iter() if child.tag.endswith("path"))
    xs = [float(value) for value in path.get("d").replace("M", " ").replace("L", " ").replace("z", " ").split()[::2]]
    width_pt = float(root.get("width").removesuffix("pt"))
    assert (max(xs) - min(xs)) / width_pt > .6


def test_group_names_take_the_same_rows_so_n_reads_across(tmp_path):
    import matplotlib.pyplot as plt
    from cytellect_analysis import publication_figure

    result = demo_comparison()
    captured = {}
    original = publication_figure.draw_comparison

    def record(fig, ax, *args, **kwargs):
        value = original(fig, ax, *args, **kwargs)
        captured["labels"] = [label.get_text() for label in ax.get_xticklabels()]
        return value

    publication_figure.draw_comparison = record
    try:
        drawn(result, tmp_path, "labels")
    finally:
        publication_figure.draw_comparison = original
        plt.close("all")
    lines = {label.count("\n") for label in captured["labels"]}
    assert len(lines) == 1 and all(label.split("\n")[-1].startswith("n = ") for label in captured["labels"])


@pytest.mark.parametrize("kind,observations", [("box", "box"), ("violin", "violin"), ("paired", "points"), ("histogram", "points")])
def test_a_form_saved_before_is_drawn_as_its_nearest_publication_form(tmp_path, kind, observations):
    # Three runs offer no run-value form; a figure saved with one is drawn as the run hierarchy.
    result = demo_comparison()
    result["spec"]["plot"].update(kind=kind, presentation=OPENING)
    manifest = render_common_statistics(result, tmp_path)
    assert manifest["common_statistics_figure_version"] == "2.0.0"
    assert manifest["presentation"]["observations"] == observations


# Independent review (2026-11-20): what each form draws, and that its legend draft says no more.
TWELVE_RUNS = (("A", [1, 3, 6, 2, 8, 5, 4, 7, 9, 3, 6, 5]), ("B", [2, 5, 10, 7, 9, 11, 6, 8, 12, 4, 10, 9]))


def captured_axes(monkeypatch):
    """The axes each comparison is drawn on, kept open for inspection."""
    from cytellect_analysis import publication_figure

    axes = []
    original = publication_figure.draw_comparison

    def record(fig, ax, *args, **kwargs):
        value = original(fig, ax, *args, **kwargs)
        axes.append(ax)
        return value

    monkeypatch.setattr(publication_figure, "draw_comparison", record)
    return axes


def test_a_long_group_name_keeps_the_width_the_layout_gave_it(tmp_path):
    # The panel widened for a long word but the axis was shrunk back to the short-name width,
    # so the names overlapped and the default figure was refused.
    report, config = comparison_fixture((("A", [1, 3, 6]), ("B", [2, 5, 10])))
    result = analyze_region_comparison(report, config, request_v2(test="welch-t"))
    result = json.loads(json.dumps(result).replace('"A"', '"Cycloheximide-treated"').replace('"B"', '"Actinomycin-treated"'))
    result["spec"]["plot"].update(kind="superplot", presentation=OPENING)
    manifest = render_common_statistics(result, tmp_path)
    assert manifest["style"]["width_mm"] > 70


def test_a_run_histogram_draws_the_saved_bins_that_hold_a_value(tmp_path, monkeypatch):
    from matplotlib.axes import Axes

    report, config = comparison_fixture(TWELVE_RUNS)
    result = analyze_region_comparison(report, config, request_v2(test="welch-t"))
    result["spec"]["plot"].update(kind="histogram", histogram_bins=6, presentation=OPENING)
    lengths = []
    original = Axes.barh

    def record(self, y, width, *args, **kwargs):
        lengths.extend(np.atleast_1d(width).tolist())
        return original(self, y, width, *args, **kwargs)

    monkeypatch.setattr(Axes, "barh", record)
    render_common_statistics(result, tmp_path)
    data = json.loads((tmp_path / "figure-data.json").read_text(encoding="utf-8"))
    bins = [row for row in data["graphical_summary"] if "bin_left" in row]
    assert {row["condition"] for row in bins} == {"A", "B"} and len(bins) == 12
    assert all(sum(row["count"] for row in bins if row["condition"] == group) == 12 for group in ("A", "B"))
    # An empty bin is no mark (it drew as a line that read as data).
    assert lengths and all(length > 0 for length in lengths)
    assert len(lengths) == sum(row["count"] > 0 for row in bins)
    assert "grey bars show a histogram of run values" in (tmp_path / "figure-legend.md").read_text(encoding="utf-8")


def test_a_summary_that_cannot_be_drawn_is_not_in_the_legend(tmp_path):
    report, config = comparison_fixture((("A", [5] * 12), ("B", [8] * 12)))
    result = analyze_region_comparison(report, config, request_v2(test="none"))
    result["spec"]["plot"].update(kind="violin", presentation=OPENING)
    render_common_statistics(result, tmp_path)
    legend = (tmp_path / "figure-legend.md").read_text(encoding="utf-8")
    data = json.loads((tmp_path / "figure-data.json").read_text(encoding="utf-8"))
    assert "grey outlines" not in legend
    assert not any(row.get("shape") for row in data["graphical_summary"])


def test_a_box_records_its_quartiles_and_a_run_line_stays_over_it(tmp_path, monkeypatch):
    from cytellect_analysis.publication_figure import natural_order

    report, config = comparison_fixture(TWELVE_RUNS)
    result = analyze_region_comparison(report, config, request_v2(paired=True, test="paired-t"))
    result["spec"]["plot"].update(kind="box", presentation=OPENING)
    axes = captured_axes(monkeypatch)
    render_common_statistics(result, tmp_path)
    data = json.loads((tmp_path / "figure-data.json").read_text(encoding="utf-8"))
    rows = [row for row in data["graphical_summary"] if row.get("shape") == "box"]
    assert len(rows) == 2 and all(row["q1"] <= row["median"] <= row["q3"] and row["of"] == "run values" for row in rows)
    box_face = max(patch.get_zorder() for patch in axes[0].patches)
    # A run's line joins its two groups; a whisker or a median stays within one.
    run_lines = [line for line in axes[0].lines if np.ptp(np.asarray(line.get_xdata(), dtype=float)) > .5]
    assert run_lines and min(line.get_zorder() for line in run_lines) > box_face
    # Runs read in order: p2 before p10.
    assert natural_order(["p10", "p2", "p1"]) == ["p1", "p2", "p10"]


def test_the_fields_behind_a_comparison_read_group_then_run_then_field(tmp_path):
    from statistics import median

    result = demo_comparison()
    result["spec"]["plot"] = {**result["spec"]["plot"], "kind": "superplot", "presentation": OPENING}
    manifest = render_common_statistics(copy.deepcopy(result), tmp_path)
    assert {"fields.svg", "fields.pdf", "fields.png"} <= set(manifest["source_files"])
    assert all((tmp_path / name).stat().st_size for name in ("fields.svg", "fields.pdf", "fields.png"))
    fields = manifest["field_check"]["fields"]
    order = result["spec"]["plot"]["group_order"] or result["spec"]["conditions"]
    groups = [field["condition"] for field in fields]
    # Group by group, run by run within it: the order the comparison summarises its values.
    assert groups == sorted(groups, key=order.index)
    for group in order:
        runs = [field["run"] for field in fields if field["condition"] == group]
        assert runs == sorted(runs, key=lambda run: [field["run"] for field in fields if field["condition"] == group].index(run))
        assert len(runs) == len({(r, i) for i, r in enumerate(runs)})
    # Every saved observation is drawn once, and each line is the median of its field's observations.
    rows = [row for row in result["plot_data"] if row.get("selection_status", "selected") == "selected" and row.get("value") is not None]
    assert sum(field["observations"] for field in fields) == len(rows)
    for field in fields:
        values = [row["value"] for row in rows if row["field_id"] == field["field_id"]]
        assert field["median"] == pytest.approx(median(values))
    # The runs take the colours of the comparison figure.
    svg = (tmp_path / "fields.svg").read_text(encoding="utf-8")
    assert "#0072b2" in svg.lower() and "Field median" in svg


def test_many_fields_leave_the_numbers_off_and_never_fail_the_comparison(tmp_path):
    # Forty independent units per group: field numbers cannot fit, and the field check must not cost the figure.
    report, config = comparison_fixture((("A", list(range(1, 41))), ("B", list(range(2, 42)))))
    result = analyze_region_comparison(report, config, request_v2(test="welch-t"))
    result = json.loads(json.dumps(result).replace('"A"', '"Untreated control cells"').replace('"B"', '"Treated with compound X"'))
    result["spec"]["plot"].update(kind="superplot", presentation=OPENING)
    manifest = render_common_statistics(result, tmp_path)
    assert (tmp_path / "figure.svg").is_file()
    check = manifest["field_check"]
    assert check.get("skipped") is None, check
    # An independent design has no runs to group by; every field still appears, without its number.
    assert check["runs_labelled"] is False and check["numbered"] is False
    assert len(check["fields"]) == 80 and {field["run"] for field in check["fields"]} == {None}
    assert set(check["files"]) <= set(manifest["source_files"])
