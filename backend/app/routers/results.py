import logging
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, selectinload

from app import mappers, models, schemas
from app.config import Settings, get_settings
from app.db import get_db
from app.inference import nebius
from app.inference.engine import run_inference
from app.services import app_settings

router = APIRouter(prefix="/api", tags=["results"])

logger = logging.getLogger("sawitscan")


def _get_image(db: Session, image_id: UUID) -> models.Image:
    image = db.execute(
        select(models.Image)
        .where(models.Image.id == image_id)
        .options(selectinload(models.Image.detections))
    ).scalar_one_or_none()
    if image is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Citra tidak ditemukan.")
    return image


def require_analyzed_image(db: Session, image_id: UUID) -> models.Image:
    """Fetch an image that has results, or fail with a message the user can act on."""
    image = _get_image(db, image_id)
    if image.status != "analyzed":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Citra belum dianalisis. Jalankan /api/analyze/{image_id} terlebih dahulu.",
        )
    return image


@router.post("/analyze/{image_id}", response_model=schemas.DetectionResult)
def analyze_image(
    image_id: UUID,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> schemas.DetectionResult:
    """Run inference on an uploaded image and persist the detections.

    Re-analysing replaces previous detections, so a swapped-in model can be applied
    to images already in the system.
    """
    image = _get_image(db, image_id)

    gps = None
    if image.gps_lat is not None and image.gps_lng is not None:
        gps = (image.gps_lat, image.gps_lng)

    # Settings dari database: berkas model dapat diganti lewat layar Training
    # tanpa restart container.
    result = run_inference(
        image.storage_path,
        gps,
        image.area_ha,
        settings=app_settings.effective_settings(db, settings),
    )

    image.detections.clear()
    for item in result["detections"]:
        x, y, w, h = item["bbox"]
        point = item.get("gps") or {}
        image.detections.append(
            models.Detection(
                bbox_x=x,
                bbox_y=y,
                bbox_w=w,
                bbox_h=h,
                condition=item["condition"],
                severity=item["severity"],
                confidence=item["confidence"],
                gps_lat=point.get("lat"),
                gps_lng=point.get("lng"),
            )
        )
    image.status = "analyzed"
    db.commit()
    db.refresh(image)

    return mappers.detection_result(image)


@router.post("/analyze/{image_id}/ai", response_model=schemas.DetectionResult)
def ai_review(
    image_id: UUID,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> schemas.DetectionResult:
    """Minta penilaian tingkat citra dari model vision.

    Terpisah dari /analyze karena panggilan ke penyedia AI memakan waktu beberapa
    detik dan bisa gagal; deteksi per pohon tidak boleh ikut tertahan olehnya.
    """
    # Kunci yang diisi lewat layar Pengaturan menimpa nilai dari environment.
    settings = app_settings.effective_settings(db, settings)
    if not settings.ai_enabled:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Analisis AI belum dikonfigurasi. Isi kunci Nebius di layar Pengaturan.",
        )

    image = require_analyzed_image(db, image_id)

    ringkasan = mappers.summarise(image.detections)
    per_kondisi: dict[str, int] = {}
    for d in image.detections:
        per_kondisi[d.condition] = per_kondisi.get(d.condition, 0) + 1

    try:
        hasil = nebius.assess_image(
            image.storage_path,
            settings,
            summary={**ringkasan.model_dump(), "per_kondisi": per_kondisi},
        )
    except nebius.NebiusError as exc:
        logger.warning("Analisis AI gagal untuk %s: %s", image_id, exc)
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            f"Analisis AI gagal: {exc}",
        ) from exc

    image.ai_summary = hasil.summary
    image.ai_recommendation = hasil.recommendation
    image.ai_dominant_condition = hasil.dominant_condition
    image.ai_confidence = hasil.confidence
    image.ai_affected_share = hasil.affected_share
    image.ai_notes = "\n".join(hasil.notes)
    image.ai_model = f"{hasil.model} ({hasil.mode})" if hasil.mode == "teks" else hasil.model
    image.ai_created_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(image)

    return mappers.detection_result(image)


#: Kolom yang boleh dipakai mengurutkan. Daftar tertutup: nilai dari klien tidak
#: pernah menjadi bagian kueri, hanya menjadi kunci pencarian di peta ini.
SORT_COLUMNS = {"created_at", "label", "captured_at", "trees", "affected"}

MAX_PAGE = 200


@router.get("/results", response_model=schemas.ResultPage)
def list_results(
    q: str | None = Query(None, description="Cari pada label atau nama berkas"),
    status_filter: str | None = Query(
        None, alias="status", description="uploaded | analyzed"
    ),
    sort: str = Query("created_at", description=f"Salah satu dari: {sorted(SORT_COLUMNS)}"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    limit: int = Query(50, ge=1, le=MAX_PAGE),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> schemas.ResultPage:
    """Riwayat unggahan, satu halaman sekaligus.

    Ringkasan per citra dihitung lewat agregasi SQL, bukan dengan memuat seluruh
    baris deteksi. Cara lama memuat setiap pohon dari setiap citra hanya untuk
    menghitungnya — pada 187 citra itu berarti 15.422 baris per permintaan, dan
    pada ribuan citra tidak lagi dapat dipakai.
    """
    if sort not in SORT_COLUMNS:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Pengurutan tidak dikenal. Pilihan: {', '.join(sorted(SORT_COLUMNS))}.",
        )

    ringkas = (
        select(
            models.Detection.image_id.label("image_id"),
            func.count().label("total"),
            func.sum(case((models.Detection.severity == "sehat", 1), else_=0)).label("healthy"),
            func.sum(case((models.Detection.severity == "berat", 1), else_=0)).label("severe"),
        )
        .group_by(models.Detection.image_id)
        .subquery()
    )

    saring = []
    if q and q.strip():
        kunci = q.strip().lower()
        saring.append(
            func.lower(
                func.coalesce(models.Image.label, models.Image.filename)
            ).contains(kunci)
        )
    if status_filter in {"uploaded", "analyzed"}:
        saring.append(models.Image.status == status_filter)

    total = db.scalar(
        select(func.count()).select_from(models.Image).where(*saring)
    ) or 0

    jumlah_pohon = func.coalesce(ringkas.c.total, 0)
    jumlah_bermasalah = func.coalesce(ringkas.c.total, 0) - func.coalesce(ringkas.c.healthy, 0)
    kolom = {
        "created_at": models.Image.created_at,
        # coalesce: citra tanpa label diurutkan memakai nama berkasnya, bukan
        # menggumpal di ujung daftar.
        "label": func.lower(func.coalesce(models.Image.label, models.Image.filename)),
        "captured_at": models.Image.captured_at,
        "trees": jumlah_pohon,
        "affected": jumlah_bermasalah,
    }[sort]
    arah = kolom.desc() if order == "desc" else kolom.asc()

    baris = db.execute(
        select(
            models.Image,
            ringkas.c.total,
            ringkas.c.healthy,
            ringkas.c.severe,
        )
        .outerjoin(ringkas, ringkas.c.image_id == models.Image.id)
        .where(*saring)
        # Kunci kedua yang unik: tanpa ini, baris dengan nilai urut sama dapat
        # bertukar tempat antarhalaman dan satu citra muncul dua kali.
        .order_by(arah, models.Image.id)
        .limit(limit)
        .offset(offset)
    ).all()

    items = [
        schemas.ResultListItem(
            **mappers.image_out(image).model_dump(),
            summary=schemas.Summary(
                total=jml or 0,
                healthy=sehat or 0,
                infected=(jml or 0) - (sehat or 0),
                severe=berat or 0,
            )
            if image.status == "analyzed"
            else None,
        )
        for image, jml, sehat, berat in baris
    ]

    return schemas.ResultPage(items=items, total=total, limit=limit, offset=offset)


@router.get("/images/{image_id}/file", response_class=FileResponse)
def get_image_file(image_id: UUID, db: Session = Depends(get_db)) -> FileResponse:
    """Serve the stored image itself, so the results screen can draw boxes over it."""
    image = _get_image(db, image_id)
    path = Path(image.storage_path)
    if not path.is_file():
        raise HTTPException(
            status.HTTP_410_GONE, "Berkas citra tidak lagi tersedia di penyimpanan."
        )
    return FileResponse(path, filename=image.filename)


@router.get("/results/{image_id}", response_model=schemas.DetectionResult)
def get_result(image_id: UUID, db: Session = Depends(get_db)) -> schemas.DetectionResult:
    return mappers.detection_result(require_analyzed_image(db, image_id))
