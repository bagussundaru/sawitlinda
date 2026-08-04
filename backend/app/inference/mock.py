"""Mock detection generator.

Stands in for the trained model until it is delivered. Output is deterministic per
image so that re-analysing the same file gives a stable result during demos.

Dibuat menyerupai kebun sungguhan dalam dua hal yang paling kelihatan di layar:

1. **Tata tanam.** Kelapa sawit ditanam pada pola segitiga sama sisi berjarak
   ~9 m, bukan kisi persegi. Barisnya berselang-seling setengah langkah.
2. **Persoalan mengelompok.** Defisiensi hara dan kematian pohon mengikuti
   kondisi tanah dan drainase, jadi muncul sebagai bercak, bukan tersebar acak.
   Titik acak seragam langsung terlihat palsu begitu diplot di peta.

Nothing outside `engine.py` should import this module.
"""

import hashlib
import math
import random
from pathlib import Path

from PIL import Image

from app.inference.conditions import AFFECTED_CLASSES, CLASS_LABELS, HEALTHY_CLASS

#: Jarak tanam kelapa sawit yang lazim: segitiga sama sisi 9 m.
SPACING_M = 9.0
#: Jarak antarbaris pada pola segitiga = 9 · sin(60°).
ROW_SPACING_M = SPACING_M * math.sin(math.pi / 3)

#: Satu bingkai UAV pada ketinggian kerja mencakup petak sebesar ini.
MIN_COLS, MAX_COLS = 6, 9
MIN_ROWS, MAX_ROWS = 4, 7

#: Bagian pohon yang bermasalah di luar bercak — kebun sehat pun tidak nol.
BASE_AFFECTED = 0.04
#: Peluang tambahan di pusat bercak.
#:
#: Disetel agar rata-rata sekitar 18% pohon bermasalah dan 6% berat — kebun yang
#: perlu perhatian tapi belum gawat. Nilai lebih tinggi membuat hampir seluruh
#: bingkai memerah dan justru terbaca tidak masuk akal.
FOCUS_STRENGTH = 0.55
#: Radius bercak dalam meter. Harus jauh lebih kecil dari lebar bingkai (~70 m),
#: kalau tidak bercaknya menutup seluruh petak dan pola mengelompoknya hilang.
FOCUS_RADIUS_M = 10.0

DEFAULT_IMAGE_SIZE = (4000, 3000)

METRES_PER_DEG_LAT = 111_320.0


def _image_size(image_path: str) -> tuple[int, int]:
    try:
        with Image.open(image_path) as img:
            return img.size
    except Exception:
        return DEFAULT_IMAGE_SIZE


def _seed_for(image_path: str) -> int:
    # hashlib rather than hash(): the latter is salted per process, which would
    # make a re-analysis after a restart return a different result.
    digest = hashlib.sha256(Path(image_path).stem.encode()).digest()
    return int.from_bytes(digest[:4], "big")


def _severity_for(condition: str, intensity: float, rng: random.Random) -> str:
    """Keparahan mengikuti kedekatan ke pusat bercak.

    Pengganti sementara kepala keparahan Swin + MTL. Pohon mati selalu berat;
    sisanya memburuk saat makin dekat ke pusat persoalan.
    """
    if condition == HEALTHY_CLASS:
        return "sehat"
    if condition == "dead":
        return "berat"
    if intensity > 0.66:
        return rng.choices(["sedang", "berat"], weights=[4, 6])[0]
    if intensity > 0.33:
        return rng.choices(["ringan", "sedang"], weights=[5, 5])[0]
    return "ringan"


def _foci(rng: random.Random, cols: int, rows: int) -> list[tuple[float, float]]:
    """Satu sampai tiga pusat persoalan, dalam koordinat meter."""
    count = rng.choices([1, 2, 3], weights=[5, 4, 2])[0]
    return [
        (
            rng.uniform(0, (cols - 1) * SPACING_M),
            rng.uniform(0, (rows - 1) * ROW_SPACING_M),
        )
        for _ in range(count)
    ]


def _intensity(x_m: float, y_m: float, foci: list[tuple[float, float]]) -> float:
    """Seberapa dalam sebuah titik berada di dalam bercak, 0..1."""
    terkuat = 0.0
    for fx, fy in foci:
        jarak = math.hypot(x_m - fx, y_m - fy)
        nilai = math.exp(-(jarak**2) / (2 * FOCUS_RADIUS_M**2))
        terkuat = max(terkuat, nilai)
    return terkuat


def generate(image_path: str, gps: tuple[float, float] | None = None) -> dict:
    """Produce a detection payload for one image.

    `gps` is the image centre from EXIF, used to scatter plausible per-tree
    coordinates around it. Without it, detections carry no coordinates.
    """
    rng = random.Random(_seed_for(image_path))
    width, height = _image_size(image_path)

    cols = rng.randint(MIN_COLS, MAX_COLS)
    rows = rng.randint(MIN_ROWS, MAX_ROWS)
    foci = _foci(rng, cols, rows)

    # Petak yang tercakup, dalam meter, dipakai untuk memetakan meter -> piksel.
    span_x_m = max((cols - 1) * SPACING_M, 1.0) + SPACING_M
    span_y_m = max((rows - 1) * ROW_SPACING_M, 1.0) + ROW_SPACING_M

    # Tajuk dewasa berdiameter ~7 m; kotaknya sedikit lebih longgar.
    box_w = width * (7.5 / span_x_m)
    box_h = height * (7.5 / span_y_m)

    detections = []
    for row in range(rows):
        # Pola segitiga: baris ganjil bergeser setengah langkah.
        offset = SPACING_M / 2 if row % 2 else 0.0
        for col in range(cols):
            x_m = col * SPACING_M + offset + rng.gauss(0, 0.35)
            y_m = row * ROW_SPACING_M + rng.gauss(0, 0.35)

            intensity = _intensity(x_m, y_m, foci)
            peluang = BASE_AFFECTED + FOCUS_STRENGTH * intensity

            if rng.random() < peluang:
                # Di pusat bercak, pohon mati lebih mungkin; di tepinya menguning.
                bobot = [3, 1, 2] if intensity > 0.6 else [6, 1, 3]
                condition = rng.choices(AFFECTED_CLASSES, weights=bobot)[0]
            else:
                condition = HEALTHY_CLASS

            severity = _severity_for(condition, intensity, rng)

            # Meter -> piksel, lalu dijaga tetap di dalam bingkai.
            cx = (x_m + SPACING_M / 2) / span_x_m * width
            cy = (y_m + ROW_SPACING_M / 2) / span_y_m * height
            x = min(max(cx - box_w / 2, 0.0), width - box_w)
            y = min(max(cy - box_h / 2, 0.0), height - box_h)

            detection_gps = None
            if gps is not None:
                lat, lng = gps
                # Meter -> derajat, relatif terhadap titik tengah citra.
                dx_m = x_m - span_x_m / 2
                dy_m = y_m - span_y_m / 2
                metres_per_deg_lng = METRES_PER_DEG_LAT * math.cos(math.radians(lat))
                detection_gps = {
                    "lat": lat - dy_m / METRES_PER_DEG_LAT,
                    "lng": lng + dx_m / max(metres_per_deg_lng, 1.0),
                }

            # Pohon sehat terbaca lebih yakin daripada yang bermasalah — itu pola
            # yang wajar pada detektor sungguhan.
            confidence = (
                rng.uniform(0.88, 0.98)
                if condition == HEALTHY_CLASS
                else rng.uniform(0.71, 0.93)
            )

            detections.append(
                {
                    "bbox": [round(x, 1), round(y, 1), round(box_w, 1), round(box_h, 1)],
                    "condition": CLASS_LABELS[condition],
                    "severity": severity,
                    "confidence": round(confidence, 2),
                    "gps": detection_gps,
                }
            )

    return {"detections": detections}
