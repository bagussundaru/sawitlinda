"""Training model: memulai, memantau, dan menjadikan hasilnya model aktif.

Aplikasi tidak melatih apa pun sendiri — VM ini tidak punya GPU. Router ini
adalah proxy ke mesin training di Modal (lihat training_engine/), ditambah
riwayat yang disimpan di PostgreSQL agar bertahan melewati restart.

Token Modal tidak pernah dikirim ke peramban. Peramban berbicara dengan router
ini; router ini yang berbicara dengan Modal.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.config import Settings, get_settings
from app.db import get_db
from app.services import app_settings, auth, training_engine

router = APIRouter(prefix="/api/train", tags=["training"])

logger = logging.getLogger("sawitscan")

BASE_MODELS = ["yolov8n.pt", "yolov8s.pt", "yolov8m.pt", "yolov8l.pt", "yolov8x.pt"]

#: Batas ukuran dataset. Dataset klien (1.007 citra) sekitar 66 MB; 2 GB memberi
#: ruang lapang tanpa membiarkan unggahan liar mengisi disk VM.
MAX_DATASET_MB = 2048


class TrainingRunOut(BaseModel):
    id: UUID
    job_id: str
    run_name: str
    base_model: str
    epochs: int
    dataset_filename: str | None
    status: str
    started_by: str | None
    created_at: datetime
    finished_at: datetime | None
    final_map50: float | None
    final_map50_95: float | None
    last_epoch: int | None
    error: str | None
    is_active: bool

    class Config:
        from_attributes = True


class TrainingStatusOut(BaseModel):
    job_id: str
    status: str
    epoch: int | None = None
    total_epochs: int | None = None
    history: list[dict] = []
    latest: dict | None = None
    error: str | None = None
    run_name: str | None = None
    is_active: bool = False


class TrainingConfigOut(BaseModel):
    configured: bool
    base_models: list[str]
    max_epochs: int
    max_dataset_mb: int
    active_model: str | None


def _aman(nama: str) -> str:
    """Nama run yang aman dipakai sebagai bagian nama berkas.

    Titik ikut dibuang, bukan hanya pemisah path: nama tanpa pemisah pun tidak
    ada gunanya mengandung "..", dan membuangnya menutup seluruh kelas
    kekeliruan penyusunan path sekaligus.
    """
    bersih = re.sub(r"[^A-Za-z0-9_-]+", "-", nama.strip())[:64].strip("-")
    return bersih or "training"


def _model_aktif(db: Session, settings: Settings) -> str | None:
    berkas = app_settings.effective_settings(db, settings).model_file
    return berkas.name if berkas else None


def _ke_out(run: models.TrainingRun, aktif_path: str | None) -> TrainingRunOut:
    return TrainingRunOut(
        **{k: getattr(run, k) for k in TrainingRunOut.model_fields if k != "is_active"},
        is_active=bool(run.weights_path and run.weights_path == aktif_path),
    )


@router.get("/config", response_model=TrainingConfigOut)
def config(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _: models.User = Depends(auth.current_user),
) -> TrainingConfigOut:
    """Apa yang boleh diisi di formulir, dan apakah mesinnya siap."""
    return TrainingConfigOut(
        configured=settings.training_enabled,
        base_models=BASE_MODELS,
        max_epochs=300,
        max_dataset_mb=MAX_DATASET_MB,
        active_model=_model_aktif(db, settings),
    )


@router.post("", response_model=TrainingRunOut, status_code=status.HTTP_202_ACCEPTED)
async def mulai_training(
    dataset: UploadFile = File(...),
    epochs: int = Form(50),
    base_model: str = Form("yolov8m.pt"),
    run_name: str = Form(""),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    pengguna: models.User = Depends(auth.current_user),
) -> TrainingRunOut:
    """Kirim dataset ke mesin GPU dan mulai training di latar belakang."""
    if base_model not in BASE_MODELS:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Model dasar tidak dikenal. Pilihan: {', '.join(BASE_MODELS)}.",
        )
    if not 1 <= epochs <= 300:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Jumlah epoch harus antara 1 dan 300."
        )
    nama_berkas = dataset.filename or ""
    if not nama_berkas.lower().endswith(".zip"):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Dataset harus berupa berkas .zip dalam format YOLOv8.",
        )

    isi = await dataset.read()
    if len(isi) > MAX_DATASET_MB * 1024 * 1024:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"Dataset melebihi batas {MAX_DATASET_MB} MB.",
        )
    if not isi:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Berkas dataset kosong.")

    nama = _aman(run_name or f"sawit-{datetime.now(timezone.utc):%Y%m%d-%H%M}")
    hasil = await training_engine.start(
        settings,
        dataset_bytes=isi,
        dataset_filename=nama_berkas,
        epochs=epochs,
        base_model=base_model,
        run_name=nama,
    )

    run = models.TrainingRun(
        job_id=hasil["job_id"],
        run_name=hasil.get("run_name", nama),
        base_model=base_model,
        epochs=epochs,
        dataset_filename=nama_berkas,
        status=hasil.get("status", "queued"),
        started_by=pengguna.username,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    logger.info("Training dimulai: job=%s oleh %s", run.job_id, pengguna.username)
    return _ke_out(run, app_settings.get(db, app_settings.MODEL_PATH))


@router.get("/runs", response_model=list[TrainingRunOut])
def daftar_run(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _: models.User = Depends(auth.current_user),
) -> list[TrainingRunOut]:
    """Riwayat training, terbaru dulu."""
    runs = db.scalars(
        select(models.TrainingRun).order_by(models.TrainingRun.created_at.desc()).limit(50)
    ).all()
    aktif = app_settings.get(db, app_settings.MODEL_PATH)
    return [_ke_out(r, aktif) for r in runs]


def _run(db: Session, job_id: str) -> models.TrainingRun:
    run = db.scalar(select(models.TrainingRun).where(models.TrainingRun.job_id == job_id))
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Training tidak ditemukan.")
    return run


@router.get("/{job_id}/status", response_model=TrainingStatusOut)
async def status_training(
    job_id: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _: models.User = Depends(auth.current_user),
) -> TrainingStatusOut:
    """Progres terkini, ditanyakan langsung ke mesin training.

    Hasilnya sekaligus disalin ke database, sehingga run yang sudah selesai tetap
    punya angka akhir walaupun catatan sementara di Modal sudah hilang.
    """
    run = _run(db, job_id)

    # Run yang sudah selesai tidak perlu ditanyakan lagi — catatan di Modal Dict
    # tidak permanen, dan menanyakannya hanya menambah latensi.
    if run.status in {"done", "failed"}:
        return TrainingStatusOut(
            job_id=job_id,
            status=run.status,
            epoch=run.last_epoch,
            total_epochs=run.epochs,
            latest={"map50": run.final_map50, "map50_95": run.final_map50_95},
            error=run.error,
            run_name=run.run_name,
            is_active=bool(
                run.weights_path
                and run.weights_path == app_settings.get(db, app_settings.MODEL_PATH)
            ),
        )

    catatan = await training_engine.status_of(settings, job_id)
    status_baru = catatan.get("status", run.status)

    run.status = status_baru
    run.last_epoch = catatan.get("epoch") or run.last_epoch
    if status_baru == "done":
        akhir = catatan.get("final") or catatan.get("latest") or {}
        run.final_map50 = akhir.get("map50")
        run.final_map50_95 = akhir.get("map50_95")
        run.finished_at = datetime.now(timezone.utc)
    elif status_baru == "failed":
        run.error = catatan.get("error")
        run.finished_at = datetime.now(timezone.utc)
    db.commit()

    return TrainingStatusOut(
        job_id=job_id,
        status=status_baru,
        epoch=catatan.get("epoch"),
        total_epochs=catatan.get("total_epochs", run.epochs),
        history=catatan.get("history", []),
        latest=catatan.get("latest"),
        error=catatan.get("error"),
        run_name=run.run_name,
    )


@router.post("/{job_id}/activate", response_model=TrainingRunOut)
async def jadikan_aktif(
    job_id: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    pengguna: models.User = Depends(auth.current_user),
) -> TrainingRunOut:
    """Unduh best.pt dan jadikan model yang dipakai seluruh aplikasi.

    Bobot disimpan di sebelah model lain, lalu penunjuknya dicatat di
    app_settings. Berlaku pada analisis berikutnya, tanpa restart container.
    """
    run = _run(db, job_id)
    if run.status != "done":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Training belum selesai (status: {run.status}).",
        )

    isi = await training_engine.download_weights(settings, job_id)
    if not isi:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Bobot yang diunduh kosong.")

    # Di dalam volume storage, BUKAN di backend/models: folder itu di-mount
    # read-only di produksi supaya model yang diserahkan klien tidak dapat
    # tertimpa dari aplikasi.
    folder = settings.storage_path / "models"
    folder.mkdir(parents=True, exist_ok=True)
    tujuan = folder / f"{_aman(run.run_name)}-{job_id}.pt"

    # Ditulis ke berkas sementara lalu dipindahkan: kalau proses mati di tengah
    # unduhan, model aktif tidak pernah menunjuk ke berkas yang separuh jadi.
    sementara = tujuan.with_suffix(".pt.part")
    sementara.write_bytes(isi)
    sementara.replace(tujuan)

    app_settings.set_value(db, app_settings.MODEL_PATH, str(tujuan))
    run.weights_path = str(tujuan)
    run.activated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(run)

    logger.info(
        "Model aktif diganti ke %s (job=%s) oleh %s", tujuan.name, job_id, pengguna.username
    )
    return _ke_out(run, str(tujuan))
