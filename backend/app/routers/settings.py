"""Pengaturan yang diisi operator lewat aplikasi.

Dipakai untuk kunci API, supaya nilainya tidak perlu dituliskan ke berkas mana
pun di repositori. Kunci hanya bisa DIKIRIM, tidak pernah dibaca kembali.

PERINGATAN yang juga ditampilkan di layar: aplikasi ini belum punya autentikasi.
Selama itu belum ada, siapa pun yang dapat membuka alamatnya dapat mengganti
kunci di sini. Batasi aksesnya di reverse proxy sampai autentikasi dibangun.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import schemas
from app.config import Settings, get_settings
from app.db import get_db
from app.services import app_settings

router = APIRouter(prefix="/api/settings", tags=["settings"])

logger = logging.getLogger("sawitscan")


class NebiusKeyIn(BaseModel):
    api_key: str = Field(min_length=8, max_length=4096)
    #: Kosongkan untuk mempertahankan model yang sedang dipakai.
    model: str | None = Field(default=None, max_length=128)


class RoboflowKeyIn(BaseModel):
    api_key: str = Field(min_length=8, max_length=512)


class NebiusModelIn(BaseModel):
    model: str = Field(min_length=1, max_length=128)


def _status(db: Session, settings: Settings) -> schemas.AiSettingsOut:
    dari_db = app_settings.get(db, app_settings.NEBIUS_KEY)
    dari_env = settings.nebius_api_key.strip() or None
    berlaku = dari_db or dari_env
    model = app_settings.get(db, app_settings.NEBIUS_MODEL) or settings.nebius_model

    return schemas.AiSettingsOut(
        configured=bool(berlaku),
        source="aplikasi" if dari_db else ("environment" if dari_env else None),
        key_hint=app_settings.mask(berlaku),
        model=model,
    )


@router.get("/ai", response_model=schemas.AiSettingsOut)
def get_ai_settings(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> schemas.AiSettingsOut:
    """Keadaan lapisan analisis AI. Kunci tidak pernah ikut dikembalikan."""
    return _status(db, settings)


@router.put("/ai", response_model=schemas.AiSettingsOut)
def set_ai_key(
    body: NebiusKeyIn,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> schemas.AiSettingsOut:
    """Simpan kunci Nebius. Berlaku seketika, tanpa restart container."""
    if not body.api_key.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Kunci tidak boleh kosong.")

    app_settings.set_value(db, app_settings.NEBIUS_KEY, body.api_key)
    if body.model and body.model.strip():
        app_settings.set_value(db, app_settings.NEBIUS_MODEL, body.model)
    return _status(db, settings)


@router.put("/ai/model", response_model=schemas.AiSettingsOut)
def set_ai_model(
    body: NebiusModelIn,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> schemas.AiSettingsOut:
    """Ganti model yang dipakai tanpa menyentuh kunci.

    Tidak semua model menerima gambar. Bila model yang dipilih hanya menerima
    teks, penilaian tetap dibuat — dari ringkasan deteksi, bukan dari citra —
    dan hasilnya ditandai supaya perbedaannya tidak tersamar.
    """
    app_settings.set_value(db, app_settings.NEBIUS_MODEL, body.model.strip())
    return _status(db, settings)


@router.delete("/ai", response_model=schemas.AiSettingsOut)
def clear_ai_key(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> schemas.AiSettingsOut:
    """Hapus kunci yang tersimpan di aplikasi.

    Nilai dari environment, bila ada, kembali berlaku setelah ini.
    """
    app_settings.clear(db, app_settings.NEBIUS_KEY)
    return _status(db, settings)


# --- Roboflow ---------------------------------------------------------------
#
# Kunci dipakai menarik versi dataset langsung dari Roboflow, sehingga citra dan
# anotasinya tidak perlu diunggah manual. Sama seperti kunci Nebius: dikirim
# sekali, tidak pernah dapat dibaca kembali lewat aplikasi.

ROBOFLOW_KEY = "roboflow_api_key"


class RoboflowSettingsOut(BaseModel):
    configured: bool
    key_hint: str | None = None


def _roboflow_status(db: Session) -> RoboflowSettingsOut:
    nilai = app_settings.get(db, ROBOFLOW_KEY)
    return RoboflowSettingsOut(configured=bool(nilai), key_hint=app_settings.mask(nilai))


@router.get("/roboflow", response_model=RoboflowSettingsOut)
def get_roboflow_settings(db: Session = Depends(get_db)) -> RoboflowSettingsOut:
    return _roboflow_status(db)


@router.put("/roboflow", response_model=RoboflowSettingsOut)
def set_roboflow_key(
    body: RoboflowKeyIn, db: Session = Depends(get_db)
) -> RoboflowSettingsOut:
    app_settings.set_value(db, ROBOFLOW_KEY, body.api_key)
    return _roboflow_status(db)


@router.delete("/roboflow", response_model=RoboflowSettingsOut)
def clear_roboflow_key(db: Session = Depends(get_db)) -> RoboflowSettingsOut:
    app_settings.clear(db, ROBOFLOW_KEY)
    return _roboflow_status(db)
