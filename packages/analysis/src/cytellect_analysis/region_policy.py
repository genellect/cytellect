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


MeasurementPolicy = RegionMeasurementPolicy | RawIntensityPolicy
MEASUREMENT_POLICY: TypeAdapter[MeasurementPolicy] = TypeAdapter(MeasurementPolicy)


def measurement_protocol(policy: MeasurementPolicy | None) -> str:
    return "1.0.0" if policy is None else ("2.0.0" if policy.mode == "area_only" else "3.0.0")
