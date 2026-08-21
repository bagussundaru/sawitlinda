"""Penyusunan dataset YOLO dengan split bebas kebocoran (B0)."""

import io
import zipfile

import pytest
from PIL import Image

from app.training import datasets


def _jpeg() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (512, 512), "green").save(buf, "JPEG")
    return buf.getvalue()


def _arsip(
    mosaik=("44000_16000", "52000_20000"),
    ubin_per_mosaik=4,
    bingkai=12,
) -> bytes:
    """Arsip Roboflow tiruan: beberapa mosaik dan sejumlah bingkai."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("data.yaml", "nc: 4\nnames: ['dead', 'healthy', 'small', 'yellow']\n")
        # Split bawaan sengaja dibuat BOCOR: tiap mosaik tersebar ke train & test.
        for m in mosaik:
            for i in range(ubin_per_mosaik):
                split = "train" if i % 2 == 0 else "test"
                stem = f"{m}_{i}_{i}_jpg.rf.{i:032x}"
                zf.writestr(f"{split}/images/{stem}.jpg", _jpeg())
                zf.writestr(f"{split}/labels/{stem}.txt", "1 0.5 0.5 0.2 0.2\n")
        for i in range(bingkai):
            split = ("train", "valid", "test")[i % 3]
            stem = f"DJI_{i:04d}_JPG.rf.{i:032x}"
            zf.writestr(f"{split}/images/{stem}.jpg", _jpeg())
            zf.writestr(
                f"{split}/labels/{stem}.txt", "1 0.5 0.5 0.2 0.2\n3 0.3 0.3 0.1 0.1\n"
            )
    return buf.getvalue()


def _isi(archive: bytes) -> list[str]:
    return zipfile.ZipFile(io.BytesIO(archive)).namelist()


class TestRencanaSplit:
    def test_ubin_mosaik_selalu_masuk_train(self):
        """Validation dan test hanya boleh berisi populasi yang benar-benar
        diproses aplikasi."""
        split, jenis, _ = datasets.plan_split(_arsip())

        mosaik = [s for s, j in jenis.items() if j == "mosaic"]
        assert mosaik
        assert all(split[s] == "train" for s in mosaik)

    def test_bingkai_tersebar_ke_tiga_split(self):
        split, jenis, _ = datasets.plan_split(_arsip())

        bingkai = {split[s] for s, j in jenis.items() if j == "frame"}
        assert bingkai == {"train", "val", "test"}

    def test_urutan_kelas_diambil_dari_arsip(self):
        _, _, nama = datasets.plan_split(_arsip())

        assert nama == ["dead", "healthy", "small", "yellow"]

    def test_deterministik(self):
        a = datasets.plan_split(_arsip())[0]
        b = datasets.plan_split(_arsip())[0]

        assert a == b


class TestPenyusunan:
    def test_b1_tidak_memuat_ubin_mosaik(self):
        hasil = datasets.build(_arsip(), name="B1", include_mosaic=False)

        nama = _isi(hasil.archive)
        assert not any("44000_16000" in n for n in nama)
        assert any("DJI_" in n for n in nama)

    def test_b2_memuat_ubin_mosaik_hanya_pada_train(self):
        hasil = datasets.build(_arsip(), name="B2", include_mosaic=True)

        mosaik = [n for n in _isi(hasil.archive) if "44000_16000" in n]
        assert mosaik
        assert all(n.startswith("train/") for n in mosaik)

    def test_validation_dan_test_identik_antara_b1_dan_b2(self):
        """Selisih angka B1 dan B2 hanya boleh berasal dari data latih
        tambahan; kalau test-nya berbeda, perbandingannya tidak menjawab apa
        pun."""
        b1 = datasets.build(_arsip(), name="B1", include_mosaic=False)
        b2 = datasets.build(_arsip(), name="B2", include_mosaic=True)

        def cuplik(hasil, folder):
            return sorted(n for n in _isi(hasil.archive) if n.startswith(f"{folder}/"))

        assert cuplik(b1, "valid") == cuplik(b2, "valid")
        assert cuplik(b1, "test") == cuplik(b2, "test")
        assert b1.images["val"] == b2.images["val"]
        assert b1.images["test"] == b2.images["test"]

    def test_train_b2_lebih_besar_dari_b1(self):
        b1 = datasets.build(_arsip(), name="B1", include_mosaic=False)
        b2 = datasets.build(_arsip(), name="B2", include_mosaic=True)

        assert b2.images["train"] > b1.images["train"]

    @pytest.mark.parametrize("mosaik", [True, False])
    def test_tidak_ada_kebocoran_walau_arsip_asalnya_bocor(self, mosaik):
        """Arsip uji sengaja dibuat bocor pada split bawaannya."""
        hasil = datasets.build(_arsip(), name="X", include_mosaic=mosaik)

        assert hasil.leaked_groups == {}

    def test_setiap_citra_punya_labelnya(self):
        hasil = datasets.build(_arsip(), name="B2", include_mosaic=True)

        nama = _isi(hasil.archive)
        citra = {n.rsplit("/", 1)[-1].rsplit(".", 1)[0] for n in nama if "/images/" in n}
        label = {n.rsplit("/", 1)[-1].rsplit(".", 1)[0] for n in nama if "/labels/" in n}
        assert citra == label

    def test_data_yaml_menjaga_urutan_kelas(self):
        hasil = datasets.build(_arsip(), name="B1", include_mosaic=False)

        isi = zipfile.ZipFile(io.BytesIO(hasil.archive)).read("data.yaml").decode()
        assert "names: ['dead', 'healthy', 'small', 'yellow']" in isi

    def test_manifest_memuat_baris_per_citra(self):
        hasil = datasets.build(_arsip(), name="B2", include_mosaic=True)

        csv = zipfile.ZipFile(io.BytesIO(hasil.archive)).read("split-manifest.csv").decode()
        baris = csv.strip().split("\n")
        assert baris[0] == "image,split,source_group,source_type,boxes"
        assert len(baris) - 1 == sum(hasil.images.values())

    def test_catatan_split_ikut_di_dalam_arsip(self):
        """Arsip yang berpindah tangan harus dapat dibaca cara pembagiannya."""
        hasil = datasets.build(_arsip(), name="B2", include_mosaic=True)

        catatan = zipfile.ZipFile(io.BytesIO(hasil.archive)).read("SPLIT.md").decode()
        assert "bebas kebocoran" in catatan
        assert "Kelompok sumber yang muncul di lebih dari satu split: **0**" in catatan

    def test_jumlah_kotak_dihitung_per_kelas(self):
        hasil = datasets.build(_arsip(), name="B1", include_mosaic=False)

        assert sum(sum(v.values()) for v in hasil.boxes.values()) > 0
        assert all(k in hasil.class_names for v in hasil.boxes.values() for k in v)
