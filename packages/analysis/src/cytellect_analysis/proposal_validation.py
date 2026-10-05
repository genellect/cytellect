"""Local semantic validation of model-drafted proposals (requirement L02).

A draft that passes is still only a proposal: adoption is a separate explicit
action, and actual channel, background, acquisition and independence
confirmations remain the researcher's.
"""
import hashlib
import json
import re

from pydantic import ValidationError

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


class ProposalRejected(ValueError):
    def __init__(self, codes: list[str]):
        super().__init__(",".join(codes))
        self.codes = codes


def context_sha256(context: ProposalContext) -> str:
    canonical = json.dumps(context.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _texts(draft: ProposalDraft) -> list[str]:
    return [draft.rationale, *draft.missing_information, *(channel.reason for channel in draft.channels)]


def validate_draft(context: ProposalContext, raw: object, *, model: str, prompt_version: str) -> ValidatedProposal:
    try:
        draft = ProposalDraft.model_validate(raw)
    except ValidationError:
        raise ProposalRejected(["proposal_shape_invalid"]) from None
    codes: list[str] = []
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
        if actual.stain is None and channel.role != "unused":
            needs_confirmation.append(channel.token)
    nuclear = [token for token, role in roles.items() if role == "nuclear"]
    ncl = {token for token, channel in known.items() if channel.stain and channel.stain.casefold() in NCL_STAINS}
    if draft.recipe in ("nuclear-intensity", "nuclear-ncl") and len(nuclear) != 1:
        codes.append("proposal_one_nuclear_channel_required")
    if draft.recipe == "nuclear-ncl" and not any(roles.get(token) == "measure" for token in ncl):
        codes.append("proposal_ncl_channel_not_acquired")
    if draft.recipe == "supplied-regions" and not context.supplied_regions:
        codes.append("proposal_supplied_regions_absent")
    if draft.recipe == "measured-table" and not context.measured_table:
        codes.append("proposal_measured_table_absent")
    proposed = set()
    for metric in draft.metrics:
        proposed.add((metric.metric, metric.channel))
        if metric.metric in INTENSITY_METRICS:
            if metric.channel is None or roles.get(metric.channel) != "measure":
                codes.append("proposal_metric_channel_invalid")
            if metric.metric.endswith("_corrected") and not context.background_available:
                codes.append("proposal_background_not_available")
        elif metric.metric in NCL_METRICS:
            if draft.recipe != "nuclear-ncl" or metric.channel not in ncl:
                codes.append("proposal_ncl_metric_invalid")
        elif metric.channel is not None:
            codes.append("proposal_metric_channel_invalid")
    statistics = draft.statistics
    if statistics.kind == "descriptive":
        if statistics.test or statistics.omnibus or statistics.association:
            codes.append("proposal_descriptive_has_test")
    elif not context.units_known:
        # Cells and fields never become independent replicates.
        codes.append("proposal_units_required")
    if statistics.kind == "comparison":
        paired = statistics.test in ("paired-t", "wilcoxon")
        if statistics.test is None or statistics.association is not None or context.condition_count < 2:
            codes.append("proposal_comparison_invalid")
        if paired and not context.pairing_known:
            codes.append("proposal_pairing_required")
        if paired and statistics.omnibus is not None:
            codes.append("proposal_omnibus_design_mismatch")
        if not paired and context.condition_count >= 3:
            expected = {"welch-t": "welch-anova", "mann-whitney-u": "kruskal-wallis"}.get(statistics.test or "")
            if statistics.omnibus != expected:
                codes.append("proposal_omnibus_required")
        if not paired and context.condition_count < 3 and statistics.omnibus is not None:
            codes.append("proposal_omnibus_design_mismatch")
    if statistics.kind == "association" and (statistics.association is None or statistics.test or statistics.omnibus):
        codes.append("proposal_association_invalid")
    for figure in draft.figures:
        if (figure.metric, figure.channel) not in proposed:
            codes.append("proposal_figure_metric_not_proposed")
        if figure.kind == "unit-comparison" and statistics.kind != "comparison":
            codes.append("proposal_figure_design_mismatch")
        if figure.kind == "paired" and statistics.test not in ("paired-t", "wilcoxon"):
            codes.append("proposal_figure_design_mismatch")
        if figure.kind == "association-scatter" and statistics.kind != "association":
            codes.append("proposal_figure_design_mismatch")
    if len(set(draft.reference_ids)) != len(draft.reference_ids):
        codes.append("proposal_reference_duplicate")
    if any(FORBIDDEN_TEXT.search(text) for text in _texts(draft)):
        codes.append("proposal_text_not_allowed")
    if codes:
        raise ProposalRejected(sorted(set(codes)))
    return ValidatedProposal(draft=draft, needs_confirmation=needs_confirmation, model=model,
                             prompt_version=prompt_version, context_sha256=context_sha256(context))
