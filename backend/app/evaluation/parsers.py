"""Pembaca berkas anotasi ground truth.

Mendukung dua format yang bisa diunduh langsung dari Roboflow:

- **YOLOv8** — arsip zip berisi `labels/*.txt` (satu baris per objek, koordinat
  ternormalisasi 0..1) beserta `data.yaml` atau `classes.txt` untuk nama kelas.
- **COCO JSON** — satu berkas dengan `images`, `annotations`, dan `categories`.

Keduanya dinormalkan menjadi daftar `GroundTruth` dengan koordinat piksel, sama
seperti yang dipakai deteksi, sehingga metriknya sebanding.

Nama kelas dataset (`healthy`, `yellow`, `dead`, `small`) dipetakan ke label yang
dipakai sistem. Kelas di luar keempatnya ditolak dengan pesan yang menyebutkan
nama aslinya — lebih baik gagal terang-terangan daripada diam-diam menghitung
metrik atas kelas yang tidak dikenal.
"""

from __future__ import annotations

import json
import zipfile
from io import BytesIO
from pathlib import Path

from app.evaluation.metrics import GroundTruth
from app.inference.conditions import BY_LABEL, CLASS_LABELS


class AnnotationError(ValueError):
    """Berkas anotasi tidak dapat dibaca."""


def _to_label(nama: str) -> str:
    """Terima nama kelas dataset maupun label sistem."""
    bersih = nama.strip()
    if bersih in CLASS_LABELS:
        return CLASS_LABELS[bersih]
    if bersih.lower() in CLASS_LABELS:
        return CLASS_LABELS[bersih.lower()]
    if bersih in BY_LABEL:
        return bersih
    raise AnnotationError(
        f"Kelas '{nama}' tidak dikenal. Yang berlaku: "
        + ", ".join(f"{k} ({v})" for k, v in CLASS_LABELS.items())
    )


def _names_from_yaml(isi: str) -> list[str]:
    """Ambil `names:` dari data.yaml tanpa menambah dependensi YAML.

    Roboflow menulisnya sebagai daftar sebaris (`names: ['a', 'b']`) atau
    berbutir (`- a`). Dua bentuk itu saja yang perlu ditangani.
    """
    baris_baris = isi.splitlines()
    for i, baris in enumerate(baris_baris):
        if not baris.strip().startswith("names:"):
            continue

        sisa = baris.split("names:", 1)[1].strip()
        if sisa.startswith("["):
            isi_kurung = sisa[1 : sisa.rindex("]")] if "]" in sisa else sisa[1:]
            return [n.strip().strip("'\"") for n in isi_kurung.split(",") if n.strip()]

        nama = []
        for lanjutan in baris_baris[i + 1 :]:
            butir = lanjutan.strip()
            if butir.startswith("- "):
                nama.append(butir[2:].strip().strip("'\""))
            elif butir and not butir.startswith("#"):
                break
        return nama
    return []


def parse_yolo_zip(data: bytes, sizes: dict[str, tuple[int, int]]) -> list[GroundTruth]:
    """Baca arsip ekspor YOLOv8.

    `sizes` memetakan nama berkas citra (tanpa ekstensi, huruf kecil) ke
    (lebar, tinggi) — dibutuhkan karena koordinat YOLO ternormalisasi.
    """
    try:
        arsip = zipfile.ZipFile(BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise AnnotationError("Berkas bukan arsip zip yang sah.") from exc

    nama_kelas: list[str] = []
    for anggota in arsip.namelist():
        akhiran = Path(anggota).name.lower()
        if akhiran == "data.yaml":
            nama_kelas = _names_from_yaml(arsip.read(anggota).decode("utf-8", "replace"))
            break
        if akhiran == "classes.txt":
            nama_kelas = [
                b.strip()
                for b in arsip.read(anggota).decode("utf-8", "replace").splitlines()
                if b.strip()
            ]

    if not nama_kelas:
        raise AnnotationError(
            "Nama kelas tidak ditemukan. Sertakan data.yaml atau classes.txt "
            "dari ekspor Roboflow."
        )

    label_kelas = [_to_label(n) for n in nama_kelas]

    hasil: list[GroundTruth] = []
    terlewat: set[str] = set()
    berkas_label = [
        n for n in arsip.namelist() if n.lower().endswith(".txt") and "label" in n.lower()
    ]
    if not berkas_label:
        berkas_label = [
            n
            for n in arsip.namelist()
            if n.lower().endswith(".txt") and Path(n).name.lower() != "classes.txt"
        ]

    for anggota in berkas_label:
        stem = Path(anggota).stem.lower()
        ukuran = sizes.get(stem)
        if ukuran is None:
            terlewat.add(Path(anggota).stem)
            continue
        lebar, tinggi = ukuran

        for nomor, baris in enumerate(
            arsip.read(anggota).decode("utf-8", "replace").splitlines(), start=1
        ):
            bagian = baris.split()
            if not bagian:
                continue
            if len(bagian) < 5:
                raise AnnotationError(
                    f"{anggota} baris {nomor}: butuh 5 kolom, dapat {len(bagian)}."
                )
            try:
                indeks = int(float(bagian[0]))
                cx, cy, w, h = (float(v) for v in bagian[1:5])
            except ValueError as exc:
                raise AnnotationError(f"{anggota} baris {nomor}: angka tidak sah.") from exc

            if not 0 <= indeks < len(label_kelas):
                raise AnnotationError(
                    f"{anggota} baris {nomor}: indeks kelas {indeks} di luar jangkauan."
                )

            hasil.append(
                GroundTruth(
                    box=(
                        (cx - w / 2) * lebar,
                        (cy - h / 2) * tinggi,
                        w * lebar,
                        h * tinggi,
                    ),
                    label=label_kelas[indeks],
                    image=stem,
                )
            )

    if not hasil:
        pesan = "Tidak ada anotasi yang cocok dengan citra di sistem."
        if terlewat:
            contoh = ", ".join(sorted(terlewat)[:5])
            pesan += f" Nama berkas yang tidak dikenali: {contoh}."
        raise AnnotationError(pesan)

    return hasil


def parse_coco(data: bytes, sizes: dict[str, tuple[int, int]]) -> list[GroundTruth]:
    """Baca satu berkas COCO JSON."""
    try:
        isi = json.loads(data.decode("utf-8", "replace"))
    except json.JSONDecodeError as exc:
        raise AnnotationError("Berkas bukan JSON yang sah.") from exc

    if not isinstance(isi, dict) or "annotations" not in isi:
        raise AnnotationError("Struktur COCO tidak dikenali: kunci 'annotations' tidak ada.")

    kategori = {
        int(k["id"]): _to_label(str(k.get("name", ""))) for k in isi.get("categories", [])
    }
    if not kategori:
        raise AnnotationError("Berkas COCO tidak memuat 'categories'.")

    citra = {
        int(g["id"]): Path(str(g.get("file_name", ""))).stem.lower()
        for g in isi.get("images", [])
    }

    hasil: list[GroundTruth] = []
    for anotasi in isi["annotations"]:
        stem = citra.get(int(anotasi.get("image_id", -1)))
        if stem is None or stem not in sizes:
            continue
        kotak = anotasi.get("bbox")
        if not kotak or len(kotak) < 4:
            continue
        kelas = kategori.get(int(anotasi.get("category_id", -1)))
        if kelas is None:
            continue

        x, y, w, h = (float(v) for v in kotak[:4])
        hasil.append(GroundTruth(box=(x, y, w, h), label=kelas, image=stem))

    if not hasil:
        raise AnnotationError("Tidak ada anotasi yang cocok dengan citra di sistem.")
    return hasil


def parse(filename: str, data: bytes, sizes: dict[str, tuple[int, int]]) -> list[GroundTruth]:
    """Pilih pembaca berdasarkan ekstensi berkas."""
    akhiran = Path(filename).suffix.lower()
    if akhiran == ".zip":
        return parse_yolo_zip(data, sizes)
    if akhiran == ".json":
        return parse_coco(data, sizes)
    raise AnnotationError(
        "Format tidak didukung. Unggah .zip (ekspor YOLOv8) atau .json (COCO)."
    )
