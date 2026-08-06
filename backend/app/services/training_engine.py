"""Klien untuk mesin training YOLOv8 di Modal.

Satu-satunya tempat aplikasi berbicara dengan Modal. Token bearer tidak pernah
meninggalkan proses ini — peramban hanya melihat hasilnya, tidak pernah kuncinya.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from fastapi import HTTPException, status

from app.config import Settings

logger = logging.getLogger("sawitscan")


class EngineError(Exception):
    """Mesin training tidak dapat dihubungi atau menolak permintaan."""


def _base(settings: Settings) -> str:
    if not settings.training_enabled:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Mesin training belum dikonfigurasi. Isi MODAL_TRAINING_URL dan "
            "MODAL_TRAINING_TOKEN di server.",
        )
    return settings.modal_training_url.rstrip("/")


def _headers(settings: Settings) -> dict[str, str]:
    return {"Authorization": f"Bearer {settings.modal_training_token.strip()}"}


def _terjemahkan(exc: httpx.HTTPStatusError) -> HTTPException:
    """Ubah galat dari Modal menjadi pesan yang berarti bagi operator."""
    kode = exc.response.status_code
    try:
        pesan = exc.response.json().get("detail")
    except Exception:  # noqa: BLE001
        pesan = None

    if kode == 401:
        return HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "Mesin training menolak token. Periksa MODAL_TRAINING_TOKEN.",
        )
    if kode == 404:
        return HTTPException(status.HTTP_404_NOT_FOUND, "Job training tidak ditemukan.")
    if kode == 409:
        return HTTPException(status.HTTP_409_CONFLICT, pesan or "Training belum selesai.")
    if 400 <= kode < 500:
        return HTTPException(status.HTTP_400_BAD_REQUEST, pesan or "Permintaan ditolak mesin training.")
    return HTTPException(
        status.HTTP_502_BAD_GATEWAY, pesan or f"Mesin training gagal (HTTP {kode})."
    )


async def start(
    settings: Settings,
    *,
    dataset_bytes: bytes,
    dataset_filename: str,
    epochs: int,
    base_model: str,
    run_name: str,
) -> dict[str, Any]:
    """Kirim dataset dan mulai training. Kembali segera dengan job_id."""
    try:
        async with httpx.AsyncClient(timeout=settings.modal_timeout_s) as client:
            respons = await client.post(
                f"{_base(settings)}/train",
                headers=_headers(settings),
                files={"dataset": (dataset_filename, dataset_bytes, "application/zip")},
                data={
                    "epochs": str(epochs),
                    "base_model": base_model,
                    "run_name": run_name,
                },
            )
            respons.raise_for_status()
            return respons.json()
    except httpx.HTTPStatusError as exc:
        raise _terjemahkan(exc) from exc
    except httpx.HTTPError as exc:
        logger.exception("Gagal menghubungi mesin training")
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "Mesin training tidak dapat dihubungi. Periksa apakah Modal app sudah di-deploy.",
        ) from exc


async def status_of(settings: Settings, job_id: str) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            respons = await client.get(
                f"{_base(settings)}/train/{job_id}/status", headers=_headers(settings)
            )
            respons.raise_for_status()
            return respons.json()
    except httpx.HTTPStatusError as exc:
        raise _terjemahkan(exc) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, "Mesin training tidak dapat dihubungi."
        ) from exc


async def download_weights(settings: Settings, job_id: str) -> bytes:
    """Ambil best.pt. Berkas model YOLOv8m sekitar 50 MB."""
    try:
        async with httpx.AsyncClient(timeout=settings.modal_timeout_s) as client:
            respons = await client.get(
                f"{_base(settings)}/train/{job_id}/weights", headers=_headers(settings)
            )
            respons.raise_for_status()
            return respons.content
    except httpx.HTTPStatusError as exc:
        raise _terjemahkan(exc) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, "Gagal mengunduh bobot dari mesin training."
        ) from exc
