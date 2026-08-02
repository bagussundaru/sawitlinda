from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models, schemas
from app.db import get_db
from app.inference.diseases import SEVERITIES

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/dashboard", response_model=schemas.Dashboard)
def get_dashboard(db: Session = Depends(get_db)) -> schemas.Dashboard:
    """Aggregate figures across every analysed image, for the statistics screen."""
    images_total = db.scalar(select(func.count()).select_from(models.Image)) or 0
    images_analyzed = (
        db.scalar(
            select(func.count())
            .select_from(models.Image)
            .where(models.Image.status == "analyzed")
        )
        or 0
    )

    severity_counts = dict(
        db.execute(
            select(models.Detection.severity, func.count())
            .group_by(models.Detection.severity)
        ).all()
    )
    disease_counts = db.execute(
        select(models.Detection.disease, func.count())
        .group_by(models.Detection.disease)
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
        by_disease=[
            schemas.NamedCount(label=disease, count=count) for disease, count in disease_counts
        ],
        # Fixed order so the chart keeps a stable axis even when a level is absent.
        by_severity=[
            schemas.NamedCount(label=level, count=severity_counts.get(level, 0))
            for level in SEVERITIES
        ],
    )
