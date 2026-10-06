"""Dependency-free, versioned measurement policies."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, TypeAdapter


class RegionMeasurementPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, revalidate_instances="always")
    version: Literal["1.0.0"]
    mode: Literal["area_only"]


class RawIntensityPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, revalidate_instances="always")
    version: Literal["1.1.0"]
    mode: Literal["raw_intensity"]


class AutomaticBackgroundPolicy(BaseModel):
    """Raw values plus corrections from an automatic, unconfirmed background candidate."""
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, revalidate_instances="always")
    version: Literal["1.2.0"]
    mode: Literal["automatic_background"]


MeasurementPolicy = RegionMeasurementPolicy | RawIntensityPolicy | AutomaticBackgroundPolicy
MEASUREMENT_POLICY: TypeAdapter[MeasurementPolicy] = TypeAdapter(MeasurementPolicy)
PROTOCOL_BY_MODE = {"area_only": "2.0.0", "raw_intensity": "3.0.0", "automatic_background": "4.0.0"}
MODE_BY_PROTOCOL = {protocol: mode for mode, protocol in PROTOCOL_BY_MODE.items()}


def measurement_protocol(policy: MeasurementPolicy | None) -> str:
    return "1.0.0" if policy is None else PROTOCOL_BY_MODE[policy.mode]
