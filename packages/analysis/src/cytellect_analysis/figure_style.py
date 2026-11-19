"""Shared publication style: bundled font, physical sizes, colours, axis and label rules.

Presentation only. Nothing here reads or changes a measurement; axis helpers format the
saved values for display (for example a fraction shown in percent).
"""
from __future__ import annotations

import math
import re
import textwrap
from functools import lru_cache
from pathlib import Path

import numpy as np
from matplotlib import font_manager
from matplotlib.ticker import FuncFormatter, MaxNLocator

MM = 1 / 25.4
FONT_DIR = Path(__file__).parent / "assets/fonts"
FONT_FAMILY = "Liberation Sans"
FONT_FILES = {"regular": FONT_DIR / "LiberationSans-Regular.ttf", "bold": FONT_DIR / "LiberationSans-Bold.ttf"}
# Liberation Sans has Arial's metrics, so an editor substituting Arial or Helvetica keeps the layout.
SVG_FONT_STACK = "'Liberation Sans', Arial, Helvetica, sans-serif"
# Okabe–Ito (Wong 2011), without yellow, which is unreadable on white.
OKABE_ITO = ("#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9", "#D55E00", "#000000")
RUN_MARKERS = ("o", "s", "^", "D", "v", "P", "X")
INK = "#1A1A1A"
MUTED = "#6B6B6B"
DENSITY_FILL = "#E9E9E9"
DENSITY_EDGE = "#A6A6A6"
BAR_FILL = "#DDDDDD"
SIZES_MM = {"single-column": 89.0, "double-column": 183.0}
PNG_DPI = 600


@lru_cache(maxsize=1)
def register_bundled_fonts() -> bool:
    """Make the bundled Liberation Sans available to Matplotlib (idempotent)."""
    present = [path for path in FONT_FILES.values() if path.is_file()]
    for path in present:
        font_manager.fontManager.addfont(str(path))
    return len(present) == len(FONT_FILES)


def rc(font_size: float) -> dict:
    """Matplotlib settings for one figure; used inside ``plt.rc_context``."""
    tick = max(5.0, font_size - .5)
    return {
        "svg.fonttype": "none", "pdf.fonttype": 42, "ps.fonttype": 42,
        "font.family": "sans-serif", "font.sans-serif": [FONT_FAMILY, "Arial", "DejaVu Sans"],
        "font.size": font_size, "axes.labelsize": font_size, "axes.titlesize": font_size,
        "xtick.labelsize": tick, "ytick.labelsize": tick, "legend.fontsize": tick,
        "axes.linewidth": .5, "xtick.major.width": .5, "ytick.major.width": .5,
        "xtick.major.size": 2.5, "ytick.major.size": 2.5, "xtick.major.pad": 2, "ytick.major.pad": 2,
        "axes.labelpad": 3, "lines.linewidth": .6, "lines.solid_capstyle": "butt",
        "axes.spines.top": False, "axes.spines.right": False, "axes.edgecolor": INK,
        "xtick.color": INK, "ytick.color": INK, "text.color": INK, "axes.labelcolor": INK,
        "legend.frameon": False, "legend.handletextpad": .3, "legend.borderaxespad": 0,
        "legend.labelspacing": .35, "svg.hashsalt": "cytellect-publication-figure-1",
    }


def run_colors(runs, overrides=None):
    """One colour per run in run order; a researcher's colour for a run wins."""
    overrides = overrides or {}
    return {run: overrides.get(str(run), OKABE_ITO[index % len(OKABE_ITO)]) for index, run in enumerate(runs)}


def run_marker(index: int) -> str:
    # More runs than colours: the marker shape keeps them distinguishable.
    return RUN_MARKERS[(index // len(OKABE_ITO)) % len(RUN_MARKERS)]


_NUMBER_UNIT = re.compile(r"(\d(?:[\d.,]*\d)?)\s+(?=[^\s\d])")


def keep_together(text: str) -> str:
    """Never separate a number from its unit (``10 µM``) when wrapping."""
    return _NUMBER_UNIT.sub(lambda match: match.group(1) + " ", text)


def wrap_label(text: str, width_mm: float, font_size: float, *, max_lines: int = 3) -> str:
    """Wrap at word boundaries to fit ``width_mm``; numbers stay with their units."""
    per_char_mm = font_size * .52 * 25.4 / 72  # average Arial glyph width
    columns = max(6, int(width_mm / per_char_mm))
    lines = textwrap.wrap(keep_together(text), columns, break_long_words=False, break_on_hyphens=False)
    if len(lines) > max_lines:
        lines = lines[:max_lines - 1] + [" ".join(lines[max_lines - 1:])]
    return "\n".join(lines).replace(" ", " ") or text


def balanced_two_lines(text: str, width_mm: float, font_size: float) -> str:
    """An axis title on one line when it fits, otherwise two lines of similar length."""
    per_char_mm = font_size * .52 * 25.4 / 72
    if len(text) * per_char_mm <= width_mm:
        return text
    protected = keep_together(text)
    words = protected.split(" ")
    if len(words) < 2:
        return text
    best = min(range(1, len(words)), key=lambda cut: abs(len(" ".join(words[:cut])) - len(" ".join(words[cut:]))))
    return (" ".join(words[:best]) + "\n" + " ".join(words[best:])).replace(" ", " ")


def nice_upper(value: float) -> float:
    """The smallest 1, 2, 2.5 or 5 × 10^k at or above ``value``."""
    if value <= 0:
        return 1.0
    power = 10 ** math.floor(math.log10(value))
    for step in (1, 2, 2.5, 5, 10):
        if step * power >= value * (1 - 1e-12):
            return step * power
    return 10 * power


def tick_locator():
    return MaxNLocator(nbins=5, steps=[1, 2, 2.5, 5, 10], min_n_ticks=3)


def value_formatter(scale: str, values) -> tuple[FuncFormatter, str]:
    """A tick formatter and the unit note for the axis title.

    Fractions are shown in percent. Large values are shown in multiples of a power of ten so
    the tick labels stay short; the multiplier goes into the axis title.
    """
    if scale == "fraction":
        return FuncFormatter(lambda value, _: f"{value * 100:.0f}"), "%"
    peak = float(np.nanmax(np.abs(values))) if len(values) else 0.0
    if peak >= 1e5:
        power = int(math.floor(math.log10(peak)))
        factor = 10 ** power
        superscript = str(power).translate(str.maketrans("0123456789-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁻"))
        return FuncFormatter(lambda value, _: _compact(value / factor)), f"×10{superscript}"
    return FuncFormatter(lambda value, _: _compact(value)), ""


def _compact(value: float) -> str:
    if abs(value) < 1e-12:
        return "0"
    if abs(value) >= 1000:
        return f"{value:,.0f}"
    text = f"{value:.3g}"
    return text.replace("-", "−")


def signed(value: float, digits: int = 0) -> str:
    """A signed number with a true minus sign (``+52``, ``−6``)."""
    text = f"{value:+.{digits}f}"
    return text.replace("-", "−")


def p_text(p: float | None) -> str | None:
    if p is None or not np.isfinite(p):
        return None
    if p < .001:
        return "P < 0.001"
    if p >= .1:
        return f"P = {p:.2f}"
    return f"P = {float(f'{p:.2g}'):g}"


def p_stars(p: float | None) -> str | None:
    if p is None or not np.isfinite(p):
        return None
    return "***" if p < .001 else "**" if p < .01 else "*" if p < .05 else "n.s."


register_bundled_fonts()
