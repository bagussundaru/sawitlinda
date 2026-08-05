"""The single point of contact between the web app and the AI model.

Every other module calls `run_inference()` and nothing else. Swapping the trained
model (.pt / ONNX) means editing the body of this function only — the signature and
the returned payload shape must not change. See docs/SWAP_MODEL.md.
"""

import logging

from app.config import get_settings
from app.inference import mock, yolo

logger = logging.getLogger("sawitscan")


def model_is_available() -> bool:
    """Apakah berkas model terlatih benar-benar ada di tempatnya."""
    berkas = get_settings().model_file
    return bool(berkas and berkas.is_file())


def run_inference(
    image_path: str,
    gps: tuple[float, float] | None = None,
    area_ha: float | None = None,
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
    settings = get_settings()

    if model_is_available():
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
