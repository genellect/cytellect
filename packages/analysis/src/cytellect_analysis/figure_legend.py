"""A draft figure legend for a paper, written by rule from the saved result (English).

The title states the result as the summary on the screen does (direction, rough size, agreement of the
runs); every number is a saved one. Facts that the workspace does not record (cell line, treatment
time, antibodies or dyes) are left as bracketed gaps for the researcher to fill; they are never guessed.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from .figure_annotations import _grouped
from .publication_figure import axis_title

GAPS = ("[Cell line]", "[treatment and duration]", "[antibody or dye for each stain]")
# Saved unit labels that are not units of a size; the summary on the screen leaves them out too.
UNITLESS = frozenset({"dimensionless", "count", "fraction of evaluable nuclei"})


def _join(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def _rough(value: float) -> str:
    """Two significant digits, as the summary heading states a size (result-summary.ts `rough`)."""
    return _decimal_number(abs(value))


def _decimal_number(value: float, precision: int = 2) -> str:
    number = Decimal(str(value))
    if not number:
        return "0"
    rounded = number.quantize(Decimal(1).scaleb(number.adjusted() - precision + 1), rounding=ROUND_HALF_UP)
    text = format(rounded, "f")
    # Rounded as result-summary.ts does; the English text groups thousands, as the legend's body does.
    return _grouped((text.rstrip("0").rstrip(".") if "." in text else text).replace("-", "−"))


def _mid_sentence(title: str) -> str:
    """Lower-case an ordinary first word ("Nuclear"); a stain name keeps its capitals ("NPM1", "EdU")."""
    word = title.split(" ", 1)[0]
    return title[0].lower() + title[1:] if word.isalpha() and word[1:].islower() else title


def _span(values: list[float]) -> str:
    low, high = _rough(min(values)), _rough(max(values))
    return low if low == high else f"{low}–{high}"


def _sign(value: float) -> int:
    return (value > 0) - (value < 0)


def _outcome_title(canonical) -> str:
    title, _ = axis_title(canonical)
    return ("The proportion of " + title.replace("Positive nuclei", "positive nuclei")
            if canonical.get("metric") == "positive_fraction" else title)


def _title(canonical, order) -> str:
    """One sentence for what the figure shows: the heading of the result summary (FL-03, RS-02)."""
    title = _outcome_title(canonical)
    unit = canonical.get("unit") or ""
    unit = "" if unit in UNITLESS else unit
    estimates = canonical.get("estimates")
    if not estimates or len(order) != 2:
        return f"{title} in {_join(list(order))}"
    control, treatment, scale = estimates["control"], estimates["treatment"], estimates["scale"]
    runs = estimates.get("runs") or []
    difference, ratio = estimates["difference"], estimates["ratio"]
    suffix = " percentage points" if scale == "fraction" else " (log2)" if scale == "log2" else f" {unit}" if unit else ""

    def moved(direction: int, size: str = "") -> str:
        return f"{title} {'decreased' if direction < 0 else 'increased'}{size} with {treatment}"

    unclear = f"{title} did not differ clearly between {treatment} and {control}"
    if estimates["test"] == "none":
        means = {group["condition"]: group.get("mean") for group in estimates.get("groups") or []}
        if runs:
            shown = _sign(sum(_sign(run["difference"]) for run in runs))
        elif means.get(control) is not None and means.get(treatment) is not None:
            shown = _sign(means[treatment] - means[control])
        else:
            shown = 0
        if not runs:
            if means.get(control) is None or means.get(treatment) is None:
                return unclear
            def mean_text(group):
                value = _decimal_number(means[group] * (100 if scale == "fraction" else 1), 3)
                return f"{value}%" if scale == "fraction" else f"{value}{suffix}"
            return f"Mean {_mid_sentence(title.removeprefix('The '))} was {mean_text(control)} in {control} and {mean_text(treatment)} in {treatment}"
        if not shown or sum(_sign(run["difference"]) == shown for run in runs) < len(runs):
            return f"{title} did not change consistently with {treatment}"
        ratios = [run["ratio"] for run in runs] if all((run.get("ratio") or 0) > 0 for run in runs) else None
        if ratios and all(value >= 2 for value in ratios):
            return f"{title} increased {_span(ratios)}-fold with {treatment}"
        if ratios:
            return moved(shown, f" by {_span([abs(value - 1) * 100 for value in ratios])}%")
        return moved(shown, f" by {_span([abs(run['difference']) for run in runs])}{suffix}")
    if difference["estimate"] is not None and difference["ci_low"] is not None and difference["ci_high"] is not None:
        direction = _sign(difference["estimate"])
        if not direction or difference["ci_low"] <= 0 <= difference["ci_high"]:
            return unclear
        change = ratio["estimate"]
        if change is None or change <= 0 or _sign(change - 1) != direction:
            return moved(direction, f" by about {_rough(difference['estimate'])}{suffix}")
        if change >= 2:
            return f"{title} increased about {_rough(change)}-fold with {treatment}"
        return moved(direction, f" by about {_rough((change - 1) * 100)}%")
    # A rank test gives no mean difference: the direction is the saved effect's, stated only when P < 0.05.
    row = (canonical.get("comparisons") or [{}])[0]
    p, effect, name = row.get("p_value"), row.get("effect"), row.get("effect_name") or ""
    if p is None or not p < 0.05:
        return unclear
    centre = 0.5 if "superiority" in name else 0 if "rank-biserial" in name else None
    facing = (1 if (row.get("group_a"), row.get("group_b")) == (treatment, control)
              else -1 if (row.get("group_a"), row.get("group_b")) == (control, treatment) else 0)
    ranked = _sign(effect - centre) * facing if effect is not None and centre is not None else 0
    return moved(ranked) if ranked else f"{title} differed between {treatment} and {control}"


def _run_value(spec, counts, order, nouns: str) -> str:
    """How one run's value is made from its observations, in words."""
    fields_only = (spec.get("selection") or {}).get("source") == "field-summary"
    rows = [counts[c] for c in order if c in counts]
    # One sample per run in every group: the sample level adds nothing to say.
    single = bool(rows) and all(row.get("samples") is not None and row.get("samples") == row.get("experimental_units")
                                for row in rows)
    field = "" if fields_only else f", each field summarised by the median of its {nouns}"
    if single:
        return f"the mean of its fields{field}"
    return f"the mean of its samples, each sample the mean of its fields{field}"


def _counts(counts, order, nouns: str, unit_word: str) -> str:
    """n and what it is made of: runs, then the observations and fields behind them."""
    rows = [(c, counts[c]) for c in order if c in counts]

    def each(key: str, noun: str) -> str:
        values = [row.get(key) for _, row in rows]
        if any(value is None for value in values):
            return ""
        if len(set(values)) == 1:
            return f"{values[0]:,} {noun} per condition"
        return _join([f"{value:,} ({c})" for (c, _), value in zip(rows, values, strict=True)]) + f" {noun}"

    units = each("experimental_units", unit_word)
    fields = each("selected_fields", "fields")
    if nouns == "fields":
        detail = each("observations", "fields")
        replicates = "individual fields are"
    else:
        observed = [row.get("observations") for _, row in rows]
        detail = ("" if any(value is None for value in observed)
                  else _join([f"{value:,} ({c})" for (c, _), value in zip(rows, observed, strict=True)]) + f" {nouns}")
        if detail and fields:
            detail += f" from {fields}"
        replicates = f"individual {nouns} and fields are"
    text = f"n = {units}" if units else ""
    if detail:
        text += ("; " if text else "") + detail
    return f"{text}; {replicates} not treated as independent replicates." if text else ""


def _opening(title: str, corrected: bool = False) -> str:
    note = " (background-subtracted)" if corrected else ""
    return f"We quantified {_mid_sentence(title)}{note} in {GAPS[0]} cells ({GAPS[1]}) labelled with {GAPS[2]}."


def _selection_sentence(canonical) -> list[str]:
    selection = canonical.get("selection") or {}
    record = selection.get("channel_gate") or selection.get("gfp_gate")
    if not record:
        return []
    gate = record["filter"]
    channel = record.get("channel") or record.get("gfp_channel") or {}
    label = channel.get("stain") or channel.get("label") or gate.get("channel_id") or gate.get("gfp_channel_id") or "GFP"
    method = gate.get("method", "negative_control")
    classification = ("a threshold derived from designated negative-control nuclei" if method == "negative_control"
                      else "a researcher-specified threshold" if method == "manual"
                      else "Otsu thresholding per acquisition date")
    objects = "cell ROIs" if gate.get("unit") == "cell_roi" else "nuclei"
    metric = canonical.get("metric")
    subset = (f"Only {label}-{gate['keep']} {objects} were analysed. "
              if record.get("purpose") != "field_positivity" else
              "Positive fractions used all evaluable positive and negative nuclei as the denominator. "
              if metric == "positive_fraction" else
              f"{label}-positive nuclei were counted in each field. " if metric == "positive_count" else "")
    return [subset + f"Classification used {classification} of mean {label} intensities; a value strictly above the "
            "threshold was positive and equality was negative. Unclassified objects were not selected."]


def comparison_legend(canonical, order, drawn, presentation, panels=None) -> tuple[str, list[str]]:
    """The legend text and the list of gaps left for the researcher."""
    spec = canonical["spec"]
    description = drawn.description
    title = _outcome_title(canonical)
    counts = {row["condition"]: row for row in canonical.get("counts") or []}
    nouns = description.get("observations", "observations")
    paired = description.get("paired")
    unit_word = "runs" if paired else "experimental units"
    lines = [_opening(title, str(canonical.get("metric", "")).endswith("_corrected"))]
    lines.extend(panels or [])
    # What the figure draws: the observations (unless a summary of dense data leaves them out), each run, and
    # the summary the chosen form adds.
    parts = []
    if description.get("points", True):
        parts.append(f"small dots show individual {nouns}" + (", coloured by run" if description.get("by_run") else ""))
    parts.append(f"large symbols show the value of each {unit_word[:-1]} ({_run_value(spec, counts, order, nouns)})")
    if paired:
        parts.append("lines join the same run")
    summarised = "run values" if description.get("run_level") else nouns
    shape = description.get("shape") or ("violin" if description.get("density") else None)
    if shape == "box":
        parts.append(f"boxes show the median and interquartile range of {summarised}, whiskers the most extreme values "
                     "within 1.5 × the interquartile range")
    elif shape == "violin":
        parts.append(f"grey outlines show the distribution of {summarised}")
    elif shape == "histogram":
        parts.append("grey bars show a histogram of run values")
    if shape and not description.get("shape_in_every_group", True):
        # A box or an outline needs at least three values (an outline, values that differ); a histogram, a value.
        parts[-1] += " (where a group has enough values to summarise)"
    parts.append(("bars" if description.get("bars") else "horizontal lines") + f" show the mean of {unit_word}")
    sentence = "; ".join(parts)
    if lines[-1] == "b,":
        lines[-1] = "b, " + sentence[0].upper() + sentence[1:] + "."
    else:
        lines.append(sentence[0].upper() + sentence[1:] + ".")
    n = _counts(counts, order, nouns, unit_word)
    if n:
        lines.append(n)
    lines.extend(_selection_sentence(canonical))
    groups = drawn.summary
    if groups and any(g.get("ci_low") is not None for g in groups):
        lines.append(f"Error bars show the 95% confidence interval of the mean of {unit_word}.")
    lines.extend(sentence if sentence.endswith(".") else sentence + "." for sentence in drawn.annotations.legend)
    excluded = sum(row.get("explicitly_excluded_units", 0) for row in canonical.get("counts") or [])
    missing = len(canonical.get("missingness") or [])
    left_out = []
    if missing:
        noun = description.get("observation", "observation") if missing == 1 else nouns
        left_out.append(f"{missing:,} {noun} without a value for this measure")
    if excluded:
        left_out.append(f"{excluded:,} excluded {unit_word[:-1] if excluded == 1 else unit_word}")
    if left_out:
        lines.append(f"Not shown: {_join(left_out)} (listed in the source tables).")
    return f"**{_title(canonical, order)}.**\n\n" + " ".join(lines) + "\n", list(GAPS)


def association_legend(canonical, order, drawn) -> tuple[str, list[str]]:
    x_title, _ = axis_title(canonical["x_source"])
    y_title, _ = axis_title(canonical["y_source"])
    counts = {row["condition"]: row for row in canonical.get("counts") or []}
    n = _join([f"{counts[c].get('matched_units', counts[c].get('experimental_units', '?'))} ({c})" for c in order if c in counts])
    method = (canonical.get("spec") or {}).get("method", "")
    method_name = {"pearson": "Pearson", "spearman": "Spearman"}.get(method, method)
    scope = "across the explicitly pooled conditions" if (canonical.get("spec") or {}).get("scope") == "pooled" else "within each condition"
    body = [_opening(f"{y_title} against {x_title}"),
            "Each point is one independent experimental unit (the mean of its samples, each sample the mean of its "
            f"fields, each field summarised by its median); n = {n}.",
            *([f"{method_name} correlation was calculated {scope}."] if method_name else []),
            *[line + "." for line in drawn.annotations.legend],
            "No line is fitted and no confidence band is shown; an association does not establish causation."]
    return f"**{y_title} against {x_title}.**\n\n" + " ".join(body) + "\n", list(GAPS)
