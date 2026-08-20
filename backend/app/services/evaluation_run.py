"""Menjalankan satu evaluasi terhadap anotasi acuan.

Dipisahkan dari router agar dipakai dua jalur — unggahan berkas dan penarikan
dari Roboflow — tanpa menggandakan aturannya. Dua salinan aturan evaluasi akan
berbeda begitu salah satunya disunting, dan angka disertasi lalu bergantung pada
jalur mana yang kebetulan dipakai.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image as PILImage
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app import models
from app.config import Settings
from app.evaluation.metrics import Prediction, evaluate
from app.evaluation.parsers import parse

logger = logging.getLogger("sawitscan.evaluation")


class NoAnalysedImages(Exception):
    """Tidak ada citra yang sudah dianalisis untuk dibandingkan."""


def image_sizes(images: list[models.Image]) -> dict[str, tuple[int, int]]:
    """Ukuran piksel tiap citra, dikunci nama berkas tanpa ekstensi.

    Dibutuhkan karena koordinat YOLO ternormalisasi 0..1 dan hanya dapat
    dikembalikan ke piksel bila ukuran aslinya diketahui.
    """
    ukuran: dict[str, tuple[int, int]] = {}
    for image in images:
        try:
            with PILImage.open(image.storage_path) as berkas:
                ukuran[Path(image.filename).stem.lower()] = berkas.size
        except OSError:
            # Berkas hilang dari penyimpanan; citranya cukup dilewati, bukan
            # menggagalkan seluruh evaluasi.
            logger.warning("Citra tidak terbaca saat evaluasi: %s", image.filename)
    return ukuran


def run(
    db: Session,
    settings: Settings,
    *,
    annotation_filename: str,
    annotation_bytes: bytes,
    iou_threshold: float,
    source_label: str | None = None,
) -> models.Evaluation:
    """Hitung metrik dan simpan hasilnya.

    `source_label` menggantikan nama berkas pada catatan hasil — dipakai jalur
    Roboflow untuk mencatat versi dataset, bukan nama berkas sementara.
    """
    images = (
        db.execute(
            select(models.Image)
            .where(models.Image.status == "analyzed")
            .options(selectinload(models.Image.detections))
        )
        .scalars()
        .all()
    )
    if not images:
        raise NoAnalysedImages(
            "Belum ada citra yang dianalisis. Unggah dan analisis citra terlebih dahulu."
        )

    ground_truths = parse(annotation_filename, annotation_bytes, image_sizes(images))

    # Hanya citra yang punya anotasi yang boleh ikut dihitung. Menyertakan citra
    # tanpa anotasi akan menjadikan seluruh deteksinya positif palsu dan menekan
    # presisi secara keliru.
    beranotasi = {g.image for g in ground_truths}

    # Satu berkas anotasi hanya boleh dipasangkan dengan SATU citra. Bila berkas
    # dengan nama sama diunggah lebih dari sekali, deteksinya terhitung berlipat
    # dan presisi anjlok tanpa sebab. Yang dipakai unggahan terbaru.
    terpilih: dict[str, models.Image] = {}
    for image in sorted(images, key=lambda i: i.created_at):
        stem = Path(image.filename).stem.lower()
        if stem in beranotasi:
            terpilih[stem] = image

    predictions = [
        Prediction(
            box=(d.bbox_x, d.bbox_y, d.bbox_w, d.bbox_h),
            label=d.condition,
            confidence=d.confidence,
            image=stem,
        )
        for stem, image in terpilih.items()
        for d in image.detections
    ]

    hasil = evaluate(predictions, ground_truths, iou_threshold=iou_threshold)

    model_path = settings.model_file
    loaded = bool(model_path and model_path.is_file())

    row = models.Evaluation(
        source_filename=(source_label or annotation_filename or "(tanpa nama)")[:255],
        iou_threshold=iou_threshold,
        # Keadaan sistem saat evaluasi dijalankan, supaya angka mock tidak pernah
        # tertukar dengan angka model sungguhan di kemudian hari.
        inference_mode="model" if loaded else "mock",
        model_name=model_path.name if loaded and model_path else None,
        images=hasil.images,
        ground_truths=len(ground_truths),
        predictions=len(predictions),
        map50=hasil.map50,
        micro_precision=hasil.micro_precision,
        micro_recall=hasil.micro_recall,
        micro_f1=hasil.micro_f1,
        per_class=[vars(m) for m in hasil.per_class],
        confusion=hasil.confusion,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
