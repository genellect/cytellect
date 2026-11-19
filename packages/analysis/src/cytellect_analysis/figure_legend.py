"""A draft figure legend for a paper, written by rule from the saved result (English).

Facts that the workspace does not record (cell line, treatment time, antibodies or dyes)
are left as bracketed gaps for the researcher to fill; they are never guessed.
"""
from __future__ import annotations

from .publication_figure import axis_title

GAPS = ("[Cell line]", "[treatment and duration]", "[antibody or dye for each stain]")
AGGREGATION = {
    "field-summary": "field values → mean of fields per sample → mean of samples per run",
    "region": "median of observations per field → mean of fields per sample → mean of samples per run",
}


def _aggregation(spec) -> str:
    source = (spec.get("selection") or {}).get("source", "region")
    return AGGREGATION["field-summary" if source == "field-summary" else "region"]


def _join(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def comparison_legend(canonical, order, drawn, presentation, panels=None) -> tuple[str, list[str]]:
    """The legend text and the list of gaps left for the researcher."""
    spec = canonical["spec"]
    description = drawn.description
    title, _ = axis_title(canonical)
    control = (canonical.get("estimates") or {}).get("control")
    treatment = (canonical.get("estimates") or {}).get("treatment")
    compared = (f"{treatment} versus {control}" if control and treatment and len(order) == 2
                else _join(list(order)))
    counts = {row["condition"]: row for row in canonical.get("counts") or []}
    nouns = description.get("observations", "observations")
    paired = description.get("paired")
    unit_word = "runs" if paired else "experimental units"
    n_units = sorted({counts[c].get("experimental_units") for c in order if c in counts})
    observations = _join([f"{counts[c]['observations']:,} {nouns} ({c})" for c in order if c in counts])
    fields = _join([f"{counts[c]['selected_fields']} ({c})" for c in order if c in counts and "selected_fields" in counts[c]])
    lines = [f"**{title}, {compared}.**", ""]
    lines.append(f"{GAPS[0]} cells were treated as indicated ({GAPS[1]}) and imaged "
                 f"({GAPS[2]}).")
    lines.extend(panels or [])
    marks = []
    if description.get("bars"):
        marks.append("bars show the mean of runs")
    else:
        marks.append("horizontal lines show the mean of runs")
    # What the figure draws: the observations (unless a summary of dense data leaves them out), each run, and
    # the summary the chosen form adds.
    parts = []
    if description.get("points", True):
        parts.append(f"small dots show individual {nouns}" + (", coloured by run" if description.get("by_run") else ""))
    parts.append(f"large symbols show the value of each run ({_aggregation(spec)})")
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
    sentence = "; ".join(parts + marks)
    sentence = sentence[0].upper() + sentence[1:]
    if lines[-1] == "b,":
        lines[-1] = "b, " + sentence[0].lower() + sentence[1:] + "."
    else:
        lines.append(sentence + ".")
    lines.append(f"n = {_join([str(v) for v in n_units])} {unit_word} per condition"
                 + (f"; {observations}" if observations else "") + (f" from {fields} fields" if fields else "")
                 + f". {nouns.capitalize()} and fields are not independent replicates.")
    groups = drawn.summary
    if groups and any(g.get("ci_low") is not None for g in groups):
        lines.append("Error bars show the 95% confidence interval of the mean of runs.")
    lines.extend(sentence if sentence.endswith(".") else sentence + "." for sentence in drawn.annotations.legend)
    excluded = sum(row.get("explicitly_excluded_units", 0) for row in canonical.get("counts") or [])
    missing = len(canonical.get("missingness") or [])
    if excluded or missing:
        lines.append(f"Excluded runs: {excluded}; observations without a value: {missing} (recorded in the source tables).")
    text = "\n\n".join(part for part in (lines[0], " ".join(lines[2:])) if part) + "\n"
    return text, list(GAPS)


def association_legend(canonical, order, drawn) -> tuple[str, list[str]]:
    x_title, _ = axis_title(canonical["x_source"])
    y_title, _ = axis_title(canonical["y_source"])
    counts = {row["condition"]: row for row in canonical.get("counts") or []}
    n = _join([f"{counts[c].get('experimental_units', '?')} ({c})" for c in order if c in counts])
    body = [f"{GAPS[0]} cells were treated as indicated ({GAPS[1]}) and imaged ({GAPS[2]}).",
            f"Each point is one independent experimental unit (median per field → mean of fields per sample → "
            f"mean of samples per unit); n = {n}.",
            *[line + "." for line in drawn.annotations.legend],
            "No fitted line or confidence band is shown; association is not causation."]
    return f"**{y_title} against {x_title}.**\n\n" + " ".join(body) + "\n", list(GAPS)
