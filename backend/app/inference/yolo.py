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


class RemoteUnavailable(Exception):
    """Mesin GPU tidak dapat dipakai; deteksi diulang di CPU.

    Dibedakan dari ModelError supaya kegagalan jaringan tidak dilaporkan sebagai
    model yang rusak — keduanya memerlukan tindakan yang berbeda.
    """

#: Ambang keyakinan minimum. Di bawah ini deteksi dibuang.
CONF_THRESHOLD = 0.25
#: Ambang IoU untuk non-maximum suppression.
IOU_THRESHOLD = 0.45

#: Sisi ubin, dalam piksel. Model dilatih pada ubin dataset berukuran 512 px,
#: dan deteksi hanya bekerja bila citra yang masuk berada pada skala yang sama.
TILE_SIZE = 512

#: Tumpang tindih antarubin. Tanpa ini, tajuk yang terpotong garis batas hanya
#: terlihat sebagian di kedua ubin dan luput dari deteksi.
TILE_OVERLAP = 0.25

#: Bingkai yang sisi terpanjangnya melebihi TILE_SIZE sekian kali akan dipotong.
#: Ubin dataset (512 px) berada di bawah ambang ini dan diproses utuh, sehingga
#: angka evaluasi terhadap dataset tidak berubah oleh perubahan ini.
TILE_TRIGGER = 1.5

#: Batas jumlah ubin per citra. Orthomosaic berukuran sangat besar akan
#: menghasilkan ribuan ubin dan menahan satu permintaan berjam-jam; lebih baik
#: menolak dengan jelas daripada tampak menggantung.
MAX_TILES = 400

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


def _tile_boxes(width: int, height: int) -> list[tuple[int, int, int, int]]:
    """Kotak potong yang menutupi seluruh bingkai, saling bertumpang tindih."""
    langkah = max(1, int(TILE_SIZE * (1 - TILE_OVERLAP)))
    kotak = []
    atas = 0
    while True:
        bawah = min(atas + TILE_SIZE, height)
        kiri = 0
        while True:
            kanan = min(kiri + TILE_SIZE, width)
            kotak.append((kiri, atas, kanan, bawah))
            if kanan >= width:
                break
            kiri += langkah
        if bawah >= height:
            break
        atas += langkah
    return kotak


def _nms(deteksi: list[dict], ambang: float = IOU_THRESHOLD) -> list[dict]:
    """Buang kotak yang saling menimpa.

    Diperlukan karena ubin sengaja bertumpang tindih: satu pohon di daerah
    tumpang tindih terdeteksi dua kali, sekali dari tiap ubin.

    Ditulis di sini, bukan memakai NMS milik ultralytics, karena penggabungan
    terjadi SETELAH koordinat tiap ubin dikembalikan ke ruang bingkai penuh —
    ultralytics hanya melihat satu ubin pada satu waktu.
    """
    if not deteksi:
        return []

    urut = sorted(deteksi, key=lambda d: d["_conf"], reverse=True)
    simpan: list[dict] = []
    for calon in urut:
        ax1, ay1, ax2, ay2 = calon["_xyxy"]
        luas_a = (ax2 - ax1) * (ay2 - ay1)
        tumpang = False
        for disimpan in simpan:
            bx1, by1, bx2, by2 = disimpan["_xyxy"]
            ix = max(0.0, min(ax2, bx2) - max(ax1, bx1))
            iy = max(0.0, min(ay2, by2) - max(ay1, by1))
            irisan = ix * iy
            if irisan <= 0:
                continue
            luas_b = (bx2 - bx1) * (by2 - by1)
            if irisan / (luas_a + luas_b - irisan) > ambang:
                tumpang = True
                break
        if not tumpang:
            simpan.append(calon)
    return simpan


def _predict_tiled(model, image_path: str) -> tuple[list[tuple], int, int]:
    """Deteksi pada bingkai besar dengan memotongnya menjadi ubin.

    Mengembalikan (kotak dalam koordinat bingkai penuh, lebar, tinggi).

    Tanpa ini, ultralytics mengecilkan seluruh bingkai ke 640 px sebelum
    mendeteksi. Pada bingkai UAV 4000 px itu berarti tajuk menyusut lebih dari
    enam kali dan nyaris tidak ada yang terdeteksi — terukur: satu bingkai yang
    menghasilkan 3 deteksi dengan cara lama menghasilkan 135 dengan cara ini.
    """
    from PIL import Image

    with Image.open(image_path) as img:
        img = img.convert("RGB")
        lebar, tinggi = img.size
        potong = _tile_boxes(lebar, tinggi)
        if len(potong) > MAX_TILES:
            raise ModelError(
                f"Citra terlalu besar: {lebar}x{tinggi} px memerlukan "
                f"{len(potong)} ubin (batas {MAX_TILES}). Potong citra lebih "
                "dahulu, atau naikkan TILE_SIZE."
            )
        ubin = [img.crop(k) for k in potong]

    kotak: list[tuple] = []
    # Dikirim per kelompok: seluruh ubin sekaligus menahan banyak salinan citra
    # di memori, dan container ini berbagi RAM dengan aplikasi lain.
    for mulai in range(0, len(ubin), 16):
        kelompok = ubin[mulai : mulai + 16]
        letak = potong[mulai : mulai + 16]
        hasil = model.predict(
            source=kelompok,
            conf=CONF_THRESHOLD,
            iou=IOU_THRESHOLD,
            imgsz=TILE_SIZE,
            verbose=False,
        )
        for frame, (kiri, atas, _, _) in zip(hasil, letak):
            for k in frame.boxes:
                x1, y1, x2, y2 = k.xyxy[0].tolist()
                kotak.append(
                    (x1 + kiri, y1 + atas, x2 + kiri, y2 + atas,
                     model.names[int(k.cls.item())], float(k.conf.item()))
                )

    return kotak, lebar, tinggi


def _predict_remote(settings, image_path: str, model_path: str) -> tuple[list[tuple], int, int]:
    """Potong ubin di sini, jalankan modelnya di GPU Modal.

    Geometri ubin tetap ditentukan di sini dan dikirim bersama citra, sehingga
    mesin GPU tidak pernah memutuskan apa pun tentang cara citra dibaca. Yang
    berpindah ke sana hanya perkalian matriksnya.
    """
    from PIL import Image

    from app.services import remote_inference

    with Image.open(image_path) as img:
        lebar, tinggi = img.size

    potong = _tile_boxes(lebar, tinggi) if max(lebar, tinggi) > TILE_SIZE * TILE_TRIGGER else [
        (0, 0, lebar, tinggi)
    ]
    if len(potong) > MAX_TILES:
        raise ModelError(
            f"Citra terlalu besar: {lebar}x{tinggi} px memerlukan {len(potong)} ubin "
            f"(batas {MAX_TILES})."
        )

    try:
        kotak_nama = remote_inference.detect(
            settings,
            image_path=image_path,
            tiles=potong,
            model_path=model_path,
            imgsz=TILE_SIZE,
            conf=CONF_THRESHOLD,
            iou=IOU_THRESHOLD,
        )
    except remote_inference.RemoteError as exc:
        raise RemoteUnavailable(str(exc)) from exc

    # Mesin GPU mengembalikan NAMA kelas, bukan indeksnya: indeks bergantung
    # pada urutan di berkas model, dan menyamakannya antara dua mesin adalah
    # kekeliruan yang menunggu terjadi.
    return kotak_nama, lebar, tinggi


def _predict_whole(model, image_path: str) -> tuple[list[tuple], int, int]:
    """Deteksi pada citra yang sudah seukuran ubin — tanpa dipotong."""
    hasil = model.predict(
        source=image_path,
        conf=CONF_THRESHOLD,
        iou=IOU_THRESHOLD,
        imgsz=TILE_SIZE,
        verbose=False,
    )
    if not hasil:
        return [], 0, 0
    frame = hasil[0]
    tinggi, lebar = frame.orig_shape
    # Nama kelas, bukan indeksnya — supaya ketiga jalur (utuh, ubin, GPU)
    # menghasilkan bentuk yang sama dan dirakit oleh kode yang sama.
    kotak = [
        (*k.xyxy[0].tolist(), model.names[int(k.cls.item())], float(k.conf.item()))
        for k in frame.boxes
    ]
    return kotak, lebar, tinggi


def _rakit(
    kotak_semua: list[tuple],
    lebar_px: int,
    tinggi_px: int,
    gps: tuple[float, float] | None,
    area_ha: float | None,
) -> dict:
    """Ubah kotak mentah menjadi payload sesuai kontrak JSON.

    Dipakai ketiga jalur — citra utuh, berubin di CPU, dan berubin di GPU —
    sehingga hasil di layar tidak pernah bergantung pada mesin mana yang
    kebetulan menjalankan modelnya.
    """
    if not kotak_semua:
        return {"detections": []}

    skala = _ground_scale(lebar_px, tinggi_px, area_ha)

    mentah = []
    for x1, y1, x2, y2, kelas, keyakinan in kotak_semua:
        if kelas not in CLASS_LABELS:
            # Kelas asing tidak diteruskan ke UI; sudah dicatat saat memuat model.
            continue

        x1, y1, x2, y2 = float(x1), float(y1), float(x2), float(y2)
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

        mentah.append(
            {
                "bbox": [round(x1, 1), round(y1, 1), round(w, 1), round(h, 1)],
                "condition": BY_KEY[kelas].label,
                "severity": SEVERITY_RULE[kelas],
                "confidence": round(float(keyakinan), 3),
                "gps": titik,
                # Dipakai penggabungan, lalu dibuang sebelum keluar.
                "_xyxy": (x1, y1, x2, y2),
                "_conf": float(keyakinan),
            }
        )

    # Ubin sengaja bertumpang tindih, jadi pohon di daerah tumpang tindih
    # terdeteksi lebih dari sekali. Penggabungan terjadi di ruang koordinat
    # bingkai penuh — satu-satunya tempat kotak dari ubin berbeda dapat
    # dibandingkan.
    digabung = _nms(mentah)

    # Urutan kembali seperti pembacaan citra: kiri ke kanan, atas ke bawah.
    # Tanpa ini urutannya mengikuti keyakinan, dan nomor deteksi pada laporan
    # melompat-lompat di seluruh bingkai.
    digabung.sort(key=lambda d: (d["_xyxy"][1], d["_xyxy"][0]))

    for d in digabung:
        d.pop("_xyxy")
        d.pop("_conf")

    return {"detections": digabung}


def run(
    image_path: str,
    gps: tuple[float, float] | None = None,
    area_ha: float | None = None,
    model_path: str = "",
    settings=None,
) -> dict:
    """Jalankan deteksi dan kembalikan payload sesuai kontrak JSON.

    Tiga jalur, hasilnya sama:

    - Citra seukuran ubin diproses utuh.
    - Bingkai besar dipotong menjadi ubin (ambangnya TILE_TRIGGER).
    - Bila mesin GPU dikonfigurasi, pemotongan tetap dihitung di sini dan hanya
      penjalanan modelnya yang dikirim ke sana.
    """
    from app.config import get_settings

    settings = settings or get_settings()

    # Jalur GPU dicoba lebih dulu bila dikonfigurasi. Kegagalannya TIDAK
    # menggagalkan permintaan: deteksi diulang di CPU — lebih lambat, tetapi
    # menghasilkan angka yang sama, karena mesin GPU menjalankan model yang
    # sama pada ubin yang sama.
    if settings.gpu_inference_enabled and model_path:
        try:
            kotak, lebar_px, tinggi_px = _predict_remote(settings, image_path, model_path)
            return _rakit(kotak, lebar_px, tinggi_px, gps, area_ha)
        except RemoteUnavailable as exc:
            logger.warning("Mesin GPU tidak dipakai (%s); kembali ke CPU", exc)

    model = load(model_path)

    try:
        from PIL import Image

        with Image.open(image_path) as img:
            sisi_terpanjang = max(img.size)

        if sisi_terpanjang > TILE_SIZE * TILE_TRIGGER:
            kotak, lebar_px, tinggi_px = _predict_tiled(model, image_path)
        else:
            kotak, lebar_px, tinggi_px = _predict_whole(model, image_path)
    except ModelError:
        raise
    except Exception as exc:
        raise ModelError(f"Inference gagal: {exc}") from exc

    return _rakit(kotak, lebar_px, tinggi_px, gps, area_ha)
