from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app import mappers
from app.db import get_db
from app.routers.results import require_analyzed_image
from app.services import export as export_service

router = APIRouter(prefix="/api", tags=["export"])


def _download_name(filename: str, extension: str) -> str:
    stem = Path(filename).stem or "laporan"
    return f"laporan_{stem}.{extension}"


def _attachment(name: str) -> dict[str, str]:
    return {"Content-Disposition": f'attachment; filename="{name}"'}


@router.get("/results/{image_id}/export.csv", response_class=Response)
def export_csv(image_id: UUID, db: Session = Depends(get_db)) -> Response:
    """Detections as CSV, one row per tree."""
    image = require_analyzed_image(db, image_id)
    payload = export_service.to_csv(mappers.detection_result(image))
    return Response(
        content=payload,
        media_type="text/csv; charset=utf-8",
        headers=_attachment(_download_name(image.filename, "csv")),
    )


@router.get("/results/{image_id}/export.pdf", response_class=Response)
def export_pdf(image_id: UUID, db: Session = Depends(get_db)) -> Response:
    """Printable report for one image."""
    image = require_analyzed_image(db, image_id)
    payload = export_service.to_pdf(mappers.detection_result(image))
    return Response(
        content=payload,
        media_type="application/pdf",
        headers=_attachment(_download_name(image.filename, "pdf")),
    )
