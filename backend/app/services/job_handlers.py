"""Isi pekerjaan latar.

Dipisahkan dari antreannya (app/services/jobs.py) supaya lapisan antrean tidak
perlu tahu apa pun tentang inference, Roboflow, atau evaluasi.
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.config import get_settings
from app.inference.engine import run_inference
from app.services import app_settings, evaluation_run, jobs, roboflow

logger = logging.getLogger("sawitscan.jobs")

ROBOFLOW_KEY = "roboflow_api_key"


def _settings(db: Session):
    """Settings dengan nilai dari database ditimpakan di atas environment."""
    return app_settings.effective_settings(db, get_settings())


def _analyse(db: Session, image: models.Image, settings) -> int:
    """Jalankan inference pada satu citra dan simpan hasilnya."""
    gps = None
    if image.gps_lat is not None and image.gps_lng is not None:
        gps = (image.gps_lat, image.gps_lng)

    hasil = run_inference(image.storage_path, gps, image.area_ha, settings=settings)

    image.detections.clear()
    db.flush()
    for d in hasil["detections"]:
        x, y, w, h = d["bbox"]
        image.detections.append(
            models.Detection(
                bbox_x=x,
                bbox_y=y,
                bbox_w=w,
                bbox_h=h,
                condition=d["condition"],
                severity=d["severity"],
                confidence=d["confidence"],
                gps_lat=(d["gps"] or {}).get("lat"),
                gps_lng=(d["gps"] or {}).get("lng"),
            )
        )
    image.status = "analyzed"
    db.commit()
    return len(hasil["detections"])


@jobs.register("reanalyse")
def reanalyse(db: Session, job: models.Job) -> dict:
    """Jalankan ulang inference pada citra yang sudah ada.

    Diperlukan setiap kali model atau cara pemrosesannya berubah — angka lama
    tidak ikut berubah sendiri, dan membiarkannya bercampur dengan angka baru
    membuat dashboard tidak dapat dibaca.
    """
    settings = _settings(db)
    hanya_id = job.payload.get("image_ids")

    kueri = select(models.Image).order_by(models.Image.created_at)
    if hanya_id:
        kueri = kueri.where(models.Image.id.in_([uuid.UUID(i) for i in hanya_id]))

    citra = db.scalars(kueri).all()
    total = len(citra)
    pohon = 0
    gagal = 0

    for i, image in enumerate(citra, start=1):
        jobs.set_progress(db, job.id, i - 1, total, f"Analysing {image.filename}")
        try:
            pohon += _analyse(db, image, settings)
        except Exception:  # noqa: BLE001 — satu citra rusak tidak boleh menghentikan sisanya
            logger.exception("Analisis ulang gagal untuk %s", image.filename)
            db.rollback()
            gagal += 1

    jobs.set_progress(db, job.id, total, total, "Finished")
    return {"images": total, "detections": pohon, "failed": gagal}


@jobs.register("roboflow_evaluate")
def roboflow_evaluate(db: Session, job: models.Job) -> dict:
    """Tarik satu versi dataset dari Roboflow, analisis, lalu evaluasi.

    Menggantikan dua unggahan manual sekaligus. Karena citra dan anotasinya
    berasal dari arsip yang sama, nama berkasnya pasti cocok — kegagalan paling
    sering pada alur unggah tidak dapat terjadi di sini.
    """
    settings = _settings(db)
    kunci = app_settings.get(db, ROBOFLOW_KEY)
    if not kunci:
        raise roboflow.RoboflowError(
            "Kunci API Roboflow belum diisi. Tambahkan di layar Settings."
        )

    p = job.payload
    workspace, project = p["workspace"], p["project"]
    version, split = int(p["version"]), p.get("split", "test")
    iou = float(p.get("iou_threshold", 0.5))

    jobs.set_progress(db, job.id, 0, 0, "Downloading dataset from Roboflow")
    arsip = roboflow.download_version(kunci, workspace, project, version)

    citra_zip = roboflow.read_split(arsip, split)
    total = len(citra_zip)
    jobs.set_progress(db, job.id, 0, total, f"{total} images downloaded")

    penyimpanan = settings.storage_path
    sudah_ada = {
        Path(f).stem.lower(): image
        for image, f in db.execute(
            select(models.Image, models.Image.filename)
        ).all()
    }

    label_versi = f"{project} v{version} · {split}"
    dianalisis = 0

    for i, (nama, isi) in enumerate(citra_zip, start=1):
        jobs.set_progress(db, job.id, i - 1, total, f"Analysing {nama}")
        stem = Path(nama).stem.lower()

        image = sudah_ada.get(stem)
        if image is None:
            image_id = uuid.uuid4()
            tujuan = penyimpanan / f"{image_id}{Path(nama).suffix.lower()}"
            tujuan.write_bytes(isi)
            image = models.Image(
                id=image_id,
                filename=nama,
                storage_path=str(tujuan),
                label=label_versi,
                status="uploaded",
            )
            db.add(image)
            db.commit()
            db.refresh(image)

        try:
            _analyse(db, image, settings)
            dianalisis += 1
        except Exception:  # noqa: BLE001
            logger.exception("Analisis gagal untuk %s", nama)
            db.rollback()

    jobs.set_progress(db, job.id, total, total, "Computing metrics")
    hasil = evaluation_run.run(
        db,
        settings,
        annotation_filename="roboflow.zip",
        annotation_bytes=roboflow.labels_only(arsip),
        iou_threshold=iou,
        # Nomor versi dicatat, bukan nama berkas sementara: inilah yang membuat
        # evaluasi dapat diulang orang lain.
        source_label=f"roboflow:{workspace}/{project}/v{version}/{split}",
    )

    jobs.set_progress(db, job.id, total, total, "Finished")
    return {
        "evaluation_id": str(hasil.id),
        "images_analysed": dianalisis,
        "map50": hasil.map50,
        "micro_f1": hasil.micro_f1,
        "dataset": f"{workspace}/{project} v{version} ({split})",
    }
