"""Display-only provenance; never an input to measurement or detection."""
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat

PREVIEW_DISPLAY_HEADER = "X-Cytellect-Preview-Display"


class PreviewPlaneDisplay(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel_id: str
    dtype: str
    value_basis: Literal["native-grayscale", "legacy-imported"]
    source_min: FiniteFloat
    source_max: FiniteFloat
    percentile_low_value: FiniteFloat
    percentile_high_value: FiniteFloat
    normalization_span: FiniteFloat = Field(ge=1)
    display_black_value: FiniteFloat
    display_white_value: FiniteFloat
    constant_plane: bool


class PreviewDisplayMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal["1.0.0"] = "1.0.0"
    field_id: str
    requested_channel: str
    composite: bool
    scope: Literal["whole-plane"] = "whole-plane"
    mode: Literal["per-plane-percentile"] = "per-plane-percentile"
    low_percentile: FiniteFloat = Field(ge=0, lt=100)
    high_percentile: FiniteFloat = Field(gt=0, le=100)
    gain: FiniteFloat = Field(ge=0.1, le=10)
    planes: list[PreviewPlaneDisplay] = Field(min_length=1, max_length=3)


PREVIEW_PNG_RESPONSE: dict[int | str, dict[str, Any]] = {
    200: {
        "content": {"image/png": {"schema": {"type": "string", "format": "binary"}}},
        "headers": {
            PREVIEW_DISPLAY_HEADER: {
                "description": "ASCII-escaped JSON for the exact rendered PNG; display only.",
                "content": {"application/json": {"schema": {
                    "$ref": "#/components/schemas/PreviewDisplayMetadata",
                }}},
            },
        },
    },
}
