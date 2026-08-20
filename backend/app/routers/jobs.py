"""Memicu dan memantau pekerjaan latar."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.services import app_settings, auth, job_handlers, jobs as job_queue

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


class JobOut(BaseModel):
    id: UUID
    kind: str
    status: str
    progress: dict
    result: dict | None
    error: str | None
    created_by: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

    class Config:
        from_attributes = True


class RoboflowEvaluateIn(BaseModel):
    workspace: str = Field(min_length=1, max_length=80)
    project: str = Field(min_length=1, max_length=80)
    version: int = Field(ge=1, le=999)
    split: str = Field(default="test", pattern="^(test|valid|train)$")
    iou_threshold: float = Field(default=0.5, gt=0, lt=1)


class ReanalyseIn(BaseModel):
    #: Kosongkan untuk menganalisis ulang seluruh citra.
    image_ids: list[UUID] | None = None


def _tolak_bila_sibuk(db: Session) -> None:
    """Satu pekerjaan berat pada satu waktu.

    VM ini berbagi dengan aplikasi lain. Dua pekerjaan inference berjalan
    bersamaan akan memakan seluruh CPU dan membuat aplikasi tetangga tersendat.
    """
    berjalan = job_queue.active(db)
    if berjalan is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"A background job is already {berjalan.status} ({berjalan.kind}). "
            "Wait for it to finish first.",
        )


@router.get("", response_model=list[JobOut])
def list_jobs(
    db: Session = Depends(get_db),
    _: models.User = Depends(auth.current_user),
) -> list[models.Job]:
    """Pekerjaan terbaru lebih dulu."""
    return list(
        db.scalars(select(models.Job).order_by(models.Job.created_at.desc()).limit(30))
    )


@router.get("/{job_id}", response_model=JobOut)
def get_job(
    job_id: UUID,
    db: Session = Depends(get_db),
    _: models.User = Depends(auth.current_user),
) -> models.Job:
    job = db.get(models.Job, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found.")
    return job


@router.post(
    "/roboflow-evaluate", response_model=JobOut, status_code=status.HTTP_202_ACCEPTED
)
def start_roboflow_evaluate(
    body: RoboflowEvaluateIn,
    db: Session = Depends(get_db),
    pengguna: models.User = Depends(auth.current_user),
) -> models.Job:
    """Tarik satu versi dataset dari Roboflow, analisis, lalu evaluasi."""
    if not app_settings.get(db, job_handlers.ROBOFLOW_KEY):
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Roboflow API key is not set. Add it on the Settings screen.",
        )
    _tolak_bila_sibuk(db)
    return job_queue.enqueue(
        db, "roboflow_evaluate", body.model_dump(), created_by=pengguna.username
    )


@router.post("/reanalyse", response_model=JobOut, status_code=status.HTTP_202_ACCEPTED)
def start_reanalyse(
    body: ReanalyseIn,
    db: Session = Depends(get_db),
    pengguna: models.User = Depends(auth.current_user),
) -> models.Job:
    """Jalankan ulang inference pada citra yang sudah ada.

    Diperlukan setiap kali model atau cara pemrosesannya berubah — hasil lama
    tidak ikut berubah sendiri.
    """
    _tolak_bila_sibuk(db)
    muatan = {
        "image_ids": [str(i) for i in body.image_ids] if body.image_ids else None
    }
    return job_queue.enqueue(db, "reanalyse", muatan, created_by=pengguna.username)
