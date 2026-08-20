"""Menarik versi dataset langsung dari Roboflow.

Menggantikan unggah manual: citra dan anotasinya datang dari sumber yang sama,
sehingga tidak ada lagi kemungkinan nama berkas tidak cocok — kegagalan paling
sering pada alur unggah.

Dipakai lewat HTTP biasa, bukan paket `roboflow`: paket itu menarik banyak
dependensi (termasuk opencv dan matplotlib) ke image produksi hanya untuk dua
permintaan HTTP.

Alurnya dua langkah, mengikuti API Roboflow:

    GET  api.roboflow.com/{ws}/{project}/{version}/yolov8?api_key=…
      -> {"export": {"link": "https://…"}}
    GET  <link>  -> arsip zip berisi train/ valid/ test/
"""

from __future__ import annotations

import logging
import re
import zipfile
from io import BytesIO

import httpx

logger = logging.getLogger("sawitscan.roboflow")

BASE = "https://api.roboflow.com"

#: Format ekspor. YOLOv8 dipilih karena pembacanya sudah ada di
#: app/evaluation/parsers.py dan sama dengan yang dipakai training.
FORMAT = "yolov8"

SPLITS = ("test", "valid", "train")

#: Nama workspace/project di Roboflow hanya berisi huruf kecil, angka, dan tanda
#: hubung. Divalidasi supaya nilai dari klien tidak pernah membentuk URL lain.
NAMA = re.compile(r"^[a-z0-9][a-z0-9-]{0,80}$")


class RoboflowError(Exception):
    """Dataset tidak dapat diambil."""


def _cek_nama(nilai: str, apa: str) -> str:
    bersih = nilai.strip().lower()
    if not NAMA.match(bersih):
        raise RoboflowError(
            f"{apa} tidak sah: '{nilai}'. Gunakan nama seperti pada URL Roboflow "
            "(huruf kecil, angka, tanda hubung)."
        )
    return bersih


def download_version(
    api_key: str,
    workspace: str,
    project: str,
    version: int,
    timeout_s: float = 600.0,
) -> bytes:
    """Unduh satu versi dataset sebagai arsip zip."""
    ws = _cek_nama(workspace, "Workspace")
    pr = _cek_nama(project, "Project")
    if not 1 <= version <= 999:
        raise RoboflowError(f"Nomor versi tidak sah: {version}.")

    url = f"{BASE}/{ws}/{pr}/{version}/{FORMAT}"
    try:
        with httpx.Client(timeout=timeout_s, follow_redirects=True) as client:
            # Kunci dikirim sebagai parameter kueri karena itu yang diterima API
            # Roboflow. Ia karena itu tidak pernah dicatat di log aplikasi ini —
            # lihat pemanggilan logger di bawah, yang hanya menyebut ws/pr/versi.
            respons = client.get(url, params={"api_key": api_key})
            if respons.status_code == 401:
                raise RoboflowError("Kunci API Roboflow ditolak.")
            if respons.status_code == 404:
                raise RoboflowError(
                    f"Versi tidak ditemukan: {ws}/{pr} v{version}. Periksa nama "
                    "workspace, project, dan nomor versinya."
                )
            respons.raise_for_status()

            tautan = (respons.json().get("export") or {}).get("link")
            if not tautan:
                raise RoboflowError(
                    "Roboflow tidak mengembalikan tautan unduhan. Versi itu "
                    "mungkin belum selesai diekspor ke format YOLOv8."
                )

            logger.info("Mengunduh dataset %s/%s v%s", ws, pr, version)
            berkas = client.get(tautan)
            berkas.raise_for_status()
            return berkas.content
    except RoboflowError:
        raise
    except httpx.HTTPError as exc:
        raise RoboflowError(f"Gagal menghubungi Roboflow: {exc}") from exc


def read_split(data: bytes, split: str) -> list[tuple[str, bytes]]:
    """Ambil berkas citra pada satu split dari arsip.

    Mengembalikan [(nama_berkas, isi)]. Anotasinya dibaca terpisah oleh
    app/evaluation/parsers.py dari arsip yang sama.
    """
    if split not in SPLITS:
        raise RoboflowError(f"Split tidak dikenal: {split}. Pilihan: {', '.join(SPLITS)}.")

    try:
        arsip = zipfile.ZipFile(BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise RoboflowError("Berkas yang diunduh bukan arsip zip yang sah.") from exc

    citra = []
    for anggota in arsip.namelist():
        bagian = anggota.replace("\\", "/").split("/")
        if split not in bagian or "images" not in bagian:
            continue
        nama = bagian[-1]
        if not nama.lower().endswith((".jpg", ".jpeg", ".png")):
            continue
        citra.append((nama, arsip.read(anggota)))

    if not citra:
        raise RoboflowError(
            f"Tidak ada citra pada split '{split}'. Versi itu mungkin tidak "
            "memuat split tersebut."
        )
    return citra


def labels_only(data: bytes) -> bytes:
    """Arsip berisi hanya anotasi dan data.yaml.

    Pembaca anotasi menerima zip; mengirimkan arsip lengkap berisi ratusan citra
    berarti membaca ulang puluhan megabyte yang tidak dipakainya.
    """
    sumber = zipfile.ZipFile(BytesIO(data))
    keluar = BytesIO()
    with zipfile.ZipFile(keluar, "w", zipfile.ZIP_DEFLATED) as tujuan:
        for anggota in sumber.namelist():
            nama = anggota.replace("\\", "/").split("/")[-1].lower()
            if nama.endswith(".txt") or nama in ("data.yaml", "classes.txt"):
                tujuan.writestr(anggota, sumber.read(anggota))
    keluar.seek(0)
    return keluar.read()
