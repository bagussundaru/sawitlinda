"""Catatan eksperimen, dan penjagaan atas test set.

Aturan yang ditegakkan di sini bersifat metodologis, bukan teknis:

1. **Hipotesis dicatat sebelum hasilnya ada.** Catatan dibuat lebih dulu, hasil
   dilampirkan kemudian. Hipotesis yang ditulis setelah melihat angkanya tidak
   membuktikan apa pun.

2. **Hasil hanya dapat dilampirkan sekali.** Tidak ada endpoint yang menyunting
   atau menghapus catatan. Catatan yang dapat diubah setelah hasilnya terlihat
   bukan catatan eksperimen.

3. **Test set dijaga.** Model yang berbeda boleh diuji pada test yang sama —
   itu justru tujuannya. Model yang SAMA diuji dua kali pada test yang sama
   harus disengaja, karena di situlah penyetelan diam-diam berdasarkan hasil
   test bermula.

`dataset_test_hash` disimpan bersama setiap catatan. Enam bulan kemudian,
ketika dataset sudah berubah beberapa kali, itulah satu-satunya cara memastikan
angka yang dilaporkan memang diukur pada test set yang sama.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.services import auth

router = APIRouter(prefix="/api/experiments", tags=["experiments"])

logger = logging.getLogger("sawitscan")

VALIDATION = "validation"
TEST = "test"

#: Siklus status, hanya maju. Indeksnya menentukan urutan; perpindahan mundur
#: ditolak, karena catatan yang dapat dikembalikan ke draft setelah hasilnya
#: terlihat bukan catatan yang dibekukan.
LIFECYCLE = (
    "draft",
    "locked",
    "training",
    "ready_for_final_test",
    "final_tested",
)

#: Sejak status ini, hipotesis dan identitas dataset tidak dapat diubah lagi.
FROZEN_FROM = LIFECYCLE.index("locked")

#: Hasil hanya boleh dilampirkan pada tahap ini — model sudah final.
READY = "ready_for_final_test"


class ExperimentIn(BaseModel):
    experiment_id: str = Field(min_length=1, max_length=64)
    kind: str = Field(pattern=f"^({VALIDATION}|{TEST})$")
    #: sha256 berkas bobot yang dievaluasi.
    model_id: str = Field(min_length=8, max_length=64)
    model_name: str | None = Field(default=None, max_length=128)
    dataset_name: str = Field(min_length=1, max_length=128)
    dataset_test_hash: str = Field(min_length=8, max_length=64)
    dataset_val_hash: str | None = Field(default=None, max_length=64)
    #: Ditulis SEBELUM hasilnya ada.
    hypothesis: str | None = None
    training_config: dict = Field(default_factory=dict)
    git_commit: str | None = Field(default=None, max_length=64)
    #: Wajib true untuk mengulang evaluasi test pada model yang sama.
    confirm_repeat: bool = False


class ResultsIn(BaseModel):
    metrics: dict


class StatusIn(BaseModel):
    status: str = Field(pattern="^(" + "|".join(LIFECYCLE) + ")$")


class DraftEditIn(BaseModel):
    """Hanya dapat dipakai selagi status masih `draft`."""

    hypothesis: str | None = None
    training_config: dict | None = None
    model_id: str | None = Field(default=None, min_length=8, max_length=64)
    model_name: str | None = Field(default=None, max_length=128)


class ExperimentOut(BaseModel):
    id: UUID
    experiment_id: str
    kind: str
    model_id: str
    model_name: str | None
    dataset_name: str
    dataset_test_hash: str
    dataset_val_hash: str | None
    hypothesis: str | None
    training_config: dict
    git_commit: str | None
    status: str
    metrics: dict | None
    results_at: datetime | None
    created_by: str | None
    created_at: datetime

    class Config:
        from_attributes = True


def _guard_test_reuse(db: Session, body: ExperimentIn) -> None:
    """Tolak evaluasi test kedua pada model yang sama, kecuali disengaja."""
    if body.kind != TEST or body.confirm_repeat:
        return

    sebelumnya = db.scalar(
        select(models.Experiment).where(
            models.Experiment.kind == TEST,
            models.Experiment.model_id == body.model_id,
            models.Experiment.dataset_test_hash == body.dataset_test_hash,
        )
    )
    if sebelumnya is None:
        return

    raise HTTPException(
        status.HTTP_409_CONFLICT,
        f"This model was already evaluated on this exact test set as "
        f"'{sebelumnya.experiment_id}' on {sebelumnya.created_at:%Y-%m-%d}. "
        "The test set is meant to be used once, after the model is final; "
        "repeating it is how tuning on test results begins. Pass "
        "confirm_repeat=true if the repeat is deliberate — it will be recorded "
        "as a separate experiment either way.",
    )


@router.get("", response_model=list[ExperimentOut])
def list_experiments(
    kind: str | None = Query(None, pattern=f"^({VALIDATION}|{TEST})$"),
    db: Session = Depends(get_db),
    _: models.User = Depends(auth.current_user),
) -> list[models.Experiment]:
    """Catatan terbaru lebih dulu."""
    kueri = select(models.Experiment).order_by(models.Experiment.created_at.desc())
    if kind:
        kueri = kueri.where(models.Experiment.kind == kind)
    return list(db.scalars(kueri.limit(100)))


@router.post("", response_model=ExperimentOut, status_code=status.HTTP_201_CREATED)
def record_experiment(
    body: ExperimentIn,
    db: Session = Depends(get_db),
    pengguna: models.User = Depends(auth.current_user),
) -> models.Experiment:
    """Catat sebuah eksperimen. Hasilnya dilampirkan terpisah, sesudahnya."""
    if db.scalar(
        select(models.Experiment).where(
            models.Experiment.experiment_id == body.experiment_id
        )
    ):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Experiment '{body.experiment_id}' already exists. Records are "
            "immutable; choose a new identifier.",
        )

    _guard_test_reuse(db, body)

    baris = models.Experiment(
        **body.model_dump(exclude={"confirm_repeat"}),
        # Commit dibaca dari environment bila ada: ia dipanggang saat image
        # dibangun, sehingga tidak dapat dikarang oleh pemanggil.
        created_by=pengguna.username,
    )
    if baris.git_commit is None:
        baris.git_commit = os.environ.get("GIT_COMMIT") or None

    db.add(baris)
    db.commit()
    db.refresh(baris)
    logger.info(
        "Eksperimen dicatat: %s (%s) oleh %s",
        baris.experiment_id,
        baris.kind,
        pengguna.username,
    )
    return baris


def _cari(db: Session, experiment_id: str) -> models.Experiment:
    baris = db.scalar(
        select(models.Experiment).where(
            models.Experiment.experiment_id == experiment_id
        )
    )
    if baris is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Experiment not found.")
    return baris


@router.patch("/{experiment_id}", response_model=ExperimentOut)
def edit_draft(
    experiment_id: str,
    body: DraftEditIn,
    db: Session = Depends(get_db),
    _: models.User = Depends(auth.current_user),
) -> models.Experiment:
    """Ubah hipotesis atau konfigurasi — hanya selagi masih draft.

    Setelah dikunci, hipotesis tidak dapat disunting. Hipotesis yang masih dapat
    diubah setelah eksperimen berjalan tidak mengikat apa pun.
    """
    baris = _cari(db, experiment_id)
    if LIFECYCLE.index(baris.status) >= FROZEN_FROM:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Experiment '{experiment_id}' is {baris.status}. Hypothesis and "
            "configuration were frozen when it left draft — that is what makes "
            "the freeze mean anything.",
        )

    for bidang, nilai in body.model_dump(exclude_none=True).items():
        setattr(baris, bidang, nilai)
    db.commit()
    db.refresh(baris)
    return baris


@router.post("/{experiment_id}/status", response_model=ExperimentOut)
def advance_status(
    experiment_id: str,
    body: StatusIn,
    db: Session = Depends(get_db),
    _: models.User = Depends(auth.current_user),
) -> models.Experiment:
    """Majukan status. Mundur ditolak.

    `final_tested` tidak dapat disetel di sini — status itu hanya diperoleh
    dengan benar-benar melampirkan hasil.
    """
    baris = _cari(db, experiment_id)
    sekarang = LIFECYCLE.index(baris.status)
    tujuan = LIFECYCLE.index(body.status)

    if body.status == "final_tested":
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "'final_tested' is reached by attaching results, not by setting it.",
        )
    if tujuan <= sekarang:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Experiment '{experiment_id}' is already {baris.status}; the "
            "lifecycle only moves forward.",
        )

    baris.status = body.status
    db.commit()
    db.refresh(baris)
    logger.info("Eksperimen %s -> %s", experiment_id, body.status)
    return baris


@router.post("/{experiment_id}/results", response_model=ExperimentOut)
def attach_results(
    experiment_id: str,
    body: ResultsIn,
    db: Session = Depends(get_db),
    _: models.User = Depends(auth.current_user),
) -> models.Experiment:
    """Lampirkan hasil, satu kali.

    Percobaan kedua ditolak: catatan yang hasilnya dapat ditimpa tidak
    membuktikan apa pun tentang apa yang benar-benar terjadi.
    """
    baris = _cari(db, experiment_id)

    # Kekekalan diperiksa lebih dulu: setelah hasil dilampirkan statusnya sudah
    # `final_tested`, sehingga syarat status di bawah akan menolak percobaan
    # kedua dengan alasan yang salah.
    if baris.metrics is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Results for '{experiment_id}' were already recorded on "
            f"{baris.results_at:%Y-%m-%d %H:%M}. Experiment records are "
            "immutable — record a new experiment instead.",
        )

    if baris.kind == TEST and baris.status != READY:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Experiment '{experiment_id}' is {baris.status}. A final test may "
            f"only be recorded once the experiment reaches '{READY}' — the "
            "model must be final before the test set is touched.",
        )

    baris.metrics = body.metrics
    baris.results_at = datetime.now(timezone.utc)
    baris.status = "final_tested"
    db.commit()
    db.refresh(baris)
    return baris
