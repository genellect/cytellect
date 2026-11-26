"""Local semantic validation of model-drafted proposals (requirement L02).

A draft that passes is still only a proposal: adoption is a separate explicit
action, and actual channel, background, acquisition and independence
confirmations remain the researcher's.
"""
import hashlib
import json
import re

from pydantic import ValidationError

from .experiment_design import _clean as _clean_label
from .proposal_contracts import (
    INTENSITY_METRICS,
    NCL_METRICS,
    ProposalContext,
    ProposalDraft,
    ValidatedProposal,
)

NCL_STAINS = frozenset({"ncl", "nucleolin"})
# Text fields are explanations only; anything executable or remote is refused.
FORBIDDEN_TEXT = re.compile(
    r"(https?://|www\.|```|<\s*script|\beval\s*\(|\bexec\s*\(|\bimport\s+\w|\bdef\s+\w+\s*\(|run\s*\(\s*\"|"
    r"\bmacro\b|\bsubprocess\b|\bos\.system\b|javascript:)", re.IGNORECASE)


# Every reason a draft can be refused for (#284 W2): the workspace maps each to a place the researcher can
# change or to a service-side failure, and a test keeps this list and the checks below in step.
REJECTION_CODES: frozenset[str] = frozenset({
    "proposal_acquisition_dates_required",
    "proposal_answer_has_settings",
    "proposal_answer_missing",
    "proposal_assignment_duplicate",
    "proposal_assignment_field_unknown",
    "proposal_assignment_group_invalid",
    "proposal_assignment_label_invalid",
    "proposal_association_axes_identical",
    "proposal_association_axes_required",
    "proposal_association_axes_unexpected",
    "proposal_association_invalid",
    "proposal_association_same_region_required",
    "proposal_background_not_available",
    "proposal_channels_mismatch",
    "proposal_choice_invalid",
    "proposal_comparison_invalid",
    "proposal_descriptive_has_test",
    "proposal_design_requires_paired",
    "proposal_figure_analysis_invalid",
    "proposal_figure_association_axis_mismatch",
    "proposal_figure_design_mismatch",
    "proposal_figure_metric_not_proposed",
    "proposal_gfp_channel_not_established",
    "proposal_gfp_controls_not_registered",
    "proposal_images_not_registered",
    "proposal_independent_units_insufficient",
    "proposal_measured_table_absent",
    "proposal_measurements_required",
    "proposal_metric_channel_invalid",
    "proposal_metric_duplicate",
    "proposal_metric_region_invalid",
    "proposal_metric_region_required",
    "proposal_model_not_selected",
    "proposal_model_selection_changed",
    "proposal_ncl_channel_not_acquired",
    "proposal_ncl_metric_invalid",
    "proposal_none_has_analysis",
    "proposal_omnibus_design_mismatch",
    "proposal_omnibus_required",
    "proposal_one_nuclear_channel_required",
    "proposal_paired_condition_count_unsupported",
    "proposal_pairing_required",
    "proposal_processing_cell_channel_invalid",
    "proposal_processing_marker_not_established",
    "proposal_processing_ncl_channel_invalid",
    "proposal_processing_nuclear_channel_invalid",
    "proposal_processing_nucleoli_channel_invalid",
    "proposal_processing_nucleoli_recipe_invalid",
    "proposal_processing_recipe_invalid",
    "proposal_processing_signal_channel_invalid",
    "proposal_reference_duplicate",
    "proposal_role_conflicts_with_user",
    "proposal_run_requires_analysis",
    "proposal_scope_required",
    "proposal_shape_invalid",
    "proposal_stain_changed",
    "proposal_stain_not_established",
    "proposal_supplied_regions_absent",
    "proposal_text_not_allowed",
    "proposal_units_required",
})


class ProposalRejected(ValueError):
    """A refused draft. When the draft was well formed and its text passed the text check, the answer it wrote
    (`answer`, `rationale`, `missing_information`) travels with the codes so the researcher still reads it (#284 W2,
    W7); the settings it proposed are never applied."""

    def __init__(self, codes: list[str], rationale: str | None = None, missing_information: tuple[str, ...] = (),
                 answer: str | None = None):
        super().__init__(",".join(codes))
        self.codes = codes
        self.rationale = rationale
        self.missing_information = missing_information
        self.answer = answer


# What a question's answer may hold (#284 W7, finding 14): its text, the items to confirm and assignment suggestions.
# Everything below is a setting, so an answer leaves it empty; any other answer is accepted.
CHOICE_LIMIT, OPTION_LIMIT = 4, 6
QUESTION_CHARS, OPTION_CHARS, LABEL_CHARS = 200, 80, 24


def reply_text(draft: ProposalDraft) -> str:
    """The answer as the researcher reads it: the direct answer, the reasoning, then each item still to provide."""
    return "\n".join(text.strip() for text in [draft.answer or "", draft.rationale, *draft.missing_information]
                     if text and text.strip())


def _carries_settings(context: ProposalContext, draft: ProposalDraft) -> bool:
    known = {channel.token: channel for channel in context.channels}
    statistics = draft.statistics
    changed_channel = any(
        channel.token not in known
        or (channel.stain is not None and channel.stain.casefold() != (known[channel.token].stain or "").casefold())
        or (channel.role != "unused" and channel.role != known[channel.token].role)
        for channel in draft.channels)
    return bool(draft.recipe != "none" or draft.metrics or draft.figures or draft.additional_analyses
                or statistics.kind != "descriptive" or statistics.test or statistics.omnibus or statistics.association
                or statistics.x is not None or statistics.y is not None or draft.processing is not None
                or draft.background is not None or draft.gfp_selection is not None
                or draft.figure_presentation is not None or changed_channel)


def _label_valid(value: str) -> bool:
    try:
        _clean_label(value)
    except ValueError:
        return False
    return len(value) <= LABEL_CHARS


def _request_codes(context: ProposalContext, draft: ProposalDraft) -> list[str]:
    """Checks of the kind of request, its choices and its assignment suggestions (#284 W7)."""
    codes: list[str] = []
    if draft.intent == "run":
        if draft.scope is None:
            codes.append("proposal_scope_required")
        if draft.recipe == "none":
            codes.append("proposal_run_requires_analysis")
    if len(draft.choices) > CHOICE_LIMIT or any(
            not choice.question.strip() or len(choice.question) > QUESTION_CHARS
            or not 2 <= len(choice.options) <= OPTION_LIMIT
            or any(not option.strip() or len(option) > OPTION_CHARS or "\n" in option for option in choice.options)
            or len({option.strip().casefold() for option in choice.options}) != len(choice.options)
            for choice in draft.choices):
        codes.append("proposal_choice_invalid")
    if draft.assignments:
        fields = {field.id for field in context.fields if field.id}
        named = [assignment.field for assignment in draft.assignments]
        if any(field not in fields for field in named):
            codes.append("proposal_assignment_field_unknown")
        if len(set(named)) != len(named):
            codes.append("proposal_assignment_duplicate")
        if not all(_label_valid(assignment.run) and _label_valid(assignment.group) for assignment in draft.assignments):
            codes.append("proposal_assignment_label_invalid")
        # As many groups as the design holds (two without one): the workspace places them by name, or names the
        # design's groups after them when none matches (W6's 「案を適用」).
        groups = {assignment.group.casefold() for assignment in draft.assignments}
        if len(groups) > (len(context.design.groups) if context.design else 2):
            codes.append("proposal_assignment_group_invalid")
    return codes


def context_sha256(context: ProposalContext) -> str:
    canonical = json.dumps(context.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _texts(draft: ProposalDraft) -> list[str]:
    return [draft.rationale, *draft.missing_information, *(channel.reason for channel in draft.channels),
            draft.answer or "", *(choice.question for choice in draft.choices),
            *(option for choice in draft.choices for option in choice.options),
            *(label for assignment in draft.assignments for label in (assignment.run, assignment.group))]


def _refuse(draft: ProposalDraft, codes: list[str]):
    """Raises the refusal, with the draft's text when that text passed the text check."""
    if "proposal_text_not_allowed" in codes:
        raise ProposalRejected(sorted(set(codes)))
    raise ProposalRejected(sorted(set(codes)), draft.rationale, tuple(draft.missing_information), draft.answer)


def _validate_answer(context: ProposalContext, draft: ProposalDraft, *, model: str, prompt_version: str) -> ValidatedProposal:
    """A question's answer (#284 W7): valid whatever the workspace holds, unless it carries a setting."""
    codes = _request_codes(context, draft)
    if _carries_settings(context, draft):
        codes.append("proposal_answer_has_settings")
    if not reply_text(draft):
        codes.append("proposal_answer_missing")
    if len(set(draft.reference_ids)) != len(draft.reference_ids):
        codes.append("proposal_reference_duplicate")
    if any(FORBIDDEN_TEXT.search(text) for text in _texts(draft)):
        codes.append("proposal_text_not_allowed")
    if codes:
        _refuse(draft, codes)
    return ValidatedProposal(draft=draft, needs_confirmation=[], model=model, prompt_version=prompt_version,
                             context_sha256=context_sha256(context))


def validate_draft(context: ProposalContext, raw: object, *, model: str, prompt_version: str) -> ValidatedProposal:
    try:
        draft = ProposalDraft.model_validate(raw)
    except ValidationError:
        raise ProposalRejected(["proposal_shape_invalid"]) from None
    if draft.intent == "answer":
        return _validate_answer(context, draft, model=model, prompt_version=prompt_version)
    codes: list[str] = _request_codes(context, draft)
    if context.field_count == 0 and (
        draft.recipe != "none" or draft.channels or draft.metrics or draft.figures
        or draft.additional_analyses or draft.statistics.kind != "descriptive"
        or draft.background is not None or draft.gfp_selection is not None or not draft.missing_information
    ):
        codes.append("proposal_images_not_registered")
    known = {channel.token: channel for channel in context.channels}
    tokens = [channel.token for channel in draft.channels]
    if sorted(tokens) != sorted(known):
        codes.append("proposal_channels_mismatch")
    roles = {channel.token: channel.role for channel in draft.channels}
    needs_confirmation: list[str] = []
    for channel in draft.channels:
        actual = known.get(channel.token)
        if actual is None:
            continue
        if actual.stain is None and channel.stain is not None:
            # Index tokens, colour or morphology never establish a stain.
            codes.append("proposal_stain_not_established")
        if actual.stain is not None and channel.stain is not None and channel.stain.casefold() != actual.stain.casefold():
            codes.append("proposal_stain_changed")
        if actual.role is not None and channel.role != actual.role and channel.role != "unused":
            codes.append("proposal_role_conflicts_with_user")
        if actual.role is None and channel.role == "nuclear":
            # Only a new detector-defining role requires confirmation. Unknown
            # marker identity never blocks generic raw intensity measurements.
            needs_confirmation.append(channel.token)
    nuclear = [token for token, role in roles.items() if role == "nuclear"]
    ncl = {token for token, channel in known.items() if channel.stain and channel.stain.casefold() in NCL_STAINS}
    if draft.recipe in ("nuclear-intensity", "nuclear-ncl") and len(nuclear) != 1:
        codes.append("proposal_one_nuclear_channel_required")
    if draft.recipe == "nuclear-ncl" and not any(roles.get(token) == "measure" for token in ncl):
        codes.append("proposal_ncl_channel_not_acquired")
    cell_processing = bool(draft.processing and draft.processing.cells)
    if draft.recipe == "supplied-regions" and not context.supplied_regions and not cell_processing:
        codes.append("proposal_supplied_regions_absent")
    if draft.recipe == "measured-table" and not context.measured_table:
        codes.append("proposal_measured_table_absent")
    processing = draft.processing
    if processing is not None:
        if draft.recipe not in ("nuclear-intensity", "nuclear-ncl") and not (draft.recipe == "supplied-regions" and cell_processing):
            codes.append("proposal_processing_recipe_invalid")
        if ((draft.recipe in ("nuclear-intensity", "nuclear-ncl") and processing.nuclei is None)
                or (processing.nuclei is not None and processing.nuclei.channel not in nuclear)):
            codes.append("proposal_processing_nuclear_channel_invalid")
        if processing.nucleoli is not None:
            candidate = processing.nucleoli
            current = context.current_processing.nucleoli if context.current_processing else None
            same_scope = current is not None and (
                current.channel == candidate.channel
                and current.detector.engine == candidate.detector.engine
                and current.detector.protocol_version == candidate.detector.protocol_version
            )
            same_model = current is not None and (
                getattr(current.detector, "model", None) == getattr(candidate.detector, "model", None)
                and getattr(current.detector, "model_sha256", None) == getattr(candidate.detector, "model_sha256", None)
            )
            # A follow-up may retain an explicitly selected experimental model,
            # but cannot select one, move it to another channel/protocol, or
            # silently change weights within the same detection method.
            if getattr(candidate.detector, "model", None) in ("ncl-r1-step0375", "ncl-r1-step0750") and not (same_scope and same_model):
                codes.append("proposal_model_not_selected")
            elif same_scope and not same_model:
                codes.append("proposal_model_selection_changed")
            source = getattr(candidate.detector, "source", "ncl")
            actual = known.get(candidate.channel)
            if draft.recipe != "nuclear-ncl":
                codes.append("proposal_processing_nucleoli_recipe_invalid")
            if source == "dapi_poor":
                if candidate.channel not in nuclear:
                    codes.append("proposal_processing_nucleoli_channel_invalid")
            elif roles.get(candidate.channel) != "measure":
                codes.append("proposal_processing_nucleoli_channel_invalid")
            elif source == "ncl" and candidate.channel not in ncl:
                codes.append("proposal_processing_ncl_channel_invalid")
            elif source == "marker" and (actual is None or not actual.stain
                    or actual.stain.casefold() not in {"ubf", "fbl", "fibrillarin"}):
                codes.append("proposal_processing_marker_not_established")
        if processing.signal is not None and roles.get(processing.signal.channel) != "measure":
            codes.append("proposal_processing_signal_channel_invalid")
        if processing.cells is not None and roles.get(processing.cells.channel) != "measure":
            codes.append("proposal_processing_cell_channel_invalid")
    background_mode = draft.background.mode if draft.background else (context.current_background.mode if context.current_background else None)
    background_ready = background_mode == "automatic" or (background_mode != "raw" and context.background_available)
    if draft.background and draft.background.mode == "confirmed_roi" and not context.background_available:
        codes.append("proposal_background_not_available")
    gate = draft.gfp_selection
    if gate is not None:
        acquired = known.get(gate.channel)
        if acquired is None or (acquired.stain or "").casefold() not in {"gfp", "egfp"}:
            codes.append("proposal_gfp_channel_not_established")
        if gate.unit == "nucleus" and len(nuclear) != 1:
            codes.append("proposal_one_nuclear_channel_required")
        if gate.unit == "cell_roi" and not context.supplied_regions and not cell_processing:
            codes.append("proposal_supplied_regions_absent")
        if gate.method == "negative_control" and not context.negative_control_fields_known:
            codes.append("proposal_gfp_controls_not_registered")
        if gate.method == "batch_otsu" and not context.acquired_dates_known:
            codes.append("proposal_acquisition_dates_required")
        if gate.values == "corrected" and not background_ready:
            codes.append("proposal_background_not_available")
    proposed = set()
    for metric in draft.metrics:
        identity = (metric.metric, metric.channel, metric.region)
        if identity in proposed:
            codes.append("proposal_metric_duplicate")
        proposed.add(identity)
        if metric.region in ("nucleoli", "nucleoplasm") and draft.recipe != "nuclear-ncl":
            codes.append("proposal_metric_region_invalid")
        if metric.region == "supplied" and draft.recipe != "supplied-regions":
            codes.append("proposal_metric_region_invalid")
        if metric.region == "nucleus" and draft.recipe not in ("nuclear-intensity", "nuclear-ncl"):
            codes.append("proposal_metric_region_invalid")
        if metric.metric in INTENSITY_METRICS or metric.metric == "area":
            if metric.region is None:
                codes.append("proposal_metric_region_required")
        if metric.metric in INTENSITY_METRICS:
            if metric.channel is None or roles.get(metric.channel) != "measure":
                codes.append("proposal_metric_channel_invalid")
            if metric.metric.endswith("_corrected") and not background_ready:
                codes.append("proposal_background_not_available")
        elif metric.metric in NCL_METRICS:
            if draft.recipe != "nuclear-ncl" or metric.channel not in ncl:
                codes.append("proposal_ncl_metric_invalid")
            if metric.metric == "ncl_log2_nucleoplasm_over_nucleoli" and not background_ready:
                codes.append("proposal_background_not_available")
        elif metric.channel is not None:
            codes.append("proposal_metric_channel_invalid")
    analyses = [draft.statistics, *draft.additional_analyses]
    for statistics in analyses:
        if statistics.kind == "descriptive":
            if statistics.test or statistics.omnibus or statistics.association:
                codes.append("proposal_descriptive_has_test")
        elif not context.units_known:
            # Cells and fields never become independent replicates.
            codes.append("proposal_units_required")
        if statistics.kind != "association" and (statistics.x is not None or statistics.y is not None):
            codes.append("proposal_association_axes_unexpected")
        if statistics.kind == "comparison":
            paired = statistics.test in ("paired-t", "wilcoxon")
            if statistics.test is None or statistics.association is not None or context.condition_count < 2:
                codes.append("proposal_comparison_invalid")
            if paired and not context.pairing_known:
                codes.append("proposal_pairing_required")
            if not paired and context.pairing_known:
                codes.append("proposal_design_requires_paired")
            if paired and context.complete_pair_count < 2:
                codes.append("proposal_independent_units_insufficient")
            if not paired and (len(context.units_per_condition) != context.condition_count
                               or any(count < 2 for count in context.units_per_condition)):
                codes.append("proposal_independent_units_insufficient")
            # A paired test has two explicitly identified conditions. Multi-condition
            # repeated-measures designs cannot be represented by this protocol.
            if paired and context.condition_count != 2:
                codes.append("proposal_paired_condition_count_unsupported")
            if paired and statistics.omnibus is not None:
                codes.append("proposal_omnibus_design_mismatch")
            if not paired and context.condition_count >= 3:
                expected = {"welch-t": "welch-anova", "mann-whitney-u": "kruskal-wallis"}.get(statistics.test or "")
                if statistics.omnibus != expected:
                    codes.append("proposal_omnibus_required")
            if not paired and context.condition_count < 3 and statistics.omnibus is not None:
                codes.append("proposal_omnibus_design_mismatch")
        if statistics.kind == "association":
            if not context.units_per_condition or any(count < 3 for count in context.units_per_condition):
                codes.append("proposal_independent_units_insufficient")
            if statistics.association is None or statistics.test or statistics.omnibus:
                codes.append("proposal_association_invalid")
            axes = [statistics.x, statistics.y]
            if any(axis is None or (axis.metric, axis.channel, axis.region) not in proposed for axis in axes):
                codes.append("proposal_association_axes_required")
            if statistics.x is not None and statistics.x == statistics.y:
                codes.append("proposal_association_axes_identical")
            if (statistics.x is not None and statistics.y is not None
                    and (statistics.x.region is None or statistics.y.region is None
                         or statistics.x.region != statistics.y.region)):
                codes.append("proposal_association_same_region_required")
    for figure in draft.figures:
        if (figure.metric, figure.channel, figure.region) not in proposed:
            codes.append("proposal_figure_metric_not_proposed")
        if figure.analysis_index >= len(analyses):
            codes.append("proposal_figure_analysis_invalid")
            continue
        statistics = analyses[figure.analysis_index]
        if figure.kind == "unit-comparison" and statistics.kind != "comparison":
            codes.append("proposal_figure_design_mismatch")
        if figure.kind == "paired" and statistics.test not in ("paired-t", "wilcoxon"):
            codes.append("proposal_figure_design_mismatch")
        if figure.kind == "association-scatter" and statistics.kind != "association":
            codes.append("proposal_figure_design_mismatch")
        if figure.kind == "association-scatter" and statistics.y is not None:
            if (figure.metric, figure.channel, figure.region) != (
                    statistics.y.metric, statistics.y.channel, statistics.y.region):
                codes.append("proposal_figure_association_axis_mismatch")
    if draft.recipe == "none" and (draft.metrics or draft.figures or any(s.kind != "descriptive" for s in analyses)):
        codes.append("proposal_none_has_analysis")
    if draft.recipe != "none" and not draft.metrics:
        codes.append("proposal_measurements_required")
    if len(set(draft.reference_ids)) != len(draft.reference_ids):
        codes.append("proposal_reference_duplicate")
    if any(FORBIDDEN_TEXT.search(text) for text in _texts(draft)):
        codes.append("proposal_text_not_allowed")
    if codes:
        _refuse(draft, codes)
    return ValidatedProposal(draft=draft, needs_confirmation=needs_confirmation, model=model,
                             prompt_version=prompt_version, context_sha256=context_sha256(context))
