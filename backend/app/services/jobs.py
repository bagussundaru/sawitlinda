"""Antrean pekerjaan latar.

Pekerjaan yang memakan menit — menganalisis ratusan citra, menarik dataset dari
Roboflow — tidak boleh menahan satu permintaan HTTP. Reverse proxy memutus pada
300 detik, dan pengguna tidak punya cara mengetahui apakah pekerjaannya masih
berjalan atau sudah mati.

RANCANGAN: satu tabel di PostgreSQL, satu thread pekerja di dalam container
backend. Tanpa Redis, tanpa container tambahan — VM ini berbagi dengan aplikasi
lain dan disknya sudah padat. Beban aplikasi ini pun satu operator dengan
pekerjaan berurutan.

Pengambilan pekerjaan memakai `UPDATE … WHERE status='queued' … RETURNING`
dalam satu pernyataan, sehingga tetap benar bila kelak dijalankan lebih dari
satu proses: dua pekerja tidak akan pernah mengambil baris yang sama.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Callable

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app import models
from app.db import SessionLocal

logger = logging.getLogger("sawitscan.jobs")

#: Jeda saat antrean kosong. Cukup cepat agar terasa langsung jalan, cukup
#: lambat agar tidak membebani database yang dipakai bersama.
POLL_SECONDS = 2.0

#: kind -> fungsi penjalan. Diisi oleh modul yang mendaftarkan pekerjaannya
#: sendiri, supaya modul ini tidak perlu tahu apa pun tentang isi pekerjaan.
HANDLERS: dict[str, Callable[[Session, models.Job], dict]] = {}

_worker: threading.Thread | None = None
_stop = threading.Event()


def register(kind: str):
    """Daftarkan penjalan untuk satu jenis pekerjaan."""

    def bungkus(fn: Callable[[Session, models.Job], dict]):
        HANDLERS[kind] = fn
        return fn

    return bungkus


# --- Antrean ----------------------------------------------------------------
def enqueue(
    db: Session, kind: str, payload: dict, created_by: str | None = None
) -> models.Job:
    if kind not in HANDLERS:
        raise ValueError(f"Jenis pekerjaan tidak dikenal: {kind}")
    job = models.Job(
        kind=kind,
        payload=payload,
        progress={"current": 0, "total": 0, "message": "Queued"},
        created_by=created_by,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    logger.info("Pekerjaan diantrekan: %s (%s)", kind, job.id)
    return job


def active(db: Session, kind: str | None = None) -> models.Job | None:
    """Pekerjaan yang sedang antre atau berjalan, bila ada.

    Dipakai untuk mencegah dua pekerjaan berat berjalan bersamaan di VM yang
    berbagi dengan aplikasi lain.
    """
    kueri = select(models.Job).where(models.Job.status.in_(("queued", "running")))
    if kind:
        kueri = kueri.where(models.Job.kind == kind)
    return db.scalars(kueri.order_by(models.Job.created_at)).first()


def _claim(db: Session) -> models.Job | None:
    """Ambil satu pekerjaan antre dan tandai berjalan, dalam satu pernyataan."""
    calon = db.scalars(
        select(models.Job.id)
        .where(models.Job.status == "queued")
        .order_by(models.Job.created_at)
        .limit(1)
    ).first()
    if calon is None:
        return None

    hasil = db.execute(
        update(models.Job)
        .where(models.Job.id == calon, models.Job.status == "queued")
        .values(status="running", started_at=datetime.now(timezone.utc))
        .returning(models.Job.id)
    ).first()
    db.commit()
    if hasil is None:
        return None  # pekerja lain lebih dulu
    return db.get(models.Job, calon)


def set_progress(db: Session, job_id: uuid.UUID, current: int, total: int, message: str):
    """Perbarui progres. Dipanggil sering, jadi sengaja ringan."""
    db.execute(
        update(models.Job)
        .where(models.Job.id == job_id)
        .values(progress={"current": current, "total": total, "message": message})
    )
    db.commit()


def _finish(db: Session, job: models.Job, result: dict):
    job.status = "done"
    job.result = result
    job.finished_at = datetime.now(timezone.utc)
    db.commit()


def _fail(db: Session, job: models.Job, exc: BaseException):
    job.status = "failed"
    job.error = f"{type(exc).__name__}: {exc}"[:2000]
    job.finished_at = datetime.now(timezone.utc)
    db.commit()


def reset_interrupted() -> int:
    """Tandai gagal pekerjaan yang tertinggal berstatus "running".

    Dipanggil saat aplikasi start. Pekerjaan berstatus running setelah restart
    berarti prosesnya mati di tengah jalan — dan tidak ada cara mengetahui
    sejauh mana ia sempat berjalan. Membiarkannya "running" selamanya membuat
    layar memutar spinner tanpa akhir; mengantrekannya ulang secara membabi buta
    bisa mengerjakan dua kali hal yang tidak boleh diulang.
    """
    with SessionLocal() as db:
        hasil = db.execute(
            update(models.Job)
            .where(models.Job.status == "running")
            .values(
                status="failed",
                error="Terputus karena aplikasi dijalankan ulang.",
                finished_at=datetime.now(timezone.utc),
            )
            .returning(models.Job.id)
        ).all()
        db.commit()
        if hasil:
            logger.warning("%d pekerjaan tertinggal ditandai gagal", len(hasil))
        return len(hasil)


# --- Pekerja ----------------------------------------------------------------
def _loop():
    logger.info("Pekerja latar berjalan")
    while not _stop.is_set():
        try:
            with SessionLocal() as db:
                job = _claim(db)
                if job is None:
                    _stop.wait(POLL_SECONDS)
                    continue

                logger.info("Menjalankan pekerjaan %s (%s)", job.kind, job.id)
                mulai = time.monotonic()
                try:
                    hasil = HANDLERS[job.kind](db, job)
                    _finish(db, job, hasil)
                    logger.info(
                        "Pekerjaan %s selesai dalam %.1fs", job.id, time.monotonic() - mulai
                    )
                except Exception as exc:  # noqa: BLE001 — kegagalan apa pun harus tercatat
                    logger.exception("Pekerjaan %s gagal", job.id)
                    _fail(db, job, exc)
        except Exception:  # noqa: BLE001
            # Kegagalan pada lapisan antrean sendiri — mis. database sedang tak
            # terjangkau. Dicatat lalu dicoba lagi; pekerja tidak boleh mati.
            logger.exception("Pekerja latar bermasalah; mencoba lagi")
            _stop.wait(POLL_SECONDS * 3)


def start():
    """Nyalakan pekerja. Aman dipanggil dua kali."""
    global _worker
    if _worker is not None and _worker.is_alive():
        return
    _stop.clear()
    _worker = threading.Thread(target=_loop, name="sawitscan-jobs", daemon=True)
    _worker.start()


def stop():
    _stop.set()
