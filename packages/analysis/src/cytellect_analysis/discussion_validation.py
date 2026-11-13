"""Local checks of a model-drafted result discussion (requirements AC-05, AC-06).

A draft is shown only when every number it states is one of the saved result's numbers, and when it
claims no significance, no proof, no "no change" and no literature the result does not support. A
draft that fails is not shown at all; the computed result is never affected (AC-07).
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Literal

from pydantic import ValidationError

from .discussion_contracts import (
    DISCUSSION_PROMPT_VERSION,
    DiscussionContext,
    DiscussionDraft,
    ValidatedDiscussion,
)


class DiscussionRejected(ValueError):
    def __init__(self, codes: list[str]):
        super().__init__(",".join(codes))
        self.codes = codes


def context_sha256(context: DiscussionContext) -> str:
    canonical = json.dumps(context.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# A number in prose: not part of a name such as PLK1, 5-EU, U2OS, H2B or 18S (letters or a hyphen and letter next
# to it). Thousands separators and an exponent belong to the number; a partial match of a longer number is refused.
_NUMBER = re.compile(r"(?<![A-Za-z0-9.,\-])([+\-−]?\d+(?:,\d{3})*(?:[.,]\d+)?(?:[eE][+\-−]?\d+)?)(?![A-Za-z0-9]|[.,]\d|-[A-Za-z])")
# A unit written against its number (50nM, 24h, 3x) leaves the number a stated value, unlike a name (18S, 3T3).
_UNIT = re.compile(r"(?<=\d)(?=(?:[nµμumpfk]?[Mm]|[nµμumk]?[gGlL]|kDa|Da|bp|kb|px|hrs?|h|min|sec|fold|x)(?![A-Za-z]))")
_LINKS = re.compile(r"(https?://|www\.|doi\s*[:.]|\bPMID\b|\bet al\b|```|<\s*script)", re.IGNORECASE)
# Claims a descriptive result cannot carry, and words that turn "not clear" into "no change" (S-07).
_SIGNIFICANCE = re.compile(r"(有意|証明|実証|立証|確立|示された|明らかになった|確認された)")
_NO_CHANGE = re.compile(r"(変化がない|変化はない|変化しない|変わらない|影響しない|影響はない|影響がない|差がない|差はない|同等である)")


# Counting words (2 つの対照, 3 種類) are not values of the result.
_COUNTED = re.compile(r"(?<![\d.,])\d+\s*(つ|群|種類|種|点|段階|番目|通り)")
# A count of runs (3 回中 2 回): never more than the runs or units the result holds.
_RUNS = re.compile(r"(?<![\d.,])(\d+)\s*回(?!目)")


def _text_numbers(text: str, runs: int = 0) -> list[float]:
    """The numbers a sentence states. `runs`: counts of runs up to this many are not values of their own."""
    text = _UNIT.sub(" ", text.replace("，", ","))
    if runs:
        text = _RUNS.sub(lambda match: "" if int(match.group(1)) <= runs else match.group(0), text)
    values = []
    for match in _NUMBER.finditer(_COUNTED.sub("", text)):
        token = match.group(1).replace("−", "-").replace(",", "")
        try:
            values.append(float(token))
        except ValueError:
            continue
    return values


def allowed_numbers(context: DiscussionContext) -> list[float]:
    """Every number the result states, and the forms the summary writes them in (%, points, fold, counts)."""
    result = context.result
    # 0 is the reference every difference is read against ("区間が 0 を含む"), not a value of its own.
    values: list[float] = [0.0, result.n_control, result.n_treatment, len(result.runs), 95.0]
    if result.n_runs is not None:
        values.append(result.n_runs)
    if result.p_value is not None:
        values += [result.p_value, 0.05, 0.001]
    if result.effect is not None:
        values.append(result.effect)
    percent = result.scale == "fraction"
    for group in result.groups:
        if group.mean is not None:
            values += [group.mean, group.mean * 100] if percent else [group.mean]
    for interval in (result.difference, result.ratio):
        if interval is not None:
            values += [interval.estimate, interval.ci_low, interval.ci_high]
    if result.ratio is not None:
        values += [(value - 1) * 100 for value in (result.ratio.estimate, result.ratio.ci_low, result.ratio.ci_high)]
    for run in result.runs:
        values += [run.control, run.treatment, run.difference]
        if percent:
            # A fraction's unit values are fractions, stated as percentages; its difference is already in points.
            values += [run.control * 100, run.treatment * 100]
        if run.ratio is not None:
            values += [run.ratio, (run.ratio - 1) * 100]
    if result.heading:
        values += _text_numbers(result.heading)
    # What the researcher wrote (a dose, a time) may be repeated.
    for text in (context.experiment.purpose or "", context.experiment.cells or "", *context.experiment.stains):
        values += _text_numbers(text)
    return [value for value in values if math.isfinite(value)]


def _known(value: float, allowed: list[float]) -> bool:
    """A stated number matches a saved one only as that value or as it is rounded for reading.

    Accepted forms: the value within 5 % (two significant digits), or the value rounded to 1–3 significant digits
    or to 0–3 decimals. There is no absolute tolerance, so a small number (a p value, an effect near 0) never
    matches another small number it was not rounded from; 0 matches only 0.
    """
    stated = abs(value)
    for candidate in allowed:
        saved = abs(candidate)
        if saved == 0:
            if stated == 0:
                return True
            continue
        if math.isclose(stated, saved, rel_tol=0.05):
            return True
        if any(stated == float(f"{saved:.{digits}g}") for digits in (1, 2, 3)):
            return True
        if any(stated == round(saved, decimals) and stated != 0 for decimals in (0, 1, 2, 3)):
            return True
    return False


def _unclear(context: DiscussionContext) -> bool:
    """Whether the result cannot carry "no change": nothing was tested, an interval includes no difference
    (0 for a difference, 1 for a ratio), or the test gave p of at least 0.05 (or none)."""
    result = context.result
    if result.test == "none":
        return True
    if result.difference is not None and result.difference.ci_low <= 0 <= result.difference.ci_high:
        return True
    if result.ratio is not None and result.ratio.ci_low <= 1 <= result.ratio.ci_high:
        return True
    return result.p_value is None or result.p_value >= 0.05


def validate_discussion(raw: object, context: DiscussionContext, *, model: str,
                        prompt_version: str = DISCUSSION_PROMPT_VERSION,
                        origin: Literal["model", "example"] = "model") -> ValidatedDiscussion:
    """Check a draft against the result it discusses; raise `DiscussionRejected` with reason codes."""
    try:
        draft = raw if isinstance(raw, DiscussionDraft) else DiscussionDraft.model_validate(raw)
    except ValidationError:
        raise DiscussionRejected(["discussion_schema_invalid"]) from None
    items = [*draft.implications, *draft.alternatives, *draft.next_steps]
    codes: list[str] = []
    allowed = allowed_numbers(context)
    result = context.result
    runs = max(len(result.runs), result.n_runs or 0, result.n_control, result.n_treatment)
    if any(not _known(value, allowed) for text in items for value in _text_numbers(text, runs)):
        codes.append("discussion_number_not_in_result")
    if any(_LINKS.search(text) for text in items):
        codes.append("discussion_reference_or_link")
    descriptive = context.result.test == "none"
    if (descriptive or _unclear(context)) and any(_SIGNIFICANCE.search(text) for text in items):
        codes.append("discussion_claims_significance")
    if _unclear(context) and any(_NO_CHANGE.search(text) for text in items):
        codes.append("discussion_claims_no_change")
    if codes:
        raise DiscussionRejected(codes)
    return ValidatedDiscussion(context_sha256=context_sha256(context), prompt_version=prompt_version, model=model,
                               origin=origin, draft=draft)
