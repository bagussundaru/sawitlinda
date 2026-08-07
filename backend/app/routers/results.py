import logging
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app import mappers, models, schemas
from app.config import Settings, get_settings
from app.db import get_db
from app.inference import nebius
from app.inference.engine import run_inference
from app.services import app_settings

router = APIRouter(prefix="/api", tags=["results"])

logger = logging.getLogger("sawitscan")


def _get_image(db: Session, image_id: UUID) -> models.Image:
    image = db.execute(
        select(models.Image)
        .where(models.Image.id == image_id)
        .options(selectinload(models.Image.detections))
    ).scalar_one_or_none()
    if image is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Citra tidak ditemukan.")
    return image


def require_analyzed_image(db: Session, image_id: UUID) -> models.Image:
    """Fetch an image that has results, or fail with a message the user can act on."""
    image = _get_image(db, image_id)
    if image.status != "analyzed":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Citra belum dianalisis. Jalankan /api/analyze/{image_id} terlebih dahulu.",
        )
    return image


@router.post("/analyze/{image_id}", response_model=schemas.DetectionResult)
def analyze_image(
    image_id: UUID,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> schemas.DetectionResult:
    """Run inference on an uploaded image and persist the detections.

    Re-analysing replaces previous detections, so a swapped-in model can be applied
    to images already in the system.
    """
    image = _get_image(db, image_id)

    gps = None
    if image.gps_lat is not None and image.gps_lng is not None:
        gps = (image.gps_lat, image.gps_lng)

    # Settings dari database: berkas model dapat diganti lewat layar Training
    # tanpa restart container.
    result = run_inference(
        image.storage_path,
        gps,
        image.area_ha,
        settings=app_settings.effective_settings(db, settings),
    )

    image.detections.clear()
    for item in result["detections"]:
        x, y, w, h = item["bbox"]
        point = item.get("gps") or {}
        image.detections.append(
            models.Detection(
                bbox_x=x,
                bbox_y=y,
                bbox_w=w,
                bbox_h=h,
                condition=item["condition"],
                severity=item["severity"],
                confidence=item["confidence"],
                gps_lat=point.get("lat"),
                gps_lng=point.get("lng"),
            )
        )
    image.status = "analyzed"
    db.commit()
    db.refresh(image)

    return mappers.detection_result(image)


@router.post("/analyze/{image_id}/ai", response_model=schemas.DetectionResult)
def ai_review(
    image_id: UUID,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> schemas.DetectionResult:
    """Minta penilaian tingkat citra dari model vision.

    Terpisah dari /analyze karena panggilan ke penyedia AI memakan waktu beberapa
    detik dan bisa gagal; deteksi per pohon tidak boleh ikut tertahan olehnya.
    """
    # Kunci yang diisi lewat layar Pengaturan menimpa nilai dari environment.
    settings = app_settings.effective_settings(db, settings)
    if not settings.ai_enabled:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Analisis AI belum dikonfigurasi. Isi kunci Nebius di layar Pengaturan.",
        )

    image = require_analyzed_image(db, image_id)

    ringkasan = mappers.summarise(image.detections)
    per_kondisi: dict[str, int] = {}
    for d in image.detections:
        per_kondisi[d.condition] = per_kondisi.get(d.condition, 0) + 1

    try:
        hasil = nebius.assess_image(
            image.storage_path,
            settings,
            summary={**ringkasan.model_dump(), "per_kondisi": per_kondisi},
        )
    except nebius.NebiusError as exc:
        logger.warning("Analisis AI gagal untuk %s: %s", image_id, exc)
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            f"Analisis AI gagal: {exc}",
        ) from exc

    image.ai_summary = hasil.summary
    image.ai_recommendation = hasil.recommendation
    image.ai_dominant_condition = hasil.dominant_condition
    image.ai_confidence = hasil.confidence
    image.ai_affected_share = hasil.affected_share
    image.ai_notes = "\n".join(hasil.notes)
    image.ai_model = f"{hasil.model} ({hasil.mode})" if hasil.mode == "teks" else hasil.model
    image.ai_created_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(image)

    return mappers.detection_result(image)


@router.get("/results", response_model=list[schemas.ResultListItem])
def list_results(db: Session = Depends(get_db)) -> list[schemas.ResultListItem]:
    """Upload history, newest first."""
    images = (
        db.execute(
            select(models.Image)
            .options(selectinload(models.Image.detections))
            .order_by(models.Image.created_at.desc())
        )
        .scalars()
        .all()
    )
    return [
        schemas.ResultListItem(
            **mappers.image_out(image).model_dump(),
            summary=mappers.summarise(image.detections) if image.status == "analyzed" else None,
        )
        for image in images
    ]


@router.get("/images/{image_id}/file", response_class=FileResponse)
def get_image_file(image_id: UUID, db: Session = Depends(get_db)) -> FileResponse:
    """Serve the stored image itself, so the results screen can draw boxes over it."""
    image = _get_image(db, image_id)
    path = Path(image.storage_path)
    if not path.is_file():
        raise HTTPException(
            status.HTTP_410_GONE, "Berkas citra tidak lagi tersedia di penyimpanan."
        )
    return FileResponse(path, filename=image.filename)


@router.get("/results/{image_id}", response_model=schemas.DetectionResult)
def get_result(image_id: UUID, db: Session = Depends(get_db)) -> schemas.DetectionResult:
    return mappers.detection_result(require_analyzed_image(db, image_id))
