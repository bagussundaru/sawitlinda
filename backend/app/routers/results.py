from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app import mappers, models, schemas
from app.db import get_db
from app.inference.engine import run_inference

router = APIRouter(prefix="/api", tags=["results"])


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
def analyze_image(image_id: UUID, db: Session = Depends(get_db)) -> schemas.DetectionResult:
    """Run inference on an uploaded image and persist the detections.

    Re-analysing replaces previous detections, so a swapped-in model can be applied
    to images already in the system.
    """
    image = _get_image(db, image_id)

    gps = None
    if image.gps_lat is not None and image.gps_lng is not None:
        gps = (image.gps_lat, image.gps_lng)

    result = run_inference(image.storage_path, gps)

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


@router.get("/map", response_model=list[schemas.MapPoint])
def list_map_points(db: Session = Depends(get_db)) -> list[schemas.MapPoint]:
    """Every geo-referenced detection across all images, for the spread map."""
    rows = db.execute(
        select(models.Detection, models.Image)
        .join(models.Image, models.Detection.image_id == models.Image.id)
        .where(models.Detection.gps_lat.is_not(None))
        .where(models.Detection.gps_lng.is_not(None))
        .order_by(models.Detection.id)
    ).all()

    return [
        schemas.MapPoint(
            detection_id=detection.id,
            image_id=image.id,
            filename=image.filename,
            condition=detection.condition,
            severity=detection.severity,
            confidence=detection.confidence,
            gps=schemas.Gps(lat=detection.gps_lat, lng=detection.gps_lng),
        )
        for detection, image in rows
    ]


@router.get("/results/{image_id}", response_model=schemas.DetectionResult)
def get_result(image_id: UUID, db: Session = Depends(get_db)) -> schemas.DetectionResult:
    return mappers.detection_result(require_analyzed_image(db, image_id))
