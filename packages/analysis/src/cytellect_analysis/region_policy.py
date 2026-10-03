"""Dependency-free measurement policy shared by planning and scientific inputs."""
from typing import Literal

from pydantic import BaseModel, ConfigDict


class RegionMeasurementPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, revalidate_instances="always")

    version: Literal["1.0.0"]
    mode: Literal["area_only"]
