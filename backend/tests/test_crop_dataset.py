"""Dataset potongan untuk classifier tahap kedua (C0).

Yang diuji di sini bersifat metodologis: potongan berasal dari kotak ground
truth, split-nya diwarisi dari arsip deteksi (bukan dihitung ulang), dan test
Swin karena itu berasal dari bingkai yang sama persis dengan test detektornya.
"""

import io
import zipfile

import pytest
from PIL import Image

from app.training import crop_dataset


def _jpeg(w=512, h=512, warna="green") -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), warna).save(buf, "JPEG")
    return buf.getvalue()


def _arsip_deteksi(
    per_split=(("train", 4), ("valid", 2), ("test", 2)),
    kotak="1 0.5 0.5 0.2 0.2\n2 0.3 0.3 0.05 0.05\n",
) -> bytes:
    """Arsip B1 tiruan: bingkai DJI sudah terbagi ke folder split."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("data.yaml", "nc: 4\nnames: ['dead', 'healthy', 'small', 'yellow']\n")
        n = 0
        for split, jumlah in per_split:
            for _ in range(jumlah):
                stem = f"DJI_{n:04d}_JPG.rf.{n:032x}"
                zf.writestr(f"{split}/images/{stem}.jpg", _jpeg())
                zf.writestr(f"{split}/labels/{stem}.txt", kotak)
                n += 1
    return buf.getvalue()


def _isi(archive: bytes) -> list[str]:
    return zipfile.ZipFile(io.BytesIO(archive)).namelist()


class TestSplitDiwarisi:
    def test_potongan_mengikuti_folder_arsip_sumber(self):
        """Split tidak dihitung ulang. Kalau meleset, potongan test Swin tidak
        lagi berasal dari bingkai yang sama dengan test detektornya."""
        d = crop_dataset.build(_arsip_deteksi())

        # 2 kotak per citra, 4/2/2 citra.
        assert d.totals == {"train": 8, "val": 4, "test": 4}

    def test_folder_valid_dipetakan_ke_val(self):
        """Roboflow memakai `valid`, sisa pipeline memakai `val`."""
        d = crop_dataset.build(_arsip_deteksi())

        assert any(n.startswith("val/") for n in _isi(d.archive))
        assert not any(n.startswith("valid/") for n in _isi(d.archive))

    def test_tidak_ada_kebocoran_bila_sumbernya_bersih(self):
        d = crop_dataset.build(_arsip_deteksi())

        assert d.leaked_groups == {}

    def test_kebocoran_arsip_sumber_dilaporkan_bukan_disembunyikan(self):
        """Kalau satu bingkai muncul di dua split, itu harus terlihat."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("data.yaml", "nc: 4\nnames: ['dead','healthy','small','yellow']\n")
            # Bingkai yang SAMA, dua kali diekspor Roboflow dengan sidik berbeda.
            for i, split in enumerate(("train", "test")):
                stem = f"DJI_0001_JPG.rf.{i:032x}"
                zf.writestr(f"{split}/images/{stem}.jpg", _jpeg())
                zf.writestr(f"{split}/labels/{stem}.txt", "1 0.5 0.5 0.2 0.2\n")

        d = crop_dataset.build(buf.getvalue())

        assert d.leaked_groups
        assert "ADA KEBOCORAN" in zipfile.ZipFile(
            io.BytesIO(d.archive)
        ).read("SPLIT.md").decode()


class TestPelabelan:
    def test_urutan_kelas_dibaca_dari_data_yaml(self):
        d = crop_dataset.build(_arsip_deteksi())

        assert d.class_names == ["dead", "healthy", "small", "yellow"]

    def test_potongan_disimpan_di_folder_kelasnya(self):
        """indeks 1 -> healthy, indeks 2 -> small menurut data.yaml."""
        d = crop_dataset.build(_arsip_deteksi())
        isi = _isi(d.archive)

        assert any(n.startswith("train/healthy/") for n in isi)
        assert any(n.startswith("train/small/") for n in isi)

    def test_arsip_tanpa_names_ditolak(self):
        """Menebak urutan kelas sekali saja sudah cukup untuk menukar label
        seluruh dataset tanpa ada yang menyadarinya."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("data.yaml", "nc: 4\n")
            zf.writestr("train/images/DJI_0001.jpg", _jpeg())
            zf.writestr("train/labels/DJI_0001.txt", "1 0.5 0.5 0.2 0.2\n")

        with pytest.raises(ValueError):
            crop_dataset.build(buf.getvalue())


class TestGeometri:
    def test_kotak_dilebarkan_oleh_padding(self):
        """Kotak 0.2 dari 512 px = 102.4 px, ditambah 10% tiap sisi."""
        d = crop_dataset.build(_arsip_deteksi(kotak="1 0.5 0.5 0.2 0.2\n"))
        baris = crop_dataset.read_manifest(d.archive)[0]

        assert float(baris["raw_w"]) == pytest.approx(102.4, abs=0.1)
        assert float(baris["pad_w"]) == pytest.approx(102.4 * 1.2, abs=0.2)

    def test_ukuran_asli_dicatat_terpisah_dari_yang_dilebarkan(self):
        """Heuristik ukuran harus diukur pada kotak GT apa adanya; kotak yang
        sudah dilebarkan 20% mengukur hal lain."""
        d = crop_dataset.build(_arsip_deteksi())
        baris = crop_dataset.read_manifest(d.archive)[0]

        assert float(baris["pad_w"]) > float(baris["raw_w"])

    def test_kotak_terlalu_kecil_dilewati(self):
        d = crop_dataset.build(_arsip_deteksi(kotak="1 0.5 0.5 0.005 0.005\n"))

        assert sum(d.totals.values()) == 0

    def test_potongan_berukuran_seragam(self):
        """Swin menuntut masukan berukuran tetap."""
        d = crop_dataset.build(_arsip_deteksi(), ukuran=224)
        z = zipfile.ZipFile(io.BytesIO(d.archive))
        nama = next(n for n in z.namelist() if n.endswith(".jpg"))

        with Image.open(io.BytesIO(z.read(nama))) as gambar:
            assert gambar.size == (224, 224)

    def test_kotak_di_tepi_tidak_keluar_dari_citra(self):
        d = crop_dataset.build(_arsip_deteksi(kotak="1 0.02 0.02 0.1 0.1\n"))
        baris = crop_dataset.read_manifest(d.archive)[0]

        assert float(baris["x1"]) >= 0
        assert float(baris["y1"]) >= 0


class TestHashSplit:
    def test_hash_berbeda_antar_split(self):
        d = crop_dataset.build(_arsip_deteksi())

        assert len({d.split_hashes[s] for s in ("train", "val", "test")}) == 3

    def test_hash_stabil_untuk_masukan_yang_sama(self):
        a = crop_dataset.build(_arsip_deteksi())
        b = crop_dataset.build(_arsip_deteksi())

        assert a.split_hashes == b.split_hashes

    def test_hash_berubah_bila_isinya_berubah(self):
        """Enam bulan kemudian, inilah satu-satunya cara memastikan angkanya
        diukur pada potongan test yang sama."""
        a = crop_dataset.build(_arsip_deteksi())
        b = crop_dataset.build(_arsip_deteksi(kotak="1 0.5 0.5 0.3 0.3\n"))

        assert a.split_hashes["test"] != b.split_hashes["test"]


class TestManifest:
    def test_setiap_potongan_dapat_ditelusuri_ke_asalnya(self):
        d = crop_dataset.build(_arsip_deteksi())
        baris = crop_dataset.read_manifest(d.archive)

        assert len(baris) == sum(d.totals.values())
        satu = baris[0]
        assert satu["source_image"].startswith("DJI_")
        assert satu["source_group"]
        assert satu["split"] in {"train", "val", "test"}
