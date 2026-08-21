"""Menyusun dataset YOLO dengan split yang bebas kebocoran.

Menghasilkan arsip siap-latih dari arsip Roboflow, dengan pembagian split
dihitung ulang memakai satuan sumber yang benar — bukan memakai split bawaan,
yang membagi per ubin dan menyebarkan mosaik yang sama ke train dan test.

Dua susunan dihasilkan agar dapat dibandingkan:

- **B1** — hanya bingkai UAV berdiri sendiri.
- **B2** — sama, ditambah ubin orthomosaic pada TRAIN saja.

Keduanya memakai VALIDATION dan TEST yang identik, sehingga selisih angkanya
hanya dapat berasal dari data latih tambahan itu. Tanpa itu, perbandingannya
tidak menjawab apa pun.
"""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass
from pathlib import Path

from app.training import crops

#: Nama folder split di dalam arsip keluaran. `valid`, bukan `val`, mengikuti
#: konvensi Roboflow yang juga dipahami ultralytics.
FOLDER = {"train": "train", "val": "valid", "test": "test"}


@dataclass(frozen=True)
class BuildResult:
    """Ringkasan satu arsip yang dihasilkan."""

    name: str
    archive: bytes
    #: {split: jumlah citra}
    images: dict[str, int]
    #: {split: {kelas: jumlah kotak}}
    boxes: dict[str, dict[str, int]]
    #: Kelompok sumber yang muncul di lebih dari satu split. Harus kosong.
    leaked_groups: dict[str, list[str]]
    class_names: list[str]


def _is_mosaic(group: str) -> bool:
    """Ubin orthomosaic dikenali dari kelompok sumbernya yang berupa angka."""
    return bool(crops.UBIN_MOSAIK.match(group + "_0_0"))


def plan_split(
    archive: bytes,
    ratios: tuple[float, float, float] = (0.7, 0.15, 0.15),
    seed: int = 0,
) -> tuple[dict[str, str], dict[str, str], list[str]]:
    """Tentukan split tiap citra.

    Mengembalikan (peta citra -> split, peta citra -> jenis sumber, nama kelas).

    Hanya bingkai berdiri sendiri yang dibagi ke tiga split; ubin orthomosaic
    seluruhnya masuk train. Alasannya bukan kenyamanan: ubin dan bingkai punya
    sebaran kelas yang nyaris berlawanan, dan menempatkan ubin di test berarti
    mengukur populasi yang berbeda dari yang benar-benar dipakai aplikasi.
    """
    nama_kelas = crops.class_names(archive)
    anotasi = crops.read_annotations(archive, nama_kelas)

    citra_per_kelompok: dict[str, list[str]] = {}
    for stem in anotasi:
        citra_per_kelompok.setdefault(crops.source_group(stem), []).append(stem)

    berdiri_sendiri = {
        g: len(v) for g, v in citra_per_kelompok.items() if not _is_mosaic(g)
    }
    pembagian_kelompok = crops.split_groups(berdiri_sendiri, ratios, seed)

    split_citra: dict[str, str] = {}
    jenis_citra: dict[str, str] = {}
    for g, daftar in citra_per_kelompok.items():
        mosaik = _is_mosaic(g)
        for stem in daftar:
            jenis_citra[stem] = "mosaic" if mosaik else "frame"
            split_citra[stem] = "train" if mosaik else pembagian_kelompok[g]

    return split_citra, jenis_citra, nama_kelas


def build(
    archive: bytes,
    *,
    name: str,
    include_mosaic: bool,
    ratios: tuple[float, float, float] = (0.7, 0.15, 0.15),
    seed: int = 0,
) -> BuildResult:
    """Susun satu arsip YOLO siap-latih."""
    split_citra, jenis_citra, nama_kelas = plan_split(archive, ratios, seed)
    sumber = zipfile.ZipFile(io.BytesIO(archive))

    # Petakan stem -> anggota arsip, untuk citra maupun labelnya.
    citra_anggota: dict[str, str] = {}
    label_anggota: dict[str, str] = {}
    for anggota in sumber.namelist():
        bagian = anggota.replace("\\", "/").split("/")
        stem = Path(anggota).stem
        if "images" in bagian and anggota.lower().endswith((".jpg", ".jpeg", ".png")):
            citra_anggota[stem] = anggota
        elif (
            "labels" in bagian
            and anggota.lower().endswith(".txt")
            and Path(anggota).name.lower() != "classes.txt"
        ):
            label_anggota[stem] = anggota

    jumlah_citra = {s: 0 for s in crops.SPLITS}
    jumlah_kotak: dict[str, dict[str, int]] = {s: {} for s in crops.SPLITS}
    kelompok_split: dict[str, set[str]] = {}
    baris_manifest = ["image,split,source_group,source_type,boxes"]

    keluar = io.BytesIO()
    with zipfile.ZipFile(keluar, "w", zipfile.ZIP_DEFLATED) as tujuan:
        for stem, split in sorted(split_citra.items()):
            if not include_mosaic and jenis_citra[stem] == "mosaic":
                continue
            if stem not in citra_anggota or stem not in label_anggota:
                continue  # pasangan tidak lengkap; dilewati, bukan ditebak

            folder = FOLDER[split]
            asal_citra = citra_anggota[stem]
            tujuan.writestr(
                f"{folder}/images/{Path(asal_citra).name}", sumber.read(asal_citra)
            )
            isi_label = sumber.read(label_anggota[stem])
            tujuan.writestr(f"{folder}/labels/{stem}.txt", isi_label)

            n = 0
            for baris in isi_label.decode("utf-8", "replace").splitlines():
                bagian = baris.split()
                if not bagian:
                    continue
                kelas = nama_kelas[int(float(bagian[0]))]
                jumlah_kotak[split][kelas] = jumlah_kotak[split].get(kelas, 0) + 1
                n += 1

            jumlah_citra[split] += 1
            g = crops.source_group(stem)
            kelompok_split.setdefault(g, set()).add(split)
            baris_manifest.append(f"{stem},{split},{g},{jenis_citra[stem]},{n}")

        tujuan.writestr(
            "data.yaml",
            "train: ../train/images\n"
            "val: ../valid/images\n"
            "test: ../test/images\n"
            f"nc: {len(nama_kelas)}\n"
            f"names: {nama_kelas}\n",
        )
        tujuan.writestr("split-manifest.csv", "\n".join(baris_manifest) + "\n")

        bocor = {g: sorted(s) for g, s in kelompok_split.items() if len(s) > 1}
        tujuan.writestr(
            "SPLIT.md",
            _catatan(name, include_mosaic, jumlah_citra, jumlah_kotak, bocor, seed),
        )

    return BuildResult(
        name=name,
        archive=keluar.getvalue(),
        images=jumlah_citra,
        boxes=jumlah_kotak,
        leaked_groups=bocor,
        class_names=nama_kelas,
    )


def _catatan(
    name: str,
    include_mosaic: bool,
    images: dict[str, int],
    boxes: dict[str, dict[str, int]],
    leaked: dict[str, list[str]],
    seed: int,
) -> str:
    """Catatan yang ikut di dalam arsip.

    Arsip yang berpindah tangan tanpa keterangan cara pembagiannya tidak dapat
    dipertanggungjawabkan; siapa pun yang menerimanya harus dapat membaca
    bagaimana ia disusun tanpa bertanya.
    """
    baris = [
        f"# {name}",
        "",
        "Dataset YOLO dengan split bebas kebocoran.",
        "",
        "## Cara pembagian",
        "",
        "Satuan pembagian adalah SUMBER, bukan citra. Ubin dari satu orthomosaic",
        "berasal dari satu sumber dan tidak pernah terbelah antar-split — ubin",
        "bertetangga saling bersinggungan, sehingga pohon yang sama dapat muncul",
        "di dua ubin.",
        "",
        "Validation dan test HANYA berisi bingkai UAV berdiri sendiri: itulah",
        "populasi yang benar-benar diproses aplikasi.",
        "",
    ]
    if include_mosaic:
        baris += [
            "Ubin orthomosaic disertakan pada TRAIN saja, sebagai data latih",
            "tambahan. Statusnya harus disebut apa adanya pada setiap laporan.",
            "",
        ]
    else:
        baris += ["Ubin orthomosaic TIDAK disertakan sama sekali.", ""]

    baris += [f"Seed pembagian: {seed}", "", "## Isi", "", "| Split | Citra | Kotak |", "| --- | ---: | ---: |"]
    for s in crops.SPLITS:
        baris.append(f"| {s} | {images[s]} | {sum(boxes[s].values())} |")

    baris += ["", "## Sebaran kelas", "", "| Split | " + " | ".join(sorted({k for b in boxes.values() for k in b})) + " |"]
    kelas = sorted({k for b in boxes.values() for k in b})
    baris.append("| --- | " + " | ".join("---:" for _ in kelas) + " |")
    for s in crops.SPLITS:
        baris.append(f"| {s} | " + " | ".join(str(boxes[s].get(k, 0)) for k in kelas) + " |")

    baris += [
        "",
        "## Pemeriksaan kebocoran",
        "",
        f"Kelompok sumber yang muncul di lebih dari satu split: **{len(leaked)}**",
    ]
    if leaked:
        baris += ["", "```"] + [f"{g}: {', '.join(s)}" for g, s in leaked.items()] + ["```"]
    else:
        baris += ["", "Tidak ada. Setiap sumber berada tepat di satu split."]

    baris += [
        "",
        "`split-manifest.csv` memuat baris per citra beserta split, kelompok",
        "sumber, jenisnya, dan jumlah kotaknya.",
        "",
    ]
    return "\n".join(baris)
