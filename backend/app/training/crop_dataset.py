"""Menyusun dataset klasifikasi dari arsip deteksi yang sudah dibekukan.

Potongan diambil dari kotak GROUND TRUTH, bukan dari prediksi detektor. Melatih
classifier pada keluaran detektor berarti mewariskan kesalahannya, dan angka
yang keluar tidak lagi mengukur kemampuan classifier-nya sendiri.

Split TIDAK dihitung ulang di sini. Ia dibaca dari folder tempat citra berada di
dalam arsip sumber. Menghitung ulang dengan seed yang sama memang *seharusnya*
menghasilkan pembagian yang sama, tetapi "seharusnya" bukan jaminan — dan bila
meleset, potongan test Swin tidak lagi berasal dari bingkai yang sama dengan
test detektornya, sehingga kedua hasil tidak dapat dikaitkan sama sekali.

Dengan membaca split dari arsip, populasi test keduanya identik menurut
konstruksi, bukan menurut harapan.
"""

from __future__ import annotations

import csv
import hashlib
import io
import zipfile
from dataclasses import dataclass
from pathlib import Path

from app.training import crops

#: Folder split di arsip deteksi -> nama split kanonis.
DARI_FOLDER = {"train": "train", "valid": "val", "test": "test"}

#: Potongan yang lebih kecil dari ini tidak menyisakan apa pun untuk dikenali.
MIN_SISI = 8

#: Kotak dilebarkan sedikit: pembeda tajuk sehat dan kerdil justru ada pada
#: perbandingannya dengan sekeliling, yang hilang bila dipotong tepat di garis.
PADDING = 0.10


@dataclass(frozen=True)
class CropDataset:
    archive: bytes
    #: {split: {kelas: jumlah}}
    counts: dict[str, dict[str, int]]
    #: {split: jumlah potongan}
    totals: dict[str, int]
    #: Kelompok sumber yang muncul di lebih dari satu split. Harus kosong.
    leaked_groups: dict[str, list[str]]
    class_names: list[str]
    #: sha256 per split, untuk dicatat bersama hasil eksperimen.
    split_hashes: dict[str, str]


def _baca_nama_kelas(archive: bytes) -> list[str]:
    """Urutan kelas diambil dari arsip, tidak pernah ditebak.

    `crops.class_names` menolak arsip tanpa `names:` alih-alih memberi urutan
    bawaan — menebak urutannya sekali saja sudah cukup untuk menukar label
    seluruh dataset tanpa ada yang menyadarinya.
    """
    return crops.class_names(archive)


def _kotak_piksel(
    baris: str, lebar: int, tinggi: int
) -> tuple[int, float, float, float, float, float, float] | None:
    """Kembalikan (indeks, x1, y1, x2, y2, lebar_asli, tinggi_asli).

    Ukuran asli ikut dikembalikan karena heuristik ukuran harus diukur pada
    kotak GT apa adanya. Kotak yang sudah dilebarkan 10% ke tiap sisi berukuran
    20% lebih besar, dan ambang yang diterapkan padanya mengukur hal lain.
    """
    bagian = baris.split()
    if len(bagian) < 5:
        return None
    indeks = int(float(bagian[0]))
    cx, cy, w, h = (float(v) for v in bagian[1:5])

    bw, bh = w * lebar, h * tinggi
    px, py = bw * PADDING, bh * PADDING
    x1 = max(0.0, cx * lebar - bw / 2 - px)
    y1 = max(0.0, cy * tinggi - bh / 2 - py)
    x2 = min(float(lebar), cx * lebar + bw / 2 + px)
    y2 = min(float(tinggi), cy * tinggi + bh / 2 + py)

    if x2 - x1 < MIN_SISI or y2 - y1 < MIN_SISI:
        return None
    return indeks, x1, y1, x2, y2, bw, bh


def build(archive: bytes, *, ukuran: int = 224) -> CropDataset:
    """Potong seluruh kotak GT menjadi dataset klasifikasi.

    `ukuran` adalah sisi keluaran; Swin menuntut masukan berukuran tetap.
    Potongan diregangkan ke bujur sangkar, bukan dipotong tengahnya — memotong
    lagi akan membuang bagian tajuk yang justru menjadi penciri kelasnya.
    """
    from PIL import Image

    sumber = zipfile.ZipFile(io.BytesIO(archive))
    nama_kelas = _baca_nama_kelas(archive)

    # stem -> (anggota citra, split)
    citra: dict[str, tuple[str, str]] = {}
    label: dict[str, str] = {}
    for anggota in sumber.namelist():
        bagian = anggota.replace("\\", "/").split("/")
        if len(bagian) < 3 or bagian[0] not in DARI_FOLDER:
            continue
        split = DARI_FOLDER[bagian[0]]
        stem = Path(anggota).stem
        if bagian[1] == "images" and anggota.lower().endswith((".jpg", ".jpeg", ".png")):
            citra[stem] = (anggota, split)
        elif bagian[1] == "labels" and anggota.lower().endswith(".txt"):
            label[stem] = anggota

    jumlah: dict[str, dict[str, int]] = {s: {} for s in crops.SPLITS}
    total: dict[str, int] = {s: 0 for s in crops.SPLITS}
    kelompok_split: dict[str, set[str]] = {}
    baris_manifest = [
        "crop_id,split,class,source_image,source_group,tree_index,"
        "x1,y1,x2,y2,pad_w,pad_h,raw_w,raw_h"
    ]
    #: {split: [(nama berkas, sha256 isi)]} — dasar hash split.
    sidik: dict[str, list[tuple[str, str]]] = {s: [] for s in crops.SPLITS}

    keluar = io.BytesIO()
    with zipfile.ZipFile(keluar, "w", zipfile.ZIP_DEFLATED) as tujuan:
        for stem in sorted(citra):
            anggota_citra, split = citra[stem]
            if stem not in label:
                continue  # pasangan tidak lengkap; dilewati, bukan ditebak

            with Image.open(io.BytesIO(sumber.read(anggota_citra))) as gambar:
                gambar = gambar.convert("RGB")
                lebar, tinggi = gambar.size
                isi_label = sumber.read(label[stem]).decode("utf-8", "replace")

                for i, baris in enumerate(isi_label.splitlines()):
                    kotak = _kotak_piksel(baris, lebar, tinggi)
                    if kotak is None:
                        continue
                    indeks, x1, y1, x2, y2, bw, bh = kotak
                    kelas = nama_kelas[indeks]

                    potongan = gambar.crop((int(x1), int(y1), int(x2), int(y2)))
                    potongan = potongan.resize((ukuran, ukuran), Image.BILINEAR)

                    penyangga = io.BytesIO()
                    potongan.save(penyangga, format="JPEG", quality=92)
                    data = penyangga.getvalue()

                    crop_id = f"{stem}#{i:03d}"
                    nama = f"{split}/{kelas}/{stem}_{i:03d}.jpg"
                    tujuan.writestr(nama, data)

                    sidik[split].append((nama, hashlib.sha256(data).hexdigest()))
                    jumlah[split][kelas] = jumlah[split].get(kelas, 0) + 1
                    total[split] += 1

                    g = crops.source_group(stem)
                    kelompok_split.setdefault(g, set()).add(split)
                    baris_manifest.append(
                        f"{crop_id},{split},{kelas},{stem},{g},{i},"
                        f"{x1:.1f},{y1:.1f},{x2:.1f},{y2:.1f},"
                        f"{x2 - x1:.1f},{y2 - y1:.1f},{bw:.1f},{bh:.1f}"
                    )

        bocor = {
            g: sorted(s) for g, s in kelompok_split.items() if len(s) > 1
        }

        tujuan.writestr("manifest.csv", "\n".join(baris_manifest) + "\n")
        tujuan.writestr("classes.txt", "\n".join(nama_kelas) + "\n")
        tujuan.writestr("SPLIT.md", _catatan(jumlah, total, bocor, nama_kelas))

    hash_split = {
        s: _hash_split(daftar) for s, daftar in sidik.items()
    }

    return CropDataset(
        archive=keluar.getvalue(),
        counts=jumlah,
        totals=total,
        leaked_groups=bocor,
        class_names=nama_kelas,
        split_hashes=hash_split,
    )


def _hash_split(daftar: list[tuple[str, str]]) -> str:
    """sha256 atas isi satu split, tidak bergantung urutan penulisan arsip.

    Nama berkas ikut dicerna: dua potongan yang isinya kebetulan sama tetapi
    berasal dari pohon berbeda tetap membedakan hash-nya.
    """
    pencerna = hashlib.sha256()
    for nama, sidik in sorted(daftar):
        pencerna.update(nama.encode("utf-8"))
        pencerna.update(bytes.fromhex(sidik))
    return pencerna.hexdigest()


def _catatan(
    jumlah: dict[str, dict[str, int]],
    total: dict[str, int],
    bocor: dict[str, list[str]],
    nama_kelas: list[str],
) -> str:
    baris = [
        "# Dataset klasifikasi tajuk (potongan ground truth)",
        "",
        "Potongan berasal dari kotak GROUND TRUTH, bukan prediksi detektor.",
        "",
        "Split TIDAK dihitung ulang: ia dibaca dari folder pada arsip deteksi,",
        "sehingga potongan test berasal dari bingkai yang sama persis dengan",
        "test detektornya. Kedua hasil karena itu dapat dikaitkan.",
        "",
        f"Kelas, menurut urutan data.yaml: {nama_kelas}",
        "",
        "| split | " + " | ".join(nama_kelas) + " | total |",
        "|---|" + "---|" * (len(nama_kelas) + 1),
    ]
    for s in crops.SPLITS:
        sel = " | ".join(str(jumlah[s].get(k, 0)) for k in nama_kelas)
        baris.append(f"| {s} | {sel} | {total[s]} |")

    baris += ["", "## Kebocoran", ""]
    if bocor:
        baris.append("**ADA KEBOCORAN.** Kelompok berikut muncul di lebih dari satu split:")
        baris += [f"- `{g}`: {', '.join(s)}" for g, s in sorted(bocor.items())]
    else:
        baris.append("Tidak ada kelompok sumber yang muncul di lebih dari satu split.")

    baris += [
        "",
        "## Padding",
        "",
        f"Kotak dilebarkan {PADDING:.0%} ke setiap sisi sebelum dipotong. Pembeda",
        "tajuk sehat dan kerdil ada pada perbandingannya dengan sekeliling, dan",
        "potongan tepat di garis kotak menghilangkannya.",
        "",
    ]
    return "\n".join(baris)


def read_manifest(archive: bytes) -> list[dict[str, str]]:
    """Baca manifest dari arsip potongan. Dipakai heuristik ukuran dan analisis."""
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        teks = z.read("manifest.csv").decode("utf-8")
    return list(csv.DictReader(io.StringIO(teks)))
