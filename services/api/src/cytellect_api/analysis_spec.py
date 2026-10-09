"""Persistent editable analysis intent; saving a draft never executes or adopts results."""
from typing import Annotated, Literal

from cytellect_analysis.common_statistics_contracts import AssociationPlot, CommonComparisonPlot
from cytellect_analysis.descriptive_contracts import GfpFilter, LegacyMetric, RegionMetric
from cytellect_analysis.proposal_contracts import (
    DraftCellProcessing,
    DraftFigure,
    DraftMetric,
    DraftNuclearProcessing,
    DraftNucleolarProcessing,
    DraftSignalProcessing,
    DraftStatistics,
    MetricId,
)
from cytellect_analysis.region_contracts import RegionBackground, RegionFieldMetadata
from cytellect_analysis.region_policy import AutomaticBackgroundPolicy, RawIntensityPolicy
from cytellect_analysis.regions import Id, Label, RegionModel
from fastapi import Depends, HTTPException
from pydantic import Field, FiniteFloat, model_validator
from sqlalchemy import select

from .channel_assignments import assignments_at
from .db import fields, workspace_analysis_specs


class NucleolarDefinitionDraft(RegionModel):
    source: Literal["dapi_poor", "marker", "ncl"] = "dapi_poor"
    marker: Annotated[str, Field(max_length=80, pattern=r"^[A-Za-z0-9_-]*$")] = ""
    pixelUm: Annotated[FiniteFloat, Field(gt=0)] | None = None
    relative: Annotated[FiniteFloat, Field(gt=0, lt=1)] = 0.7
    algorithm: Literal["cellpose", "objects", "legacy"] | None = None


class CellDefinitionDraft(RegionModel):
    source: Literal["manual", "cellpose"] = "manual"
    channel: Annotated[str, Field(max_length=80, pattern=r"^[A-Za-z0-9_-]*$")] = ""


class RuntimeSettingsDraft(RegionModel):
    """Names deliberately match the workspace runtime; null keeps versioned detector defaults."""
    nuclearMaxSide: Annotated[int, Field(ge=64, le=2048)] | None = None
    nuclearProbability: Annotated[FiniteFloat, Field(ge=0, le=1)] = 0.5
    nuclearNms: Annotated[FiniteFloat, Field(ge=0, le=1)] = 0.3
    nucleolarDefinition: NucleolarDefinitionDraft = Field(default_factory=NucleolarDefinitionDraft)
    cellDefinition: CellDefinitionDraft = Field(default_factory=CellDefinitionDraft)
    nucleolarSigma: Annotated[FiniteFloat, Field(ge=0, le=20)] | None = None
    nucleolarRim: Annotated[int, Field(ge=0, le=100)] | None = None
    nucleolarMinimumArea: Annotated[int, Field(ge=1, le=100000)] | None = None
    nucleolarMaximumArea: Annotated[int, Field(ge=1, le=16777216)] | None = None
    background: Literal["raw", "automatic", "confirmed_roi"] = "raw"

    @model_validator(mode="after")
    def ordered_area(self):
        if (self.nucleolarDefinition.source == "ncl" and self.nucleolarSigma is not None
                and self.nucleolarSigma > 10):
            raise ValueError("analysis_spec_ncl_sigma_out_of_range")
        if (self.nucleolarMinimumArea is not None and self.nucleolarMaximumArea is not None
                and self.nucleolarMaximumArea < self.nucleolarMinimumArea):
            raise ValueError("analysis_spec_area_range_invalid")
        return self


class AnalysisSelectionDraft(RegionModel):
    field_ids: list[Id] = Field(default_factory=list, max_length=100)
    gfp: GfpFilter | None = None

    @model_validator(mode="after")
    def unique_fields(self):
        if len(self.field_ids) != len(set(self.field_ids)):
            raise ValueError("analysis_spec_duplicate_field")
        return self


class SavedDraftMetric(DraftMetric):
    # Saved editable metrics intentionally include the manual measurement vocabulary.
    metric: MetricId | RegionMetric | LegacyMetric  # type: ignore[assignment]
    channel: Id | None


class SavedDraftStatistics(DraftStatistics):
    x: SavedDraftMetric | None = None
    y: SavedDraftMetric | None = None


class SavedDraftFigure(DraftFigure):
    channel: Id | None


class StatisticsDraft(RegionModel):
    method: SavedDraftStatistics | None = None
    metric: RegionMetric | LegacyMetric = "area_px"
    channel_id: Id | None = None
    x_metric: RegionMetric | None = None
    x_channel_id: Id | None = None
    design: Literal["independent", "paired"] | None = None
    unit_definition: str = Field(default="", max_length=200)
    pairing_basis: str = Field(default="", max_length=200)
    conditions: list[Label] = Field(default_factory=list, max_length=30)
    comparisons: list[Annotated[list[Label], Field(min_length=2, max_length=2)]] = Field(
        default_factory=list, max_length=100)
    field_metadata: dict[Id, RegionFieldMetadata] = Field(default_factory=dict, max_length=100)
    # Drafts may be incomplete. Scientific confirmations remain in the execution contracts.


class FigureDraft(RegionModel):
    metric: RegionMetric | LegacyMetric = "area_px"
    channel_id: Id | None = None
    plot: CommonComparisonPlot | AssociationPlot = Field(default_factory=CommonComparisonPlot)


class SavedNuclearProcessing(DraftNuclearProcessing):
    channel: Id


class SavedNucleolarProcessing(DraftNucleolarProcessing):
    channel: Id


class SavedSignalProcessing(DraftSignalProcessing):
    channel: Id


class SavedCellProcessing(DraftCellProcessing):
    channel: Id


class SavedProcessing(RegionModel):
    version: Literal["1.0.0"] = "1.0.0"
    nuclei: SavedNuclearProcessing | None
    nucleoli: SavedNucleolarProcessing | None
    signal: SavedSignalProcessing | None
    cells: SavedCellProcessing | None = None


class AnalysisSpec(RegionModel):
    schema_version: Literal["1.0.0"] = "1.0.0"
    channel_assignment_version: int = Field(ge=0)
    target: Literal["nuclei", "nucleoli", "nucleoplasm", "cell"] = "nuclei"
    settings: RuntimeSettingsDraft = Field(default_factory=RuntimeSettingsDraft)
    processing: SavedProcessing | None = None
    measurement: RawIntensityPolicy | AutomaticBackgroundPolicy | None = None
    backgrounds: dict[Id, dict[Id, RegionBackground]] = Field(default_factory=dict, max_length=100)
    confirmed_channel_ids: list[Id] = Field(default_factory=list, max_length=6)
    metrics: list[SavedDraftMetric] = Field(default_factory=list, max_length=8)
    selection: AnalysisSelectionDraft = Field(default_factory=AnalysisSelectionDraft)
    statistics: StatisticsDraft | None = None
    additional_analyses: list[SavedDraftStatistics] = Field(default_factory=list, max_length=3)
    figure_proposals: list[SavedDraftFigure] = Field(default_factory=list, max_length=8)
    figure: FigureDraft | None = None

    @model_validator(mode="after")
    def consistent_measurement(self):
        if len(set(self.confirmed_channel_ids)) != len(self.confirmed_channel_ids):
            raise ValueError("analysis_spec_duplicate_confirmed_channel")
        if self.settings.background == "confirmed_roi" and self.measurement is not None:
            raise ValueError("analysis_spec_background_mismatch")
        if self.measurement is not None:
            expected = "raw_intensity" if self.settings.background == "raw" else "automatic_background"
            if self.measurement.mode != expected:
                raise ValueError("analysis_spec_background_mismatch")
        return self


class AnalysisSpecWrite(RegionModel):
    version: int = Field(ge=0)
    spec: AnalysisSpec

    @model_validator(mode="after")
    def executable_association_axes(self):
        methods = [*self.spec.additional_analyses]
        if self.spec.statistics is not None and self.spec.statistics.method is not None:
            methods.append(self.spec.statistics.method)
        for method in methods:
            if method.kind == "association" and (method.x is not None or method.y is not None):
                if (method.x is None or method.y is None or method.x.region is None
                        or method.y.region is None or method.x.region != method.y.region):
                    raise ValueError("proposal_association_same_region_required")
        return self


class AnalysisSpecView(RegionModel):
    version: int = Field(ge=0)
    spec: AnalysisSpec | None


def analysis_spec_at(conn, wid):
    row = conn.execute(select(workspace_analysis_specs).where(
        workspace_analysis_specs.c.workspace_id == wid)).mappings().first()
    return {"version": row["version"], "spec": row["spec"]} if row else {"version": 0, "spec": None}


def register_analysis_spec_routes(api, store, owner, workspace, touch):
    Owner = Annotated[str, Depends(owner)]

    @api.get("/v1/workspaces/{wid}/analysis-spec", response_model=AnalysisSpecView)
    def get_spec(wid: str, who: Owner):
        workspace(wid, who)
        with store.engine.connect() as conn:
            return analysis_spec_at(conn, wid)

    @api.put("/v1/workspaces/{wid}/analysis-spec", response_model=AnalysisSpecView)
    def save_spec(wid: str, body: AnalysisSpecWrite, who: Owner):
        workspace(wid, who)
        with store.transaction() as conn:
            touch(conn, wid)
            previous = analysis_spec_at(conn, wid)
            if previous["version"] != body.version:
                raise HTTPException(409, "analysis_spec_changed")
            if assignments_at(conn, wid)["version"] != body.spec.channel_assignment_version:
                raise HTTPException(409, "channel_assignments_changed")
            registered = conn.execute(select(fields.c.id).where(fields.c.workspace_id == wid)).scalars().all()
            referenced = set(body.spec.selection.field_ids)
            referenced.update(body.spec.backgrounds)
            if body.spec.selection.gfp is not None:
                referenced.update(getattr(body.spec.selection.gfp, "control_field_ids", []))
            if body.spec.statistics is not None:
                referenced.update(body.spec.statistics.field_metadata)
            if referenced - set(registered):
                raise HTTPException(422, "analysis_spec_unknown_field")
            updated = {"version": body.version + 1, "spec": body.spec.model_dump(mode="json")}
            if previous["version"]:
                conn.execute(workspace_analysis_specs.update().where(
                    workspace_analysis_specs.c.workspace_id == wid).values(**updated))
            else:
                conn.execute(workspace_analysis_specs.insert().values(workspace_id=wid, **updated))
            return updated
