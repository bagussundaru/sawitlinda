from pathlib import Path

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app import models, schemas
from app.inference import conditions
from app.config import Settings, get_settings
from app.db import get_db
from app.inference import engine, yolo
from app.inference.conditions import CONDITIONS, SEVERITIES
from app.services import app_settings

#: Kept in step with the version declared on the FastAPI app in main.py.
APP_VERSION = "0.1.0"

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/system", response_model=schemas.SystemInfo)
def get_system_info(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> schemas.SystemInfo:
    """Honest description of the running system.

    The UI shows this where a mock-up would show model metrics — reporting an mAP
    for a model that is not loaded would be inventing a number.
    """
    settings = app_settings.effective_settings(db, settings)
    model_path = settings.model_file
    mode, galat = engine.engine_status(settings)
    loaded = mode == "model"

    return schemas.SystemInfo(
        version=APP_VERSION,
        inference_mode=mode,
        model_loaded=loaded,
        model_name=model_path.name if loaded and model_path else None,
        model_error=galat,
        confidence_threshold=yolo.CONF_THRESHOLD,
        nms_iou_threshold=yolo.IOU_THRESHOLD,
        tile_size=yolo.TILE_SIZE,
        severity_source="rule",
        ai_enabled=settings.ai_enabled,
        ai_model=settings.nebius_model if settings.ai_enabled else None,
        max_upload_mb=settings.max_upload_mb,
        condition_count=len(CONDITIONS),
        severities=SEVERITIES,
    )


@router.get("/conditions", response_model=list[schemas.ConditionInfo])
def list_conditions() -> list[schemas.ConditionInfo]:
    """Reference table of tree conditions — legend for the results screen and the
    source of the recommended actions shown to the operator."""
    return [schemas.ConditionInfo(**vars(condition)) for condition in CONDITIONS]





@router.get("/dashboard", response_model=schemas.Dashboard)
def get_dashboard(
    q: str | None = Query(None, description="Batasi ke citra yang labelnya memuat teks ini"),
    db: Session = Depends(get_db),
) -> schemas.Dashboard:
    """Angka agregat lintas citra yang sudah dianalisis.

    `q` menyaring berdasarkan label yang diberikan pengunggah. Pencocokan memakai
    lower() + contains, bukan ILIKE, supaya perilakunya sama di PostgreSQL
    (produksi) dan SQLite (pengujian).
    """
    kunci = q.strip().lower() if q and q.strip() else None
    image_filter = (
        [func.lower(func.coalesce(models.Image.label, models.Image.filename)).contains(kunci)]
        if kunci
        else []
    )

    images_total = (
        db.scalar(select(func.count()).select_from(models.Image).where(*image_filter)) or 0
    )
    images_analyzed = (
        db.scalar(
            select(func.count())
            .select_from(models.Image)
            .where(models.Image.status == "analyzed", *image_filter)
        )
        or 0
    )

    def detections_of():
        query = select(models.Detection)
        if image_filter:
            query = query.join(
                models.Image, models.Detection.image_id == models.Image.id
            ).where(*image_filter)
        return query.subquery()

    scope = detections_of()

    severity_counts = dict(
        db.execute(
            select(scope.c.severity, func.count()).group_by(scope.c.severity)
        ).all()
    )
    terhitung = dict(
        db.execute(
            select(scope.c.condition, func.count()).group_by(scope.c.condition)
        ).all()
    )

    # Keempat kelas selalu dikembalikan, dalam urutan tetap, termasuk yang nol.
    # Kelas yang hilang dari layar terbaca seolah tidak pernah ada, dan urutan
    # yang berubah-ubah mengikuti jumlah membuat dua tangkapan layar sulit
    # dibandingkan.
    condition_counts = [
        (conditions.CLASS_LABELS[key], terhitung.get(conditions.CLASS_LABELS[key], 0))
        for key in conditions.DISPLAY_ORDER
    ]

    total = sum(severity_counts.values())
    healthy = severity_counts.get("sehat", 0)

    return schemas.Dashboard(
        images_total=images_total,
        images_analyzed=images_analyzed,
        summary=schemas.Summary(
            total=total,
            healthy=healthy,
            infected=total - healthy,
            severe=severity_counts.get("berat", 0),
        ),
        by_condition=[
            schemas.NamedCount(label=condition, count=count) for condition, count in condition_counts
        ],
        # Fixed order so the chart keeps a stable axis even when a level is absent.
        by_severity=[
            schemas.NamedCount(label=level, count=severity_counts.get(level, 0))
            for level in SEVERITIES
        ],
    )
