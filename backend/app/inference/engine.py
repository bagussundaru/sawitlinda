"""The single point of contact between the web app and the AI model.

Every other module calls `run_inference()` and nothing else. Swapping the trained
model (.pt / ONNX) means editing the body of this function only — the signature and
the returned payload shape must not change. See docs/SWAP_MODEL.md.
"""

import logging

from app.config import Settings, get_settings
from app.inference import mock, yolo

logger = logging.getLogger("sawitscan")


def _settings(settings: Settings | None) -> Settings:
    """Settings yang dipakai: yang diberikan pemanggil, atau dari environment.

    Pemanggil memberikan salinan yang sudah ditimpa nilai dari database, karena
    berkas model dapat diganti lewat tombol "Jadikan Model Aktif" tanpa restart.
    """
    return settings or get_settings()


def model_is_available(settings: Settings | None = None) -> bool:
    """Apakah berkas model terlatih benar-benar ada di tempatnya."""
    berkas = _settings(settings).model_file
    return bool(berkas and berkas.is_file())


def engine_status(settings: Settings | None = None) -> tuple[str, str | None]:
    """Mesin mana yang benar-benar akan dipakai, dan kenapa kalau bukan model.

    Memeriksa keberadaan berkas saja tidak cukup: berkas model bisa ada sementara
    mesinnya tidak dapat dimuat — pustaka sistem kurang, berkas rusak, paket
    hilang. Melaporkan "model" dalam keadaan itu menyembunyikan kegagalan di
    balik status yang terlihat sehat.

    Mengembalikan ("model" | "mock", pesan galat bila ada).
    """
    settings = _settings(settings)
    if not model_is_available(settings):
        return "mock", None
    try:
        yolo.load(str(settings.model_file))
    except yolo.ModelError as exc:
        return "mock", str(exc)
    return "model", None


def run_inference(
    image_path: str,
    gps: tuple[float, float] | None = None,
    area_ha: float | None = None,
    settings: Settings | None = None,
) -> dict:
    """Detect and classify palm trees in one image.

    Returns ``{"detections": [...]}`` where each detection carries `bbox`, `condition`,
    `severity`, `confidence` and `gps` — the model-derived half of the JSON contract
    in CLAUDE.md. Identity fields (`image_id`, `filename`, `captured_at`) and the
    `summary` are added by the caller, which owns that data; the model cannot know them.

    `gps` adalah titik tengah citra dari EXIF; `area_ha` luas yang dicakup citra,
    dipakai untuk mengubah posisi piksel menjadi koordinat.

    Model terlatih dipakai bila `MODEL_PATH` menunjuk ke berkas yang ada. Kalau
    tidak, generator mock yang dipakai — sistem tetap berjalan penuh, dan
    `GET /api/system` melaporkan mana yang sedang aktif.

    Kegagalan model tidak dibiarkan menjatuhkan permintaan: sistem turun ke mock
    dan mencatatnya di log, supaya satu berkas model yang rusak tidak membuat
    seluruh aplikasi tak dapat dipakai.
    """
    settings = _settings(settings)

    if model_is_available(settings):
        try:
            return yolo.run(
                image_path,
                gps=gps,
                area_ha=area_ha,
                model_path=str(settings.model_file),
            )
        except yolo.ModelError:
            logger.exception("Model gagal dijalankan, kembali memakai mock")

    return mock.generate(image_path, gps)
