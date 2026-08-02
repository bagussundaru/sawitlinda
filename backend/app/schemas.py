"""Pydantic schemas — the authoritative shape of the JSON contract in CLAUDE.md.

Mirrored on the frontend in `frontend/src/types/detection.ts`. Change both together.
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

Severity = Literal["ringan", "sedang", "berat"]
ImageStatus = Literal["uploaded", "analyzed"]


class Gps(BaseModel):
    lat: float
    lng: float


class DetectionOut(BaseModel):
    id: int
    #: [x, y, w, h] in image pixel coordinates
    bbox: list[float] = Field(min_length=4, max_length=4)
    disease: str
    severity: Severity
    confidence: float
    gps: Gps | None = None


class Summary(BaseModel):
    total: int
    healthy: int
    infected: int
    severe: int


class DetectionResult(BaseModel):
    image_id: UUID
    filename: str
    captured_at: datetime | None = None
    gps: Gps | None = None
    summary: Summary
    detections: list[DetectionOut]


class ImageOut(BaseModel):
    """An uploaded image, before or after analysis."""

    image_id: UUID
    filename: str
    captured_at: datetime | None = None
    gps: Gps | None = None
    status: ImageStatus
    created_at: datetime


class UploadResponse(BaseModel):
    """Result of a batch upload: one entry per accepted file."""

    images: list[ImageOut]
