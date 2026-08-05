from pathlib import Path

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app import models, schemas
from app.config import Settings, get_settings
from app.db import get_db
from app.inference.conditions import CONDITIONS, SEVERITIES

#: Kept in step with the version declared on the FastAPI app in main.py.
APP_VERSION = "0.1.0"

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/system", response_model=schemas.SystemInfo)
def get_system_info(
    settings: Settings = Depends(get_settings),
) -> schemas.SystemInfo:
    """Honest description of the running system.

    The UI shows this where a mock-up would show model metrics — reporting an mAP
    for a model that is not loaded would be inventing a number.
    """
    model_path = settings.model_file
    loaded = bool(model_path and model_path.is_file())

    return schemas.SystemInfo(
        version=APP_VERSION,
        inference_mode="model" if loaded else "mock",
        model_loaded=loaded,
        model_name=model_path.name if loaded and model_path else None,
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


@router.get("/blocks", response_model=list[schemas.BlockInfo])
def list_blocks(db: Session = Depends(get_db)) -> list[schemas.BlockInfo]:
    """Plantation blocks as described by the uploads, for the block selector."""
    rows = db.execute(
        select(
            models.Image.block,
            func.count(func.distinct(models.Image.id)),
            func.count(
                func.distinct(
                    case((models.Image.status == "analyzed", models.Image.id))
                )
            ),
            func.sum(func.coalesce(models.Image.area_ha, 0.0)),
        ).group_by(models.Image.block)
    ).all()

    # Tree counts need their own pass; joining detections would multiply the
    # image-level figures above.
    tree_rows = dict(
        db.execute(
            select(
                models.Image.block,
                func.count(models.Detection.id),
            )
            .join(models.Detection, models.Detection.image_id == models.Image.id)
            .group_by(models.Image.block)
        ).all()
    )
    affected_rows = dict(
        db.execute(
            select(
                models.Image.block,
                func.count(models.Detection.id),
            )
            .join(models.Detection, models.Detection.image_id == models.Image.id)
            .where(models.Detection.severity != "sehat")
            .group_by(models.Image.block)
        ).all()
    )

    blocks = [
        schemas.BlockInfo(
            block=block,
            images=images,
            analyzed=analyzed,
            trees=tree_rows.get(block, 0),
            affected=affected_rows.get(block, 0),
            area_ha=round(area, 2) if area else None,
        )
        for block, images, analyzed, area in rows
    ]
    # Named blocks first, alphabetically; the unlabelled bucket goes last.
    blocks.sort(key=lambda b: (b.block is None, b.block or ""))
    return blocks


@router.get("/dashboard", response_model=schemas.Dashboard)
def get_dashboard(
    block: str | None = Query(None, description="Batasi agregat ke satu blok kebun"),
    db: Session = Depends(get_db),
) -> schemas.Dashboard:
    """Aggregate figures across every analysed image, for the statistics screen."""
    image_filter = [models.Image.block == block] if block is not None else []

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
        if block is not None:
            query = query.join(
                models.Image, models.Detection.image_id == models.Image.id
            ).where(models.Image.block == block)
        return query.subquery()

    scope = detections_of()

    severity_counts = dict(
        db.execute(
            select(scope.c.severity, func.count()).group_by(scope.c.severity)
        ).all()
    )
    condition_counts = db.execute(
        select(scope.c.condition, func.count())
        .group_by(scope.c.condition)
        .order_by(func.count().desc())
    ).all()

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
