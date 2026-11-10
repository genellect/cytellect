"""Channel gate 1.0.0: explicit nuclear-mean classification, separate from legacy GFP."""
from typing import Annotated, Any, Literal

from pydantic import Field, FiniteFloat, StrictInt, model_validator

from .contracts import StrictModel
from .regions import Id

PROTOCOL: Literal["channel-gate/1.0.0"] = "channel-gate/1.0.0"


def _optional_reference(schema: dict[str, Any]) -> None:
    schema.pop("default", None)


class ChannelGateFilter(StrictModel):
    version: Literal["1.0.0"]
    gate_protocol: Literal["channel-gate/1.0.0"]
    channel_id: Id
    method: Literal["negative_control", "manual", "batch_otsu"]
    values: Literal["raw", "corrected"] = "raw"
    keep: Literal["positive", "negative"]
    percentile: Annotated[FiniteFloat, Field(ge=50, lt=100)] = 99.0
    threshold: FiniteFloat | None = None
    control_field_ids: Annotated[list[Id], Field(max_length=100)] = Field(default_factory=list)
    reference_sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")] | None = Field(default=None, json_schema_extra=_optional_reference)

    @model_validator(mode="after")
    def explicit_method(self):
        if (self.method == "manual") != (self.threshold is not None):
            raise ValueError("channel_gate_threshold_invalid")
        if (self.method == "negative_control") != bool(self.control_field_ids):
            raise ValueError("channel_gate_control_fields_invalid")
        if len(self.control_field_ids) != len(set(self.control_field_ids)):
            raise ValueError("channel_gate_duplicate_control_field")
        return self


class ChannelGateField(StrictModel):
    field_id: Id
    revision_id: Id


class ChannelGateRequest(StrictModel):
    """Classify saved nuclear measurements; this endpoint does not adopt or review them."""
    filter: ChannelGateFilter
    fields: Annotated[list[ChannelGateField], Field(min_length=1, max_length=100)]

    @model_validator(mode="after")
    def unique_fields(self):
        ids = [item.field_id for item in self.fields]
        if len(ids) != len(set(ids)):
            raise ValueError("channel_gate_duplicate_field")
        if set(self.filter.control_field_ids) - set(ids):
            raise ValueError("channel_gate_unknown_control_field")
        return self


class ChannelGateNucleus(StrictModel):
    field_id: Id
    region_id: Annotated[StrictInt, Field(ge=1, le=4294967295)]
    acquisition_date: str | None
    channel_mean: FiniteFloat | None
    positive: bool | None
    status: Literal["positive", "negative", "unclassified", "control", "excluded"]
    reason: str
    threshold: FiniteFloat | None
    exclusion_reason: str | None


class ChannelGateCounts(StrictModel):
    status: Literal["measured", "no_regions", "excluded", "failed"]
    nuclei: StrictInt | None
    positive: StrictInt
    negative: StrictInt
    unclassified: StrictInt
    control: StrictInt
    excluded: StrictInt
    evaluable: StrictInt


class ChannelGateResult(StrictModel):
    protocol: Literal["channel-gate/1.0.0"] = PROTOCOL
    filter: ChannelGateFilter
    channel: dict[str, Any]
    dates: dict[str, Any]
    nuclei: list[ChannelGateNucleus]
    field_counts: dict[Id, ChannelGateCounts]
    record: dict[str, Any]
