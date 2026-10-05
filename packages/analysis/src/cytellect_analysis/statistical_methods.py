"""Versioned prose from saved facts; never calculate or change scientific results."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class StatisticalMethodsTemplate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, revalidate_instances="always")
    id: Literal["cytellect-statistical-methods"]
    version: Literal["1.0.0"]


CURRENT_METHODS_TEMPLATE = StatisticalMethodsTemplate(id="cytellect-statistical-methods", version="1.0.0")


def methods_metadata(template):
    """None is the internal historical dispatch; explicit saved null is invalid."""
    if template is None:
        return {}
    return {"methods_template": StatisticalMethodsTemplate.model_validate(template).model_dump(mode="json")}


def saved_methods_template(result):
    figure = result.get("figure", {})
    if not isinstance(figure, dict):
        raise ValueError("statistical_methods_template_invalid")
    if "methods_template" not in figure:
        return None
    if figure["methods_template"] is None:
        raise ValueError("statistical_methods_template_invalid")
    return StatisticalMethodsTemplate.model_validate(figure["methods_template"])


def _count(row, key):
    value = row[key]
    if type(value) is not int or value < 0:
        raise ValueError("statistical_methods_source_invalid")
    return str(value)


def _measurement(result):
    source, metric, fields = result["source_kind"], result["metric"], result["source_fields"]
    if not fields:
        raise ValueError("statistical_methods_source_invalid")
    lines = [f"Selected outcome: {metric}; unit: {result['unit']}."]
    if source == "measured-numerical-assay":
        lines.append("Previously measured numerical values were described in their recorded units. "
                     "This step performed no image measurement or background correction.")
        return lines
    legacy = False
    if source == "region-2d":
        from .region_policy import MEASUREMENT_POLICY

        modes: set[str] = set()
        for field in fields:
            protocol = field.get("measurement_protocol", "1.0.0")
            policy = field.get("measurement")
            if protocol in ("2.0.0", "3.0.0"):
                policy = MEASUREMENT_POLICY.validate_python(policy)
                modes.add(policy.mode)
            elif protocol == "1.0.0" and policy is None:
                modes.add("intensity-and-area")
            else:
                raise ValueError("statistical_methods_source_invalid")
        if len(modes) != 1:
            raise ValueError("statistical_methods_source_invalid")
        labels = {field["region_set"]["label"] for field in fields}
        if len(labels) != 1:
            raise ValueError("statistical_methods_source_invalid")
        review_word = "saved" if result.get("source_review") == "automatic_unreviewed" else "saved reviewed"
        lines.append(f"Region definition: {next(iter(labels))}. {review_word.capitalize()} integer-labelled pixel unions "
                     "in original image coordinates defined the measured regions; an object ID does not establish a biological cell.")
        channel_id = result["spec"]["selection"].get("channel_id")
        if channel_id is not None:
            identities = set()
            for field in fields:
                channels = [entry["channel"] for entry in field["channel_provenance"]
                            if entry["channel"]["channel_id"] == channel_id]
                if len(channels) != 1:
                    raise ValueError("statistical_methods_source_invalid")
                identities.add((channels[0]["label"], channels[0].get("stain")))
            if len(identities) != 1:
                raise ValueError("statistical_methods_source_invalid")
            label, stain = next(iter(identities))
            lines.append(f"Measured channel: {label}; stain: {stain or 'not recorded'}; recorded channel ID: {channel_id}.")
        if "raw_intensity" in modes:
            lines.append("Raw-intensity protocol 3.0.0 measured original pixels. Background was not established; corrected intensities are missing.")
        if "area_only" in modes:
            if metric not in ("area_px", "area_um2"):
                raise ValueError("statistical_methods_source_invalid")
            lines.append("Area-only measurement used measurement protocol 2.0.0 and policy 1.0.0 (area_only). "
                         "Fluorescence intensity and signal-saturation fractions were not measured. "
                         "Background estimation and correction were not performed.")
    elif source == "legacy-image-measurements":
        recipes = {field.get("recipe", {}).get("id") for field in fields}
        if len(recipes) != 1 or not recipes <= {"ncl-native-2d", "ncl-legacy-rgb", "gfp-nuclear-2d"}:
            raise ValueError("statistical_methods_source_invalid")
        recipe = next(iter(recipes))
        legacy = recipe == "ncl-legacy-rgb"
        lines.append(f"Source recipe: {recipe}. Saved nuclear masks and any applicable compartment masks defined the measurements.")
        if legacy:
            lines.append("For RGB inputs, the compatibility importer used max(R,G,B). Measurements used the recorded resized grid; "
                         "these intensities are not newly calculated native-resolution measurements. "
                         "Background was the median outside all nuclei on that grid, or zero when no outside pixels existed. "
                         "Corrected negative pixels were clipped to zero before averaging or summing. "
                         "Recorded conversion, resampling and compatibility QC parameters are retained in figure-data.json.")
        else:
            lines.append("Native measurements used unchanged original pixels. The nuclear-stain channel role does not establish the dye identity.")
        if metric.startswith("ncl_"):
            lines.append(("Compatibility compartments distinguish the nucleus, the NCL high-intensity region union and the remaining pixels; "
                          "high intensity does not establish biological nucleolar identity. " if legacy else
                          "NCL compartments distinguish the nucleus, the union of nucleolar candidate regions and the remaining nucleoplasm. ")
                         + "A union mean weights pixels, not individual object means. "
                         "Where regions were defined using NCL, their boundaries may change with the NCL distribution; "
                         "interpretation requires independent review.")
    else:
        raise ValueError("statistical_methods_source_invalid")
    if "area_px" in metric or "area_um2" in metric:
        lines.append("Area is the number of original-coordinate mask pixels; calibrated area multiplies this count by "
                     "the recorded X and Y pixel sizes (or the square of the scalar pixel size in nuclear recipes). "
                     "Unknown calibration is missing, never zero. Repeated channel rows do not increase region counts.")
    elif metric == "ncl_legacy_release":
        lines.append("The compatibility outcome is log2[(whole-nucleus corrected mean + epsilon)/(high-region corrected mean + epsilon)], "
                     "with epsilon=max(1, 1.4826 × background NCL MAD) as recorded by that recipe.")
    elif "over_nucleoli" in metric:
        if not legacy:
            lines.append("Native compartment correction subtracts the median of the recorded user-confirmed background ROI.")
        lines.append("The outcome is the background-corrected nucleoplasmic mean divided by the nucleolar-union mean"
                     + (", followed by log2." if "log2" in metric else ".")
                     + " Both corrected compartment means must be positive; undefined ratios retain a missing-value reason.")
    elif metric.endswith("count"):
        lines.append("The outcome counts high-intensity candidate objects on the compatibility measurement grid within each nucleus."
                     if legacy else "The outcome counts the saved nucleolar candidate objects within each nucleus.")
    elif metric.endswith("fraction"):
        lines.append("The outcome is the high-intensity union area divided by the nucleus area on the compatibility measurement grid."
                     if legacy else "The outcome is the nucleolar-union area divided by the nucleus area.")
    else:
        operation = next((name for name in ("integrated", "median", "mean") if name in metric), None)
        if operation is None:
            raise ValueError("statistical_methods_source_invalid")
        corrected = metric.endswith("_corrected")
        values = "max(I − b, 0)" if legacy and corrected else ("I − b" if corrected else "I")
        operator = {"integrated": "sum", "median": "median", "mean": "arithmetic mean"}[operation]
        lines.append(f"Each region outcome is the {operator} of ({values}) over its measured pixels.")
        if corrected and not legacy:
            lines.append("Here b is the median of the saved user-confirmed background ROI. Native negative corrected values remain signed.")
        if not corrected:
            lines.append("The selected raw outcome does not subtract background.")
        if operation == "integrated":
            lines.append("Integrated intensity is a pixel sum, not concentration.")
    return lines


def _gating(result):
    if result["source_kind"] != "legacy-image-measurements":
        return []
    records = result["selection"]["records"]
    methods = sorted({row["gfp_gate_method"] for row in records if row.get("gfp_gate_method")})
    lines = ["Saved GFP selection flags were retained; no new threshold was fitted for this description."]
    if methods:
        lines.append("Recorded GFP selection methods: " + ", ".join(methods) + ".")
    for key, label in (("gfp_gate_threshold", "lower threshold"), ("gfp_gate_maximum", "upper bound")):
        values = {row[key] for row in records if row.get(key) is not None}
        if len(values) == 1:
            lines.append(f"Recorded GFP {label}: {next(iter(values))}.")
        elif values:
            lines.append(f"The recorded GFP {label} varies by field; all actual values are retained in selection.csv.")
    if any("gfp_selection" in warning for warning in result["warnings"]):
        lines.append("Manual or data-derived GFP selection is exploratory and requires independent validation.")
    return lines


def readable_descriptive_methods(result):
    counts, selection = result["counts"], result["selection"]
    lines = ["# Cytellect descriptive Methods", "", "Generated from saved settings; review before publication.",
             "Statistical Methods template: cytellect-statistical-methods 1.0.0.",
             f"Descriptive protocol: {result['descriptive_version']}; source: {result['source_kind']}.",
             *(["Regions have not completed visual review. These automatic descriptive outputs do not certify segmentation quality."]
               if result.get("source_review") == "automatic_unreviewed" else []),
             *_measurement(result),
             "Only per-field descriptions were calculated: median and linearly interpolated quartiles "
             "at index (n−1)p in the ordered observations. No hypothesis test, regression, standard error or confidence interval was calculated.",
             f"Selected observations: {_count(counts, 'observations')}; fields with selected values: "
             f"{_count(counts, 'selected_fields')} of {_count(counts, 'input_fields')} registered fields. "
             "Independent experimental n was not assessed; region, field and sample labels do not establish independence.",
             f"Of {_count(selection, 'input_rows')} measured observation rows, {_count(selection, 'excluded')} were explicitly excluded, "
             f"{_count(selection, 'gate_unselected')} were unselected by the saved gate and "
             f"{_count(selection, 'missing_metric_selected')} otherwise selected outcomes were missing.",
             f"Explicitly excluded failed fields: {_count(counts, 'excluded_failed_fields')}; their observation counts remain unknown. "
             "Missing values and empty fields were retained with reasons, not replaced with zero.",
             *_gating(result),
             "No new normalization, image processing or selection was performed by this descriptive protocol.",
             "Complete observation values, field summaries and selection records are in plot-data.csv, field-summary.csv, "
             "selection.csv and figure-data.json; missingness.csv is included when missing outcomes exist. "
             "The source JSON retains field, mask, channel, recipe and applicable background/calibration provenance. "
             "Hashes in the accompanying source/manifest identify those files.",
             "Original acquisition details and biological suitability require researcher review; absent facts are not inferred.",
             "Warnings: " + "; ".join(result["warnings"]), ""]
    return "\n".join(lines)


def readable_comparison_methods(result):
    design, family = result["spec"]["design"], result["spec"]["comparison_family"]
    paired = design["kind"] == "paired"
    expected = "paired t-test" if paired else "Welch t-test"
    comparisons = result["comparisons"]
    if (not comparisons or any(row["method"] != expected or row["alternative"] != "two-sided"
                               or row["confidence_level"] != .95 for row in comparisons)):
        raise ValueError("statistical_methods_source_invalid")
    lines = ["# Cytellect generic-region comparison Methods", "", "Generated from saved settings; review before publication.",
             "Statistical Methods template: cytellect-statistical-methods 1.0.0.",
             f"Region comparison protocol: {result['region_comparison_version']}; inference core: {result['inference_version']}.",
             *_measurement(result), f"Declared independent experimental unit: {design['unit_definition']}.",
             "Aggregation: median of region observations within each field, mean of fields within each sample, "
             "then mean of samples within each independent experimental unit. Each retained unit contributes one value per condition; "
             "unequal numbers of regions or fields do not weight independent units."]
    for row in result["counts"]:
        lines.append(f"Condition {row['condition']}: n={_count(row, 'experimental_units')} independent experimental units "
                     f"from {_count(row, 'input_units')} input units ({_count(row, 'explicitly_excluded_units')} explicitly excluded); "
                     f"{_count(row, 'samples')} selected samples, {_count(row, 'selected_fields')}/{_count(row, 'input_fields')} "
                     f"selected/input fields and {_count(row, 'observations')} selected region observations.")
    if paired:
        lines.append(f"Pairing basis: {design['pairing_basis']}. Two-sided paired t-tests used the recorded within-pair differences.")
        for row in comparisons:
            lines.append(f"{row['group_a']} minus {row['group_b']}: {_count(row, 'complete_pairs')} complete pairs. "
                         "The effect is the mean within-pair difference; its 95% CI uses the paired-difference standard error and t distribution.")
    else:
        lines.append("Independent groups were compared by two-sided Welch t-tests without an equal-variance assumption. "
                     "Effects are differences between independent-unit means in the declared A minus B direction. "
                     "Difference 95% CIs use the Welch standard error and Welch–Satterthwaite degrees of freedom.")
    lines.append("Displayed group-mean 95% CIs use the standard error across independent units and Student t with n−1 degrees of freedom. "
                 "Group-mean and contrast intervals are pointwise, not simultaneous or multiplicity-adjusted.")
    lines.append(f"Holm correction covered the complete declared family {family['family_id']}: "
                 + "; ".join(f"{a} minus {b}" for a, b in family["contrasts"]) + ".")
    lines.extend([
        f"Recorded acquisition comparison basis: {result['acquisition']['review']['basis']}; researcher-confirmed, not machine-verified. "
        "No normalization or batch adjustment was applied.",
        "Explicit exclusions and unavailable outcomes remain in the source, observation, unit and pair ledgers. "
        "Unresolved failures, unexcluded units without outcomes and incomplete pairs were not silently omitted. "
        "Missingness was not assumed random; excluded failed-field observation counts remain unknown.",
        "Full values, test results and audit records are retained in figure-data.json and the accompanying plot-data, source-fields, "
        "observations, field-summary, sample-summary, experimental-units, unit-ledger, comparisons and applicable pair/missingness CSVs. "
        "File hashes are recorded in the source JSON and export manifest.",
        f"Source revision: {result['revision_id']}; source fingerprint: {result['source_fingerprint']}.",
        "Original acquisition details and biological suitability require researcher review; absent facts are not inferred.",
        "Warnings: " + "; ".join(result["warnings"]), "",
    ])
    return "\n".join(lines)
