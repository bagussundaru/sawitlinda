"""Menyiapkan dataset klasifikasi dari anotasi ground truth.

Tahap kedua pipeline — Swin Transformer — mengklasifikasi potongan tajuk. Modul
ini menyiapkan potongan itu beserta jejak asalnya.

DUA ATURAN METODOLOGIS YANG DITEGAKKAN DI SINI:

1. **Label berasal dari ground truth, bukan dari prediksi YOLOv8.** Melatih Swin
   pada keluaran YOLOv8 berarti mengajarinya meniru YOLOv8, bukan belajar dari
   kebenaran; akurasinya akan tinggi dan tidak berarti apa-apa. YOLOv8 tetap
   dipakai saat inference, tidak saat menyiapkan data latih.

2. **Pembagian split per SUMBER, bukan per citra.** Dataset ini memuat ubin dari
   mosaik yang sama — mis. `44000_16000_1031_1863` dan `44000_16000_1059_3696`
   berasal dari mosaik `44000_16000`. Ubin bertetangga saling bersinggungan,
   sehingga pohon yang sama dapat muncul di dua ubin. Bila ubin dibagi acak,
   pohon itu berakhir di train sekaligus di test — kebocoran yang membuat angka
   evaluasi terlihat bagus tanpa dasar.

Modul ini murni: tanpa database, tanpa jaringan, tanpa berkas selain yang
diberikan pemanggil.
"""

from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

#: Ubin mosaik bernama `<x>_<y>_<dx>_<dy>_jpg.rf.<hash>.jpg`. Dua bilangan
#: pertama menandai mosaik asalnya; itulah satuan yang tidak boleh terbelah.
UBIN_MOSAIK = re.compile(r"^(\d+_\d+)_\d+_\d+")

#: Roboflow menambahkan `.rf.<hash>` pada tiap nama berkas saat ekspor, dan
#: menyisipkan ekstensi aslinya di depannya — `DJI_0476_JPG.rf.<hash>`. Huruf
#: besar-kecilnya mengikuti berkas asli, jadi pencocokannya tidak boleh peka.
AKHIRAN_ROBOFLOW = re.compile(r"(_(jpg|jpeg|png))?\.rf\.[0-9a-f]+$", re.I)

SPLITS = ("train", "val", "test")


@dataclass(frozen=True)
class Crop:
    """Satu potongan tajuk beserta jejak asalnya.

    Seluruh bidang ikut ditulis ke manifest supaya setiap potongan dapat
    ditelusuri kembali ke kotak mana pada citra mana.
    """

    crop_id: str
    source_image: str
    #: Mosaik atau penerbangan asal — satuan pembagian split.
    source_group: str
    tree_index: int
    label: str
    #: Kotak dalam piksel citra asal.
    x1: float
    y1: float
    x2: float
    y2: float


def source_group(filename: str) -> str:
    """Satuan yang tidak boleh terbelah antar-split.

    Untuk ubin mosaik, mosaiknya. Untuk bingkai berdiri sendiri, bingkainya.
    """
    nama = Path(filename).name
    nama = re.sub(r"\.(jpg|jpeg|png|txt)$", "", nama, flags=re.I)
    nama = AKHIRAN_ROBOFLOW.sub("", nama)

    cocok = UBIN_MOSAIK.match(nama)
    return cocok.group(1) if cocok else nama


def split_groups(
    counts: dict[str, int],
    ratios: tuple[float, float, float] = (0.7, 0.15, 0.15),
    seed: int = 0,
    strata: dict[str, str] | None = None,
) -> dict[str, str]:
    """Bagikan SELURUH kelompok ke split, bukan potongan per potongan.

    Mengembalikan {kelompok: split}. Kelompok besar dibagikan lebih dulu supaya
    proporsi akhirnya tidak melenceng jauh — membagikan berurutan dari yang
    kecil membuat satu kelompok raksasa di akhir menjatuhkan seluruh imbangan.

    `strata` memetakan kelompok ke jenis sumbernya, dan bila diberikan, tiap
    jenis dibagikan SENDIRI-SENDIRI ke ketiga split. Tanpa itu, jenis yang
    kelompoknya besar bisa jatuh seluruhnya ke satu split — dan bila sebaran
    kelasnya berbeda antar-jenis, split itu mengukur populasi yang berbeda.
    Pada dataset ini ubin mosaik didominasi `yellow`/`dead` sementara bingkai
    berdiri sendiri didominasi `small`; membiarkannya terpisah membuat angka
    evaluasi tidak dapat dibandingkan dengan apa pun.

    Deterministik untuk `seed` yang sama: dua orang yang menjalankan ini pada
    dataset yang sama harus memperoleh pembagian yang sama, atau angkanya tidak
    dapat dibandingkan.
    """
    if not counts:
        return {}
    if abs(sum(ratios) - 1.0) > 1e-6:
        raise ValueError(f"Rasio harus berjumlah 1, dapat {sum(ratios)}.")

    if strata is None:
        return _bagikan(counts, ratios, seed)

    hasil: dict[str, str] = {}
    for jenis in sorted({strata.get(g, "") for g in counts}):
        bagian = {g: n for g, n in counts.items() if strata.get(g, "") == jenis}
        hasil.update(_bagikan(bagian, ratios, seed))
    return hasil


def _bagikan(
    counts: dict[str, int], ratios: tuple[float, float, float], seed: int
) -> dict[str, str]:
    """Bagikan satu himpunan kelompok ke ketiga split."""
    if not counts:
        return {}

    total = sum(counts.values())
    target = dict(zip(SPLITS, (r * total for r in ratios)))
    terisi = {s: 0.0 for s in SPLITS}
    hasil: dict[str, str] = {}

    # Urutan: jumlah menurun, lalu nama — agar tidak bergantung urutan dict.
    # `seed` menggeser urutan secara deterministik tanpa membuatnya acak penuh.
    urut = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    if seed:
        geser = seed % len(urut)
        urut = urut[geser:] + urut[:geser]

    for kelompok, jumlah in urut:
        # Taruh di split yang paling jauh dari targetnya.
        pilih = max(SPLITS, key=lambda s: target[s] - terisi[s])
        hasil[kelompok] = pilih
        terisi[pilih] += jumlah

    return hasil


def class_names(archive: bytes) -> list[str]:
    """Nama kelas menurut arsip, MENURUT URUTANNYA SENDIRI.

    Wajib dipakai, bukan ditebak. Dataset ini menulis
    `names: ['dead', 'healthy', 'small', 'yellow']` — urutan yang berbeda dari
    urutan tampilan di aplikasi. Menebaknya menukar seluruh kelas tanpa satu pun
    galat muncul, dan angka yang keluar tetap terlihat masuk akal.
    """
    arsip = zipfile.ZipFile(io.BytesIO(archive))
    for anggota in arsip.namelist():
        if Path(anggota).name.lower() != "data.yaml":
            continue
        for baris in arsip.read(anggota).decode("utf-8", "replace").splitlines():
            if not baris.strip().startswith("names:"):
                continue
            sisa = baris.split("names:", 1)[1].strip()
            if sisa.startswith("["):
                return [
                    n.strip().strip("'\"")
                    for n in sisa.strip("[]").split(",")
                    if n.strip()
                ]
    raise ValueError(
        "data.yaml tidak memuat `names:`. Urutan kelas tidak boleh ditebak — "
        "menebaknya menukar seluruh kelas tanpa galat apa pun."
    )


def read_annotations(
    archive: bytes, class_names: list[str]
) -> dict[str, list[tuple[int, float, float, float, float]]]:
    """Baca seluruh label YOLO dari arsip, apa pun split aslinya.

    Split bawaan Roboflow sengaja diabaikan: ia membagi per ubin, sehingga
    mosaik yang sama dapat tersebar ke train dan test. Pembagian dilakukan
    ulang di sini dengan satuan yang benar.
    """
    arsip = zipfile.ZipFile(io.BytesIO(archive))
    hasil: dict[str, list[tuple[int, float, float, float, float]]] = {}

    for anggota in arsip.namelist():
        bagian = anggota.replace("\\", "/").split("/")
        if "labels" not in bagian or not anggota.lower().endswith(".txt"):
            continue
        if Path(anggota).name.lower() == "classes.txt":
            continue

        stem = Path(anggota).stem
        kotak = []
        for nomor, baris in enumerate(
            arsip.read(anggota).decode("utf-8", "replace").splitlines(), start=1
        ):
            bagian_baris = baris.split()
            if not bagian_baris:
                continue
            if len(bagian_baris) < 5:
                raise ValueError(f"{anggota} baris {nomor}: butuh 5 kolom.")
            indeks = int(float(bagian_baris[0]))
            if not 0 <= indeks < len(class_names):
                raise ValueError(
                    f"{anggota} baris {nomor}: indeks kelas {indeks} di luar jangkauan."
                )
            cx, cy, w, h = (float(v) for v in bagian_baris[1:5])
            kotak.append((indeks, cx, cy, w, h))

        if kotak:
            hasil[stem] = kotak
    return hasil


def plan_crops(
    annotations: dict[str, list[tuple[int, float, float, float, float]]],
    class_names: list[str],
    sizes: dict[str, tuple[int, int]],
    ratios: tuple[float, float, float] = (0.7, 0.15, 0.15),
    seed: int = 0,
    padding: float = 0.10,
) -> tuple[list[Crop], dict[str, str]]:
    """Susun daftar potongan beserta split-nya, tanpa menyentuh berkas citra.

    `padding` melebarkan kotak sedikit ke luar. Tajuk yang terpotong tepat di
    garis kotak kehilangan konteks tepinya, dan pembeda antara tajuk sehat dan
    kerdil justru ada pada perbandingannya dengan sekelilingnya.

    Mengembalikan (daftar potongan, peta kelompok -> split).
    """
    per_kelompok: dict[str, int] = {}
    for stem, kotak in annotations.items():
        per_kelompok[source_group(stem)] = per_kelompok.get(source_group(stem), 0) + len(kotak)

    pembagian = split_groups(per_kelompok, ratios, seed)

    potongan: list[Crop] = []
    for stem in sorted(annotations):
        ukuran = sizes.get(stem)
        if ukuran is None:
            continue  # citranya tidak ada di arsip; dilewati, bukan ditebak
        lebar, tinggi = ukuran

        for i, (indeks, cx, cy, w, h) in enumerate(annotations[stem]):
            bw, bh = w * lebar, h * tinggi
            px, py = bw * padding, bh * padding
            x1 = max(0.0, (cx * lebar) - bw / 2 - px)
            y1 = max(0.0, (cy * tinggi) - bh / 2 - py)
            x2 = min(float(lebar), (cx * lebar) + bw / 2 + px)
            y2 = min(float(tinggi), (cy * tinggi) + bh / 2 + py)

            if x2 - x1 < 8 or y2 - y1 < 8:
                continue  # terlalu kecil untuk dikenali apa pun

            potongan.append(
                Crop(
                    crop_id=f"{stem}#{i:03d}",
                    source_image=stem,
                    source_group=source_group(stem),
                    tree_index=i,
                    label=class_names[indeks],
                    x1=round(x1, 1),
                    y1=round(y1, 1),
                    x2=round(x2, 1),
                    y2=round(y2, 1),
                )
            )

    return potongan, pembagian


def manifest_csv(crops: list[Crop], assignment: dict[str, str]) -> str:
    """Manifest yang menyertai dataset.

    Tanpa ini, sebuah potongan hanya berupa berkas gambar di dalam folder kelas
    — tidak ada cara menelusurinya kembali ke kotak mana pada citra mana, dan
    tidak ada cara membuktikan tidak terjadi kebocoran antar-split.
    """
    baris = [
        "crop_id,split,source_image,source_group,tree_index,label,x1,y1,x2,y2"
    ]
    for c in crops:
        baris.append(
            f"{c.crop_id},{assignment.get(c.source_group, '')},{c.source_image},"
            f"{c.source_group},{c.tree_index},{c.label},{c.x1},{c.y1},{c.x2},{c.y2}"
        )
    return "\n".join(baris) + "\n"


def leakage_report(crops: list[Crop], assignment: dict[str, str]) -> dict:
    """Bukti bahwa tidak ada sumber yang muncul di lebih dari satu split.

    Dihitung, bukan diasumsikan: pembagian yang benar harus dapat ditunjukkan,
    bukan sekadar dipercaya karena kodenya terlihat benar.
    """
    split_per_kelompok: dict[str, set[str]] = {}
    for c in crops:
        split_per_kelompok.setdefault(c.source_group, set()).add(
            assignment.get(c.source_group, "")
        )

    bocor = {g: sorted(s) for g, s in split_per_kelompok.items() if len(s) > 1}

    per_split: dict[str, dict[str, int]] = {s: {} for s in SPLITS}
    for c in crops:
        s = assignment.get(c.source_group)
        if s:
            per_split[s][c.label] = per_split[s].get(c.label, 0) + 1

    return {
        "groups": len(split_per_kelompok),
        "crops": len(crops),
        "leaked_groups": bocor,
        "per_split": per_split,
        "split_sizes": {s: sum(v.values()) for s, v in per_split.items()},
    }
