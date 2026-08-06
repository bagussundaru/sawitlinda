"""Endpoint evaluasi terhadap anotasi ground truth.

Membandingkan deteksi yang tersimpan di sistem dengan anotasi acuan, lalu
menghitung mAP@50, presisi/recall/F1 per kelas, dan confusion matrix.

Hasilnya disimpan bersama keadaan sistem saat itu (mock atau model sungguhan),
supaya angka yang dihasilkan mock tidak pernah tertukar dengan angka model.
"""

from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from PIL import Image as PILImage
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app import models, schemas
from app.config import Settings, get_settings
from app.db import get_db
from app.evaluation import parsers
from app.evaluation.metrics import Prediction, evaluate

router = APIRouter(prefix="/api", tags=["evaluation"])

MAX_ANNOTATION_MB = 32


def _image_sizes(images: list[models.Image]) -> dict[str, tuple[int, int]]:
    """Ukuran piksel tiap citra, untuk mengubah koordinat YOLO jadi piksel."""
    ukuran: dict[str, tuple[int, int]] = {}
    for image in images:
        try:
            with PILImage.open(image.storage_path) as berkas:
                ukuran[Path(image.filename).stem.lower()] = berkas.size
        except Exception:
            # Citra yang berkasnya hilang tidak bisa dievaluasi; lewati saja.
            continue
    return ukuran


def _to_out(row: models.Evaluation) -> schemas.EvaluationOut:
    return schemas.EvaluationOut(
        id=row.id,
        created_at=row.created_at,
        source_filename=row.source_filename,
        iou_threshold=row.iou_threshold,
        inference_mode=row.inference_mode,
        model_name=row.model_name,
        images=row.images,
        ground_truths=row.ground_truths,
        predictions=row.predictions,
        map50=row.map50,
        micro_precision=row.micro_precision,
        micro_recall=row.micro_recall,
        micro_f1=row.micro_f1,
        per_class=[schemas.ClassMetricsOut(**m) for m in row.per_class],
        confusion=row.confusion,
    )


@router.post(
    "/evaluate",
    response_model=schemas.EvaluationOut,
    status_code=status.HTTP_201_CREATED,
)
def run_evaluation(
    file: UploadFile = File(..., description="Ekspor YOLOv8 (.zip) atau COCO (.json)"),
    iou_threshold: float = Form(0.5, ge=0.05, le=0.95),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> schemas.EvaluationOut:
    """Bandingkan deteksi tersimpan dengan anotasi ground truth yang diunggah."""
    data = file.file.read(MAX_ANNOTATION_MB * 1024 * 1024 + 1)
    if len(data) > MAX_ANNOTATION_MB * 1024 * 1024:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"Berkas anotasi melebihi batas {MAX_ANNOTATION_MB} MB.",
        )

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
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Belum ada citra yang dianalisis. Unggah dan analisis citra terlebih dahulu.",
        )

    sizes = _image_sizes(images)
    try:
        ground_truths = parsers.parse(file.filename or "", data, sizes)
    except parsers.AnnotationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    # Hanya citra yang punya anotasi yang boleh ikut dihitung. Menyertakan citra
    # tanpa anotasi akan menjadikan seluruh deteksinya positif palsu dan menekan
    # presisi secara keliru.
    beranotasi = {g.image for g in ground_truths}

    # Satu berkas anotasi hanya boleh dipasangkan dengan SATU citra. Bila berkas
    # dengan nama sama diunggah lebih dari sekali, deteksinya akan terhitung
    # berlipat dan presisi anjlok tanpa sebab. Yang dipakai unggahan terbaru.
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
        source_filename=file.filename or "(tanpa nama)",
        iou_threshold=iou_threshold,
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

    return _to_out(row)


@router.get("/evaluations", response_model=list[schemas.EvaluationOut])
def list_evaluations(db: Session = Depends(get_db)) -> list[schemas.EvaluationOut]:
    """Riwayat evaluasi, terbaru dulu."""
    rows = (
        db.execute(select(models.Evaluation).order_by(models.Evaluation.created_at.desc()))
        .scalars()
        .all()
    )
    return [_to_out(row) for row in rows]


@router.get("/evaluations/{evaluation_id}", response_model=schemas.EvaluationOut)
def get_evaluation(
    evaluation_id: UUID, db: Session = Depends(get_db)
) -> schemas.EvaluationOut:
    row = db.get(models.Evaluation, evaluation_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Evaluasi tidak ditemukan.")
    return _to_out(row)
