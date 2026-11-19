"""Representative image panels for publication figures (presentation only).

The pixels are the original channel values of the saved fields, cropped and shown with one
linear display range per stain shared by every condition. Nothing here changes a pixel or a
measurement; the display range, the field and the crop are recorded with the figure.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np

OUTLINE = "#FFD400"
GREEN = np.array([0.10, 0.85, 0.25])
MAGENTA = np.array([0.90, 0.10, 0.85])
DISPLAY_PERCENTILES = (0.5, 99.5)
SCALE_BARS_UM = (1, 2, 5, 10, 20, 25, 50, 100, 200, 500)


@dataclass
class ImagePanel:
    group: str
    field_id: str
    crop: tuple[int, int, int, int]  # y0, y1, x0, x1 in original pixels
    channels: dict[str, np.ndarray]
    labels: np.ndarray
    regions: list[int]
    pixel_um: float | None
    selection: str  # "rule" or "researcher"


@dataclass
class ImageFigure:
    panels: list[ImagePanel]
    measured: str | None
    counterstain: str | None
    names: dict[str, str]
    display: dict[str, tuple[float, float]] = field(default_factory=dict)
    scale_bar_um: float | None = None

    def record(self) -> dict[str, Any]:
        return {"measured_channel": self.measured, "counterstain_channel": self.counterstain,
                "display_range": {key: list(value) for key, value in self.display.items()},
                "display_rule": "linear; 0.5–99.5th percentile of the shown pixels of all conditions, per stain",
                "scale_bar_um": self.scale_bar_um,
                "fields": [{"condition": p.group, "field_id": p.field_id, "crop_yx": list(p.crop),
                            "selection": p.selection, "outlined_regions": len(p.regions)} for p in self.panels]}


def _field_values(canonical) -> dict[str, float]:
    return {row["field_id"]: float(row["value"]) for row in canonical.get("field_summary") or []
            if row.get("value") is not None}


def representative_fields(canonical, order, chosen: dict[str, str] | None = None) -> dict[str, tuple[str, str]]:
    """Each condition's field: the researcher's choice, else the field whose saved value is closest
    to the condition's mean of runs (ties: the field listed first)."""
    chosen = chosen or {}
    values = _field_values(canonical)
    sources = canonical.get("source_fields") or []
    units = canonical.get("unit_summary") or []
    result: dict[str, tuple[str, str]] = {}
    for group in order:
        candidates = [s["field_id"] for s in sources if (s.get("metadata") or {}).get("condition") == group]
        if chosen.get(group) in candidates:
            result[group] = (chosen[group], "researcher")
            continue
        runs = [u["value"] for u in units if u["condition"] == group]
        target = float(np.mean(runs)) if runs else 0.0
        ranked = [(abs(values[fid] - target), index, fid) for index, fid in enumerate(candidates) if fid in values]
        if ranked:
            result[group] = (min(ranked)[2], "rule")
    return result


def image_channels(canonical) -> tuple[str | None, str | None, dict[str, str]]:
    """The measured stain and the stain that defines the regions (shown in the merge)."""
    sources = canonical.get("source_fields") or []
    names: dict[str, str] = {}
    for source in sources[:1]:
        for channel in (source.get("image_info") or {}).get("channels") or []:
            names[channel["channel_id"]] = channel.get("stain") or channel.get("label") or channel["channel_id"]
    measured = (canonical.get("channel") or {}).get("channel_id")
    gate = ((canonical.get("selection") or {}).get("channel_gate") or {}).get("channel") or {}
    measured = measured or gate.get("channel_id")
    region = canonical.get("region") or (sources[0].get("region_set") if sources else {}) or {}
    counterstain = region.get("defining_channel_id")
    if measured == counterstain:
        counterstain = None
    if measured is None:
        measured, counterstain = counterstain, None
    return measured, counterstain, names


def _regions_of(canonical, field_id) -> list[tuple[int, float]]:
    return [(int(row["region_id"]), float(row["value"])) for row in canonical.get("plot_data") or []
            if row.get("field_id") == field_id and row.get("region_id") is not None
            and row.get("selection_status", "selected") == "selected" and row.get("value") is not None]


def _centroid(labels: np.ndarray, region: int) -> tuple[int, int] | None:
    ys, xs = np.nonzero(labels == region)
    return (int(round(ys.mean())), int(round(xs.mean()))) if len(ys) else None


def _crop_box(labels: np.ndarray, centre_region: int | None, side: int) -> tuple[int, int, int, int]:
    height, width = labels.shape
    side = min(side, height, width)
    centre = _centroid(labels, centre_region) if centre_region is not None else None
    cy, cx = centre if centre else (height // 2, width // 2)
    y0 = int(np.clip(cy - side // 2, 0, height - side))
    x0 = int(np.clip(cx - side // 2, 0, width - side))
    return y0, y0 + side, x0, x0 + side


def build_panels(canonical, order, loaded: dict[str, dict[str, Any]], chosen=None) -> ImageFigure | None:
    """Crop the representative fields (same physical size in every condition) and fix the shared range.

    ``loaded[field_id]`` holds ``channels`` (original arrays by channel id) and ``labels`` (the saved
    label image of the result's analysis revision).
    """
    measured, counterstain, names = image_channels(canonical)
    picks = representative_fields(canonical, order, chosen)
    sources = {s["field_id"]: s for s in canonical.get("source_fields") or []}
    if measured is None or not picks or any(fid not in loaded for fid, _ in picks.values()):
        return None
    group_means = {g: float(np.mean([u["value"] for u in canonical["unit_summary"] if u["condition"] == g]))
                   for g in order if any(u["condition"] == g for u in canonical["unit_summary"])}
    # A third of the field (or four region diameters, if larger), the same in micrometres everywhere.
    first = loaded[next(iter(picks.values()))[0]]
    height, width = first["labels"].shape
    areas = [int(np.sum(first["labels"] == region)) for region, _ in _regions_of(canonical, next(iter(picks.values()))[0])[:50]]
    diameter = 2 * math.sqrt(float(np.median(areas)) / math.pi) if areas else 0
    side_px = int(min(height, width, max(min(height, width) / 3, 4 * diameter)))
    first_um = ((sources.get(next(iter(picks.values()))[0]) or {}).get("calibration") or {}).get("pixel_size_x_um")
    panels = []
    for group in order:
        if group not in picks:
            continue
        fid, how = picks[group]
        data = loaded[fid]
        pixel_um = ((sources.get(fid) or {}).get("calibration") or {}).get("pixel_size_x_um")
        side = side_px if not (first_um and pixel_um) else int(round(side_px * first_um / pixel_um))
        regions = _regions_of(canonical, fid)
        target = group_means.get(group, 0.0)
        labels = np.asarray(data["labels"])
        # The crop centres on the region closest to the condition's mean of runs, preferring one the
        # crop can show whole (away from the field's edge).
        inner = [item for item in regions if (c := _centroid(labels, item[0])) is not None
                 and side // 2 <= c[0] <= labels.shape[0] - side // 2 and side // 2 <= c[1] <= labels.shape[1] - side // 2]
        pool = inner or regions
        centre = min(pool, key=lambda item: (abs(item[1] - target), item[0]))[0] if pool else None
        box = _crop_box(labels, centre, side)
        y0, y1, x0, x1 = box
        channels = {cid: np.asarray(array)[y0:y1, x0:x1] for cid, array in data["channels"].items()
                    if cid in (measured, counterstain)}
        panels.append(ImagePanel(group, fid, box, channels, np.asarray(data["labels"])[y0:y1, x0:x1],
                                 [region for region, _ in regions], pixel_um, how))
    figure = ImageFigure(panels, measured, counterstain, names)
    for cid in (measured, counterstain):
        if cid is None:
            continue
        shown = np.concatenate([p.channels[cid].ravel().astype(float) for p in panels if cid in p.channels])
        low, high = (float(v) for v in np.percentile(shown, DISPLAY_PERCENTILES))
        figure.display[cid] = (low, high if high > low else low + 1)
    pixel_sizes = {p.pixel_um for p in panels}
    if None not in pixel_sizes and len(pixel_sizes) == 1:
        width_um = panels[0].labels.shape[1] * panels[0].pixel_um  # type: ignore[operator]
        figure.scale_bar_um = max((v for v in SCALE_BARS_UM if v <= width_um * .3), default=None)
    return figure


def scaled(figure: ImageFigure, panel: ImagePanel, cid: str) -> np.ndarray:
    low, high = figure.display[cid]
    return np.clip((panel.channels[cid].astype(float) - low) / (high - low), 0, 1)


def merge(figure: ImageFigure, panel: ImagePanel) -> np.ndarray:
    """The measured stain in magenta and the region stain in green (never red with green)."""
    rgb = scaled(figure, panel, figure.measured)[..., None] * MAGENTA  # type: ignore[arg-type]
    if figure.counterstain and figure.counterstain in panel.channels:
        rgb = rgb + scaled(figure, panel, figure.counterstain)[..., None] * GREEN
    return np.clip(rgb, 0, 1)


def draw_images(fig, holder, figure: ImageFigure, font_size: float, outlines: bool = True):
    """Square tiles packed in the space of ``holder`` (an empty axes the layout reserved): one row per
    condition, the measured stain in grey with the measured outlines, then the merge. Call after the
    layout is fixed."""
    from scipy import ndimage
    from skimage import measure

    columns = 2 if figure.counterstain else 1
    rows = len(figure.panels)
    holder.set_axis_off()
    x0, y0, width, height = holder.get_position().bounds
    fig_w, fig_h = fig.get_figwidth(), fig.get_figheight()
    gap = .03  # inches between tiles
    title = (font_size + 3) / 72  # the stain names above the first row
    tile = min((width * fig_w - gap * (columns - 1)) / columns, (height * fig_h - title - gap * (rows - 1)) / rows)
    top = y0 + height - title / fig_h
    left = x0 + width - (columns * tile + gap * (columns - 1)) / fig_w
    axes_list = []
    for row, panel in enumerate(figure.panels):
        pictures = [scaled(figure, panel, figure.measured)]  # type: ignore[arg-type]
        if columns == 2:
            pictures.append(merge(figure, panel))
        for column, picture in enumerate(pictures):
            ax = fig.add_axes((left + column * (tile + gap) / fig_w, top - ((row + 1) * tile + row * gap) / fig_h,
                               tile / fig_w, tile / fig_h))
            axes_list.append(ax)
            ax.imshow(picture, cmap="gray" if picture.ndim == 2 else None, vmin=0, vmax=1, interpolation="nearest",
                      aspect="auto")
            ax.set_xticks([])
            ax.set_yticks([])
            for spine in ax.spines.values():
                spine.set_visible(False)
            ax.set_gid(f"panel-a-image-{row + 1}-{column + 1}")
            side = picture.shape[1]
            if column == 0 and outlines:
                for region in panel.regions:
                    mask = panel.labels == region
                    if not mask.any():
                        continue
                    filled = ndimage.binary_fill_holes(mask).astype(float)
                    for contour in measure.find_contours(np.pad(filled, 1), .5):
                        ax.plot(contour[:, 1] - 1, contour[:, 0] - 1, color=OUTLINE, linewidth=.4)
                ax.set_xlim(-.5, side - .5)
                ax.set_ylim(picture.shape[0] - .5, -.5)
            if column == 0:
                from .figure_style import wrap_label

                label_size = max(5.0, font_size - 1)
                ax.text(.04, .96, wrap_label(panel.group, tile * 25.4 * .9, label_size), transform=ax.transAxes,
                        ha="left", va="top", color="white", fontsize=label_size, linespacing=1.1)
            if row == 0:
                if column == 0:
                    ax.set_title(figure.names.get(figure.measured or "", figure.measured), fontsize=font_size, pad=2)
                else:
                    ax.text(.48, 1.03, figure.names.get(figure.counterstain or "", ""), color="#1A9E3A",
                            transform=ax.transAxes, ha="right", va="bottom", fontsize=font_size)
                    ax.text(.52, 1.03, figure.names.get(figure.measured or "", ""), color="#C0119D",
                            transform=ax.transAxes, ha="left", va="bottom", fontsize=font_size)
            if row == rows - 1 and column == columns - 1 and figure.scale_bar_um and panel.pixel_um:
                bar = figure.scale_bar_um / panel.pixel_um
                margin = side * .06
                ax.plot([side - margin - bar, side - margin], [side - margin, side - margin], color="white",
                        linewidth=1.4, solid_capstyle="butt")
                ax.text(side - margin, side - margin * 1.5, f"{figure.scale_bar_um:g} µm", color="white",
                        ha="right", va="bottom", fontsize=5)
    return axes_list


def legend_sentence(figure: ImageFigure) -> str:
    measured = figure.names.get(figure.measured or "", figure.measured or "")
    parts = ["Representative fields, one per condition"]
    rules = {p.selection for p in figure.panels}
    if rules == {"rule"}:
        parts[0] += " (the field whose value is closest to the condition's mean of runs)"
    elif "researcher" in rules:
        parts[0] += " (chosen by the researcher)"
    text = parts[0] + f": {measured} in grey"
    if figure.counterstain:
        counter = figure.names.get(figure.counterstain, figure.counterstain)
        text += f" and merge ({counter} green, {measured} magenta)"
    text += ("; each stain is shown with the same linear display range in every condition "
             "(0.5–99.5th percentile of the shown pixels); yellow outlines mark the measured regions")
    if figure.scale_bar_um:
        text += f". Scale bar, {figure.scale_bar_um:g} µm"
    return text + "."
