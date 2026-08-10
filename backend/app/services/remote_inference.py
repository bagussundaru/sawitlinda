"""Klien mesin inference GPU di Modal.

Yang dikirim ke sana hanya citra dan daftar ubin; yang kembali hanya kotak
mentah. Seluruh penafsiran — penggabungan NMS, pemetaan kelas ke kondisi,
aturan keparahan, georeferensi — tetap di `app/inference/yolo.py`, sehingga
hasil di layar tidak bergantung pada mesin mana yang kebetulan menjalankannya.
"""

from __future__ import annotations

import hashlib
import json
import logging
from functools import lru_cache
from pathlib import Path

import httpx

from app.config import Settings

logger = logging.getLogger("sawitscan.remote")


class RemoteError(Exception):
    """Mesin GPU tidak dapat dihubungi atau menolak permintaan."""


@lru_cache(maxsize=8)
def model_sha256(path: str, mtime: float, size: int) -> str:
    """sha256 berkas bobot.

    mtime dan size ikut menjadi kunci cache: berkas yang diganti di tempat
    menghasilkan kunci berbeda, sehingga hash lama tidak pernah dipakai untuk
    bobot baru. Menghitung ulang sha 50 MB tiap citra akan sia-sia.
    """
    pencerna = hashlib.sha256()
    with open(path, "rb") as f:
        while potongan := f.read(4 * 1024 * 1024):
            pencerna.update(potongan)
    return pencerna.hexdigest()


def _sha(model_path: str) -> str:
    stat = Path(model_path).stat()
    return model_sha256(model_path, stat.st_mtime, stat.st_size)


def _headers(settings: Settings) -> dict[str, str]:
    return {"Authorization": f"Bearer {settings.modal_inference_token.strip()}"}


def _base(settings: Settings) -> str:
    return settings.modal_inference_url.rstrip("/")


def _unggah_bobot(client: httpx.Client, settings: Settings, model_path: str) -> None:
    logger.info("Mengunggah bobot ke mesin GPU: %s", Path(model_path).name)
    with open(model_path, "rb") as f:
        respons = client.post(
            f"{_base(settings)}/model",
            headers=_headers(settings),
            files={"weights": (Path(model_path).name, f, "application/octet-stream")},
        )
    respons.raise_for_status()


def detect(
    settings: Settings,
    *,
    image_path: str,
    tiles: list[tuple[int, int, int, int]],
    model_path: str,
    imgsz: int,
    conf: float,
    iou: float,
) -> list[tuple[float, float, float, float, str, float]]:
    """Jalankan deteksi di GPU. Mengembalikan kotak dalam koordinat bingkai penuh.

    Bobot diunggah sekali lalu dikenali dari sha256-nya; permintaan berikutnya
    hanya mengirim citra.
    """
    sha = _sha(model_path)
    muatan = {
        "tiles": json.dumps([list(t) for t in tiles]),
        "model_sha": sha,
        "imgsz": str(imgsz),
        "conf": str(conf),
        "iou": str(iou),
    }

    try:
        with httpx.Client(timeout=settings.modal_inference_timeout_s) as client:
            for percobaan in (1, 2):
                with open(image_path, "rb") as f:
                    respons = client.post(
                        f"{_base(settings)}/detect",
                        headers=_headers(settings),
                        files={"image": (Path(image_path).name, f, "image/jpeg")},
                        data=muatan,
                    )
                # 409 berarti bobot belum ada di sana. Diunggah lalu diulang —
                # sekali saja, supaya bobot yang selalu gagal tidak berputar
                # tanpa akhir.
                if respons.status_code == 409 and percobaan == 1:
                    _unggah_bobot(client, settings, model_path)
                    continue
                respons.raise_for_status()
                badan = respons.json()
                return [
                    (float(b[0]), float(b[1]), float(b[2]), float(b[3]), str(b[4]), float(b[5]))
                    for b in badan.get("boxes", [])
                ]
    except httpx.HTTPStatusError as exc:
        raise RemoteError(
            f"Mesin GPU menolak permintaan (HTTP {exc.response.status_code})."
        ) from exc
    except httpx.HTTPError as exc:
        raise RemoteError(f"Mesin GPU tidak dapat dihubungi: {exc}") from exc
    except OSError as exc:
        raise RemoteError(f"Berkas tidak dapat dibaca: {exc}") from exc

    raise RemoteError("Mesin GPU tidak mengembalikan hasil.")
