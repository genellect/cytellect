"""Experiment design 1.0.0 and 1.1.0: groups, independent runs and samples entered before analysis.

The design is an editable record of what the researcher declared. It never
infers groups, runs, samples or independence from file names, folders, dates or
plate labels. `field_metadata` derives the existing per-field metadata
(condition, experimental unit, sample, pair, acquisition date) deterministically,
so the established aggregation (field → sample → independent unit, S02) and the
comparison ledgers are reused unchanged. See docs/methods.md, "Experiment design 1.0.0".

Version 1.1.0 adds declared strata (docs/methods.md, "Experiment design 1.1.0"): the
researcher names the factors and their levels (for example a cell line or a time
point), declares each stratum as one level of every factor, and assigns every field
to one stratum. Nothing is inferred or filled in. Comparisons stay two groups within
one selected stratum; strata are never pooled, compared or modelled as factors.
"""
from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import Discriminator, Field, Tag, TypeAdapter, field_validator, model_validator

from .region_contracts import RegionFieldMetadata
from .regions import Id, RegionModel

VERSION: Literal["1.0.0"] = "1.0.0"
# Short labels keep derived "run · group" and "run · sample" identities within the
# 80-character metadata limit and readable in tables and figure legends.
ShortLabel = Annotated[str, Field(min_length=1, max_length=24)]
IsoDate = Annotated[str, Field(pattern=r"^\d{4}-\d{2}-\d{2}$")]
SEPARATOR = " · "


def _clean(value: str) -> str:
    if not value.strip() or value != value.strip() or any(ord(char) < 32 for char in value) or SEPARATOR.strip() in value:
        raise ValueError("experiment_design_invalid_label")
    return value


class ExperimentGroup(RegionModel):
    id: Id
    label: ShortLabel

    @field_validator("label")
    @classmethod
    def clean_label(cls, value):
        return _clean(value)


class ExperimentRun(RegionModel):
    """One independently performed experiment (seeded, treated and stained separately)."""
    id: Id
    label: ShortLabel
    performed_on: IsoDate | None = None
    acquired_on: IsoDate | None = None

    @field_validator("label")
    @classmethod
    def clean_label(cls, value):
        return _clean(value)


class FieldAssignment(RegionModel):
    group_id: Id
    run_id: Id
    # A coverslip or well within the run; None means the run has one sample per group.
    sample: ShortLabel | None = None
    # Imaging date of this field when it differs from the run's acquisition date.
    acquired_on: IsoDate | None = None

    @field_validator("sample")
    @classmethod
    def clean_sample(cls, value):
        return value if value is None else _clean(value)


class ExperimentDesign(RegionModel):
    version: Literal["1.0.0"] = VERSION
    layout: Literal["single", "pair"]
    groups: Annotated[list[ExperimentGroup], Field(min_length=1, max_length=2)]
    # Required before a pair comparison; drafts may leave it unset.
    control_group_id: Id | None = None
    runs: Annotated[list[ExperimentRun], Field(max_length=50)] = Field(default_factory=list)
    # The researcher's statement that runs were performed independently (E-05).
    independence_confirmed: bool = False
    fields: Annotated[dict[Id, FieldAssignment], Field(max_length=100)] = Field(default_factory=dict)

    @model_validator(mode="after")
    def consistent(self):
        if len(self.groups) != (1 if self.layout == "single" else 2):
            raise ValueError("experiment_design_group_count")
        if self.layout == "single" and self.control_group_id is not None:
            raise ValueError("experiment_design_control_requires_pair")
        groups = {group.id for group in self.groups}
        runs = {run.id for run in self.runs}
        if (len(groups) != len(self.groups) or len(runs) != len(self.runs)
                or len({group.label.casefold() for group in self.groups}) != len(self.groups)
                or len({run.label.casefold() for run in self.runs}) != len(self.runs)):
            raise ValueError("experiment_design_duplicate")
        if self.control_group_id is not None and self.control_group_id not in groups:
            raise ValueError("experiment_design_unknown_group")
        for assignment in self.fields.values():
            if assignment.group_id not in groups:
                raise ValueError("experiment_design_unknown_group")
            if assignment.run_id not in runs:
                raise ValueError("experiment_design_unknown_run")
        return self


class StratumLevel(RegionModel):
    id: Id
    label: ShortLabel

    @field_validator("label")
    @classmethod
    def clean_label(cls, value):
        return _clean(value)


class StratumFactor(RegionModel):
    """A condition the researcher holds constant within each comparison (e.g. cell line)."""
    id: Id
    label: ShortLabel
    levels: Annotated[list[StratumLevel], Field(min_length=1, max_length=12)]

    @field_validator("label")
    @classmethod
    def clean_label(cls, value):
        return _clean(value)


class Stratum(RegionModel):
    """One declared stratum: exactly one level of every factor."""
    id: Id
    label: ShortLabel
    levels: Annotated[dict[Id, Id], Field(min_length=1, max_length=3)]

    @field_validator("label")
    @classmethod
    def clean_label(cls, value):
        return _clean(value)


class StratifiedFieldAssignment(FieldAssignment):
    # The stratum the researcher assigned; None until assigned, never guessed. An unassigned
    # field belongs to no stratum: no cohort takes it and readiness names it.
    stratum_id: Id | None = None


class StratifiedExperimentDesign(RegionModel):
    version: Literal["1.1.0"]
    layout: Literal["single", "pair"]
    groups: Annotated[list[ExperimentGroup], Field(min_length=1, max_length=2)]
    control_group_id: Id | None = None
    runs: Annotated[list[ExperimentRun], Field(max_length=50)] = Field(default_factory=list)
    independence_confirmed: bool = False
    factors: Annotated[list[StratumFactor], Field(min_length=1, max_length=3)]
    # Empty while the researcher is still declaring factors; no cohort can be made until a stratum exists.
    strata: Annotated[list[Stratum], Field(max_length=24)]
    fields: Annotated[dict[Id, StratifiedFieldAssignment], Field(max_length=100)] = Field(default_factory=dict)

    @model_validator(mode="after")
    def consistent(self):
        ExperimentDesign.model_validate({**self.model_dump(mode="json", exclude={"factors", "strata", "fields"}),
                                         "version": "1.0.0", "fields": {}})
        groups = {group.id for group in self.groups}
        runs = {run.id for run in self.runs}
        factors = {factor.id: {level.id for level in factor.levels} for factor in self.factors}
        if (len(factors) != len(self.factors)
                or len({factor.label.casefold() for factor in self.factors}) != len(self.factors)
                or any(len(levels) != len(factor.levels) or len({level.label.casefold() for level in factor.levels}) != len(levels)
                       for factor, levels in zip(self.factors, factors.values(), strict=True))):
            raise ValueError("experiment_design_duplicate")
        strata = {stratum.id for stratum in self.strata}
        if (len(strata) != len(self.strata) or len({stratum.label.casefold() for stratum in self.strata}) != len(self.strata)
                or len({tuple(sorted(stratum.levels.items())) for stratum in self.strata}) != len(self.strata)):
            raise ValueError("experiment_design_duplicate")
        for stratum in self.strata:
            if set(stratum.levels) != set(factors) or any(level not in factors[factor] for factor, level in stratum.levels.items()):
                raise ValueError("experiment_design_stratum_levels")
        for assignment in self.fields.values():
            if assignment.group_id not in groups:
                raise ValueError("experiment_design_unknown_group")
            if assignment.run_id not in runs:
                raise ValueError("experiment_design_unknown_run")
            if assignment.stratum_id is not None and assignment.stratum_id not in strata:
                raise ValueError("experiment_design_unknown_stratum")
        return self


def _design_version(value: Any) -> str:
    version = value.get("version", VERSION) if isinstance(value, dict) else getattr(value, "version", VERSION)
    return "1.1.0" if version == "1.1.0" else "1.0.0"


# 1.0.0 documents (with or without `version`) keep their model and bytes; 1.1.0 adds strata.
AnyExperimentDesign = Annotated[
    Annotated[ExperimentDesign, Tag("1.0.0")] | Annotated[StratifiedExperimentDesign, Tag("1.1.0")],
    Discriminator(_design_version),
]
_ANY_DESIGN: TypeAdapter = TypeAdapter(AnyExperimentDesign)


def parse_design(value) -> ExperimentDesign | StratifiedExperimentDesign:
    return _ANY_DESIGN.validate_python(value)


def field_metadata(design: ExperimentDesign | StratifiedExperimentDesign) -> dict[str, RegionFieldMetadata]:
    """Per-field metadata for the existing comparison ledgers.

    condition = group label; experimental unit = "run · group" (one unit per run
    and group, so independent and paired designs both validate); pair = run label
    (pair layout only); sample = "run · sample", or the unit when the run has one
    sample per group; acquisition date = the field's imaging date, else the run's.
    """
    groups = {group.id: group for group in design.groups}
    runs = {run.id: run for run in design.runs}
    derived = {}
    for field_id, assignment in sorted(design.fields.items()):
        group, run = groups[assignment.group_id], runs[assignment.run_id]
        unit = f"{run.label}{SEPARATOR}{group.label}"
        derived[field_id] = RegionFieldMetadata(
            condition=group.label,
            experimental_unit=unit,
            sample=unit if assignment.sample is None else f"{run.label}{SEPARATOR}{assignment.sample}",
            acquisition_date=assignment.acquired_on or run.acquired_on,
            pair=run.label if design.layout == "pair" else None,
        )
    return derived


def readiness(design: ExperimentDesign | StratifiedExperimentDesign, registered_field_ids) -> list[dict]:
    """Issues to resolve before inference, in a stable order (E-05, E-06).

    Description (1 screen, S09) never waits for these issues.
    """
    registered = set(registered_field_ids)
    runs_by_id = {run.id: run for run in design.runs}
    issues = []
    unassigned = sorted(registered - set(design.fields))
    if unassigned:
        issues.append({"code": "experiment_design_unassigned_fields", "field_ids": unassigned})
    unknown = sorted(set(design.fields) - registered)
    if unknown:
        issues.append({"code": "experiment_design_unknown_fields", "field_ids": unknown})
    if not design.runs:
        issues.append({"code": "experiment_design_no_runs"})
    if design.layout == "pair" and design.control_group_id is None:
        issues.append({"code": "experiment_design_control_required"})
    if isinstance(design, StratifiedExperimentDesign):
        unstratified = sorted(fid for fid, a in design.fields.items() if fid in registered and a.stratum_id is None)
        if not design.strata:
            issues.append({"code": "experiment_design_no_strata"})
        if unstratified:
            issues.append({"code": "experiment_design_unstratified_fields", "field_ids": unstratified})
        # Within each stratum, every run that appears there needs both groups (strata are never pooled).
        for stratum in design.strata:
            within = {(a.run_id, a.group_id) for fid, a in design.fields.items()
                      if fid in registered and a.stratum_id == stratum.id}
            if not within:
                issues.append({"code": "experiment_design_empty_stratum", "stratum_id": stratum.id})
            for run in design.runs:
                if not any(run_id == run.id for run_id, _ in within):
                    continue
                missing = [group.id for group in design.groups if (run.id, group.id) not in within]
                if missing:
                    issues.append({"code": "experiment_design_missing_combination", "run_id": run.id,
                                   "group_ids": missing, "stratum_id": stratum.id})
    else:
        present = {(a.run_id, a.group_id) for fid, a in design.fields.items() if fid in registered}
        for run in design.runs:
            missing = [group.id for group in design.groups if (run.id, group.id) not in present]
            if missing:
                issues.append({"code": "experiment_design_missing_combination", "run_id": run.id, "group_ids": missing})
    undated = sorted(fid for fid, a in design.fields.items()
                     if fid in registered and not (a.acquired_on or runs_by_id[a.run_id].acquired_on))
    if undated:
        # Intensities need actual acquisition dates (S10); areas and counts do not.
        issues.append({"code": "experiment_design_acquisition_dates_missing", "field_ids": undated})
    if not design.independence_confirmed:
        issues.append({"code": "experiment_design_independence_unconfirmed"})
    return issues


def comparison_defaults(design: ExperimentDesign | StratifiedExperimentDesign) -> dict:
    """Default pair comparison: paired by run, effect reported as treatment − control.

    Existing comparison contrasts are `[a, b]` with effect `a − b`, so the
    treatment comes first. The caller must still confirm the design (S10).
    """
    if design.layout != "pair" or design.control_group_id is None:
        raise ValueError("experiment_design_control_required")
    control = next(group for group in design.groups if group.id == design.control_group_id)
    treatment = next(group for group in design.groups if group.id != design.control_group_id)
    return {"conditions": [control.label, treatment.label], "control": control.label, "treatment": treatment.label,
            "contrasts": [[treatment.label, control.label]], "design": "paired",
            "pairing_basis": "control and treatment from the same independent experimental run"}

