"""Pydantic schemas — the authoritative shape of the JSON contract in CLAUDE.md.

Mirrored on the frontend in `frontend/src/types/detection.ts`. Change both together.
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

#: "sehat" marks a detected tree with no condition — those trees are part of the
#: detections array too, since the result screen and map draw every tree.
Severity = Literal["sehat", "ringan", "sedang", "berat"]
ImageStatus = Literal["uploaded", "analyzed"]


class Gps(BaseModel):
    lat: float
    lng: float


class DetectionOut(BaseModel):
    id: int
    #: [x, y, w, h] in image pixel coordinates
    bbox: list[float] = Field(min_length=4, max_length=4)
    condition: str
    severity: Severity
    confidence: float
    gps: Gps | None = None


class Summary(BaseModel):
    total: int
    healthy: int
    infected: int
    severe: int


class AiAssessmentOut(BaseModel):
    """Penilaian tingkat citra dari model vision — pendapat kedua di samping
    deteksi per pohon, bukan penggantinya."""

    summary: str
    recommendation: str
    dominant_condition: str
    confidence: float
    affected_share: float
    notes: list[str] = []
    model: str
    created_at: datetime
    #: Selisih perkiraan model vision dengan hasil deteksi, dalam poin persen.
    #: Nilai besar berarti keduanya tidak sepakat dan citra layak diperiksa manual.
    disagreement_pp: float | None = None


class DetectionResult(BaseModel):
    image_id: UUID
    filename: str
    captured_at: datetime | None = None
    block: str | None = None
    area_ha: float | None = None
    gps: Gps | None = None
    summary: Summary
    detections: list[DetectionOut]
    ai: AiAssessmentOut | None = None


class ImageOut(BaseModel):
    """An uploaded image, before or after analysis."""

    image_id: UUID
    filename: str
    captured_at: datetime | None = None
    block: str | None = None
    area_ha: float | None = None
    gps: Gps | None = None
    status: ImageStatus
    created_at: datetime
    has_ai: bool = False


class UploadResponse(BaseModel):
    """Result of a batch upload: one entry per accepted file."""

    images: list[ImageOut]


class ResultListItem(ImageOut):
    """History entry. `summary` is null while the image has not been analysed."""

    summary: Summary | None = None


class MapPoint(BaseModel):
    """One detected tree with coordinates, for the spread map."""

    detection_id: int
    image_id: UUID
    filename: str
    block: str | None = None
    #: When the source image was taken, so the map can show sortie dates.
    captured_at: datetime | None = None
    condition: str
    severity: Severity
    confidence: float
    gps: Gps


class SystemInfo(BaseModel):
    """What the system actually is right now — no invented model metrics."""

    version: str
    #: "mock" selama model asli belum dipasang.
    inference_mode: Literal["mock", "model"]
    #: True hanya bila mesin model benar-benar dapat dimuat, bukan sekadar
    #: berkasnya ada di tempatnya.
    model_loaded: bool
    model_name: str | None = None
    #: Terisi bila berkas model ada tapi mesinnya gagal dimuat.
    model_error: str | None = None
    #: Dari mana nilai keparahan berasal. "rule" berarti diturunkan dari aturan
    #: tetap, bukan diprediksi model — dataset belum memuat label keparahan.
    severity_source: Literal["rule", "model"] = "rule"
    #: Lapisan analisis AI (Nebius) aktif atau tidak.
    ai_enabled: bool = False
    ai_model: str | None = None
    max_upload_mb: int
    condition_count: int
    severities: list[str]


class ConditionInfo(BaseModel):
    """Reference entry: how to read a condition and what to do about it."""

    key: str
    label: str
    appearance: str
    interpretation: str
    action: str


class NamedCount(BaseModel):
    label: str
    count: int


class BlockInfo(BaseModel):
    """One plantation block, as far as the uploaded images describe it."""

    #: None mengumpulkan citra yang diunggah tanpa keterangan blok.
    block: str | None = None
    images: int
    analyzed: int
    trees: int
    affected: int
    area_ha: float | None = None


class Dashboard(BaseModel):
    """Aggregate across every analysed image."""

    images_total: int
    images_analyzed: int
    summary: Summary
    by_condition: list[NamedCount]
    by_severity: list[NamedCount]


class ClassMetricsOut(BaseModel):
    """Metrik satu kelas kondisi."""

    label: str
    #: Jumlah ground truth untuk kelas ini.
    support: int
    predicted: int
    true_positive: int
    false_positive: int
    false_negative: int
    precision: float
    recall: float
    f1: float
    average_precision: float


class EvaluationOut(BaseModel):
    """Hasil satu kali evaluasi terhadap anotasi ground truth."""

    id: UUID
    created_at: datetime
    source_filename: str
    iou_threshold: float
    #: Keadaan sistem saat evaluasi dijalankan; "mock" berarti angka ini TIDAK
    #: mengukur model apa pun dan tidak boleh dilaporkan sebagai hasil.
    inference_mode: Literal["mock", "model"]
    model_name: str | None = None

    images: int
    ground_truths: int
    predictions: int

    map50: float
    micro_precision: float
    micro_recall: float
    micro_f1: float

    per_class: list[ClassMetricsOut]
    #: confusion[aktual][prediksi]
    confusion: dict[str, dict[str, int]]
