"""Inference dengan model YOLOv8 terlatih.

Dipakai begitu `MODEL_PATH` menunjuk ke berkas model yang ada. Tanpa itu, sistem
tetap memakai generator mock — lihat `engine.py`.

DUA HAL YANG BUKAN KELUARAN MODEL, dan karena itu ditandai jelas:

1. **Keparahan.** Model ini detektor 4 kelas; ia tidak punya kepala keparahan.
   Dataset klien juga belum memuat label keparahan. Nilai `severity` karena itu
   diturunkan dari aturan tetap di bawah, bukan diprediksi. `GET /api/system`
   melaporkannya sebagai `severity_source: "rule"` supaya tidak pernah dikira
   hasil pengukuran.

2. **Koordinat per pohon.** Model mengembalikan kotak dalam piksel. Mengubahnya
   menjadi lintang/bujur memerlukan skala tanah (meter per piksel), yang tidak
   ada di dalam citra. Skala dihitung dari luas area yang diisi operator saat
   mengunggah. Bila luas tidak diisi, deteksi sengaja TIDAK diberi koordinat —
   lebih baik peta kosong daripada titik yang salah tempat.
"""

from __future__ import annotations

import logging
import math
import os
import threading
from pathlib import Path

# Ultralytics secara bawaan memasang paket yang kurang lewat internet SAAT
# inference berjalan. Di produksi itu berarti satu permintaan bisa memicu
# instalasi paket, gagal karena tidak ada jaringan, lalu menahan respons.
# Dimatikan sebelum modulnya diimpor.
os.environ.setdefault("YOLO_AUTOINSTALL", "false")
os.environ.setdefault("ULTRALYTICS_AUTOINSTALL", "false")
# Jangan kirim statistik pemakaian dari server klien.
os.environ.setdefault("YOLO_OFFLINE", "true")

from app.inference.conditions import BY_KEY, CLASS_LABELS

logger = logging.getLogger("sawitscan.yolo")

#: Ambang keyakinan minimum. Di bawah ini deteksi dibuang.
CONF_THRESHOLD = 0.25
#: Ambang IoU untuk non-maximum suppression.
IOU_THRESHOLD = 0.45

METRES_PER_DEG_LAT = 111_320.0

#: Keparahan per kondisi — ATURAN, bukan keluaran model.
#:
#: `dead` selalu berat karena tanaman mati adalah kasus terparah dan tidak
#: diperdebatkan. `yellow` ringan karena defisiensi hara umumnya masih dapat
#: dipulihkan lewat pemupukan. `small` sedang karena pertumbuhan terhambat
#: bersifat kronis tapi belum darurat. Ganti aturan ini begitu klien menyediakan
#: label keparahan yang sebenarnya.
SEVERITY_RULE = {
    "healthy": "sehat",
    "yellow": "ringan",
    "small": "sedang",
    "dead": "berat",
}

_model = None
_model_path: str | None = None
_lock = threading.Lock()


class ModelError(RuntimeError):
    """Model tidak dapat dimuat atau dijalankan."""


def load(model_path: str):
    """Muat model sekali, lalu pakai ulang.

    Memuat ulang tiap permintaan akan menghabiskan beberapa detik dan ratusan MB
    berulang kali. Dikunci karena uvicorn melayani permintaan dari beberapa thread.
    """
    global _model, _model_path

    with _lock:
        if _model is not None and _model_path == model_path:
            return _model

        if not Path(model_path).is_file():
            raise ModelError(f"Berkas model tidak ditemukan: {model_path}")

        try:
            from ultralytics import YOLO
        except ImportError as exc:  # pragma: no cover - hanya bila paket hilang
            raise ModelError(
                "Paket 'ultralytics' belum terpasang di lingkungan ini."
            ) from exc

        logger.info("Memuat model dari %s", model_path)
        try:
            _model = YOLO(model_path)
        except Exception as exc:
            raise ModelError(f"Gagal memuat model: {exc}") from exc
        _model_path = model_path

        tak_dikenal = [n for n in _model.names.values() if n not in CLASS_LABELS]
        if tak_dikenal:
            logger.warning(
                "Model memuat kelas di luar daftar sistem: %s. "
                "Deteksi berkelas itu akan diabaikan.",
                ", ".join(sorted(tak_dikenal)),
            )

        return _model


def _ground_scale(
    width_px: int, height_px: int, area_ha: float | None
) -> tuple[float, float] | None:
    """Meter per piksel pada sumbu x dan y, dari luas area yang dicakup citra.

    Luas dianggap mencakup seluruh bingkai. Rasio sisi bingkai dipakai untuk
    membagi luas itu menjadi lebar dan tinggi dalam meter.
    """
    if not area_ha or area_ha <= 0 or width_px <= 0 or height_px <= 0:
        return None

    luas_m2 = area_ha * 10_000.0
    rasio = width_px / height_px
    lebar_m = math.sqrt(luas_m2 * rasio)
    tinggi_m = luas_m2 / lebar_m
    return lebar_m / width_px, tinggi_m / height_px


def run(
    image_path: str,
    gps: tuple[float, float] | None = None,
    area_ha: float | None = None,
    model_path: str = "",
) -> dict:
    """Jalankan deteksi dan kembalikan payload sesuai kontrak JSON."""
    model = load(model_path)

    try:
        hasil = model.predict(
            source=image_path,
            conf=CONF_THRESHOLD,
            iou=IOU_THRESHOLD,
            verbose=False,
        )
    except Exception as exc:
        raise ModelError(f"Inference gagal: {exc}") from exc

    if not hasil:
        return {"detections": []}

    frame = hasil[0]
    tinggi_px, lebar_px = frame.orig_shape
    skala = _ground_scale(lebar_px, tinggi_px, area_ha)

    detections = []
    for kotak in frame.boxes:
        kelas = model.names.get(int(kotak.cls.item()))
        if kelas not in CLASS_LABELS:
            # Kelas asing tidak diteruskan ke UI; sudah dicatat saat memuat model.
            continue

        x1, y1, x2, y2 = (float(v) for v in kotak.xyxy[0].tolist())
        w, h = x2 - x1, y2 - y1

        titik = None
        if gps is not None and skala is not None:
            lat, lng = gps
            m_per_px_x, m_per_px_y = skala
            # Geser dari titik tengah citra, dalam meter, lalu ke derajat.
            dx_m = (x1 + w / 2 - lebar_px / 2) * m_per_px_x
            dy_m = (y1 + h / 2 - tinggi_px / 2) * m_per_px_y
            m_per_deg_lng = METRES_PER_DEG_LAT * math.cos(math.radians(lat))
            titik = {
                "lat": lat - dy_m / METRES_PER_DEG_LAT,
                "lng": lng + dx_m / max(m_per_deg_lng, 1.0),
            }

        detections.append(
            {
                "bbox": [round(x1, 1), round(y1, 1), round(w, 1), round(h, 1)],
                "condition": BY_KEY[kelas].label,
                "severity": SEVERITY_RULE[kelas],
                "confidence": round(float(kotak.conf.item()), 3),
                "gps": titik,
            }
        )

    return {"detections": detections}
