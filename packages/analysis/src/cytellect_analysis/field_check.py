"""The fields behind a group comparison, on one panel (presentation only).

Every saved observation of the comparison, field by field, in the order the comparison summarises them:
group → run → field. Each field shows its observations and their median; the runs take the colours of the
comparison figure. It is the check of which fields carry a result (genellect/cytellect#257, owner decisions
2026-11-21 15 and 19), drawn from the same saved result as the comparison figure. Nothing is computed
here but the median a field already reports and the positions of the marks.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from .figure_layout import beeswarm
from .figure_sources import attach_svg_sources, bind_points
from .figure_style import INK, MM, MUTED, PNG_DPI, fit_axis_title, rc, run_colors, value_formatter, wrap_label
from .figures import _validate_text_layout, plt

FILES = ("fields.svg", "fields.pdf", "fields.png")
# A field number takes about this much width; with more fields than fit, numbers are left off (the marks stay bound
# to their fields), and the run row is left off when its labels would not fit either.
LABEL_MM = 4.2
# Millimetres between neighbouring fields, between runs and between groups (the hierarchy reads as gaps).
FIELD_STEP, RUN_GAP, GROUP_GAP = 1.0, .5, 1.2
HEIGHT_MM = 62.0


def columns(canonical: dict[str, Any], order: list[str]) -> list[dict[str, Any]]:
    """One column per field that has an observation in the comparison, in group → run → field order.

    Fields are numbered as the result lists them (the numbers of the descriptive field pages)."""
    from .publication_figure import _observations, natural_order

    rows = _observations(canonical, order)
    paired = canonical["spec"]["design"]["kind"] == "paired"
    numbers = {field["field_id"]: index + 1 for index, field in enumerate(canonical.get("source_fields") or [])}
    result = []
    for group in order:
        in_group = [row for row in rows if row["condition"] == group]
        # Runs are the pairs of a paired design; an independent design has no run to group by.
        run_of = (lambda row: row.get("pair") or row["experimental_unit"]) if paired else (lambda row: None)
        for run in natural_order({run_of(row) for row in in_group}) if paired else [None]:
            in_run = [row for row in in_group if run_of(row) == run]
            for field in sorted({row["field_id"] for row in in_run}, key=lambda fid: (numbers.get(fid, 10 ** 6), fid)):
                result.append({"group": group, "run": run, "field_id": field, "number": numbers.get(field),
                               "rows": [row for row in in_run if row["field_id"] == field]})
    return result


def render_field_check(canonical: dict[str, Any], order: list[str], output: Path, *, font_size: float = 7.0,
                       series_colors: dict[str, str] | None = None) -> dict[str, Any] | None:
    """Write ``fields.svg``/``.pdf``/``.png``; None when the comparison has no field to show."""
    from .common_statistics_figures import _write_svg_font_stack
    from .publication_figure import _full_title, _scale, axis_title, bind_fonts, natural_order

    placed = columns(canonical, order)
    if not placed:
        return None
    paired = canonical["spec"]["design"]["kind"] == "paired"
    runs = natural_order({column["run"] for column in placed}) if paired else []
    colours = run_colors(runs, series_colors) if paired else {}
    x, positions, previous = 0.0, [], None
    for column in placed:
        if previous is not None and previous["group"] != column["group"]:
            x += GROUP_GAP
        elif previous is not None and previous["run"] != column["run"]:
            x += RUN_GAP
        positions.append(x)
        previous = column
        x += FIELD_STEP
    width_mm = float(np.clip(28 + 7.2 * (positions[-1] + 1), 89.0, 183.0))
    values = np.array([row["value"] for column in placed for row in column["rows"]], dtype=float)
    scale = _scale(canonical)
    with plt.rc_context(rc(font_size)):
        fig, ax = plt.subplots(figsize=(width_mm * MM, HEIGHT_MM * MM), layout="constrained")
        try:
            low, high = float(min(0.0, values.min())), float(values.max())
            span = high - low or 1.0
            ax.set_xlim(-.6, positions[-1] + .6)
            ax.set_ylim(low, high + .04 * span)
            formatter, multiplier = value_formatter(scale, ax.get_yticks())
            ax.yaxis.set_major_formatter(formatter)
            title, unit = axis_title(canonical)
            unit_note = "%" if scale == "fraction" else unit
            if multiplier:
                unit_note = f"{multiplier} {unit}".strip()
            # The title runs along the value axis, wrapped to its length as on the comparison figure.
            ax.set_ylabel(fit_axis_title(_full_title(title, unit_note, ""), max(24.0, HEIGHT_MM - 16), font_size))
            fig.canvas.draw()
            # Field numbers on the axis, runs (in their colours) and groups below them, as far as they fit.
            axis_mm = ax.get_window_extent().width / fig.dpi * 25.4
            per_unit = axis_mm / (positions[-1] + 1.2)
            numbered = per_unit * FIELD_STEP >= LABEL_MM
            ax.set_xticks(positions, [str(column["number"] or "") if numbered else "" for column in placed])
            ax.tick_params(axis="x", length=0, pad=1.5)
            ax.spines["bottom"].set_color(INK)
            centre = lambda keep: float(np.mean([p for p, c in zip(positions, placed, strict=True) if keep(c)]))  # noqa: E731
            run_keys = list(dict.fromkeys((c["group"], c["run"]) for c in placed)) if paired else []
            if run_keys and min(sum(1 for c in placed if (c["group"], c["run"]) == key) for key in run_keys) * per_unit < LABEL_MM * 2:
                run_keys = []
            run_axis = ax.secondary_xaxis("bottom")
            run_axis.set_xticks([centre(lambda c, k=key: (c["group"], c["run"]) == k) for key in run_keys],
                                [str(run) for _, run in run_keys])
            run_axis.spines["bottom"].set_position(("outward", font_size * 1.6 if numbered else 0))
            run_axis.spines["bottom"].set_visible(False)
            run_axis.tick_params(length=0, pad=1.5)
            for label, (_, run) in zip(run_axis.get_xticklabels(), run_keys, strict=True):
                label.set_color(colours.get(run, INK) if paired else INK)
            group_axis = ax.secondary_xaxis("bottom")
            shown = [group for group in order if any(c["group"] == group for c in placed)]
            # Each group's name fits under its own fields: the width they take on the axis.
            extent = per_unit
            spans = {group: (max(p for p, c in zip(positions, placed, strict=True) if c["group"] == group)
                             - min(p for p, c in zip(positions, placed, strict=True) if c["group"] == group) + 1) * extent
                     for group in shown}
            group_axis.set_xticks([centre(lambda c, g=group: c["group"] == g) for group in shown],
                                  [wrap_label(group, max(9.0, spans[group]), font_size) for group in shown])
            group_axis.spines["bottom"].set_position(("outward", font_size * (1.6 * bool(numbered) + 1.7 * bool(run_keys))))
            group_axis.spines["bottom"].set_visible(False)
            group_axis.tick_params(length=0, pad=1.5)
            if numbered:
                ax.annotate("Field", xy=(0, 0), xycoords="axes fraction", xytext=(-3, -1.5), textcoords="offset points",
                            ha="right", va="top", color=MUTED, fontsize=max(5.0, font_size - .5))
            ax.legend(handles=[plt.Line2D([], [], color=INK, linewidth=.9)], labels=["Field median"], loc="upper left",
                      frameon=False)
            # Names the bundled face cannot write (Japanese group or run names) take the fallback face, as on the
            # comparison figure. Tick labels take their text when drawn, so the figure is drawn first.
            fig.canvas.draw()
            bind_fonts(fig)
            fig.canvas.draw()

            def collide(axis) -> bool:
                boxes = [label.get_window_extent() for label in axis.get_xticklabels() if label.get_text()]
                return any(left.overlaps(right) for index, left in enumerate(boxes) for right in boxes[index + 1:])

            if run_keys and collide(run_axis):
                # Run names that run into each other are left off; the fields stay grouped by run.
                run_keys = []
                run_axis.set_xticks([], [])
                group_axis.spines["bottom"].set_position(("outward", font_size * 1.6 * bool(numbered)))
                fig.canvas.draw()
            if collide(group_axis):
                raise ValueError("figure_labels_overlap")
            # The marks are placed on the final layout: the labels below shorten the value axis, and one marker
            # diameter in data units is read from the axis as it is written.
            inverse = ax.transData.inverted()
            point_d = np.sqrt(3.2) * 1.05 * fig.dpi / 72
            dx = abs(inverse.transform((point_d, 0))[0] - inverse.transform((0, 0))[0])
            dy = abs(inverse.transform((0, point_d))[1] - inverse.transform((0, 0))[1])
            drawn = []
            for position, column in zip(positions, placed, strict=True):
                field_values = np.array([row["value"] for row in column["rows"]], dtype=float)
                offsets = beeswarm(field_values, dx=dx, dy=dy, half_width=.36)
                colour = colours.get(column["run"], MUTED) if paired else MUTED
                collection = ax.scatter(position + offsets, field_values, s=3.2, color=colour, alpha=.6, linewidths=0,
                                        zorder=2)
                bind_points(collection, column["rows"], keys=("field_id", "region_id", "nucleus_id"), focusable=False)
                median = float(np.median(field_values))
                ax.hlines(median, position - .32, position + .32, color=INK, linewidth=.9, zorder=3)
                drawn.append({"field_id": column["field_id"], "number": column["number"], "condition": column["group"],
                              "run": column["run"], "observations": len(field_values), "median": median})
            _validate_text_layout(fig, ax)
            for suffix in ("svg", "pdf", "png"):
                metadata: dict[str, str | None] = {"Creator": "Cytellect field check 1.0.0"}
                if suffix == "svg":
                    metadata["Date"] = None
                if suffix == "pdf":
                    metadata.update(CreationDate=None, ModDate=None)
                fig.savefig(output / f"fields.{suffix}", dpi=PNG_DPI, metadata=metadata)
                if suffix == "svg":
                    attach_svg_sources(output / "fields.svg", fig)
                    _write_svg_font_stack(output / "fields.svg")
        finally:
            plt.close(fig)
    return {"version": "1.0.0", "width_mm": width_mm, "height_mm": HEIGHT_MM, "order": "group, run, field",
            "numbered": bool(numbered), "runs_labelled": bool(run_keys), "fields": drawn, "files": list(FILES)}
