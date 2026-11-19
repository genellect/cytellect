"""Figure annotations written by rule from a saved result (presentation only).

Every number comes from the saved statistics (``estimates``, ``comparisons``,
``associations``); nothing is estimated here. The direction is always treatment − control.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from .figure_style import p_stars, p_text, signed


@dataclass
class Bracket:
    left: str
    right: str
    lines: list[str]
    # The same facts in full, for the written legend.
    legend: str = ""


@dataclass
class Annotations:
    brackets: list[Bracket] = field(default_factory=list)
    legend: list[str] = field(default_factory=list)


def _number(value: float) -> str:
    """Two significant digits, never fewer than the integer part."""
    if value == 0:
        return "0"
    magnitude = math.floor(math.log10(abs(value)))
    digits = max(0, 1 - magnitude)
    return f"{value:.{digits}f}".replace("-", "−")


def _signed_number(value: float) -> str:
    text = _number(value)
    return text if text.startswith("−") or text == "0" else "+" + text


def _percent(ratio: float) -> str:
    change = (ratio - 1) * 100
    return signed(change, 0 if abs(change) >= 10 else 1) + "%"


def _effect(estimates) -> tuple[str | None, str | None]:
    """The figure text and the legend sentence of a tested two-group estimate."""
    ratio, difference = estimates["ratio"], estimates["difference"]
    if estimates["scale"] == "ratio" and ratio["estimate"] is not None:
        text = (f"{_percent(ratio['estimate'])} (95% CI {_percent(ratio['ci_low'])} to "
                f"{_percent(ratio['ci_high'])})")
        return text, f"{ratio['basis']}: {text}"
    if difference["estimate"] is not None:
        unit = " pp" if estimates["scale"] == "fraction" else ""
        text = (f"Δ = {_signed_number(difference['estimate'])}{unit} (95% CI "
                f"{_signed_number(difference['ci_low'])} to {_signed_number(difference['ci_high'])}{unit})")
        return text, f"{difference['basis']}: {text}"
    return None, None


def _runs(estimates) -> tuple[str | None, str | None]:
    """Per-run changes of a descriptive comparison: a range when all agree, else a count."""
    runs = estimates.get("runs") or []
    if not runs:
        return None, None
    ratio_scale = estimates["scale"] == "ratio" and all(run.get("ratio") is not None for run in runs)
    if ratio_scale:
        changes = [(run["ratio"] - 1) * 100 for run in runs]
        shown = [signed(change, 0 if abs(change) >= 10 else 1) + "%" for change in changes]
    else:
        changes = [run["difference"] for run in runs]
        unit = " pp" if estimates["scale"] == "fraction" else ""
        shown = [_signed_number(change) + unit for change in changes]
    higher = sum(change > 0 for change in changes)
    lower = sum(change < 0 for change in changes)
    total = len(changes)
    listing = ", ".join(f"{run['pair']} {text}" for run, text in zip(runs, shown, strict=True))
    if higher == total or lower == total:
        order = sorted(range(total), key=lambda index: abs(changes[index]))
        first, last = shown[order[0]], shown[order[-1]]
        if ratio_scale:
            first = first.removesuffix("%")
        elif estimates["scale"] == "fraction":
            first = first.removesuffix(" pp")
        prefix = "" if ratio_scale or estimates["scale"] == "fraction" else "Δ "
        text = f"{prefix}{first} to {last} ({total}/{total} runs)" if total > 1 else f"{prefix}{last} (1 run)"
    elif higher >= lower:
        text = f"Higher in {higher} of {total} runs"
    else:
        text = f"Lower in {lower} of {total} runs"
    kind = "change" if ratio_scale else "difference"
    return text, f"Per-run {kind} ({estimates['treatment']} − {estimates['control']}): {listing}"


def comparison_annotations(result, order, mode: str = "value") -> Annotations:
    """Brackets and legend sentences for a saved group comparison."""
    notes = Annotations()
    if mode == "none":
        mode = "value"  # the legend keeps the facts; the renderer omits the brackets
    spec = result["spec"]
    estimates = result.get("estimates")
    if spec.get("test") == "none":
        if estimates:
            text, sentence = _runs(estimates)
            if text:
                notes.brackets.append(Bracket(estimates["control"], estimates["treatment"], [text], sentence or ""))
                notes.legend.append(sentence or text)
        notes.legend.append("Descriptive comparison: run independence was not confirmed, so no hypothesis test "
                            "or confidence interval was calculated.")
        return notes
    rows = result.get("comparisons") or []
    adjusted = len(rows) > 1
    for row in rows:
        p = row.get("p_holm") if adjusted and row.get("p_holm") is not None else row.get("p_value")
        p_line = p_stars(p) if mode == "stars" else p_text(p)
        lines: list[str] = []
        sentence = ""
        pair = {row["group_a"], row["group_b"]}
        if estimates and {estimates["control"], estimates["treatment"]} == pair:
            effect, sentence = _effect(estimates)
            if effect and mode != "stars":
                lines.append(effect)
            left, right = estimates["control"], estimates["treatment"]
        else:
            left, right = row["group_a"], row["group_b"]
        if p_line:
            lines.append(p_line)
        test = row.get("method", "test")
        p_sentence = (f"{test}, {'Holm-adjusted ' if adjusted else ''}{p_text(p) or 'P not available'}"
                      if p is not None else f"{test}")
        legend = "; ".join(part for part in (f"{right} versus {left}", sentence, p_sentence) if part)
        notes.brackets.append(Bracket(left, right, lines, legend))
        notes.legend.append(legend)
    if result.get("omnibus"):
        omnibus = result["omnibus"]
        notes.legend.append(f"Omnibus {omnibus.get('method', 'test')}: {p_text(omnibus.get('p_value')) or 'P not available'}.")
    if mode == "stars":
        notes.legend.append("* P < 0.05, ** P < 0.01, *** P < 0.001; n.s., P ≥ 0.05"
                            + (" (Holm-adjusted)" if adjusted else "") + ".")
    if len(notes.brackets) > 3:
        notes.brackets = []  # four or more contrasts are listed in the legend and the table
    known = set(order)
    notes.brackets = [b for b in notes.brackets if b.left in known and b.right in known]
    return notes


def association_label(result, row) -> str:
    symbol = "r" if "Pearson" in row.get("method", "") else "ρ"
    adjusted = len(result.get("associations") or []) > 1 and row.get("p_holm") is not None
    p = row["p_holm"] if adjusted else row.get("p_value")
    coefficient = row.get("coefficient")
    parts = [f"{symbol} = {_number(coefficient)}" if coefficient is not None else f"{symbol} not estimated"]
    shown = p_text(p)
    if shown:
        parts.append(shown + (" (Holm)" if adjusted else ""))
    return ", ".join(parts)
