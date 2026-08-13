"""Sebaran spasial citra: peta dan pengelompokan per desa.

Penanda dipasang per CITRA, bukan per pohon. Koordinat per pohon memerlukan
skala tanah (meter per piksel) yang hanya dapat diturunkan dari luas area yang
dicakup bingkai — nilai yang tidak lagi diminta saat unggah. Koordinat citra dari
EXIF sebaliknya benar-benar terukur oleh drone.

Untuk 187 citra berisi belasan ribu pohon, penanda per citra juga lebih terbaca
daripada titik yang bertumpuk di satu tempat.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app import models, schemas, villages
from app.db import get_db

router = APIRouter(prefix="/api", tags=["spatial"])


def _ringkas_deteksi():
    """Subkueri jumlah pohon per citra, dihitung di database."""
    return (
        select(
            models.Detection.image_id.label("image_id"),
            func.count().label("total"),
            func.sum(case((models.Detection.severity == "sehat", 1), else_=0)).label("healthy"),
            func.sum(case((models.Detection.severity == "berat", 1), else_=0)).label("severe"),
        )
        .group_by(models.Detection.image_id)
        .subquery()
    )


@router.get("/villages", response_model=list[schemas.VillageInfo])
def list_villages(db: Session = Depends(get_db)) -> list[schemas.VillageInfo]:
    """Kelima desa contoh beserta berapa banyak citra yang tercatat di sana.

    Daftarnya tetap lengkap walau sebuah desa belum punya citra — desa yang
    hilang dari layar akan terbaca seolah tidak termasuk penelitian.
    """
    ringkas = _ringkas_deteksi()
    baris = db.execute(
        select(
            models.Image.village,
            func.count(func.distinct(models.Image.id)),
            func.count(func.distinct(
                case((models.Image.status == "analyzed", models.Image.id))
            )),
            func.coalesce(func.sum(ringkas.c.total), 0),
            func.coalesce(func.sum(ringkas.c.total - ringkas.c.healthy), 0),
        )
        .outerjoin(ringkas, ringkas.c.image_id == models.Image.id)
        .group_by(models.Image.village)
    ).all()

    hitung = {
        kunci: (citra, dianalisis, int(pohon), int(bermasalah))
        for kunci, citra, dianalisis, pohon, bermasalah in baris
    }

    return [
        schemas.VillageInfo(
            key=v.key,
            name=v.name,
            district=v.district,
            lat=v.lat,
            lng=v.lng,
            images=hitung.get(v.key, (0, 0, 0, 0))[0],
            analyzed=hitung.get(v.key, (0, 0, 0, 0))[1],
            trees=hitung.get(v.key, (0, 0, 0, 0))[2],
            affected=hitung.get(v.key, (0, 0, 0, 0))[3],
        )
        for v in villages.VILLAGES
    ]


@router.get("/map", response_model=list[schemas.MapImagePoint])
def list_map_points(
    village: str | None = Query(None, description="Batasi ke satu desa"),
    db: Session = Depends(get_db),
) -> list[schemas.MapImagePoint]:
    """Citra yang punya koordinat, siap digambar sebagai penanda.

    Citra tanpa koordinat sengaja tidak dikembalikan: menempatkannya di titik
    tengah wilayah akan terlihat seperti data survei padahal bukan.
    """
    ringkas = _ringkas_deteksi()
    saring = [
        models.Image.gps_lat.is_not(None),
        models.Image.gps_lng.is_not(None),
        models.Image.status == "analyzed",
    ]
    if village:
        saring.append(models.Image.village == village)

    baris = db.execute(
        select(
            models.Image,
            func.coalesce(ringkas.c.total, 0),
            func.coalesce(ringkas.c.healthy, 0),
            func.coalesce(ringkas.c.severe, 0),
        )
        .outerjoin(ringkas, ringkas.c.image_id == models.Image.id)
        .where(*saring)
        .order_by(models.Image.created_at.desc())
        .limit(2000)
    ).all()

    titik = []
    for image, total, sehat, berat in baris:
        total, sehat, berat = int(total), int(sehat), int(berat)
        bermasalah = total - sehat

        dominan = db.scalar(
            select(models.Detection.condition)
            .where(models.Detection.image_id == image.id)
            .group_by(models.Detection.condition)
            .order_by(func.count().desc())
            .limit(1)
        )

        titik.append(
            schemas.MapImagePoint(
                image_id=image.id,
                filename=image.filename,
                label=image.label,
                village=image.village,
                captured_at=image.captured_at,
                gps=schemas.Gps(lat=image.gps_lat, lng=image.gps_lng),
                summary=schemas.Summary(
                    total=total, healthy=sehat, infected=bermasalah, severe=berat
                ),
                dominant_condition=dominan,
                affected_share=(bermasalah / total) if total else 0.0,
            )
        )
    return titik
