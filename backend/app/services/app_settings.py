"""Pengaturan yang dapat diubah saat aplikasi berjalan.

Menyediakan tempat bagi nilai rahasia — kunci API — untuk diisi operator lewat
layar Pengaturan, tanpa pernah masuk ke repositori maupun berkas `.env` yang
di-commit.

Aturan yang dipegang di sini:

- **Nilai rahasia tidak pernah dikembalikan.** Yang keluar hanya keterangan
  sudah terisi atau belum, beserta empat karakter terakhir sebagai penanda —
  cukup untuk memastikan kunci yang benar sedang dipakai, tidak cukup untuk
  memakainya.
- **Nilai dari database menimpa environment.** Jadi kunci yang diisi lewat layar
  langsung berlaku tanpa restart container.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app import models
from app.config import Settings

logger = logging.getLogger("sawitscan")

NEBIUS_KEY = "nebius_api_key"


def get(db: Session, key: str) -> str | None:
    row = db.get(models.AppSetting, key)
    nilai = (row.value if row else "").strip()
    return nilai or None


def set_value(db: Session, key: str, value: str) -> None:
    bersih = value.strip()
    row = db.get(models.AppSetting, key)
    if row is None:
        db.add(models.AppSetting(key=key, value=bersih))
    else:
        row.value = bersih
    db.commit()
    # Jangan pernah mencatat nilainya, hanya peristiwanya.
    logger.info("Pengaturan '%s' diperbarui lewat aplikasi", key)


def clear(db: Session, key: str) -> bool:
    row = db.get(models.AppSetting, key)
    if row is None:
        return False
    db.delete(row)
    db.commit()
    logger.info("Pengaturan '%s' dihapus lewat aplikasi", key)
    return True


def mask(value: str | None) -> str | None:
    """Penanda pendek untuk memastikan kunci yang benar dipakai."""
    if not value:
        return None
    return f"…{value[-4:]}" if len(value) > 4 else "…"


def effective_settings(db: Session, settings: Settings) -> Settings:
    """Settings dengan nilai dari database ditimpakan di atas environment.

    Dikembalikan sebagai salinan, bukan diubah di tempat: objek Settings
    di-cache lewat lru_cache dan dipakai bersama seluruh permintaan.
    """
    kunci = get(db, NEBIUS_KEY)
    if not kunci:
        return settings
    return settings.model_copy(update={"nebius_api_key": kunci})
