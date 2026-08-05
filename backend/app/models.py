import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Image(Base):
    """One uploaded UAV image."""

    __tablename__ = "images"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    filename: Mapped[str] = mapped_column(String(255))
    storage_path: Mapped[str] = mapped_column(String(512))
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    #: Plantation block the frame covers, e.g. "A-3". Entered at upload time —
    #: it cannot be derived from the image or its metadata.
    block: Mapped[str | None] = mapped_column(String(64), index=True)
    #: Area the frame covers, in hectares.
    area_ha: Mapped[float | None] = mapped_column(Float)
    gps_lat: Mapped[float | None] = mapped_column(Float)
    gps_lng: Mapped[float | None] = mapped_column(Float)
    # uploaded | analyzed
    status: Mapped[str] = mapped_column(String(16), default="uploaded")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    # --- Penilaian tingkat citra dari model vision (opsional, lihat
    #     app/inference/nebius.py). Semua nullable: fitur boleh dimatikan. ---
    ai_summary: Mapped[str | None] = mapped_column(Text)
    ai_recommendation: Mapped[str | None] = mapped_column(Text)
    ai_dominant_condition: Mapped[str | None] = mapped_column(String(128))
    ai_confidence: Mapped[float | None] = mapped_column(Float)
    ai_affected_share: Mapped[float | None] = mapped_column(Float)
    #: Catatan keterbatasan dari model, dipisah baris baru.
    ai_notes: Mapped[str | None] = mapped_column(Text)
    ai_model: Mapped[str | None] = mapped_column(String(128))
    ai_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    detections: Mapped[list["Detection"]] = relationship(
        back_populates="image",
        cascade="all, delete-orphan",
        order_by="Detection.id",
    )


class Detection(Base):
    """One detected palm tree within an image."""

    __tablename__ = "detections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    image_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("images.id", ondelete="CASCADE"), index=True
    )
    bbox_x: Mapped[float] = mapped_column(Float)
    bbox_y: Mapped[float] = mapped_column(Float)
    bbox_w: Mapped[float] = mapped_column(Float)
    bbox_h: Mapped[float] = mapped_column(Float)
    condition: Mapped[str] = mapped_column(String(128))
    # ringan | sedang | berat
    severity: Mapped[str] = mapped_column(String(16))
    confidence: Mapped[float] = mapped_column(Float)
    gps_lat: Mapped[float | None] = mapped_column(Float)
    gps_lng: Mapped[float | None] = mapped_column(Float)

    image: Mapped[Image] = relationship(back_populates="detections")


class Evaluation(Base):
    """Satu kali evaluasi terhadap anotasi ground truth.

    Disimpan agar angkanya dapat dibuka kembali dan dibandingkan antarwaktu —
    tanpa itu, metrik disertasi hanya ada di layar sekali jalan.
    """

    __tablename__ = "evaluations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    source_filename: Mapped[str] = mapped_column(String(255))
    iou_threshold: Mapped[float] = mapped_column(Float)

    #: Keadaan sistem saat evaluasi dijalankan — supaya angka mock tidak pernah
    #: tertukar dengan angka model sungguhan di kemudian hari.
    inference_mode: Mapped[str] = mapped_column(String(16))
    model_name: Mapped[str | None] = mapped_column(String(128))

    images: Mapped[int] = mapped_column(Integer)
    ground_truths: Mapped[int] = mapped_column(Integer)
    predictions: Mapped[int] = mapped_column(Integer)

    map50: Mapped[float] = mapped_column(Float)
    micro_precision: Mapped[float] = mapped_column(Float)
    micro_recall: Mapped[float] = mapped_column(Float)
    micro_f1: Mapped[float] = mapped_column(Float)

    per_class: Mapped[list] = mapped_column(JSON)
    confusion: Mapped[dict] = mapped_column(JSON)


class AppSetting(Base):
    """Pengaturan yang dapat diubah saat aplikasi berjalan.

    Dipakai untuk nilai yang tidak boleh masuk repositori — mis. kunci API —
    sehingga operator dapat mengisinya lewat layar Pengaturan tanpa menyunting
    berkas .env dan tanpa restart container.

    Nilai di sini menimpa environment variable dengan nama yang setara.
    """

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )
