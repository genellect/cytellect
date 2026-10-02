"""Public response contracts; paths and authentication hashes never leave storage."""

from typing import Any, Literal

from cytellect_analysis.contracts import FieldMetadata
from pydantic import BaseModel


class WorkspaceView(BaseModel):
    id: str
    owner: str
    title: str
    created: float
    expires: float
    deleted: bool
    active_revision: str | None
    bytes: int


class ImageInfo(BaseModel):
    shape: list[int]
    dtype: str
    legacy: bool
    inputs: dict[str, dict[str, Any]]
    axes: str
    channel_mapping: list[str | int]


class FieldView(BaseModel):
    id: str
    workspace_id: str
    metadata: FieldMetadata
    image_info: ImageInfo
    synthetic: bool


class RevisionView(BaseModel):
    id: str
    workspace_id: str
    parent_id: str | None
    config: dict[str, Any]
    state: Literal["queued", "running", "succeeded", "failed", "cancelled"]
    reviewed: bool
    created: float


class JobView(BaseModel):
    id: str
    revision_id: str
    kind: Literal["analysis", "statistics", "table-statistics", "export"]
    state: Literal["queued", "running", "succeeded", "failed", "cancelled"]
    created: float
    error: str | None
    attempts: int


class ContourView(BaseModel):
    id: int
    points: list[tuple[float, float]]


class MasksView(BaseModel):
    nuclei: list[ContourView]
    nucleoli: list[ContourView]
    manual: list[ContourView]
