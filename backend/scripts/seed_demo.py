"""Isi sistem dengan data demo yang meyakinkan.

Membuat beberapa blok kebun, masing-masing dipotret dalam beberapa bingkai UAV
yang BERSEBELAHAN — sehingga titik di peta membentuk hamparan kebun, bukan
segerombol titik di satu tempat.

Setiap bingkai dibuat dengan EXIF GPS dan waktu pemotretan sungguhan, jadi
alur ekstraksi metadata ikut teruji seperti pada citra drone asli.

    python scripts/seed_demo.py                  # ke server lokal :8000
    python scripts/seed_demo.py --url http://... # ke server lain
    python scripts/seed_demo.py --reset          # hanya cetak cara mengosongkan

Aman diulang: setiap kali dijalankan menambah sortie baru, tidak menimpa.
"""

from __future__ import annotations

import argparse
import io
import math
import random
import sys
from datetime import datetime, timedelta
from fractions import Fraction

import httpx
from PIL import Image

#: Titik acuan kebun (Riau). Tiap blok digeser dari sini.
ORIGIN_LAT, ORIGIN_LNG = -0.78912, 101.41233
METRES_PER_DEG_LAT = 111_320.0

#: Satu bingkai UAV mencakup kira-kira sepetak 70 x 45 m pada ketinggian kerja.
FRAME_W_M, FRAME_H_M = 70.0, 45.0

BLOCKS = [
    # (nama blok, kolom x baris bingkai, luas ha, geser timur (m), geser utara (m))
    ("A-1", 3, 2, 12.4, 0, 0),
    ("A-2", 3, 2, 11.8, 240, 0),
    ("B-1", 2, 2, 8.6, 0, -180),
    ("B-2", 3, 1, 6.2, 210, -180),
    ("C-1", 2, 2, 9.1, 430, -90),
]


def dms(value: float):
    value = abs(value)
    degrees = int(value)
    minutes = int((value - degrees) * 60)
    seconds = (value - degrees - minutes / 60) * 3600
    return (Fraction(degrees), Fraction(minutes), Fraction(round(seconds * 100), 100))


def frame_bytes(seed: int, lat: float, lng: float, taken: datetime) -> bytes:
    """Bingkai UAV tiruan: hamparan hijau bertekstur, ber-EXIF GPS & waktu.

    Bukan foto sungguhan — hanya agar ukuran, metadata, dan alur unggahnya
    menyerupai citra drone.
    """
    rnd = random.Random(seed)
    img = Image.new("RGB", (1600, 1200), "#3f6b3c")
    px = img.load()
    for _ in range(60_000):
        x, y = rnd.randrange(1600), rnd.randrange(1200)
        px[x, y] = (
            rnd.randint(38, 92),
            rnd.randint(88, 152),
            rnd.randint(36, 84),
        )

    meta = Image.Exif()
    meta[0x0132] = taken.strftime("%Y:%m:%d %H:%M:%S")
    meta[0x010F] = "DJI"
    meta[0x0110] = "FC7303"
    meta[0x8825] = {
        1: "S" if lat < 0 else "N",
        2: dms(lat),
        3: "W" if lng < 0 else "E",
        4: dms(lng),
    }

    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=88, exif=meta)
    return buffer.getvalue()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument(
        "--ai",
        action="store_true",
        help="Jalankan juga analisis AI tiap citra (butuh NEBIUS_API_KEY di server)",
    )
    args = parser.parse_args()
    base = args.url.rstrip("/")

    client = httpx.Client(timeout=180.0, verify=False)
    try:
        client.get(f"{base}/health").raise_for_status()
    except Exception as exc:  # noqa: BLE001 — pesan ramah lebih berguna di sini
        print(f"Tidak bisa menghubungi {base}: {exc}", file=sys.stderr)
        return 1

    sortie = datetime(2026, 7, 21, 7, 40)
    nomor = 4100
    total_citra = total_pohon = 0

    for block, cols, rows, area_ha, east_m, north_m in BLOCKS:
        m_per_deg_lng = METRES_PER_DEG_LAT * math.cos(math.radians(ORIGIN_LAT))
        print(f"\n{block} — {cols * rows} bingkai, {area_ha} ha")

        for row in range(rows):
            for col in range(cols):
                # Bingkai bersebelahan dengan tumpang tindih kecil, seperti
                # jalur terbang drone yang sebenarnya.
                dx = east_m + col * FRAME_W_M * 0.92
                dy = north_m - row * FRAME_H_M * 0.92
                lat = ORIGIN_LAT + dy / METRES_PER_DEG_LAT
                lng = ORIGIN_LNG + dx / m_per_deg_lng

                nomor += 1
                name = f"DJI_{nomor}.JPG"
                sortie += timedelta(seconds=8)

                data = frame_bytes(nomor, lat, lng, sortie)
                unggah = client.post(
                    f"{base}/api/upload",
                    files={"files": (name, data, "image/jpeg")},
                    data={"block": block, "area_ha": str(area_ha / (cols * rows))},
                )
                unggah.raise_for_status()
                image_id = unggah.json()["images"][0]["image_id"]

                hasil = client.post(f"{base}/api/analyze/{image_id}")
                hasil.raise_for_status()
                ringkas = hasil.json()["summary"]
                total_citra += 1
                total_pohon += ringkas["total"]
                print(
                    f"  {name}  {ringkas['total']:>3} pohon"
                    f"  ·  {ringkas['infected']:>2} bermasalah"
                    f"  ·  {ringkas['severe']:>2} berat"
                )

                if args.ai:
                    ai = client.post(f"{base}/api/analyze/{image_id}/ai")
                    if ai.status_code == 200:
                        print(f"        AI: {ai.json()['ai']['dominant_condition']}")
                    else:
                        print(f"        AI dilewati: {ai.status_code}")

    print(f"\nSelesai: {total_citra} citra, {total_pohon} pohon di {len(BLOCKS)} blok.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
